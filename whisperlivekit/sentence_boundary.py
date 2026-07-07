"""문장 종결 온점 판별기 — 형태소 하이브리드.

Whisper가 찍는 마침표를 문장 분할 신호로 쓰되, '진짜 종결'과 '거짓 마침표'
(한국어 어간·조사 중간 온점, 영어 약어, 소수점)를 형태소로 구분한다.
순수 함수 — 모델·상태 무의존. 로직/목록 변경 시
docs/SENTENCE_FINALIZATION_LOGIC.md §3·§5를 함께 갱신한다(§7 규약).
"""
from whisperlivekit.timed_objects import PUNCTUATION_MARKS

# 한국어 종결어미(고정밀 Tier 1). bare 단음절(군/네/다/까)은 명사·조사 충돌로 제외한다.
KO_FINAL_SUFFIXES = (
    "니다", "십시오",                                        # 합쇼체(-습니다/-ㅂ니다/-십시오)
    "어요", "아요", "여요", "해요", "워요", "와요", "봐요",       # 해요체 동사
    "세요", "예요", "에요", "래요", "게요", "네요",              # 해요체 기타
    "군요", "는군요", "구나", "죠", "지요",                     # 감탄·반말
    "았다", "었다", "였다", "겠다",                            # 과거·추측 평서(받침형, 명사 충돌 낮음)
)

# 연결어미·조사(동형 종결어미 오탐 차단, 우선 적용).
KO_EXCLUDE_SUFFIXES = (
    "니까", "는데", "ㄴ데", "다가", "다고", "다면", "라고", "라며",
    "면서", "으며", "어서", "아서", "지만", "거나", "든지",
    "으로", "로", "에서", "에게", "부터", "까지", "보다", "처럼",
    "만큼", "이나", "라는", "다는",
)

EN_ABBREV = frozenset({
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "mt", "rev", "hon",
    "gen", "col", "sgt", "capt", "lt", "gov", "sen", "rep", "pres", "dept", "univ",
    "etc", "eg", "ie", "vs", "al", "cf", "viz", "et",
    "am", "pm", "no", "vol", "pp", "fig", "ch", "sec", "min", "hr",
    "us", "uk", "un", "eu", "usa", "dc", "inc", "ltd", "co", "corp", "llc", "plc",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
})


def _has_hangul(text: str) -> bool:
    """한글 음절(U+AC00–D7A3) 포함 여부 — 언어 라우팅(스크립트 판정)용."""
    return any('가' <= c <= '힣' for c in text)


def _last_word(text: str) -> str:
    """후행 구두점·공백을 떼고 마지막 공백구분 어절을 반환(없으면 '')."""
    s = text.strip()
    while s and s[-1] in PUNCTUATION_MARKS:
        s = s[:-1]
    s = s.rstrip()
    parts = s.split()
    return parts[-1] if parts else ""


def is_sentence_final_ko(word: str) -> bool:
    """한국어 어절이 종결어미로 끝나는지(연결어미·조사는 우선 차단)."""
    if not _has_hangul(word):
        return False
    if word.endswith(KO_EXCLUDE_SUFFIXES):
        return False
    return word.endswith(KO_FINAL_SUFFIXES)


def is_abbreviation_en(word: str) -> bool:
    """영어 어절이 약어/이니셜인지(온점 분할하면 안 되는 케이스)."""
    core = word.replace(".", "")
    if not core:
        return False
    if len(core) == 1:
        return True                       # 이니셜 J. F.
    if "." in word and core.isupper():
        return True                       # U.S U.N U.K
    return core.lower() in EN_ABBREV


def is_genuine_sentence_end(closing_text: str, next_text=None) -> bool:
    """닫히는 세그먼트 텍스트가 '진짜 문장 종결'인지 판정.

    next_text: 다음 어절 텍스트(있으면). 영어 판정에서 대문자 시작 여부에 사용.
    한국어는 종결어미가 자족적이라 next_text 불요.
    """
    s = closing_text.rstrip()
    # 전역 가드: 종결 온점 직전 문자가 숫자면 서수/열거/소수("3." "1.") → 분할 안 함.
    j = len(s)
    while j > 0 and s[j - 1] in PUNCTUATION_MARKS:
        j -= 1
    if j > 0 and s[j - 1].isdigit():
        return False
    word = _last_word(closing_text)
    if not word:
        return False
    if _has_hangul(word):
        return is_sentence_final_ko(word)
    # 영어: 약어 아니고, 다음 어절이 대문자로 시작할 때만(발화끝/침묵은 호출부 (a)/(b)가 처리).
    if is_abbreviation_en(word):
        return False
    if next_text is None:
        return False
    nxt = next_text.strip()
    return bool(nxt) and nxt[0].isupper()
