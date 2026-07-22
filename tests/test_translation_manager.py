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


# ─── 수정1: interim 캐리오버 (line_id 생성가드 리셋) ──────────────────────────

def test_interim_line_id_change_discards_previous_block_translation():
    """미확정 줄(블록)이 바뀌면(line_id 변경) 이전 블록 미리보기 번역이 즉시 버려진다.

    캐리오버 버그 회귀 방어 — 새 블록 초반(짧아 아직 새 번역 없음)에 이전 블록 번역이
    반환되면 프론트 마지막 행에 이전 번역이 잠깐 보인다.
    """
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)

    # 블록 A: 번역이 완료돼 결과가 남아있는 상태를 시뮬레이션
    manager._interim_line_id = 10.0
    manager._interim_result = "블록 A 번역"
    manager._interim_source = "block A source"

    # 블록 B(새 line_id)의 짧은 조각 — 길이 게이트에 걸려 새 번역은 아직 없음.
    # 캐리오버가 없다면 이전 블록 결과가 아니라 "" 를 반환해야 한다.
    short_b = "가"  # _MIN_INTERIM_CHARS 미만
    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        result = manager.apply_interim_translation(short_b, "ko", line_id=20.0)

    mock_ensure.assert_not_called()
    assert result == "", "새 블록에서 이전 블록 번역이 반환되면 안 된다(캐리오버 방지)"
    assert manager._interim_line_id == 20.0
    assert manager._interim_result == ""
    assert manager._interim_source == ""


def test_interim_same_line_id_keeps_previous_result():
    """같은 line_id면 리셋되지 않아 직전 결과를 계속 미리보기로 반환한다(정상 유지)."""
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)
    manager._interim_line_id = 10.0
    manager._interim_result = "진행 중 번역"
    manager._interim_source = "some long enough source text"

    # 같은 블록에서 짧은 조각(게이트 미달)이 와도 직전 결과 유지
    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        result = manager.apply_interim_translation("가", "ko", line_id=10.0)

    mock_ensure.assert_not_called()
    assert result == "진행 중 번역"
    assert manager._interim_result == "진행 중 번역"


@pytest.mark.anyio
async def test_translate_interim_generation_guard_ignores_stale_line():
    """_translate_interim_and_store 세대 가드: 번역 왕복 중 줄이 바뀌면(line_id 불일치)
    이전 줄의 뒤늦은 완료가 현재 줄 상태를 오염시키지 않는다.
    """
    translator = make_translator_mock(return_value="이전 줄 번역")
    manager = TranslationManager(translator)

    # 현재 줄은 이미 블록 B(line_id=20.0)로 넘어가 있고 그 상태가 세팅돼 있음
    manager._interim_line_id = 20.0
    manager._interim_result = "블록 B 번역"
    manager._interim_in_flight = True

    # 블록 A(line_id=10.0)의 뒤늦은 완료가 도착 — 현재 줄을 덮어쓰면 안 됨
    await manager._translate_interim_and_store("block A source", "en", line_id=10.0)

    assert manager._interim_result == "블록 B 번역", "이전 줄 결과가 현재 줄을 덮어쓰면 안 된다"
    assert manager._interim_in_flight is True, "이전 줄 완료가 현재 줄 in_flight를 건드리면 안 된다"


@pytest.mark.anyio
async def test_translate_interim_stores_when_line_id_matches():
    """세대 가드: line_id가 현재 줄과 일치하면 정상적으로 결과를 저장하고 in_flight를 내린다."""
    translator = make_translator_mock(return_value="현재 줄 번역")
    manager = TranslationManager(translator)
    manager._interim_line_id = 10.0
    manager._interim_in_flight = True

    await manager._translate_interim_and_store("block source", "en", line_id=10.0)

    assert manager._interim_result == "현재 줄 번역"
    assert manager._interim_in_flight is False
    # 미확정 경로이므로 use_rag=False 로 호출돼야 한다.
    translator.translate_sentence.assert_called_once_with("block source", "en", use_rag=False)
