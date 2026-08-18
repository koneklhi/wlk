# -*- coding: utf-8 -*-
"""경계 보호 보존형 refresh (GOAL_BOUNDARY_QG_PRESERVE P1/P1b) 단위 테스트.

배경: QualityGate가 N회 연속 억제하면 `_on_quality_suppressed`가
`refresh_segment(complete=True)`를 불러 **오디오 버퍼를 통째로 폐기**한다. 언어/화자 전환
경계에서는 그 버퍼가 곧 새 문장의 서두 오디오라 비가역 유실이 되고, 문맥 없이 재시작한
디코더가 그 자리를 환각으로 채운다(Exp-177 Type B, 2026-08-18 재실증).

수정: 경계 보호창 이내의 첫 streak 도달에서는 **오디오를 보존하고 디코더 상태만 리셋**한다
(`refresh_segment(complete=False, keep_secs=segments_len())`). 같은 경계에서 재차 도달하면
기존 폐기로 폴백해 환각 루프 안전망(Exp-028/154 계열)을 유지한다.

전부 순수 로직 계층이라 모델 없이 검증한다(test_case1_expB.py 패턴 재사용).
"""

import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import whisperlivekit.simul_whisper.align_att_base as aab
from whisperlivekit.simul_whisper.align_att_base import AlignAttBase
from whisperlivekit.simul_whisper.decoder_state import DecoderState

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────


def _make_fake_decoder(
    decode_str: str = "garbage",
    reset_after: int = 3,
    *,
    segments_len: float = 1.5,
    stream_time: float = 10.0,
    last_boundary_event_at: float = 10.0,
    qg_preserve_used: bool = False,
    detected_language: str = "en",
    reprobe_result: object = "en",
):
    """QG streak 경로만 태우는 최소 디코더 스텁."""
    fs = SimpleNamespace(
        tokenizer=SimpleNamespace(decode=lambda h: decode_str),
        state=SimpleNamespace(
            quality_suppress_streak=0,
            detected_language=detected_language,
            last_boundary_event_at=last_boundary_event_at,
            qg_preserve_used=qg_preserve_used,
        ),
        cfg=SimpleNamespace(quality_gate_reset_after=reset_after),
    )
    fs._clean_cache = lambda: None
    fs.refresh_segment = MagicMock()
    fs.segments_len = lambda: segments_len
    fs._current_stream_time = lambda: stream_time
    fs.detect_current_language = MagicMock(return_value=reprobe_result)
    fs._apply_detected_language = MagicMock()
    # 검증 대상 실로직은 실제 구현을 바인딩한다(스텁으로 대체하지 않는다).
    for name in ("_is_punct_only", "_try_preserving_refresh", "_probe_language_for_preserve"):
        setattr(fs, name, types.MethodType(getattr(AlignAttBase, name), fs))
    return fs


def _drive_streak(fs, times: int = 3):
    for _ in range(times):
        AlignAttBase._on_quality_suppressed(fs, [1, 2])


# ─── P1: 보호창 이내 첫 streak → 오디오 보존 ──────────────────────────────────


def test_preserve_within_window_keeps_audio():
    """보호창 이내 첫 streak 도달은 complete=False + 전량 keep으로 오디오를 보존한다."""
    fs = _make_fake_decoder(segments_len=1.53, stream_time=11.0, last_boundary_event_at=10.0)
    _drive_streak(fs)
    fs.refresh_segment.assert_called_once()
    kwargs = fs.refresh_segment.call_args.kwargs
    assert kwargs.get("complete") is False, "보호창 내에서 버퍼를 폐기하면 안 된다"
    assert kwargs.get("keep_secs") == 1.53, "보존은 버퍼 전량을 유지해야 한다"
    assert fs.state.quality_suppress_streak == 0, "streak은 리셋돼야 한다"
    assert fs.state.qg_preserve_used is True, "보존 1회 소진이 기록돼야 한다"


def test_preserve_marks_used_and_second_streak_discards():
    """같은 경계에서 재차 streak 도달 → 기존 폐기(complete=True)로 폴백."""
    fs = _make_fake_decoder(segments_len=1.5, stream_time=11.0, last_boundary_event_at=10.0)
    _drive_streak(fs)          # 1회차 = 보존
    _drive_streak(fs)          # 2회차 = 폐기 폴백
    assert fs.refresh_segment.call_count == 2
    second = fs.refresh_segment.call_args_list[1]
    assert second.kwargs.get("complete") is True, "재발 시엔 기존 폐기 안전망이 살아있어야 한다"


def test_out_of_window_discards_as_before():
    """보호창 밖 streak은 현행 그대로 폐기한다(비회귀 보증)."""
    fs = _make_fake_decoder(stream_time=100.0, last_boundary_event_at=10.0)
    _drive_streak(fs)
    fs.refresh_segment.assert_called_once_with(complete=True)


def test_window_boundary_is_inclusive():
    """정확히 보호창 경계(Δt == BOUNDARY_PROTECT_SECS)는 보호 대상이다."""
    fs = _make_fake_decoder(
        stream_time=10.0 + aab.BOUNDARY_PROTECT_SECS, last_boundary_event_at=10.0
    )
    _drive_streak(fs)
    assert fs.refresh_segment.call_args.kwargs.get("complete") is False


def test_empty_buffer_falls_back_to_discard():
    """버퍼가 비어 있으면 보존할 오디오가 없으므로 기존 폐기 경로."""
    fs = _make_fake_decoder(segments_len=0.0, stream_time=11.0, last_boundary_event_at=10.0)
    _drive_streak(fs)
    fs.refresh_segment.assert_called_once_with(complete=True)


def test_session_start_is_protected_by_default():
    """세션 초입(경계 스탬프 없음, 기본 0.0)도 보호창에 포함된다 — 콜드스타트 유실 대응."""
    fs = _make_fake_decoder(stream_time=2.0, last_boundary_event_at=0.0)
    _drive_streak(fs)
    assert fs.refresh_segment.call_args.kwargs.get("complete") is False


def test_punct_only_still_not_counted():
    """구두점-only 억제는 여전히 streak 미산입 (Exp-B B2 비회귀)."""
    fs = _make_fake_decoder(". .", stream_time=11.0, last_boundary_event_at=10.0)
    _drive_streak(fs, times=5)
    assert fs.state.quality_suppress_streak == 0
    fs.refresh_segment.assert_not_called()


def test_flag_off_restores_legacy_behavior(monkeypatch):
    """롤백 플래그 OFF면 보호창 안이어도 완전히 현행(폐기) 동작."""
    monkeypatch.setattr(aab, "BOUNDARY_QG_PRESERVE_ENABLED", False)
    fs = _make_fake_decoder(stream_time=11.0, last_boundary_event_at=10.0)
    _drive_streak(fs)
    fs.refresh_segment.assert_called_once_with(complete=True)


def test_streak_below_threshold_does_not_refresh():
    """문턱 미도달 억제는 refresh를 부르지 않는다(억제 자체는 복구 가능)."""
    fs = _make_fake_decoder(stream_time=11.0, last_boundary_event_at=10.0)
    _drive_streak(fs, times=2)
    fs.refresh_segment.assert_not_called()
    assert fs.state.quality_suppress_streak == 2


# ─── P1b: 언어 확신 게이트 (보존 전 프로브) ───────────────────────────────────
#
# bong1 짝지음 N=3에서 규명된 실패모드 대응: 오디오를 보존해도 **언어 잠금이 틀린 채**
# 재디코딩되면 한국어 구간이 통째로 영어로 번역돼 나온다(은닉 번역, LMR +22.8pp).
# 기존 폐기는 단어를 죽이는 대신 그 오언어 출력도 함께 버리고 있었다. 따라서 보존은
# "이 오디오를 어떤 언어로 읽어야 하는지 아는" 경우로 한정한다.


def test_preserve_requires_confident_language():
    """언어 프로브가 확신하지 못하면(None) 보존하지 않고 기존 폐기로 폴백한다."""
    fs = _make_fake_decoder(
        stream_time=11.0, last_boundary_event_at=10.0,
        detected_language="en", reprobe_result=None,
    )
    _drive_streak(fs)
    fs.refresh_segment.assert_called_once_with(complete=True)
    assert fs.state.qg_preserve_used is False, "폴백은 보존 예산을 소진하지 않아야 한다"


def test_probe_runs_before_refresh():
    """프로브는 refresh 전에 원본 버퍼로 돌아야 한다(refresh 후엔 상태가 리셋됨)."""
    order = []
    fs = _make_fake_decoder(stream_time=11.0, last_boundary_event_at=10.0)
    fs.detect_current_language = MagicMock(side_effect=lambda **kw: order.append("probe") or "en")
    fs.refresh_segment = MagicMock(side_effect=lambda **kw: order.append("refresh"))
    _drive_streak(fs)
    assert order == ["probe", "refresh"], f"호출 순서가 잘못됨: {order}"


def test_probe_confirming_same_language_preserves():
    """프로브가 현재 언어를 확인해주면 보존하되 토크나이저는 건드리지 않는다."""
    fs = _make_fake_decoder(
        stream_time=11.0, last_boundary_event_at=10.0,
        detected_language="ko", reprobe_result="ko",
    )
    _drive_streak(fs)
    assert fs.refresh_segment.call_args.kwargs.get("complete") is False
    fs._apply_detected_language.assert_not_called()


def test_probe_correcting_language_applies_without_trim():
    """다른 언어를 확신하면 교정하되 skip_trim=True — 방금 보존한 오디오를 다시 자르면 안 된다."""
    fs = _make_fake_decoder(
        stream_time=11.0, last_boundary_event_at=10.0,
        detected_language="en", reprobe_result="ko",
    )
    _drive_streak(fs)
    assert fs.refresh_segment.call_args.kwargs.get("complete") is False
    fs._apply_detected_language.assert_called_once_with("ko", skip_trim=True)


def test_probe_not_called_on_discard_path():
    """보호창 밖 등 폐기 경로에서는 프로브를 돌리지 않는다(신규 forward 비용 회피)."""
    fs = _make_fake_decoder(stream_time=100.0, last_boundary_event_at=10.0, reprobe_result="ko")
    _drive_streak(fs)
    fs.detect_current_language.assert_not_called()


# ─── 경계 스탬프 / state 배선 ────────────────────────────────────────────────


def test_decoder_state_has_boundary_fields():
    """DecoderState에 경계 스탬프 필드가 있고 세션 초입 기본값이 0.0이다."""
    st = DecoderState()
    assert st.last_boundary_event_at == 0.0
    assert st.qg_preserve_used is False


def test_mark_boundary_event_stamps_and_resets_budget():
    """경계 이벤트 스탬프는 시각을 갱신하고 보존 예산을 되살린다."""
    fs = SimpleNamespace(
        state=SimpleNamespace(last_boundary_event_at=0.0, qg_preserve_used=True),
    )
    fs._current_stream_time = lambda: 42.0
    AlignAttBase.mark_boundary_event(fs)
    assert fs.state.last_boundary_event_at == 42.0
    assert fs.state.qg_preserve_used is False


def test_mark_boundary_event_accepts_explicit_time():
    """호출부가 스트림 시각을 직접 알면(backend self.end) 그 값을 쓴다."""
    fs = SimpleNamespace(
        state=SimpleNamespace(last_boundary_event_at=0.0, qg_preserve_used=True),
    )
    fs._current_stream_time = lambda: 42.0
    AlignAttBase.mark_boundary_event(fs, at=77.5)
    assert fs.state.last_boundary_event_at == 77.5
    assert fs.state.qg_preserve_used is False


def test_current_stream_time_is_trim_invariant():
    """스트림 시계 = global + cumulative + segments_len — 트림/refresh에 불변이어야 한다."""
    fs = SimpleNamespace(
        state=SimpleNamespace(global_time_offset=5.0, cumulative_time_offset=2.0),
    )
    fs.segments_len = lambda: 3.0
    assert AlignAttBase._current_stream_time(fs) == 10.0
    # 트림이 1초를 잘라내 cumulative로 옮겨도 총합 불변
    fs.state.cumulative_time_offset = 3.0
    fs.segments_len = lambda: 2.0
    assert AlignAttBase._current_stream_time(fs) == 10.0
