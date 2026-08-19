r"""배포 PC에서 실행 중인 소스 트리를 반입 산출물과 대조해 갱신 누락 파일을 찾는다.

배경: whisperlivekit 프로젝트는 wheel로 설치하지 않는다. 배포 PC는 항상
``python -m whisperlivekit.basic_server``로 켜고 cwd의 raw 소스 사본이 그대로 로드되므로,
**파일 복사 누락을 잡아줄 백스톱이 없다**. 게다가 반입은 증분(``git diff <직전>..master``)이라
배치를 한 번 놓치면 그 뒤로 안 바뀐 파일은 이후 어떤 배치에도 실리지 않아 **영구히 구세대로
남는다** — 2026-08 배포 PC에서 ``llm_translation/translator.py``만 구세대로 남아 실시간 번역이
``TypeError``로 죽은 사고가 정확히 이 경로였다(``docs/DEPLOYMENT_OFFLINE.md`` 8절 참조).

정답 소스는 이미 USB로 함께 가는 ``deploy/deploy_source.zip``(``git archive master`` 산출물)이다.
추가로 반입할 산출물이 없다는 점이 이 도구의 핵심이다.

이 스크립트는 **읽기 전용**이다 — 파일을 고치거나 지우지 않고 목록과 종료 코드만 낸다.
표준 라이브러리만 쓰므로 venv 없는 배포 PC에서 ``C:\Python312\python.exe``로 바로 돈다.

사용법 (배포 PC, 저장소 루트에서):
    C:\Python312\python.exe scripts\verify_deploy_tree.py --zip deploy\deploy_source.zip

종료 코드: 이상 없으면 0, STALE/MISSING이 하나라도 있으면 1, 실행 자체가 불가하면 2.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

#: 배포 PC가 소스에서 직접 로드하는 트리. docs/·tests/는 stale해도 동작에 영향이 없어 기본 대상이 아니다.
DEFAULT_PREFIXES = ("whisperlivekit/", "scripts/")
DEFAULT_ZIP = "deploy/deploy_source.zip"

#: 줄바꿈을 정규화한 뒤 비교할 확장자. 개발 트리는 CRLF, wlk_in·zip은 LF라
#: (git show/git archive가 LF blob을 그대로 쓴다) 정규화하지 않으면 전 파일이 STALE로 오탐된다.
_TEXT_SUFFIXES = frozenset({
    ".py", ".pyi", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".csv",
})

#: EXTRA 목록에서 제외할 디렉터리. 항상 PC에만 존재해 목록을 덮어버린다.
_EXCLUDED_DIR_NAMES = frozenset({"__pycache__"})


@dataclass
class ComparisonResult:
    """대조 결과. ``extra``는 정보용이며 판정(``ok``)에 넣지 않는다."""

    stale: list = field(default_factory=list)      # 양쪽에 있으나 내용이 다름 - 갱신 필요
    missing: list = field(default_factory=list)    # zip에 있는데 PC에 없음 - 복사 필요
    extra: list = field(default_factory=list)      # PC에만 존재 - 삭제 금지(아래 print_report 참조)
    compared: int = 0

    @property
    def ok(self) -> bool:
        return not self.stale and not self.missing


def _digest(data: bytes, suffix: str) -> str:
    """텍스트는 CRLF를 LF로 정규화한 뒤, 그 외는 바이트 그대로 해시한다."""
    if suffix.lower() in _TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _normalize_prefixes(prefixes: Iterable) -> tuple:
    return tuple(p.replace("\\", "/").rstrip("/") + "/" for p in prefixes)


def _find_extra(root: Path, prefixes: Sequence, known: set) -> list:
    """PC에만 있는 파일 목록. RAG 자산·모델 가중치·user DB가 정상적으로 여기 걸린다."""
    found = set()
    for prefix in prefixes:
        base = root / prefix.rstrip("/")
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(root).parts
            if any(part in _EXCLUDED_DIR_NAMES for part in rel_parts):
                continue
            rel = "/".join(rel_parts)
            if rel not in known:
                found.add(rel)
    return sorted(found)


def compare_tree(root, zip_path, prefixes: Sequence = DEFAULT_PREFIXES) -> ComparisonResult:
    """``root`` 트리를 ``zip_path`` 안의 같은 경로와 대조한다."""
    root = Path(root)
    prefixes = _normalize_prefixes(prefixes)
    result = ComparisonResult()

    expected = {}
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if not name.startswith(prefixes):
                continue
            expected[name] = _digest(archive.read(info), Path(name).suffix)

    for name in sorted(expected):
        target = root / name
        if not target.is_file():
            result.missing.append(name)
            continue
        result.compared += 1
        if _digest(target.read_bytes(), target.suffix) != expected[name]:
            result.stale.append(name)

    result.extra = _find_extra(root, prefixes, set(expected))
    return result


def _print_section(title: str, entries: Sequence) -> None:
    print(f"\n{title}")
    if not entries:
        print("  (없음)")
        return
    for entry in entries:
        print(f"  {entry}")


def print_report(result: ComparisonResult, root: Path, zip_path: Path, prefixes: Sequence) -> None:
    print(f"[verify] root = {root}")
    print(f"[verify] zip  = {zip_path}")
    print(f"[verify] 대상 = {', '.join(prefixes)}")
    print(f"[verify] 대조한 파일 수 = {result.compared}")

    _print_section("STALE (내용 불일치 - 반드시 갱신):", result.stale)
    _print_section("MISSING (zip에 있으나 PC에 없음 - 반드시 복사):", result.missing)
    _print_section("EXTRA (PC에만 존재 - 정보용, 삭제하지 말 것):", result.extra)

    print(
        f"\n결과: STALE {len(result.stale)} / MISSING {len(result.missing)} "
        f"/ EXTRA {len(result.extra)}  ->  " + ("이상 없음" if result.ok else "갱신 필요")
    )
    print(
        "\n참고: EXTRA에는 RAG 자산(local_stt_shot/·Embedding_model/)·모델 가중치·user_*.db가\n"
        "      정상적으로 잡힌다. 이들은 .gitignore 대상이라 zip에 없을 뿐이며 지우면 안 된다.\n"
        "한계: frontend/static/(빌드 dist)도 .gitignore 대상이라 zip에 없어 이 도구로 검증되지\n"
        "      않는다. index.html의 asset 해시 대조(/deploy-sync 5단계)로 따로 확인한다."
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="배포 PC 소스 트리를 deploy_source.zip과 대조해 갱신 누락 파일을 찾는다(읽기 전용).",
    )
    parser.add_argument("--root", default=".", help="점검할 저장소 루트 (기본: 현재 디렉터리)")
    parser.add_argument("--zip", dest="zip_path", default=DEFAULT_ZIP, help=f"정답 zip 경로 (기본: {DEFAULT_ZIP})")
    parser.add_argument(
        "--paths", nargs="+", default=list(DEFAULT_PREFIXES),
        help=f"점검할 경로 prefix (기본: {' '.join(DEFAULT_PREFIXES)})",
    )
    args = parser.parse_args(argv)

    try:  # 콘솔 코드페이지가 한글 일부를 못 담아도 죽지 않게 한다(배포 PC는 cmd 콘솔).
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, OSError):
        pass

    root = Path(args.root).resolve()
    zip_path = Path(args.zip_path)
    if not zip_path.is_absolute():
        zip_path = root / zip_path

    if not root.is_dir():
        print(f"[verify] 오류: 루트를 찾을 수 없습니다 - {root}")
        return 2
    if not zip_path.is_file():
        print(f"[verify] 오류: zip을 찾을 수 없습니다 - {zip_path}")
        print("         반입 USB의 deploy/deploy_source.zip을 배포 PC에 복사했는지 확인하세요.")
        return 2

    prefixes = _normalize_prefixes(args.paths)
    result = compare_tree(root, zip_path, prefixes)
    print_report(result, root, zip_path, prefixes)
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
