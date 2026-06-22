import httpx


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

    async def translate_sentence(self, content: str, src_lang: str) -> str:
        raise NotImplementedError


class LlamaTranslator(TranslatorBase):
    """prod 환경용 — llama.cpp/vLLM completions API"""

    async def translate_sentence(self, content: str, src_lang: str) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = [self.get_static_system_text(from_lang, to_lang)]
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
        except Exception:
            return ""


class OllamaTranslator(TranslatorBase):
    """dev 환경용 — Ollama chat completions API (harmony 태그 미지원)"""

    async def translate_sentence(self, content: str, src_lang: str) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_text = self.get_static_system_text(from_lang, to_lang)
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
        except Exception:
            return ""


def create_translator(serve: str, model_name: str, endpoint: str) -> TranslatorBase:
    if serve == "ollama":
        return OllamaTranslator(model_name, endpoint)
    elif serve == "llama":
        return LlamaTranslator(model_name, endpoint)
    else:
        raise ValueError(f"Unknown serve type: {serve!r}. Use 'ollama' or 'llama'.")
