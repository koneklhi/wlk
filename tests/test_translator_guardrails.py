# -*- coding: utf-8 -*-
"""번역 가드레일 단위 테스트 (순수 로직 — 네트워크 호출 없음).

배포 실측에서 관찰된 두 버그를 방어하는 3개 단위:
1. resolve_src_lang / _infer_script_lang — STT detected_language 오검출로 인한
   번역 방향 반전(한국어가 번역 없이 그대로 통과)을 문자 구성으로 보정.
2. _sanitize_result — LLM 멀티라인/과장 출력(환각) 폐기.
3. (manager) 미확정 버퍼 최소 길이 게이트 — 짧은 조각은 번역 요청하지 않고, 확정 경로
   apply_translations 에는 길이 게이트가 없다.

resolve_src_lang/_sanitize_result 는 인스턴스 메서드지만 네트워크를 타지 않으므로
더미 인스턴스(LlamaTranslator(...) — __init__ 은 httpx.AsyncClient 생성만 함)로 테스트한다.
"""

import unittest.mock as mock_module
from unittest.mock import AsyncMock, MagicMock

from whisperlivekit.llm_translation.manager import _MIN_INTERIM_CHARS, TranslationManager
from whisperlivekit.llm_translation.translator import (
    LlamaTranslator,
    _infer_script_lang,
)


def _translator() -> LlamaTranslator:
    """네트워크를 타지 않는 더미 인스턴스 (__init__ 은 httpx 클라이언트만 생성)."""
    return LlamaTranslator("dummy", "http://x")


# ─── _infer_script_lang ──────────────────────────────────────────────────────

def test_infer_script_lang_pure_korean():
    """순수 한국어 문장 → 'ko'."""
    assert _infer_script_lang("오늘 회의는 오후 세시에 시작합니다") == "ko"


def test_infer_script_lang_pure_english():
    """순수 영어 문장 → 'en'."""
    assert _infer_script_lang("The meeting starts at three this afternoon") == "en"


def test_infer_script_lang_short_abbreviation_returns_none():
    """짧은 약어("GPS") → 표본 부족(total < 6)으로 None (판단 보류)."""
    assert _infer_script_lang("GPS") is None


def test_infer_script_lang_mixed_returns_none():
    """혼합 문장(어느 쪽도 85% 미만) → None."""
    # 한글 5자 + 영문 5자 → 각 50%, 어느 쪽도 0.85 미만
    assert _infer_script_lang("안녕하세요 hello") is None


def test_infer_script_lang_empty_returns_none():
    """빈 문자열 → 표본 부족 None (0/0 division 회피 확인)."""
    assert _infer_script_lang("") is None


# ─── resolve_src_lang ────────────────────────────────────────────────────────

def test_resolve_src_lang_corrects_misdetected_en_to_ko():
    """detected_language='en' 이지만 문자구성이 한국어 → 'ko'로 보정.

    배포 버그 재현: 한국어 발화가 en 으로 오검출되면 방향이 반전돼 번역 없이 통과된다.
    """
    t = _translator()
    result = t.resolve_src_lang("오늘 회의는 오후 세시에 시작합니다", "en")
    assert result == "ko"


def test_resolve_src_lang_keeps_matching_language():
    """문자 구성이 detected_language 와 일치하면 원래 값 유지."""
    t = _translator()
    assert t.resolve_src_lang("오늘 회의는 오후 세시에 시작합니다", "ko") == "ko"
    assert t.resolve_src_lang("The meeting starts at three", "en") == "en"


def test_resolve_src_lang_keeps_original_when_inference_none():
    """문자 구성으로 판단 불가(None)면 detected_language 를 신뢰(원래 값 유지)."""
    t = _translator()
    # 짧은 약어 — _infer_script_lang → None
    assert t.resolve_src_lang("GPS", "en") == "en"
    assert t.resolve_src_lang("GPS", "ko") == "ko"


# ─── _sanitize_result ────────────────────────────────────────────────────────

def test_sanitize_result_multiline_takes_first_line():
    """개행 포함 멀티라인 출력 → 첫 번째 비어있지 않은 줄만 남는다 (다중 문장 환각 방어)."""
    t = _translator()
    out = t._sanitize_result("Hello.\nHow are you?\nI hope you are well.")
    assert out == "Hello."


def test_sanitize_result_multiline_skips_leading_blank_lines():
    """선행 빈 줄이 있어도 첫 번째 비어있지 않은 줄을 취한다."""
    t = _translator()
    out = t._sanitize_result("\n   \nHello there.\nextra line")
    assert out == "Hello there."


def test_sanitize_result_normal_length_passes_through():
    """정상 길이 한 줄 → 그대로 통과."""
    t = _translator()
    out = t._sanitize_result("Hello, nice to meet you.")
    assert out == "Hello, nice to meet you."


def test_sanitize_result_short_result_passes_through():
    """아주 짧은 정상 결과("Yes") → 그대로 통과 (폐기 없음)."""
    t = _translator()
    assert t._sanitize_result("Yes") == "Yes"


def test_sanitize_result_overlong_single_line_truncated_not_discarded():
    """_MAX_RESULT_CHARS(500)를 초과하는 개행 없는 초장문 → 빈 문자열이 아니라 500자로 절단.

    폐기(빈 문자열)하면 확정 경로에서 캐시에 안 남아 temperature=0 가비지가 매 tick
    재번역되는 무한 재시도가 된다. 잘라서라도 non-empty로 돌려줘야 캐시에 정착한다.
    """
    from whisperlivekit.llm_translation.translator import _MAX_RESULT_CHARS

    t = _translator()
    runaway = "A" * (_MAX_RESULT_CHARS + 300)  # 개행 없는 초장문
    out = t._sanitize_result(runaway)
    assert out != "", "초장문이라도 폐기하지 않고 절단해 non-empty로 돌려줘야 한다"
    assert len(out) <= _MAX_RESULT_CHARS, "절대 상한(500자) 이하로 절단돼야 한다(rstrip으로 그 이하 가능)"
    assert len(out) == _MAX_RESULT_CHARS, "공백 없는 'A' 연속이므로 rstrip 후에도 정확히 500자"


# ─── manager: 미확정 버퍼 최소 길이 게이트 ────────────────────────────────────

def _manager() -> TranslationManager:
    translator = MagicMock()
    translator.translate_sentence = AsyncMock(return_value="translated")
    return TranslationManager(translator)


def test_interim_gate_blocks_short_text():
    """미확정 버퍼가 _MIN_INTERIM_CHARS 미만이면 새 LLM 요청을 트리거하지 않는다."""
    manager = _manager()
    manager._interim_result = "직전 결과"  # 직전 완료된 미리보기 결과

    short = "가" * (_MIN_INTERIM_CHARS - 1)
    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        result = manager.apply_interim_translation(short, "ko")

    mock_ensure.assert_not_called()
    assert result == "직전 결과", "짧은 조각은 직전 결과를 그대로 반환해야 한다"
    assert manager._interim_source == "", "짧은 조각은 source 갱신 없이 무시돼야 한다"


def test_interim_gate_allows_long_enough_text():
    """미확정 버퍼가 _MIN_INTERIM_CHARS 이상이면 정상적으로 번역 요청을 트리거한다."""
    manager = _manager()
    long_enough = "가" * _MIN_INTERIM_CHARS

    captured = []

    def closing_ensure_future(coro):
        captured.append(coro)
        coro.close()  # RuntimeWarning 방지
        return MagicMock()

    with mock_module.patch("asyncio.ensure_future", side_effect=closing_ensure_future):
        manager.apply_interim_translation(long_enough, "ko")

    assert len(captured) == 1, "충분한 길이의 버퍼는 번역 task를 1회 트리거해야 한다"
    assert manager._interim_in_flight is True
    assert manager._interim_source == long_enough


def test_interim_empty_text_resets_state():
    """빈 문자열은 기존 리셋 분기를 유지 — 내부 상태를 비운다(게이트 이전 처리)."""
    manager = _manager()
    manager._interim_source = "이전"
    manager._interim_result = "이전 결과"
    manager._interim_in_flight = True

    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        result = manager.apply_interim_translation("", "ko")

    mock_ensure.assert_not_called()
    assert result == ""
    assert manager._interim_source == ""
    assert manager._interim_result == ""
    assert manager._interim_in_flight is False


def test_apply_translations_has_no_length_gate_for_short_finalized_seg():
    """확정 경로(apply_translations)에는 길이 게이트가 없다 — 짧은 확정 발화("다음")도 번역된다.

    interim 게이트가 확정 경로로 새지 않았음을 회귀 방어로 고정한다.
    """
    from whisperlivekit.timed_objects import Segment

    manager = _manager()
    seg = Segment(start=1.0, end=1.5, text="다음", speaker=-1,
                  detected_language="ko", finalized=True)

    captured = []

    def closing_ensure_future(coro):
        captured.append(coro)
        coro.close()
        return MagicMock()

    with mock_module.patch("asyncio.ensure_future", side_effect=closing_ensure_future):
        manager.apply_translations([seg])

    # 2글자 짧은 확정 발화라도 번역 task가 스케줄돼야 한다(길이 게이트 없음).
    key = manager._cache_key(seg)
    assert key in manager._in_flight
    assert len(captured) == 1
