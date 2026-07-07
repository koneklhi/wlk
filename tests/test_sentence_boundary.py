# -*- coding: utf-8 -*-
"""문장 종결 온점 판별기(sentence_boundary) 단위 테스트.

형태소 하이브리드 판별 3함수(is_sentence_final_ko / is_abbreviation_en /
is_genuine_sentence_end)의 True/False 케이스를 고정한다.
"""

from whisperlivekit.sentence_boundary import (
    is_abbreviation_en,
    is_genuine_sentence_end,
    is_sentence_final_ko,
)

# ─── is_sentence_final_ko ─────────────────────────────────────────────────────

def test_ko_final_true_cases():
    for word in ["보입니다", "올렸습니다", "합니다", "했어요", "하세요",
                 "그렇네요", "크구나", "먹었다", "하는군요"]:
        assert is_sentence_final_ko(word) is True, f"종결어미인데 False: {word!r}"


def test_ko_final_false_cases():
    for word in ["것으로", "올렸", "주한미군", "공군", "강연",
                 "그러니까", "하는데", "했다는", "world"]:
        assert is_sentence_final_ko(word) is False, f"비종결인데 True: {word!r}"


# ─── is_abbreviation_en ───────────────────────────────────────────────────────

def test_en_abbrev_true_cases():
    for word in ["Mr", "U.S", "U.N", "etc", "J", "am"]:
        assert is_abbreviation_en(word) is True, f"약어인데 False: {word!r}"


def test_en_abbrev_false_cases():
    for word in ["world", "NASA", "Hello", "Government"]:
        assert is_abbreviation_en(word) is False, f"비약어인데 True: {word!r}"


# ─── is_genuine_sentence_end ──────────────────────────────────────────────────

def test_genuine_end_true_cases():
    cases = [
        ("그렇습니다.", None),
        ("보입니다.", "다음"),
        ("world.", "Hello"),
        ("island.", "Or"),
    ]
    for closing, nxt in cases:
        assert is_genuine_sentence_end(closing, nxt) is True, (
            f"진짜 종결인데 False: {closing!r} / next={nxt!r}"
        )


def test_genuine_end_false_cases():
    cases = [
        ("U.S.", "Government"),
        ("island.", "or"),
        ("world.", "much"),
        ("3.", "Next"),
        ("것으로.", "보입니다"),
        ("올렸.", "습니다"),
        ("world.", None),
    ]
    for closing, nxt in cases:
        assert is_genuine_sentence_end(closing, nxt) is False, (
            f"거짓 종결인데 True: {closing!r} / next={nxt!r}"
        )
