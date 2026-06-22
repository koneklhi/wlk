import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from whisperlivekit.llm_translation.translator import TranslatorBase

logger = logging.getLogger(__name__)


class TranslationManager:
    """확정 세그먼트 LLM 번역 캐시 및 비차단 스케줄러."""

    def __init__(self, translator: "TranslatorBase"):
        self.translator = translator
        self._cache: dict[tuple, str] = {}        # (start_rounded, text) -> 번역 결과
        self._in_flight: set[tuple] = set()       # 번역 중인 키 집합

    def _cache_key(self, seg) -> tuple:
        """캐시 키: (시작시간 반올림, 텍스트)."""
        start = round(seg.start, 2) if seg.start is not None else 0.0
        return (start, seg.text or "")

    async def _translate_and_cache(self, key: tuple, text: str, src_lang: str) -> None:
        """번역 완료 후 캐시에 저장. 에러 시 in_flight 에서 제거."""
        try:
            result = await self.translator.translate_sentence(text, src_lang)
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
