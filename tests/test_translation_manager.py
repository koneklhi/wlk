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


def make_closing_ensure_future():
    """ensure_future mock side_effect — 전달된 coroutine을 닫아 RuntimeWarning을 막는다."""
    def _side_effect(coro):
        coro.close()
        return MagicMock()
    return MagicMock(side_effect=_side_effect)


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
    # 미확정 경로이므로 use_rag=False 로 호출돼야 한다(RAG는 확정 전용).
    # 에코 정책은 CLI 노브라 값을 못박지 않는다 — 기본값 변경이 이 테스트를 깨뜨려선 안 된다.
    translator.translate_sentence.assert_called_once()
    assert translator.translate_sentence.call_args.kwargs["use_rag"] is False


# ─── 확정 경로 실패 시도 상한 (_attempts / _note_failure) ─────────────────────

@pytest.mark.anyio
async def test_empty_result_once_counts_attempt_without_caching():
    """빈 결과(에코 2연속 폐기 등) 1회 → 캐시에 안 남고 attempts=1, in_flight 해제."""
    translator = make_translator_mock(return_value="")
    manager = TranslationManager(translator)
    key = (1.0, "감사합니다")
    manager._in_flight.add(key)

    await manager._translate_and_cache(key, "감사합니다", "en")

    assert key not in manager._cache, "1회 실패는 아직 캐시에 정착되면 안 된다"
    assert manager._attempts[key] == 1
    assert key not in manager._in_flight


@pytest.mark.anyio
async def test_empty_result_twice_settles_empty_translation_in_cache():
    """빈 결과 2회(_MAX_FINAL_ATTEMPTS) → 캐시에 ""로 정착 + attempts 정리,
    이후 apply_translations는 캐시 히트로 처리(재스케줄 없음, translation="")."""
    import unittest.mock as mock_module

    translator = make_translator_mock(return_value="")
    manager = TranslationManager(translator)
    seg = make_text_seg("감사합니다", start=1.0, end=2.0, finalized=True)
    key = manager._cache_key(seg)

    for _ in range(2):
        manager._in_flight.add(key)
        await manager._translate_and_cache(key, seg.text, "en")

    assert manager._cache[key] == "", "상한 도달 시 빈 번역으로 정착돼야 한다"
    assert key not in manager._attempts, "정착 후 attempts는 정리돼야 한다"

    # 정착 후에는 캐시 히트 — 새 번역 task가 생기지 않고 translation="" 적용
    with mock_module.patch("asyncio.ensure_future") as mock_ensure:
        manager.apply_translations([seg])

    mock_ensure.assert_not_called()
    assert seg.translation == ""


@pytest.mark.anyio
async def test_exception_path_also_counts_attempts():
    """예외 경로도 시도 횟수를 센다 — 반복 예외는 상한 도달 시 ""로 정착(과거 무한 재스케줄)."""
    translator = make_translator_mock()
    translator.translate_sentence = AsyncMock(side_effect=RuntimeError("번역 서버 오류"))
    manager = TranslationManager(translator)
    key = (0.5, "오류 케이스")

    manager._in_flight.add(key)
    await manager._translate_and_cache(key, "오류 케이스", "ko")
    assert manager._attempts[key] == 1
    assert key not in manager._cache

    manager._in_flight.add(key)
    await manager._translate_and_cache(key, "오류 케이스", "ko")
    assert manager._cache[key] == ""
    assert key not in manager._attempts


@pytest.mark.anyio
async def test_success_after_failure_caches_result_and_clears_attempts():
    """1회 실패 후 성공 → 정상 결과가 캐시되고 attempts가 정리된다."""
    translator = make_translator_mock(return_value="")
    manager = TranslationManager(translator)
    key = (1.0, "다시 성공")

    manager._in_flight.add(key)
    await manager._translate_and_cache(key, "다시 성공", "ko")
    assert manager._attempts[key] == 1

    translator.translate_sentence = AsyncMock(return_value="Success again")
    manager._in_flight.add(key)
    await manager._translate_and_cache(key, "다시 성공", "ko")

    assert manager._cache[key] == "Success again"
    assert key not in manager._attempts


# ─── interim 디바운스: 시간(_INTERIM_MIN_INTERVAL_S) + 델타(_INTERIM_MIN_DELTA_CHARS) ──

def test_interim_time_debounce_holds_within_interval():
    """시간 디바운스: 텍스트가 바뀌어도 직전 발동 후 0.5s 미만이면 dispatch 안 됨,
    간격이 지나면 dispatch 된다."""
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)

    text1 = "미래의 합동작전을 준비하고 있습니다"  # 충분히 김(델타 게이트 통과)

    # t=1.0 첫 발동 (last_dispatch_ts=0.0 이므로 시간 게이트 통과)
    with mock_module.patch("asyncio.ensure_future", make_closing_ensure_future()) as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=1.0):
        manager.apply_interim_translation(text1, "ko", line_id=1.0)
    assert mock_ensure.call_count == 1, "첫 발동은 일어나야 한다"
    assert manager._interim_last_dispatch_ts == 1.0

    # 번역 왕복이 끝났다고 가정하고 in-flight 내림 (시간 게이트만 격리 검증)
    manager._interim_in_flight = False

    text2 = text1 + " 그리고 새로운 문장이 더 붙었습니다"  # 델타 >= 12 (델타 게이트는 통과)

    # t=1.3 → 1.3-1.0=0.3 < 0.5 : 시간 게이트에 걸려 보류
    with mock_module.patch("asyncio.ensure_future") as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=1.3):
        manager.apply_interim_translation(text2, "ko", line_id=1.0)
    mock_ensure.assert_not_called()

    # t=1.6 → 1.6-1.0=0.6 >= 0.5 : 간격 경과, 발동
    with mock_module.patch("asyncio.ensure_future", make_closing_ensure_future()) as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=1.6):
        manager.apply_interim_translation(text2, "ko", line_id=1.0)
    assert mock_ensure.call_count == 1
    assert manager._interim_last_dispatch_ts == 1.6


def test_interim_delta_gate_holds_small_growth():
    """델타 게이트: 직전 소스 대비 12자 미만 성장은 dispatch 안 됨, 12자 이상은 됨.
    (시간 게이트는 통과하도록 last_dispatch_ts=0.0 + 큰 monotonic 값으로 격리.)"""
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)
    # 줄 전환 리셋을 피하려 line_id 를 미리 맞추고, 이미 번역된 소스를 세팅
    manager._interim_line_id = 1.0
    manager._interim_source = "기존에 번역된 긴 소스 텍스트"

    small = manager._interim_source + "가나다"  # 델타 3자 < 12
    with mock_module.patch("asyncio.ensure_future") as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=100.0):
        manager.apply_interim_translation(small, "ko", line_id=1.0)
    mock_ensure.assert_not_called()

    big = manager._interim_source + "가나다라마바사아자차카타"  # 델타 12자 >= 12
    with mock_module.patch("asyncio.ensure_future", make_closing_ensure_future()) as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=100.0):
        manager.apply_interim_translation(big, "ko", line_id=1.0)
    assert mock_ensure.call_count == 1


def test_interim_in_flight_guard_still_blocks():
    """회귀: in-flight 가드는 그대로 유지 — 번역 중이면 새 dispatch 안 됨."""
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)
    manager._interim_line_id = 1.0
    manager._interim_in_flight = True  # 이미 번역 중

    with mock_module.patch("asyncio.ensure_future") as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=100.0):
        manager.apply_interim_translation("충분히 길고 새로운 미확정 버퍼 텍스트", "ko", line_id=1.0)
    mock_ensure.assert_not_called()


def test_interim_min_chars_gate_still_blocks_short_buffer():
    """회귀: _MIN_INTERIM_CHARS 게이트는 그대로 — 짧은 버퍼는 새 게이트 이전에 보류된다."""
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)
    manager._interim_line_id = 1.0

    with mock_module.patch("asyncio.ensure_future") as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=100.0):
        manager.apply_interim_translation("짧다", "ko", line_id=1.0)  # 2자 < 6
    mock_ensure.assert_not_called()


def test_interim_last_dispatch_ts_survives_line_transition():
    """회귀+설계: 줄(블록) 전환 리셋 시 _interim_last_dispatch_ts 는 리셋되지 않아
    전역 요청률 상한이 줄 경계를 넘어 유지된다(폭주 방지)."""
    import unittest.mock as mock_module

    translator = make_translator_mock()
    manager = TranslationManager(translator)

    # 줄 A 에서 방금 발동한 상태
    manager._interim_line_id = 1.0
    manager._interim_last_dispatch_ts = 10.0

    # 줄 B 로 전환 + 충분히 긴 버퍼. t=10.2 (< 10.5) 이면 시간 게이트에 걸려 보류돼야 한다.
    with mock_module.patch("asyncio.ensure_future") as mock_ensure, \
         mock_module.patch("time.monotonic", return_value=10.2):
        manager.apply_interim_translation("새 줄의 충분히 긴 미확정 버퍼 텍스트", "ko", line_id=2.0)
    mock_ensure.assert_not_called()
    assert manager._interim_line_id == 2.0  # 줄 전환은 반영됨
    assert manager._interim_last_dispatch_ts == 10.0  # 발동 시각은 유지됨


# ─── 녹음 중 대치어/번역용어 등록에 대한 소급 재번역 ──────────────────────────
#
# 규칙(manager.apply_translations 참조):
#   - **최초** 번역은 소급 창과 무관하게 항상 수행한다(실시간 정상 경로 무회귀).
#   - **재**번역(대치어로 텍스트가 바뀜 / 용어집 변경)은 최근 _retro_scope개로 제한한다.
#   - 새 번역이 도착하기 전까지는 직전 번역을 유지한다(빈칸 깜빡임 방지).

def _make_segs(n: int, prefix: str = "문장"):
    return [make_text_seg(f"{prefix}{i}.", start=float(i), end=float(i) + 0.5) for i in range(n)]


def _prefill_cache(manager, segs, value_fn=lambda s: f"T-{s.text}"):
    """이미 번역이 끝난 상태를 만든다(캐시 + _last_translation_by_id 채움)."""
    for seg in segs:
        manager._cache[manager._cache_key(seg)] = value_fn(seg)
    manager.apply_translations(segs)          # 캐시 히트 경로 — dispatch 없음
    assert not manager._in_flight


def test_first_translation_dispatches_even_outside_retro_window():
    """최초 번역은 소급 창 밖이어도 반드시 수행된다(정상 실시간 경로 무회귀)."""
    import unittest.mock as mock_module

    manager = TranslationManager(make_translator_mock(), retro_scope=1)
    segs = _make_segs(3)

    with mock_module.patch("asyncio.ensure_future", side_effect=make_closing_ensure_future()):
        manager.apply_translations(segs)

    assert len(manager._in_flight) == 3


def test_text_change_retranslates_only_inside_retro_window():
    """대치어로 텍스트가 바뀌어도 재번역은 최근 N개 확정 문장으로 제한된다."""
    import unittest.mock as mock_module

    manager = TranslationManager(make_translator_mock(), retro_scope=1)
    segs = _make_segs(3)
    _prefill_cache(manager, segs)

    old_first, old_last = segs[0].translation, segs[2].translation
    segs[0].text = "문장0정정."       # 창 밖 — 텍스트만 교정되고 재번역은 생략
    segs[2].text = "문장2정정."       # 창 안 — 재번역

    with mock_module.patch("asyncio.ensure_future", side_effect=make_closing_ensure_future()):
        manager.apply_translations(segs)

    assert manager._cache_key(segs[2]) in manager._in_flight
    assert manager._cache_key(segs[0]) not in manager._in_flight
    # 새 번역 도착 전까지 직전 번역을 유지한다(빈칸 깜빡임 방지)
    assert segs[0].translation == old_first
    assert segs[2].translation == old_last


def test_glossary_revision_bump_marks_recent_lines_stale():
    """번역용어 등록(revision 증가) 시 텍스트가 그대로여도 최근 N개가 재번역된다."""
    import unittest.mock as mock_module
    from types import SimpleNamespace

    import whisperlivekit.llm_translation.manager as mgr_module

    manager = TranslationManager(make_translator_mock(), retro_scope=2)
    segs = _make_segs(4)
    _prefill_cache(manager, segs)

    stub = SimpleNamespace(revision=manager._glossary_revision + 1)
    with mock_module.patch.object(mgr_module, "get_prompt_manager", lambda: stub):
        with mock_module.patch("asyncio.ensure_future", side_effect=make_closing_ensure_future()):
            manager.apply_translations(segs)

    assert len(manager._in_flight) == 2, "최근 2개만 재번역 대상이어야 한다"
    assert manager._cache_key(segs[2]) in manager._in_flight
    assert manager._cache_key(segs[3]) in manager._in_flight
    # 재번역 중에도 기존 번역이 계속 보인다
    assert all(seg.translation == f"T-{seg.text}" for seg in segs)


def test_glossary_revision_bump_is_noop_when_unchanged():
    """용어집이 그대로면 재번역이 일어나지 않는다(매 tick 폭주 방지)."""
    manager = TranslationManager(make_translator_mock(), retro_scope=5)
    segs = _make_segs(3)
    _prefill_cache(manager, segs)

    for _ in range(3):
        manager.apply_translations(segs)

    assert not manager._in_flight
    assert not manager._stale


def test_retro_scope_zero_disables_retranslation():
    """--retro-retranslate-lines 0 이면 소급 재번역을 아예 하지 않는다."""
    import unittest.mock as mock_module
    from types import SimpleNamespace

    import whisperlivekit.llm_translation.manager as mgr_module

    manager = TranslationManager(make_translator_mock(), retro_scope=0)
    segs = _make_segs(3)
    _prefill_cache(manager, segs)

    segs[2].text = "문장2정정."
    stub = SimpleNamespace(revision=manager._glossary_revision + 1)
    with mock_module.patch.object(mgr_module, "get_prompt_manager", lambda: stub):
        with mock_module.patch("asyncio.ensure_future", side_effect=make_closing_ensure_future()):
            manager.apply_translations(segs)

    assert not manager._in_flight
    assert segs[2].translation == "T-문장2.", "직전 번역은 그대로 유지된다"


@pytest.mark.anyio
async def test_final_translation_concurrency_is_capped():
    """확정 번역 동시 실행이 상한을 넘지 않는다(단일 LLM 서버 폭주 방지)."""
    import asyncio

    from whisperlivekit.llm_translation.manager import _MAX_CONCURRENT_FINAL

    seen = {"cur": 0, "max": 0}
    release = asyncio.Event()

    class GatedTranslator:
        async def translate_sentence(self, text, src_lang, use_rag=False, retry_on_echo=True):
            seen["cur"] += 1
            seen["max"] = max(seen["max"], seen["cur"])
            await release.wait()
            seen["cur"] -= 1
            return f"T-{text}"

    manager = TranslationManager(GatedTranslator(), retro_scope=50)
    segs = _make_segs(6)

    manager.apply_translations(segs)
    assert len(manager._in_flight) == 6, "6개 모두 스케줄돼야 한다(상한은 실행 동시성만 제한)"

    for _ in range(10):
        await asyncio.sleep(0)
    assert seen["max"] <= _MAX_CONCURRENT_FINAL

    release.set()
    for _ in range(500):
        if not manager._in_flight:
            break
        await asyncio.sleep(0.01)

    assert not manager._in_flight
    assert seen["max"] <= _MAX_CONCURRENT_FINAL
    assert all(manager._cache[manager._cache_key(seg)] == f"T-{seg.text}" for seg in segs)


# ─── translation_pending — 확정됐지만 번역 왕복이 안 끝난 상태 표시 ─────────────

def test_translation_pending_true_while_awaiting_first_translation():
    """번역이 아직 없는 확정 세그먼트는 pending=True — 프론트가 '번역 중…'을 유지한다."""
    import unittest.mock as mock_module

    manager = TranslationManager(make_translator_mock())
    seg = make_text_seg("안녕하세요.", start=1.0, end=2.0, finalized=True)

    with mock_module.patch("asyncio.ensure_future", make_closing_ensure_future()):
        manager.apply_translations([seg])

    assert seg.translation_pending is True
    assert seg.translation == ""


def test_translation_pending_false_on_cache_hit():
    """번역이 도착해 캐시에 있으면 pending=False."""
    manager = TranslationManager(make_translator_mock())
    seg = make_text_seg("안녕하세요.", start=1.0, end=2.0, finalized=True)
    manager._cache[manager._cache_key(seg)] = "Hello."

    manager.apply_translations([seg])

    assert seg.translation == "Hello."
    assert seg.translation_pending is False


def test_translation_pending_false_when_settled_empty():
    """재시도 상한 도달로 빈 번역이 '정착'한 줄은 pending=False.

    이게 이 플래그가 필요한 이유다 — 프론트가 `!hasTranslation` 만 보고 로더를 띄우면
    영영 도착하지 않을 번역을 기다리며 스피너가 영구히 남는다.
    """
    manager = TranslationManager(make_translator_mock())
    seg = make_text_seg("안녕하세요.", start=1.0, end=2.0, finalized=True)
    manager._cache[manager._cache_key(seg)] = ""   # _MAX_FINAL_ATTEMPTS 도달 후 정착 상태

    manager.apply_translations([seg])

    assert seg.translation == ""
    assert seg.translation_pending is False, "더 도착할 번역이 없으므로 대기 상태가 아니다"


def test_translation_pending_false_when_retro_window_gives_up():
    """소급 창 밖이라 재번역을 포기한 줄도 pending=False (기존 번역으로 정착)."""
    import unittest.mock as mock_module

    manager = TranslationManager(make_translator_mock(), retro_scope=1)
    old = make_text_seg("옛 문장.", start=1.0, end=2.0, finalized=True)
    recent = make_text_seg("최근 문장.", start=9.0, end=10.0, finalized=True)

    # old 는 과거에 번역된 적이 있고(=_last_translation_by_id), 용어집 변경으로 stale 이 된 상태.
    manager._last_translation_by_id[manager._seg_id(old)] = "Old sentence."
    manager._cache[manager._cache_key(old)] = "Old sentence."
    manager._stale.add(manager._cache_key(old))

    with mock_module.patch("asyncio.ensure_future", make_closing_ensure_future()):
        manager.apply_translations([old, recent])   # retro_scope=1 → old 는 창 밖

    assert old.translation == "Old sentence."
    assert old.translation_pending is False, "재번역을 포기했으므로 대기 상태가 아니다"


def test_translation_pending_not_emitted_when_false():
    """to_dict 는 pending=True 일 때만 필드를 방출한다(기본 상태를 전송량에 싣지 않는다)."""
    seg = make_text_seg("안녕하세요.", start=1.0, end=2.0, finalized=True)

    assert "translation_pending" not in seg.to_dict()
    seg.translation_pending = True
    assert seg.to_dict()["translation_pending"] is True
