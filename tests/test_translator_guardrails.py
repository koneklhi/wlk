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
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from whisperlivekit.llm_translation.manager import (
    _INTERIM_MIN_DELTA_CHARS,
    _MIN_INTERIM_CHARS,
    TranslationManager,
)
from whisperlivekit.llm_translation.translator import (
    LlamaTranslator,
    OllamaTranslator,
    TranslatorBase,
    _infer_script_lang,
)


def _translator() -> LlamaTranslator:
    """네트워크를 타지 않는 더미 인스턴스 (__init__ 은 httpx 클라이언트만 생성)."""
    return LlamaTranslator("dummy", "http://x")


# ─── _infer_script_lang (다수결 우세 60%) ─────────────────────────────────────

def test_infer_script_lang_pure_korean():
    """순수 한국어 문장 → 'ko'."""
    assert _infer_script_lang("오늘 회의는 오후 세시에 시작합니다") == "ko"


def test_infer_script_lang_pure_english():
    """순수 영어 문장 → 'en'."""
    assert _infer_script_lang("The meeting starts at three this afternoon") == "en"


def test_infer_script_lang_korean_with_abbreviation_returns_ko():
    """한글 우세인데 영어 약어(GPS)가 섞인 문장 → 'ko' (이번 수정의 핵심 회귀 방어).

    한글 10자 + 영문 3자 → 한글 우세 0.77 ≥ 0.6. 과거 85% 임계는 여기서 None을 내
    detected_language='en' 오검출로 인한 동일언어 통과를 못 잡았다(개발 PC 재현 확인).
    """
    assert _infer_script_lang("GPS 시스템을 확인했습니다") == "ko"


def test_infer_script_lang_short_abbreviation_returns_none():
    """짧은 약어("GPS") → 표본 부족(total < 6)으로 None (판단 보류)."""
    assert _infer_script_lang("GPS") is None


def test_infer_script_lang_near_tie_mixed_returns_none():
    """한·영 근소차 혼합문(우세 < 60%) → None — 진짜 code-switching으로 보고 STT 판단 존중."""
    # 완전 동수(한글 6 = 영문 6)
    assert _infer_script_lang("I think 우리가 맞아요") is None
    # 우세 스크립트가 있으나 60% 미만 (한글 7 / 영문 5 = 0.583 < 0.6)
    assert _infer_script_lang("우리가 확인했다 check") is None
    # 기존 동수 케이스(한글 5 = 영문 5)
    assert _infer_script_lang("안녕하세요 hello") is None


def test_infer_script_lang_empty_returns_none():
    """빈 문자열 → 표본 부족 None (0/0 division 회피 확인)."""
    assert _infer_script_lang("") is None


# ─── _infer_script_lang 순수 스크립트 fast-path ──────────────────────────────

def test_infer_script_lang_pure_short_korean_fast_path():
    """순수 한글은 표본수 무관 즉시 'ko' — "감사합니다"(한글 5자<6) 사각지대 해소."""
    assert _infer_script_lang("감사합니다") == "ko"


def test_infer_script_lang_single_hangul_char_fast_path():
    """한글 1자("네")도 'ko' 확정 — 한글 스크립트는 한국어 배타적."""
    assert _infer_script_lang("네") == "ko"


def test_infer_script_lang_pure_latin_four_chars_is_en():
    """라틴 단독 4자 이상("Okay.") → 'en' 확정."""
    assert _infer_script_lang("Okay.") == "en"


def test_infer_script_lang_short_latin_abbreviation_still_none():
    """라틴 단독 3자 약어("GPS"·"ROK") → 여전히 None (약어 오판 방지, 기존 거동 유지)."""
    assert _infer_script_lang("GPS") is None
    assert _infer_script_lang("ROK") is None


# ─── resolve_src_lang ────────────────────────────────────────────────────────

def test_resolve_src_lang_corrects_misdetected_en_to_ko():
    """detected_language='en' 이지만 문자구성이 한국어 → 'ko'로 보정.

    배포 버그 재현: 한국어 발화가 en 으로 오검출되면 방향이 반전돼 번역 없이 통과된다.
    """
    t = _translator()
    result = t.resolve_src_lang("오늘 회의는 오후 세시에 시작합니다", "en")
    assert result == "ko"


def test_resolve_src_lang_corrects_misdetected_en_to_ko_with_abbreviation():
    """영어 약어가 섞인 한국어 발화(det='en' 오검출) → 'ko' 보정 (동일언어 통과 방어의 핵심).

    개발 PC 재현: STT가 "GPS 시스템을 확인했습니다"를 en으로 오검출 → 방향 반전 →
    번역 결과가 한국어 그대로 통과. 다수결(우세 60%)로 한글 우세를 잡아 방향을 ko로 보정한다.
    """
    t = _translator()
    assert t.resolve_src_lang("GPS 시스템을 확인했습니다", "en") == "ko"


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


def test_resolve_src_lang_corrects_short_pure_korean():
    """대표 버그 회귀 방어: 짧은 순수 한국어("감사합니다", 한글 5자)가 detected='en'
    캐리오버로 들어와도 fast-path가 'ko'로 보정한다 — 과거엔 표본 부족(<6)으로 사각지대."""
    t = _translator()
    assert t.resolve_src_lang("감사합니다", "en") == "ko"


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
    """미확정 버퍼가 충분히 길면 정상적으로 번역 요청을 트리거한다.

    interim 디바운스(시간·델타) 도입 후, 새 줄(_interim_source="")의 첫 발동은
    델타 게이트 _INTERIM_MIN_DELTA_CHARS(=12) 이상이어야 통과한다 — 이는
    _MIN_INTERIM_CHARS(=6)보다 엄격하므로 여기서는 델타 게이트 기준으로 버퍼를 잡는다.
    시간 게이트는 갓 생성한 manager(last_dispatch_ts=0.0)라 통과한다.
    """
    manager = _manager()
    long_enough = "가" * _INTERIM_MIN_DELTA_CHARS

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


# ─── _is_echo (출력측 에코 게이트 판정) ──────────────────────────────────────

def test_is_echo_ko_content_ko_result_true():
    """ko 원문 + ko 결과 = 에코(True) — 방향 반전으로 원문이 그대로 돌아온 경우."""
    assert TranslatorBase._is_echo("감사합니다", "감사합니다 정말로") is True


def test_is_echo_ko_content_en_result_false():
    """ko 원문 + en 결과 = 정상 번역(False)."""
    assert TranslatorBase._is_echo("감사합니다", "Thank you very much") is False


def test_is_echo_en_content_en_result_true():
    """en 원문 + en 결과 = 에코(True)."""
    assert TranslatorBase._is_echo("Thank you very much", "Thank you very much") is True


def test_is_echo_mixed_content_returns_false():
    """혼합문 원문(스크립트 판정 None) → 보류(False) — §3.2 혼합문 STT 존중, 위양성 방지."""
    assert TranslatorBase._is_echo("I think 우리가 맞아요", "I think 우리가 맞아요") is False


def test_is_echo_undecidable_result_returns_false():
    """결과 쪽 판정 불가(짧은 라틴 "ROK") → 보류(False)."""
    assert TranslatorBase._is_echo("감사합니다", "ROK") is False


def test_is_echo_empty_result_returns_false():
    """빈 결과 → False (실패 처리는 다른 계층 책임)."""
    assert TranslatorBase._is_echo("감사합니다", "") is False


# ─── translate_sentence 오케스트레이션 (에코 재시도 템플릿 메서드) ────────────

class _StubTranslator(TranslatorBase):
    """_translate_once 호출을 기록하고 미리 준비한 결과를 차례로 반환하는 스텁."""

    def __init__(self, results: list[str]):
        super().__init__("dummy", "http://x")
        self._results = list(results)
        self.calls: list[dict] = []

    async def _translate_once(
        self, content: str, src_lang: str, use_rag: bool = False, strict_direction: bool = False
    ) -> str:
        self.calls.append({
            "content": content, "src_lang": src_lang,
            "use_rag": use_rag, "strict_direction": strict_direction,
        })
        return self._results.pop(0)


@pytest.mark.anyio
async def test_translate_sentence_retries_with_forced_src_and_strict_direction():
    """1차 에코 → 2차가 forced_src(문자구성 기준) + strict_direction=True로 호출되고,
    2차가 정상이면 그 값을 반환한다."""
    stub = _StubTranslator(["감사합니다 그대로 에코", "Thank you"])
    result = await stub.translate_sentence("감사합니다", "en", use_rag=True)

    assert result == "Thank you"
    assert len(stub.calls) == 2
    # 1차: resolve_src_lang이 이미 en→ko 보정 (fast-path)
    assert stub.calls[0]["src_lang"] == "ko"
    assert stub.calls[0]["strict_direction"] is False
    assert stub.calls[0]["use_rag"] is True
    # 2차: 문자구성 강제 src + 방향 지시문
    assert stub.calls[1]["src_lang"] == "ko"
    assert stub.calls[1]["strict_direction"] is True
    assert stub.calls[1]["use_rag"] is True


@pytest.mark.anyio
async def test_translate_sentence_double_echo_returns_empty():
    """2연속 에코 → 번역 실패로 빈 문자열 반환."""
    stub = _StubTranslator(["감사합니다 에코", "감사합니다 재차 에코"])
    result = await stub.translate_sentence("감사합니다", "ko")

    assert result == ""
    assert len(stub.calls) == 2


@pytest.mark.anyio
async def test_translate_sentence_no_retry_when_retry_on_echo_false():
    """retry_on_echo=False(interim 경로) — 1차 에코 즉시 빈 문자열, 2차 호출 없음."""
    stub = _StubTranslator(["감사합니다 에코"])
    result = await stub.translate_sentence("감사합니다", "ko", retry_on_echo=False)

    assert result == ""
    assert len(stub.calls) == 1


@pytest.mark.anyio
async def test_translate_sentence_single_call_when_no_echo():
    """1차 정상 → 재시도 없이 1회 호출로 끝난다."""
    stub = _StubTranslator(["Thank you"])
    result = await stub.translate_sentence("감사합니다", "ko")

    assert result == "Thank you"
    assert len(stub.calls) == 1
    assert stub.calls[0]["strict_direction"] is False


# ─── strict_direction 지시문 주입 (백엔드 프롬프트 레벨) ─────────────────────

def _empty_prompt_manager() -> MagicMock:
    pm = MagicMock()
    pm.get_relevant_glossary.return_value = ""
    pm.get_sentence_block.return_value = ""
    return pm


@pytest.mark.anyio
async def test_llama_strict_direction_injects_directive_into_prompt():
    """LlamaTranslator: strict_direction=True면 completions 프롬프트에 방향 강제 지시문 포함."""
    t = LlamaTranslator("dummy", "http://x")
    t._call_completions = AsyncMock(return_value="Thank you")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager",
               return_value=_empty_prompt_manager()):
        await t._translate_once("감사합니다", "ko", strict_direction=True)

    prompt = t._call_completions.call_args[0][0]
    assert "ONLY in" in prompt
    assert "Korean" in prompt and "English" in prompt


@pytest.mark.anyio
async def test_llama_no_directive_without_strict_direction():
    """strict_direction=False(기본) — 지시문이 프롬프트에 없어야 한다."""
    t = LlamaTranslator("dummy", "http://x")
    t._call_completions = AsyncMock(return_value="Thank you")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager",
               return_value=_empty_prompt_manager()):
        await t._translate_once("감사합니다", "ko")

    prompt = t._call_completions.call_args[0][0]
    assert "ONLY in" not in prompt


@pytest.mark.anyio
async def test_ollama_strict_direction_injects_directive_into_system_text():
    """OllamaTranslator: strict_direction=True면 system 텍스트에 방향 강제 지시문 포함."""
    t = OllamaTranslator("dummy", "http://x")
    t._call_chat = AsyncMock(return_value="Thank you")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager",
               return_value=_empty_prompt_manager()):
        await t._translate_once("감사합니다", "ko", strict_direction=True)

    system_text = t._call_chat.call_args[0][0]
    assert "ONLY in" in system_text
