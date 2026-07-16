# -*- coding: utf-8 -*-
"""Phase 5 /api/prompts REST 엔드포인트 테스트.

basic_server.py의 번역 Glossary 관리 API를 검증한다:
- GET /api/prompts -> 사용자 뷰 설정 반환 (glossary는 사용자분만, sentence는 전체)
- POST /api/prompts/add-item -> 항목 추가 (즉시 반영)
- POST /api/prompts/delete-item -> 항목 삭제 (즉시 반영)
"""

import json
from typing import Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from whisperlivekit.llm_translation.prompt_manager import TranslationPromptManager


def create_test_app():
    """테스트용 FastAPI 앱 생성 (parse_args 우회)."""
    from whisperlivekit.llm_translation import get_prompt_manager

    app = FastAPI()

    class PromptItemRequest(BaseModel):
        block_key: str
        origin: str
        translation: Optional[str] = None

    @app.get("/api/prompts")
    async def get_prompts():
        return get_prompt_manager().get_user_view_settings()

    @app.post("/api/prompts/add-item")
    async def add_prompt_item(request: PromptItemRequest):
        if request.block_key not in ("glossary_block", "sentence_block"):
            raise HTTPException(status_code=400, detail="Invalid block key")
        get_prompt_manager().add_item(request.block_key, request.origin, request.translation)
        return {"status": "success"}

    @app.post("/api/prompts/delete-item")
    async def delete_prompt_item(request: PromptItemRequest):
        if request.block_key not in ("glossary_block", "sentence_block"):
            raise HTTPException(status_code=400, detail="Invalid block key")
        success = get_prompt_manager().remove_item(request.block_key, request.origin)
        if success:
            return {"status": "success"}
        return {"status": "warning", "message": "Item not found or cannot delete default glossary item"}

    return app


app = create_test_app()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def isolated_prompt_manager(tmp_path):
    """각 테스트마다 새로운 격리된 TranslationPromptManager를 생성한다.

    전역 싱글톤 _prompt_manager를 재설정하고 테스트 단위로 독립적인 DB를 사용한다.
    """
    json_path = tmp_path / "admin_translation_glossary.json"
    db_path = tmp_path / "user_translation_glossary.db"
    json_path.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    manager = TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))

    import whisperlivekit.llm_translation as llm_translation_module
    original_manager = llm_translation_module._prompt_manager
    llm_translation_module._prompt_manager = manager

    yield manager

    llm_translation_module._prompt_manager = original_manager


def test_get_prompts_empty(client, isolated_prompt_manager):
    """GET /api/prompts - 빈 사용자 glossary + 기본 sentence_block 반환."""
    response = client.get("/api/prompts")
    assert response.status_code == 200
    data = response.json()
    assert data["glossary_block"] == {}
    assert "The ROK Air Force conducted joint air operations" in data["sentence_block"]


def test_post_add_glossary_item(client, isolated_prompt_manager):
    """POST /api/prompts/add-item - glossary_block 항목 추가."""
    response = client.post(
        "/api/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "해군", "translation": "ROKN"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_get_prompts_after_add_glossary(client, isolated_prompt_manager):
    """GET /api/prompts - 추가된 glossary 항목이 포함되어 반환되는지 확인."""
    client.post(
        "/api/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "해군", "translation": "ROKN"},
    )
    response = client.get("/api/prompts")
    data = response.json()
    assert data["glossary_block"] == {"해군": "ROKN"}


def test_post_add_sentence_item(client, isolated_prompt_manager):
    """POST /api/prompts/add-item - sentence_block 항목 추가."""
    response = client.post(
        "/api/prompts/add-item",
        json={"block_key": "sentence_block", "origin": "테스트 입력", "translation": "테스트 출력"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_add_item_invalid_block_key(client, isolated_prompt_manager):
    """POST /api/prompts/add-item - 잘못된 block_key는 400을 반환한다."""
    response = client.post(
        "/api/prompts/add-item",
        json={"block_key": "invalid_block", "origin": "x", "translation": "y"},
    )
    assert response.status_code == 400


def test_delete_glossary_item(client, isolated_prompt_manager):
    """POST /api/prompts/delete-item - glossary_block 항목 삭제."""
    client.post(
        "/api/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "해군", "translation": "ROKN"},
    )
    response = client.post(
        "/api/prompts/delete-item",
        json={"block_key": "glossary_block", "origin": "해군"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_delete_nonexistent_item_returns_warning(client, isolated_prompt_manager):
    """POST /api/prompts/delete-item - 존재하지 않는 항목 삭제는 warning을 반환한다."""
    response = client.post(
        "/api/prompts/delete-item",
        json={"block_key": "glossary_block", "origin": "없는용어"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "warning"


def test_delete_item_invalid_block_key(client, isolated_prompt_manager):
    """POST /api/prompts/delete-item - 잘못된 block_key는 400을 반환한다."""
    response = client.post(
        "/api/prompts/delete-item",
        json={"block_key": "invalid_block", "origin": "x"},
    )
    assert response.status_code == 400
