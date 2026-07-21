"""whisperlivekit.metrics.compute_language_mismatch / compute_language_flip_events 유닛 테스트.

측정 대상은 "한국어 발화가 영어로 뒤집혀 전사되는" 언어잠금 실패다. 이 실패는 삽입이 아니라
**치환**이므로 Levenshtein 정렬의 sub 연산만 골라 스크립트(한글/라틴)를 비교한다.
"""

from whisperlivekit.metrics import (
    _word_script,
    compute_language_flip_events,
    compute_language_mismatch,
    compute_wer,
)

# 실측 실패 사례(bong1) — 정답은 전부 한국어인데 전사가 통째로 영어로 뒤집혔다.
REAL_KO_REF = "누가 주인공일까 이런 생각을 제가 제일 많이 했어요"
REAL_KO_HYP = "Who is the one who is the one who Yes, it's a"

# 음차(transliteration) 사례 — "플라스틱 말랑말랑"이 발음만 옮겨져 라틴 문자로 전사됐다.
TRANSLIT_REF = "아니 그 플라스틱 말랑말랑한 것도 만들었죠"
TRANSLIT_HYP = "I go plus guys malang Thank you"


def test_identical_text_has_zero_mismatch():
    """정답과 전사가 같으면 양방향 모두 0.0(측정은 했고 뒤집힘이 없음)."""
    text = "안녕 하세요 thank you minister 감사 합니다"
    r = compute_language_mismatch(text, text)
    assert r["lmr_ko"] == 0.0
    assert r["lmr_en"] == 0.0
    assert r["lmr_wer_pp"] == 0.0
    assert r["ko_to_en"] == 0
    assert r["en_to_ko"] == 0
    assert r["ko_ok"] == r["ko_ref_words"]
    assert r["en_ok"] == r["en_ref_words"]


def test_real_ko_to_en_failure_is_counted():
    """실측 실패 사례에서 ko→en 뒤집힘이 잡혀야 한다(WER에서는 다른 오류와 섞여 희석된다)."""
    r = compute_language_mismatch(REAL_KO_REF, REAL_KO_HYP)
    assert r["ko_to_en"] > 0
    assert r["lmr_ko"] > 0.0
    assert r["lmr_wer_pp"] > 0.0
    # 정답에 영어 단어가 하나도 없으므로 반대 방향은 "해당 없음"(None)이다.
    assert r["lmr_en"] is None


def test_transliteration_counts_as_mismatch():
    """음차(플라스틱→plus guys)도 라틴 문자로 나온 이상 스크립트 기준으로는 뒤집힘이다."""
    r = compute_language_mismatch(TRANSLIT_REF, TRANSLIT_HYP)
    assert r["ko_to_en"] > 0
    assert r["lmr_ko"] > 0.0


def test_reverse_direction_en_to_ko():
    """영어 정답이 한국어로 뒤집히면 lmr_en(부작용 감시 지표)이 잡힌다."""
    r = compute_language_mismatch("thank you minister", "감사 합니다 장관님")
    assert r["en_to_ko"] == 3
    assert r["lmr_en"] == 1.0
    assert r["lmr_ko"] is None  # 정답에 한국어 단어 없음
    assert r["ko_to_en"] == 0


def test_no_ko_reference_words_yields_none_not_zero():
    """해당 스크립트 정답 단어가 0개면 0.0이 아니라 None이어야 한다.

    0.0은 "측정했는데 다 맞음/틀림"으로 오독된다 — eng1·kor1~3처럼 한쪽 언어만 있는
    데이터에서 반대 방향이 자동으로 None이 되게 하려는 의도적 설계다.
    """
    r = compute_language_mismatch("hello world", "hello world")
    assert r["lmr_ko"] is None
    assert r["lmr_ko"] != 0.0  # "측정 불가"와 "측정했는데 0"은 다른 값이어야 한다
    assert r["lmr_en"] == 0.0
    assert r["ko_ref_words"] == 0


def test_mix_and_neutral_words_are_excluded_from_denominators():
    """MIX(한글+라틴 혼합)·NEU(숫자·기호)는 방향 판정에서 제외돼 분모에 들어가지 않는다."""
    # "AI기술"=MIX, "2024"=NEU, "안녕"=KO, "hello"=EN
    r = compute_language_mismatch("AI기술 2024 안녕 hello", "AI기술 2024 안녕 hello")
    assert r["ref_words"] == 4
    assert r["ko_ref_words"] == 1
    assert r["en_ref_words"] == 1
    assert _word_script("AI기술") == "MIX"
    assert _word_script("2024") == "NEU"
    assert _word_script("안녕") == "KO"
    assert _word_script("hello") == "EN"


def test_deletion_and_insertion_are_not_mismatches():
    """누락(del)·환각 삽입(ins)은 "뒤집힘"이 아니다 — LMR 분자에 들어가면 안 된다."""
    # 정답 3단어 중 1개 누락
    r_del = compute_language_mismatch("안녕 하세요 반갑습니다", "안녕 하세요")
    assert r_del["ko_del"] == 1
    assert r_del["ko_to_en"] == 0
    assert r_del["lmr_ko"] == 0.0

    # 정답에 없는 영어 3단어가 삽입됨(연속 런 3)
    r_ins = compute_language_mismatch("안녕", "안녕 alpha beta gamma")
    assert r_ins["ins_en"] == 3
    assert r_ins["ko_to_en"] == 0
    assert r_ins["lmr_ko"] == 0.0
    assert r_ins["max_ins_run"] == 3
    assert r_ins["ins_runs_ge3"] == 1


def test_insertion_run_stats():
    """연속 삽입 런의 최대 길이 / 길이≥3 런 개수(반복 환각 근사)."""
    r = compute_language_mismatch("a c", "a x y c")  # 중간에 ins 2개 런 하나
    assert r["max_ins_run"] == 2
    assert r["ins_runs_ge3"] == 0

    # 정답 단어가 치환으로 소비되면 그 자리는 ins가 아니다 — 런이 끊긴다.
    r2 = compute_language_mismatch("a b c", "a x y c")  # b→x 치환 + y 삽입 1
    assert r2["max_ins_run"] == 1


def test_lmr_wer_pp_denominator_matches_compute_wer():
    """lmr_wer_pp는 WER과 분모를 공유해야 귀속량이 덧셈 가능한 양이 된다."""
    ref = "안녕 하세요 thank you minister 감사 합니다"
    hyp = "hello there thank you minister 감사 합니다"
    r = compute_language_mismatch(ref, hyp)
    assert r["ref_words"] == compute_wer(ref, hyp)["ref_words"]
    expected = (r["ko_to_en"] + r["en_to_ko"]) / r["ref_words"]
    assert r["lmr_wer_pp"] == expected


def test_bucket_invariants():
    """정답 단어의 행방 4분할은 남김없이 분모와 일치해야 한다(EN도 동일)."""
    for ref, hyp in [
        (REAL_KO_REF, REAL_KO_HYP),
        (TRANSLIT_REF, TRANSLIT_HYP),
        ("안녕 하세요 thank you minister", "hello there 감사 you minister"),
        ("a b c", ""),
        ("", "안녕 hello"),
    ]:
        r = compute_language_mismatch(ref, hyp)
        assert r["ko_ok"] + r["ko_to_ko"] + r["ko_to_en"] + r["ko_del"] == r["ko_ref_words"]
        assert r["en_ok"] + r["en_to_en"] + r["en_to_ko"] + r["en_del"] == r["en_ref_words"]


def test_empty_reference_is_safe():
    """정답이 비면 분모가 0 — 예외 없이 None/0.0으로 떨어진다."""
    r = compute_language_mismatch("", "안녕 hello")
    assert r["lmr_ko"] is None
    assert r["lmr_en"] is None
    assert r["lmr_wer_pp"] == 0.0
    assert r["ins_ko"] == 1
    assert r["ins_en"] == 1


def test_script_patterns_do_not_drift_from_tokens_alignment():
    """스크립트 판정 패턴은 런타임 모듈(tokens_alignment)과 **동일**해야 한다.

    metrics.py는 "외부 의존성 없음"이 설계 원칙이라 런타임 모듈을 import하지 않고 로컬
    재정의를 쓴다 — 그래서 드리프트를 이 테스트가 막는다.
    """
    from whisperlivekit import metrics, tokens_alignment

    assert metrics._HANGUL_PATTERN.pattern == tokens_alignment._HANGUL_PATTERN.pattern
    assert metrics._LATIN_PATTERN.pattern == tokens_alignment._LATIN_PATTERN.pattern


# ── compute_language_flip_events (정성 리포트 전용) ────────────────────────────


def test_flip_events_detect_sentence_level_reversal():
    """한국어 지배 문장이 통째로 영어로 전사되면 이벤트 1건."""
    ref = ["thank you minister", REAL_KO_REF]
    events = compute_language_flip_events(ref, "thank you minister " + REAL_KO_HYP)
    assert len(events) == 1
    assert events[0]["ref_script"] == "KO"
    assert events[0]["hyp_script"] == "EN"
    assert events[0]["ref_text"] == REAL_KO_REF
    assert events[0]["ref_words"] == 8


def test_flip_events_none_when_scripts_match():
    ref = ["thank you minister", "안녕 하세요 반갑습니다"]
    assert compute_language_flip_events(ref, "thank you minister 안녕 하세요 반갑습니다") == []


def test_flip_events_carry_speaker_when_provided():
    """dict 형태로 화자를 함께 주면 이벤트에 speaker가 실린다(str만 주면 speaker 키 없음)."""
    ref = [
        {"text": "thank you minister", "speaker": "spk1"},
        {"text": REAL_KO_REF, "speaker": "spk2"},
    ]
    events = compute_language_flip_events(ref, "thank you minister " + REAL_KO_HYP)
    assert len(events) == 1
    assert events[0]["speaker"] == "spk2"

    plain_events = compute_language_flip_events(["thank you minister", REAL_KO_REF],
                                                "thank you minister " + REAL_KO_HYP)
    assert "speaker" not in plain_events[0]


def test_flip_events_empty_inputs():
    assert compute_language_flip_events([], "무엇이든") == []
    assert compute_language_flip_events(["   "], "무엇이든") == []
