# -*- coding: utf-8 -*-
import json
import re
from pathlib import Path

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
