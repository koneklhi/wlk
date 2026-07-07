# -*- coding: utf-8 -*-
"""finalize_trigger 계측 필드 — 단위 테스트.

문장이 확정될 때 어떤 트리거로 분리됐는지("silence"/"punctuation"/
"language_switch"/"speaker_change") 라벨이 붙는지 검증한다.
계측 전용 — 문장 확정 동작 자체는 바뀌지 않는다.
"""

from types import SimpleNamespace

from whisperlivekit.timed_objects import (
    ASRToken,
    LanguageSwitch,
    Segment,
    Silence,
    TimedText,
)
from whisperlivekit.tokens_alignment import FINALIZE_GRACE_SECS, TokensAlignment

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
    return Silence(start=start, end=end, has_ended=has_ended)


def text_segments(proc: TokensAlignment) -> list:
    return [s for s in proc.validated_segments if not s.is_silence()]


# ─── 테스트 ──────────────────────────────────────────────────────────────────

def test_silence_commit_trigger_is_silence():
    """종결부호 없는 텍스트 뒤 침묵으로 확정된 세그먼트는 trigger='silence'."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, '안녕'),
        make_token(0.5, 1.0, '하세요'),
        make_silence(1.0, 2.0),
    ]

    proc.get_lines(diarization=False, current_silence=None, translation=False)

    segs = text_segments(proc)
    assert len(segs) == 1
    assert segs[0].finalized is True
    assert segs[0].finalize_trigger == "silence", (
        f"기대 'silence', 실제 {segs[0].finalize_trigger!r}"
    )


def test_punctuation_termination_trigger_is_punctuation():
    """온점(.)으로 끝나는 텍스트 뒤 침묵 → trigger='punctuation'."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, 'Hello'),
        make_token(0.5, 1.0, ' world.'),
        make_silence(1.0, 2.0),
    ]

    proc.get_lines(diarization=False, current_silence=None, translation=False)

    segs = text_segments(proc)
    assert len(segs) == 1
    assert segs[0].text.strip().endswith('.')
    assert segs[0].finalized is True
    assert segs[0].finalize_trigger == "punctuation", (
        f"기대 'punctuation', 실제 {segs[0].finalize_trigger!r}"
    )


def test_language_switch_boundary_trigger_is_language_switch():
    """LanguageSwitch 경계로 확정된 세그먼트는 trigger='language_switch'."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, 'Hello'),
        make_token(0.5, 1.0, ' world'),
        LanguageSwitch(start=1.0, end=1.0, detected_language='ko'),
    ]

    proc.get_lines(diarization=False, current_silence=None, translation=False)

    segs = text_segments(proc)
    assert len(segs) == 1
    assert segs[0].finalized is True
    assert segs[0].finalize_trigger == "language_switch", (
        f"기대 'language_switch', 실제 {segs[0].finalize_trigger!r}"
    )


def test_grace_window_suspends_trigger_then_restores():
    """유예 창 안에서는 finalized=False·trigger=None, 경과 후 확정되면 trigger 복귀."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, '안녕'),
        make_token(0.5, 1.0, '하세요'),
        make_silence(1.0, 2.0),
    ]

    # 유예 창 안(1.5 - 1.0 = 0.5 < FINALIZE_GRACE_SECS) → 확정 보류
    within = 1.0 + (FINALIZE_GRACE_SECS / 2.0)
    proc.get_lines(diarization=False, current_silence=None, translation=False, audio_time=within)

    seg = text_segments(proc)[0]
    assert seg.finalized is False, "유예 창 안인데 finalized=True"
    assert seg.finalize_trigger is None, (
        f"유예 창 안인데 trigger가 None이 아님: {seg.finalize_trigger!r}"
    )

    # 유예 창 경과 후 재평가 → 확정 + trigger 복귀
    proc.new_tokens = []
    beyond = 1.0 + FINALIZE_GRACE_SECS + 1.0
    proc.get_lines(diarization=False, current_silence=None, translation=False, audio_time=beyond)

    assert seg.finalized is True, "유예 경과 후에도 finalized=False"
    assert seg.finalize_trigger == "silence", (
        f"유예 경과 후 trigger가 복귀하지 않음: {seg.finalize_trigger!r}"
    )


def test_to_dict_always_contains_finalize_trigger_key():
    """Segment.to_dict()에 finalize_trigger 키가 (None이어도) 항상 포함된다."""
    seg = Segment.from_tokens([make_token(0.0, 1.0, '미확정')])
    assert seg is not None
    d = seg.to_dict()
    assert 'finalize_trigger' in d, "to_dict()에 'finalize_trigger' 키가 없습니다"
    assert d['finalize_trigger'] is None

    seg.finalize_trigger = "silence"
    d2 = seg.to_dict()
    assert d2['finalize_trigger'] == "silence"
