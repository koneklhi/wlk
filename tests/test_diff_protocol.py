"""델타(diff) WebSocket 출력 프로토콜 — 서버/클라이언트 왕복 정합성 테스트.

검증 대상:
  A. `DiffTracker.to_message()`가 만든 snapshot/diff 시퀀스를, 문서화된 **클라이언트 재구성
     알고리즘**(prune → common = n_lines - len(new_lines) → 꼬리 교체 → n_lines 검증)으로
     되돌리면 매 스텝 서버의 현재 lines와 정확히 일치한다.
     특히 **최근 줄이 소급 수정되는 케이스**(reconcile/침묵게이트 재개방)를 포함한다 —
     new_lines를 append로 잘못 구현하면 이 테스트가 실패해야 한다.
  B. `_resolve_ws_protocol` — 기본 full(델타 미대응 클라이언트 무수정 호환), ?mode=delta opt-in,
     diff 별칭, 잘못된 값 폴백.
"""

from typing import Any, Dict, List

import pytest

from whisperlivekit.diff_protocol import DiffTracker
from whisperlivekit.timed_objects import FrontData, Segment

# ══════════════════════════════════════════════════════════════════════════════
# 클라이언트 재구성 시뮬레이터 (docs/API_SPEC.md §2.4.3 / diff_protocol 모듈 docstring 그대로)
# ══════════════════════════════════════════════════════════════════════════════


class ClientState:
    """내장 UI(live_transcription.js)와 동일한 알고리즘의 파이썬 미러."""

    def __init__(self) -> None:
        self.lines: List[Dict[str, Any]] = []
        self.buffer_transcription = ""
        self.buffer_diarization = ""
        self.buffer_translation = ""
        self.status = ""
        self.desync = False

    def apply(self, msg: Dict[str, Any]) -> None:
        if msg["type"] == "snapshot":
            self.lines = list(msg["lines"])
        elif msg["type"] == "diff":
            pruned = msg.get("lines_pruned", 0)
            if pruned:
                del self.lines[:pruned]
            new_lines = msg.get("new_lines", [])
            common = msg["n_lines"] - len(new_lines)
            # 꼬리 교체 — append가 아니다.
            self.lines = self.lines[:common] + list(new_lines)
            if len(self.lines) != msg["n_lines"]:
                self.desync = True
        else:  # pragma: no cover - 방어
            raise AssertionError(f"unexpected message type: {msg['type']}")

        self.status = msg["status"]
        self.buffer_transcription = msg["buffer_transcription"]
        self.buffer_diarization = msg["buffer_diarization"]
        self.buffer_translation = msg["buffer_translation"]


def _seg(start: float, text: str, speaker: int = 1, finalized: bool = True) -> Segment:
    return Segment(
        start=start,
        end=start + max(len(text) * 0.1, 0.1),
        text=text,
        speaker=speaker,
        finalized=finalized,
    )


def _front(lines: List[Segment], **kw: Any) -> FrontData:
    return FrontData(
        status=kw.pop("status", "active_transcription"),
        lines=lines,
        buffer_transcription=kw.pop("buffer_transcription", ""),
        buffer_diarization=kw.pop("buffer_diarization", ""),
        buffer_translation=kw.pop("buffer_translation", ""),
        **kw,
    )


def _roundtrip(sequence: List[FrontData]) -> None:
    """시퀀스를 DiffTracker로 흘려보내며 매 스텝 클라이언트 재구성 == 서버 lines 를 확인."""
    tracker = DiffTracker()
    client = ClientState()
    for step, front in enumerate(sequence):
        msg = tracker.to_message(front)
        expected = front.to_dict()["lines"]
        client.apply(msg)
        assert not client.desync, f"step {step}: n_lines 검증 실패 (재동기 필요)"
        assert client.lines == expected, f"step {step}: 재구성 lines 불일치\n{client.lines}\n!=\n{expected}"
        assert client.buffer_transcription == front.buffer_transcription
        assert client.buffer_diarization == front.buffer_diarization
        assert client.buffer_translation == front.buffer_translation
        assert client.status == front.status


# ══════════════════════════════════════════════════════════════════════════════
# A. 왕복 정합성
# ══════════════════════════════════════════════════════════════════════════════


def test_first_message_is_snapshot_with_full_state():
    tracker = DiffTracker()
    msg = tracker.to_message(_front([_seg(0.0, "hello")]))
    assert msg["type"] == "snapshot"
    assert msg["seq"] == 1
    assert len(msg["lines"]) == 1
    assert "buffer_transcription" in msg


def test_roundtrip_pure_append():
    """줄이 뒤에 붙기만 하는 기본 흐름."""
    lines: List[Segment] = []
    seq = []
    for i in range(5):
        lines = lines + [_seg(float(i), f"line {i}")]
        seq.append(_front(list(lines)))
    _roundtrip(seq)


def test_roundtrip_last_line_retroactively_rewritten():
    """**핵심 케이스** — 이미 보낸 마지막 줄이 소급 수정된다(reconcile).

    append 구현이면 같은 줄이 두 번 쌓여 실패한다.
    """
    a, b = _seg(0.0, "첫 문장입니다."), _seg(3.0, "둘째")
    b_fixed = _seg(3.0, "둘째 문장입니다.")
    seq = [
        _front([a]),
        _front([a, b]),
        _front([a, b_fixed]),           # 꼬리 1줄 소급 수정
        _front([a, b_fixed, _seg(7.0, "셋째")]),
    ]
    _roundtrip(seq)


def test_roundtrip_multiple_tail_lines_rewritten():
    """꼬리 2줄이 한꺼번에 재조정되는 경우(경계 재조정 계층)."""
    a = _seg(0.0, "고정된 앞줄")
    seq = [
        _front([a, _seg(2.0, "가", speaker=1), _seg(4.0, "나", speaker=1)]),
        _front([a, _seg(2.0, "가나다", speaker=2), _seg(5.0, "라마", speaker=2)]),
        _front([a, _seg(2.0, "가나다", speaker=2), _seg(5.0, "라마바", speaker=2)]),
    ]
    _roundtrip(seq)


def test_roundtrip_front_pruning():
    """앞부분이 잘려나가는 경우(lines_pruned)."""
    segs = [_seg(float(i), f"line {i}") for i in range(6)]
    seq = [
        _front(segs[:4]),
        _front(segs[2:5]),   # 앞 2줄 prune + 1줄 추가
        _front(segs[4:6]),   # 다시 앞 2줄 prune
    ]
    _roundtrip(seq)


def test_roundtrip_prune_and_tail_rewrite_together():
    a, b, c = _seg(0.0, "A"), _seg(2.0, "B"), _seg(4.0, "C")
    c2 = _seg(4.0, "C 수정본")
    seq = [
        _front([a, b, c]),
        _front([b, c2]),      # 앞 1줄 prune + 꼬리 소급 수정 동시
    ]
    _roundtrip(seq)


def test_roundtrip_empty_and_recovery():
    """빈 상태 → 채워짐 → 전체 교체(공통 prefix 0) → 다시 빈 상태."""
    seq = [
        _front([]),
        _front([]),
        _front([_seg(0.0, "첫줄")]),
        _front([_seg(9.0, "완전히 다른 줄")]),   # 공통 prefix 없음
        _front([]),
    ]
    _roundtrip(seq)


def test_roundtrip_no_change_repeated():
    """동일 상태 반복 — diff는 new_lines 없이 volatile 필드만 실어야 한다."""
    front = _front([_seg(0.0, "동일")], buffer_transcription="…")
    tracker = DiffTracker()
    tracker.to_message(front)
    msg = tracker.to_message(front)
    assert msg["type"] == "diff"
    assert "new_lines" not in msg
    assert msg["n_lines"] == 1


def test_diff_carries_volatile_fields_and_error():
    tracker = DiffTracker()
    tracker.to_message(_front([]))
    front = _front([], buffer_transcription="buf", buffer_translation="트", error="boom")
    msg = tracker.to_message(front)
    assert msg["type"] == "diff"
    assert msg["buffer_transcription"] == "buf"
    assert msg["buffer_translation"] == "트"
    assert msg["error"] == "boom"


def test_naive_append_client_would_diverge():
    """append 구현이 실제로 깨진다는 것을 명시적으로 고정(회귀 가드).

    같은 시퀀스를 '꼬리 교체' 대신 'append'로 처리하면 줄이 중복된다.
    """
    a, b = _seg(0.0, "A"), _seg(3.0, "B")
    b_fixed = _seg(3.0, "B 수정본")
    tracker = DiffTracker()
    naive: List[Dict[str, Any]] = []
    for front in [_front([a]), _front([a, b]), _front([a, b_fixed])]:
        msg = tracker.to_message(front)
        if msg["type"] == "snapshot":
            naive = list(msg["lines"])
        else:
            naive += list(msg.get("new_lines", []))
    expected = _front([a, b_fixed]).to_dict()["lines"]
    assert len(expected) == 2
    assert len(naive) == 3          # 2줄이어야 하는데 3줄(B 수정 전/후가 공존) — append는 틀렸다
    assert naive != expected


def test_reset_produces_fresh_snapshot():
    tracker = DiffTracker()
    tracker.to_message(_front([_seg(0.0, "A")]))
    tracker.reset()
    msg = tracker.to_message(_front([_seg(0.0, "A")]))
    assert msg["type"] == "snapshot"
    assert msg["seq"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# B. 프로토콜 기본값 / opt-out
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def basic_server():
    """basic_server는 import 시 ``config = parse_args()``로 argv를 읽으므로 더미 argv로 로드한다.

    (모델 로드는 lifespan에서만 일어나며 여기서는 lifespan을 발동시키지 않는다.)
    """
    import importlib
    import sys
    from unittest import mock

    with mock.patch.object(sys, "argv", ["prog"]):
        if "whisperlivekit.basic_server" in sys.modules:
            return importlib.reload(sys.modules["whisperlivekit.basic_server"])
        import whisperlivekit.basic_server as bs

        return bs


@pytest.mark.parametrize(
    "requested,default,expected",
    [
        (None, "full", "full"),          # 기본 = full (델타 미대응 클라이언트 무수정 호환)
        (None, "delta", "delta"),        # --ws-protocol delta 로 서버 기본 전환
        ("delta", "full", "delta"),      # ?mode=delta opt-in
        ("full", "delta", "full"),       # 쿼리파라미터가 CLI 기본을 오버라이드
        ("diff", "full", "delta"),       # 구 별칭
        ("DELTA", "full", "delta"),      # 대소문자 무시
        ("garbage", "full", "full"),     # 잘못된 값 → 기본값 폴백
        ("garbage", "delta", "delta"),
    ],
)
def test_resolve_ws_protocol(basic_server, requested, default, expected):
    assert basic_server._resolve_ws_protocol(requested, default) == expected


def test_server_default_config_is_full(basic_server):
    """서버 모듈이 인자 없이 기동되면 기본 프로토콜은 full — 델타 미대응 클라이언트가 무수정으로 동작해야 한다."""
    assert basic_server.config.ws_protocol == "full"
    assert basic_server._resolve_ws_protocol(None, basic_server.config.ws_protocol) == "full"
    # 델타는 클라이언트가 명시적으로 opt-in할 때만 적용된다.
    assert basic_server._resolve_ws_protocol("delta", basic_server.config.ws_protocol) == "delta"


class _FakeWS:
    def __init__(self):
        self.sent = []

    async def send_json(self, payload):
        self.sent.append(payload)


async def _gen(items):
    for item in items:
        yield item


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_delta_path_emits_snapshot_then_diff(basic_server):
    """diff_tracker가 있으면 snapshot 1회 + 이후 diff."""
    ws = _FakeWS()
    fronts = [_front([_seg(0.0, "A")]), _front([_seg(0.0, "A"), _seg(2.0, "B")])]
    _run(basic_server.handle_websocket_results(ws, _gen(fronts), DiffTracker(), None))
    assert [m.get("type") for m in ws.sent] == ["snapshot", "diff", "ready_to_stop"]
    assert ws.sent[1]["new_lines"][0]["text"] == "B"


def test_full_path_emits_legacy_schema(basic_server):
    """?mode=full(=diff_tracker None)은 기존 스키마(type 없음 + lines 전량)를 그대로 낸다."""
    ws = _FakeWS()
    fronts = [_front([_seg(0.0, "A")]), _front([_seg(0.0, "A"), _seg(2.0, "B")])]
    _run(basic_server.handle_websocket_results(ws, _gen(fronts), None, None))
    payloads = ws.sent[:-1]
    assert all("type" not in p for p in payloads)
    assert all("seq" not in p for p in payloads)
    assert [len(p["lines"]) for p in payloads] == [1, 2]
    assert set(payloads[0]) >= {
        "status", "lines", "buffer_transcription", "buffer_diarization",
        "buffer_translation", "remaining_time_transcription", "remaining_time_diarization",
    }
    assert ws.sent[-1] == {"type": "ready_to_stop"}


def test_test_client_reconstruct_state_replaces_tail():
    """test_client(경로 A 하니스)의 재구성도 append가 아니라 꼬리 교체여야 한다."""
    from whisperlivekit.test_client import reconstruct_state

    tracker = DiffTracker()
    a, b = _seg(0.0, "A"), _seg(3.0, "B")
    b_fixed = _seg(3.0, "B 수정본")
    lines: List[Dict[str, Any]] = []
    for front in [_front([a]), _front([a, b]), _front([a, b_fixed]), _front([a, b_fixed, _seg(7.0, "C")])]:
        msg = tracker.to_message(front)
        state = reconstruct_state(msg, lines)
        expected = front.to_dict()["lines"]
        assert lines == expected
        assert state["lines"] == expected


def test_cli_default_is_full():
    from whisperlivekit.parse_args import create_parser

    args = create_parser().parse_args([])
    assert args.ws_protocol == "full"
    assert create_parser().parse_args(["--ws-protocol", "delta"]).ws_protocol == "delta"


def test_config_carries_ws_protocol():
    from whisperlivekit.config import WhisperLiveKitConfig

    assert WhisperLiveKitConfig().ws_protocol == "full"
    assert WhisperLiveKitConfig(ws_protocol="delta").ws_protocol == "delta"
