# -*- coding: utf-8 -*-
"""Task 4: TranslationManager 단위 테스트.

검증 항목:
- finalized=True + text 있는 세그먼트에 번역 task 생성됨 (_in_flight에 키 추가)
- 캐시 히트 시 seg.translation에 값이 세팅됨
- finalized=False 세그먼트는 건너뜀
- silence 세그먼트는 건너뜀
- _translate_and_cache: 번역기 호출 후 캐시에 저장, in_flight 에서 제거
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from whisperlivekit.llm_translation.manager import TranslationManager
from whisperlivekit.timed_objects import Segment


# ─── 헬퍼 ────────────────────────────────────────────────────────────────────

def make_text_seg(text: str, start: float = 0.0, end: float = 1.0,
                  finalized: bool = True, detected_language: str = "ko") -> Segment:
    """텍스트 세그먼트 (speaker=-1) 생성."""
    seg = Segment(start=start, end=end, text=text, speaker=-1,
                  detected_language=detected_language, finalized=finalized)
    return seg


def make_silence_seg(start: float = 0.0, end: float = 0.5) -> Segment:
    """Silence 세그먼트 (speaker=-2) 생성."""
    return Segment(start=start, end=end, text=None, speaker=-2)


def make_translator_mock(return_value: str = "번역 결과") -> MagicMock:
    """translate_sentence가 즉시 값을 반환하는 mock translator."""
    mock = MagicMock()
    mock.translate_sentence = AsyncMock(return_value=return_value)
    return mock


# ─── 테스트 ──────────────────────────────────────────────────────────────────

def test_apply_translations_schedules_task_for_finalized_seg():
    """finalized=True + text 있는 세그먼트에 비차단 task가 생성돼 _in_flight에 키가 추가된다."""
    translator = make_translator_mock()
    manager = TranslationManager(translator)

    seg = make_text_seg("안녕하세요.", start=1.0, end=2.0, finalized=True)

    captured_coros = []

    def closing_ensure_future(coro):
        """coroutine을 닫아 RuntimeWarning 방지."""
        captured_coros.append(coro)
        coro.close()
        return MagicMock()

    import unittest.mock as mock_module
    with mock_module.patch("asyncio.ensure_future", side_effect=closing_ensure_future):
        manager.apply_translations([seg])

    key = manager._cache_key(seg)
    assert key in manager._in_flight, "_in_flight에 키가 없습니다"
    assert len(captured_coros) == 1, "asyncio.ensure_future가 1회 호출돼야 합니다"


def test_apply_translations_cache_hit_sets_translation():
    """캐시 히트 시 seg.translation에 캐시된 값이 세팅된다."""
    translator = make_translator_mock()
    manager = TranslationManager(translator)

    seg = make_text_seg("Hello.", start=0.5, end=1.0, finalized=True)
    key = manager._cache_key(seg)
    manager._cache[key] = "안녕하세요."

    manager.apply_translations([seg])

    assert seg.translation == "안녕하세요.", f"seg.translation 값이 올바르지 않습니다: {seg.translation}"
    # 캐시 히트이므로 _in_flight에 추가되지 않아야 함
    assert key not in manager._in_flight, "캐시 히트인데 _in_flight에 키가 추가됐습니다"


def test_apply_translations_skips_not_finalized():
    """finalized=False 세그먼트는 번역 task를 생성하지 않는다."""
    translator = make_translator_mock()
    manager = TranslationManager(translator)

    seg = make_text_seg("진행 중 문장", start=0.0, end=0.5, finalized=False)

    import unittest.mock as mock_module
    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        manager.apply_translations([seg])

    assert len(manager._in_flight) == 0, "_in_flight에 키가 추가됐습니다"
    mock_ensure.assert_not_called()


def test_apply_translations_skips_silence():
    """silence 세그먼트는 번역 task를 생성하지 않는다."""
    translator = make_translator_mock()
    manager = TranslationManager(translator)

    seg = make_silence_seg(start=1.0, end=2.0)

    import unittest.mock as mock_module
    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        manager.apply_translations([seg])

    assert len(manager._in_flight) == 0, "silence인데 _in_flight에 키가 추가됐습니다"
    mock_ensure.assert_not_called()


@pytest.mark.anyio
async def test_translate_and_cache_stores_result_and_removes_in_flight():
    """_translate_and_cache: 번역기 호출 후 캐시에 저장, _in_flight에서 제거."""
    translator = make_translator_mock(return_value="번역 결과")
    manager = TranslationManager(translator)

    key = (1.0, "test text")
    manager._in_flight.add(key)

    await manager._translate_and_cache(key, "test text", "en")

    assert key in manager._cache, "번역 결과가 캐시에 저장되지 않았습니다"
    assert manager._cache[key] == "번역 결과", f"캐시 값이 올바르지 않습니다: {manager._cache[key]}"
    assert key not in manager._in_flight, "_in_flight에서 키가 제거되지 않았습니다"
    # 확정 경로이므로 use_rag=True — Qdrant RAG 예시가 프롬프트에 주입돼야 한다(Stage 2).
    translator.translate_sentence.assert_called_once_with("test text", "en", use_rag=True)


@pytest.mark.anyio
async def test_translate_and_cache_removes_in_flight_on_error():
    """_translate_and_cache: 번역기 예외 발생 시에도 _in_flight에서 키가 제거된다."""
    translator = make_translator_mock()
    translator.translate_sentence = AsyncMock(side_effect=RuntimeError("번역 서버 오류"))

    manager = TranslationManager(translator)
    key = (0.5, "오류 케이스")
    manager._in_flight.add(key)

    await manager._translate_and_cache(key, "오류 케이스", "ko")

    assert key not in manager._in_flight, "예외 후에도 _in_flight에 키가 남아 있습니다"
    assert key not in manager._cache, "예외 시 캐시에 저장되면 안 됩니다"
