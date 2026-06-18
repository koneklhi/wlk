"""Exp-093: 언어 고착 근본 수정 — 단위 테스트.

silence 발생 시 detected_language / first_timestamp 를 None으로 리셋해
다음 infer 에서 언어 재감지가 트리거되는지 검증한다.
"""

from unittest.mock import MagicMock

from whisperlivekit.simul_whisper.backend import (
    MIN_DURATION_REAL_SILENCE,
    SimulStreamingOnlineProcessor,
)


def _make_processor_for_silence(language="ko"):
    """end_silence() 테스트용 최소 프로세서 생성 (모델 로드 없이)."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc.buffer = []
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc.end = 0.0
    proc._consecutive_char_repeat = 0

    model = MagicMock()
    model.cfg.language = language
    # state mock: detected_language / first_timestamp 를 실제 속성처럼 설정
    model.state = MagicMock()
    model.state.detected_language = "ko"
    model.state.first_timestamp = 1.5
    proc.model = model
    return proc


# ── 상수 검증 ─────────────────────────────────────────────────────────────────

def test_min_duration_real_silence_constant():
    """(1) MIN_DURATION_REAL_SILENCE 가 2로 변경됐는지 확인."""
    assert MIN_DURATION_REAL_SILENCE == 2


# ── long_silence 경로 ──────────────────────────────────────────────────────────

def test_long_silence_resets_detected_language():
    """(2) long_silence=True 시 end_silence() 후 state.detected_language is None."""
    proc = _make_processor_for_silence()
    silence_duration = MIN_DURATION_REAL_SILENCE  # 정확히 임계값 = long_silence 경계
    proc.end_silence(silence_duration=silence_duration, offset=0.0)
    assert proc.model.state.detected_language is None


def test_long_silence_resets_first_timestamp():
    """(3) long_silence=True 시 end_silence() 후 state.first_timestamp is None."""
    proc = _make_processor_for_silence()
    silence_duration = MIN_DURATION_REAL_SILENCE + 1  # 임계값 초과
    proc.end_silence(silence_duration=silence_duration, offset=0.0)
    assert proc.model.state.first_timestamp is None


# ── short_silence 경로 (false positive 방어) ───────────────────────────────────

def test_short_silence_does_not_reset_detected_language():
    """(4) short_silence=True 시 state.detected_language 가 변경되지 않음."""
    proc = _make_processor_for_silence()
    original_lang = proc.model.state.detected_language  # "ko"
    silence_duration = MIN_DURATION_REAL_SILENCE - 1  # 임계값 미만
    proc.end_silence(silence_duration=silence_duration, offset=0.0)
    assert proc.model.state.detected_language == original_lang
