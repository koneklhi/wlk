"""SimulStreamingOnlineProcessor 디코더 멈춤 복구 워치독 유닛 테스트.

SimulStreaming 디코더가 연속 발화(30s+) 후 영구히 0토큰 상태(비-fire)에 빠지는 버그를
backend 통합 레이어에서 복구하는 워치독 로직만 격리해 테스트한다.

__init__은 실제 디코더를 만들어 무거우므로 __new__로 인스턴스를 만들고 속성을 수동 주입한다.
"""

import types
from unittest.mock import MagicMock

from whisperlivekit.simul_whisper.backend import (
    STALL_RECOVER_SEC,
    SimulStreamingOnlineProcessor,
)


def _make_processor(infer_return, end, language="ko"):
    """모델 로드 없이 process_iter 워치독 로직만 테스트하기 위한 최소 프로세서 생성."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc.buffer = []
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc.end = end

    model = MagicMock()
    model.cfg.language = language
    model.infer.return_value = infer_return
    proc.model = model
    return proc


def test_stall_triggers_refresh():
    """(A) 멈춤(infer가 항상 []) → 임계 초과 시 refresh_segment 발동."""
    proc = _make_processor(infer_return=[], end=5.0)

    # end=5.0: 임계(STALL_RECOVER_SEC=10.0) 미만 → refresh 호출 0회
    tokens, processed = proc.process_iter()
    assert tokens == []
    assert proc.model.refresh_segment.call_count == 0

    # end=20.0: 임계 초과 → refresh 호출 1회 + baseline 갱신
    proc.end = 20.0
    tokens, processed = proc.process_iter()
    assert tokens == []
    assert proc.model.refresh_segment.call_count == 1
    assert proc._last_emit_end == 20.0


def test_normal_emit_no_refresh():
    """(B) 정상 방출 시 refresh 안 함 + baseline = self.end."""
    word = types.SimpleNamespace(text="안녕", detected_language="ko")
    proc = _make_processor(infer_return=[word], end=12.0)
    # _filter_cross_batch_repetitions는 token.text/start 등을 사용하므로 SimpleNamespace로 충분
    word.start = 0.0
    word.end = 0.5

    tokens, processed = proc.process_iter()
    assert proc.model.refresh_segment.call_count == 0
    assert len(tokens) == 1
    assert proc._last_emit_end == proc.end


def test_stall_recover_sec_constant():
    """워치독 임계 상수가 명세대로 10.0초인지 확인."""
    assert STALL_RECOVER_SEC == 10.0
