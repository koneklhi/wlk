# -*- coding: utf-8 -*-
"""배포 React admin `/api/corrections/prompts*` alias 경로 테스트.

배포 React admin 페이지는 번역 사전(glossary/sentence) API를 CORRECTIONS_URL 기반으로
``/api/corrections/`` 접두를 붙여 호출한다. 백엔드 정본 경로는 ``/api/prompts*`` 이지만
프론트를 못 고치므로 basic_server가 alias 경로를 함께 등록한다(FastAPI stacked decorator):
  - GET  /api/corrections/prompts             → get_prompts (정본 /api/prompts)
  - POST /api/corrections/prompts/add-item    → add_prompt_item (정본 /api/prompts/add-item)
  - POST /api/corrections/prompts/delete-item → delete_prompt_item (정본 /api/prompts/delete-item)

alias 미등록 시 GET /api/corrections/prompts 는 DELETE /api/corrections/{wrong_word} 패턴에
path만 걸려 405, add/delete-item 은 매칭 라우트가 없어 404가 난다. 이 테스트는 실제
basic_server 앱을 로드해(미니 앱 재현이 아니라) alias가 실제로 등록됐는지 검증한다.

basic_server는 import 시 ``config = parse_args()``(argv를 읽음)와, lifespan에서
``TranscriptionEngine(config=config)``(무거운 GPU 모델 로드)을 수행한다. 실모델을 로드하지
않기 위해 test_frontend_base_serving.py와 동일하게: (1) import 전 sys.argv를 더미로,
(2) importlib.reload로 재평가, (3) TranscriptionEngine을 더미로 치환, (4) TestClient를
``with`` 없이 사용해 lifespan(모델 로드)을 아예 트리거하지 않는다.
"""
import importlib
import json
import sys
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from whisperlivekit.filtering.manager import WordCorrectionManager
from whisperlivekit.llm_translation.prompt_manager import TranslationPromptManager


def _load_basic_server():
    """더미 argv로 basic_server를 fresh import(reload)하고 엔진을 더미로 치환해 반환."""
    argv = ["prog", "--frontend-dir", "frontend/static"]
    with mock.patch.object(sys, "argv", argv):
        if "whisperlivekit.basic_server" in sys.modules:
            bs = importlib.reload(sys.modules["whisperlivekit.basic_server"])
        else:
            import whisperlivekit.basic_server as bs

    # lifespan이 돌더라도 실모델을 로드하지 않도록 방어적으로 치환
    # (아래 테스트는 TestClient를 with 없이 써서 lifespan 자체가 발동하지 않는다).
    def _dummy_engine(*args, **kwargs):
        return object()

    bs.TranscriptionEngine = _dummy_engine
    return bs


@pytest.fixture(scope="module")
def bs_module():
    """실제 basic_server 모듈(라우트 등록 포함)을 1회 로드."""
    return _load_basic_server()


@pytest.fixture
def client(bs_module, isolated_managers):
    """실제 basic_server 앱에 대한 TestClient (lifespan 미발동 = 모델 로드 없음)."""
    return TestClient(bs_module.app)


@pytest.fixture
def isolated_managers(tmp_path):
    """prompt/word 매니저를 tmp_path DB로 격리 — 실 DB/파일을 건드리지 않는다.

    basic_server는 get_prompt_manager()/get_word_manager()를 호출하고, 두 함수는 각
    서브모듈의 module-level 싱글톤을 call 시점에 읽으므로 여기서 싱글톤만 교체하면 된다.
    """
    import whisperlivekit.filtering as filtering_module
    import whisperlivekit.llm_translation as llm_translation_module

    # prompt manager 격리
    pm_json = tmp_path / "admin_translation_glossary.json"
    pm_db = tmp_path / "user_translation_glossary.db"
    pm_json.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    prompt_manager = TranslationPromptManager(base_json_path=str(pm_json), db_path=str(pm_db))

    # word manager 격리
    wm_json = tmp_path / "admin_replacement.json"
    wm_db = tmp_path / "user_replacement.db"
    wm_json.write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    word_manager = WordCorrectionManager(base_json_path=str(wm_json), db_path=str(wm_db))

    orig_pm = llm_translation_module._prompt_manager
    orig_wm = filtering_module._word_manager
    llm_translation_module._prompt_manager = prompt_manager
    filtering_module._word_manager = word_manager

    yield

    llm_translation_module._prompt_manager = orig_pm
    filtering_module._word_manager = orig_wm


# ---------------------------------------------------------------------------
# alias 경로 — 배포 React admin 호환
# ---------------------------------------------------------------------------

def test_get_corrections_prompts_alias_is_200_not_405(client):
    """GET /api/corrections/prompts → 200 (alias 미등록이면 405). 본문은 /api/prompts와 동일."""
    canonical = client.get("/api/prompts")
    assert canonical.status_code == 200

    alias = client.get("/api/corrections/prompts")
    # 핵심: alias 미등록 시 DELETE /api/corrections/{wrong_word} 에 path만 걸려 405가 난다.
    assert alias.status_code == 200, f"alias가 405/404가 아니어야 함(실제={alias.status_code})"
    assert alias.status_code != 405
    assert alias.json() == canonical.json()


def test_post_corrections_prompts_add_item_alias_is_200_not_404(client):
    """POST /api/corrections/prompts/add-item → 200 success (alias 미등록이면 404)."""
    resp = client.post(
        "/api/corrections/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "공군", "translation": "ROKAF"},
    )
    assert resp.status_code == 200, f"alias가 404가 아니어야 함(실제={resp.status_code})"
    assert resp.status_code != 404
    assert resp.json() == {"status": "success"}

    # 추가분이 정본 GET /api/prompts 및 alias GET에 반영되는지 확인
    view = client.get("/api/prompts").json()
    assert view["glossary_block"].get("공군") == "ROKAF"
    alias_view = client.get("/api/corrections/prompts").json()
    assert alias_view["glossary_block"].get("공군") == "ROKAF"


def test_post_corrections_prompts_delete_item_alias_is_200(client):
    """POST /api/corrections/prompts/delete-item → 200 (alias 미등록이면 404)."""
    client.post(
        "/api/corrections/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "공군", "translation": "ROKAF"},
    )
    resp = client.post(
        "/api/corrections/prompts/delete-item",
        json={"block_key": "glossary_block", "origin": "공군"},
    )
    assert resp.status_code == 200, f"alias가 404가 아니어야 함(실제={resp.status_code})"
    assert resp.status_code != 404
    assert resp.json() == {"status": "success"}

    # 삭제 반영 확인
    view = client.get("/api/prompts").json()
    assert "공군" not in view["glossary_block"]


def test_add_item_alias_invalid_block_key_returns_400(client):
    """alias도 정본과 동일 검증 로직 공유: 잘못된 block_key는 400."""
    resp = client.post(
        "/api/corrections/prompts/add-item",
        json={"block_key": "invalid_block", "origin": "x", "translation": "y"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# 회귀 — 기존 /api/corrections 단어교정 경로가 alias 추가로 깨지지 않아야 함
# ---------------------------------------------------------------------------

def test_get_corrections_list_still_works(client):
    """GET /api/corrections (단어 교정 목록) 정상 동작 유지."""
    resp = client.get("/api/corrections")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_delete_correction_word_still_works(client):
    """DELETE /api/corrections/{wrong_word} (단어 교정 삭제) 정상 동작 유지."""
    add = client.post("/api/corrections", json={"wrong_word": "6군", "correct_word": "육군"})
    assert add.status_code == 200
    assert client.get("/api/corrections").json().get("6군") == "육군"

    delete = client.delete("/api/corrections/6군")
    assert delete.status_code == 200
    assert delete.json() == {"status": "success"}
    assert "6군" not in client.get("/api/corrections").json()
