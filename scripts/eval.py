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
import re
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
    seg_f1: Optional[float] = None
    seg_precision: Optional[float] = None
    seg_recall: Optional[float] = None
    ref_sentences: Optional[int] = None
    hyp_sentences: Optional[int] = None


@dataclass
class EvalResult:
    timestamp: str
    paths_run: list
    model_dir: str
    files: list = field(default_factory=list)

    def _avg(self, attr: str, path: str) -> Optional[float]:
        vals = [getattr(f, attr) for f in self.files if f.path == path and getattr(f, attr) is not None]
        return sum(vals) / len(vals) if vals else None

    @property
    def avg_wer_a(self) -> Optional[float]:
        return self._avg("wer", "A")

    @property
    def avg_wer_c(self) -> Optional[float]:
        return self._avg("wer", "C")

    @property
    def avg_seg_f1_a(self) -> Optional[float]:
        return self._avg("seg_f1", "A")

    @property
    def avg_seg_f1_c(self) -> Optional[float]:
        return self._avg("seg_f1", "C")


def parse_reference_sentences(ref_text: str) -> list:
    """빈 줄(\\n\\n)로 구분된 블록 = 문장 1개."""
    return [b.strip() for b in re.split(r"\n\s*\n", ref_text) if b.strip()]


def start_server(model_dir: str, pcm_input: bool, port: int, warmup: str, lan: str = "auto") -> subprocess.Popen:
    cmd = [
        sys.executable, "-m", "whisperlivekit.basic_server",
        "--model_dir", model_dir,
        "--backend", "whisper",
        "--lan", lan,
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


def _build_result(audio_path: Path, transcription: str, hyp_sentences: list, path: str) -> FileResult:
    """전사 결과로부터 WER + 문장 분리 F1을 산출해 FileResult를 만든다."""
    from whisperlivekit.metrics import compute_segmentation, compute_wer

    reference = None
    wer = None
    seg = None
    ref_path = audio_path.with_suffix(".txt")
    if ref_path.exists():
        reference = ref_path.read_text(encoding="utf-8").strip()
        wer = compute_wer(reference, transcription.strip())["wer"]
        seg = compute_segmentation(parse_reference_sentences(reference), hyp_sentences)

    return FileResult(
        audio_file=str(audio_path),
        transcription=transcription,
        reference=reference,
        wer=wer,
        path=path,
        seg_f1=seg["f1"] if seg else None,
        seg_precision=seg["precision"] if seg else None,
        seg_recall=seg["recall"] if seg else None,
        ref_sentences=seg["ref_sentences"] if seg else None,
        hyp_sentences=seg["hyp_sentences"] if seg else None,
    )


async def eval_path_a(audio_file: Path, base_url: str) -> Optional[FileResult]:
    from whisperlivekit.test_client import transcribe_audio

    ws_url = base_url.replace("http://", "ws://") + "/asr"
    print(f"  [A] {audio_file.name} ...", flush=True)
    try:
        result = await transcribe_audio(
            audio_path=str(audio_file),
            url=ws_url,
            speed=0,
            timeout=120.0,
        )
    except Exception as e:
        print(f"[eval] 경고: {audio_file.name} 전사 실패: {e}", file=sys.stderr)
        return None
    hyp_sentences = [line["text"] for line in result.lines if line.get("text")]
    transcription = result.committed_text or result.text
    return _build_result(audio_file, transcription, hyp_sentences, "A")


async def eval_path_c(audio_file: Path, base_url: str, wait_sec: int = 120) -> FileResult:
    from vbcable_test import run_browser_test

    print(f"  [C] {audio_file.name} ...", flush=True)
    try:
        hyp_sentences = await run_browser_test(audio_file, base_url, wait_sec, None)
    except Exception as e:
        print(f"[eval] 경고: {audio_file.name} 브라우저 테스트 실패: {e}", file=sys.stderr)
        hyp_sentences = []
    transcription = " ".join(hyp_sentences)
    return _build_result(audio_file, transcription, hyp_sentences, "C")


def print_summary(result: EvalResult) -> None:
    print("\n" + "=" * 60)
    print(f"평가 결과 | {result.timestamp}")
    print(f"모델: {result.model_dir}")
    print("=" * 60)
    for f in result.files:
        wer_str = f"{f.wer * 100:.1f}%" if f.wer is not None else "N/A"
        f1_str = f"{f.seg_f1 * 100:.1f}%" if f.seg_f1 is not None else "N/A"
        name = Path(f.audio_file).name
        print(f"  [{f.path}] {name:20s}  WER: {wer_str:>7s}  F1: {f1_str:>7s}")
    print("-" * 60)
    if result.avg_wer_a is not None:
        f1a = f"{result.avg_seg_f1_a * 100:.1f}%" if result.avg_seg_f1_a is not None else "N/A"
        print(f"  경로 A 평균  WER: {result.avg_wer_a * 100:.1f}%  |  문장분리 F1: {f1a}")
    if result.avg_wer_c is not None:
        f1c = f"{result.avg_seg_f1_c * 100:.1f}%" if result.avg_seg_f1_c is not None else "N/A"
        print(f"  경로 C 평균  WER: {result.avg_wer_c * 100:.1f}%  |  문장분리 F1: {f1c}")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="경로 C (VBCable 루프백) 성능 평가 실행기. 경로 A는 빠른 개발 체크용 옵션.")
    parser.add_argument("--model-dir", required=True, help="Whisper 모델 디렉토리 경로")
    parser.add_argument(
        "--paths", default="C",
        help="실행할 경로 (쉼표 구분, 기본: C). A는 빠른 개발 체크용. 예: C 또는 A,C",
    )
    parser.add_argument(
        "--files", nargs="+", type=Path,
        default=[Path("test_data/sbs1.mp3"), Path("test_data/ytn1.mp3")],
        help="테스트할 오디오 파일 (기본: test_data/sbs1.mp3 + test_data/ytn1.mp3)",
    )
    parser.add_argument("--wait", type=int, default=15, help="경로 C 재생 완료 후 대기 시간(초)")
    parser.add_argument("--output", type=Path, default=None, help="결과 JSON 저장 경로")
    parser.add_argument(
        "--lan",
        default="auto",
        help="STT 언어 코드 (기본: auto). 예: ko, en, auto",
    )
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
        print(f"\n[eval] 경로 A 테스트 시작 (파일별 서버 재시작)...")
        for audio_path in args.files:
            print(f"[eval] 경로 A 서버 기동 중 (포트 {SERVER_PORT})...")
            proc = start_server(args.model_dir, pcm_input=True, port=SERVER_PORT, warmup=warmup, lan=args.lan)
            try:
                if not wait_for_ready(base_url, proc):
                    print("[오류] 서버 ready 대기 시간 초과", file=sys.stderr)
                    continue
                print("[eval] 서버 준비 완료.")
                file_result = asyncio.run(eval_path_a(audio_path, base_url))
                if file_result is not None:
                    result.files.append(file_result)
            finally:
                stop_server(proc)
                print("[eval] 경로 A 서버 종료.")

    if "C" in paths:
        from audio_device import vbcable_audio_context

        with vbcable_audio_context() as vbcable_ok:
            if not vbcable_ok:
                print("[eval] 경고: VBCable 설정 실패. 경로 C를 건너뜁니다.", file=sys.stderr)
            else:
                print(f"\n[eval] 경로 C 테스트 시작 (파일별 서버 재시작)...")
                for audio_path in args.files:
                    print(f"[eval] 경로 C 서버 기동 중 (포트 {SERVER_PORT})...")
                    proc = start_server(args.model_dir, pcm_input=False, port=SERVER_PORT, warmup=warmup, lan=args.lan)
                    try:
                        if not wait_for_ready(base_url, proc):
                            print("[오류] 서버 ready 대기 시간 초과", file=sys.stderr)
                            continue
                        print("[eval] 서버 준비 완료.")
                        file_result = asyncio.run(eval_path_c(audio_path, base_url, args.wait))
                        result.files.append(file_result)
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
        "avg_seg_f1_a": result.avg_seg_f1_a,
        "avg_seg_f1_c": result.avg_seg_f1_c,
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
