# -*- coding: utf-8 -*-
"""언어전환 경계 재조정(boundary reconcile) 계층 유닛 테스트 (Exp-192, 모델 불필요).

커밋 단계별로 확장된다:
- 커밋1: ASRToken.retracted 필드 + with_offset 전필드 보존.
- 커밋3: ReconcileWindow — 복원/대체/마감 3중(D1/D2/D3)/단일 컷포인트 원자성/플래그 OFF 레거시.
- 커밋4: 시간 소유권 dedup(드롭/supersede/id 승계/정상 반복 보호).
- 커밋5: 동적 keep 클램프.
"""
from whisperlivekit import boundary_reconcile
from whisperlivekit.boundary_reconcile import (
    COVER_TOL,
    RECONCILE_DEADLINE_SECS,
    ReconcileWindow,
    TombstoneEntry,
)
from whisperlivekit.timed_objects import ASRToken, LanguageSwitch, Silence
from whisperlivekit.tokens_alignment import TokensAlignment


def _make_alignment():
    """실제 State/args 없이 TokensAlignment를 최소 구성(test_boundary_retract.py와 동일 패턴)."""

    class _Args:
        diarization = False

    class _State:
        new_tokens = []
        new_diarization = []
        new_translation = []
        new_tokens_buffer = []
        new_translation_buffer = None

    return TokensAlignment(_State(), _Args(), sep="")


def _visible_texts(ta):
    return [t.text for t in ta.all_tokens
            if not t.is_silence() and not t.is_boundary()
            and not getattr(t, "retracted", False)]


def _tok(start, end, text, lang, retracted=False):
    return ASRToken(start=start, end=end, text=text,
                    detected_language=lang, retracted=retracted)


def _retract_marker(boundary_t, new_lang, prev_lang, floor):
    return LanguageSwitch(
        start=boundary_t, end=boundary_t, detected_language=new_lang,
        retract_from=boundary_t, prev_language=prev_lang, retract_floor=floor,
    )


# ─── 커밋1: 데이터 모델 ────────────────────────────────────────────────────────


def test_asrtoken_retracted_defaults_false():
    t = ASRToken(start=1.0, end=1.1, text="hello")
    assert t.retracted is False


def test_with_offset_preserves_all_fields():
    """with_offset은 start/end만 이동하고 나머지 전 필드를 보존해야 한다.

    dataclasses.replace 기반이라 이후 필드가 추가돼도 복사 누락이 생기지 않는다 —
    과거 위치 인자 나열 방식은 새 필드(retracted 등)를 조용히 잃는 footgun이었다.
    """
    t = ASRToken(
        start=10.0, end=10.5, text=" 미니스터", speaker=3,
        detected_language="ko", probability=0.87, retracted=True,
    )
    moved = t.with_offset(2.5)
    assert moved is not t
    assert moved.start == 12.5
    assert moved.end == 13.0
    assert moved.text == " 미니스터"
    assert moved.speaker == 3
    assert moved.detected_language == "ko"
    assert moved.probability == 0.87
    assert moved.retracted is True
    # 원본 불변
    assert t.start == 10.0 and t.end == 10.5


def test_with_offset_copies_every_declared_field():
    """필드 목록이 늘어나도 with_offset이 전부 복사하는지 구조적으로 고정한다."""
    import dataclasses
    t = ASRToken(start=0.0, end=0.1, text="x")
    moved = t.with_offset(1.0)
    for f in dataclasses.fields(ASRToken):
        if f.name in ("start", "end"):
            continue
        assert getattr(moved, f.name) == getattr(t, f.name), f.name


# ─── 커밋3: 재조정 계층 — 복원 ─────────────────────────────────────────────────


def test_restore_uncovered_tombstone_reappears_in_time_order():
    """미커버 tombstone은 resolve 시 복원(un-retract)되어 가시 뷰에 시간순 재등장한다.

    ko 꼬리 " 반갑습니다"(11.0)가 잠정 철회됐지만 en 재디코딩이 12.5부터만 나와
    그 구간을 못 덮음(Δ=1.5 > COVER_TOL) → 컷 T-τ=12.0보다 앞이라 복원.
    """
    ta = _make_alignment()
    tail = _tok(11.0, 11.4, " 반갑습니다", "ko")
    ta.all_tokens = [tail]
    marker = _retract_marker(12.0, new_lang="en", prev_lang="ko", floor=10.0)
    en1 = _tok(12.5, 12.6, " Nice", "en")   # D1: 12.5 >= 12.0 + PASS_EPS → 즉시 마감
    ta._insert_with_reattachment([marker, en1])

    assert tail.retracted is False  # 복원됨
    assert ta.reconciler.window.resolved is True
    assert ta.reconciler.window.resolve_reason == "d1"
    # 가시 뷰 시간순 재등장 — 경계 마커 앞(구언어 세그먼트)에 그대로 위치.
    segs = ta.compute_punctuations_segments()
    texts = [s.text for s in segs if not s.is_silence()]
    assert texts == [" 반갑습니다", " Nice"]
    assert segs[0].hard_boundary is True


def test_restore_all_when_no_new_lang_token_arrives_d3():
    """D3 캡: 신언어 토큰이 하나도 안 오면 audio_time 마감 시 전량 복원된다."""
    ta = _make_alignment()
    tail = _tok(11.5, 11.9, " 미니스터.", "ko")
    ta.all_tokens = [tail]
    marker = _retract_marker(12.0, new_lang="en", prev_lang="ko", floor=10.0)
    ta._insert_with_reattachment([marker])
    assert tail.retracted is True  # 잠정 tombstone(subzone)

    # 마감 전에는 유지
    ta.reconciler.check_deadline(12.0 + RECONCILE_DEADLINE_SECS - 0.1)
    assert ta.reconciler.window.resolved is False
    # audio_time 기준 3.0s 경과 → D3 전량 복원
    ta.reconciler.check_deadline(12.0 + RECONCILE_DEADLINE_SECS)
    assert ta.reconciler.window.resolved is True
    assert ta.reconciler.window.resolve_reason == "d3"
    assert tail.retracted is False
    assert _visible_texts(ta) == [" 미니스터."]


def test_d3_hook_wired_through_get_lines_audio_time():
    """get_lines(audio_time=...) 경유로도 D3가 발동한다(벽시계 미사용 배선 확인)."""
    ta = _make_alignment()
    tail = _tok(11.5, 11.9, " 꼬리", "ko")
    ta.all_tokens = [tail]
    ta._insert_with_reattachment([_retract_marker(12.0, "en", "ko", 10.0)])
    assert tail.retracted is True
    ta.get_lines(diarization=False, audio_time=12.0 + RECONCILE_DEADLINE_SECS)
    assert tail.retracted is False


# ─── 커밋3: 재조정 계층 — 대체(미니스터 시나리오) ───────────────────────────────


def test_replace_covered_samescript_subzone_minister_scenario():
    """구역2 확대 + 커버 도착 = 영구 tombstone — "미니스터."→" Minister..." 중복 소멸.

    ko "미니스터."(11.9)는 같은 스크립트라 기존 zone2에선 보존됐지만(→중복 확정),
    subzone 잠정 철회 후 en " Minister"(12.0)가 start 근접(Δ=0.1)으로 커버 → 대체.
    """
    ta = _make_alignment()
    minister_ko = _tok(11.9, 12.3, " 미니스터.", "ko")
    ta.all_tokens = [minister_ko]
    marker = _retract_marker(12.4, new_lang="en", prev_lang="ko", floor=10.0)
    en1 = _tok(12.0, 12.4, " Minister", "en")
    en2 = _tok(12.8, 12.9, " of", "en")  # 진행도 12.8 >= 12.4+0.25 → D1 마감
    ta._insert_with_reattachment([marker, en1, en2])

    assert minister_ko.retracted is True  # 영구 tombstone(대체)
    w = ta.reconciler.window
    assert w.resolved is True and w.resolve_reason == "d1"
    assert w.entries[0].covered is True
    assert w.entries[0].zone == "zone2_samescript"
    assert _visible_texts(ta) == [" Minister", " of"]


def test_samescript_subzone_flag_off_preserves_legacy_zone2():
    """RECONCILE_SAMESCRIPT_SUBZONE_ENABLED=False면 같은 스크립트 토큰은 철회 대상이 아니다."""
    import pytest  # noqa: F401
    old = boundary_reconcile.RECONCILE_SAMESCRIPT_SUBZONE_ENABLED
    boundary_reconcile.RECONCILE_SAMESCRIPT_SUBZONE_ENABLED = False
    try:
        ta = _make_alignment()
        minister_ko = _tok(11.9, 12.3, " 미니스터.", "ko")
        ta.all_tokens = [minister_ko]
        ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
        assert minister_ko.retracted is False  # 보존(기존 zone2 보수성)
    finally:
        boundary_reconcile.RECONCILE_SAMESCRIPT_SUBZONE_ENABLED = old


# ─── 커밋3: 마감 D2 (마커 도착) ────────────────────────────────────────────────


def test_d2_silence_marker_resolves_window():
    """다음 Silence 마커 도착 시 활성 창이 즉시 resolve된다(미커버분 복원)."""
    ta = _make_alignment()
    tail = _tok(11.5, 11.9, " 꼬리", "ko")
    ta.all_tokens = [tail]
    ta._insert_with_reattachment([_retract_marker(12.0, "en", "ko", 10.0)])
    assert tail.retracted is True
    ta._insert_with_reattachment([Silence(start=12.3, end=12.9)])
    w = ta.reconciler.window
    assert w.resolved is True and w.resolve_reason == "d2_silence"
    assert tail.retracted is False


def test_multi_boundary_new_marker_resolves_previous_window_and_rearms():
    """다중 경계: 새 LanguageSwitch(철회 arm) 도착 시 이전 창 resolve 후 재arm — 활성 최대 1개."""
    ta = _make_alignment()
    tail1 = _tok(9.9, 10.1, " first", "ko")
    ta.all_tokens = [tail1]
    ta._insert_with_reattachment([_retract_marker(10.0, "en", "ko", 8.0)])
    assert tail1.retracted is True
    w1 = ta.reconciler.window
    assert w1.boundary_t == 10.0

    # 두 번째 경계(en→ko) 마커가 신언어 토큰 도착 전에 곧바로 도착 — 이전 창은
    # d2_new_boundary로 마감(무커버 → 복원)되고 새 창이 열린다(활성 최대 1개).
    ta._insert_with_reattachment([_retract_marker(15.0, "ko", "en", 12.0)])
    w2 = ta.reconciler.window
    assert w2 is not w1
    assert w1.resolved is True and w1.resolve_reason == "d2_new_boundary"
    assert tail1.retracted is False  # 이전 창 미커버분 복원
    assert w2.boundary_t == 15.0 and w2.resolved is False


def test_new_lang_token_after_arm_triggers_d1_before_next_boundary():
    """arm 직후 boundary+PASS_EPS를 넘는 신언어 토큰이 오면 다음 마커를 기다리지 않고
    D1로 즉시 마감된다 — 다중 경계에서 창이 겹쳐 늘어지지 않는 근거."""
    ta = _make_alignment()
    tail1 = _tok(9.9, 10.1, " first", "ko")
    ta.all_tokens = [tail1]
    ta._insert_with_reattachment([_retract_marker(10.0, "en", "ko", 8.0)])
    w1 = ta.reconciler.window
    ta._insert_with_reattachment([_tok(10.3, 10.5, " new", "en")])
    assert w1.resolved is True and w1.resolve_reason == "d1"


# ─── 커밋3: 단일 컷포인트 원자성 ───────────────────────────────────────────────


def test_single_cutpoint_no_partial_restore_hole():
    """컷 파티션은 단일 임계 — 복원/대체가 교차(구멍)하지 않는다."""
    w = ReconcileWindow(boundary_t=12.0, floor=10.0, prev_lang="ko", new_lang="en")
    early = TombstoneEntry(token=_tok(10.5, 10.6, " 이른꼬리", "ko", retracted=True), zone="zone2_samescript")
    late = TombstoneEntry(token=_tok(11.9, 12.0, " 늦은꼬리", "ko", retracted=True), zone="zone1")
    w.entries = [early, late]
    w.observe(_tok(12.1, 12.2, " New", "en"))  # 컷 T=12.1, 임계=11.6
    w.resolve("test")
    assert early.token.retracted is False and early.replaced is False   # < 11.6 → 복원
    assert late.token.retracted is True and late.replaced is True       # >= 11.6 → 대체


def test_cutpoint_snaps_to_word_start_no_subword_fragment():
    """컷이 하위단어 연속 중간에 떨어지면 단어 시작 방향으로 스냅 — "올렸"⏎"습니다" 파편 금지.

    " 올렸"(11.50)+"습니다"(11.75, 공백 접두 없음·갭 0.15s)는 한 단어다. 컷 임계
    (T−τ=11.70)가 두 토큰 사이에 떨어져도 단어 전체가 대체돼야 한다 — "올렸"만
    복원되면 단어 중간 분절(Case B) 파편이 남는다.
    """
    w = ReconcileWindow(boundary_t=12.0, floor=10.0, prev_lang="ko", new_lang="en")
    part1 = TombstoneEntry(token=_tok(11.50, 11.60, " 올렸", "ko", retracted=True), zone="zone2_samescript")
    part2 = TombstoneEntry(token=_tok(11.75, 11.85, "습니다", "ko", retracted=True), zone="zone1")
    w.entries = [part1, part2]
    w.observe(_tok(12.20, 12.30, " Raised", "en"))  # T=12.2, 임계=11.7 — part1/part2 사이
    w.resolve("test")
    # 스냅: part2가 part1과 같은 단어(공백 접두 없음·갭<=0.3) → 단어 전체 대체.
    assert part1.token.retracted is True and part2.token.retracted is True


def test_cutpoint_does_not_snap_across_word_boundary():
    """임계 위 토큰이 공백 접두(새 단어)면 스냅하지 않는다 — 앞 단어는 복원 유지."""
    w = ReconcileWindow(boundary_t=12.0, floor=10.0, prev_lang="ko", new_lang="en")
    word1 = TombstoneEntry(token=_tok(11.40, 11.50, " 앞단어", "ko", retracted=True), zone="zone2_samescript")
    word2 = TombstoneEntry(token=_tok(11.80, 11.90, " 뒷단어", "ko", retracted=True), zone="zone1")
    w.entries = [word1, word2]
    w.observe(_tok(12.25, 12.35, " New", "en"))  # T=12.25, 임계=11.75 — 단어 경계와 일치
    w.resolve("test")
    assert word1.token.retracted is False
    assert word2.token.retracted is True


# ─── 커밋3: RECONCILE_ENABLED=False 레거시 재현 ────────────────────────────────


def test_flag_off_reproduces_legacy_destructive_pop(monkeypatch):
    """RECONCILE_ENABLED=False면 철회가 파괴적 pop으로 재현되고 창도 arm되지 않는다."""
    monkeypatch.setattr(boundary_reconcile, "RECONCILE_ENABLED", False)
    ta = _make_alignment()
    stale = _tok(13.06, 13.50, "? Who is the.", "en")
    keep_ko = _tok(12.5, 12.9, "새 언어로 이미 커밋됨", "ko")
    ta.all_tokens = [keep_ko, stale]
    marker = _retract_marker(13.0, new_lang="ko", prev_lang="en", floor=11.0)
    ta._insert_with_reattachment([marker])
    # 파괴적 제거: 리스트에서 실제로 사라진다(tombstone 아님).
    assert all(t is not stale for t in ta.all_tokens)
    assert not getattr(stale, "retracted", False)
    assert ta.reconciler.window is None
    # 같은 스크립트 subzone도 미적용(레거시 zone2 보수성) — keep_ko 보존.
    assert keep_ko in ta.all_tokens


def test_flag_off_marker_and_deadline_are_noop(monkeypatch):
    """플래그 OFF에서는 D2/D3 훅도 완전 no-op(창 부재 + 예외 없음)."""
    monkeypatch.setattr(boundary_reconcile, "RECONCILE_ENABLED", False)
    ta = _make_alignment()
    ta._insert_with_reattachment([Silence(start=1.0, end=1.5)])
    ta.reconciler.check_deadline(100.0)
    assert ta.reconciler.window is None


# ─── 커밋3: 창 관측 세부 ──────────────────────────────────────────────────────


def test_cover_tolerance_boundary_values():
    """커버 판정은 |Δstart| <= COVER_TOL 근접만 사용(토큰 end는 가짜라 미사용)."""
    w = ReconcileWindow(boundary_t=12.0, floor=10.0, prev_lang="ko", new_lang="en")
    e = TombstoneEntry(token=_tok(11.9, 12.0, " 꼬리", "ko", retracted=True), zone="zone1")
    w.entries = [e]
    w.observe(_tok(11.9 + COVER_TOL + 0.01, 12.6, " far", "en"))
    assert e.covered is False
    w.observe(_tok(11.9 + COVER_TOL - 0.01, 12.5, " near", "en"))
    assert e.covered is True


def test_observe_ignores_non_new_lang_tokens():
    """구언어(재귀속 꼬리 등) 토큰은 창 관측 대상이 아니다 — D1 진행도에 미반영."""
    ta = _make_alignment()
    ta.all_tokens = [_tok(11.5, 11.9, " 꼬리", "ko")]
    ta._insert_with_reattachment([_retract_marker(12.0, "en", "ko", 10.0)])
    ta._insert_with_reattachment([_tok(13.0, 13.1, " 한국어재귀속", "ko")])
    w = ta.reconciler.window
    assert w.resolved is False
    assert w.new_high_start is None


def test_d1_requires_pass_eps_progress():
    """D1은 신언어 진행도가 boundary_t+PASS_EPS를 넘어야 발동한다.

    토큰 간격은 OWN_TOL(0.4)보다 크게 둔다 — 근접 연속 토큰은 시간 소유권
    dedup(①)의 대상이라 이 테스트의 관심사(D1 진행도)와 분리한다.
    """
    ta = _make_alignment()
    ta.all_tokens = [_tok(11.5, 11.9, " 꼬리", "ko")]
    ta._insert_with_reattachment([_retract_marker(12.0, "en", "ko", 10.0)])
    ta._insert_with_reattachment([_tok(11.9, 12.1, " early", "en")])  # 11.9 < 12.25
    assert ta.reconciler.window.resolved is False
    ta._insert_with_reattachment([_tok(12.35, 12.5, " past", "en")])  # 12.35 >= 12.25
    assert ta.reconciler.window.resolved is True
    assert ta.reconciler.window.resolve_reason == "d1"


# ─── 커밋4: 시간 소유권 dedup ─────────────────────────────────────────────────


def test_timededup_drops_identical_reemission():
    """① 동일 재방출: 기존 커버리지가 신규를 포함 + start 근접 → 신규 배치 드롭."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    batch1 = [_tok(12.5, 12.6, " It's", "en"), _tok(12.8, 12.9, " just", "en"),
              _tok(13.1, 13.2, " a", "en")]
    ta._insert_with_reattachment(batch1)
    n_before = len(ta.all_tokens)
    # 재디코딩 창 겹침 이중방출 — 같은 구간을 같은 start로 다시 방출
    dup = [_tok(12.5, 12.6, " It's", "en"), _tok(12.8, 12.9, " just", "en"),
           _tok(13.1, 13.2, " a", "en")]
    ta._insert_with_reattachment(dup)
    assert len(ta.all_tokens) == n_before  # 전량 드롭
    assert _visible_texts(ta).count(" It's") == 1


def test_timededup_drops_jittered_exact_reemission():
    """② 지터(Δstart<=OWN_TOL)·표기 변형(대소문자/양끝 구두점)이 있어도 정규화
    완전일치 재방출은 드롭된다."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    ta._insert_with_reattachment([_tok(12.5, 12.6, " Everyone", "en"),
                                  _tok(12.9, 13.0, " here", "en")])
    n_before = len(ta.all_tokens)
    dup = [_tok(12.55, 12.65, " everyone,", "en"), _tok(12.95, 13.05, " here.", "en")]
    ta._insert_with_reattachment(dup)
    assert len(ta.all_tokens) == n_before
    assert all(t.text not in (" everyone,", " here.") for t in ta.all_tokens)


def test_no_drop_for_consecutive_new_words_ytn2_regression():
    """실측 회귀(ytn2 98.97): 창 내 조밀 간격(0.14s)의 **연속 증분 방출 다음 단어**는
    텍스트 비매칭이므로 절대 드롭/supersede되지 않는다 — " There is…to be done" 보존."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(98.9, "en", "ko", 96.0)])
    there = _tok(98.97, 99.05, " There", "en")
    ta._insert_with_reattachment([there])
    cont = [_tok(99.11, 99.2, " is", "en"), _tok(99.3, 99.4, " to", "en"),
            _tok(99.45, 99.5, " be", "en"), _tok(99.6, 99.7, " done", "en")]
    ta._insert_with_reattachment(cont)
    assert there.retracted is False  # supersede 오탐 금지(' There'←' more' 사례)
    assert _visible_texts(ta) == [" There", " is", " to", " be", " done"]


def test_no_supersede_for_unmatched_subword_continuation():
    """실측 회귀(ytn2 56.29 "정경두"→"경두"): 비매칭 하위단어 연속('경두'는 ' 정'과
    완전일치도 접두어도 아님)은 supersede 대상이 아니다."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(56.2, "ko", "en", 54.0)])
    jung = _tok(56.29, 56.35, " 정", "ko")
    ta._insert_with_reattachment([jung])
    ta._insert_with_reattachment([_tok(56.35, 56.45, "경두", "ko"),
                                  _tok(56.9, 57.0, " 국방부", "ko")])
    assert jung.retracted is False
    assert _visible_texts(ta) == [" 정", "경두", " 국방부"]


def test_prefix_absorption_supersede_with_id_inheritance():
    """접두어 흡수: committed ' 우'가 신규 ' 우선…'(확장 배치)의 접두어면 supersede +
    id(start) 승계 — "우 사안 중에서는 우선" 유형 완전 정리."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.9, "ko", "en", 10.5)])
    woo = _tok(13.0, 13.1, " 우", "ko")
    ta._insert_with_reattachment([woo])
    full = [_tok(13.05, 13.15, " 우선", "ko"), _tok(13.5, 13.6, " 사안", "ko"),
            _tok(13.85, 13.95, " 중에서는", "ko")]
    ta._insert_with_reattachment(full)
    assert woo.retracted is True
    assert full[0].start == 13.0  # id(start) 승계
    assert _visible_texts(ta) == [" 우선", " 사안", " 중에서는"]


def test_ghost_prefix_adjacent_punct_token_absorbed_in_supersede():
    """supersede 시 매칭 run에 인접한 구두점-only committed('.')도 함께 tombstone —
    유령 "In."의 '.'만 잔존하는 구멍 방지."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    ghost_in = _tok(13.0, 13.1, " In", "en")
    ghost_dot = _tok(13.1, 13.2, ".", "en")
    ta._insert_with_reattachment([ghost_in, ghost_dot])
    full = [_tok(13.05, 13.15, " In", "en"), _tok(13.5, 13.6, " support", "en"),
            _tok(13.85, 13.95, " of", "en")]
    ta._insert_with_reattachment(full)
    assert ghost_in.retracted is True
    assert ghost_dot.retracted is True  # 인접 구두점 동반 소멸
    assert full[0].start == 13.0
    assert _visible_texts(ta) == [" In", " support", " of"]


def test_prefix_matched_new_token_not_dropped_in_nonextend():
    """비확장(drop 방향)에서 접두어 매칭 신규는 드롭 금지 — 더 완전한 신규를 버리지
    않는다(완전일치만 드롭)."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "ko", "en", 10.0)])
    full_word = _tok(12.5, 12.6, " 우선", "ko")
    ta._insert_with_reattachment([full_word])
    short = _tok(12.55, 12.65, " 우", "ko")
    ta._insert_with_reattachment([short])
    assert short in ta.all_tokens  # 접두어 매칭이지만 드롭되지 않음
    assert full_word.retracted is False


def test_pure_punct_tokens_never_match():
    """순수 구두점 토큰(정규화 후 빈 문자열)은 매칭 후보에서 제외 — 드롭/supersede 없음."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    dot1 = _tok(12.5, 12.6, ".", "en")
    ta._insert_with_reattachment([dot1])
    dot2 = _tok(12.55, 12.65, ".", "en")
    ta._insert_with_reattachment([dot2])
    assert dot1.retracted is False
    assert dot2 in ta.all_tokens


def test_ghost_prefix_supersede_direction_and_id_inheritance():
    """② 유령 접두어: 기존("In.")이 신규 배치 커버리지의 부분집합 + 신규가 그 너머 확장
    → 기존 tombstone + 신규 채택 + id(start) 승계(소멸 세그먼트의 최초 start 이어받기)."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    ghost = _tok(13.0, 13.1, " In.", "en")
    ta._insert_with_reattachment([ghost])  # D1 resolve(13.0 >= 12.65)
    full = [_tok(13.05, 13.15, " In", "en"), _tok(13.5, 13.6, " support", "en"),
            _tok(13.85, 13.95, " of", "en")]
    ta._insert_with_reattachment(full)
    assert ghost.retracted is True  # 기존 tombstone
    assert full[0].start == 13.0    # id(start) 승계 — UI finalizedHistory 유령 방지
    assert _visible_texts(ta) == [" In", " support", " of"]


def test_normal_repeat_outside_window_is_protected():
    """정상 반복("네, 네")은 창 구간(dedup_limit) 밖 새 오디오라 드롭되지 않는다.

    dedup_limit은 경계 앵커 고정(boundary_t+PASS_EPS+유예)이라 발화 프런티어를
    쫓아가며 자기확장하지 않는다 — 경계에서 멀어진 반복은 자동 보호.
    """
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "ko", "en", 10.0)])
    ta._insert_with_reattachment([_tok(14.0, 14.1, " 네,", "ko")])
    n_before = len(ta.all_tokens)
    ta._insert_with_reattachment([_tok(14.3, 14.4, " 네", "ko")])
    assert len(ta.all_tokens) == n_before + 1  # 드롭 없음
    assert _visible_texts(ta) == [" 네,", " 네"]


def test_timededup_no_action_on_forward_continuation():
    """정상 연속 배치(프런티어 전진)는 ①/② 어느 방향도 발동하지 않는다."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    ta._insert_with_reattachment([_tok(12.5, 12.6, " In", "en")])
    cont = [_tok(13.0, 13.1, " support", "en"), _tok(13.4, 13.5, " of", "en")]
    ta._insert_with_reattachment(cont)
    assert _visible_texts(ta) == [" In", " support", " of"]
    assert all(not t.retracted for t in ta.all_tokens if not t.is_boundary())


def test_late_cover_after_early_d2_resolve_within_grace():
    """D2 조기 resolve로 복원된 tombstone을, 유예(+0.5s) 안에 도착한 신언어 커버가
    재대체한다 — 복원분 중복 방지."""
    ta = _make_alignment()
    tail = _tok(11.9, 12.3, " 미니스터.", "ko")
    ta.all_tokens = [tail]
    ta._insert_with_reattachment([_retract_marker(12.4, "en", "ko", 10.0)])
    assert tail.retracted is True
    # D2 조기 resolve(신언어 무도착) → 복원
    ta._insert_with_reattachment([Silence(start=12.5, end=12.7)])
    assert tail.retracted is False
    # 유예 안 늦은 커버 도착(|12.0-11.9|=0.1 <= COVER_TOL, start 12.0 <= dedup_limit)
    ta._insert_with_reattachment([_tok(12.0, 12.4, " Minister", "en")])
    assert tail.retracted is True  # 재대체 — 이중언어 중복 소멸


def test_late_cover_far_from_restored_tombstone_no_replace():
    """resolve 후 도착한 신언어 토큰이라도 복원분과 start 근접이 아니면 재대체하지 않는다."""
    ta = _make_alignment()
    tail = _tok(11.0, 11.4, " 반갑습니다", "ko")
    ta.all_tokens = [tail]
    ta._insert_with_reattachment([_retract_marker(12.0, "en", "ko", 10.0)])
    ta._insert_with_reattachment([Silence(start=12.1, end=12.2)])  # D2 → 복원
    assert tail.retracted is False
    ta._insert_with_reattachment([_tok(12.6, 12.7, " Nice", "en")])  # Δ=1.6 > COVER_TOL
    assert tail.retracted is False


def test_dedup_noop_when_flag_off(monkeypatch):
    """RECONCILE_ENABLED=False면 dedup_batch도 완전 무동작(레거시 거동)."""
    monkeypatch.setattr(boundary_reconcile, "RECONCILE_ENABLED", False)
    ta = _make_alignment()
    ta._insert_with_reattachment([_tok(12.5, 12.6, " It's", "en")])
    ta._insert_with_reattachment([_tok(12.5, 12.6, " It's", "en")])
    assert _visible_texts(ta) == [" It's", " It's"]  # 드롭 없음(레거시)


def test_window_released_after_grace_via_check_deadline():
    """resolve된 창은 dedup 유예가 지나면 check_deadline에서 해제된다(참조 정리)."""
    ta = _make_alignment()
    ta._insert_with_reattachment([_retract_marker(12.0, "en", "ko", 10.0)])
    ta._insert_with_reattachment([_tok(12.5, 12.6, " New", "en")])  # D1 resolve
    assert ta.reconciler.window is not None
    ta.reconciler.check_deadline(ta.reconciler.window.dedup_limit() + 0.01)
    assert ta.reconciler.window is None


# ─── 커밋5: 동적 keep 클램프 ──────────────────────────────────────────────────


def test_dynamic_keep_lower_clamp():
    """미방출 구간이 짧으면(기본값 이하) 기존 고정값 2.5s 하한으로 클램프."""
    from whisperlivekit.simul_whisper.align_att_base import (
        LANG_SWITCH_KEEP_SECS,
        compute_dynamic_keep,
    )
    # 미방출 1.0s + margin 0.3 = 1.3 < 2.5 → 하한
    assert compute_dynamic_keep(20.0, 19.0) == LANG_SWITCH_KEEP_SECS


def test_dynamic_keep_upper_clamp():
    """미방출 구간이 길어도 5.0s 상한 캡(Exp-166 방송클로징 환각 전례 감시)."""
    from whisperlivekit.simul_whisper.align_att_base import (
        LANG_SWITCH_KEEP_MAX_SECS,
        compute_dynamic_keep,
    )
    # 미방출 10.0s + 0.3 = 10.3 > 5.0 → 상한
    assert compute_dynamic_keep(30.0, 20.0) == LANG_SWITCH_KEEP_MAX_SECS


def test_dynamic_keep_tracks_unemitted_span_with_margin():
    """클램프 사이 구간에서는 keep = (버퍼끝 − last_emit_end) + margin(0.3)."""
    from whisperlivekit.simul_whisper.align_att_base import compute_dynamic_keep
    assert compute_dynamic_keep(20.0, 16.5) == 3.8  # 3.5 + 0.3


def test_dynamic_keep_none_falls_back_to_fixed():
    """last_emit_end 미설정(None) 또는 버퍼끝 불명이면 기존 고정 2.5s 폴백."""
    from whisperlivekit.simul_whisper.align_att_base import (
        LANG_SWITCH_KEEP_SECS,
        compute_dynamic_keep,
    )
    assert compute_dynamic_keep(20.0, None) == LANG_SWITCH_KEEP_SECS
    assert compute_dynamic_keep(None, 19.0) == LANG_SWITCH_KEEP_SECS
