# -*- coding: utf-8 -*-
"""CASE1 문장 꼬리 분리 버그 — 침묵-인지 재귀속 단위 테스트.

AlignAtt가 유보한 마지막 단어(꼬리)가 재디코딩 후 Silence 마커 뒤로 들어가
다음 줄 첫머리로 밀리는 문제를 하류에서 교정한다. 순수 로직 계층이라
모델 없이 state 주입만으로 검증한다(test_finalized_flag.py 패턴 재사용).

재귀속 술어의 기준 시각은 Silence.end가 아니라 Silence.start이다
(긴 침묵 후 앵커 재설정 시 직후 토큰 start가 침묵 end보다 앞설 수 있으므로).
"""

from types import SimpleNamespace

from whisperlivekit.filtering import filter_segments
from whisperlivekit.timed_objects import (
    ASRToken,
    LanguageSwitch,
    Segment,
    Silence,
    TimedText,
)
from whisperlivekit.tokens_alignment import (
    FINALIZE_GRACE_SECS,
    TokensAlignment,
)

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


def sil(start: float, end: float, has_ended: bool = True) -> Silence:
    return Silence(start=start, end=end, has_ended=has_ended)


def feed(proc: TokensAlignment, tokens, **kwargs):
    """state.new_tokens에 넣고 update()로 all_tokens에 반영한 뒤 get_lines 호출."""
    proc.state.new_tokens = list(tokens)
    proc.update()
    return proc.get_lines(**kwargs)


def text_segs(segments):
    return [s for s in segments if s is not None and not s.is_silence()]


# ─── 1. diar CASE1 재현 ──────────────────────────────────────────────────────

def test_diar_case1_tail_reattaches():
    """꼬리(습니다.)가 Silence 앞으로 재귀속돼 앞 문장에 병합된다."""
    proc = make_processor(diarization=True)
    # batch1: 지도를 올렸 (아직 확정 전)
    feed(proc, [tok(6.0, 6.4, '지도를'), tok(6.4, 6.8, '올렸')], diarization=True, audio_time=6.8)
    # batch2: 침묵 7.0~7.8
    feed(proc, [sil(7.0, 7.8)], diarization=True, audio_time=7.8)
    # batch3: 유보됐던 꼬리(start 6.8 < 침묵 start 7.0) + 다음 줄 첫 단어
    segments, _, _ = feed(
        proc,
        [tok(6.8, 7.0, '습니다.'), tok(7.9, 8.3, '브런슨')],
        diarization=True,
        audio_time=8.3,
    )

    txts = text_segs(segments)
    # 앞 문장에 꼬리가 붙어 온점으로 끝난다
    assert any('올렸습니다.' in s.text for s in txts), f"꼬리 병합 실패: {[s.text for s in txts]}"
    # 브런슨은 별도 trailing 세그먼트
    assert any(s.text.strip() == '브런슨' for s in txts), f"브런슨 분리 실패: {[s.text for s in txts]}"
    # 병합 문장이 브런슨보다 앞선다
    joined = [s.text for s in txts]
    merged_idx = next(i for i, t in enumerate(joined) if '올렸습니다.' in t)
    brunson_idx = next(i for i, t in enumerate(joined) if '브런슨' in t)
    assert merged_idx < brunson_idx


# ─── 2. 비-diar CASE1 재현 ───────────────────────────────────────────────────

def test_nondiar_case1_tail_reattaches():
    """비-diar 경로: 꼬리가 직전 확정 세그먼트로 병합, 세그먼트 수 비정상 증가 없음."""
    proc = make_processor(diarization=False)
    feed(proc, [tok(6.0, 6.4, '지도를'), tok(6.4, 6.8, '올렸')], diarization=False, audio_time=6.8)
    feed(proc, [sil(7.0, 7.8)], diarization=False, audio_time=7.8)
    feed(proc, [tok(6.8, 7.0, '습니다.'), tok(7.9, 8.3, '브런슨')], diarization=False, audio_time=8.3)

    txts = [s for s in proc.validated_segments if not s.is_silence()]
    # 꼬리가 앞 확정 세그먼트에 병합
    assert txts, "확정 텍스트 세그먼트가 없다"
    assert '올렸습니다.' in txts[-1].text, f"꼬리 병합 실패: {txts[-1].text!r}"
    # 확정 텍스트 세그먼트는 1개(과분할 없음)
    assert len(txts) == 1, f"세그먼트 과분할: {[s.text for s in txts]}"


# ─── 3. finalize 유예 ────────────────────────────────────────────────────────

def test_finalize_grace_within_window_not_finalized():
    """침묵 직후(유예 내) 직전 텍스트 세그먼트는 finalized=False."""
    proc = make_processor(diarization=True)
    feed(proc, [tok(6.0, 6.4, '지도를'), tok(6.4, 6.8, '올렸.')], diarization=True, audio_time=6.8)
    segments, _, _ = feed(
        proc, [sil(7.0, 7.8)], diarization=True, audio_time=7.0 + 1.0,
    )
    txts = text_segs(segments)
    assert txts and txts[-1].finalized is False, "유예 내인데 finalized=True"


def test_finalize_grace_expired_finalized():
    """유예(2.0s) 경과 후 직전 텍스트 세그먼트는 finalized=True."""
    assert FINALIZE_GRACE_SECS == 2.0
    proc = make_processor(diarization=True)
    feed(proc, [tok(6.0, 6.4, '지도를'), tok(6.4, 6.8, '올렸.')], diarization=True, audio_time=6.8)
    segments, _, _ = feed(
        proc, [sil(7.0, 7.8)], diarization=True, audio_time=7.0 + 2.0,
    )
    txts = text_segs(segments)
    assert txts and txts[-1].finalized is True, "유예 경과인데 finalized=False"


def test_finalize_grace_followed_by_speech_finalized():
    """침묵 후 후속 발화가 도착하면 직전 세그먼트는 즉시 finalized=True."""
    proc = make_processor(diarization=True)
    feed(proc, [tok(6.0, 6.4, '지도를'), tok(6.4, 6.8, '올렸.')], diarization=True, audio_time=6.8)
    feed(proc, [sil(7.0, 7.8)], diarization=True, audio_time=7.5)
    segments, _, _ = feed(
        proc, [tok(8.0, 8.4, '다음')], diarization=True, audio_time=8.4,
    )
    txts = text_segs(segments)
    first = next(s for s in txts if '올렸' in s.text)
    assert first.finalized is True, "후속 발화 도착했는데 finalized=False"


# ─── 4. 오귀속 방어(앵커 함정) ───────────────────────────────────────────────

def test_long_silence_no_false_reattach():
    """긴 침묵(10~13) 뒤 토큰 start=12.6(=end-0.4)은 재귀속되지 않는다.

    기준이 silence.end였다면 12.6<13.0 → 오귀속. silence.start(10.0)이 기준이면 방어.
    """
    proc = make_processor(diarization=True)
    feed(proc, [tok(8.0, 9.0, '앞문장.')], diarization=True, audio_time=9.0)
    feed(proc, [sil(10.0, 13.0)], diarization=True, audio_time=13.0)
    segments, _, _ = feed(proc, [tok(12.6, 13.2, '뒷단어')], diarization=True, audio_time=13.2)

    # all_tokens 순서상 뒷단어가 Silence 뒤에 남아야 한다
    order = [type(t).__name__ for t in proc.all_tokens]
    sil_idx = order.index('Silence')
    word_idx = next(i for i, t in enumerate(proc.all_tokens)
                    if getattr(t, 'text', '') == '뒷단어')
    assert word_idx > sil_idx, "긴 침묵 뒤 토큰이 침묵 앞으로 오귀속됨"


# ─── 5. 경계 불가침(is_boundary 스캔 중단) ───────────────────────────────────

def test_reattach_stops_at_boundary():
    """LanguageSwitch(is_boundary) 너머로는 재귀속하지 않는다."""
    proc = make_processor(diarization=True)
    proc.state.new_tokens = [tok(6.0, 6.8, '앞.'), sil(7.0, 7.8), LanguageSwitch(start=7.8, end=7.8)]
    proc.update()
    # 꼬리 시각(6.9)은 침묵 앞이지만, 경계가 사이에 있으므로 재귀속 금지
    proc.state.new_tokens = [tok(6.85, 7.0, '꼬리')]
    proc.update()

    order = [type(t).__name__ for t in proc.all_tokens]
    boundary_idx = order.index('LanguageSwitch')
    tail_idx = next(i for i, t in enumerate(proc.all_tokens)
                    if getattr(t, 'text', '') == '꼬리')
    assert tail_idx > boundary_idx, "경계 너머로 재귀속됨"


# ─── 6. 유령 온점 필터 ───────────────────────────────────────────────────────

def test_filter_drops_punctuation_only_with_spaces():
    """공백 낀 구두점-only 세그먼트( ' . .' , ' . ' )도 드롭한다."""
    keep = Segment(start=0.0, end=1.0, text='정상 문장', speaker=-1)
    ghost1 = Segment(start=1.0, end=2.0, text=' . .', speaker=-1)
    ghost2 = Segment(start=2.0, end=3.0, text=' . ', speaker=-1)
    out = filter_segments([keep, ghost1, ghost2])
    texts = [s.text for s in out]
    assert '정상 문장' in texts
    assert not any(set(t.replace(' ', '')) <= {'.', '?', '!'} for t in texts if t), \
        f"유령 온점 세그먼트가 남음: {texts}"


# ─── 7. 온점 부착 finalized 게이트 ───────────────────────────────────────────

def test_terminal_punctuation_gated_by_finalized():
    from whisperlivekit.audio_processor import _append_terminal_punctuation

    final_seg = Segment(start=0.0, end=1.0, text='확정 문장', speaker=-1)
    final_seg.finalized = True
    unfinal_seg = Segment(start=1.0, end=2.0, text='미확정 문장', speaker=-1)
    unfinal_seg.finalized = False
    trailing = Segment(start=2.0, end=3.0, text='진행 중', speaker=-1)

    lines = [final_seg, unfinal_seg, trailing]
    _append_terminal_punctuation(lines)

    assert final_seg.text.endswith('.'), "확정 세그먼트에 온점 미부착"
    assert not unfinal_seg.text.endswith('.'), "미확정 세그먼트에 온점 부착됨"
    assert trailing.text == '진행 중', "마지막(진행 중) 세그먼트가 수정됨"

    # 멱등: 재호출해도 온점 중복 안 됨
    _append_terminal_punctuation(lines)
    assert final_seg.text.endswith('.') and not final_seg.text.endswith('..')


# ─── 8. 연속 침묵 통과 ───────────────────────────────────────────────────────

def test_reattach_through_consecutive_silences():
    """다중 Silence 사이를 통과해 꼬리가 첫 침묵 앞까지 재귀속된다."""
    proc = make_processor(diarization=True)
    proc.state.new_tokens = [tok(6.0, 6.8, '앞'), sil(7.0, 7.5), sil(8.0, 8.5)]
    proc.update()
    proc.state.new_tokens = [tok(6.85, 7.0, '꼬리')]  # start < 첫 침묵 start(7.0)
    proc.update()

    order = [(type(t).__name__, getattr(t, 'text', '')) for t in proc.all_tokens]
    tail_idx = next(i for i, (_, txt) in enumerate(order) if txt == '꼬리')
    first_sil_idx = next(i for i, (name, _) in enumerate(order) if name == 'Silence')
    assert tail_idx < first_sil_idx, f"연속 침묵 통과 재귀속 실패: {order}"


# ─── 9. 경로4(구두점-매개 꼬리분리) — 갭 기반 분기 완전 제거(Exp-166 FIX 1) ─────
#
# 1라운드 결론 정정: PUNCT_SPLIT_GAP_SECS를 0.3→0.4로 올린 조치("Direction A")는
# 근본 수정이 아니었다. 서버로그의 "Silence of = 0.32s"는 backend.py가 재는 VAD
# 침묵 길이일 뿐, _punct_split_justified()가 실제로 쓰는 토큰 타임스탬프 갭
# (nxt.start - tokens[idx].end)과는 다른 양이다 — 이 둘을 같다고 가정한 게 Direction
# A가 실패한 원인이었다(N=3 확정측정에서 bong1/sbs1 모두 3/3 재현으로 드러남).
#
# 소거법: get_lines()/get_lines_diarization()은 매 틱 self.all_tokens 전체를 새로
# 계산하는 풀스냅샷이고 영속 상태가 없다(1라운드에서 이미 확인). 최종 스냅샷에
# 분리가 남아있다는 것 자체가 최종 all_tokens 기준으로 _punct_split_justified가
# True를 반환했다는 뜻이고, (a)발화 끝도 아니고 (b)Silence 토큰도 없으니(VAD 침묵이
# 0.4 미만이라 안 만들어짐) 남는 건 구 (c)갭 분기뿐 — 즉 실제 토큰 갭은 이미 (문턱을
# 얼마로 올리든) 그 문턱 이상이었다는 뜻이다. 갭 기반 분기는 "문턱을 얼마로 잡아도
# 그보다 큰 실제 갭 앞에서는 무력하다"는 구조적 결함이 있어 문턱 조정 대신 (c)분기
# 자체를 제거했다 — 온점 분할은 이제 오직 (a)발화 끝 또는 (b)실제 Silence 토큰에서만
# 일어난다. 아래 테스트들은 "갭 값이 얼마든(0.32든 1.5든) 분할 근거가 못 된다"는
# 문턱-무관성을 검증한다 — 특정 갭 값 하나만 고쳐 맞추는 게 아니다.
#
# finalized 플래그는 이 버그와 무관하다(Direction B 원안을 기각한 근거는 1라운드와
# 동일하게 유지): whisperlivekit/web/live_transcription.js의 renderLinesWithBuffer()는
# finalized/completed 값과 무관하게 lines[] 각 항목마다 .textcontent 한 줄을 만들고,
# scripts/eval.py의 hyp_sentences도 finalized를 보지 않고 text만으로 줄을 센다.

def test_large_token_gap_without_silence_merges_at_source():
    """실서버 재현값(gap=0.45s, 실제 Silence 없음) — compute_punctuations_segments
    원천에서 병합돼야 한다.

    N=3 확정측정에서 bong1 "자빠졌/는데" 지점은 VAD 침묵이 0.29~0.32s(Silence 토큰
    미생성)였는데도 3/3 전부 분리가 재현됐다 — 소거법상 실제 토큰 갭은 이미 0.4s
    이상이었다는 뜻이다(구 Direction A로는 못 막았던 바로 그 값대). 이 테스트는
    그 실서버 케이스를 gap=0.45s로 직접 재현한다. 구 코드(Direction A, 문턱=0.4)라면
    0.45>=0.4로 여전히 분할됐을 값이다.
    """
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(0.0, 0.5, '것으로.'), tok(0.95, 1.3, '보입니다.')]  # gap=0.45s
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"갭(0.45s)이 여전히 과분할됨: {[s.text for s in txts]}"
    assert '것으로.' in txts[0].text and '보입니다.' in txts[0].text


def test_very_large_token_gap_without_silence_still_merges():
    """갭이 훨씬 커도(1.5s) 실제 Silence 토큰이 없으면 분할 근거가 못 된다.

    "문턱을 더 올리면 되지 않을까"류의 재도입을 막기 위해 극단값으로도 문턱
    자체가 없어졌음을 명시적으로 검증한다.
    """
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(0.0, 0.5, '것으로.'), tok(2.0, 2.5, '보입니다.')]  # gap=1.5s
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"큰 갭인데도 과분할됨(갭 기반 분기 재도입 의심): {[s.text for s in txts]}"


def test_zero_gap_midpunct_still_not_split():
    """gap=0(중간 온점, "very. much"류)은 여전히 안 끊긴다 — 회귀 없음 확인."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), tok(1.4, 1.8, ' much')]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"갭 없는 중간 온점이 과분할됨: {[s.text for s in txts]}"


def test_real_silence_still_hard_splits():
    """실제 Silence 토큰이 있으면 여전히 무조건 분할한다 — (b)분기 회귀 없음."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), sil(1.5, 2.0)]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1 and txts[0].text.strip() == 'very.'
    assert any(s.is_silence() for s in segments), "침묵 세그먼트가 없다"


def test_utterance_end_still_splits():
    """발화 끝(다음 토큰 없음)은 여전히 분할한다 — (a)분기 회귀 없음."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, '끝.')]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1 and txts[0].text.strip() == '끝.'


def test_large_gap_no_permanent_split_across_calls():
    """것으로/보입니다류 실전 재현(갭 기반 분기 완전 제거 버전): 꼬리 도착 전/후
    두 시점 재조회, 화자귀속 지연과 겹쳐도 병합 유지.

    diar-ON 경로의 인접-동일화자 병합은 두 조각이 같은 화자로 판정되면 자동
    재병합하지만, 화자분할이 비동기로 뒤처지면(diarization lag) 꼬리 세그먼트가
    아직 화자 미귀속 상태(get_lines_diarization의
    `punctuation_segment.start >= diarization_segments[-1].end` 분기)라 병합이
    실패할 수 있다 — 이는 여전히 유효한 2차 메커니즘이지만(1라운드에서 확인),
    갭 기반 분기가 완전히 제거된 지금은 애초에 compute_punctuations_segments
    단계에서 분할 자체가 안 일어나므로 diar-lag 유무와 무관하게 항상 병합 상태다.
    """
    from whisperlivekit.timed_objects import SpeakerSegment

    proc = make_processor(diarization=True)
    # 화자분할 커버리지가 것으로.까지만 도달(보입니다.는 아직 미도달 = 지연 재현)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=0.6, speaker=0)]

    # T1: "것으로."만 존재 — 꼬리 도착 전, "발화 끝"으로 오인되는 시점
    segs, _, _ = feed(proc, [tok(0.0, 0.5, '것으로.')], diarization=True, audio_time=0.5)
    txts = text_segs(segs)
    assert len(txts) == 1 and txts[0].text.strip() == '것으로.'

    # T2: "보입니다." 도착 (gap=0.45s, 실서버 재현값 + 화자귀속 지연 겹침)
    segs, _, _ = feed(proc, [tok(0.95, 1.3, '보입니다.')], diarization=True, audio_time=1.3)
    txts = text_segs(segs)
    assert len(txts) == 1, (
        f"갭+화자귀속 지연이 겹쳐 분리됨: {[s.text for s in txts]}"
    )
    assert '것으로.' in txts[0].text and '보입니다.' in txts[0].text
