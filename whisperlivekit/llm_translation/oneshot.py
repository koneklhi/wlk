"""세션과 무관한 1회성 번역 — 관리자 페이지의 블록 재번역용.

실시간 파이프라인의 번역은 세션마다 만들어지는 ``TranslationManager``가 담당하지만, 관리자
페이지는 진행 중 세션 객체에 접근할 수 없다(서버에 세션 레지스트리가 없고, 일시중단→재개하면
새 세션이라 화면의 블록 번호와 서버의 줄 번호가 어긋난다). 다행히 ``create_translator``는
config 값만으로 만드는 순수 팩토리라, 세션을 거치지 않고 번역 1건을 돌릴 수 있다.

그래서 이 모듈은 **세션·WebSocket·프로토콜을 전혀 건드리지 않는다**. 부수 이득으로 일시중단
이전 구간(서버가 이미 잊은 구간 — docs/API_SPEC.md §3.5가 "한계"로 명시한 사각지대)도
재번역할 수 있다.

주의: ``TranslatorBase``의 httpx 클라이언트는 ``timeout=None``이다. LLM 서버가 응답하지 않으면
요청이 영구히 매달리므로 여기서 반드시 ``asyncio.wait_for``로 상한을 건다.
"""

import asyncio
import logging
from typing import Optional

import httpx

from whisperlivekit.llm_translation.translator import TranslatorBase, create_translator

logger = logging.getLogger(__name__)

#: 1회성 번역 응답 대기 상한(초). 첫 호출은 RAG(bge-m3) 로드가 겹칠 수 있어 넉넉히 잡는다.
RETRANSLATE_TIMEOUT_S = 60.0

_translator: Optional[TranslatorBase] = None


class RetranslateError(Exception):
    """1회성 번역 실패. ``status``는 그대로 HTTP 상태코드로 쓴다."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def get_oneshot_translator(config) -> Optional[TranslatorBase]:
    """1회성 번역용 translator 싱글턴. LLM 번역이 꺼져 있으면 None.

    세션별 translator와 별개의 인스턴스다 — 세션은 연결마다 생기고 사라지는데, REST는 세션
    바깥에서 불리므로 수명을 공유할 수 없다.
    """
    global _translator
    if not getattr(config, "llm_translation", False):
        return None
    if _translator is None:
        _translator = create_translator(
            serve=config.translation_serve,
            model_name=config.translation_model,
            endpoint=config.translation_endpoint,
        )
        logger.info(
            "[Retranslate] 1회성 번역기 생성 (serve=%s model=%s endpoint=%s)",
            config.translation_serve, config.translation_model, config.translation_endpoint,
        )
    return _translator


async def close_oneshot_translator() -> None:
    """httpx 세션 정리. 서버 lifespan 종료 시 호출한다."""
    global _translator
    if _translator is not None:
        await _translator.close()
        _translator = None


async def retranslate_once(
    config,
    text: str,
    src_lang: str = "ko",
    timeout: float = RETRANSLATE_TIMEOUT_S,
) -> str:
    """텍스트 1건을 지금의 용어집으로 다시 번역한다.

    ``src_lang``이 틀려도 ``translate_sentence``가 문자 구성 기반으로 보정하므로(resolve_src_lang),
    호출측이 정확한 언어를 몰라도 된다.

    반환값이 빈 문자열이면 **실패가 아니라 에코 폐기**다(원문을 그대로 뱉는 응답을 2회 연속
    받은 경우). 호출측은 이 경우 화면 번역을 덮어쓰지 않아야 한다 — 빈칸이 되어 번역이
    사라진 것처럼 보인다.
    """
    content = (text or "").strip()
    if not content:
        raise RetranslateError(400, "번역할 텍스트가 비어 있습니다.")

    translator = get_oneshot_translator(config)
    if translator is None:
        raise RetranslateError(503, "번역 기능이 비활성화되어 있습니다.")

    try:
        # 확정 문장 경로와 같은 품질을 내려면 use_rag=True (배포 PC에만 자산이 있어 개발 PC에선 자동 비활성).
        return await asyncio.wait_for(
            translator.translate_sentence(content, src_lang, use_rag=True),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("[Retranslate] %.0f초 내 응답 없음 (text=%r)", timeout, content[:50])
        raise RetranslateError(504, "번역 서버가 응답하지 않습니다.") from None
    except httpx.ConnectError as e:
        logger.warning("[Retranslate] 번역 서버 연결 실패: %s", e)
        raise RetranslateError(502, "번역 서버에 연결할 수 없습니다.") from None
    except Exception as e:
        logger.exception("[Retranslate] 예기치 못한 실패: %s", e)
        raise RetranslateError(500, "번역 중 오류가 발생했습니다.") from None
