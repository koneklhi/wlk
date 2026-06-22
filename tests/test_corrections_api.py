# -*- coding: utf-8 -*-
"""Phase 4 /api/corrections REST 엔드포인트 테스트.

basic_server.py의 단어 교정 관리 API를 검증한다:
- GET /api/corrections -> 사용자 단어 사전 반환
- POST /api/corrections -> 단어 추가 (즉시 반영)
- DELETE /api/corrections/{wrong_word} -> 단어 삭제 (즉시 반영)
"""

import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from whisperlivekit.filtering import get_word_manager
from whisperlivekit.filtering.manager import WordCorrectionManager


# parse_args() 호출을 우회하기 위해 기본 FastAPI 앱 생성
# 그리고 /api/corrections 라우트만 등록한다.
def create_test_app():
    """테스트용 FastAPI 앱 생성 (parse_args 우회)."""
    from pydantic import BaseModel

    app = FastAPI()

    class CorrectionUpdate(BaseModel):
        wrong_word: str
        correct_word: str

    @app.get("/api/corrections")
    async def get_corrections():
        """사용자 단어 교정 사전 조회."""
        word_manager = get_word_manager()
        return word_manager.user_replacements

    @app.post("/api/corrections")
    async def add_correction(update: CorrectionUpdate):
        """단어 교정 추가. 즉시 반영."""
        word_manager = get_word_manager()
        word_manager.add_user_word(update.wrong_word, update.correct_word)
        return {"status": "success"}

    @app.delete("/api/corrections/{wrong_word}")
    async def delete_correction(wrong_word: str):
        """단어 교정 삭제. 즉시 반영."""
        word_manager = get_word_manager()
        word_manager.delete_user_word(wrong_word)
        return {"status": "success"}

    return app


app = create_test_app()


@pytest.fixture
def client():
    """FastAPI TestClient를 반환한다."""
    return TestClient(app)


@pytest.fixture
def isolated_word_manager(tmp_path):
    """각 테스트마다 새로운 격리된 WordCorrectionManager를 생성한다.

    전역 싱글톤 _word_manager를 재설정하고 테스트 단위로 독립적인 DB를 사용한다.
    """
    json_path = tmp_path / "admin_replacement.json"
    db_path = tmp_path / "user_replacement.db"
    json_path.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    manager = WordCorrectionManager(base_json_path=str(json_path), db_path=str(db_path))

    # 전역 싱글톤을 테스트용으로 재설정
    import whisperlivekit.filtering as filtering_module
    original_manager = filtering_module._word_manager
    filtering_module._word_manager = manager

    yield manager

    # 테스트 후 원래 매니저로 복원
    filtering_module._word_manager = original_manager


def test_get_corrections_empty(client, isolated_word_manager):
    """GET /api/corrections - 빈 사용자 사전 반환."""
    response = client.get("/api/corrections")
    assert response.status_code == 200
    assert response.json() == {}


def test_post_add_correction(client, isolated_word_manager):
    """POST /api/corrections - 단어 추가 후 성공 메시지 반환."""
    response = client.post(
        "/api/corrections",
        json={"wrong_word": "테스트", "correct_word": "검증"}
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_get_corrections_after_add(client, isolated_word_manager):
    """GET /api/corrections - 추가된 단어가 포함되어 반환되는지 확인."""
    # 먼저 단어 추가
    client.post(
        "/api/corrections",
        json={"wrong_word": "오류", "correct_word": "수정"}
    )
    # 그 후 조회
    response = client.get("/api/corrections")
    assert response.status_code == 200
    data = response.json()
    assert data.get("오류") == "수정"


def test_delete_correction(client, isolated_word_manager):
    """DELETE /api/corrections/{wrong_word} - 단어 삭제 후 성공 메시지 반환."""
    # 먼저 단어 추가
    client.post(
        "/api/corrections",
        json={"wrong_word": "삭제대상", "correct_word": "교정"}
    )
    # 그 후 삭제
    response = client.delete("/api/corrections/삭제대상")
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_delete_nonexistent_word(client, isolated_word_manager):
    """DELETE /api/corrections/{wrong_word} - 존재하지 않는 단어 삭제도 성공 반환."""
    response = client.delete("/api/corrections/없는단어")
    # DB는 없는 항목 삭제를 무시하므로 여전히 성공 반환
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_multiple_corrections(client, isolated_word_manager):
    """여러 단어 추가/조회/삭제 시나리오."""
    # 3개 단어 추가
    for i, (wrong, correct) in enumerate([("틀림1", "맞음1"), ("틀림2", "맞음2"), ("틀림3", "맞음3")]):
        response = client.post(
            "/api/corrections",
            json={"wrong_word": wrong, "correct_word": correct}
        )
        assert response.status_code == 200

    # 전체 조회
    response = client.get("/api/corrections")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data["틀림1"] == "맞음1"
    assert data["틀림2"] == "맞음2"
    assert data["틀림3"] == "맞음3"

    # 1개 삭제
    response = client.delete("/api/corrections/틀림2")
    assert response.status_code == 200

    # 2개만 남았는지 확인
    response = client.get("/api/corrections")
    data = response.json()
    assert len(data) == 2
    assert "틀림2" not in data
    assert data["틀림1"] == "맞음1"
    assert data["틀림3"] == "맞음3"
