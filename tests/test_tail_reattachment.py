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
    PUNCT_SPLIT_GAP_SECS,
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


# ─── 9. 경로4(구두점-매개 꼬리분리) 사각지대 갭 회귀 ─────────────────────────────
#
# 1단계 조사 결론(정확한 커밋 메커니즘):
# compute_punctuations_segments()는 매 호출마다 self.all_tokens 전체로 새로 계산되고
# finalized 플래그도 매번 새로 부여된다(영속 상태 아님) — 그래서 "먼저 굳어 버려서
# 되돌릴 수 없는" lock은 실제로 존재하지 않는다. 그런데도 분리가 "영구화"돼 보이는
# 이유는 더 단순하다: 꼬리 토큰 도착 전엔 idx+1>=len(tokens)("발화 끝")로 온점이
# 분할점을 얻고, 꼬리 도착 후 재계산에서도 nxt.start - tokens[idx].end 라는 고정된
# 타임스탬프 갭을 그대로 재평가하므로 매번 같은(틀린) 결론에 도달한다 — 입력이
# 안 바뀌니 결과도 안 바뀔 뿐이다. audio_processor.MIN_DURATION_REAL_SILENCE(0.4)
# 보다 짧은 갭(예 0.32s, bong1 실측 "자빠졌/는데")은 Silence 토큰을 만들지 않지만
# 구 PUNCT_SPLIT_GAP_SECS(0.3) 문턱은 넘어 "실제 pause"로 오판된다 — [0.3,0.4) 사각지대.
#
# finalized 플래그는 이 버그와 무관하다(중요 — Direction B 원안을 기각한 근거):
# whisperlivekit/web/live_transcription.js의 renderLinesWithBuffer()는 lines[]의
# 각 항목마다 finalized/completed 값과 무관하게 <p>.textcontent 한 줄을 만든다
# (item.finalized 참조 자체가 코드에 없음 — grep으로 확인). scripts/eval.py의
# hyp_sentences(경로 A: `[line["text"] for line in result.lines if line.get("text")]`,
# 경로 C: DOM `.textcontent` 스냅샷)도 finalized 여부를 보지 않고 text만으로 줄을 센다.
# 즉 "확정 유예"만 확장해선(Direction B 원안) 이미 갈라진 텍스트 자체를 되돌리지 못해
# hyp 문장수·꼬리분리 증상을 전혀 개선하지 못한다 — 그래서 Direction A(문턱 정합)만
# 적용하고 Direction B는 채택하지 않았다.

def test_audio_processor_min_silence_matches_punct_split_gap():
    """순환 임포트 회피로 값이 중복 정의된 두 상수가 어긋나지 않는지 회귀 방지.

    audio_processor.py가 tokens_alignment.py를 임포트하므로 역방향 임포트는 순환
    임포트가 된다 — 그래서 두 상수는 값으로만 동기화하고, 이 테스트로 드리프트를 잡는다.
    """
    from whisperlivekit.audio_processor import MIN_DURATION_REAL_SILENCE
    assert PUNCT_SPLIT_GAP_SECS == MIN_DURATION_REAL_SILENCE == 0.4


def test_deadzone_gap_no_split_at_source():
    """[0.3,0.4) 사각지대(bong1 실측 0.32s) — compute_punctuations_segments 원천에서 병합."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(0.0, 0.5, '것으로.'), tok(0.82, 1.2, '보입니다.')]  # gap=0.32s
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"사각지대 갭(0.32s)이 여전히 과분할됨: {[s.text for s in txts]}"
    assert '것으로.' in txts[0].text and '보입니다.' in txts[0].text


def test_gap_at_new_threshold_still_splits():
    """문턱 정합 후에도 실제 pause(>=0.4s)는 여전히 분할한다 — 과교정(never split) 방지."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(0.0, 0.5, '것으로.'), tok(0.9, 1.3, '보입니다.')]  # gap=0.4s
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 2, f"신 문턱(0.4s) 이상 갭인데 분할 안 됨: {[s.text for s in txts]}"


def test_zero_gap_midpunct_still_not_split():
    """gap=0(중간 온점, "very. much"류)은 여전히 안 끊긴다 — 문턱 상향 후 회귀 없음 확인."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), tok(1.4, 1.8, ' much')]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1, f"갭 없는 중간 온점이 과분할됨: {[s.text for s in txts]}"


def test_real_silence_still_hard_splits():
    """실제 Silence 토큰이 있으면(0.4s 이상 침묵) 여전히 무조건 분할한다 — 회귀 없음."""
    proc = make_processor(diarization=True)
    proc.all_tokens = [tok(1.0, 1.4, 'very.'), sil(1.5, 2.0)]
    segments = proc.compute_punctuations_segments()
    txts = text_segs(segments)
    assert len(txts) == 1 and txts[0].text.strip() == 'very.'
    assert any(s.is_silence() for s in segments), "침묵 세그먼트가 없다"


def test_deadzone_gap_no_permanent_split_across_calls():
    """것으로/보입니다류 실전 재현: 화자분할 지연과 겹쳐도 사각지대 갭 자체가 없으면
    (Direction A) 애초에 분할되지 않아 화자귀속 지연에 영향받지 않는다.

    실전에서 diar-ON 경로가 "영구" 분리로 관찰되는 이유는 사각지대 갭 하나만으로는
    설명되지 않는다 — get_lines_diarization()의 인접-동일화자 병합 단계가 두 조각을
    같은 화자로 판정하면 자동으로 재병합되기 때문이다(이 부분은 사각지대 갭과
    무관하게 항상 존재하던 기존 동작). 진짜로 "영구" 분리되려면 그 자동 재병합이
    실패해야 한다 — 예: 화자분할이 비동기로 뒤처져(diarization lag) 꼬리 세그먼트가
    아직 어떤 diar 세그먼트에도 덮이지 않은 시점(get_lines_diarization의
    `punctuation_segment.start >= diarization_segments[-1].end` 분기 — 화자 미귀속
    상태로 diarization_buffer에만 쌓임)에 재계산되면, 머리(이미 화자 귀속됨)와
    화자값이 달라(귀속됨 vs 기본값 -1) 병합되지 못하고 2개로 굳는다.

    이 테스트는 그 지연 상황을 재현한다: diar 커버리지가 "것으로."까지만(0.0~0.6)
    도달하고 "보입니다."(start=0.82)는 아직 안 덮인 상태. 수정 전엔 사각지대 갭이
    compute_punctuations_segments 단계에서 먼저 2개로 쪼개 놓고, 그 다음 화자귀속
    지연이 재병합을 막아 2개로 "영구" 고정된다(진짜 sbs1/bong1처럼). 수정 후
    (Direction A)엔 애초에 소스 단계에서 1개로 합쳐지므로, 그 뒤 화자귀속이
    지연되든 말든 세그먼트 개수엔 영향이 없다 — 즉 Direction A는 화자분할 타이밍과
    무관하게 견고하다.
    """
    from whisperlivekit.timed_objects import SpeakerSegment

    proc = make_processor(diarization=True)
    # 화자분할 커버리지가 것으로.까지만 도달(보입니다.는 아직 미도달 = 지연 재현)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=0.6, speaker=0)]

    # T1: "것으로."만 존재 — 꼬리 도착 전, "발화 끝"으로 오인되는 시점
    segs, _, _ = feed(proc, [tok(0.0, 0.5, '것으로.')], diarization=True, audio_time=0.5)
    txts = text_segs(segs)
    assert len(txts) == 1 and txts[0].text.strip() == '것으로.'

    # T2: "보입니다." 도착 (gap=0.32s, 사각지대 + 화자귀속 지연 겹침)
    segs, _, _ = feed(proc, [tok(0.82, 1.2, '보입니다.')], diarization=True, audio_time=1.2)
    txts = text_segs(segs)
    assert len(txts) == 1, (
        f"사각지대 갭+화자귀속 지연이 겹쳐 분리 유지됨: {[s.text for s in txts]}"
    )
    assert '것으로.' in txts[0].text and '보입니다.' in txts[0].text
