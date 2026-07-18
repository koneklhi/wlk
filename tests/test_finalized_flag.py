# -*- coding: utf-8 -*-
"""Task 1: finalized 확정 신호 활성화 — 단위 테스트.

validated_segments에 커밋된 세그먼트는 finalized=True,
trailing 진행중 라인은 finalized=False,
to_dict()['finalized'] 값도 검증한다.
"""

from types import SimpleNamespace

from whisperlivekit.timed_objects import ASRToken, Segment, Silence, TimedText
from whisperlivekit.tokens_alignment import SILENCE_HARD_SECS, TokensAlignment


# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def make_processor() -> TokensAlignment:
    """최소 mock state/args로 TokensAlignment 인스턴스를 생성한다."""
    state = SimpleNamespace(
        new_tokens=[],
        new_diarization=[],
        new_translation=[],
        new_tokens_buffer=[],
        new_translation_buffer=TimedText(),
    )
    args = SimpleNamespace(diarization=False)
    proc = TokensAlignment(state=state, args=args, sep=' ')
    proc.beg_loop = 0.0  # get_lines()에서 time() - beg_loop 사용하므로 초기화 필요
    return proc


def make_token(start: float, end: float, text: str) -> ASRToken:
    return ASRToken(start=start, end=end, text=text)


def make_silence(start: float, end: float, has_ended: bool = True) -> Silence:
    sil = Silence(start=start, end=end, has_ended=has_ended)
    return sil


# ─── 테스트 ──────────────────────────────────────────────────────────────────

def test_validated_segment_is_finalized():
    """무음 경계에서 validated_segments에 커밋된 세그먼트는 finalized=True여야 한다."""
    proc = make_processor()
    # 토큰 2개 → 무음 → 토큰 1개(trailing)
    proc.new_tokens = [
        make_token(0.0, 0.5, '안녕'),
        make_token(0.5, 1.0, '하세요'),
        make_silence(1.0, 2.0),
        make_token(2.0, 2.5, '다음'),
    ]

    proc.get_lines(diarization=False, current_silence=None, translation=False)

    # validated_segments 에 하나 커밋돼야 함
    text_segs = [s for s in proc.validated_segments if not s.is_silence()]
    assert len(text_segs) == 1
    assert text_segs[0].finalized is True, "validated_segments 세그먼트가 finalized=True가 아닙니다"


def test_trailing_line_is_not_finalized():
    """trailing 진행중 라인(무음 없이 끝나는 마지막 토큰)은 finalized=False여야 한다."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, '진행'),
        make_token(0.5, 1.0, '중'),
    ]

    segments, _, _ = proc.get_lines(diarization=False, current_silence=None, translation=False)

    # validated_segments는 비어 있어야 하고, trailing 세그먼트는 get_lines 반환값에 있음
    assert len(proc.validated_segments) == 0, "무음 없이 trailing만 있는데 validated_segments가 비어있지 않습니다"

    # 반환된 세그먼트 중 텍스트가 있는 것
    text_segs = [s for s in segments if s is not None and not s.is_silence()]
    assert len(text_segs) == 1
    assert text_segs[0].finalized is False, "trailing 세그먼트가 finalized=True입니다 (False여야 함)"


def test_to_dict_finalized_true():
    """validated_segments 세그먼트의 to_dict()['finalized']가 True여야 한다."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, 'Hello'),
        make_token(0.5, 1.0, ' world'),
        # 뒤에 이어지는 토큰이 없어 안전망(SILENCE_HARD_SECS)으로만 분할되므로,
        # 문턱을 확실히 넘도록 margin 0.5s를 둔다.
        make_silence(1.0, 1.0 + SILENCE_HARD_SECS + 0.5),
    ]

    proc.get_lines(diarization=False, current_silence=None, translation=False)

    text_segs = [s for s in proc.validated_segments if not s.is_silence()]
    assert len(text_segs) >= 1
    d = text_segs[0].to_dict()
    assert 'finalized' in d, "to_dict()에 'finalized' 키가 없습니다"
    assert d['finalized'] is True, f"to_dict()['finalized'] 값이 True가 아닙니다: {d['finalized']}"


def test_to_dict_finalized_false_for_trailing():
    """trailing 세그먼트 to_dict()['finalized']는 False여야 한다."""
    # Segment.from_tokens()로 직접 생성 (trailing 경로)
    tokens = [make_token(0.0, 0.5, '미확정')]
    seg = Segment.from_tokens(tokens)
    assert seg is not None
    assert seg.finalized is False
    d = seg.to_dict()
    assert d['finalized'] is False


def test_multiple_sentences_all_finalized():
    """무음이 여러 번 오면 각 validated 세그먼트가 모두 finalized=True여야 한다."""
    proc = make_processor()
    # 두 침묵 모두 뒤에 새 문장이 이어지지만, 안전망(SILENCE_HARD_SECS)이 실제로
    # 분할을 트리거해야 하는 의도이므로 각 침묵 길이를 문턱 + margin 0.5s로 둔다.
    # 토큰 시각은 이전 구간이 끝난 직후부터 이어지도록 순차 배치한다.
    silence1_end = 1.0 + SILENCE_HARD_SECS + 0.5
    token3_start = silence1_end
    token4_start = token3_start + 0.5
    silence2_start = token4_start + 0.5
    silence2_end = silence2_start + SILENCE_HARD_SECS + 0.5
    proc.new_tokens = [
        make_token(0.0, 0.5, '첫'),
        make_token(0.5, 1.0, '문장'),
        make_silence(1.0, silence1_end),
        make_token(token3_start, token4_start, '두번째'),
        make_token(token4_start, silence2_start, '문장'),
        make_silence(silence2_start, silence2_end),
    ]

    proc.get_lines(diarization=False, current_silence=None, translation=False)

    text_segs = [s for s in proc.validated_segments if not s.is_silence()]
    assert len(text_segs) >= 2, f"텍스트 세그먼트 수가 2 미만입니다: {len(text_segs)}"
    for seg in text_segs:
        assert seg.finalized is True, f"세그먼트 '{seg.text}'가 finalized=True가 아닙니다"
