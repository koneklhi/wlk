# -*- coding: utf-8 -*-
"""CASE1 잔여 3종(Exp-B) 단위 테스트.

B1: 중간 온점 분리 조건화 — 갭 자체는(Exp-166 FIX 1로 은퇴) 분할 근거가 아니고,
    실제 Silence 토큰 또는 발화 끝일 때만 끊는다(tests/test_tail_reattachment.py §9 참조).
B2: QG 온점-only 억제는 refresh streak에 미산입 — 실단어 억제만 누적한다.
B3: 유령/중복 온점 collapse — ". ." → ".", 선두 단독 온점 스트립, 정상 온점 보존.

전부 순수 로직 계층이라 모델 없이 검증한다(test_tail_reattachment.py 패턴 재사용).
"""

import types
from types import SimpleNamespace
from unittest.mock import MagicMock

from whisperlivekit.filtering import filter_segments
from whisperlivekit.simul_whisper.align_att_base import (
    _PUNCT_ONLY_CHARS,
    AlignAttBase,
)
from whisperlivekit.timed_objects import (
    ASRToken,
    Segment,
    Silence,
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


def seg(text: str) -> Segment:
    return Segment(start=0.0, end=1.0, text=text, speaker=-1)


def text_segs(segments):
    return [s for s in segments if s is not None and not s.is_silence()]


# ─── B1: 중간 온점 분리 조건화 ────────────────────────────────────────────────

def test_b1_gapless_midpunct_not_split():
    """갭 없는 중간 온점("very. much")은 분할하지 않는다 — 세그먼트 1개."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), tok(1.4, 1.8, ' much')]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"갭 없는 온점이 과분할됨: {[s.text for s in txts]}"
    assert 'very.' in txts[0].text and 'much' in txts[0].text


def test_b1_gap_alone_no_longer_splits():
    """온점 뒤 갭만으로는(실제 Silence 토큰 없이) 더 이상 분할하지 않는다 — 세그먼트 1개.

    Exp-166 FIX 1: 과거엔 PUNCT_SPLIT_GAP_SECS(갭 임계값, 0.3→0.4로 상향까지 시도)
    기반 분기가 있었으나, N=3 확정측정에서 그 문턱 조정으로는 실서버 재현이 안 됨을
    확인 — 소거법상 실제 토큰 갭이 문턱을 얼마로 올리든 그 이상이었다는 뜻이라
    갭 기반 분기 자체를 제거했다(PUNCT_SPLIT_GAP_SECS 상수도 은퇴). 이제 온점 분할은
    (a)발화 끝 또는 (b)실제 Silence 토큰에서만 일어난다 — 큰 갭(여기선 1.4s)이어도
    Silence 토큰이 없으면 병합된다.
    """
    proc = make_processor(diarization=True)
    # 갭 = 2.8 - 1.4 = 1.4 (과거라면 분할됐을 큰 값이지만 Silence 토큰이 없다)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), tok(2.8, 3.2, ' much')]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"갭만으로 여전히 분할됨(갭 기반 분기 잔존 의심): {[s.text for s in txts]}"


def test_b1_punct_before_silence_splits():
    """온점 뒤 침묵이면 분할한다."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), sil(1.5, 2.0)]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1 and txts[0].text.strip() == 'very.'
    assert any(s.is_silence() for s in segments), "침묵 세그먼트가 없다"


def test_b1_punct_at_end_splits():
    """온점 뒤 토큰이 없으면(발화 끝) 분할한다(final_segment로 닫힘)."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, '끝.')]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1 and txts[0].text.strip() == '끝.'


# ─── B2: QG 온점-only 억제 refresh streak 미산입 ──────────────────────────────

def _make_fake_decoder(decode_str: str, reset_after: int = 3):
    """B2 스텁 — 경계 보호창 **밖**(스탬프 0.0, 현재 시각 1000s)으로 고정한다.

    보존형 refresh(BOUNDARY_QG_PRESERVE, tests/test_boundary_qg_preserve.py)는 경계 직후
    구간에서만 개입하므로, 여기서는 그 창을 벗어나게 두어 B2가 검증하려던 **기존 폐기
    동작**을 그대로 측정한다. 보호창 안쪽 거동은 전용 테스트 파일이 담당한다.
    """
    fs = SimpleNamespace(
        tokenizer=SimpleNamespace(decode=lambda h: decode_str),
        state=SimpleNamespace(
            quality_suppress_streak=0,
            detected_language=None,
            last_boundary_event_at=0.0,
            qg_preserve_used=False,
        ),
        cfg=SimpleNamespace(quality_gate_reset_after=reset_after),
    )
    fs._clean_cache = lambda: None
    fs.refresh_segment = MagicMock()
    fs.segments_len = lambda: 1.5
    fs._current_stream_time = lambda: 1000.0  # 경계로부터 한참 뒤 = 보호창 밖
    for name in ("_is_punct_only", "_try_preserving_refresh"):
        setattr(fs, name, types.MethodType(getattr(AlignAttBase, name), fs))
    return fs


def test_b2_is_punct_only_true_for_punct():
    fs = SimpleNamespace(tokenizer=SimpleNamespace(decode=lambda h: ". ."))
    assert AlignAttBase._is_punct_only(fs, [1, 2]) is True


def test_b2_is_punct_only_true_for_empty():
    fs = SimpleNamespace(tokenizer=SimpleNamespace(decode=lambda h: "  "))
    assert AlignAttBase._is_punct_only(fs, [1]) is True
    assert AlignAttBase._is_punct_only(fs, []) is True


def test_b2_is_punct_only_false_for_word():
    fs = SimpleNamespace(tokenizer=SimpleNamespace(decode=lambda h: "공군"))
    assert AlignAttBase._is_punct_only(fs, [1, 2]) is False


def test_b2_punct_only_suppression_no_streak():
    """구두점-only 억제는 streak을 증가시키지 않고 refresh도 안 부른다."""
    fs = _make_fake_decoder(". .", reset_after=3)
    for _ in range(5):
        AlignAttBase._on_quality_suppressed(fs, [1, 2])
    assert fs.state.quality_suppress_streak == 0
    fs.refresh_segment.assert_not_called()


def test_b2_word_suppression_increments_and_refreshes():
    """실단어 억제는 streak 누적 → reset_after 도달 시 refresh_segment 발동·리셋."""
    fs = _make_fake_decoder("공군", reset_after=3)
    AlignAttBase._on_quality_suppressed(fs, [1])
    assert fs.state.quality_suppress_streak == 1
    AlignAttBase._on_quality_suppressed(fs, [1])
    assert fs.state.quality_suppress_streak == 2
    AlignAttBase._on_quality_suppressed(fs, [1])
    fs.refresh_segment.assert_called_once_with(complete=True)
    assert fs.state.quality_suppress_streak == 0


def test_b2_no_hypothesis_still_increments():
    """하위호환: hypothesis 미전달 시 기존 동작(무조건 산입)."""
    fs = _make_fake_decoder("공군", reset_after=10)
    AlignAttBase._on_quality_suppressed(fs)
    assert fs.state.quality_suppress_streak == 1


def test_b2_punct_only_chars_membership():
    assert '.' in _PUNCT_ONLY_CHARS and ',' in _PUNCT_ONLY_CHARS
    assert '가' not in _PUNCT_ONLY_CHARS


# ─── B3: 유령/중복 온점 collapse ──────────────────────────────────────────────

def test_b3_double_period_collapsed():
    """'사령관. .' → '사령관.' (중복 온점 collapse, 종료 온점 1개 보존)."""
    out = filter_segments([seg('사령관. .')])
    assert len(out) == 1
    assert out[0].text == '사령관.', f"collapse 실패: {out[0].text!r}"


def test_b3_leading_period_stripped():
    """'. 자신의' → '자신의' (선두 단독 온점 스트립)."""
    out = filter_segments([seg('. 자신의')])
    assert len(out) == 1
    assert out[0].text == '자신의', f"선두 온점 스트립 실패: {out[0].text!r}"


def test_b3_normal_terminal_period_preserved():
    out = filter_segments([seg('정상 문장입니다.')])
    assert len(out) == 1
    assert out[0].text == '정상 문장입니다.'


def test_b3_midword_single_period_preserved():
    """'very. much' 단어 사이 단일 온점은 보존(B1이 같은 세그먼트에 남긴 것)."""
    out = filter_segments([seg('very. much')])
    assert len(out) == 1
    assert out[0].text == 'very. much', f"단어 사이 온점이 훼손됨: {out[0].text!r}"


def test_b3_question_exclamation_preserved():
    out = filter_segments([seg('맞나요?')])
    assert len(out) == 1
    assert out[0].text == '맞나요?'


def test_b3_ghost_only_still_dropped():
    """순수 유령 온점 세그먼트는 여전히 드롭된다."""
    out = filter_segments([seg(' . .'), seg('정상')])
    texts = [s.text for s in out]
    assert '정상' in texts
    assert not any(set(t.replace(' ', '')) <= {'.', '?', '!'} for t in texts if t)
