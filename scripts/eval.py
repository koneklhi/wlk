#!/usr/bin/env python3
"""경로 A (파일 기반 WebSocket) + 경로 C (VBCable 루프백) 통합 평가 스크립트.

사용법:
    # 경로 A만
    python scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo --paths A

    # 경로 A + C 모두 (기본)
    python scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo

    # 결과를 JSON 파일로 저장
    python scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo --output .omc/benchmarks/eval_baseline.json
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

SERVER_PORT = 8001
WARMUP_FILE = "test_data/sbs1_10s.mp3"
SERVER_READY_TIMEOUT = 120
POLL_INTERVAL = 2.0

_SCRIPTS_DIR = Path(__file__).parent
_ROOT_DIR = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))


@dataclass
class FileResult:
    audio_file: str
    transcription: str
    reference: Optional[str]
    wer: Optional[float]
    path: str


@dataclass
class EvalResult:
    timestamp: str
    paths_run: list
    model_dir: str
    files: list = field(default_factory=list)

    @property
    def avg_wer_a(self) -> Optional[float]:
        vals = [f.wer for f in self.files if f.path == "A" and f.wer is not None]
        return sum(vals) / len(vals) if vals else None

    @property
    def avg_wer_c(self) -> Optional[float]:
        vals = [f.wer for f in self.files if f.path == "C" and f.wer is not None]
        return sum(vals) / len(vals) if vals else None


def start_server(model_dir: str, pcm_input: bool, port: int, warmup: str) -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "whisperlivekit.basic_server",
        "--model_dir", model_dir,
        "--backend", "whisper",
        "--lan", "ko",
        "--host", "localhost",
        "--port", str(port),
        "--warmup-file", warmup,
    ]
    if pcm_input:
        cmd.append("--pcm-input")
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def wait_for_ready(url: str, proc: subprocess.Popen, timeout: int = SERVER_READY_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"[eval] 서버 프로세스가 예기치 않게 종료됨 (returncode={proc.returncode})")
            return False
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=5) as resp:
                data = json.loads(resp.read())
            if data.get("ready", False):
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(POLL_INTERVAL)
    return False


def stop_server(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


async def eval_path_a(audio_files: list, base_url: str) -> list:
    from whisperlivekit.test_client import transcribe_audio
    from whisperlivekit.metrics import compute_wer

    results = []
    ws_url = base_url.replace("http://", "ws://") + "/asr"
    for audio_path in audio_files:
        print(f"  [A] {audio_path.name} ...", flush=True)
        result = await transcribe_audio(
            audio_path=str(audio_path),
            url=ws_url,
            speed=0,
            timeout=120.0,
        )
        transcription = result.committed_text or result.text

        reference = None
        wer = None
        ref_path = audio_path.with_suffix(".txt")
        if ref_path.exists():
            reference = ref_path.read_text(encoding="utf-8").strip()
            wer = compute_wer(reference, transcription.strip())["wer"]

        results.append(FileResult(
            audio_file=str(audio_path),
            transcription=transcription,
            reference=reference,
            wer=wer,
            path="A",
        ))
    return results


async def eval_path_c(audio_files: list, base_url: str, wait_sec: int = 15) -> list:
    from vbcable_test import run_browser_test, find_reference, compute_wer_score

    results = []
    for audio_path in audio_files:
        print(f"  [C] {audio_path.name} ...", flush=True)
        transcription = await run_browser_test(audio_path, base_url, wait_sec, None)
        reference = find_reference(audio_path)
        wer = compute_wer_score(transcription, reference) if reference else None
        results.append(FileResult(
            audio_file=str(audio_path),
            transcription=transcription,
            reference=reference,
            wer=wer,
            path="C",
        ))
    return results


def print_summary(result: EvalResult) -> None:
    print("\n" + "=" * 60)
    print(f"평가 결과 | {result.timestamp}")
    print(f"모델: {result.model_dir}")
    print("=" * 60)
    for f in result.files:
        wer_str = f"{f.wer * 100:.1f}%" if f.wer is not None else "N/A"
        name = Path(f.audio_file).name
        print(f"  [{f.path}] {name:20s}  WER: {wer_str}")
    print("-" * 60)
    if result.avg_wer_a is not None:
        print(f"  경로 A 평균 WER: {result.avg_wer_a * 100:.1f}%")
    if result.avg_wer_c is not None:
        print(f"  경로 C 평균 WER: {result.avg_wer_c * 100:.1f}%")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="경로 A + C 통합 평가 실행기")
    parser.add_argument("--model-dir", required=True, help="Whisper 모델 디렉토리 경로")
    parser.add_argument(
        "--paths", default="A,C",
        help="실행할 경로 (쉼표 구분, 기본: A,C). 예: A 또는 A,C",
    )
    parser.add_argument(
        "--files", nargs="+", type=Path,
        default=[Path("test_data/sbs1.mp3")],
        help="테스트할 오디오 파일 (기본: test_data/sbs1.mp3)",
    )
    parser.add_argument("--wait", type=int, default=15, help="경로 C 재생 완료 후 대기 시간(초)")
    parser.add_argument("--output", type=Path, default=None, help="결과 JSON 저장 경로")
    args = parser.parse_args()

    paths = [p.strip().upper() for p in args.paths.split(",")]
    base_url = f"http://localhost:{SERVER_PORT}"

    for f in args.files:
        if not f.exists():
            print(f"[오류] 파일 없음: {f}", file=sys.stderr)
            sys.exit(1)

    warmup = WARMUP_FILE if Path(WARMUP_FILE).exists() else str(args.files[0])

    result = EvalResult(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        paths_run=paths,
        model_dir=args.model_dir,
    )

    if "A" in paths:
        print(f"\n[eval] 경로 A 서버 기동 중 (포트 {SERVER_PORT})...")
        proc = start_server(args.model_dir, pcm_input=True, port=SERVER_PORT, warmup=warmup)
        try:
            if not wait_for_ready(base_url, proc):
                print("[오류] 서버 ready 대기 시간 초과", file=sys.stderr)
                stop_server(proc)
                sys.exit(1)
            print("[eval] 서버 준비 완료. 경로 A 테스트 시작...")
            result.files.extend(asyncio.run(eval_path_a(args.files, base_url)))
        finally:
            stop_server(proc)
            print("[eval] 경로 A 서버 종료.")

    if "C" in paths:
        from audio_device import vbcable_audio_context

        with vbcable_audio_context() as vbcable_ok:
            if not vbcable_ok:
                print("[eval] 경고: VBCable 설정 실패. 경로 C를 건너뜁니다.", file=sys.stderr)
            else:
                print(f"\n[eval] 경로 C 서버 기동 중 (포트 {SERVER_PORT})...")
                proc = start_server(args.model_dir, pcm_input=False, port=SERVER_PORT, warmup=warmup)
                try:
                    if not wait_for_ready(base_url, proc):
                        print("[오류] 서버 ready 대기 시간 초과", file=sys.stderr)
                        stop_server(proc)
                    else:
                        print("[eval] 서버 준비 완료. 경로 C 테스트 시작...")
                        result.files.extend(asyncio.run(eval_path_c(args.files, base_url, args.wait)))
                finally:
                    stop_server(proc)
                    print("[eval] 경로 C 서버 종료.")

    print_summary(result)

    output_data = {
        "timestamp": result.timestamp,
        "model_dir": result.model_dir,
        "paths_run": result.paths_run,
        "avg_wer_a": result.avg_wer_a,
        "avg_wer_c": result.avg_wer_c,
        "files": [asdict(f) for f in result.files],
    }

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[eval] 결과 저장: {args.output}")
    else:
        print("\n--- JSON ---")
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
