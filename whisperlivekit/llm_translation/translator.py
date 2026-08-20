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
                         # runaway로 보고 절단한다(빈 문자열 폐기가 아니라 절단). 무한 재번역
                         # 방지 책임은 manager의 시도 상한(_MAX_FINAL_ATTEMPTS·_attempts)으로
                         # 이관됐지만, 여기서도 굳이 폐기하지 않는다 — 잘린 번역이 빈칸보다 낫다.

_SCRIPT_DOMINANCE = 0.6  # 우세 스크립트 비율이 이 미만이면 진짜 한·영 혼합(code-switching)으로 보고
                         # 번역 방향 판정을 보류(§3.2 존중). 이상이면 약어가 섞여도 우세 언어로 판정.

_PURE_LATIN_MIN = 4  # 라틴 단독을 en으로 확정하는 최소 글자수. 영어 약어(GPS·ROK)는 2~3자라 보류 유지.
                     # 한글은 스크립트가 한국어 배타적이라 1자면 ko 확정.

_HANGUL_WEIGHT = 2.8  # 한글 1자가 차지하는 발화 시간을 라틴 몇 자로 볼지. test_data 실측치
                      # (kor1~3 5.4~5.6자/초 vs eng1 15.3자/초 → 비 2.79)에서 나왔다.
                      # 문자수 게이트를 raw len으로 재면 같은 임계에 한국어가 2.8배 늦게
                      # 도달해 한→영 미리보기 번역만 뒤늦게 뜬다(배포 실측 증상).


def effective_len(text: str, hangul_weight: float = _HANGUL_WEIGHT) -> float:
    """스크립트 밀도를 보정한 '체감 길이'.

    한글은 라틴 대비 정보 밀도가 높아 같은 발화 시간에 문자가 적게 쌓인다. 길이 게이트를
    raw len으로 재면 한국어만 늦게 발동하므로, 한글 문자에 hangul_weight를 줘 '발화 시간'
    기준으로 맞춘다. 혼용문(code-switching)은 한글/라틴 비율에 따라 자연히 중간값이 된다.

    공백·구두점·숫자는 가중치 1 — 한·영 양쪽에 같은 비율로 섞이므로 보정 대상이 아니다.

    hangul_weight를 **올리면** 한국어 미리보기가 더 이른 시점(= 더 적은 한글 글자수)에 발동한다
    (`--interim-hangul-weight`). 라틴 전용 텍스트는 가중치와 무관하게 항상 raw len과 같다.
    """
    return len(text) + len(_HANGUL_RE.findall(text)) * (hangul_weight - 1.0)


def _infer_script_lang(text: str) -> str | None:
    """텍스트의 문자 구성으로 실제 언어를 추정. 판단 불가하면 None.

    순수 스크립트 fast-path: 한 스크립트만 존재하면 다수결·표본수 게이트를 건너뛰고 즉시
    확정한다 — 짧은 순수 한국어 문장("감사합니다"=한글 5자<6)이 표본 부족으로 None이 돼
    detected_language 캐리오버(en)를 못 잡던 사각지대 해소. 라틴 단독은 약어(GPS·ROK)
    오판을 피하려 _PURE_LATIN_MIN(4자) 이상만 en으로 확정한다.

    혼합문은 기존 다수결(우세 60%) 유지 — 한국어 발화에 흔한 영어 약어가 섞여도 한글이
    우세하면 ko로 판정한다. 과거 85% 임계는 약어 한둘에 None이 돼 detected_language
    오검출로 인한 동일언어 통과를 못 잡았다(개발 PC 재현 확인)."""
    hangul = len(_HANGUL_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if latin == 0 and hangul >= 1:
        return "ko"
    if hangul == 0 and latin >= _PURE_LATIN_MIN:
        return "en"
    total = hangul + latin
    if total < 6:  # 표본 부족 — 판정 보류
        return None
    if hangul == latin:
        return None
    dominant, count = ("ko", hangul) if hangul > latin else ("en", latin)
    if count / total < _SCRIPT_DOMINANCE:
        return None  # 근소차 = 진짜 혼합문 → STT 판단 존중
    return dominant


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
        self, from_lang: str, to_lang: str, content: str, use_rag: bool = False,
        strict_direction: bool = False,
    ) -> list:
        """정적 프롬프트 + (매칭 시) glossary 블록 + (존재 시) sentence 예시 블록 +
        (use_rag이고 활성 시) Qdrant RAG 유사 예시 블록을 조립.

        use_rag는 **문장이 확정된 번역 경로에서만** True다(TranslationManager._translate_and_cache).
        미확정 버퍼 번역은 버퍼가 갱신될 때마다 재호출되므로, 여기에 RAG를 태우면 초당 수 회의
        bge-m3 인코딩 + Qdrant 검색이 돌아 실시간성이 무너진다. 기본값을 False로 두어
        새 호출자가 플래그를 빠뜨려도 RAG가 미확정 경로로 새지 않게 한다(fail-safe).

        strict_direction=True(에코 감지 후 재시도 경로)면 blocks 마지막에 출력 언어 강제
        지시문을 덧붙인다 — Llama harmony·Ollama chat 양쪽이 blocks join을 쓰므로 여기
        한 곳에 두면 두 백엔드에 모두 적용된다.
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

        if strict_direction:
            blocks.append(self._direction_directive(from_lang, to_lang))

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
        절대 상한으로만 절단한다 — 빈 문자열로 폐기하지 않는다(잘린 번역이 빈칸보다 낫다).
        과거엔 '폐기하면 무한 재번역'이라 폐기가 금지였지만, 지금은 확정 경로의 무한 재시도
        방지 책임이 manager의 시도 상한(_MAX_FINAL_ATTEMPTS·_attempts — 빈 결과가 반복되면
        캐시에 ""로 정착)으로 이관돼, 빈 문자열이 나와도 무한루프는 생기지 않는다.
        """
        if "\n" in text:
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            text = lines[0] if lines else ""
        if len(text) > _MAX_RESULT_CHARS:
            logger.warning("[Translation] 초장문 출력 절단 (result=%d자 > %d)", len(text), _MAX_RESULT_CHARS)
            text = text[:_MAX_RESULT_CHARS].rstrip()
        return text

    @staticmethod
    def _is_echo(content: str, result: str) -> bool:
        """결과가 원문과 같은 언어(에코)인지. 양쪽 스크립트 판정이 모두 결정적일 때만 True —
        한쪽이라도 None(혼합문·짧은 라틴)이면 보류(위양성 방지, §3.2 혼합문 STT 존중)."""
        if not result:
            return False
        src = _infer_script_lang(content)
        out = _infer_script_lang(result)
        return src is not None and out is not None and src == out

    @staticmethod
    def _direction_directive(from_lang: str, to_lang: str) -> str:
        return (
            f"CRITICAL: The input is {from_lang}. You must write your answer ONLY in {to_lang}. "
            "Never repeat or echo the input language."
        )

    async def translate_sentence(
        self,
        content: str,
        src_lang: str,
        use_rag: bool = False,
        retry_on_echo: bool = True,
        echo_policy: str = "retry",
        strict_direction_first: bool = False,
    ) -> str:
        """번역 오케스트레이션(템플릿 메서드) — 백엔드 본체는 _translate_once가 담당.

        출력측 에코 게이트: 결과가 원문과 같은 언어면(번역 방향이 반전됐거나 LLM이 짧은 조각을
        번역하지 못하고 원문을 되돌려줌) 아래 정책에 따라 처리한다.

        echo_policy — 에코를 감지했을 때의 반응(확정 경로는 항상 "retry"):
          - "retry"  : 문자구성 기반 src 강제 + 방향 지시문으로 1회 재시도. 재시도도 에코면 실패("").
          - "discard": 재시도 없이 즉시 폐기(""). 실시간성 우선 — 과거 interim 기본값.
          - "off"    : 에코 게이트를 적용하지 않고 결과를 그대로 통과시킨다. `_is_echo` 위양성이
                       의심될 때(번역이 정상인데 폐기되는 정황) 진단·회피용.

        strict_direction_first=True면 **첫 호출부터** 방향 지시문을 붙인다. 에코가 난 뒤 재시도로
        고치는 대신 애초에 예방하는 쪽이라 LLM 왕복이 늘지 않는다 — 짧은 미확정 조각에서 에코가
        잦은 배포 실측(gpt-oss-20b)에 대응한 경로다.

        retry_on_echo는 하위호환용 별칭 — False면 echo_policy="discard"와 같다.
        """
        if not retry_on_echo and echo_policy == "retry":
            echo_policy = "discard"
        src_lang = self.resolve_src_lang(content, src_lang)
        result = await self._translate_once(
            content, src_lang, use_rag, strict_direction=strict_direction_first
        )
        if echo_policy == "off":
            return result
        if not self._is_echo(content, result):
            return result
        if echo_policy == "discard":
            logger.warning(
                "[Translation] 에코 감지(interim) — 재시도 없이 폐기 (src=%s content=%r result=%r)",
                src_lang, content[:50], result[:50],
            )
            return ""
        forced_src = _infer_script_lang(content) or src_lang
        if strict_direction_first and forced_src == src_lang:
            # 첫 호출이 이미 '방향 지시문 + 같은 src' 였다면 재시도는 **완전히 동일한 요청**이다
            # (temperature=0이라 결과도 같다). LLM 왕복만 낭비하므로 바로 실패 처리한다.
            logger.warning(
                "[Translation] 에코 감지 — 첫 호출이 이미 방향 지시문 경로라 재시도 생략 "
                "(src=%s content=%r result=%r)",
                src_lang, content[:50], result[:50],
            )
            return ""
        logger.warning(
            "[Translation] 에코 감지 — src=%s 강제 + 방향 지시문 재시도 (content=%r result=%r)",
            forced_src, content[:50], result[:50],
        )
        retry = await self._translate_once(content, forced_src, use_rag, strict_direction=True)
        if not self._is_echo(content, retry):
            return retry
        logger.warning(
            "[Translation] 재시도도 에코 — 번역 실패 처리 (content=%r retry=%r)",
            content[:50], retry[:50],
        )
        return ""

    async def _translate_once(
        self, content: str, src_lang: str, use_rag: bool = False, strict_direction: bool = False
    ) -> str:
        """백엔드별 1회 번역 호출 본체. src_lang 보정·에코 게이트는 translate_sentence가 담당."""
        raise NotImplementedError


class LlamaTranslator(TranslatorBase):
    """prod 환경용 — llama.cpp/vLLM completions API"""

    async def _translate_once(
        self, content: str, src_lang: str, use_rag: bool = False, strict_direction: bool = False
    ) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = await self.build_system_blocks(
            from_lang, to_lang, content, use_rag=use_rag, strict_direction=strict_direction
        )
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

    async def _translate_once(
        self, content: str, src_lang: str, use_rag: bool = False, strict_direction: bool = False
    ) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = await self.build_system_blocks(
            from_lang, to_lang, content, use_rag=use_rag, strict_direction=strict_direction
        )
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
