# -*- coding: utf-8 -*-
"""Phase 5 번역 Glossary(TranslationPromptManager) 독립 모듈 검증 테스트.

whisperlivekit/llm_translation/prompt_manager.py가 audio_processor 등 코어 없이도
독립적으로 동작하는지 확인한다. 각 테스트는 tmp_path 기반 임시 fixture를 사용해
전역 싱글턴 오염 없이 격리 실행된다.
"""

import json
from pathlib import Path

from whisperlivekit.llm_translation.prompt_manager import TranslationPromptManager


def make_prompt_manager(tmp_path: Path, glossary: dict) -> TranslationPromptManager:
    """임시 JSON + DB로 TranslationPromptManager를 생성한다."""
    json_path = tmp_path / "admin_translation_glossary.json"
    db_path = tmp_path / "user_translation_glossary.db"
    json_path.write_text(json.dumps(glossary, ensure_ascii=False), encoding="utf-8")
    return TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))


def test_load_default_glossary_from_file(tmp_path):
    """admin JSON의 기본 용어집이 정상 로드되는지 확인 (버그 수정 회귀 테스트)."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    assert mgr.defaults["glossary_block"] == {"공군": "ROKAF"}


def test_load_default_glossary_missing_file(tmp_path):
    """admin JSON 파일이 없으면 빈 딕셔너리를 반환한다."""
    db_path = tmp_path / "user_translation_glossary.db"
    mgr = TranslationPromptManager(
        base_json_path=str(tmp_path / "nonexistent.json"), db_path=str(db_path)
    )
    assert mgr.defaults["glossary_block"] == {}


def test_get_relevant_glossary_matches_origin(tmp_path):
    """입력 문장에 원문 용어가 등장하면 glossary 블록에 포함된다."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    result = mgr.get_relevant_glossary("우리 공군은 임무를 수행했다")
    assert "공군 : ROKAF" in result
    assert result.startswith("GLOSSARY(Term:Translation)")


def test_get_relevant_glossary_matches_translation_bidirectional(tmp_path):
    """번역어가 입력 문장에 등장해도(영→한 방향) glossary 블록에 포함된다."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    result = mgr.get_relevant_glossary("The ROKAF conducted a mission")
    assert "공군 : ROKAF" in result


def test_get_relevant_glossary_no_match_returns_empty(tmp_path):
    """매칭되는 용어가 없으면 빈 문자열을 반환한다 (빈 헤더 방지)."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    result = mgr.get_relevant_glossary("오늘 날씨가 좋다")
    assert result == ""


def test_add_glossary_item_persists_and_merges(tmp_path):
    """add_item으로 추가한 용어가 사용자 사전에 저장되고 get_relevant_glossary에 반영된다."""
    mgr = make_prompt_manager(tmp_path, {})
    mgr.add_item("glossary_block", "해군", "ROKN")
    assert mgr.user_settings["glossary_block"] == {"해군": "ROKN"}
    result = mgr.get_relevant_glossary("해군 함정이 이동했다")
    assert "해군 : ROKN" in result


def test_remove_glossary_item(tmp_path):
    """remove_item으로 사용자 추가 용어를 삭제할 수 있다."""
    mgr = make_prompt_manager(tmp_path, {})
    mgr.add_item("glossary_block", "해군", "ROKN")
    assert mgr.remove_item("glossary_block", "해군") is True
    assert "해군" not in mgr.user_settings["glossary_block"]


def test_remove_glossary_item_not_found(tmp_path):
    """존재하지 않는 용어 삭제는 False를 반환한다."""
    mgr = make_prompt_manager(tmp_path, {})
    assert mgr.remove_item("glossary_block", "없는용어") is False


def test_get_user_view_settings_hides_admin_glossary(tmp_path):
    """get_user_view_settings는 admin 기본 glossary는 숨기고 사용자 추가분만 노출한다."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    mgr.add_item("glossary_block", "해군", "ROKN")
    view = mgr.get_user_view_settings()
    assert view["glossary_block"] == {"해군": "ROKN"}
    assert "공군" not in view["glossary_block"]


def test_get_sentence_block_default(tmp_path):
    """sentence_block 수정 전에는 기본 예시 문장이 반환된다."""
    mgr = make_prompt_manager(tmp_path, {})
    result = mgr.get_sentence_block()
    assert result.startswith("### EXAMPLES")
    assert "The ROK Air Force conducted joint air operations" in result


def test_add_sentence_item_overrides_defaults_copy_on_write(tmp_path):
    """sentence_block에 add_item을 한 번이라도 호출하면 기본값을 복사해 사용자 버전으로 전환된다."""
    mgr = make_prompt_manager(tmp_path, {})
    mgr.add_item("sentence_block", "테스트 입력", "테스트 출력")
    assert mgr.user_settings["sentence_block"] is not None
    result = mgr.get_sentence_block()
    assert "테스트 입력" in result
    assert "The ROK Air Force conducted joint air operations" in result


def test_get_user_view_settings_sentence_shows_full(tmp_path):
    """sentence_block은 기본+사용자 전체가 노출된다 (glossary와 달리 숨기지 않음)."""
    mgr = make_prompt_manager(tmp_path, {})
    view = mgr.get_user_view_settings()
    assert "The ROK Air Force conducted joint air operations" in view["sentence_block"]


def test_settings_persist_across_manager_instances(tmp_path):
    """DB에 저장된 사용자 설정은 매니저를 새로 생성해도 로드된다."""
    json_path = tmp_path / "admin_translation_glossary.json"
    db_path = tmp_path / "user_translation_glossary.db"
    json_path.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")

    mgr1 = TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))
    mgr1.add_item("glossary_block", "공군", "ROKAF")

    mgr2 = TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))
    assert mgr2.user_settings["glossary_block"] == {"공군": "ROKAF"}
