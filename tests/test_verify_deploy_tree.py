"""scripts/verify_deploy_tree.py 유닛 테스트 (네트워크·서버 없음, 순수 오프라인).

`scripts/`는 패키지가 아니므로 sys.path에 추가해 임포트한다
(tests/test_backfill_lang_mismatch.py와 동일 방식).

핵심 회귀 테스트는 test_stale_detected_reproduces_translator_accident 이다 —
2026-08 배포 PC 사고(증분 반입 배치 누락으로 translator.py만 구세대로 남음)를
그대로 재현해, 이 도구가 그 사고를 실제로 잡아내는지 검증한다.
"""

import sys
import zipfile
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from verify_deploy_tree import compare_tree, main  # noqa: E402

_NEW_TRANSLATOR = b"async def translate_sentence(self, content, src_lang, use_rag=False, retry_on_echo=True):\n"
_OLD_TRANSLATOR = b"async def translate_sentence(self, content, src_lang, use_rag=False):\n"


def _make_zip(path: Path, entries: dict) -> None:
    with zipfile.ZipFile(path, "w") as z:
        for name, data in entries.items():
            z.writestr(name, data)


def _write_tree(root: Path, entries: dict) -> None:
    for name, data in entries.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def _baseline(tmp_path: Path) -> tuple:
    """zip과 트리가 완전히 일치하는 기준 상태를 만든다."""
    entries = {
        "whisperlivekit/llm_translation/translator.py": _NEW_TRANSLATOR,
        "whisperlivekit/llm_translation/manager.py": b"retry_on_echo=False\n",
        "scripts/eval.py": b"SERVER_PORT = 8900\n",
    }
    zip_path = tmp_path / "deploy_source.zip"
    root = tmp_path / "wlk"
    _make_zip(zip_path, entries)
    _write_tree(root, entries)
    return root, zip_path, entries


def test_identical_tree_is_clean(tmp_path):
    root, zip_path, _ = _baseline(tmp_path)
    result = compare_tree(root, zip_path, ["whisperlivekit/", "scripts/"])
    assert result.stale == []
    assert result.missing == []
    assert result.compared == 3
    assert result.ok is True


def test_stale_detected_reproduces_translator_accident(tmp_path):
    """배포 PC 사고 재현 — translator.py만 구세대로 남은 상태를 STALE로 잡아야 한다."""
    root, zip_path, _ = _baseline(tmp_path)
    (root / "whisperlivekit/llm_translation/translator.py").write_bytes(_OLD_TRANSLATOR)

    result = compare_tree(root, zip_path, ["whisperlivekit/", "scripts/"])

    assert result.stale == ["whisperlivekit/llm_translation/translator.py"]
    assert result.missing == []
    assert result.ok is False


def test_crlf_tree_vs_lf_zip_is_not_stale(tmp_path):
    """개발 트리는 CRLF, zip은 LF다(실측). 텍스트 파일은 정규화 후 비교해 오탐을 막는다."""
    root, zip_path, entries = _baseline(tmp_path)
    for name, data in entries.items():
        (root / name).write_bytes(data.replace(b"\n", b"\r\n"))

    result = compare_tree(root, zip_path, ["whisperlivekit/", "scripts/"])

    assert result.stale == []
    assert result.ok is True


def test_binary_file_is_compared_byte_exact(tmp_path):
    """바이너리는 정규화하지 않는다 — 줄바꿈 차이도 실제 차이다."""
    payload = b"\x00\x01\r\n\x02"
    _make_zip(tmp_path / "deploy_source.zip", {"whisperlivekit/model/blob.bin": payload})
    _write_tree(tmp_path / "wlk", {"whisperlivekit/model/blob.bin": payload.replace(b"\r\n", b"\n")})

    result = compare_tree(tmp_path / "wlk", tmp_path / "deploy_source.zip", ["whisperlivekit/"])

    assert result.stale == ["whisperlivekit/model/blob.bin"]


def test_missing_file_detected(tmp_path):
    root, zip_path, _ = _baseline(tmp_path)
    (root / "whisperlivekit/llm_translation/manager.py").unlink()

    result = compare_tree(root, zip_path, ["whisperlivekit/", "scripts/"])

    assert result.missing == ["whisperlivekit/llm_translation/manager.py"]
    assert result.ok is False


def test_extra_file_is_informational_only(tmp_path):
    """PC에만 있는 파일(RAG 자산·모델 가중치·user DB)은 EXTRA로 보고하되 실패로 치지 않는다."""
    root, zip_path, _ = _baseline(tmp_path)
    _write_tree(root, {"whisperlivekit/llm_translation/user_translation_glossary.db": b"sqlite"})

    result = compare_tree(root, zip_path, ["whisperlivekit/", "scripts/"])

    assert result.extra == ["whisperlivekit/llm_translation/user_translation_glossary.db"]
    assert result.stale == []
    assert result.ok is True


def test_pycache_excluded_from_extra(tmp_path):
    """__pycache__는 항상 EXTRA라 목록을 덮어버린다 — 제외한다."""
    root, zip_path, _ = _baseline(tmp_path)
    _write_tree(root, {"whisperlivekit/__pycache__/core.cpython-312.pyc": b"\x00"})

    result = compare_tree(root, zip_path, ["whisperlivekit/", "scripts/"])

    assert result.extra == []


def test_paths_outside_prefixes_are_ignored(tmp_path):
    """점검 대상은 배포 PC가 소스에서 직접 로드하는 트리뿐이다."""
    root, zip_path, _ = _baseline(tmp_path)
    _write_tree(root, {"docs/DEPLOYMENT_OFFLINE.md": b"stale docs are harmless\n"})

    result = compare_tree(root, zip_path, ["whisperlivekit/"])

    assert result.compared == 2
    assert result.extra == []


def test_main_exit_codes(tmp_path, capsys):
    root, zip_path, _ = _baseline(tmp_path)
    argv = ["--root", str(root), "--zip", str(zip_path)]

    assert main(argv) == 0

    (root / "whisperlivekit/llm_translation/translator.py").write_bytes(_OLD_TRANSLATOR)
    assert main(argv) == 1
    assert "translator.py" in capsys.readouterr().out
