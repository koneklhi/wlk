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
    SpeakerSegment,
    TimedText,
)
from whisperlivekit.tokens_alignment import FINALIZE_GRACE_SECS, SILENCE_HARD_SECS, TokensAlignment

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def make_processor(diarization: bool = False) -> TokensAlignment:
    """최소 mock state/args로 TokensAlignment 인스턴스를 생성한다."""
    state = SimpleNamespace(
        new_tokens=[],
        new_diarization=[],
        new_translation=[],
        new_tokens_buffer=[],
        new_translation_buffer=TimedText(),
    )
    args = SimpleNamespace(diarization=diarization)
    proc = TokensAlignment(state=state, args=args, sep=' ')
    proc.beg_loop = 0.0  # get_lines()에서 time() - beg_loop 사용하므로 초기화 필요
    return proc


def make_token(start: float, end: float, text: str) -> ASRToken:
    return ASRToken(start=start, end=end, text=text)


def make_silence(start: float, end: float, has_ended: bool = True) -> Silence:
    return Silence(start=start, end=end, has_ended=has_ended)


def text_segments(proc: TokensAlignment) -> list:
    return [s for s in proc.validated_segments if not s.is_silence()]


def feed_diar(proc: TokensAlignment, tokens, **kwargs):
    """diar 경로: state.new_tokens에 넣고 update()로 all_tokens에 반영한 뒤 get_lines 호출."""
    proc.state.new_tokens = list(tokens)
    proc.update()
    return proc.get_lines(**kwargs)


def diar_text_segs(segments) -> list:
    return [s for s in segments if s is not None and not s.is_silence()]


# ─── 테스트 ──────────────────────────────────────────────────────────────────

def test_silence_commit_trigger_is_silence():
    """종결부호 없는 텍스트 뒤 침묵으로 확정된 세그먼트는 trigger='silence'."""
    proc = make_processor()
    proc.new_tokens = [
        make_token(0.0, 0.5, '안녕'),
        make_token(0.5, 1.0, '하세요'),
        # 뒤에 이어지는 토큰이 없어 안전망(SILENCE_HARD_SECS)으로만 분할되므로,
        # 문턱을 확실히 넘도록 margin 0.5s를 둔다.
        make_silence(1.0, 1.0 + SILENCE_HARD_SECS + 0.5),
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
        # 뒤에 이어지는 토큰이 없어 안전망(SILENCE_HARD_SECS)으로만 분할되므로,
        # 문턱을 확실히 넘도록 margin 0.5s를 둔다.
        make_silence(1.0, 1.0 + SILENCE_HARD_SECS + 0.5),
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


# ─── Exp-186/187 — diar 화자전환 경계가 침묵을 사이에 두고 발생하는 경우 ────────
#
# tests/test_silence_grammar_gate.py::test_diar_speaker_change_blocks_merge와 동일한
# 입력(화자전환 사이에 짧은 침묵)을 재사용한다. 그 테스트는 "병합 안 됨(분할됨)"만
# 검증하고 finalize_trigger 라벨은 확인하지 않는다 — 분할 자체는 _gate_decide()의
# "diar_mode and next_seg.speaker != closing.speaker" 조건(split_grammar)이 이미
# 강제하고 있으나(문법상 미종결이어도 화자가 다르면 무조건 분할), 그 판정 결과가
# TriggerAssign 단계로 전달되지 않아 finalize_trigger는 "silence"로 잘못 붙는다
# (get_lines_diarization의 `elif segment.is_silence():` 분기가 화자비교보다 먼저
# 걸림 — Exp-186이 관찰한 "diar NewSpeaker 26~27회 vs speaker_change 트리거 1~4회"
# 손실의 구조적 원인).

def test_diar_speaker_change_across_silence_gets_speaker_change_trigger():
    """화자전환이 침묵을 사이에 두고 일어나도 trigger는 'speaker_change'여야 한다."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [
        SpeakerSegment(start=0.0, end=1.2, speaker=0),
        SpeakerSegment(start=1.2, end=2.0, speaker=1),
    ]
    segments, _, _ = feed_diar(
        proc,
        [make_token(0.0, 0.4, '중요한'), make_token(0.4, 0.8, '관련'),
         make_silence(0.9, 1.2), make_token(1.3, 1.7, '다음')],
        diarization=True, audio_time=1.7,
    )
    txts = diar_text_segs(segments)
    assert len(txts) == 2, f"화자 전환인데 병합됨: {[s.text for s in txts]}"
    closing = txts[0]
    assert '관련' in closing.text
    assert closing.finalize_trigger == "speaker_change", (
        f"화자전환으로 강제분할된 세그먼트인데 trigger={closing.finalize_trigger!r} "
        "(silence/punctuation으로 흡수됨 — 분기 우선순위 버그)"
    )


def test_diar_same_speaker_across_silence_still_gets_silence_trigger():
    """화자가 같으면(진짜 침묵 경계) 기존대로 trigger='silence' — 회귀 방지."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [
        SpeakerSegment(start=0.0, end=2.0, speaker=0),
    ]
    segments, _, _ = feed_diar(
        proc,
        [make_token(0.0, 0.4, '안녕'), make_token(0.4, 0.8, '하세요'),
         make_silence(0.9, 0.9 + SILENCE_HARD_SECS + 0.5), make_token(2.5, 2.9, '다음')],
        diarization=True, audio_time=2.9,
    )
    txts = diar_text_segs(segments)
    closing = next(s for s in txts if '하세요' in s.text)
    assert closing.finalize_trigger == "silence", (
        f"같은 화자 침묵 경계인데 trigger={closing.finalize_trigger!r}"
    )
