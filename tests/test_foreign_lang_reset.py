"""단계 D-2 — ForeignLang 복구 경로의 lang_before_reset 승계 단위 테스트.

'(speaking in foreign language)' 감지 시 backend.process_iter는 방출을 garbage로
간주하고 detected_language=None으로 재감지를 트리거한다. 이때 new_speaker와
일관되게 현재 언어를 lang_before_reset로 승계해야, 재감지 후 언어가 달라질 때
_apply_detected_language의 prev_lang 폴백이 전환 마커/트림을 발동한다.

- backend 2개: 승계(ko 보존) / or-체이닝(기존 lang_before_reset 유지)
- base 1개: 승계 후 다른 언어 재감지 → is_switch=True(pending_language_switch arm)
"""

import types
from unittest.mock import MagicMock

import torch

from whisperlivekit.simul_whisper.backend import (
    STALL_RECOVER_SEC,
    SimulStreamingOnlineProcessor,
)
from whisperlivekit.simul_whisper.decoder_state import DecoderState
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt


class _FakeToken:
    """process_iter가 요구하는 최소 토큰 인터페이스: .text / .detected_language."""

    def __init__(self, text, detected_language="en"):
        self.text = text
        self.detected_language = detected_language


def _make_processor(detected_language="ko", lang_before_reset=None):
    """process_iter(ForeignLang 경로) 테스트용 최소 프로세서. 모델 로드 없이."""
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
    model.cfg.language = "auto"
    model.state = MagicMock()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = lang_before_reset
    model.state.first_timestamp = 1.0
    # infer가 foreign-language 세그먼트만 반환 → 필터 후 timestamped_words 비어 조기 return
    model.infer = MagicMock(return_value=[
        _FakeToken("(speaking in foreign language)", detected_language="en"),
    ])
    proc.model = model
    return proc


# ── 사전조건: 상수·watchdog 미발동 보장 ──────────────────────────────────────────

def test_stall_watchdog_not_triggered_in_fixture():
    """(0) 픽스처가 stall watchdog을 발동하지 않는지 — end 차이가 임계값 미만."""
    proc = _make_processor()
    assert proc.end - proc._last_emit_end < STALL_RECOVER_SEC


# ── backend 2개 ─────────────────────────────────────────────────────────────────

def test_foreign_lang_saves_lang_before_reset():
    """(1) ForeignLang: detected_language='ko' 상태에서 감지 → lang_before_reset='ko' 승계 후 detected=None.

    new_speaker와 일관된 승계. 미승계 시 _apply_detected_language의 prev_lang이
    stale해 정당한 전환이 누락된다.
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    committed, _ = proc.process_iter(is_last=False)
    # foreign 세그먼트는 방출되지 않음
    assert committed == []
    # 승계 검증
    assert proc.model.state.lang_before_reset == "ko"
    assert proc.model.state.detected_language is None
    assert proc.model.state.first_timestamp is None


def test_foreign_lang_or_chain_preserves_existing_lang_before_reset():
    """(2) or-체이닝: detected_language=None + lang_before_reset='en' 상태에서 감지 시
    lang_before_reset='en' 유지(None으로 덮어쓰지 않음).

    detected_language or lang_before_reset → None or 'en' = 'en'.
    """
    proc = _make_processor(detected_language=None, lang_before_reset="en")
    proc.process_iter(is_last=False)
    assert proc.model.state.lang_before_reset == "en"
    assert proc.model.state.detected_language is None


# ── base 1개: 승계 후 재감지 → is_switch 경로 ────────────────────────────────────

def _make_model(segments, detected_language=None, lang_before_reset=None):
    """_apply_detected_language 테스트용 최소 AlignAtt. 모델 로드 없이 (test_lang_switch_wiring 스타일)."""
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = lang_before_reset
    model.state.cumulative_time_offset = 0.0
    model.state.global_time_offset = 0.0
    model.state.pending_language_switch = None
    model.state.segments = segments
    model.cfg = types.SimpleNamespace(rewind_threshold=200)
    model.create_tokenizer = MagicMock()
    model.init_tokens = MagicMock()
    model.init_context = MagicMock()
    return model


def test_foreign_lang_succession_then_switch_arms_marker():
    """(3) 승계 후 다른 언어 재감지 → is_switch=True: ForeignLang이 lang_before_reset='ko'로
    승계한 상태(detected=None)에서 _apply_detected_language('en') 호출 →
    prev_lang='ko' 폴백으로 is_switch=True → pending_language_switch arm.

    이것이 D-2 승계의 목적: garbage 방출 후 정당한 전환 경계가 보존된다.
    미승계(lang_before_reset=None)였다면 prev_lang=None → is_switch=False → 마커 누락.
    """
    model = _make_model(
        segments=[torch.zeros(16000 * 3)],  # 3s 오디오
        detected_language=None,      # ForeignLang이 리셋한 상태
        lang_before_reset="ko",      # ForeignLang이 승계한 직전 언어
    )
    model._apply_detected_language("en")
    assert model.state.pending_language_switch is not None
    # consume-once
    assert model.state.lang_before_reset is None
