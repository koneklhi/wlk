import asyncio
import logging
import re

import httpx

from whisperlivekit.llm_translation import get_prompt_manager, get_rag_manager


def _search_rag_examples(content: str) -> str:
    """RAG 매니저 획득 + 유사 예시 검색. 워커 스레드에서 실행되는 전 구간 블로킹 함수."""
    rag_manager = get_rag_manager()
    if not rag_manager.enabled:
        return ""
    return rag_manager.search_similar(content)

logger = logging.getLogger(__name__)


_HANGUL_RE = re.compile(r"[가-힣]")
_LATIN_RE = re.compile(r"[A-Za-z]")

_MAX_RESULT_CHARS = 500  # 개행 없는 한 줄 출력의 절대 상한. 실시간 자막 한 문장이 이보다 길면
                         # runaway로 보고 절단한다(빈 문자열 폐기가 아니라 절단 — 폐기하면
                         # 확정 경로에서 캐시에 안 남아 temperature=0 가비지가 매 tick 재번역되는
                         # 무한 재시도가 된다).


def _infer_script_lang(text: str) -> str | None:
    """텍스트의 문자 구성(한글/영문 비율)으로 실제 언어를 추정. 판단 불가하면 None을 반환."""
    hangul = len(_HANGUL_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    total = hangul + latin
    if total < 6:  # 표본 부족(고유명사·약어 등) — 판단 보류, detected_language 신뢰
        return None
    if hangul / total >= 0.85:
        return "ko"
    if latin / total >= 0.85:
        return "en"
    return None


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
        analysis_instruction = "We need to translate the following sentence into formal."

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

    def resolve_src_lang(self, content: str, detected_language: str) -> str:
        """STT detected_language 오검출로 인한 번역 방향 반전(동일 언어 통과)을 방지.

        content의 실제 문자 구성이 detected_language와 크게 어긋나면(=detected_language가
        틀렸을 가능성 높음) 문자 구성 쪽을 신뢰해 방향을 보정한다. 배포 실측에서 한국어
        발화가 detected_language='en'으로 오검출되어 "한국어가 번역 없이 그대로 통과"되는
        현상이 관찰됨.
        """
        inferred = _infer_script_lang(content)
        if inferred and inferred != detected_language:
            logger.warning(
                "[Translation] detected_language=%s 이지만 문자구성 추정=%s — 번역 방향을 %s 기준으로 보정 (content=%r)",
                detected_language, inferred, inferred, content[:50],
            )
            return inferred
        return detected_language

    def _sanitize_result(self, text: str) -> str:
        """LLM 출력 폭주(환각) 가드. 정상 출력은 개행 없는 한 문장이다.

        핵심 방어는 개행 제거다(관찰 증상 '6~7줄 폭주' = 개행 다수). 개행이 섞이면 다중 문장
        환각 신호로 보고 첫 번째 비어있지 않은 줄만 취한다. 길이는 개행 없는 한 줄 runaway를 위한
        절대 상한으로만 절단한다 — **빈 문자열로 폐기하지 않는다**. 폐기하면 확정 경로에서 캐시에
        안 남아(_translate_and_cache의 `if result:`) 같은 입력이 매 tick 재번역·재폐기되는 무한
        재시도가 된다(temperature=0이라 결과가 늘 같음). 잘라서라도 non-empty로 돌려주면 캐시에
        정착해 재시도가 끝난다.
        """
        if "\n" in text:
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            text = lines[0] if lines else ""
        if len(text) > _MAX_RESULT_CHARS:
            logger.warning("[Translation] 초장문 출력 절단 (result=%d자 > %d)", len(text), _MAX_RESULT_CHARS)
            text = text[:_MAX_RESULT_CHARS].rstrip()
        return text

    async def translate_sentence(self, content: str, src_lang: str, use_rag: bool = False) -> str:
        raise NotImplementedError


class LlamaTranslator(TranslatorBase):
    """prod 환경용 — llama.cpp/vLLM completions API"""

    async def translate_sentence(self, content: str, src_lang: str, use_rag: bool = False) -> str:
        src_lang = self.resolve_src_lang(content, src_lang)
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
            text = self._sanitize_result(text)
            return text
        except Exception as e:
            self._log_failure("llama", e)
            return ""


class OllamaTranslator(TranslatorBase):
    """dev 환경용 — Ollama chat completions API (harmony 태그 미지원)"""

    async def translate_sentence(self, content: str, src_lang: str, use_rag: bool = False) -> str:
        src_lang = self.resolve_src_lang(content, src_lang)
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
            text = data["choices"][0]["message"]["content"].strip()
            text = self._sanitize_result(text)
            return text
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
