from pathlib import Path

from .prompt_manager import TranslationPromptManager

_LLM_TRANSLATION_DIR = Path(__file__).resolve().parent

_prompt_manager = None


def get_prompt_manager() -> TranslationPromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = TranslationPromptManager(
            base_json_path=str(_LLM_TRANSLATION_DIR / "admin_translation_glossary.json"),
            db_path=str(_LLM_TRANSLATION_DIR / "user_translation_glossary.db"),
        )
    return _prompt_manager
