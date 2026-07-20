"""Stage 1 — 언어전환 경계 오언어 커밋 토큰 철회(retraction) 단위 테스트 (모델 불필요).

Exp-192 tombstone 리팩토링 이후: 철회는 파괴적 pop이 아니라 retracted=True 마킹이다.
테스트는 "가시 토큰 뷰"(비-retracted) 기준으로 판정한다 — 하한·Silence 정지·반대방향
불가침·retract_floor 의미는 pop 시절과 전부 동일하게 보존된다.
"""
from whisperlivekit.timed_objects import ASRToken, LanguageSwitch, Silence
from whisperlivekit.tokens_alignment import (
    LANG_SWITCH_KEEP_SECS,
    RETRACT_EPS,
    TokensAlignment,
    _is_opposite_script,
)


def _make_alignment():
    """실제 State/args 없이 TokensAlignment를 최소 구성(test_lang_switch_protocol.py와 동일 패턴)."""

    class _Args:
        diarization = False

    class _State:
        new_tokens = []
        new_diarization = []
        new_translation = []
        new_tokens_buffer = []
        new_translation_buffer = None

    return TokensAlignment(_State(), _Args(), sep="")


def _visible(ta):
    """가시 토큰 뷰 — 파생 뷰(compute_punctuations_segments)와 동일한 필터."""
    return [t for t in ta.all_tokens if not getattr(t, "retracted", False)]


def _visible_texts(ta):
    return [t.text for t in _visible(ta) if not t.is_silence() and not t.is_boundary()]


def test_is_opposite_script_ko_vs_latin():
    assert _is_opposite_script("Who is the", "ko") is True
    assert _is_opposite_script("누가 주인공일까", "ko") is False  # 한글 포함 = 정상 스크립트
    assert _is_opposite_script("Who 주인공", "ko") is False  # 혼합 스크립트는 보존(False)


def test_is_opposite_script_en_vs_hangul():
    assert _is_opposite_script("인공일까", "en") is True
    assert _is_opposite_script("hello world", "en") is False
    assert _is_opposite_script("123", "en") is False  # 스크립트 무관 텍스트는 보존


def test_is_opposite_script_unknown_lang_never_retracts():
    assert _is_opposite_script("Who is the", "ja") is False


def test_retract_zone1_removes_stale_language_regardless_of_script():
    """구역 1(start >= boundary_t - EPS): 언어 매치만으로 제거 — damage A(오번역 잔존) 케이스."""
    ta = _make_alignment()
    boundary_t = 13.0
    ta.all_tokens = [
        ASRToken(start=13.06, end=13.30, text="? Who", detected_language="en"),
        ASRToken(start=13.30, end=13.50, text=" is the.", detected_language="en"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="en")
    assert _visible(ta) == []
    # tombstone 리팩토링: 토큰 자체는 남고 retracted 마크만 붙는다(복원 가능성 보존).
    assert len(ta.all_tokens) == 2
    assert all(t.retracted for t in ta.all_tokens)


def test_retract_zone2_removes_only_opposite_script_glue_case():
    """구역 2(경계 직전): prev_lang 스탬프 + 스크립트 불일치만 제거 — damage A'(접착) 케이스.

    "했어요"(정상 ko 꼬리, ko 스탬프)는 보존하고, "The thought that."(en 텍스트인데
    ko 잠금 아래 디코딩되어 ko로 스탬프된 접착 토큰)만 철회한다.
    """
    ta = _make_alignment()
    boundary_t = 17.74
    ta.all_tokens = [
        ASRToken(start=16.50, end=17.00, text="많이 했어요.", detected_language="ko"),
        ASRToken(start=17.00, end=17.60, text=" The thought that.", detected_language="ko"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="ko")
    assert _visible_texts(ta) == ["많이 했어요."]


def test_retract_stops_scan_at_silence():
    """Silence를 만나면 즉시 스캔 중단 — 경계를 넘어 철회하지 않는다.

    token[0]은 prev_lang="ko" 기준 반대-스크립트(Latin)라 스캔이 도달하면 zone2로
    철회 대상이 되지만, 그 앞의 Silence가 스캔을 막아 도달 자체를 못하게 한다.
    token[2](zone1, 언어매치만으로 무조건 철회)는 정상적으로 철회되어야 한다.
    """
    ta = _make_alignment()
    boundary_t = 20.0
    ta.all_tokens = [
        ASRToken(start=17.0, end=17.2, text="would-be-removed-if-reached", detected_language="ko"),
        Silence(start=17.2, end=17.5),
        ASRToken(start=19.96, end=20.0, text="stale", detected_language="ko"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="ko")
    vis = _visible(ta)
    assert len(vis) == 2
    assert vis[0].text == "would-be-removed-if-reached"
    assert isinstance(vis[1], Silence)


def test_retract_respects_lower_bound():
    """하한(boundary_t - LANG_SWITCH_KEEP_SECS - 1.0)보다 앞선 토큰은 평가 자체를 안 한다.

    text가 반대-스크립트(Latin, prev_lang="ko")라 하한이 없다면 zone2로 철회됐을
    토큰이지만, start가 하한보다 앞서 있어 언어/스크립트 검사에 도달하기 전에 스캔이
    끊긴다.
    """
    ta = _make_alignment()
    boundary_t = 20.0
    lower_bound = boundary_t - LANG_SWITCH_KEEP_SECS - 1.0  # = 16.5
    ta.all_tokens = [
        ASRToken(start=16.0, end=16.3, text="Too far back", detected_language="ko"),
    ]
    assert ta.all_tokens[0].start < lower_bound
    ta._retract_stale_language_tokens(boundary_t, prev_lang="ko")
    assert _visible_texts(ta) == ["Too far back"]


def test_retract_never_touches_opposite_direction_language():
    """prev_lang과 다른 언어로 스탬프된 토큰(=이미 전환된 새 언어)은 절대 제거하지 않는다."""
    ta = _make_alignment()
    boundary_t = 13.0
    ta.all_tokens = [
        ASRToken(start=12.5, end=12.9, text="새 언어로 이미 커밋됨", detected_language="ko"),
        ASRToken(start=13.1, end=13.3, text="stale", detected_language="en"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="en")
    assert _visible_texts(ta) == ["새 언어로 이미 커밋됨"]


def test_retract_noop_when_prev_lang_none():
    ta = _make_alignment()
    ta.all_tokens = [ASRToken(start=1.0, end=1.2, text="x", detected_language="en")]
    ta._retract_stale_language_tokens(boundary_t=5.0, prev_lang=None)
    assert _visible_texts(ta) == ["x"]


def test_retract_scan_transparently_passes_already_retracted():
    """이미 tombstone된 토큰은 스캔에서 투명 통과 — scanned/removed에 산입되지 않고,
    그 너머의 철회 대상까지 스캔이 계속된다(레거시 pop과 동일한 도달 범위)."""
    ta = _make_alignment()
    boundary_t = 13.0
    already = ASRToken(start=13.2, end=13.3, text="ghost", detected_language="en", retracted=True)
    target = ASRToken(start=13.06, end=13.18, text="stale", detected_language="en")
    ta.all_tokens = [target, already]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="en")
    assert _visible(ta) == []
    assert target.retracted is True


def test_marker_without_retract_from_is_noop():
    """retract_from이 없는 일반 LanguageSwitch 마커는 철회를 실행하지 않는다(기존 동작 보존)."""
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=1.0, end=1.2, text="hello", detected_language="en"),
    ]
    marker = LanguageSwitch(start=1.3, end=1.3, detected_language="ko")
    ta._insert_with_reattachment([marker])
    assert _visible_texts(ta) == ["hello"]
    assert ta.all_tokens[-1] is marker


def test_insert_with_reattachment_retracts_before_appending_marker():
    """전체 경로: 철회 대상 토큰이 이미 all_tokens에 있고, retract_from이 실린 마커가
    _insert_with_reattachment로 들어오면 마커 append 전에 철회가 먼저 일어난다.

    Exp-192 재조정 이후: 신언어 토큰이 철회 구간을 start 근접으로 커버(13.30 vs
    13.06, Δ=0.24 <= COVER_TOL)하므로 resolve(D1) 후에도 stale은 영구 tombstone으로
    남는다. 미커버 시 복원되는 경로는 test_boundary_reconcile.py에서 검증한다.
    """
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=13.06, end=13.50, text="? Who is the.", detected_language="en"),
    ]
    marker = LanguageSwitch(
        start=13.60, end=13.60, detected_language="ko",
        retract_from=13.0, prev_language="en",
    )
    new_ko_token = ASRToken(start=13.30, end=14.0, text="인공일까", detected_language="ko")
    ta._insert_with_reattachment([marker, new_ko_token])
    assert _visible_texts(ta) == ["인공일까"]


def test_retract_eps_is_positive_and_small():
    """EPS는 프레임 지터 방어용 소량 여유 — 큰 값이면 zone1/zone2 경계가 무의미해진다."""
    assert 0 < RETRACT_EPS < 0.5


def test_retract_floor_preserves_pre_window_onset():
    """재디코딩 창(redecode_floor) 이전 토큰은 철회하지 않는다 — ① 서두유실 방지(Exp-173).

    화자전환 트림이 버퍼를 76.59s부터로 잘라내 "You don't"의 오디오가 사라졌으면,
    그 토큰들은 재디코딩으로 재현 불가하므로 철회하면 순유실. redecode_floor=76.59로
    창 이전 토큰(You/don/'t)을 보존한다.
    """
    ta = _make_alignment()
    boundary_t = 77.31
    ta.all_tokens = [
        ASRToken(start=76.19, end=76.37, text=" You", detected_language="ko"),
        ASRToken(start=76.37, end=76.51, text=" don", detected_language="ko"),
        ASRToken(start=76.51, end=76.61, text="'t understand", detected_language="ko"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="ko", redecode_floor=76.59)
    # 76.59 미만(You 76.19, don 76.37, 't understand 76.51)은 전부 보존
    assert _visible_texts(ta) == [" You", " don", "'t understand"]


def test_retract_floor_still_removes_in_window_stale():
    """재디코딩 창 안(redecode_floor 이상) 오언어 스탬프 토큰은 여전히 철회한다."""
    ta = _make_alignment()
    boundary_t = 77.31
    ta.all_tokens = [
        ASRToken(start=76.20, end=76.50, text=" outside", detected_language="ko"),  # 창 밖 보존
        ASRToken(start=76.80, end=77.00, text=" inside", detected_language="ko"),   # 창 안 철회(zone2 반대스크립트)
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="ko", redecode_floor=76.59)
    assert _visible_texts(ta) == [" outside"]


def test_retract_floor_none_falls_back_to_keep_secs_bound():
    """redecode_floor=None(구 마커)이면 기존 KEEP_SECS 기반 하한으로 동작(하위호환)."""
    ta = _make_alignment()
    boundary_t = 20.0
    # 하한 = 20 - 2.5 - 1.0 = 16.5. 16.0은 하한 밖이라 보존, 19.0은 zone2 철회.
    ta.all_tokens = [
        ASRToken(start=16.0, end=16.3, text=" farback", detected_language="ko"),
        ASRToken(start=19.0, end=19.3, text=" nearby", detected_language="ko"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="ko", redecode_floor=None)
    assert _visible_texts(ta) == [" farback"]


def test_derived_view_hides_retracted_tokens():
    """compute_punctuations_segments(파생 뷰 단일 초크포인트)는 retracted 토큰을 숨긴다."""
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=1.0, end=1.2, text="보임", detected_language="ko"),
        ASRToken(start=1.2, end=1.4, text=" 숨김", detected_language="ko", retracted=True),
        ASRToken(start=1.4, end=1.6, text=" 또보임", detected_language="ko"),
    ]
    segs = ta.compute_punctuations_segments()
    assert len(segs) == 1
    assert segs[0].text == "보임 또보임"


def test_derived_view_unretract_restores_token_in_time_order():
    """retracted 플래그를 되돌리면(복원) 파생 뷰에 시간순 그대로 재등장한다."""
    ta = _make_alignment()
    hidden = ASRToken(start=1.2, end=1.4, text=" 숨김", detected_language="ko", retracted=True)
    ta.all_tokens = [
        ASRToken(start=1.0, end=1.2, text="보임", detected_language="ko"),
        hidden,
        ASRToken(start=1.4, end=1.6, text=" 또보임", detected_language="ko"),
    ]
    hidden.retracted = False
    segs = ta.compute_punctuations_segments()
    assert len(segs) == 1
    assert segs[0].text == "보임 숨김 또보임"
