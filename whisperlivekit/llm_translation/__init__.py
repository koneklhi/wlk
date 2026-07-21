from pathlib import Path

from .prompt_manager import TranslationPromptManager
from .rag_manager import TranslationRagManager

_LLM_TRANSLATION_DIR = Path(__file__).resolve().parent

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
    collection_name: str = "official_translation",
    top_k: int = 3,
) -> TranslationRagManager:
    """서버 기동 시 1회 호출해 RAG 매니저를 (재)구성한다.

    경로가 None이거나 존재하지 않으면 TranslationRagManager 생성자 안에서 자동으로
    비활성 처리되므로 여기서는 조건 분기 없이 무조건 새 인스턴스를 만들어 저장한다.
    """
    global _rag_manager
    _rag_manager = TranslationRagManager(
        qdrant_path=qdrant_path,
        embedding_model_path=embedding_model_path,
        collection_name=collection_name,
        top_k=top_k,
    )
    return _rag_manager


def get_rag_manager() -> TranslationRagManager:
    """RAG 매니저 반환. configure_rag_manager()가 아직 호출되지 않았다면(예: 단위 테스트에서
    translator.py를 직접 사용하는 경우) 비활성 상태의 기본 인스턴스를 만들어 반환한다."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = TranslationRagManager(None, None)
    return _rag_manager
