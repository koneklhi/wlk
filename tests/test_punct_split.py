# -*- coding: utf-8 -*-
"""형태소 종결 온점 분할 — 통합 단위 테스트.

compute_punctuations_segments / get_lines_diarization / 비-diar get_lines
경로에서 '진짜 문장 종결 온점'이 세그먼트를 분할하고, 거짓 온점(연결어미·조사)은
분할하지 않으며, 화자변경이 온점 분할보다 우선함을 검증한다.

순수 로직 계층 — 모델 없이 state 주입만으로 검증(test_tail_reattachment.py 패턴 재사용).
"""

from types import SimpleNamespace

from whisperlivekit.timed_objects import (
    ASRToken,
    Silence,
    SpeakerSegment,
    TimedText,
)
from whisperlivekit.tokens_alignment import TokensAlignment

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def make_processor(diarization: bool = False) -> TokensAlignment:
    state = SimpleNamespace(
        new_tokens=[],
        new_diarization=[],
        new_translation=[],
        new_tokens_buffer=[],
        new_translation_buffer=TimedText(),
    )
    args = SimpleNamespace(diarization=diarization)
    proc = TokensAlignment(state=state, args=args, sep=' ')
    proc.beg_loop = 0.0
    return proc


def tok(start: float, end: float, text: str) -> ASRToken:
    return ASRToken(start=start, end=end, text=text)


def sil(start: float, end: float) -> Silence:
    return Silence(start=start, end=end, has_ended=True)


def feed(proc: TokensAlignment, tokens, **kwargs):
    """state.new_tokens에 넣고 update()로 all_tokens에 반영한 뒤 get_lines 호출."""
    proc.state.new_tokens = list(tokens)
    proc.update()
    return proc.get_lines(**kwargs)


def text_segs(segments):
    return [s for s in segments if s is not None and not s.is_silence()]


# ─── 1. diar 같은 화자 mid-stream 종결 분할 ──────────────────────────────────

def test_diar_same_speaker_sentence_final_splits():
    """같은 화자 발화 중간의 진짜 종결 온점(…했습니다.)에서 2개로 분리되고,
    닫힌 세그먼트는 finalize_trigger='punctuation' + punct_boundary=True."""
    proc = make_processor(diarization=True)
    # 하나의 화자(0)가 전 구간을 커버 → 온점 분할이 없으면 한 세그먼트로 병합됐을 상황
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '강조'), tok(0.4, 0.8, '했습니다.'),
         tok(0.9, 1.3, '지도를'), tok(1.3, 1.7, '봤어요.')],
        diarization=True,
        audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"종결 온점 분할 실패(2개 기대): {[s.text for s in txts]}"
    closing = next(s for s in txts if '했습니다.' in s.text)
    assert closing.finalize_trigger == "punctuation", (
        f"기대 'punctuation', 실제 {closing.finalize_trigger!r}"
    )
    assert getattr(closing, "punct_boundary", False) is True, "punct_boundary 미설정"


# ─── 2. 거짓 온점(연결어미·조사) 비분할 ──────────────────────────────────────

def test_diar_false_period_does_not_split():
    """'…것으로.' 뒤 같은 화자 발화 — 종결어미 아님(으로/EXCLUDE)이라 분할 안 됨."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '그런'), tok(0.4, 0.8, '것으로.'), tok(0.9, 1.3, '보입니다.')],
        diarization=True,
        audio_time=1.3,
    )
    txts = text_segs(segments)
    assert len(txts) == 1, f"거짓 온점이 과분할됨: {[s.text for s in txts]}"
    assert '것으로.' in txts[0].text and '보입니다.' in txts[0].text
    # punctuation 라벨이 붙지 않아야 함(중간에 닫힌 세그먼트가 없으므로 trigger None)
    assert txts[0].finalize_trigger != "punctuation", (
        f"거짓 온점에 punctuation 라벨: {txts[0].finalize_trigger!r}"
    )


# ─── 3. 화자변경이 온점 분할보다 우선 ────────────────────────────────────────

def test_speaker_change_takes_priority_over_punctuation():
    """종결 온점 세그먼트 다음이 다른 화자면 trigger='speaker_change'(punctuation 아님)."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [
        SpeakerSegment(start=0.0, end=0.85, speaker=0),
        SpeakerSegment(start=0.85, end=2.0, speaker=1),
    ]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '강조'), tok(0.4, 0.8, '했습니다.'),
         tok(0.9, 1.3, 'Hello'), tok(1.3, 1.7, 'there.')],
        diarization=True,
        audio_time=1.7,
    )
    txts = text_segs(segments)
    closing = next(s for s in txts if '했습니다.' in s.text)
    assert closing.finalize_trigger == "speaker_change", (
        f"화자변경 우선 실패: 기대 'speaker_change', 실제 {closing.finalize_trigger!r}"
    )


# ─── 4. 비-diar 종결 분할 ────────────────────────────────────────────────────

def test_nondiar_sentence_final_splits():
    """비-diar: '그렇습니다.' 뒤 '다음은' 도착 시 앞 줄을 선-확정(punctuation)하고
    '다음은'은 진행 중 줄로 남는다."""
    proc = make_processor(diarization=False)
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.5, '그렇습니다.'), tok(0.9, 1.3, '다음은')],
        diarization=False,
        audio_time=1.3,
    )
    validated_txts = [s for s in proc.validated_segments if not s.is_silence()]
    assert len(validated_txts) == 1, (
        f"확정 세그먼트 수 이상(1개 기대): {[s.text for s in validated_txts]}"
    )
    assert '그렇습니다.' in validated_txts[0].text
    assert validated_txts[0].finalize_trigger == "punctuation", (
        f"기대 'punctuation', 실제 {validated_txts[0].finalize_trigger!r}"
    )
    txts = text_segs(segments)
    assert txts and txts[-1].text.strip() == '다음은', (
        f"진행 중 줄이 '다음은'이 아님: {[s.text for s in txts]}"
    )
