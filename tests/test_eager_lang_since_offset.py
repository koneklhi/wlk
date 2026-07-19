"""CASE2 경계2(Exp-case2-frontloss) — detect_current_language since_offset 유닛 테스트.

배경: new_speaker()의 eager 언어감지(detect_current_language(window_secs=1.5))는 화자전환
경계 시각과 무관하게 버퍼 끝에서 무조건 마지막 1.5초를 자른다. 화자전환 직후(새 화자
오디오가 아직 0.1~0.5s밖에 안 쌓인 시점)엔 이 1.5s 창의 대부분이 이전 화자(예: EN) 오디오라서
새 화자(예: KO) 대신 이전 화자 언어로 고신뢰 오판된다(ytn2 실측 로그: spk=0→1 시점에
eager=en, det_before=en — "Thank you" 필러 폭주로 이어지는 직접 원인).

수정: detect_current_language에 선택적 since_offset(버퍼 시작 기준 상대 초) 파라미터를 추가해,
주어지면 그 시각 이전 오디오는 배제하고(최근 window_secs로는 여전히 캡) 감지한다.
new_speaker()는 화자전환 절대시각(change_speaker.start)을 버퍼 시작(global_time_offset,
refresh 전이므로 유효)기준 상대 오프셋으로 환산해 넘긴다.
"""

from unittest.mock import MagicMock

import pytest
import torch

from whisperlivekit.simul_whisper.backend import SimulStreamingOnlineProcessor
from whisperlivekit.simul_whisper.decoder_state import DecoderState
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt
from whisperlivekit.timed_objects import ChangeSpeaker

SR = 16000


def _make_lang_model(total_secs: float, global_offset: float = 0.0):
    """detect_current_language 단위 테스트용 최소 AlignAtt 인스턴스.

    _encode/lang_id를 모킹해 실제 인코더/언어감지 모델 없이 슬라이싱 로직만 검증한다.
    captured['len']에 _encode에 전달된 오디오 샘플 길이를 기록한다.
    """
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.segments = [torch.zeros(int(total_secs * SR))]
    model.state.global_time_offset = global_offset
    model.state.cumulative_time_offset = 0.0

    captured = {}

    def _encode(input_segments):
        captured["len"] = len(input_segments)
        return "encoder_feature", None

    model._encode = _encode
    model.lang_id = MagicMock(return_value=(None, [{"en": 0.99}]))
    return model, captured


# ── detect_current_language: since_offset 슬라이싱 ────────────────────────────

def test_since_offset_none_keeps_existing_window_behavior():
    """(1) since_offset=None(기존 호출부 하위호환) → 마지막 window_secs 그대로 사용."""
    model, captured = _make_lang_model(total_secs=4.0)
    result = model.detect_current_language(window_secs=1.5, min_prob=0.90)
    assert result == "en"
    assert captured["len"] == int(1.5 * SR)


def test_since_offset_recent_boundary_restricts_to_new_speaker_audio():
    """(2) 핵심 수정 검증: 화자전환이 window_secs보다 최근(예: 0.5s 전)이면
    since_offset 이후(0.5s)만 사용 — 1.5s 전체가 아니라 0.5s만 인코딩돼야 한다.

    이게 ytn2 경계2 버그의 직접 수정: 화자전환 후 0.5s밖에 안 쌓였는데 1.5s 창으로
    감지하면 앞의 1.0s(이전 화자=EN)가 섞여 오판된다.
    """
    model, captured = _make_lang_model(total_secs=4.0)
    # 버퍼 총 4.0s, 화자전환은 버퍼 상대 3.5s 지점(끝에서 0.5s 전)
    result = model.detect_current_language(window_secs=1.5, min_prob=0.90, since_offset=3.5)
    assert result == "en"
    assert captured["len"] == int(0.5 * SR), (
        f"since_offset 이후(0.5s)만 써야 하는데 {captured['len']/SR:.2f}s 사용됨 — "
        "이전 화자 오디오가 섞여 있을 위험"
    )


def test_since_offset_old_boundary_still_capped_by_window_secs():
    """(3) since_offset이 window_secs보다 더 과거면 window_secs 캡이 우선(하한 유지).

    화자전환이 오래 전(2.5s 전)이면 최근 1.5s만 쓰는 기존 상한 동작을 유지해야 한다
    (since_offset은 하한만 당길 뿐, 상한을 넓히면 안 됨).
    """
    model, captured = _make_lang_model(total_secs=4.0)
    result = model.detect_current_language(window_secs=1.5, min_prob=0.90, since_offset=0.5)
    assert result == "en"
    assert captured["len"] == int(1.5 * SR)


def test_since_offset_at_buffer_end_returns_none_without_encoding():
    """(4) since_offset이 버퍼 끝과 같으면(새 화자 오디오 아직 0s) 빈 슬라이스 → 인코딩 생략, None 반환."""
    model, captured = _make_lang_model(total_secs=4.0)
    result = model.detect_current_language(window_secs=1.5, min_prob=0.90, since_offset=4.0)
    assert result is None
    assert "len" not in captured, "빈 오디오로 _encode가 호출되면 안 됨"


# ── new_speaker(): since_offset 배선 ──────────────────────────────────────────

def _make_processor(detected_language="ko", lang_before_reset=None):
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
    model.detect_current_language = MagicMock(return_value=None)
    proc.model = model
    return proc


def test_new_speaker_passes_buffer_relative_since_offset():
    """(5) new_speaker: change_speaker.start(절대) - global_time_offset(버퍼시작 절대) =
    버퍼상대 오프셋을 since_offset으로 detect_current_language에 전달해야 한다.
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.global_time_offset = 8.0  # 버퍼 시작 = 절대 8.0s (refresh 전이므로 아직 유효)
    cs = ChangeSpeaker(start=9.2, speaker=1)  # 화자전환 절대 9.2s → 버퍼상대 1.2s

    proc.new_speaker(cs)

    proc.model.detect_current_language.assert_called_once_with(
        window_secs=1.5, min_prob=0.85, since_offset=pytest.approx(1.2),
    )


# ── Exp-189: eager 언어체크 버스트(diar flip-flop) 쿨다운 ─────────────────────

def test_new_speaker_skips_eager_when_within_cooldown_of_last_check():
    """(6) kor1 실측(Exp-189) 규명: Sortformer가 단일화자 파일에서도 순간적으로
    speaker 0↔1을 반복 오귀속하는 노이즈(Exp-188과 동일 근원)가 있고, 매 flip마다
    new_speaker()의 eager 언어감지가 다시 실행된다. 버스트 중 새 화자 오디오가
    거의 안 쌓인 채(연쇄 flip일수록 창이 더 좁아짐) 반복 재시도되면서 우연히 고신뢰
    오탐(en, p=0.95→1.00→0.99 연속)이 나오면 그 상태가 버스트 내내 유지돼 실제
    영어 환각("We have a lot of work...")까지 이어졌다(R2, WER 20.5%→47.4%).

    직전 eager 체크로부터 EAGER_LANG_COOLDOWN_SECS 이내에 또 화자전환 이벤트가 오면
    eager 재감지 자체를 건너뛴다(encoder forward 생략) — detected_language는 여전히
    None으로 리셋되므로, infer()의 표준 eager_lang_detect 폴백(더 많은 표본 확보 후
    판정하는 기존 안전 경로)이 대신 처리한다.
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.global_time_offset = 8.0
    proc.model.detect_current_language = MagicMock(return_value="en")

    proc.end = 9.5
    cs1 = ChangeSpeaker(start=9.4, speaker=1)
    proc.new_speaker(cs1)
    assert proc.model.detect_current_language.call_count == 1

    # 0.4s 뒤 재전환(버스트) — 쿨다운(기본 1.5s) 이내이므로 eager 재감지를 건너뛰어야 한다.
    proc.end = 9.9
    cs2 = ChangeSpeaker(start=9.8, speaker=0)
    proc.new_speaker(cs2)
    assert proc.model.detect_current_language.call_count == 1, (
        "쿨다운 이내 재호출은 eager 재감지를 건너뛰어야 한다"
    )


def test_new_speaker_runs_eager_again_after_cooldown_elapses():
    """(7) 쿨다운 경과 후에는 정상적으로 eager 재감지를 수행한다(회귀 방지 대조군).

    ytn2 CASE2(genuine 화자전환)처럼 다음 화자전환이 쿨다운 창 밖에서 일어나는
    정상 케이스는 이번 변경으로 영향받지 않아야 한다.
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.global_time_offset = 8.0
    proc.model.detect_current_language = MagicMock(return_value="en")

    proc.end = 9.5
    cs1 = ChangeSpeaker(start=9.4, speaker=1)
    proc.new_speaker(cs1)
    assert proc.model.detect_current_language.call_count == 1

    # 쿨다운(1.5s) 밖 — 정상적으로 다시 실행돼야 한다.
    proc.end = 11.2
    cs2 = ChangeSpeaker(start=11.1, speaker=0)
    proc.new_speaker(cs2)
    assert proc.model.detect_current_language.call_count == 2
