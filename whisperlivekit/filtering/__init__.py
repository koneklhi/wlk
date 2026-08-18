# -*- coding: utf-8 -*-
import copy
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 배포 환경 불변식: 한국어·영어만 존재.
# CJK 한자·히라가나·가타카나 포함 세그먼트는 정의상 오언어 환각 → 통째 드롭.
# 한글(U+AC00-D7A3)은 이 범위에 포함되지 않으므로 한국어 전사는 절대 안 걸린다.
_CJK_KANA_RE = re.compile(
    "[一-鿿"   # CJK 한자 기본
    "㐀-䶿"    # CJK 확장 A
    "⺀-⻿"    # CJK 부수 보충
    "⼀-⿟"    # 강희자전 부수
    "豈-﫿"    # CJK 호환 한자
    "぀-ゟ"    # 히라가나
    "゠-ヿ]"   # 가타카나
)

# 비음성 주석 스팬 제거: (웃음) [구독] ♪...♪ 등.
# 제거 후 공백만 남으면 기존 empty-drop 로직이 드롭한다.
_ANNOTATION_RE = re.compile(
    r"\([^)]*\)"      # (웃음) (laughter) — 닫힌 괄호 주석
    r"|\[[^\]]*\]"    # [구독] [MUSIC] — 닫힌 대괄호 주석
    # 안 닫힌 비음성 주석(Whisper가 웃음/외국어 구간에서 방출, 닫는 괄호 유실):
    # 알려진 주석 키워드로 시작하는 경우만, ASCII 영문/공백/따옴표/마침표까지만 제거해
    # 뒤따르는 정상(한글 등) 텍스트는 보존한다(과잉 제거 방지).
    r"|\((?:speaking|laughter|applause|music|singing|coughs?|sighs?|noise|sound)[A-Za-z' .]*\)?"
    r"|\[[A-Z][A-Za-z_ .]*\]?"   # 안 닫힌 대괄호 주석([LAUGHTER, [MUSIC PLAYING) — 대문자 시작
    r"|[♪♩♫♬]"       # 음표 기호
)

from .manager import WordCorrectionManager

_FILTERING_DIR = Path(__file__).resolve().parent

# ─── 단어 오인식 교정 매니저 ──────────────────────────────────────────────────

_word_manager = None


def get_word_manager() -> WordCorrectionManager:
    global _word_manager
    if _word_manager is None:
        _word_manager = WordCorrectionManager(
            base_json_path=str(_FILTERING_DIR / "admin_replacement.json"),
            db_path=str(_FILTERING_DIR / "user_replacement.db"),
        )
    return _word_manager


# 컴파일된 치환 정규식 캐시. 키는 combined_replacements **객체 자신**(is 비교)이다 —
# WordCorrectionManager.refresh_replacements()가 갱신 때마다 새 dict를 만들어 대입하므로,
# 사전이 바뀌면 identity가 달라져 자동으로 재컴파일된다(값 비교 불필요·stale 불가).
_pattern_cache: tuple = (None, None)


def _current_replacements():
    """현재 단어 교정 사전과 컴파일된 정규식을 반환. 없으면 (None, None).

    사전은 프로세스 전역 싱글턴이라, REST(/api/corrections)로 갱신하면 **다음 호출부터**
    새 사전이 잡힌다 — 녹음(세션) 진행 중 등록한 단어가 즉시 반영되는 근거다.
    """
    global _pattern_cache
    replacements = get_word_manager().combined_replacements
    if not replacements:
        return None, None
    cached_replacements, cached_pattern = _pattern_cache
    if cached_replacements is replacements:
        return replacements, cached_pattern
    pattern = re.compile("|".join(re.escape(k) for k in replacements.keys()))
    _pattern_cache = (replacements, pattern)
    return replacements, pattern


def apply_word_corrections(text: str) -> str:
    """단어 교정 사전을 문자열 하나에 적용한다.

    확정 세그먼트(filter_segments)와 **미확정 버퍼**(results_formatter의 buffer_transcription/
    buffer_diarization) 양쪽이 같은 사전을 쓰도록 뽑아낸 공개 헬퍼다. 버퍼에도 적용해야
    "지금 전사 중인 문장"에 대치가 실시간으로 보인다.
    """
    if not text:
        return text
    replacements, pattern = _current_replacements()
    if pattern is None:
        return text
    return pattern.sub(lambda m: replacements[m.group(0)], text)


# ─── 환각 토큰 목록 (최초 1회 로드) ─────────────────────────────────────────

def _load_hallucination_json() -> list:
    """hallucination.json은 변동이 거의 없으므로 최초 한 번만 로드"""
    file_path = _FILTERING_DIR / "hallucination.json"
    if not file_path.exists():
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        data = list(json.load(f))
    return sorted(data, key=len, reverse=True)


_HALLUCINATIONS = _load_hallucination_json()


# ─── 필터링 함수 ─────────────────────────────────────────────────────────────

def filter_hallucination(raw_transcript: list) -> list:
    """
    hallucination.json 에 정의된 불필요 토큰 삭제 후
    WordCorrectionManager.combined_replacements 로 단어 교정.

    입출력 형식: [(start, end, text), ...]  (whisperlive 기존 형태 유지)
    """
    if not raw_transcript:
        return []

    filtered = []
    for segment in raw_transcript:
        seg = list(segment)
        for bad_token in _HALLUCINATIONS:
            if bad_token in seg[2]:
                seg[2] = seg[2].replace(bad_token, "")

        # 환각 토큰 제거 후 다중 공백 정리
        seg[2] = re.sub(r'\s+', ' ', seg[2]).strip()

        txt = seg[2].strip()
        if txt and txt not in {".", "?"} and set(txt) != {"."}:
            filtered.append(seg)

    for seg in filtered:
        seg[2] = apply_word_corrections(seg[2])

    return [tuple(seg) for seg in filtered]


def filter_segments(segments: list) -> list:
    """Segment 객체 리스트에 환각 제거 + 단어 교정을 적용한다.

    results_formatter() 에서 get_lines() 직후 호출용.
    침묵 세그먼트(is_silence())는 그대로 통과시킨다.

    **원본 세그먼트를 변형하지 않는다** — 텍스트가 바뀌는 세그먼트는 사본을 만들어 반환한다.
    비-diar 경로(get_lines의 `segments = list(self.validated_segments)`)는 세그먼트 객체가
    tick 을 넘어 살아남기 때문에, 원본을 in-place 로 고치면 ① 치환 결과가 다시 패턴에 걸릴 때
    매 tick 누적되고("6군"→"제6군단"→"제제6군단단") ② 관리자 페이지에서 사전 항목을 지워도
    원문으로 돌아오지 않는다. 매 tick 원문에서 다시 계산하게 해 두 문제를 함께 막는다.
    (diar 경로는 어차피 매 tick 토큰에서 세그먼트를 새로 만들므로 동작 변화가 없다.)
    """
    if not segments:
        return segments

    result = []
    for seg in segments:
        if not seg.text or seg.is_silence():
            result.append(seg)
            continue

        text = seg.text

        # 불변식 1: 비음성 주석 스팬 제거 ((웃음), [구독], 음표 등)
        text = _ANNOTATION_RE.sub("", text).strip()

        # 불변식 2: CJK 한자/히라가나/가타카나 포함 세그먼트 → 오언어 환각, 통째 드롭
        if _CJK_KANA_RE.search(text):
            # 버려진 텍스트를 로깅 (단계 C 계측: 오언어 드롭이 정상 한국어를 오탈하는지 감시).
            logger.warning("[CJKDrop] CJK/kana 포함 세그먼트 드롭: %.200s", text)
            continue

        pre_hallucination_text = text
        for bad in _HALLUCINATIONS:
            if bad in text:
                text = text.replace(bad, "")
        text = re.sub(r"\s+", " ", text).strip()
        if text != pre_hallucination_text:
            logger.debug(
                "[HallucinationDrop] 원문=%.200s 치환문=%.200s",
                pre_hallucination_text, text,
            )

        # 유령/중복 온점 collapse: QG 억제→재디코딩이 재귀속 자리에 만든 중복 "."을 정리한다.
        # ". ." ".." → ".", 선두 단독 온점 스트립(". 자신의" → "자신의"). 문장 끝 정상 온점
        # 1개와 단어 사이 단일 온점("very. much")은 보존, 물음표·느낌표도 보존.
        text = re.sub(r"(?:\s*\.\s*){2,}", ". ", text).strip()
        text = re.sub(r"^[.\s]+", "", text).strip()

        # 빈/구두점-only 세그먼트 제거. 공백을 무시해 " . ."(diar 병합 유령 온점)도 드롭한다.
        bare = text.replace(" ", "")
        if not bare or set(bare) <= {".", "?", "!", "。", "！", "？"}:
            continue

        corrected = apply_word_corrections(text)
        if corrected != text:
            logger.debug(
                "[WordCorrection] 원문=%.200s 치환문=%.200s",
                text, corrected,
            )
        text = corrected

        if text == seg.text:
            result.append(seg)
            continue

        out = copy.copy(seg)
        out.text = text
        result.append(out)

    return result
