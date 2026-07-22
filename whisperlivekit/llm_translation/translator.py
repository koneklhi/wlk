import asyncio
import logging

import httpx

from whisperlivekit.llm_translation import get_prompt_manager, get_rag_manager


def _search_rag_examples(content: str) -> str:
    """RAG 매니저 획득 + 유사 예시 검색. 워커 스레드에서 실행되는 전 구간 블로킹 함수."""
    rag_manager = get_rag_manager()
    if not rag_manager.enabled:
        return ""
    return rag_manager.search_similar(content)

logger = logging.getLogger(__name__)


class TranslatorBase:
    def __init__(self, model_name: str, endpoint: str):
        self.model_name = model_name
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=None)

    async def connect(self) -> None:
        """httpx 세션은 생성자에서 이미 준비됨 — 명시적 호출 불필요."""
        pass

    async def close(self) -> None:
        """httpx 클라이언트 세션 종료."""
        if not self.client.is_closed:
            await self.client.aclose()

    @staticmethod
    def get_to_lang(language: str) -> str:
        return "ko" if language == "en" else "en"

    @staticmethod
    def convert_lang_formal(language: str) -> str:
        return "Korean" if language == "ko" else "English"

    def get_static_system_text(self, from_lang: str, to_lang: str) -> str:
        return f"""You are a military professional translator.
            Rules:
            1. Always translate the given {from_lang} content into natural, fluent, polite, and formal {to_lang}.
            2. Even if the input is incomplete, ambiguous, or contains typos, you must still produce a translation.
            3. Do not apologize, refuse, or output explanations. Never contain special token.
            4. Output only the final translated {to_lang}!!
            5. Use polite endings (e.g., -습니다, -ㅂ니다 for Korean).
            6. If start word of sentence is \"다음\", its means \"Next slide,\"
            7. when the context refers to Republic of Korea, convert similar-sounding words(rock, lock, rog, etc,) to Rok.
            8. \"sir\" is only a politeness marker. Ignore it and do not translate it.
            """

    @staticmethod
    def get_glossary_rules_text(to_lang: str) -> str:
        return (
            "9. GLOSSARY PRIORITY: Strictly follow the provided GLOSSARY for technical military terms to ensure consistency.\n"
            f"10. Contextual Translation: While following the glossary, ensure the overall sentence structure is grammatically correct in {to_lang}."
        )

    async def build_system_blocks(
        self, from_lang: str, to_lang: str, content: str, use_rag: bool = False
    ) -> list:
        """정적 프롬프트 + (매칭 시) glossary 블록 + (존재 시) sentence 예시 블록 +
        (use_rag이고 활성 시) Qdrant RAG 유사 예시 블록을 조립.

        use_rag는 **문장이 확정된 번역 경로에서만** True다(TranslationManager._translate_and_cache).
        미확정 버퍼 번역은 버퍼가 갱신될 때마다 재호출되므로, 여기에 RAG를 태우면 초당 수 회의
        bge-m3 인코딩 + Qdrant 검색이 돌아 실시간성이 무너진다. 기본값을 False로 두어
        새 호출자가 플래그를 빠뜨려도 RAG가 미확정 경로로 새지 않게 한다(fail-safe).
        """
        blocks = [self.get_static_system_text(from_lang, to_lang)]

        prompt_manager = get_prompt_manager()
        glossary_part = prompt_manager.get_relevant_glossary(content)
        if glossary_part:
            blocks.append(self.get_glossary_rules_text(to_lang))
            blocks.append(glossary_part)

        sentence_part = prompt_manager.get_sentence_block()
        if sentence_part:
            blocks.append(sentence_part)

        if use_rag:
            # 매니저 획득까지 통째로 to_thread에 넣는다. get_rag_manager()는 최초 호출 시
            # bge-m3 로드(수 초)를 유발할 수 있는데, core.py 워밍업을 타지 못한 경우
            # (엔진 싱글턴이 이미 초기화된 뒤 등) 그 로드가 이벤트루프 위에서 벌어져
            # 모든 세션의 오디오 수신이 멈춘다. 인코딩+검색 자체도 블로킹 CPU 호출이다
            # (원본 whisperlive_code/translator.py 124줄과 동일한 to_thread 처리).
            rag_part = await asyncio.to_thread(_search_rag_examples, content)
            if rag_part:
                blocks.append(rag_part)

        return blocks

    def build_prompt(self, content: str, system_blocks: list) -> str:
        """system_blocks 리스트를 받아서 최종 프롬프트 문자열 생성"""
        full_system_content = "\n\n".join(system_blocks)
        analysis_instruction = f"We need to translate the following sentence into formal. using military terminology. Sentence: \"{content}\""

        return f"""<|start|>system<|message|>
        {full_system_content}<|end|>
        <|start|>user<|message|>
        {content}<|end|>
        <|start|>assistant<|channel|>analysis<|message|>
        {analysis_instruction}<|end|>
        <|start|>assistant<|channel|>final<|message|>
        """

    def _log_failure(self, serve: str, exc: Exception) -> None:
        """번역 실패를 진단 가능한 형태로 남긴다.

        번역 결과는 실패해도 빈 문자열로 삼켜야 한다(전사까지 멈출 수는 없다). 그런데 로그마저
        없으면 서버 미기동·모델명 오타·404 가 전부 "번역이 안 나온다" 하나로 보인다. 폐쇄망
        배포 PC 에는 디버거가 없으므로 이 로그가 유일한 진단 수단이다.

        스택 트레이스는 남기지 않는다 — 문장마다 실패하면 로그가 그것만으로 가득 찬다.
        """
        logger.warning(
            "[Translation] %s 번역 실패 — endpoint=%s model=%s reason=%s: %s",
            serve,
            self.endpoint,
            self.model_name,
            type(exc).__name__,
            exc,
        )

    async def translate_sentence(self, content: str, src_lang: str, use_rag: bool = False) -> str:
        raise NotImplementedError


class LlamaTranslator(TranslatorBase):
    """prod 환경용 — llama.cpp/vLLM completions API"""

    async def translate_sentence(self, content: str, src_lang: str, use_rag: bool = False) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = await self.build_system_blocks(from_lang, to_lang, content, use_rag=use_rag)
        prompt = self.build_prompt(content, system_blocks)
        return await self._call_completions(prompt)

    async def _call_completions(self, prompt: str) -> str:
        try:
            response = await self.client.post(
                f"{self.endpoint}/v1/completions",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "use_beam_search": False,
                    "n": 1,
                    "temperature": 0,
                    "max_tokens": 1024,
                    "top_p": 1,
                    "top_k": 0,
                    "repeat_penalty": 1,
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["text"]
            if "<" in text:
                text = text[: text.find("<")]
            text = text.strip().strip('"').strip("'")
            return text
        except Exception as e:
            self._log_failure("llama", e)
            return ""


class OllamaTranslator(TranslatorBase):
    """dev 환경용 — Ollama chat completions API (harmony 태그 미지원)"""

    async def translate_sentence(self, content: str, src_lang: str, use_rag: bool = False) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = await self.build_system_blocks(from_lang, to_lang, content, use_rag=use_rag)
        system_text = "\n\n".join(system_blocks)
        return await self._call_chat(system_text, content)

    async def _call_chat(self, system_text: str, content: str) -> str:
        try:
            response = await self.client.post(
                f"{self.endpoint}/v1/chat/completions",
                json={
                    "model": self.model_name,
                    "messages": [
                        {"role": "system", "content": system_text},
                        {"role": "user", "content": content},
                    ],
                    "temperature": 0,
                    "max_tokens": 1024,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            self._log_failure("ollama", e)
            return ""


def create_translator(serve: str, model_name: str, endpoint: str) -> TranslatorBase:
    if serve == "ollama":
        return OllamaTranslator(model_name, endpoint)
    elif serve == "llama":
        return LlamaTranslator(model_name, endpoint)
    else:
        raise ValueError(f"Unknown serve type: {serve!r}. Use 'ollama' or 'llama'.")
