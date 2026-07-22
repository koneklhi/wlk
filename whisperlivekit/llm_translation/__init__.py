from pathlib import Path

from .prompt_manager import TranslationPromptManager
from .rag_manager import TranslationRagManager

_LLM_TRANSLATION_DIR = Path(__file__).resolve().parent

# Stage 2 RAG 실물 자산 경로 — CLI 플래그가 아니라 코드에 고정한다.
# 폐쇄망 배포 PC의 기존 whisperlive는 이 자산을 src/realtime_asr/filtering/{local_qdrant_db,bge-m3}에
# 두었고, wlk는 llm_translation 콜로케이션 규약(admin_translation_glossary.json·
# user_translation_glossary.db와 같은 디렉터리)에 맞춰 아래 경로에 둔다.
#
# 두 디렉터리가 실제로 존재하면 RAG가 켜지고, 없으면(개발 PC 기본) TranslationRagManager
# 생성자가 조용히 비활성화한다 — 코드·설정 변경 없이 파일 존재 여부만으로 갈린다.
RAG_QDRANT_DB_PATH = str(_LLM_TRANSLATION_DIR / "local_qdrant_db")
RAG_EMBEDDING_MODEL_PATH = str(_LLM_TRANSLATION_DIR / "bge-m3")
RAG_COLLECTION_NAME = "official_translation"
RAG_TOP_K = 3

_prompt_manager = None
_rag_manager = None


def get_prompt_manager() -> TranslationPromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = TranslationPromptManager(
            base_json_path=str(_LLM_TRANSLATION_DIR / "admin_translation_glossary.json"),
            db_path=str(_LLM_TRANSLATION_DIR / "user_translation_glossary.db"),
        )
    return _prompt_manager


def configure_rag_manager(
    qdrant_path=None,
    embedding_model_path=None,
    collection_name=None,
    top_k=None,
) -> TranslationRagManager:
    """RAG 매니저 싱글턴을 (재)구성한다.

    운영 경로에서는 인자 없이 호출한다 — None인 인자는 위 하드코딩 상수로 채워진다.
    인자는 테스트나 자산을 다른 위치에 둔 특수 배치에서만 넘긴다. 경로가 존재하지 않으면
    TranslationRagManager 생성자가 자동으로 비활성 처리하므로 여기서 조건 분기는 없다.

    기본값을 시그니처에 직접 박지 않고 호출 시점에 모듈 전역을 읽는 이유는, 상수를
    monkeypatch한 테스트가 실제로 반영되게 하기 위해서다(기본 인자는 import 시점에 고정된다).
    """
    global _rag_manager
    _rag_manager = TranslationRagManager(
        qdrant_path=RAG_QDRANT_DB_PATH if qdrant_path is None else qdrant_path,
        embedding_model_path=(
            RAG_EMBEDDING_MODEL_PATH if embedding_model_path is None else embedding_model_path
        ),
        collection_name=RAG_COLLECTION_NAME if collection_name is None else collection_name,
        top_k=RAG_TOP_K if top_k is None else top_k,
    )
    return _rag_manager


def get_rag_manager() -> TranslationRagManager:
    """RAG 매니저 반환(최초 호출 시 하드코딩 경로로 지연 생성).

    자산 디렉터리가 없는 개발 PC에서는 비활성 인스턴스가 만들어져 RAG 블록 없이 번역이
    돌아간다. 배포 PC처럼 자산이 실제로 있으면 이 시점에 bge-m3 로드 + Qdrant 오픈이
    일어나므로, 첫 확정 문장 번역이 그 비용을 물지 않도록 core.py가 서버 기동 시 미리 부른다.
    """
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = configure_rag_manager()
    return _rag_manager
