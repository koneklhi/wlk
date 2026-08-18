"""관리자 페이지 블록 재번역(1회성 번역) 테스트.

basic_server는 import 시 parse_args()를 실행하므로 라우트를 직접 띄우지 않고, 순수 로직인
whisperlivekit.llm_translation.oneshot을 목 translator로 검증한다(test_llm_translator.py 패턴).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from whisperlivekit.llm_translation import oneshot
from whisperlivekit.llm_translation.oneshot import (
    RetranslateError,
    close_oneshot_translator,
    get_oneshot_translator,
    retranslate_once,
)


def _config(llm_translation=True):
    return SimpleNamespace(
        llm_translation=llm_translation,
        translation_serve="ollama",
        translation_model="qwen2.5:7b",
        translation_endpoint="http://localhost:11434",
    )


@pytest.fixture(autouse=True)
def _reset_singleton():
    """모듈 레벨 싱글턴이 테스트 간에 새지 않도록 매번 비운다."""
    oneshot._translator = None
    yield
    oneshot._translator = None


def test_disabled_returns_none():
    assert get_oneshot_translator(_config(llm_translation=False)) is None


def test_singleton_created_once():
    with patch("whisperlivekit.llm_translation.oneshot.create_translator") as factory:
        factory.return_value = object()
        a = get_oneshot_translator(_config())
        b = get_oneshot_translator(_config())
    assert a is b
    factory.assert_called_once()


@pytest.mark.anyio
async def test_translates_text():
    fake = SimpleNamespace(translate_sentence=AsyncMock(return_value="Hello."))
    with patch("whisperlivekit.llm_translation.oneshot.create_translator", return_value=fake):
        result = await retranslate_once(_config(), "안녕하세요.", "ko")
    assert result == "Hello."
    # 확정 문장 경로와 같은 품질 — RAG를 켠 채 호출해야 한다.
    assert fake.translate_sentence.call_args.kwargs["use_rag"] is True


@pytest.mark.anyio
async def test_blank_text_rejected():
    with pytest.raises(RetranslateError) as e:
        await retranslate_once(_config(), "   ")
    assert e.value.status == 400


@pytest.mark.anyio
async def test_disabled_translation_rejected():
    with pytest.raises(RetranslateError) as e:
        await retranslate_once(_config(llm_translation=False), "안녕하세요.")
    assert e.value.status == 503


@pytest.mark.anyio
async def test_connect_error_maps_to_502():
    fake = SimpleNamespace(
        translate_sentence=AsyncMock(side_effect=httpx.ConnectError("refused"))
    )
    with patch("whisperlivekit.llm_translation.oneshot.create_translator", return_value=fake):
        with pytest.raises(RetranslateError) as e:
            await retranslate_once(_config(), "안녕하세요.")
    assert e.value.status == 502


@pytest.mark.anyio
async def test_timeout_maps_to_504():
    """TranslatorBase의 httpx 클라이언트는 timeout=None이라 상한을 여기서 걸어야 한다."""

    async def never(*_a, **_kw):
        await asyncio.sleep(10)

    fake = SimpleNamespace(translate_sentence=never)
    with patch("whisperlivekit.llm_translation.oneshot.create_translator", return_value=fake):
        with pytest.raises(RetranslateError) as e:
            await retranslate_once(_config(), "안녕하세요.", timeout=0.05)
    assert e.value.status == 504


@pytest.mark.anyio
async def test_echo_discard_returns_empty_string_not_error():
    """에코 2연속은 예외가 아니라 빈 문자열로 온다 — 호출측이 화면을 덮어쓰지 않게 구분해야 한다."""
    fake = SimpleNamespace(translate_sentence=AsyncMock(return_value=""))
    with patch("whisperlivekit.llm_translation.oneshot.create_translator", return_value=fake):
        result = await retranslate_once(_config(), "안녕하세요.")
    assert result == ""


@pytest.mark.anyio
async def test_close_releases_singleton():
    fake = SimpleNamespace(close=AsyncMock())
    with patch("whisperlivekit.llm_translation.oneshot.create_translator", return_value=fake):
        get_oneshot_translator(_config())
    await close_oneshot_translator()
    fake.close.assert_awaited_once()
    assert oneshot._translator is None
