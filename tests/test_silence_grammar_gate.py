# -*- coding: utf-8 -*-
"""문법-조건부 침묵 경계 게이트(silence-grammar-gate) — 단위 테스트.

같은 화자·같은 언어 연속 발화 중 짧은 pause만으로 문장이 구/단어 중간에서
잘리는 과분할(특히 Case B: "올렸"⏎"습니다"류 단어 중간 분절)을 억제하는
게이트를 검증한다. 설계 정본은 태스크 지시서(§design) 참조 — 이 파일은:

  1. 순수 헬퍼 should_split_after_silence의 3치 판정
  2. diar 경로(compute_punctuations_segments/get_lines_diarization) 게이트 적용
  3. 비-diar 경로(get_lines, 상태 보유 pending/decide-late) 게이트 적용
  4. 롤백 플래그(SILENCE_GRAMMAR_GATE_ENABLED) OFF 시 회귀 없음

을 커버한다. 패턴은 tests/test_punct_split.py·test_tail_reattachment.py를 재사용.
"""

from types import SimpleNamespace

from whisperlivekit.sentence_boundary import is_sentence_final_ko, should_split_after_silence
from whisperlivekit.timed_objects import (
    ASRToken,
    LanguageSwitch,
    Silence,
    SpeakerSegment,
    TimedText,
)
from whisperlivekit.tokens_alignment import (
    PENDING_RESOLVE_CAP,
    SILENCE_HARD_SECS,
    TokensAlignment,
)

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def make_processor(diarization: bool = False, gate_enabled: bool = True) -> TokensAlignment:
    state = SimpleNamespace(
        new_tokens=[],
        new_diarization=[],
        new_translation=[],
        new_tokens_buffer=[],
        new_translation_buffer=TimedText(),
    )
    args = SimpleNamespace(diarization=diarization, silence_grammar_gate=gate_enabled)
    proc = TokensAlignment(state=state, args=args, sep=' ')
    proc.beg_loop = 0.0
    return proc


def tok(start: float, end: float, text: str, detected_language=None) -> ASRToken:
    return ASRToken(start=start, end=end, text=text, detected_language=detected_language)


def sil(start: float, end: float, has_ended: bool = True) -> Silence:
    return Silence(start=start, end=end, has_ended=has_ended)


def feed(proc: TokensAlignment, tokens, **kwargs):
    """state.new_tokens에 넣고 update()로 all_tokens에 반영한 뒤 get_lines 호출."""
    proc.state.new_tokens = list(tokens)
    proc.update()
    return proc.get_lines(**kwargs)


def text_segs(segments):
    return [s for s in segments if s is not None and not s.is_silence()]


def joined_text(segments) -> str:
    return "".join(s.text or "" for s in text_segs(segments))


# ─── 1. should_split_after_silence 순수 헬퍼 단위 테스트 ─────────────────────

def test_should_split_ko_final_true():
    assert should_split_after_silence("지도를 올렸습니다", None) is True
    assert should_split_after_silence("중요한 강조했습니다", "다음") is True


def test_should_split_ko_nonfinal_false():
    """Case B 핵심 케이스 — 종결어미 없는 어절은 False(병합)."""
    assert should_split_after_silence("지도를 올렸", "습니다") is False
    assert should_split_after_silence("중요한 관련", "해서") is False


def test_should_split_en_capital_true_lowercase_false():
    assert should_split_after_silence("the island", "Or") is True
    assert should_split_after_silence("the island", "or") is False


def test_should_split_en_next_missing_is_none():
    """영어 + 다음 어절 미도착 → None(decide-late 보류 신호)."""
    assert should_split_after_silence("the island", None) is None


def test_should_split_empty_closing_defaults_true():
    assert should_split_after_silence("", "next") is True


# ─── 2. diar 경로 — 한국어 종결/미종결 ────────────────────────────────────────

def test_diar_ko_final_splits():
    """'…드렸습니다' + 짧은 침묵 → 분할(종결어미 확정)."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '말씀'), tok(0.4, 0.8, '드렸습니다'),
         sil(0.9, 1.2), tok(1.3, 1.7, '감사합니다')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"종결어미인데 분할 안 됨: {[s.text for s in txts]}"
    assert any('드렸습니다' in s.text for s in txts)


def test_diar_ko_nonfinal_merges_case_b_1():
    """Case B 회귀 테스트 — '올렸' 단독 + 짧은 침묵 뒤 '습니다' → 병합(분절 금지)."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸'),
         sil(0.9, 1.2), tok(1.3, 1.7, '습니다')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 1, f"Case B 분절 발생(단어 중간 쪼개짐): {[s.text for s in txts]}"
    assert '올렸습니다' in txts[0].text, f"병합 텍스트 불일치: {txts[0].text!r}"


def test_diar_ko_nonfinal_merges_case_b_2():
    """Case B 회귀 테스트 2 — '관련' 단독 + 짧은 침묵 뒤 '해서' → 병합."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '중요한'), tok(0.4, 0.8, '관련'),
         sil(0.9, 1.2), tok(1.3, 1.7, '해서')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 1, f"Case B 분절 발생: {[s.text for s in txts]}"
    assert '관련해서' in txts[0].text


# ─── 3. diar 경로 — 영어 대문자/소문자/미도착 ─────────────────────────────────

def test_diar_en_capital_next_splits():
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.5, 'island'), sil(0.6, 0.9), tok(1.0, 1.4, 'Or')],
        diarization=True, audio_time=1.4,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"영어 대문자 다음인데 병합됨: {[s.text for s in txts]}"


def test_diar_en_lowercase_next_merges():
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.5, 'island'), sil(0.6, 0.9), tok(1.0, 1.4, 'or')],
        diarization=True, audio_time=1.4,
    )
    txts = text_segs(segments)
    assert len(txts) == 1, f"영어 소문자 다음인데 분할됨: {[s.text for s in txts]}"
    assert 'islandor' in txts[0].text.replace(' ', '')


def test_diar_en_next_not_arrived_pending():
    """다음 어절 미도착 → 보류(pending) — 세그먼트가 아직 확정 안 됨."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.5, 'island'), sil(0.6, 0.9)],
        diarization=True, audio_time=0.9,
    )
    txts = text_segs(segments)
    assert len(txts) == 1
    assert txts[0].finalized is False, "다음 어절 미도착인데 이미 확정됨(pending 실패)"
    assert txts[0].finalize_trigger is None, (
        f"pending 상태인데 trigger 설정됨: {txts[0].finalize_trigger!r}"
    )


# ─── 4. SILENCE_HARD_SECS 안전망 ──────────────────────────────────────────────

def test_diar_hard_secs_always_splits_even_case_b():
    """긴 침묵(>=SILENCE_HARD_SECS)은 문법 무관 항상 분할 — Case B 문구여도 예외 없음."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=3.0, speaker=0)]
    hard_end = 0.9 + SILENCE_HARD_SECS + 0.2
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸'),
         sil(0.9, hard_end), tok(hard_end + 0.1, hard_end + 0.5, '습니다')],
        diarization=True, audio_time=hard_end + 0.5,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"긴 침묵인데 안전망이 분할 안 함: {[s.text for s in txts]}"


def test_diar_consecutive_silences_accumulate_d_eff():
    """연속 침묵 span 누적 — 개별로는 HARD_SECS 미만이지만 합산은 초과."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=3.0, speaker=0)]
    s1_end = 0.9 + (SILENCE_HARD_SECS / 2 + 0.05)
    s2_end = s1_end + (SILENCE_HARD_SECS / 2 + 0.1)
    assert (s2_end - 0.9) >= SILENCE_HARD_SECS, "테스트 픽스처가 누적 조건을 못 만족함"
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸'),
         sil(0.9, s1_end), sil(s1_end, s2_end), tok(s2_end + 0.1, s2_end + 0.5, '습니다')],
        diarization=True, audio_time=s2_end + 0.5,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"연속 침묵 누적이 안 됨(개별로는 짧은데 분할 안 됨): {[s.text for s in txts]}"


# ─── 5. 구두점으로 이미 종결된 경우는 게이트 비대상(회귀 없음) ────────────────

def test_diar_already_punctuated_bypasses_gate():
    """'갑니다.' 뒤 짧은 침묵 — 기존 온점 경로로 그대로 분할(게이트 비관여)."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '집에'), tok(0.4, 0.8, '갑니다.'),
         sil(0.9, 1.2), tok(1.3, 1.7, '그리고')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"이미 종결된 구두점인데 분할 실패: {[s.text for s in txts]}"
    closing = next(s for s in txts if '갑니다.' in s.text)
    assert closing.finalize_trigger == "punctuation", (
        f"게이트 비대상인데 트리거가 다름: {closing.finalize_trigger!r}"
    )


# ─── 6. hard_boundary(언어전환) 인접 시 병합 절대 차단 ───────────────────────

def test_diar_hard_boundary_blocks_merge():
    """[SIL, LS] 빈 스팬 뒤에도 hard_boundary가 침묵에 스탬프되어 병합을 막는다."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '중요한'), tok(0.4, 0.8, '관련'),
         sil(0.9, 1.2), LanguageSwitch(start=1.2, end=1.2, detected_language='en'),
         tok(1.3, 1.7, 'Hello')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"언어전환 경계인데 병합됨: {[s.text for s in txts]}"
    assert not any('관련Hello' in s.text.replace(' ', '') for s in txts), (
        "hard_boundary 스탬프 누락 — 병합 금지 규칙이 깨짐"
    )


# ─── 7. 화자 다르면 병합 절대 차단 ────────────────────────────────────────────

def test_diar_speaker_change_blocks_merge():
    """문법상 미종결(Case B 문구)이어도 화자가 바뀌면 병합하지 않는다."""
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [
        SpeakerSegment(start=0.0, end=1.2, speaker=0),
        SpeakerSegment(start=1.2, end=2.0, speaker=1),
    ]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '중요한'), tok(0.4, 0.8, '관련'),
         sil(0.9, 1.2), tok(1.3, 1.7, '다음')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, f"화자 전환인데 병합됨(문법 미종결에도 불구하고): {[s.text for s in txts]}"
    assert not any('관련다음' in s.text.replace(' ', '') for s in txts)


def test_diar_unresolved_speaker_stays_pending():
    """B의 화자가 아직 미귀속(speaker=-1)이면 병합도 분할확정도 하지 않고 보류."""
    proc = make_processor(diarization=True)
    # 화자 커버리지가 0.9~1.2까지만 있고, '다음'(1.3~1.7)은 diarization 지연 구간(overflow).
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=1.2, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '중요한'), tok(0.4, 0.8, '관련'),
         sil(0.9, 1.2), tok(1.3, 1.7, '다음')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    closing = next(s for s in txts if '관련' in s.text)
    assert closing.finalized is False, "화자 미귀속 B인데 이미 확정됨(pending 실패)"


# ─── 8. 캡 만료 + 플래핑 방지 메모 ────────────────────────────────────────────

def test_diar_cap_expiry_forces_split_and_memo_prevents_flapping():
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=10.0, speaker=0)]

    # 1) 짧은 침묵 직후 — 아직 캡 미만 → pending
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸'), sil(0.9, 1.2)],
        diarization=True, audio_time=1.2,
    )
    txts = text_segs(segments)
    assert txts and txts[-1].finalized is False, "캡 미만인데 이미 확정됨"

    # 2) 새 토큰 없이 시간만 흘러 캡 초과 → 분할 확정 + 메모
    beyond_cap_time = 1.2 + PENDING_RESOLVE_CAP + 0.5
    segments, _, _ = feed(proc, [], diarization=True, audio_time=beyond_cap_time)
    txts = text_segs(segments)
    assert txts and txts[-1].finalized is True, "캡 초과인데도 확정 안 됨"
    assert '올렸' in txts[-1].text

    # 3) 뒤늦게 B('습니다')가 도착 — 문법상으론 병합 대상이지만 메모가 분할을 유지해야 함
    segments, _, _ = feed(
        proc, [tok(beyond_cap_time + 0.1, beyond_cap_time + 0.5, '습니다')],
        diarization=True, audio_time=beyond_cap_time + 0.5,
    )
    assert not any('올렸습니다' in s.text.replace(' ', '') for s in text_segs(segments)), (
        "캡 만료로 이미 분할 확정됐는데 뒤늦은 B로 병합 재번복됨(메모 실패)"
    )


# ─── 9. flush로 pending 강제 해소 ─────────────────────────────────────────────

def test_diar_flush_forces_pending_resolution():
    proc = make_processor(diarization=True)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.5, 'island'), sil(0.6, 0.9)],
        diarization=True, audio_time=0.9, flush=False,
    )
    assert text_segs(segments)[0].finalized is False, "flush=False인데 미리 확정됨"

    segments, _, _ = feed(proc, [], diarization=True, audio_time=0.95, flush=True)
    txts = text_segs(segments)
    assert txts and txts[-1].finalized is True, "flush=True인데 확정 안 됨"


# ─── 10. SILENCE_GRAMMAR_GATE_ENABLED=False — 기존 동작과 동일(회귀 없음) ────

def test_gate_disabled_reproduces_legacy_unconditional_split():
    """게이트 비활성 시 Case B 문구도 예전처럼 무조건 분할된다(롤백 확인)."""
    proc = make_processor(diarization=True, gate_enabled=False)
    proc.state.new_diarization = [SpeakerSegment(start=0.0, end=2.0, speaker=0)]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸'),
         sil(0.9, 1.2), tok(1.3, 1.7, '습니다')],
        diarization=True, audio_time=1.7,
    )
    txts = text_segs(segments)
    assert len(txts) == 2, (
        f"게이트 비활성인데 병합됨(레거시 동작과 다름): {[s.text for s in txts]}"
    )


def test_gate_disabled_nondiar_reproduces_legacy_unconditional_split():
    proc = make_processor(diarization=False, gate_enabled=False)
    feed(proc, [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸')], diarization=False, audio_time=0.8)
    feed(proc, [sil(0.9, 1.2)], diarization=False, audio_time=1.2)
    segments, _, _ = feed(proc, [tok(1.3, 1.7, '습니다')], diarization=False, audio_time=1.7)

    validated_txts = [s for s in proc.validated_segments if not s.is_silence()]
    assert len(validated_txts) == 1, (
        f"게이트 비활성인데 즉시 분할 안 됨: {[s.text for s in validated_txts]}"
    )
    assert '올렸' in validated_txts[0].text
    txts = text_segs(segments)
    assert any(s.text.strip() == '습니다' for s in txts)


# ─── 11. 비-diar 경로 — Case B 병합 ───────────────────────────────────────────

def test_nondiar_case_b_merges():
    proc = make_processor(diarization=False)
    feed(proc, [tok(0.0, 0.4, '중요한'), tok(0.4, 0.8, '관련')], diarization=False, audio_time=0.8)
    feed(proc, [sil(0.9, 1.2)], diarization=False, audio_time=1.2)
    segments, _, _ = feed(proc, [tok(1.3, 1.7, '해서')], diarization=False, audio_time=1.7)

    validated_txts = [s for s in proc.validated_segments if not s.is_silence()]
    assert not validated_txts, (
        f"Case B인데 비-diar에서 이미 확정 커밋됨(분절): {[s.text for s in validated_txts]}"
    )
    txts = text_segs(segments)
    assert len(txts) == 1 and '관련해서' in txts[0].text, (
        f"비-diar 병합 실패: {[s.text for s in txts]}"
    )


# ─── 12. 비-diar 경로 — decide-late(재귀속 꼬리 vs 새 발화 B 구분) ───────────

def test_nondiar_decide_late_distinguishes_tail_from_b():
    """침묵 도착 시점엔 불완전한 텍스트("올렸")를, 재귀속된 꼬리("습니다")까지 흡수한
    뒤에야 완성형("올렸습니다")으로 판정해야 한다(§decide-late 원칙)."""
    proc = make_processor(diarization=False)
    feed(proc, [tok(6.0, 6.4, '지도를'), tok(6.4, 6.8, '올렸')], diarization=False, audio_time=6.8)

    # 짧은 침묵 도착 — 아직 '올렸'만 보이므로(미종결) pending
    feed(proc, [sil(7.0, 7.5)], diarization=False, audio_time=7.5)
    assert proc._nondiar_pending_silence is not None, "짧은 침묵인데 pending 진입 안 함"

    # 유보됐던 꼬리(start=6.8 < silence.start=7.0) 도착 — 재귀속이지 B가 아니다.
    # 이 시점에 성급히 병합/분할 판정을 내리면 안 되고 계속 보류해야 한다.
    feed(proc, [tok(6.8, 7.0, '습니다')], diarization=False, audio_time=7.5)
    assert proc._nondiar_pending_silence is not None, (
        "재귀속 꼬리가 새 발화 B로 오판되어 게이트가 조기 해소됨"
    )
    assert proc._current_line_text() == '지도를올렸습니다', (
        f"꼬리가 현재 줄에 흡수되지 않음: {proc._current_line_text()!r}"
    )

    # 진짜 새 발화 B(start=7.6 >= silence.start=7.0) 도착 — 이제 완성된 텍스트
    # "올렸습니다"(종결어미 있음)로 판정하므로 분할돼야 한다.
    segments, _, _ = feed(proc, [tok(7.6, 8.0, '그래서')], diarization=False, audio_time=8.0)
    assert proc._nondiar_pending_silence is None, "새 발화 B 도착 후에도 게이트가 안 풀림"

    validated_txts = [s for s in proc.validated_segments if not s.is_silence()]
    assert validated_txts and '올렸습니다' in validated_txts[-1].text, (
        f"재귀속 완료 후 종결 판정 실패: {[s.text for s in validated_txts]}"
    )
    txts = text_segs(segments)
    assert any(s.text.strip() == '그래서' for s in txts)


# ─── 13. 비-diar 경로 — 캡 만료 + flush ───────────────────────────────────────

def test_nondiar_cap_expiry_forces_split():
    proc = make_processor(diarization=False)
    feed(proc, [tok(0.0, 0.4, '지도를'), tok(0.4, 0.8, '올렸')], diarization=False, audio_time=0.8)
    feed(proc, [sil(0.9, 1.2)], diarization=False, audio_time=1.2)
    assert proc._nondiar_pending_silence is not None

    beyond_cap_time = 1.2 + PENDING_RESOLVE_CAP + 0.5
    feed(proc, [], diarization=False, audio_time=beyond_cap_time)
    assert proc._nondiar_pending_silence is None, "캡 초과인데 pending이 안 풀림"
    validated_txts = [s for s in proc.validated_segments if not s.is_silence()]
    assert validated_txts and '올렸' in validated_txts[-1].text


def test_nondiar_flush_forces_pending_resolution():
    proc = make_processor(diarization=False)
    feed(proc, [tok(0.0, 0.5, 'island')], diarization=False, audio_time=0.5)
    feed(proc, [sil(0.6, 0.9)], diarization=False, audio_time=0.9)
    assert proc._nondiar_pending_silence is not None

    feed(proc, [], diarization=False, audio_time=0.95, flush=True)
    assert proc._nondiar_pending_silence is None, "flush=True인데 pending이 안 풀림"
    validated_txts = [s for s in proc.validated_segments if not s.is_silence()]
    assert validated_txts and 'island' in validated_txts[-1].text


# ─── 14. is_sentence_final_ko 재사용 확인(게이트가 실제로 이 판별기를 쓰는지) ──

def test_gate_reuses_is_sentence_final_ko_not_a_new_dictionary():
    assert is_sentence_final_ko('드렸습니다') is True
    assert is_sentence_final_ko('올렸') is False
    assert should_split_after_silence('드렸습니다', None) == is_sentence_final_ko('드렸습니다')
    assert should_split_after_silence('올렸', '습니다') == is_sentence_final_ko('올렸')


# ─── 15. Case B(Exp-188) — 짧은 세그먼트 화자 오귀속(diarization 노이즈)이
#          문법-미종결 단어를 화자불일치로 강제분할하지 않아야 한다 ───────────
#
# kor1(단일화자 낭독) 실측(Exp-186/188, --trace-tokens N=3 R3)에서 Sortformer가
# "강"(← "소모 강요"의 "강요"가 쪼개진 자리) 같은 아주 짧은 텍스트 세그먼트에만
# 순간적으로 다른 화자를 귀속하는 노이즈를 관찰했다 — 서버 로그:
#   [SilenceGate] start=57.41 end=57.89 d_eff=0.48 last_word='강' next_word='요'
#     speakers=(1, 1) ... decision=merge path=merge   (초기 tick, 정상)
#   [SilenceGate] start=57.41 end=57.89 d_eff=0.48 last_word='강' next_word='고'
#     speakers=(1, 2) ... decision=split path=split_grammar   (이후 tick, 오귀속)
# 같은 침묵 위치에서 diarization 재계산(무상태)만으로 화자값이 (1,1)→(1,2)로
# 플립되고, `_gate_decide`의 화자불일치 분기가 문법 판정보다 우선해 무조건
# 분할시켜 "강"이 "요"와 분리 확정된다(정답 "강요"가 "강."⏎"요 등..."로 절단).
# 이 테스트는 그 정확한 메커니즘을 TokensAlignment 단위에서 재현한다.

def test_diar_short_segment_speaker_flip_does_not_force_case_b_split():
    """아주 짧은 텍스트 세그먼트('강')만 순간적으로 다른 화자로 오귀속돼도
    문법상 미종결 단어 분리(Case B)를 강제하면 안 된다 — 직전 확정 화자를 승계."""
    proc = make_processor(diarization=True)
    # '강'(0.8~1.1, 길이 0.3s)만 감싸는 diar 세그먼트가 순간적으로 다른 화자(1)로
    # 잘못 귀속됨 — 앞뒤 '능력과'/'요'는 모두 화자 0으로 정상 귀속.
    proc.state.new_diarization = [
        SpeakerSegment(start=0.0, end=0.7, speaker=0),
        SpeakerSegment(start=0.7, end=1.1, speaker=1),   # 노이즈: '강' 구간만 다른 화자
        SpeakerSegment(start=1.1, end=3.0, speaker=0),
    ]
    segments, _, _ = feed(
        proc,
        [tok(0.0, 0.4, '능력과'), sil(0.4, 0.7),
         tok(0.8, 1.1, '강'), sil(1.1, 1.4),
         tok(1.5, 1.9, '요')],
        diarization=True, audio_time=1.9,
    )
    txts = text_segs(segments)
    joined = joined_text(segments)
    assert '강요' in joined.replace(' ', ''), (
        f"Case B 재현 — 짧은 세그먼트 화자오귀속으로 '강'/'요'가 분리됨: {[s.text for s in txts]}"
    )
    assert not any(s.text.strip() == '강' for s in txts), (
        f"'강'이 단독으로 확정됨(단어 중간 분절): {[s.text for s in txts]}"
    )
