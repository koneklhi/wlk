# -*- coding: utf-8 -*-
"""Stage 2 번역 RAG(TranslationRagManager) 독립 모듈 검증 테스트.

qdrant-client/sentence-transformers는 폐쇄망 배포 PC 전용 실물 의존성으로, dev .venv에는
설치돼 있지 않다는 전제로 작성한다(미설치 시 조용히 비활성화되는 경로를 실제로 태운다).
로드 성공 + 검색 파싱 검증은 sys.modules에 가짜 qdrant_client/sentence_transformers
모듈을 주입해 확인한다.
"""

import asyncio
import sys
import types
from unittest.mock import patch

import pytest

import whisperlivekit.llm_translation as llm_translation_module
from whisperlivekit.llm_translation import configure_rag_manager, get_rag_manager
from whisperlivekit.llm_translation.rag_manager import TranslationRagManager


@pytest.fixture(autouse=True)
def _reset_rag_singleton():
    """테스트 간 전역 싱글턴(_rag_manager) 오염 방지."""
    original = llm_translation_module._rag_manager
    llm_translation_module._rag_manager = None
    yield
    llm_translation_module._rag_manager = original


class _FakeHit:
    def __init__(self, payload):
        self.payload = payload


class _FakeEncodeResult:
    def tolist(self):
        return [0.1, 0.2, 0.3]


def _make_fake_sentence_transformers_module():
    class FakeSentenceTransformer:
        def __init__(self, model_path):
            self.model_path = model_path

        def encode(self, text):
            return _FakeEncodeResult()

    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeSentenceTransformer
    return module


def _make_fake_qdrant_client_module(hits):
    class FakeQdrantClient:
        def __init__(self, path=None):
            self.path = path

        def search(self, collection_name, query_vector, limit):
            return hits

    module = types.ModuleType("qdrant_client")
    module.QdrantClient = FakeQdrantClient
    return module


# ----------------------------------------------------------------------
# 1. 경로 미지정 -> 비활성, 예외 없음
# ----------------------------------------------------------------------
def test_disabled_when_paths_none():
    mgr = TranslationRagManager(None, None)
    assert mgr.enabled is False
    assert mgr.search_similar("hi") == ""


# ----------------------------------------------------------------------
# 2. 경로가 실제로 존재하지 않음 -> 비활성, 예외 없음
# ----------------------------------------------------------------------
def test_disabled_when_paths_do_not_exist(tmp_path):
    qdrant_path = str(tmp_path / "nonexistent_qdrant_db")
    embedding_path = str(tmp_path / "nonexistent_bge_m3")

    mgr = TranslationRagManager(qdrant_path, embedding_path)

    assert mgr.enabled is False
    assert mgr.search_similar("hi") == ""


# ----------------------------------------------------------------------
# 3. 경로는 존재하지만 실물 패키지가 없음(dev .venv 전제) -> ImportError를 잡아 비활성화
# ----------------------------------------------------------------------
def test_disabled_when_packages_unavailable(tmp_path):
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    # dev .venv에 qdrant_client/sentence_transformers가 설치돼 있지 않다는 전제(사전 확인 완료).
    # 실제로 설치돼 있지 않으므로 `from qdrant_client import QdrantClient`가 ImportError를 던지고,
    # rag_manager._try_load()가 이를 잡아 조용히 비활성화해야 한다(서버가 죽지 않아야 함).
    mgr = TranslationRagManager(str(qdrant_dir), str(embedding_dir))

    assert mgr.enabled is False
    assert mgr.search_similar("hi") == ""


# ----------------------------------------------------------------------
# 4. 로드 성공(가짜 모듈 주입) + 검색 결과 파싱 검증 — 중첩(metadata) / flat payload 둘 다
# ----------------------------------------------------------------------
def test_search_similar_parses_nested_metadata_payload(tmp_path):
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    hits = [_FakeHit({"metadata": {"source": "foo", "target": "바"}})]
    fake_qdrant_module = _make_fake_qdrant_client_module(hits)
    fake_st_module = _make_fake_sentence_transformers_module()

    with patch.dict(sys.modules, {"qdrant_client": fake_qdrant_module, "sentence_transformers": fake_st_module}):
        mgr = TranslationRagManager(str(qdrant_dir), str(embedding_dir))
        assert mgr.enabled is True
        result = mgr.search_similar("hello")

    assert result == "### SIMILAR EXAMPLES (RAG)\nfoo : 바"


def test_search_similar_parses_flat_payload(tmp_path):
    """langchain metadata 중첩이 아니라 flat payload(source/target 최상위)인 경우도 폴백 파싱."""
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    hits = [_FakeHit({"source": "foo2", "target": "바2"})]
    fake_qdrant_module = _make_fake_qdrant_client_module(hits)
    fake_st_module = _make_fake_sentence_transformers_module()

    with patch.dict(sys.modules, {"qdrant_client": fake_qdrant_module, "sentence_transformers": fake_st_module}):
        mgr = TranslationRagManager(str(qdrant_dir), str(embedding_dir))
        result = mgr.search_similar("hello")

    assert result == "### SIMILAR EXAMPLES (RAG)\nfoo2 : 바2"


def test_search_similar_no_hits_returns_empty(tmp_path):
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    fake_qdrant_module = _make_fake_qdrant_client_module([])
    fake_st_module = _make_fake_sentence_transformers_module()

    with patch.dict(sys.modules, {"qdrant_client": fake_qdrant_module, "sentence_transformers": fake_st_module}):
        mgr = TranslationRagManager(str(qdrant_dir), str(embedding_dir))
        result = mgr.search_similar("hello")

    assert result == ""


def test_search_similar_empty_content_returns_empty_without_calling_client(tmp_path):
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    fake_qdrant_module = _make_fake_qdrant_client_module([_FakeHit({"source": "x", "target": "y"})])
    fake_st_module = _make_fake_sentence_transformers_module()

    with patch.dict(sys.modules, {"qdrant_client": fake_qdrant_module, "sentence_transformers": fake_st_module}):
        mgr = TranslationRagManager(str(qdrant_dir), str(embedding_dir))
        assert mgr.search_similar("") == ""


# ----------------------------------------------------------------------
# 5. get_rag_manager()/configure_rag_manager() 싱글턴 팩토리 동작
# ----------------------------------------------------------------------
def test_get_rag_manager_defaults_to_disabled_instance():
    mgr = get_rag_manager()
    assert isinstance(mgr, TranslationRagManager)
    assert mgr.enabled is False


def test_configure_rag_manager_updates_singleton(tmp_path):
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    fake_qdrant_module = _make_fake_qdrant_client_module([])
    fake_st_module = _make_fake_sentence_transformers_module()

    with patch.dict(sys.modules, {"qdrant_client": fake_qdrant_module, "sentence_transformers": fake_st_module}):
        configured = configure_rag_manager(
            qdrant_path=str(qdrant_dir),
            embedding_model_path=str(embedding_dir),
            collection_name="custom_collection",
            top_k=5,
        )

    assert configured.enabled is True
    assert configured.collection_name == "custom_collection"
    assert configured.top_k == 5
    assert get_rag_manager() is configured


# ----------------------------------------------------------------------
# 6. RAG는 "문장 확정 시에만" 주입된다 (use_rag 게이트)
#
# 미확정 버퍼 번역은 발화 중 초당 수 회 재호출되므로, 거기에 RAG가 걸리면 임베딩 인코딩 +
# 벡터 검색이 그만큼 반복돼 실시간성이 무너진다. 확정 경로에만 붙는지 두 층에서 검증한다.
#   (a) TranslatorBase.build_system_blocks — use_rag 플래그가 블록 조립을 실제로 가르는가
#   (b) TranslationManager — 확정/미확정 경로가 각각 True/False로 호출하는가
# ----------------------------------------------------------------------
RAG_HEADER = "### SIMILAR EXAMPLES (RAG)"

# pytest-asyncio는 `test` extra에 있어 공유 dev .venv에는 없다(CLAUDE.md §4 uv 가드레일상
# 여기서 sync를 돌릴 수 없다). 코루틴은 asyncio.run으로 직접 구동해 플러그인 의존을 없앤다.


def _configure_enabled_rag(tmp_path):
    """가짜 모듈을 주입해 enabled=True인 RAG 싱글턴을 구성한다."""
    qdrant_dir = tmp_path / "qdrant_db"
    embedding_dir = tmp_path / "bge-m3"
    qdrant_dir.mkdir()
    embedding_dir.mkdir()

    hits = [_FakeHit({"metadata": {"source": "artillery", "target": "포병"}})]
    with patch.dict(
        sys.modules,
        {
            "qdrant_client": _make_fake_qdrant_client_module(hits),
            "sentence_transformers": _make_fake_sentence_transformers_module(),
        },
    ):
        return configure_rag_manager(qdrant_path=str(qdrant_dir), embedding_model_path=str(embedding_dir))


def test_build_system_blocks_omits_rag_when_use_rag_false(tmp_path):
    """RAG가 활성이어도 use_rag=False(미확정 경로)면 RAG 블록이 붙지 않는다."""
    from whisperlivekit.llm_translation.translator import LlamaTranslator

    assert _configure_enabled_rag(tmp_path).enabled is True
    translator = LlamaTranslator("test-model", "http://localhost:1")

    blocks = asyncio.run(
        translator.build_system_blocks("Korean", "English", "포병 지원 요청", use_rag=False)
    )

    assert not any(RAG_HEADER in b for b in blocks)


def test_build_system_blocks_includes_rag_when_use_rag_true(tmp_path):
    """확정 경로(use_rag=True)에서는 RAG 블록이 조립된다."""
    from whisperlivekit.llm_translation.translator import LlamaTranslator

    assert _configure_enabled_rag(tmp_path).enabled is True
    translator = LlamaTranslator("test-model", "http://localhost:1")

    blocks = asyncio.run(
        translator.build_system_blocks("Korean", "English", "포병 지원 요청", use_rag=True)
    )

    assert any(RAG_HEADER in b for b in blocks)
    assert any("artillery : 포병" in b for b in blocks)


def test_build_system_blocks_defaults_to_no_rag(tmp_path):
    """기본값은 False — 새 호출자가 플래그를 빠뜨려도 RAG가 미확정 경로로 새지 않는다(fail-safe)."""
    from whisperlivekit.llm_translation.translator import LlamaTranslator

    assert _configure_enabled_rag(tmp_path).enabled is True
    translator = LlamaTranslator("test-model", "http://localhost:1")

    blocks = asyncio.run(translator.build_system_blocks("Korean", "English", "포병 지원 요청"))

    assert not any(RAG_HEADER in b for b in blocks)


class _RecordingTranslator:
    """translate_sentence 호출 시 use_rag 값을 기록하는 스텁."""

    def __init__(self):
        self.calls = []

    async def translate_sentence(self, content, src_lang, use_rag=False):
        self.calls.append({"content": content, "src_lang": src_lang, "use_rag": use_rag})
        return f"translated:{content}"


def test_manager_confirmed_path_uses_rag():
    """확정 세그먼트 번역(_translate_and_cache)은 use_rag=True로 호출한다."""
    from whisperlivekit.llm_translation.manager import TranslationManager

    translator = _RecordingTranslator()
    manager = TranslationManager(translator)

    key = (1.0, "확정된 문장입니다")
    asyncio.run(manager._translate_and_cache(key, "확정된 문장입니다", "ko"))

    assert translator.calls == [{"content": "확정된 문장입니다", "src_lang": "ko", "use_rag": True}]
    assert manager._cache[key] == "translated:확정된 문장입니다"


def test_manager_interim_path_does_not_use_rag():
    """미확정 버퍼 번역(_translate_interim_and_store)은 use_rag=False로 호출한다."""
    from whisperlivekit.llm_translation.manager import TranslationManager

    translator = _RecordingTranslator()
    manager = TranslationManager(translator)

    asyncio.run(manager._translate_interim_and_store("아직 확정 안 된", "ko"))

    assert translator.calls == [{"content": "아직 확정 안 된", "src_lang": "ko", "use_rag": False}]
    assert manager._interim_result == "translated:아직 확정 안 된"
