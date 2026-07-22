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


@pytest.mark.anyio
async def test_connect_is_noop():
    """connect()는 no-op — 호출해도 예외 없음."""
    t = LlamaTranslator(model_name="test-model", endpoint="http://localhost:2010")
    await t.connect()  # 예외 없어야 함
    assert not t.client.is_closed


@pytest.mark.anyio
async def test_close_terminates_client():
    """close() 후 client.is_closed == True."""
    t = OllamaTranslator(model_name="qwen2.5:7b", endpoint="http://localhost:11434")
    await t.close()
    assert t.client.is_closed


def _make_prompt_manager_mock(glossary_result: str = "", sentence_result: str = ""):
    mock_pm = MagicMock()
    mock_pm.get_relevant_glossary.return_value = glossary_result
    mock_pm.get_sentence_block.return_value = sentence_result
    return mock_pm


@pytest.mark.anyio
async def test_llama_includes_glossary_block_when_matched():
    """glossary가 매칭되면 프롬프트에 GLOSSARY 블록이 포함된다."""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("번역결과")
    mock_pm = _make_prompt_manager_mock(glossary_result="GLOSSARY(Term:Translation)\n공군 : ROKAF")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("우리 공군은", "ko")

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "GLOSSARY(Term:Translation)" in sent_prompt
    assert "공군 : ROKAF" in sent_prompt
    assert "GLOSSARY PRIORITY" in sent_prompt


@pytest.mark.anyio
async def test_llama_omits_glossary_block_when_no_match():
    """glossary 매칭이 없으면 GLOSSARY 블록이 프롬프트에 포함되지 않는다."""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("번역결과")
    mock_pm = _make_prompt_manager_mock(glossary_result="")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("오늘 날씨가 좋다", "ko")

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "GLOSSARY" not in sent_prompt


@pytest.mark.anyio
async def test_llama_always_includes_sentence_block_when_present():
    """sentence_block이 존재하면 항상 프롬프트에 포함된다."""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("번역결과")
    mock_pm = _make_prompt_manager_mock(sentence_result="### EXAMPLES\n- INPUT : x\n- OUTPUT : y")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("아무 문장", "ko")

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "### EXAMPLES" in sent_prompt


@pytest.mark.anyio
async def test_ollama_includes_glossary_in_joined_system_text():
    """OllamaTranslator: glossary 매칭 시 system 메시지에 GLOSSARY 블록이 합쳐져 포함된다."""
    translator = OllamaTranslator("qwen2.5:7b", "http://localhost:11434")
    mock_resp = _make_chat_response("번역결과")
    mock_pm = _make_prompt_manager_mock(glossary_result="GLOSSARY(Term:Translation)\n공군 : ROKAF")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("우리 공군은", "ko")

    sent_messages = mock_post.call_args.kwargs["json"]["messages"]
    system_message = next(m["content"] for m in sent_messages if m["role"] == "system")
    assert "공군 : ROKAF" in system_message


@pytest.mark.anyio
async def test_llama_logs_failure_with_endpoint_and_model(caplog):
    """실패를 조용히 삼키지 않는다 — 엔드포인트·모델명·원인이 로그에 남아야 한다.

    번역 서버 미기동·모델명 오타·404 가 전부 빈 문자열로 끝나 "번역이 안 나온다"만 보이던
    문제. 폐쇄망 배포 PC 에서는 이 로그가 유일한 진단 수단이다.
    """
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    boom = AsyncMock(side_effect=RuntimeError("connection refused"))

    with patch.object(translator.client, "post", new=boom):
        with caplog.at_level("WARNING"):
            result = await translator.translate_sentence("Hello.", "en")

    assert result == ""
    joined = "\n".join(caplog.messages)
    assert "http://localhost:2010" in joined
    assert "gpt-oss-20b" in joined
    assert "connection refused" in joined


@pytest.mark.anyio
async def test_ollama_logs_failure_with_endpoint_and_model(caplog):
    """OllamaTranslator 도 동일하게 실패 원인을 남긴다."""
    translator = OllamaTranslator("qwen2.5:7b", "http://localhost:11434")
    boom = AsyncMock(side_effect=RuntimeError("model not found"))

    with patch.object(translator.client, "post", new=boom):
        with caplog.at_level("WARNING"):
            result = await translator.translate_sentence("안녕하세요.", "ko")

    assert result == ""
    joined = "\n".join(caplog.messages)
    assert "http://localhost:11434" in joined
    assert "qwen2.5:7b" in joined
    assert "model not found" in joined


@pytest.mark.anyio
async def test_success_does_not_log_warning(caplog):
    """정상 번역은 경고를 남기지 않는다 — 로그가 노이즈가 되면 안 본다."""
    translator = OllamaTranslator("qwen2.5:7b", "http://localhost:11434")
    mock_resp = _make_chat_response("Hello.")

    with patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)):
        with caplog.at_level("WARNING"):
            result = await translator.translate_sentence("안녕하세요.", "ko")

    assert result == "Hello."
    assert [r for r in caplog.records if r.levelname == "WARNING"] == []
