"""세션별 언어 고정(auto/ko/en) 백엔드 기능 — 단위 테스트.

검증 대상(구현 요약):
  A. `_resolve_session_cfg(language)` — None이면 전역 cfg 그대로(auto 무회귀),
     문자열이면 language 필드만 교체한 새 cfg(원본 불변). 번역 태스크는 오버라이드 무시.
  B. `online_factory` 라우팅 — simulstreaming은 SessionASRProxy로 감싸지 않고 language를
     생성자에 직접 전달, 그 외 백엔드는 SessionASRProxy로 감싼다.
  C. `new_speaker` 언어 고정 가드 — cfg.language != "auto"면 화자전환 시 언어 재감지/리셋 스킵.
  D. `process_iter` ForeignLang 가드 — 고정 세션이면 foreign 드롭은 유지하되 언어상태 리셋 스킵.
  E. `_maybe_periodic_lang_check` 가드 — cfg.language != "auto"면 즉시 return.
"""

import types
from unittest.mock import MagicMock, patch

from whisperlivekit.simul_whisper.backend import (
    _NEW_SPEAKER_KEEP_MARGIN,  # noqa: F401 (상수 존재/임포트 검증)
    _NEW_SPEAKER_MAX_KEEP,  # noqa: F401
    SimulStreamingOnlineProcessor,
)
from whisperlivekit.simul_whisper.config import AlignAttConfig
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt
from whisperlivekit.timed_objects import ChangeSpeaker

# ══════════════════════════════════════════════════════════════════════════════
# A. _resolve_session_cfg — 모델 로드 불필요(순수 로직)
# ══════════════════════════════════════════════════════════════════════════════

def _make_resolver_proc(base_language="ko", direct_english_translation=False):
    """_resolve_session_cfg 테스트용 최소 프로세서 (모델 로드 없이)."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.cfg = AlignAttConfig(language=base_language)  # 서버 전역 --lan 가정
    proc.asr.direct_english_translation = direct_english_translation
    return proc


def test_resolve_none_returns_global_cfg_identity():
    """(A1) language=None → 전역 cfg를 그 객체 그대로 반환(auto 무회귀 핵심)."""
    proc = _make_resolver_proc(base_language="ko")
    result = proc._resolve_session_cfg(None)
    assert result is proc.asr.cfg


def test_resolve_override_returns_new_cfg_and_leaves_original():
    """(A2) language="en" → language만 교체한 새 객체, 원본 cfg는 불변."""
    proc = _make_resolver_proc(base_language="ko")
    original = proc.asr.cfg
    result = proc._resolve_session_cfg("en")
    assert result.language == "en"
    assert result is not original            # 새 객체
    assert original.language == "ko"         # 원본 불변(공유 asr 오염 금지)


def test_resolve_string_auto_is_not_folded_to_none():
    """(A3) language="auto"(문자열) → 새 cfg.language == "auto" (None으로 접지 않음).

    서버 전역이 무엇이든 세션이 명시적으로 auto를 강제하는 경로.
    """
    proc = _make_resolver_proc(base_language="ko")
    result = proc._resolve_session_cfg("auto")
    assert result.language == "auto"
    assert result is not proc.asr.cfg


def test_resolve_translation_mode_ignores_override():
    """(A4) 번역 태스크(direct_english_translation=True) + base와 다른 언어 → 오버라이드 무시.

    반환이 전역 cfg 그 객체(대치 없음) — 공유 tokenizer가 전역 언어로 덮어써 충돌하므로.
    """
    proc = _make_resolver_proc(base_language="ko", direct_english_translation=True)
    result = proc._resolve_session_cfg("en")
    assert result is proc.asr.cfg            # 오버라이드 무시 → 전역 cfg 그대로


# ══════════════════════════════════════════════════════════════════════════════
# B. online_factory 라우팅 — 실제 프로세서 생성 회피(생성자 patch)
# ══════════════════════════════════════════════════════════════════════════════

def _make_factory_args(backend, backend_policy="simulstreaming"):
    return types.SimpleNamespace(backend=backend, backend_policy=backend_policy)


def test_online_factory_simulstreaming_passes_language_no_proxy():
    """(B1) simulstreaming + language="ko" → SessionASRProxy 미사용, (asr, language="ko") 직접 전달."""
    from whisperlivekit.core import online_factory
    from whisperlivekit.session_asr_proxy import SessionASRProxy

    args = _make_factory_args(backend="whisper")
    asr = MagicMock()
    with patch("whisperlivekit.simul_whisper.SimulStreamingOnlineProcessor") as MockProc:
        online_factory(args, asr, language="ko")

    MockProc.assert_called_once_with(asr, language="ko")
    # 넘어간 asr이 원본이며 SessionASRProxy로 감싸지지 않았음
    passed_asr = MockProc.call_args.args[0]
    assert passed_asr is asr
    assert not isinstance(passed_asr, SessionASRProxy)


def test_online_factory_simulstreaming_language_none():
    """(B2) simulstreaming + language=None → 생성자에 language=None 전달."""
    from whisperlivekit.core import online_factory

    args = _make_factory_args(backend="whisper")
    asr = MagicMock()
    with patch("whisperlivekit.simul_whisper.SimulStreamingOnlineProcessor") as MockProc:
        online_factory(args, asr, language=None)

    MockProc.assert_called_once_with(asr, language=None)


def test_online_factory_non_simulstreaming_wraps_proxy():
    """(B3) 비-simulstreaming(qwen3) + language="ko" → asr이 SessionASRProxy로 감싸져 전달."""
    from whisperlivekit.core import online_factory
    from whisperlivekit.session_asr_proxy import SessionASRProxy

    args = _make_factory_args(backend="qwen3")
    asr = MagicMock()
    with patch("whisperlivekit.core.OnlineASRProcessor") as MockOnline:
        online_factory(args, asr, language="ko")

    MockOnline.assert_called_once()
    passed_asr = MockOnline.call_args.args[0]
    assert isinstance(passed_asr, SessionASRProxy)


# ══════════════════════════════════════════════════════════════════════════════
# C. new_speaker 언어 고정 가드 — mock model
# ══════════════════════════════════════════════════════════════════════════════

def _make_new_speaker_proc(cfg_language, detected_language="ko"):
    """new_speaker() 테스트용 최소 프로세서 (모델 로드 없이)."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.buffer = []
    proc.end = 10.0
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc._consecutive_char_repeat = 0
    proc._script_mismatch_streak = []
    proc._anchor_repeat_window = []
    proc._script_anchor_streak = []
    proc._script_anchor_streak_start = None
    proc._script_anchor_streak_end = None

    model = MagicMock()
    model.cfg.language = cfg_language
    model.global_time_offset = 0.0
    model.segments_len = MagicMock(return_value=0.0)
    model.refresh_segment = MagicMock()
    model._apply_detected_language = MagicMock()
    # detect가 호출되면 새 언어를 반환하도록 설정 — 고정 세션에서 '호출 안 됨'을 강하게 구분
    model.detect_current_language = MagicMock(return_value="en")
    model.state = MagicMock()
    model.state.speaker = 1
    model.state.detected_language = detected_language
    model.state.lang_before_reset = None
    model.state.first_timestamp = 1.0
    proc.model = model
    return proc


def test_new_speaker_locked_skips_language_redetect():
    """(C1) 고정(cfg.language="ko"): 화자전환 시 언어 재감지/리셋 스킵.

    detect_current_language 미호출, detected_language 유지(None 아님), _apply_detected_language 미호출.
    """
    proc = _make_new_speaker_proc(cfg_language="ko", detected_language="ko")
    proc.new_speaker(ChangeSpeaker(speaker=2, start=5.0))

    proc.model.detect_current_language.assert_not_called()
    assert proc.model.state.detected_language == "ko"      # 고정 언어 유지
    proc.model._apply_detected_language.assert_not_called()


def test_new_speaker_auto_resets_and_redetects():
    """(C2) auto(cfg.language="auto"): 화자전환 시 언어 재감지 + detected_language None 리셋.

    detect_current_language 호출, detected_language None 리셋, eager 반환 언어로 _apply 호출.
    """
    proc = _make_new_speaker_proc(cfg_language="auto", detected_language="ko")
    proc.new_speaker(ChangeSpeaker(speaker=2, start=5.0))

    proc.model.detect_current_language.assert_called_once()
    assert proc.model.state.detected_language is None       # auto 재감지 arm
    proc.model._apply_detected_language.assert_called_once_with("en")
    assert proc.model.state.lang_before_reset == "ko"       # 직전 언어 승계


# ══════════════════════════════════════════════════════════════════════════════
# D. process_iter ForeignLang 가드 — mock model (test_foreign_lang_reset 스타일)
# ══════════════════════════════════════════════════════════════════════════════

class _FakeToken:
    """process_iter가 요구하는 최소 토큰 인터페이스: .text / .detected_language."""

    def __init__(self, text, detected_language="en"):
        self.text = text
        self.detected_language = detected_language


def _make_foreign_proc(cfg_language, detected_language="ko"):
    """process_iter(ForeignLang 경로) 테스트용 최소 프로세서 (모델 로드 없이)."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc.buffer = []
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc.end = 1.0  # end - _last_emit_end = 1.0 < STALL_RECOVER_SEC → stall watchdog 미발동
    proc._consecutive_char_repeat = 0
    proc._short_silence_check_at = 0.0
    proc._recent_emitted_words = []
    proc._anchor_repeat_window = []

    model = MagicMock()
    model.cfg.language = cfg_language
    model.state = MagicMock()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = None
    model.state.first_timestamp = 1.0
    model.infer = MagicMock(return_value=[
        _FakeToken("(speaking in foreign language)", detected_language="en"),
    ])
    proc.model = model
    return proc


def test_foreign_lang_locked_drops_but_keeps_language_state():
    """(D1) 고정(cfg.language="ko"): foreign 토큰은 드롭하되 언어상태는 리셋 안 함.

    committed==[](드롭 유지), detected_language="ko" 유지, lang_before_reset 불변.
    """
    proc = _make_foreign_proc(cfg_language="ko", detected_language="ko")
    committed, _ = proc.process_iter(is_last=False)

    assert committed == []                                   # foreign 드롭은 언어 무관 유지
    assert proc.model.state.detected_language == "ko"        # 고정 → 리셋 안 함
    assert proc.model.state.lang_before_reset is None        # 승계 arm 스킵


def test_foreign_lang_auto_resets_language_state():
    """(D2) 대조군 auto(cfg.language="auto"): foreign 드롭 + 언어상태 리셋(None) + 승계.

    편집 5 가드가 auto에서는 리셋을 계속 수행함을 확인(회귀 방지 대조).
    """
    proc = _make_foreign_proc(cfg_language="auto", detected_language="ko")
    committed, _ = proc.process_iter(is_last=False)

    assert committed == []
    assert proc.model.state.detected_language is None        # auto 재감지 arm
    assert proc.model.state.lang_before_reset == "ko"        # 직전 언어 승계


# ══════════════════════════════════════════════════════════════════════════════
# E. _maybe_periodic_lang_check 가드 — align_att_base
# ══════════════════════════════════════════════════════════════════════════════

def _make_periodic_model(cfg_language):
    """_maybe_periodic_lang_check 테스트용 최소 AlignAtt (모델 로드 없이)."""
    model = AlignAtt.__new__(AlignAtt)
    model.cfg = types.SimpleNamespace(language=cfg_language, periodic_lang_check_secs=4.0)
    model.state = MagicMock()
    model.state.detected_language = "ko"
    model.state.last_lang_switch_time = 0.0
    model.state.last_periodic_lang_check = 0.0
    model.detect_current_language = MagicMock(return_value="ko")
    return model


def test_periodic_lang_check_locked_returns_early():
    """(E1) 고정(cfg.language="ko"): 서두 가드로 즉시 return, detect_current_language 미호출."""
    model = _make_periodic_model(cfg_language="ko")
    model._maybe_periodic_lang_check(100.0)
    model.detect_current_language.assert_not_called()


def test_periodic_lang_check_auto_proceeds():
    """(E2) 대조군 auto(cfg.language="auto"): 조건 충족 시 detect_current_language 호출(가드 통과)."""
    model = _make_periodic_model(cfg_language="auto")
    model._maybe_periodic_lang_check(100.0)
    model.detect_current_language.assert_called_once()
