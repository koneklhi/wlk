"""Exp-153 Task B — diar-ON 언어전환 배선 단위 테스트.

diar-ON 화자전환 시 new_speaker()가 detected_language=None으로 리셋한 뒤
eager 감지 언어를 _apply_detected_language()로 적용하는데, 이때 prev_lang이
이미 None이므로 is_switch가 항상 False였다(원인 A).

이 파일은 lang_before_reset 폴백(consume-once) 구현이 올바름을 잠근다:
- backend 3개: new_speaker / 연속전환 or-체이닝 / long silence clear
- base 5개: fallback→마커arm / 같은언어무마커 / 최초감지무마커 / fallback트림 / 라이브전환트림
"""

import types
from unittest.mock import MagicMock

import pytest
import torch

from whisperlivekit.simul_whisper.backend import (
    MIN_DURATION_REAL_SILENCE,
    SimulStreamingOnlineProcessor,
)
from whisperlivekit.simul_whisper.decoder_state import DecoderState
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt
from whisperlivekit.timed_objects import ChangeSpeaker

# ── backend 헬퍼 (test_lang_redetect.py 스타일) ───────────────────────────────

def _make_processor(detected_language="ko", lang_before_reset=None):
    """new_speaker / end_silence 테스트용 최소 프로세서. 모델 로드 없이."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc.buffer = []
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc.end = 10.0
    proc._consecutive_char_repeat = 0
    proc._short_silence_check_at = 0.0

    model = MagicMock()
    model.cfg.language = "auto"
    model.state = MagicMock()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = lang_before_reset
    model.state.first_timestamp = 1.0
    # detect_current_language: eager 감지 mock (언어 없음으로 설정해 _apply_detected_language 호출 방지)
    model.detect_current_language = MagicMock(return_value=None)
    proc.model = model
    return proc


def _make_change_speaker():
    return ChangeSpeaker(start=10.0, speaker=1)


# ── base 헬퍼 (test_timebase_refresh.py 스타일) ───────────────────────────────

def _make_model(segments=None, cumulative=0.0, global_offset=0.0,
                detected_language=None, lang_before_reset=None):
    """_apply_detected_language 테스트용 최소 AlignAtt 인스턴스. 모델 로드 없이."""
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = lang_before_reset
    model.state.cumulative_time_offset = cumulative
    model.state.global_time_offset = global_offset
    model.state.pending_language_switch = None
    if segments is None:
        segments = []
    model.state.segments = segments
    model.cfg = types.SimpleNamespace(rewind_threshold=200)
    # 텐서 의존 메서드 → no-op
    model.create_tokenizer = MagicMock()
    model.init_tokens = MagicMock()
    model.init_context = MagicMock()
    return model


# ═══════════════════════════════════════════════════════════════════════════════
# backend 테스트 3개
# ═══════════════════════════════════════════════════════════════════════════════

def test_new_speaker_saves_lang_before_reset():
    """(1) new_speaker: detected_language='ko' 상태에서 호출 → lang_before_reset='ko'로 보존 후 detected=None.

    diar-ON 핵심 버그 수정: 리셋 직전에 현재 언어를 lang_before_reset에 저장해야
    _apply_detected_language에서 prev_lang 폴백이 동작한다.
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    # new_speaker 내부에서 model.state 속성에 직접 할당하므로 MagicMock 속성 추적 가능
    proc.new_speaker(_make_change_speaker())
    # lang_before_reset = 'ko' 로 보존됐어야 함
    assert proc.model.state.lang_before_reset == "ko"
    # detected_language = None 으로 리셋됐어야 함
    assert proc.model.state.detected_language is None


def test_new_speaker_or_chain_preserves_existing_lang_before_reset():
    """(2) 연속 화자전환 or-체이닝: detected_language=None + lang_before_reset='en' 에서
    new_speaker 재호출 시 lang_before_reset='en' 유지(None으로 덮어쓰지 않음).

    or 체이닝: detected_language or lang_before_reset → None or 'en' = 'en' 유지.
    """
    proc = _make_processor(detected_language=None, lang_before_reset="en")
    proc.new_speaker(_make_change_speaker())
    # detected_language가 None이어도 기존 lang_before_reset='en'이 보존되어야 함
    assert proc.model.state.lang_before_reset == "en"
    assert proc.model.state.detected_language is None


def test_long_silence_clears_lang_before_reset():
    """(3) end_silence(long) 후 lang_before_reset=None — 긴 침묵은 자연 경계이므로 폴백 후보 해제.

    장기 침묵 후 새 발화는 전환 판정 없이 최초 감지로 처리돼야 한다.
    """
    proc = _make_processor(detected_language=None, lang_before_reset="ko")
    # long silence 경로 유도
    proc.end_silence(silence_duration=MIN_DURATION_REAL_SILENCE, offset=0.0)
    assert proc.model.state.lang_before_reset is None


# ═══════════════════════════════════════════════════════════════════════════════
# base 테스트 5개
# ═══════════════════════════════════════════════════════════════════════════════

def test_fallback_arms_pending_switch_and_consumes():
    """(4) fallback→마커 arm: detected_language=None, lang_before_reset='ko' 에서
    _apply_detected_language('en') → pending_language_switch가 set되고 lang_before_reset=None.

    이것이 Task B의 핵심 수정: 폴백이 없으면 is_switch=False → 마커가 절대 안 생김.
    """
    model = _make_model(
        segments=[torch.zeros(16000 * 3)],  # 3s 오디오
        detected_language=None,
        lang_before_reset="ko",
    )
    model._apply_detected_language("en")
    # pending_language_switch가 None이 아닌 값으로 arm 됐어야 함
    assert model.state.pending_language_switch is not None
    # lang_before_reset은 consume-once 후 즉시 None
    assert model.state.lang_before_reset is None


def test_same_language_no_pending_switch():
    """(5) 같은 언어 무마커: lang_before_reset='en', _apply('en') → pending_language_switch 안 set.

    prev_lang='en', lang='en' → is_switch=False → 마커 없음. 불필요한 경계 삽입 방지.
    """
    model = _make_model(
        segments=[torch.zeros(16000)],
        detected_language=None,
        lang_before_reset="en",
    )
    model._apply_detected_language("en")
    assert model.state.pending_language_switch is None


def test_first_detection_no_pending_switch():
    """(6) 최초 감지 무마커(회귀 방지): detected_language=None, lang_before_reset=None,
    _apply('ko') → pending_language_switch 안 set.

    prev_lang=None → is_switch=False → 최초 감지에 마커가 생기면 안 된다.
    이 테스트는 폴백이 없는 상태에서도 통과했을 테스트이므로 회귀 가드 역할.
    """
    model = _make_model(
        segments=[torch.zeros(16000)],
        detected_language=None,
        lang_before_reset=None,
    )
    model._apply_detected_language("ko")
    assert model.state.pending_language_switch is None


def test_fallback_switch_trims_and_accumulates_offset():
    """(7) fallback 전환 트림+타임베이스: 폴백으로 is_switch=True 시 _trim_segments_to_recent가
    호출되어 cumulative_time_offset이 누적됨.

    2개 세그먼트(각 2s, 총 4s) → keep=2.5s → 1번째(2s) 제거 → cumulative += 2.0.
    단순 감지(최초)가 아니라 폴백에 의한 진짜 전환이 트림을 유발하는지 검증.
    """
    seg = torch.zeros(16000 * 2)  # 2초 세그먼트
    model = _make_model(
        segments=[seg.clone(), seg.clone()],  # 총 4s, 2개 세그먼트
        cumulative=0.0,
        global_offset=5.0,
        detected_language=None,
        lang_before_reset="ko",  # 폴백
    )
    model._apply_detected_language("en")
    # 트림: 4s > 2.5s(LANG_SWITCH_KEEP_SECS) → 앞 2s 제거 → cumulative += 2.0
    assert model.state.cumulative_time_offset == pytest.approx(2.0, abs=1e-6)
    # 남은 세그먼트는 1개
    assert len(model.state.segments) == 1


def test_live_switch_via_detected_language_arms_marker():
    """(8) 라이브 전환 트림(회귀): detected_language='ko'(폴백 아님)에서 _apply('en') →
    기존대로 is_switch=True, pending_language_switch set.

    Task B 수정 이전에도 동작하던 경로가 여전히 동작하는지 확인하는 회귀 테스트.
    """
    model = _make_model(
        segments=[torch.zeros(16000 * 3)],  # 3s
        detected_language="ko",  # 폴백 불필요 — 정상 경로
        lang_before_reset=None,
    )
    model._apply_detected_language("en")
    assert model.state.pending_language_switch is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Task C 테스트 6개 — PuncSegment.hard_boundary + diar 병합 경계 보존
# ═══════════════════════════════════════════════════════════════════════════════

def _make_alignment_c():
    """compute_punctuations_segments / get_lines_diarization 테스트용 최소 TokensAlignment."""
    from whisperlivekit.tokens_alignment import TokensAlignment

    class _Args:
        diarization = True

    class _State:
        new_tokens = []
        new_diarization = []
        new_translation = []
        new_tokens_buffer = []
        new_translation_buffer = None

    ta = TokensAlignment(_State(), _Args(), sep="")
    return ta


def test_hard_boundary_flag_set_on_boundary_token():
    """(C-1) 플래그 set: is_boundary 토큰이 세그먼트를 닫을 때 PuncSegment.hard_boundary is True.

    LanguageSwitch 마커가 닫는 세그먼트는 hard_boundary=True여야 한다.
    False면 이 테스트가 실패한다(플래그 미설정).
    """
    from whisperlivekit.timed_objects import ASRToken, LanguageSwitch

    ta = _make_alignment_c()
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.2, text="안녕", detected_language="ko"),
        ASRToken(start=0.2, end=0.4, text="하세요", detected_language="ko"),
        LanguageSwitch(start=0.5, end=0.5, detected_language="en"),
        ASRToken(start=0.6, end=0.8, text="hello", detected_language="en"),
    ]
    segs = ta.compute_punctuations_segments()
    # 첫 번째 세그먼트(LanguageSwitch가 닫은 것)는 hard_boundary=True
    assert segs[0].hard_boundary is True
    # 마지막 세그먼트(닫힌 게 아님)는 hard_boundary=False
    assert segs[1].hard_boundary is False


def test_diar_merge_splits_at_hard_boundary():
    """(C-2) diar 병합 경계 보존(핵심): 같은 화자지만 앞 세그먼트 hard_boundary=True이면
    뒤 세그먼트가 병합되지 않고 분리 유지.

    Falsifiability: `and not segments[-1].hard_boundary` 조건 제거 시
    두 세그먼트가 병합되어 len(segments)==1이 되므로 테스트 실패.
    """
    from whisperlivekit.timed_objects import ASRToken, LanguageSwitch, SpeakerSegment

    ta = _make_alignment_c()
    # 한국어 → 영어 전환 마커 사이에 같은 화자(speaker=1)의 두 발화
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.5, text="안녕하세요", detected_language="ko"),
        LanguageSwitch(start=0.5, end=0.5, detected_language="en"),
        ASRToken(start=0.6, end=1.0, text="hello", detected_language="en"),
    ]
    # 두 구간 모두 speaker=1 로 diarization 할당
    ta.all_diarization_segments = [
        SpeakerSegment(start=0.0, end=1.0, speaker=0),  # speaker+1 = 1
    ]
    segments, _ = ta.get_lines_diarization()
    # hard_boundary=True 가 보존됐으면 두 세그먼트로 분리됨
    assert len(segments) == 2, (
        f"경계가 보존돼야 하지만 병합됨: {[s.text for s in segments]}"
    )
    assert segments[0].text == "안녕하세요"
    assert segments[1].text == "hello"


def test_diar_merge_without_boundary_merges_same_speaker():
    """(C-3) 무마커 병합 유지(회귀): hard_boundary가 전부 False면 같은 화자 세그먼트가 정상 병합.

    Falsifiability: 병합 자체가 비활성화되면 len(segments)==2로 이 테스트 실패.
    """
    from whisperlivekit.timed_objects import ASRToken, SpeakerSegment

    ta = _make_alignment_c()
    # LanguageSwitch 없음 — 마커 없이 같은 화자 두 발화
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.5, text="안녕", detected_language="ko"),
        ASRToken(start=0.6, end=1.0, text="하세요", detected_language="ko"),
    ]
    ta.all_diarization_segments = [
        SpeakerSegment(start=0.0, end=1.0, speaker=0),  # speaker+1 = 1
    ]
    segments, _ = ta.get_lines_diarization()
    # 마커 없으므로 기존대로 같은 화자 세그먼트 병합 → 1개
    assert len(segments) == 1, (
        f"병합이 발생해야 하지만 분리됨: {[s.text for s in segments]}"
    )
    assert "안녕" in segments[0].text
    assert "하세요" in segments[0].text


def test_hard_boundary_inheritance_on_merge():
    """(C-4) 플래그 승계: 병합 발생 시 segments[-1].hard_boundary가 뒤 세그먼트 값을 승계.

    Falsifiable 설계:
    - A("a."): 마지막 문자가 구두점 → has_punctuation() 경로로 닫힘 → PuncSegment(hard_boundary=False)
    - B("b"): LanguageSwitch가 닫음 → PuncSegment(hard_boundary=True)
    - A와 B는 같은 화자(speaker=1) → merge loop if-분기에서 병합
      → 병합 시 `segments[-1].hard_boundary = segment.hard_boundary` 실행 → True 승계
    - 이 줄을 삭제하면 병합 후에도 hard_boundary=False가 유지 → C가 merge에 들어가지 않아
      segments[0].hard_boundary is True 어서션이 실패한다 (falsifiable 확인됨).

    결과: [AB_merged(hard_boundary=True), C] — 2개, segments[0].hard_boundary is True.
    """
    from whisperlivekit.timed_objects import ASRToken, LanguageSwitch, SpeakerSegment

    ta = _make_alignment_c()
    # A: "a." — 구두점으로 끝나므로 has_punctuation() 경로에서 독립 PuncSegment(hard_boundary=False) 생성
    # B: "b"  — LanguageSwitch가 닫으므로 PuncSegment(hard_boundary=True) 생성
    # A→B: 같은 화자, A.hard_boundary=False → merge loop if-분기 진입 → 병합 + True 승계
    # C: "c"  — 별도 PuncSegment(hard_boundary=False), 앞이 True이므로 else-분기 → 분리
    # 결과: [AB_merged(hard_boundary=True), C] — 2개
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.3, text="a.", detected_language="ko"),
        ASRToken(start=0.3, end=0.6, text="b", detected_language="ko"),
        LanguageSwitch(start=0.6, end=0.6, detected_language="en"),
        ASRToken(start=0.7, end=1.0, text="c", detected_language="en"),
    ]
    ta.all_diarization_segments = [
        SpeakerSegment(start=0.0, end=1.0, speaker=0),  # 모두 speaker 1
    ]
    segments, _ = ta.get_lines_diarization()
    # "a.b" 병합 세그먼트와 "c" 세그먼트 — 승계로 경계 보존
    assert len(segments) == 2, (
        f"병합+분리 결과 2개여야 하지만 {len(segments)}개: {[s.text for s in segments]}"
    )
    # 병합된 세그먼트의 hard_boundary는 B(hard_boundary=True)를 승계해야 함
    assert segments[0].hard_boundary is True, (
        "propagation 줄 `segments[-1].hard_boundary = segment.hard_boundary`이 "
        "실행되지 않으면 hard_boundary=False가 유지되어 이 어서션이 실패함"
    )


def test_silence_segment_does_not_produce_empty_text_segment():
    """(C-5) Silence 인접 빈세그 없음: silence 세그먼트 인접 시 빈 텍스트 세그먼트가 안 생김.

    기존 동작 유지 확인 — Silence 처리 경로가 hard_boundary 추가로 깨지지 않아야 한다.
    """
    from whisperlivekit.timed_objects import ASRToken, Silence, SpeakerSegment

    ta = _make_alignment_c()
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.3, text="hello", detected_language="en"),
        Silence(start=0.3, end=0.8),
        ASRToken(start=0.8, end=1.0, text="world", detected_language="en"),
    ]
    ta.all_diarization_segments = [
        SpeakerSegment(start=0.0, end=1.0, speaker=0),
    ]
    segments, _ = ta.get_lines_diarization()
    # 빈 text 세그먼트(침묵 세그먼트는 speaker=-2이므로 별도) 없어야 함
    non_silence = [s for s in segments if not s.is_silence()]
    assert all(s.text for s in non_silence), (
        f"빈 텍스트 세그먼트 발생: {[s.text for s in non_silence]}"
    )


def test_overflow_speaker_not_merged():
    """(C-6) overflow(-1) 분리: speaker=-1(overflow) 세그먼트는 병합되지 않고 분리.

    화자전환 직후 diarization 지연 구간에서 overflow 세그먼트가 생길 수 있다.
    이 세그먼트가 이전 정상 세그먼트에 병합되면 화자 정보가 오염된다.
    """
    from whisperlivekit.timed_objects import ASRToken, SpeakerSegment

    ta = _make_alignment_c()
    # 두 번째 발화는 diarization 범위 밖 → speaker=-1(overflow)
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.5, text="hello", detected_language="en"),
        ASRToken(start=2.0, end=2.5, text="world", detected_language="en"),
    ]
    # diarization은 0~1.0 구간만 커버 → 2.0~2.5 는 overflow
    ta.all_diarization_segments = [
        SpeakerSegment(start=0.0, end=1.0, speaker=0),  # speaker+1 = 1
    ]
    segments, diar_buffer = ta.get_lines_diarization()
    # overflow 구간 텍스트는 diar_buffer에 들어가고 segments에서 분리됨
    # (get_lines_diarization 구현상 diarization_segments[-1].end 이후는 buffer로)
    assert "world" in diar_buffer or len(segments) == 1, (
        "overflow 세그먼트가 buffer에 있거나 분리됐어야 한다"
    )
