# -*- coding: utf-8 -*-
"""React dist base-경로 자동추출 서빙 테스트.

basic_server.py의 프론트엔드 서빙 로직을 검증한다:
- _detect_frontend_base: index.html 자산참조에서 빌드 base 추출 (순수 함수)
- 라우팅: GET / 리다이렉트 + base 하위 assets/SPA/public 서빙 (TestClient)

basic_server는 import 시 ``config = parse_args()``(argv를 읽음)와, lifespan에서
``TranscriptionEngine(config=config)``(무거운 GPU 모델 로드)를 수행한다. 실모델을 로드하지 않기 위해:
  (1) import 전 sys.argv를 더미로 세팅, (2) importlib.reload로 그 argv/dist에 맞춰 모듈을 재평가,
  (3) TranscriptionEngine을 더미로 치환, (4) TestClient를 ``with`` 없이 사용해 lifespan(모델 로드)을
  아예 트리거하지 않는다(lifespan startup은 컨텍스트 매니저 진입 시에만 실행됨).
"""
import importlib
import sys
from unittest import mock

import pytest
from fastapi.testclient import TestClient


def _load_basic_server(frontend_dir, frontend_base="auto"):
    """더미 argv/dist로 basic_server를 fresh import(reload)하고 엔진을 더미로 치환해 반환."""
    argv = ["prog", "--frontend-dir", str(frontend_dir), "--frontend-base", frontend_base]
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


@pytest.fixture
def basic_server_module():
    """_detect_frontend_base 순수 함수 테스트용 — 안전한 기본 argv로 모듈 로드."""
    return _load_basic_server("frontend/static")


# ---------------------------------------------------------------------------
# 순수 함수 단위 테스트 — _detect_frontend_base
# ---------------------------------------------------------------------------

def test_detect_base_with_prefixed_assets(basic_server_module, tmp_path):
    """base 경로(/wlkies)로 빌드된 index.html -> '/wlkies' 추출."""
    index = tmp_path / "index.html"
    index.write_text(
        '<!doctype html><html><head>'
        '<script type="module" src="/wlkies/assets/index-abc.js"></script>'
        '</head><body></body></html>',
        encoding="utf-8",
    )
    assert basic_server_module._detect_frontend_base(index) == "/wlkies"


def test_detect_base_root_build(basic_server_module, tmp_path):
    """루트(base '/') 빌드 index.html -> '' 반환."""
    index = tmp_path / "index.html"
    index.write_text('<script src="/assets/index.js"></script>', encoding="utf-8")
    assert basic_server_module._detect_frontend_base(index) == ""


def test_detect_base_no_assets(basic_server_module, tmp_path):
    """assets 참조가 없는 index.html -> '' 반환."""
    index = tmp_path / "index.html"
    index.write_text("<html><body>no assets here</body></html>", encoding="utf-8")
    assert basic_server_module._detect_frontend_base(index) == ""


def test_detect_base_missing_file(basic_server_module, tmp_path):
    """파일이 없으면 OSError -> '' 반환."""
    assert basic_server_module._detect_frontend_base(tmp_path / "nope.html") == ""


# ---------------------------------------------------------------------------
# 라우팅 테스트 — base 하위 서빙
# ---------------------------------------------------------------------------

@pytest.fixture
def base_dist(tmp_path):
    """/wlkies base로 빌드된 더미 dist 디렉토리."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<!doctype html><html><head>'
        '<script type="module" src="/wlkies/assets/app.js"></script>'
        '</head><body><div id="root">DUMMY_INDEX</div></body></html>',
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    # public 실제 파일(예: logo) — SPA fallback이 아니라 실제 파일을 서빙해야 함
    (dist / "logo.svg").write_text("<svg></svg>", encoding="utf-8")
    return dist


def test_base_routing(base_dist):
    """base(/wlkies)로 빌드된 dist의 리다이렉트/자산/SPA/public 서빙 검증."""
    bs = _load_basic_server(base_dist, frontend_base="auto")
    assert bs._frontend_base == "/wlkies"
    client = TestClient(bs.app)

    # GET / -> base로 리다이렉트
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/wlkies/"

    # base 하위 자산 -> 실제 js (HTML 아님)
    r = client.get("/wlkies/assets/app.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["content-type"].lower()
    assert "console.log(1)" in r.text

    # base 루트 -> index.html (SPA 진입점)
    r = client.get("/wlkies/")
    assert r.status_code == 200
    assert "DUMMY_INDEX" in r.text

    # base 하위 임의 SPA 경로 -> index.html fallback
    r = client.get("/wlkies/some/spa/route")
    assert r.status_code == 200
    assert "DUMMY_INDEX" in r.text

    # base 하위 실제 public 파일 -> 그 파일(index.html 아님)
    r = client.get("/wlkies/logo.svg")
    assert r.status_code == 200
    assert "<svg>" in r.text

    # health -> JSON
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_explicit_base_override(base_dist):
    """--frontend-base 명시 오버라이드가 자동추출보다 우선하고, 후행 슬래시는 정규화된다."""
    bs = _load_basic_server(base_dist, frontend_base="/custom/")
    assert bs._frontend_base == "/custom"


@pytest.fixture
def root_dist(tmp_path):
    """루트(base '/') 빌드 더미 dist — 하위호환 검증용."""
    dist = tmp_path / "rootdist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        '<script type="module" src="/assets/app.js"></script>'
        '<div id="root">ROOT_INDEX</div>',
        encoding="utf-8",
    )
    (dist / "assets" / "app.js").write_text("console.log(2)", encoding="utf-8")
    return dist


def test_root_build_backward_compat(root_dist):
    """루트 빌드 dist는 base=''로 기존과 동일하게 GET /·/assets·SPA fallback 서빙."""
    bs = _load_basic_server(root_dist, frontend_base="auto")
    assert bs._frontend_base == ""
    client = TestClient(bs.app)

    # GET / -> 리다이렉트 없이 바로 index.html
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "ROOT_INDEX" in r.text

    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log(2)" in r.text

    r = client.get("/some/spa/route")
    assert r.status_code == 200
    assert "ROOT_INDEX" in r.text
