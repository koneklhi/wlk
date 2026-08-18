import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

from whisperlivekit.llm_translation import get_prompt_manager

if TYPE_CHECKING:
    from whisperlivekit.llm_translation.translator import TranslatorBase

logger = logging.getLogger(__name__)

_MIN_INTERIM_CHARS = 6  # 미확정 버퍼가 이 미만이면 문맥 부족 → 환각 위험이 커 아직 번역 요청하지 않는다.
                        # (확정 경로 apply_translations는 이 게이트와 무관 — 짧은 확정 발화 "다음"→"Next"는 정상 번역)

_MAX_FINAL_ATTEMPTS = 2  # 확정 번역 실패(에코 2연속·예외) 허용 시도 횟수. temperature=0이라 에코는
                         # 결정적 반복 — 초과 시 캐시에 ""로 정착시켜 매 tick 재번역 무한루프를
                         # 끊는다(빈칸이 오답 표시보다 낫다).

_INTERIM_MIN_INTERVAL_S = 0.5   # 직전 interim 번역 발동 후 이 간격(초) 미만이면 보류 — LLM 요청률 상한.
                                # 버퍼가 tick마다 갱신돼도 초당 발동 수를 묶어 LLM 서버 부하·확정 지연을 막는다.
_INTERIM_MIN_DELTA_CHARS = 12   # 버퍼가 직전 번역 소스 대비 이만큼 자라지 않았으면 보류 — 잔단어 성장마다
                                # ("미래의"→"미래의 합동"→"미래의 합동작전") 재번역하는 낭비를 방지한다.

RETRO_SCOPE_LINES = 20   # 소급 **재**번역 대상 = 최근 확정 문장 N개. 0이면 소급 재번역 비활성.
                         # 녹음 중 대치어/번역용어를 등록하면 과거 문장이 한꺼번에 재번역 대상이 되는데,
                         # 배포 LLM은 단일 서버라 전량을 한 번에 던지면 진행 중인 실시간 번역이 밀린다.
                         # **최초** 번역은 이 창과 무관하게 항상 수행된다(정상 경로 무변경).
_MAX_CONCURRENT_FINAL = 2  # 확정 번역 동시 실행 상한. 미확정 미리보기(interim) 경로는 이 상한 밖 —
                           # 실시간성이 우선이고, 그쪽은 자체 in-flight 가드 하나로 이미 직렬화된다.


class TranslationManager:
    """확정 세그먼트 LLM 번역 캐시 및 비차단 스케줄러."""

    def __init__(self, translator: "TranslatorBase", retro_scope: Optional[int] = None):
        self.translator = translator
        self._cache: dict[tuple, str] = {}        # (start_rounded, text) -> 번역 결과
        self._in_flight: set[tuple] = set()       # 번역 중인 키 집합
        self._attempts: dict[tuple, int] = {}     # 확정 번역 실패 시도 횟수 (키별) — 상한 도달 시 "" 정착
        # 미지정(None)이면 모듈 상수로 폴백 — CLI 미지정 시 무회귀(Phase A 인자 관례).
        self._retro_scope: int = max(0, int(RETRO_SCOPE_LINES if retro_scope is None else retro_scope))
        self._sem = asyncio.Semaphore(_MAX_CONCURRENT_FINAL)   # 확정 번역 동시 실행 상한
        self._glossary_revision: int = self._current_glossary_revision()
        self._stale: set[tuple] = set()           # 용어집 변경으로 재번역이 필요한 키. 값은 캐시에 남겨둔 채
                                                  # 재번역만 다시 태운다 — 새 번역 도착 전 빈칸 깜빡임 방지.
        self._last_translation_by_id: dict[float, str] = {}   # 세그먼트 id -> 마지막으로 화면에 나간 번역.
                                                  # 대치어로 텍스트가 바뀌어 캐시 키가 갈아엎어졌을 때
                                                  # 빈칸 대신 직전 번역을 유지하는 데 쓴다.
        self._interim_source: str = ""            # 마지막 번역 요청한 버퍼 텍스트
        self._interim_result: str = ""            # 마지막 완료된 번역 결과
        self._interim_in_flight: bool = False      # 번역 중 여부
        self._interim_line_id = None              # 현재 미확정 줄(블록) 식별자 — 전환 감지용
        self._interim_last_dispatch_ts: float = 0.0  # 마지막 interim 번역 발동 시각(monotonic) — 시간 디바운스용

    def _cache_key(self, seg) -> tuple:
        """캐시 키: (시작시간 반올림, 텍스트).

        텍스트가 키에 들어 있으므로 **단어 대치 사전 변경으로 seg.text가 바뀌면 캐시가 자동으로
        미스**가 되어 재번역된다. 반대로 번역 용어집만 바뀐 경우는 텍스트가 그대로라 영원히
        캐시 히트다 — 그쪽은 _stale(용어집 revision 감시)이 담당한다.
        """
        start = round(seg.start, 2) if seg.start is not None else 0.0
        return (start, seg.text or "")

    @staticmethod
    def _seg_id(seg):
        """세그먼트 안정 식별자(= 프론트 line.id). 텍스트가 바뀌어도 불변."""
        return round(seg.start, 3) if seg.start is not None else None

    @staticmethod
    def _current_glossary_revision() -> int:
        """용어집 세대. 조회 실패는 기능 비활성과 같게 취급한다(번역 자체를 막지 않는다)."""
        try:
            return int(get_prompt_manager().revision)
        except Exception:
            return 0

    async def _translate_and_cache(self, key: tuple, text: str, src_lang: str) -> None:
        """번역 완료 후 캐시에 저장. 에러 시 in_flight 에서 제거.

        확정 문장 경로이므로 use_rag=True — Qdrant 유사 예시가 프롬프트에 주입된다.
        재확정(finalize-grace 재오픈 등)으로 다시 불려도 캐시 키 (start, text)가 같으면
        apply_translations()에서 캐시 히트로 걸러지므로 RAG 재검색은 일어나지 않는다.

        실패(빈 결과 = 에코 2연속 폐기·예외)는 _note_failure로 키별 시도 횟수를 세고,
        _MAX_FINAL_ATTEMPTS 도달 시 캐시에 ""로 정착시켜 무한 재스케줄을 끊는다
        (과거엔 예외·빈 결과가 캐시에 안 남아 매 tick 재번역되는 무한루프였다).
        """
        try:
            async with self._sem:
                result = await self.translator.translate_sentence(text, src_lang, use_rag=True)
            if result:
                self._cache[key] = result
                self._attempts.pop(key, None)
            else:
                self._note_failure(key, text)
        except Exception as e:
            logger.warning(f"번역 실패: {e}")
            self._note_failure(key, text)
        finally:
            self._in_flight.discard(key)
            self._stale.discard(key)

    def _note_failure(self, key: tuple, text: str) -> None:
        """확정 번역 실패 1회 기록. 상한 도달 시 캐시에 ""를 정착시켜 재시도를 종료한다."""
        count = self._attempts.get(key, 0) + 1
        self._attempts[key] = count
        if count >= _MAX_FINAL_ATTEMPTS:
            self._cache[key] = ""
            self._attempts.pop(key, None)
            logger.warning(
                "[Translation] 확정 번역 %d회 연속 실패 — 빈 번역으로 정착 (text=%r)",
                count, text[:50],
            )

    def _mark_stale_on_glossary_change(self, window) -> None:
        """번역 용어집이 바뀌었으면 소급 창 안의 확정 문장을 재번역 대상으로 표시한다.

        캐시 값은 지우지 않는다 — 새 번역이 도착할 때까지 기존 번역을 계속 보여주기 위함
        (지우면 그 줄의 번역이 잠깐 빈칸이 됐다가 돌아온다).
        """
        rev = self._current_glossary_revision()
        if rev == self._glossary_revision:
            return
        self._glossary_revision = rev
        marked = 0
        for seg in window:
            key = self._cache_key(seg)
            if key in self._cache:
                self._stale.add(key)
                marked += 1
        if marked:
            logger.info(
                "[TranslationRetro] 용어집 변경 감지(rev=%d) — 최근 확정 %d개 소급 재번역 예약",
                rev, marked,
            )

    def apply_translations(self, segments) -> None:
        """확정 세그먼트에 번역을 적용 (캐시에서) 또는 비차단 번역 task를 생성.

        소급 재적용 규칙 (녹음 중 대치어/번역용어 등록 대응):
          - **최초** 번역은 항상 수행한다 — 소급 창과 무관(정상 실시간 경로 무변경).
          - **재**번역(대치어로 텍스트가 바뀌었거나 용어집이 바뀐 경우)은 최근 _retro_scope개
            확정 문장으로 제한한다. 흔한 단어를 등록하면 과거 수백 줄이 한꺼번에 재번역 대상이
            되는데, 배포 LLM은 단일 서버라 전량을 던지면 진행 중인 실시간 번역이 밀린다.
          - 새 번역이 도착하기 전까지는 직전 번역을 그대로 보여준다(빈칸 깜빡임 방지).
        """
        finals = [
            seg for seg in segments
            if not seg.is_silence() and seg.finalized and seg.text
        ]
        window = finals[-self._retro_scope:] if self._retro_scope > 0 else []
        in_window = {id(seg) for seg in window}

        self._mark_stale_on_glossary_change(window)

        for seg in finals:
            key = self._cache_key(seg)
            sid = self._seg_id(seg)
            cached = self._cache.get(key)

            if cached is not None and key not in self._stale:
                # 캐시 히트: 번역 결과 적용
                seg.translation = cached
                if sid is not None:
                    self._last_translation_by_id[sid] = cached
                continue

            # 캐시 미스(대치어로 텍스트가 바뀐 경우 포함) 또는 stale(용어집 변경).
            # 새 번역이 도착할 때까지 직전 번역을 유지해 빈칸 깜빡임을 막는다.
            previous = cached
            if previous is None and sid is not None:
                previous = self._last_translation_by_id.get(sid)
            seg.translation = previous if previous is not None else ""

            if key in self._in_flight:
                continue

            # 이 줄이 한 번이라도 번역된 적이 있으면 = 재번역 → 소급 창 안에서만 허용.
            is_retranslation = previous is not None
            if is_retranslation and id(seg) not in in_window:
                # 창 밖이다. 소급 재번역을 포기하고 기존 번역으로 정착시킨다 — stale 표시를 남겨두면
                # 이후 새 문장이 확정되며 창이 밀려도 그 줄이 영영 캐시 히트 경로로 돌아오지 못한다.
                self._stale.discard(key)
                continue

            src_lang = seg.detected_language or "ko"
            self._in_flight.add(key)
            asyncio.ensure_future(self._translate_and_cache(key, seg.text, src_lang))

    async def _translate_interim_and_store(self, text: str, src_lang: str, line_id) -> None:
        """중간(미확정) 버퍼 번역 완료 후 결과 저장. 에러 시 로그만 남기고 삼킴.

        미확정 경로이므로 use_rag=False — 버퍼는 발화 중 계속 갱신되므로 여기에 RAG를 태우면
        임베딩 인코딩 + 벡터 검색이 초당 수 회 반복돼 실시간성이 무너진다. 기본값과 같지만
        의도를 드러내기 위해 명시한다. retry_on_echo=False — 에코가 감지돼도 재시도하지 않고
        폐기한다(실시간성 우선; 버퍼는 곧 갱신·확정되므로 확정 경로 재시도가 품질을 책임진다).

        세대 가드: 번역 왕복 중 줄(블록)이 바뀌었으면 이 결과는 이전 줄 것이므로 현재 줄
        상태(_interim_result·_interim_in_flight)를 덮어쓰지 않는다(캐리오버 방지).
        """
        try:
            result = await self.translator.translate_sentence(text, src_lang, use_rag=False, retry_on_echo=False)
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
            now = time.monotonic()
            # 시간 디바운스: 직전 발동 후 최소 간격 미만이면 보류(직전 결과 유지 반환).
            if now - self._interim_last_dispatch_ts < _INTERIM_MIN_INTERVAL_S:
                return self._interim_result
            # 델타 게이트: 버퍼가 직전 번역 소스 대비 충분히 자라지 않았으면 보류.
            # (새 줄이면 _interim_source="" 라 len 차이가 곧 text 길이 → 첫 발동 실효 임계는
            #  _INTERIM_MIN_DELTA_CHARS(=12)로, 위 _MIN_INTERIM_CHARS(=6) 게이트보다 엄격하다.)
            if len(text) - len(self._interim_source) < _INTERIM_MIN_DELTA_CHARS:
                return self._interim_result
            self._interim_in_flight = True
            self._interim_source = text
            self._interim_last_dispatch_ts = now
            asyncio.ensure_future(self._translate_interim_and_store(text, src_lang, line_id))

        return self._interim_result
