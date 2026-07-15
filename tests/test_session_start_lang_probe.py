"""세션 초입 언어 프로브(session-start language probe) — 단위 테스트.

배경(콜드스타트 데드락): --lan auto에서 _detect_language_if_needed()는 first_timestamp
(첫 토큰 커밋) 설정 전엔 감지를 무기한 보류한다([LangDetectDeferred], Exp-093 반복폭주 방지).
그런데 미감지 상태 토크나이저 기본값이 <|en|>이라 한국어 단독 음성이 garbage로 디코드되고
QualityGate가 억제 → 토큰 커밋 불가 → first_timestamp 영원히 None → 감지 계속 보류(데드락).
그 사이 refresh/리셋이 서두 오디오를 반복 폐기해 세션 서두 25~71초가 통유실됐다(kor1).

수정: first_timestamp=None && eager_lang_detect=False일 때도 오디오 2.0s 이상 누적 시
lang_id로 감지를 시도하되, 확신도 p>=SESSION_START_LANG_MIN_PROB(0.85)일 때만 적용한다.
미달이면 적용하지 않고 다음 infer 사이클에서 재시도(무조건 적용 폴백 없음 — 틀린 언어
커밋 방지). SESSION_START_LANG_PROBE_ENABLED=False면 완전 기존 동작(짝지음 A/B 롤백).
"""

from unittest.mock import MagicMock

import torch

from whisperlivekit.simul_whisper import align_att_base
from whisperlivekit.simul_whisper.align_att_base import (
    SESSION_START_LANG_MIN_PROB,
    SESSION_START_LANG_PROBE_ENABLED,
)
from whisperlivekit.simul_whisper.decoder_state import DecoderState
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt

SR = 16000


def _make_model(total_secs, first_timestamp=None, eager=False, probs=None):
    """_detect_language_if_needed 단위 테스트용 최소 AlignAtt 인스턴스.

    lang_id/_apply_detected_language를 모킹해 실제 모델 없이 분기 로직만 검증한다.
    """
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.segments = [torch.zeros(int(total_secs * SR))]
    model.state.first_timestamp = first_timestamp
    model.state.eager_lang_detect = eager
    model.cfg = MagicMock()
    model.cfg.language = "auto"
    model.lang_id = MagicMock(return_value=(None, [probs or {"ko": 0.99, "en": 0.01}]))
    model._apply_detected_language = MagicMock()
    model.tokenizer = MagicMock()  # 기존 경로의 "Tokenizer language:" 로그 접근용
    return model


# ── ① 프로브 발동: 2.0s 이상 + p>=0.85 → 적용 ────────────────────────────────

def test_probe_applies_language_when_enough_audio_and_confident():
    """first_timestamp=None + eager=False + 2.0s 이상 누적 + p>=0.85 → 감지 적용(데드락 해소)."""
    model = _make_model(total_secs=2.5, probs={"ko": 0.99, "en": 0.01})

    model._detect_language_if_needed("encoder_feature")

    model.lang_id.assert_called_once_with("encoder_feature")
    model._apply_detected_language.assert_called_once_with("ko")


# ── ② 확신도 게이트: p<0.85 → 보류 + 재시도 가능 ─────────────────────────────

def test_probe_defers_when_low_confidence_and_can_retry():
    """p<0.85 → 적용하지 않고 보류. 상태 불변이므로 다음 infer 사이클에서 재시도된다."""
    model = _make_model(total_secs=2.5, probs={"ko": 0.60, "en": 0.40})

    model._detect_language_if_needed("encoder_feature")

    model._apply_detected_language.assert_not_called()
    assert model.state.detected_language is None

    # 다음 사이클: 여전히 미감지 상태이므로 프로브가 다시 시도해야 한다
    model._detect_language_if_needed("encoder_feature")
    assert model.lang_id.call_count == 2
    model._apply_detected_language.assert_not_called()


# ── ③ 오디오 미충족: 2.0s 미만 → 보류 ─────────────────────────────────────────

def test_probe_defers_below_two_seconds():
    """2.0s 미만 누적 → 프로브 미발동(lang_id 호출 없음), 감지 보류."""
    model = _make_model(total_secs=1.5)

    model._detect_language_if_needed("encoder_feature")

    model.lang_id.assert_not_called()
    model._apply_detected_language.assert_not_called()


# ── ④ first_timestamp 설정 시 기존 경로 그대로 (프로브 미개입) ────────────────

def test_first_timestamp_path_unchanged_applies_regardless_of_confidence():
    """first_timestamp 설정 시 기존 경로: 2.0s 경과 후 확신도 무관 적용(기존 동작 보존).

    프로브의 p>=0.85 게이트가 커밋 기반 경로에 누출되면 안 된다 — 낮은 p로도 적용돼야 한다.
    """
    model = _make_model(total_secs=2.5, first_timestamp=0.5,
                        probs={"ko": 0.60, "en": 0.40})

    model._detect_language_if_needed("encoder_feature")

    # seconds_since_start = 2.5 - 0.5 = 2.0 >= 2.0 → 확신도 무관 적용
    model._apply_detected_language.assert_called_once_with("ko")


def test_first_timestamp_path_unchanged_waits_below_threshold():
    """first_timestamp 설정 + 경과 2.0s 미만 → 기존 경로 그대로 대기(lang_id 호출 없음)."""
    model = _make_model(total_secs=2.5, first_timestamp=1.0)

    model._detect_language_if_needed("encoder_feature")

    model.lang_id.assert_not_called()
    model._apply_detected_language.assert_not_called()


# ── ⑤ eager(화자전환) 경로 그대로 ─────────────────────────────────────────────

def test_eager_path_unchanged_early_apply_with_confidence():
    """eager_lang_detect=True + 1.5s 이상 + p>=0.85 → 기존 eager 조기 적용 그대로."""
    model = _make_model(total_secs=1.6, eager=True, probs={"en": 0.90, "ko": 0.10})

    model._detect_language_if_needed("encoder_feature")

    model._apply_detected_language.assert_called_once_with("en")
    assert model.state.eager_lang_detect is False


def test_eager_path_unchanged_waits_on_low_confidence_before_two_seconds():
    """eager + 1.5~2.0s 구간 + p<0.85 → 기존 2.0s 게이트 대기 그대로(적용 없음)."""
    model = _make_model(total_secs=1.6, eager=True, probs={"en": 0.60, "ko": 0.40})

    model._detect_language_if_needed("encoder_feature")

    model._apply_detected_language.assert_not_called()
    assert model.state.eager_lang_detect is True


# ── ⑥ 플래그 OFF → 완전 기존 동작(무기한 보류) ────────────────────────────────

def test_flag_off_preserves_indefinite_deferral(monkeypatch):
    """SESSION_START_LANG_PROBE_ENABLED=False → 오디오가 충분해도 무기한 보류(기존 동작)."""
    monkeypatch.setattr(align_att_base, "SESSION_START_LANG_PROBE_ENABLED", False)
    model = _make_model(total_secs=5.0, probs={"ko": 0.99, "en": 0.01})

    model._detect_language_if_needed("encoder_feature")

    model.lang_id.assert_not_called()
    model._apply_detected_language.assert_not_called()
    assert model.state.detected_language is None


# ── 상수 검증 ─────────────────────────────────────────────────────────────────

def test_probe_constants():
    """모듈 상수 기본값: 프로브 활성 + 확신도 게이트 0.85."""
    assert SESSION_START_LANG_PROBE_ENABLED is True
    assert SESSION_START_LANG_MIN_PROB == 0.85


# ── ⑦ no_grad 실증 (Exp-158 회귀 방지) ────────────────────────────────────────

def test_detect_language_call_site_runs_under_no_grad():
    """프로브의 lang_id 호출 지점(infer 본문)이 torch.no_grad 콘텍스트 안임을 실증.

    AlignAtt.infer는 @torch.no_grad()로 감싸이고(base infer 템플릿을 호출),
    _detect_language_if_needed는 그 본문에서 실행된다. 과거 detect_current_language가
    no_grad 밖에서 실행돼 turbo 인코더 forward가 160배 폭주한 사고(Exp-158) 회귀 방지.
    infer 본문 초입의 _apply_minseglen 시점 grad 상태를 기록해 확인한다.
    """
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.segments = [torch.zeros(SR)]
    model.cfg = MagicMock()
    grad_flags = []

    def fake_minseglen():
        grad_flags.append(torch.is_grad_enabled())
        return False  # 이후 단계 진행 없이 조기 반환 유도

    model._apply_minseglen = fake_minseglen

    result = AlignAtt.infer(model, is_last=False)

    assert result == []
    assert grad_flags == [False], "infer 본문(언어감지 호출 지점)이 no_grad 밖에서 실행됨"
