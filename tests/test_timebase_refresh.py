"""refresh_segment 절대 시간 앵커 승계(Bug 1) 오프셋 산술 유닛 테스트.

토큰 절대시각 = frame*0.02 + cumulative_time_offset + global_time_offset.
refresh_segment이 버퍼를 버릴 때 global_time_offset을 버려진 오디오 길이만큼 승계하지
않으면(과거 버그) mid-stream refresh 후 토큰 타임스탬프가 과소평가돼 문장경계 F1이
붕괴한다. 이 테스트는 승계 산술(global += cumulative + discarded)만 격리해 검증한다.

__init__은 실제 디코더를 만들어 무거우므로 __new__로 인스턴스를 만들고 속성을 수동 주입한다.
init_tokens/init_context는 텐서 모델에 의존하므로 no-op으로 대체한다.
"""

import types

import torch

from whisperlivekit.simul_whisper.decoder_state import DecoderState
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt


def _make_model(segments, cumulative, global_offset):
    """모델 로드 없이 refresh_segment만 테스트하기 위한 최소 AlignAtt 인스턴스."""
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.segments = segments
    model.state.cumulative_time_offset = cumulative
    model.state.global_time_offset = global_offset
    model.cfg = types.SimpleNamespace(rewind_threshold=200)
    # init_tokens/init_context는 텐서·토크나이저 모델에 의존 → no-op으로 대체
    model.init_tokens = lambda: None
    model.init_context = lambda: None
    return model


def test_refresh_complete_advances_global_offset():
    """complete=True: 전체 세그먼트 폐기 → global이 버려진 오디오(5s)+cumulative(2s)만큼 전진."""
    model = _make_model(
        segments=[torch.zeros(16000 * 5)],  # 5s
        cumulative=2.0,
        global_offset=10.0,
    )

    model.refresh_segment(complete=True)

    assert model.state.segments == []
    assert model.state.cumulative_time_offset == 0.0
    assert abs(model.state.global_time_offset - 17.0) < 1e-6  # 10 + 2 + 5


def test_refresh_partial_advances_global_offset():
    """complete=False: 최근 2개만 유지 → 버려진 2개(2s)+cumulative(1s)만큼 global 전진."""
    model = _make_model(
        segments=[torch.zeros(16000)] * 4,  # 각 1s, 총 4s
        cumulative=1.0,
        global_offset=0.0,
    )

    model.refresh_segment(complete=False)

    assert len(model.state.segments) == 2
    assert model.state.cumulative_time_offset == 0.0
    assert abs(model.state.global_time_offset - 3.0) < 1e-6  # 0 + 1 + discarded 2
