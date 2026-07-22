import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whisperlivekit.llm_translation.translator import TranslatorBase

logger = logging.getLogger(__name__)

_MIN_INTERIM_CHARS = 6  # 미확정 버퍼가 이 미만이면 문맥 부족 → 환각 위험이 커 아직 번역 요청하지 않는다.
                        # (확정 경로 apply_translations는 이 게이트와 무관 — 짧은 확정 발화 "다음"→"Next"는 정상 번역)


class TranslationManager:
    """확정 세그먼트 LLM 번역 캐시 및 비차단 스케줄러."""

    def __init__(self, translator: "TranslatorBase"):
        self.translator = translator
        self._cache: dict[tuple, str] = {}        # (start_rounded, text) -> 번역 결과
        self._in_flight: set[tuple] = set()       # 번역 중인 키 집합
        self._interim_source: str = ""            # 마지막 번역 요청한 버퍼 텍스트
        self._interim_result: str = ""            # 마지막 완료된 번역 결과
        self._interim_in_flight: bool = False      # 번역 중 여부
        self._interim_line_id = None              # 현재 미확정 줄(블록) 식별자 — 전환 감지용

    def _cache_key(self, seg) -> tuple:
        """캐시 키: (시작시간 반올림, 텍스트)."""
        start = round(seg.start, 2) if seg.start is not None else 0.0
        return (start, seg.text or "")

    async def _translate_and_cache(self, key: tuple, text: str, src_lang: str) -> None:
        """번역 완료 후 캐시에 저장. 에러 시 in_flight 에서 제거.

        확정 문장 경로이므로 use_rag=True — Qdrant 유사 예시가 프롬프트에 주입된다.
        재확정(finalize-grace 재오픈 등)으로 다시 불려도 캐시 키 (start, text)가 같으면
        apply_translations()에서 캐시 히트로 걸러지므로 RAG 재검색은 일어나지 않는다.
        """
        try:
            result = await self.translator.translate_sentence(text, src_lang, use_rag=True)
            if result:
                self._cache[key] = result
        except Exception as e:
            logger.warning(f"번역 실패: {e}")
        finally:
            self._in_flight.discard(key)

    def apply_translations(self, segments) -> None:
        """확정 세그먼트에 번역을 적용 (캐시에서) 또는 비차단 번역 task를 생성."""
        for seg in segments:
            if seg.is_silence() or not seg.finalized or not seg.text:
                continue

            key = self._cache_key(seg)

            if key in self._cache:
                # 캐시 히트: 번역 결과 적용
                seg.translation = self._cache[key]
            elif key not in self._in_flight:
                # 캐시 미스 + 번역 중 아님: 비차단 task 생성
                src_lang = seg.detected_language or "ko"
                self._in_flight.add(key)
                asyncio.ensure_future(self._translate_and_cache(key, seg.text, src_lang))

    async def _translate_interim_and_store(self, text: str, src_lang: str, line_id) -> None:
        """중간(미확정) 버퍼 번역 완료 후 결과 저장. 에러 시 로그만 남기고 삼킴.

        미확정 경로이므로 use_rag=False — 버퍼는 발화 중 계속 갱신되므로 여기에 RAG를 태우면
        임베딩 인코딩 + 벡터 검색이 초당 수 회 반복돼 실시간성이 무너진다. 기본값과 같지만
        의도를 드러내기 위해 명시한다.

        세대 가드: 번역 왕복 중 줄(블록)이 바뀌었으면 이 결과는 이전 줄 것이므로 현재 줄
        상태(_interim_result·_interim_in_flight)를 덮어쓰지 않는다(캐리오버 방지).
        """
        try:
            result = await self.translator.translate_sentence(text, src_lang, use_rag=False)
            # 번역 왕복 중 줄(블록)이 바뀌었으면 이전 줄 결과이므로 버린다(캐리오버 방지).
            if result and line_id == self._interim_line_id:
                self._interim_result = result
        except Exception as e:
            logger.warning(f"중간 번역 실패: {e}")
        finally:
            # 세대 가드: 이미 새 줄로 넘어갔으면 새 줄의 in_flight 상태를 건드리지 않는다.
            if line_id == self._interim_line_id:
                self._interim_in_flight = False

    def apply_interim_translation(self, text: str, src_lang: str, line_id=None) -> str:
        """미확정 버퍼 텍스트를 번역해 최신 결과를 반환 (self-throttle: in-flight 가드 하나뿐).

        확정 번역용 _cache/_in_flight와는 완전히 독립된 상태.

        line_id는 현재 미확정 줄(블록)의 식별자다. 식별자가 바뀌면 새 줄로 넘어간 것이므로
        이전 줄의 미리보기 번역(_interim_result)을 즉시 버려 캐리오버를 막는다.
        """
        if not text:
            # 문장 확정으로 버퍼가 막 비워진 경우 — 내부 상태 리셋
            self._interim_source = ""
            self._interim_result = ""
            self._interim_in_flight = False
            self._interim_line_id = None
            return ""

        # 미확정 줄(블록) 전환 감지 — 식별자가 바뀌면 이전 줄의 미리보기 번역을 즉시 버린다.
        # buffer_translation은 프론트에서 항상 '마지막(현재 미확정) 행'에 붙으므로(transcriptRows.ts),
        # 이 리셋이 없으면 새 줄 초반에 이전 줄 번역이 잠깐 보이는 캐리오버가 생긴다.
        if line_id != self._interim_line_id:
            self._interim_line_id = line_id
            self._interim_source = ""
            self._interim_result = ""
            self._interim_in_flight = False

        # 미확정 버퍼가 너무 짧으면(문맥 부족) 아직 번역 요청하지 않는다 — 짧은 조각을 LLM이
        # 문장으로 상상해 늘어놓는(멀티라인) 폭주를 예방. 직전 결과를 그대로 유지해 반환한다.
        # 이 게이트는 미확정 미리보기 경로 전용이며, 확정 경로(apply_translations)는 무관하다
        # ("다음"(2글자) 같은 짧은 확정 발화도 apply_translations에서 정상 번역돼야 하므로).
        if len(text.strip()) < _MIN_INTERIM_CHARS:
            return self._interim_result

        if not self._interim_in_flight and text != self._interim_source:
            self._interim_in_flight = True
            self._interim_source = text
            asyncio.ensure_future(self._translate_interim_and_store(text, src_lang, line_id))

        return self._interim_result
