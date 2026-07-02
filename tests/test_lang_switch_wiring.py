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
