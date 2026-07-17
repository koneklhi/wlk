"""Exp-093 / Exp-101: 언어 고착 근본 수정 + short silence 언어 재감지 — 단위 테스트.

Exp-093: silence 발생 시 detected_language / first_timestamp 를 None으로 리셋해
다음 infer 에서 언어 재감지가 트리거되는지 검증한다.
Exp-101: short pause(≥0.5s) 후 1.5s 오디오 누적 시 언어 재감지 스케줄링 및 실행 검증.
"""

from unittest.mock import MagicMock

from whisperlivekit.simul_whisper.backend import (
    MIN_DURATION_REAL_SILENCE,
    MIN_DURATION_SHORT_LANG_RESET,
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
    proc._short_silence_check_at = 0.0

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
    """(2) auto 재감지 경로: language="auto" long_silence=True 시 end_silence() 후 detected_language is None.

    세션 언어 고정 도입(편집 4)으로 long_silence 리셋은 cfg.language=="auto"일 때만 None으로
    리셋된다(고정 언어면 그 언어를 유지). 이 Exp-093 테스트는 원래 auto 재감지(None 리셋)
    경로를 검증하므로 명시적으로 language="auto"를 사용한다.
    """
    proc = _make_processor_for_silence(language="auto")
    silence_duration = MIN_DURATION_REAL_SILENCE  # 정확히 임계값 = long_silence 경계
    proc.end_silence(silence_duration=silence_duration, offset=0.0)
    assert proc.model.state.detected_language is None


def test_long_silence_keeps_fixed_language():
    """(2b) 고정 경로: 고정 세션(language="ko")은 긴침묵 리셋 시 재감지가 없어 고착 방지 위해 고정 언어 유지.

    편집 5 검증 — long_silence 리셋에서 cfg.language != "auto"이면 detected_language를
    None으로 리셋하지 않고 그 고정 언어를 유지한다(auto 전용 재감지가 없어 None이면 영구 고착).
    """
    proc = _make_processor_for_silence(language="ko")
    proc.end_silence(silence_duration=MIN_DURATION_REAL_SILENCE, offset=0.0)
    assert proc.model.state.detected_language == "ko"


def test_long_silence_resets_first_timestamp():
    """(3) long_silence=True 시 end_silence() 후 state.first_timestamp is None."""
    proc = _make_processor_for_silence()
    silence_duration = MIN_DURATION_REAL_SILENCE + 1  # 임계값 초과
    proc.end_silence(silence_duration=silence_duration, offset=0.0)
    assert proc.model.state.first_timestamp is None


# ── short_silence 경로 (false positive 방어) ───────────────────────────────────

def test_short_silence_does_not_reset_detected_language():
    """(4) short_silence=True 시 state.detected_language 가 즉시 변경되지 않음."""
    proc = _make_processor_for_silence()
    original_lang = proc.model.state.detected_language  # "ko"
    silence_duration = MIN_DURATION_REAL_SILENCE - 1  # 임계값 미만
    proc.end_silence(silence_duration=silence_duration, offset=0.0)
    assert proc.model.state.detected_language == original_lang


# ── Exp-101: short silence 언어 재감지 스케줄링 ────────────────────────────────

def test_short_silence_schedules_lang_check_for_auto():
    """(5) auto 언어 + ≥0.5s pause → _short_silence_check_at = end + 1.5."""
    proc = _make_processor_for_silence(language="auto")
    proc.end = 5.0
    proc.end_silence(silence_duration=MIN_DURATION_SHORT_LANG_RESET, offset=0.0)
    assert proc._short_silence_check_at == 5.0 + MIN_DURATION_SHORT_LANG_RESET + 1.5


def test_short_silence_no_schedule_for_fixed_language():
    """(6) 고정 언어(ko) + ≥0.5s pause → _short_silence_check_at 미설정."""
    proc = _make_processor_for_silence(language="ko")
    proc.end_silence(silence_duration=MIN_DURATION_SHORT_LANG_RESET, offset=0.0)
    assert proc._short_silence_check_at == 0.0


def test_short_silence_no_schedule_below_threshold():
    """(7) auto 언어 + <0.5s pause → _short_silence_check_at 미설정."""
    proc = _make_processor_for_silence(language="auto")
    proc.end_silence(silence_duration=MIN_DURATION_SHORT_LANG_RESET - 0.1, offset=0.0)
    assert proc._short_silence_check_at == 0.0


def test_long_silence_clears_short_silence_schedule():
    """(8) long_silence 발생 시 _short_silence_check_at 초기화."""
    proc = _make_processor_for_silence(language="auto")
    proc._short_silence_check_at = 99.0
    proc.end_silence(silence_duration=MIN_DURATION_REAL_SILENCE, offset=0.0)
    assert proc._short_silence_check_at == 0.0


def test_check_short_silence_language_triggers_tokenizer_update():
    """(9) detect_current_language가 다른 언어 반환 시 _apply_detected_language(new_lang) 호출.

    (배선 버그 수정) 기존엔 create_tokenizer+init_context만 직접 호출하고 init_tokens()를 누락해
    SOT 언어 토큰이 갱신되지 않았다. 이제 _apply_detected_language 경유로 init_tokens까지 실행된다.
    """
    proc = _make_processor_for_silence(language="auto")
    proc.model.state.detected_language = "en"
    proc.model.detect_current_language = MagicMock(return_value="ko")

    proc._check_short_silence_language()

    proc.model._apply_detected_language.assert_called_once_with("ko")


def test_check_short_silence_language_no_action_if_same():
    """(10) detect_current_language가 현재 언어와 동일 시 아무 액션 없음."""
    proc = _make_processor_for_silence(language="auto")
    proc.model.state.detected_language = "ko"
    proc.model.detect_current_language = MagicMock(return_value="ko")

    proc._check_short_silence_language()

    proc.model.create_tokenizer.assert_not_called()
    proc.model.init_context.assert_not_called()


def test_check_short_silence_language_no_action_if_none():
    """(11) detect_current_language가 None 반환(확신도 미달) 시 아무 액션 없음."""
    proc = _make_processor_for_silence(language="auto")
    proc.model.state.detected_language = "en"
    proc.model.detect_current_language = MagicMock(return_value=None)

    proc._check_short_silence_language()

    proc.model.create_tokenizer.assert_not_called()
    assert proc.model.state.detected_language == "en"
