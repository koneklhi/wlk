# -*- coding: utf-8 -*-
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

    word_manager = get_word_manager()
    replacements = word_manager.combined_replacements
    if replacements:
        pattern = re.compile("|".join(re.escape(k) for k in replacements.keys()))
        for seg in filtered:
            seg[2] = pattern.sub(lambda m: replacements[m.group(0)], seg[2])

    return [tuple(seg) for seg in filtered]


def filter_segments(segments: list) -> list:
    """Segment 객체 리스트에 환각 제거 + 단어 교정을 적용한다.

    results_formatter() 에서 get_lines() 직후 호출용.
    침묵 세그먼트(is_silence())는 그대로 통과시킨다.
    """
    if not segments:
        return segments

    word_manager = get_word_manager()
    replacements = word_manager.combined_replacements
    pattern = re.compile("|".join(re.escape(k) for k in replacements.keys())) if replacements else None

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

        for bad in _HALLUCINATIONS:
            if bad in text:
                text = text.replace(bad, "")
        text = re.sub(r"\s+", " ", text).strip()

        if not text or text in {".", "?"} or set(text) == {"."}:
            continue  # 빈/구두점-only 세그먼트 제거

        if pattern:
            text = pattern.sub(lambda m: replacements[m.group(0)], text)

        seg.text = text
        result.append(seg)

    return result
