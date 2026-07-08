"""Stage 1 — 언어전환 경계 오언어 커밋 토큰 철회(retraction) 단위 테스트 (모델 불필요)."""
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
    assert ta.all_tokens == []


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
    assert len(ta.all_tokens) == 1
    assert ta.all_tokens[0].text == "많이 했어요."


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
    assert len(ta.all_tokens) == 2
    assert ta.all_tokens[0].text == "would-be-removed-if-reached"
    assert isinstance(ta.all_tokens[1], Silence)


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
    assert len(ta.all_tokens) == 1
    assert ta.all_tokens[0].text == "Too far back"


def test_retract_never_touches_opposite_direction_language():
    """prev_lang과 다른 언어로 스탬프된 토큰(=이미 전환된 새 언어)은 절대 제거하지 않는다."""
    ta = _make_alignment()
    boundary_t = 13.0
    ta.all_tokens = [
        ASRToken(start=12.5, end=12.9, text="새 언어로 이미 커밋됨", detected_language="ko"),
        ASRToken(start=13.1, end=13.3, text="stale", detected_language="en"),
    ]
    ta._retract_stale_language_tokens(boundary_t, prev_lang="en")
    assert len(ta.all_tokens) == 1
    assert ta.all_tokens[0].text == "새 언어로 이미 커밋됨"


def test_retract_noop_when_prev_lang_none():
    ta = _make_alignment()
    ta.all_tokens = [ASRToken(start=1.0, end=1.2, text="x", detected_language="en")]
    ta._retract_stale_language_tokens(boundary_t=5.0, prev_lang=None)
    assert len(ta.all_tokens) == 1


def test_marker_without_retract_from_is_noop():
    """retract_from이 없는 일반 LanguageSwitch 마커는 철회를 실행하지 않는다(기존 동작 보존)."""
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=1.0, end=1.2, text="hello", detected_language="en"),
    ]
    marker = LanguageSwitch(start=1.3, end=1.3, detected_language="ko")
    ta._insert_with_reattachment([marker])
    assert ta.all_tokens[0].text == "hello"
    assert ta.all_tokens[-1] is marker


def test_insert_with_reattachment_retracts_before_appending_marker():
    """전체 경로: 철회 대상 토큰이 이미 all_tokens에 있고, retract_from이 실린 마커가
    _insert_with_reattachment로 들어오면 마커 append 전에 철회가 먼저 일어난다."""
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=13.06, end=13.50, text="? Who is the.", detected_language="en"),
    ]
    marker = LanguageSwitch(
        start=13.60, end=13.60, detected_language="ko",
        retract_from=13.0, prev_language="en",
    )
    new_ko_token = ASRToken(start=13.60, end=14.0, text="인공일까", detected_language="ko")
    ta._insert_with_reattachment([marker, new_ko_token])
    texts = [t.text for t in ta.all_tokens if not t.is_boundary()]
    assert texts == ["인공일까"]


def test_retract_eps_is_positive_and_small():
    """EPS는 프레임 지터 방어용 소량 여유 — 큰 값이면 zone1/zone2 경계가 무의미해진다."""
    assert 0 < RETRACT_EPS < 0.5
