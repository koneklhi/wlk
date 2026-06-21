import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from whisperlivekit.llm_translation.translator import (
    LlamaTranslator,
    OllamaTranslator,
    TranslatorBase,
    create_translator,
)


def _make_completions_response(text: str):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"text": text}]}
    return mock_resp


def _make_chat_response(content: str):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return mock_resp


@pytest.mark.anyio
async def test_llama_translate_sentence_calls_completions():
    """LlamaTranslator.translate_sentence → /v1/completions 호출 및 결과 파싱"""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("안녕하세요.")

    with patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        result = await translator.translate_sentence("Hello.", "en")

    assert result == "안녕하세요."
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0]
    assert "/v1/completions" in call_url


@pytest.mark.anyio
async def test_ollama_translate_sentence_calls_chat_completions():
    """OllamaTranslator.translate_sentence → /v1/chat/completions 호출 및 결과 파싱"""
    translator = OllamaTranslator("qwen2.5:7b", "http://localhost:11434")
    mock_resp = _make_chat_response("Hello.")

    with patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        result = await translator.translate_sentence("안녕하세요.", "ko")

    assert result == "Hello."
    mock_post.assert_called_once()
    call_url = mock_post.call_args[0][0]
    assert "/v1/chat/completions" in call_url


@pytest.mark.anyio
async def test_llama_strips_harmony_token():
    """LlamaTranslator: harmony 특수토큰(<) 포함 시 앞부분만 반환"""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("안녕하세요.<|end|>")

    with patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)):
        result = await translator.translate_sentence("Hello.", "en")

    assert result == "안녕하세요."
    assert "<" not in result


def test_create_translator_ollama():
    """create_translator('ollama', ...) → OllamaTranslator 인스턴스"""
    t = create_translator("ollama", "qwen2.5:7b", "http://localhost:11434")
    assert isinstance(t, OllamaTranslator)


def test_create_translator_llama():
    """create_translator('llama', ...) → LlamaTranslator 인스턴스"""
    t = create_translator("llama", "gpt-oss-20b", "http://localhost:2010")
    assert isinstance(t, LlamaTranslator)


def test_create_translator_invalid():
    """create_translator('bad', ...) → ValueError"""
    with pytest.raises(ValueError):
        create_translator("bad", "model", "http://localhost:9999")
