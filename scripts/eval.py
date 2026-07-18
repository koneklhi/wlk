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
import os
import re
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

SERVER_PORT = 8901
WARMUP_FILE = "test_data/sbs1_10s.mp3"
SERVER_READY_TIMEOUT = 120
POLL_INTERVAL = 2.0

_SCRIPTS_DIR = Path(__file__).parent
_ROOT_DIR = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))


def _probe_provenance(cwd: Path, args) -> dict:
    """서버가 실제 import할 whisperlivekit 경로·git 정보·디코더 설정을 수집한다."""
    # 1) 서버와 같은 python+cwd 환경에서 import 경로 프로브
    try:
        probe = subprocess.run(
            [sys.executable, "-c",
             "import whisperlivekit as wlk, sys; print(wlk.__file__)"],
            capture_output=True, text=True, cwd=str(cwd), timeout=15,
        )
        wlk_file = probe.stdout.strip() if probe.returncode == 0 else "(오류)"
    except Exception as e:
        wlk_file = f"(프로브 실패: {e})"

    # 2) 그 디렉터리에서 git branch / HEAD SHA
    wlk_dir = str(Path(wlk_file).parent.parent) if wlk_file and not wlk_file.startswith("(") else str(cwd)
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, cwd=wlk_dir, timeout=10,
        ).stdout.strip() or "?"
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=wlk_dir, timeout=10,
        ).stdout.strip() or "?"
    except Exception:
        sha, branch = "?", "?"

    # 3) 서버 기본 beams 값 프로브 (parse_args.py 기본값)
    try:
        beams_probe = subprocess.run(
            [sys.executable, "-c",
             "from whisperlivekit.parse_args import create_parser; p=create_parser(); a=p.parse_args([]); print(a.beams)"],
            capture_output=True, text=True, cwd=str(cwd), timeout=15,
        )
        beams = int(beams_probe.stdout.strip()) if beams_probe.returncode == 0 else None
    except Exception:
        beams = None

    return {
        "whisperlivekit_file": wlk_file,
        "git_branch": branch,
        "git_sha": sha,
        "decoder": {
            "beams": beams,
            "compression_ratio_threshold": getattr(args, "compression_ratio_threshold", None),
            "logprob_threshold": getattr(args, "logprob_threshold", None),
            "periodic_lang_check": getattr(args, "periodic_lang_check_secs", None),
        },
        "diarization": getattr(args, "diarization", False),
        "vbcable_loopback": "pending",  # eval 실행 후 갱신
        "files": [str(f) for f in getattr(args, "files", [])],
        "repeat": getattr(args, "repeat", 1),
    }


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
    hyp_lines: Optional[list] = None   # [{"text": str, "trigger": str|None}, ...] 문장별 확정 트리거
    sentence_f1: Optional[float] = None
    sentence_precision: Optional[float] = None
    sentence_recall: Optional[float] = None
    ref_format: Optional[str] = None   # "new"(신형식 _speak,sentence_sperate.txt) | "old"(구형식 .txt) | None(정답 없음)


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

    @property
    def avg_sentence_f1_a(self) -> Optional[float]:
        return self._avg("sentence_f1", "A")

    @property
    def avg_sentence_f1_c(self) -> Optional[float]:
        return self._avg("sentence_f1", "C")


def _save_transcript(transcript_dir: Path, file_result: "FileResult", rep: int = 1) -> None:
    """전사 결과를 정답과 나란히 텍스트 파일로 저장한다 (LLM 비교 평가용)."""
    audio_name = Path(file_result.audio_file).stem
    filename = f"{audio_name}_{file_result.path}_R{rep}.txt"
    wer_str = f"{file_result.wer * 100:.1f}%" if file_result.wer is not None else "N/A"
    f1_str = f"{file_result.seg_f1 * 100:.1f}%" if file_result.seg_f1 is not None else "N/A"
    sent_f1_str = f"{file_result.sentence_f1 * 100:.1f}%" if file_result.sentence_f1 is not None else "N/A"
    ref_format_str = {"new": "신형식", "old": "구형식", None: "정답없음"}.get(file_result.ref_format, "정답없음")
    lines_block = ""
    if file_result.hyp_lines:
        rows = []
        for i, ln in enumerate(file_result.hyp_lines, 1):
            trig = ln.get("trigger") or "-"
            rows.append(f"{i}. {ln['text']}  ⟨{trig}⟩")
        lines_block = "\n[문장별 확정 트리거]\n" + "\n".join(rows) + "\n"
    content = (
        f"파일: {file_result.audio_file}\n"
        f"경로: {file_result.path} | 회차: R{rep} | 정답형식: {ref_format_str}\n"
        f"WER: {wer_str} | 화자분리F1: {f1_str} | 문장분리F1: {sent_f1_str}\n"
        f"\n[전사]\n{file_result.transcription}\n"
        f"{lines_block}"
        f"\n[정답]\n{file_result.reference or '(정답 없음)'}\n"
    )
    transcript_dir.mkdir(parents=True, exist_ok=True)
    (transcript_dir / filename).write_text(content, encoding="utf-8")


def _aggregate_runs(runs: list) -> dict:
    """runs(FileResult 리스트)에서 wer, seg_f1의 median/min/max/stdev를 계산한다."""

    def _stats(vals):
        v = [x for x in vals if x is not None]
        if not v:
            return {"median": None, "min": None, "max": None, "stdev": None}
        return {
            "median": statistics.median(v),
            "min": min(v),
            "max": max(v),
            "stdev": statistics.stdev(v) if len(v) > 1 else 0.0,
        }

    return {
        "wer": _stats([r.wer for r in runs]),
        "seg_f1": _stats([r.seg_f1 for r in runs]),
        "sentence_f1": _stats([r.sentence_f1 for r in runs]),
    }


def parse_reference_sentences(ref_text: str) -> list:
    """빈 줄(\\n\\n)로 구분된 블록 = 문장 1개."""
    return [b.strip() for b in re.split(r"\n\s*\n", ref_text) if b.strip()]


_SPEAKER_HEADER_RE = re.compile(r"^\[(spk\d+)\]\s*$", re.MULTILINE)


def parse_speaker_sentence_reference(ref_text: str) -> Optional[dict]:
    """신형식(`[spkN]` 헤더 + 문장별 줄바꿈) 정답을 파싱한다.

    `[spkN]` 헤더 줄이 하나도 없으면(구형식이거나 형식 불명) None을 반환한다 —
    호출부는 이 경우 parse_reference_sentences()로 폴백한다.

    Returns:
        {
          "blocks": [{"speaker": str, "sentences": [str, ...]}, ...],  # 문서 순서 보존,
                                                                         # 같은 화자 id 재등장도 병합하지 않음
          "plain_text": str,  # 라벨 제거 + 전체 문장 공백 join (WER 정답 텍스트)
        }
    """
    headers = list(_SPEAKER_HEADER_RE.finditer(ref_text))
    if not headers:
        return None

    blocks = []
    all_sentences: list = []
    for idx, m in enumerate(headers):
        speaker = m.group(1)
        start = m.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(ref_text)
        block_text = ref_text[start:end]
        sentences = [s.strip() for s in re.split(r"\n\s*\n", block_text) if s.strip()]
        blocks.append({"speaker": speaker, "sentences": sentences})
        all_sentences.extend(sentences)

    return {"blocks": blocks, "plain_text": " ".join(all_sentences)}


def _server_log_path(audio_path: Path, path_type: str, rep: int) -> str:
    """회차별 서버 로그 파일 경로를 생성한다.

    명명 규칙: .omc/server_logs/server_<stem>_<path>_R<rep>_<ts>.log
    예: .omc/server_logs/server_bong1_C_R1_20240101_120000.log
    """
    log_dir = Path(".omc/server_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = audio_path.stem
    filename = f"server_{stem}_{path_type}_R{rep}_{ts}.log"
    return str(log_dir / filename)


def start_server(
    model_dir: str,
    pcm_input: bool,
    port: int,
    warmup: str,
    lan: str = "auto",
    diarization: bool = False,
    sortformer_model: str = "",
    llm_translation: bool = False,
    extra_server_args: list = None,
    server_log_file: str = None,
) -> subprocess.Popen:
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
    if diarization:
        cmd.extend(["--diarization", "--diarization-backend", "sortformer"])
        if sortformer_model:
            cmd.extend(["--sortformer-model", sortformer_model])
    else:
        cmd.append("--no-diarization")
    if llm_translation:
        cmd.append("--llm-translation")
    else:
        cmd.append("--no-llm-translation")
    if extra_server_args:
        cmd.extend(extra_server_args)
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    if server_log_file:
        log_fh = open(server_log_file, "w", encoding="utf-8")
        proc = subprocess.Popen(cmd, stdout=log_fh, stderr=log_fh, env=env)
        log_fh.close()
        return proc
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)


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


def _build_result(audio_path: Path, transcription: str, hyp_sentences: list, path: str, hyp_lines: Optional[list] = None) -> FileResult:
    """전사 결과로부터 WER + 화자분리 F1 + 문장분리 F1을 산출해 FileResult를 만든다.

    정답은 신형식(`<stem>_speak,sentence_sperate.txt`)을 우선 사용한다 — 존재하고
    `[spkN]` 헤더로 정상 파싱되면(parse_speaker_sentence_reference가 non-None을 반환하면)
    화자분리 F1(seg_f1)·문장분리 F1(sentence_f1)을 함께 산출한다. 신형식 파일이 없거나,
    있어도 헤더가 없어 파싱에 실패하면 구형식(`<stem>.txt`, 빈 줄=경계)으로 완전히 동일하게
    폴백한다 — 이 경우 문장분리 F1은 산출 불가(None)이며 seg_f1은 구 정의(빈 줄 경계) 그대로다.
    """
    from whisperlivekit.metrics import (
        compute_segmentation,
        compute_speaker_sentence_segmentation,
        compute_wer,
        normalize_text,
    )

    reference = None
    wer = None
    seg_f1 = seg_precision = seg_recall = None
    ref_sentences_count = hyp_sentences_count = None
    sentence_f1 = sentence_precision = sentence_recall = None
    ref_format = None

    new_ref_path = audio_path.with_name(audio_path.stem + "_speak,sentence_sperate.txt")
    parsed = None
    if new_ref_path.exists():
        parsed = parse_speaker_sentence_reference(new_ref_path.read_text(encoding="utf-8"))

    if parsed is not None:
        reference = parsed["plain_text"]
        wer = compute_wer(reference, transcription.strip())["wer"]
        two_f1 = compute_speaker_sentence_segmentation(parsed["blocks"], hyp_sentences)
        speaker, sentence = two_f1["speaker"], two_f1["sentence"]
        seg_f1, seg_precision, seg_recall = speaker["f1"], speaker["precision"], speaker["recall"]
        ref_sentences_count = len(parsed["blocks"])
        hyp_sentences_count = len([s for s in hyp_sentences if normalize_text(s).split()])
        if sentence is not None:
            sentence_f1 = sentence["f1"]
            sentence_precision = sentence["precision"]
            sentence_recall = sentence["recall"]
        ref_format = "new"
    else:
        ref_path = audio_path.with_suffix(".txt")
        if ref_path.exists():
            reference = ref_path.read_text(encoding="utf-8").strip()
            wer = compute_wer(reference, transcription.strip())["wer"]
            seg = compute_segmentation(parse_reference_sentences(reference), hyp_sentences)
            seg_f1, seg_precision, seg_recall = seg["f1"], seg["precision"], seg["recall"]
            ref_sentences_count, hyp_sentences_count = seg["ref_sentences"], seg["hyp_sentences"]
            ref_format = "old"

    return FileResult(
        audio_file=str(audio_path),
        transcription=transcription,
        reference=reference,
        wer=wer,
        path=path,
        seg_f1=seg_f1,
        seg_precision=seg_precision,
        seg_recall=seg_recall,
        ref_sentences=ref_sentences_count,
        hyp_sentences=hyp_sentences_count,
        hyp_lines=hyp_lines,
        sentence_f1=sentence_f1,
        sentence_precision=sentence_precision,
        sentence_recall=sentence_recall,
        ref_format=ref_format,
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
    hyp_lines = [{"text": line["text"], "trigger": line.get("finalize_trigger")}
                 for line in result.lines if line.get("text")]
    transcription = result.committed_text or result.text
    return _build_result(audio_file, transcription, hyp_sentences, "A", hyp_lines=hyp_lines)


async def eval_path_c(audio_file: Path, base_url: str, wait_sec: int = 120) -> FileResult:
    from vbcable_test import run_browser_test

    print(f"  [C] {audio_file.name} ...", flush=True)
    try:
        rows = await run_browser_test(audio_file, base_url, wait_sec, None)
    except Exception as e:
        print(f"[eval] 경고: {audio_file.name} 브라우저 테스트 실패: {e}", file=sys.stderr)
        rows = []
    hyp_sentences = [r["text"] for r in rows]
    hyp_lines = [{"text": r["text"], "trigger": (r.get("trigger") or None)} for r in rows]
    transcription = " ".join(hyp_sentences)
    return _build_result(audio_file, transcription, hyp_sentences, "C", hyp_lines=hyp_lines)


def _fmt_pct(v: Optional[float]) -> str:
    return f"{v * 100:.1f}%" if v is not None else "N/A"


def print_summary(result: EvalResult, repeat: int = 1, file_summaries: Optional[list] = None) -> None:
    print("\n" + "=" * 60)
    print(f"평가 결과 | {result.timestamp}")
    print(f"모델: {result.model_dir}")
    print("=" * 60)

    if repeat > 1 and file_summaries:
        # 파일별 회차별 raw + median 출력
        # file_summaries: [{"audio_file": ..., "runs": [...FileResult], "agg": {...}}]
        for fs in file_summaries:
            name = Path(fs["audio_file"]).name
            runs = fs["runs"]
            agg = fs["agg"]
            for i, r in enumerate(runs):
                wer_str = _fmt_pct(r.wer)
                f1_str = _fmt_pct(r.seg_f1)
                sent_f1_str = _fmt_pct(r.sentence_f1)
                prefix = f"  [C] {name:20s}" if i == 0 else " " * (6 + 20)
                print(f"{prefix}  R{i+1}: WER {wer_str:>7s}  화자F1 {f1_str:>7s}  문장F1 {sent_f1_str:>7s}")
            # median 줄
            wer_agg = agg["wer"]
            f1_agg = agg["seg_f1"]
            sent_f1_agg = agg["sentence_f1"]

            med_wer = _fmt_pct(wer_agg["median"])
            med_f1 = _fmt_pct(f1_agg["median"])
            med_sent_f1 = _fmt_pct(sent_f1_agg["median"])
            min_wer = _fmt_pct(wer_agg["min"])
            max_wer = _fmt_pct(wer_agg["max"])
            std_wer = _fmt_pct(wer_agg["stdev"])
            print(
                f"{'  ' + ' ' * 26}  median WER: {med_wer:>7s}  화자F1: {med_f1:>7s}  문장F1: {med_sent_f1:>7s}"
                f"  [min {min_wer} / max {max_wer} / stdev {std_wer}]"
            )
    else:
        for f in result.files:
            wer_str = _fmt_pct(f.wer)
            f1_str = _fmt_pct(f.seg_f1)
            sent_f1_str = _fmt_pct(f.sentence_f1)
            name = Path(f.audio_file).name
            print(f"  [{f.path}] {name:20s}  WER: {wer_str:>7s}  화자F1: {f1_str:>7s}  문장F1: {sent_f1_str:>7s}")

    print("-" * 60)
    if result.avg_wer_a is not None:
        line = f"  경로 A 평균  WER: {result.avg_wer_a * 100:.1f}%  |  화자분리 F1: {_fmt_pct(result.avg_seg_f1_a)}"
        if result.avg_sentence_f1_a is not None:
            line += f"  |  문장분리 F1: {_fmt_pct(result.avg_sentence_f1_a)}"
        print(line)
    if result.avg_wer_c is not None:
        line = f"  경로 C 평균  WER: {result.avg_wer_c * 100:.1f}%  |  화자분리 F1: {_fmt_pct(result.avg_seg_f1_c)}"
        if result.avg_sentence_f1_c is not None:
            line += f"  |  문장분리 F1: {_fmt_pct(result.avg_sentence_f1_c)}"
        print(line)
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
        default=[Path("test_data/sbs1.mp3"), Path("test_data/ytn1.mp3"), Path("test_data/eng1.mp3")],
        help="테스트할 오디오 파일 (기본: test_data/sbs1.mp3 + test_data/ytn1.mp3 + test_data/eng1.mp3)",
    )
    parser.add_argument("--wait", type=int, default=15, help="경로 C 재생 완료 후 대기 시간(초)")
    parser.add_argument("--output", type=Path, default=None, help="결과 JSON 저장 경로")
    parser.add_argument(
        "--lan",
        default="auto",
        help="STT 언어 코드 (기본: auto). 예: ko, en, auto",
    )
    parser.add_argument(
        "--repeat", type=int, default=1,
        help="경로 C 반복 횟수 (기본: 1, 채택/기각 측정시: 3)",
    )
    parser.add_argument(
        "--diarization",
        action="store_true",
        default=False,
        help="화자 분할 활성화 (Sortformer 백엔드). 서버에 --diarization --diarization-backend sortformer 전달.",
    )
    parser.add_argument(
        "--sortformer-model",
        type=str,
        default="",
        help="Sortformer 모델 경로. 비어 있으면 HF 기본값 사용 (폐쇄망: 로컬 .nemo 경로 지정).",
    )
    parser.add_argument(
        "--logprob-threshold",
        type=float,
        default=None,
        dest="logprob_threshold",
        help="avg-logprob 품질 게이트 임계값 (예: -1.0). None=비활성.",
    )
    parser.add_argument(
        "--compression-ratio-threshold",
        type=float,
        default=None,
        dest="compression_ratio_threshold",
        help="compression-ratio 품질 게이트 임계값 (예: 2.4). None=비활성.",
    )
    parser.add_argument(
        "--trace-tokens",
        action="store_true",
        default=False,
        dest="trace_tokens",
        help="TokenTrace 디버그 로그 활성화 (서버에 --trace-tokens 전달).",
    )
    parser.add_argument(
        "--periodic-lang-check",
        type=float,
        default=None,
        dest="periodic_lang_check_secs",
        help="주기적 언어재감지 간격(초). 기본값 None(비활성 — 서버 기본값과 동일, Exp-160). 지정 시 서버에 --periodic-lang-check 전달.",
    )
    parser.add_argument(
        "--audio-max-len",
        type=float,
        default=None,
        dest="audio_max_len",
        help="오디오 버퍼 최대 길이(초, 서버 기본 30.0). P2 sbs1 lag 진단용. 지정 시 서버에 --audio-max-len 전달.",
    )
    parser.add_argument(
        "--frame-threshold",
        type=int,
        default=None,
        dest="frame_threshold",
        help="AlignAtt 프레임 임계값(서버 기본 25). P2 sbs1 lag 진단용. 지정 시 서버에 --frame-threshold 전달.",
    )
    parser.add_argument(
        "--beams",
        type=int,
        default=None,
        dest="beams",
        help="빔서치 빔 개수(서버 기본 2). P3 파라미터 재검증용. 지정 시 서버에 --beams 전달.",
    )
    parser.add_argument(
        "--silence-grammar-gate",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="silence_grammar_gate",
        help="문법-조건부 침묵 경계 게이트(서버 기본 ON). 미지정 시 서버 기본값 사용(전달 안 함). "
        "A/B 비교용: --no-silence-grammar-gate로 롤백, --silence-grammar-gate로 명시 ON.",
    )
    parser.add_argument(
        "--silence-hard-secs",
        type=float,
        default=None,
        dest="silence_hard_secs",
        help="문법-조건부 침묵 게이트 안전망 문턱(초, 서버 기본 0.8). 미지정 시 서버 기본값 사용(전달 안 함). "
        "실험용 스윕 오버라이드 — 서버 측 상한 2.0s 초과 불가(서버가 assert로 거부).",
    )
    parser.add_argument(
        "--expect-code-root",
        type=Path,
        default=None,
        dest="expect_code_root",
        help=(
            "측정 대상 whisperlivekit 코드의 기대 루트 경로 (기본: 현재 작업 디렉터리). "
            "프로브 결과가 이 경로 하위가 아니면 즉시 중단."
        ),
    )
    parser.add_argument(
        "--transcript-dir",
        type=Path,
        default=Path(".omc/transcripts"),
        dest="transcript_dir",
        help="전사 결과 텍스트 저장 디렉터리 (기본: .omc/transcripts). LLM 비교 평가용.",
    )
    args = parser.parse_args()

    # --- provenance 프로브 (cwd 기반 코드 버전 검증) ---
    _cwd = Path(".").resolve()
    _expect_root = (args.expect_code_root or _cwd).resolve()
    _prov = _probe_provenance(_cwd, args)

    # fail-fast: 기대 경로와 실제 import 경로가 다르면 즉시 중단
    _actual_wlk = Path(_prov["whisperlivekit_file"]).resolve() if not _prov["whisperlivekit_file"].startswith("(") else None
    if _actual_wlk is not None:
        try:
            _actual_wlk.relative_to(_expect_root)
        except ValueError:
            print(
                f"[provenance] ❌ 측정 대상 코드가 기대 경로와 다릅니다!\n"
                f"  기대: {_expect_root}\n"
                f"  실제: {_actual_wlk}\n"
                f"  → cwd가 올바른 워크트리 경로인지 확인하세요. --expect-code-root로 명시도 가능.",
                file=sys.stderr,
            )
            sys.exit(1)

    # provenance 1줄 출력 (VBCable 결과는 측정 후 갱신)
    _diar_str = "on" if _prov["diarization"] else "off"
    _crt = _prov["decoder"]["compression_ratio_threshold"]
    _plc = _prov["decoder"]["periodic_lang_check"]
    print(
        f"[provenance] code={Path(_prov['whisperlivekit_file']).parent.parent.name}"
        f" branch={_prov['git_branch']}@{_prov['git_sha']}"
        f" beams={_prov['decoder']['beams']}"
        f" CRT={_crt}"
        f" PLC={_plc}"
        f" diar={_diar_str}"
        f" vbcable=pending"
    )

    paths = [p.strip().upper() for p in args.paths.split(",")]
    base_url = f"http://localhost:{SERVER_PORT}"

    extra_server_args = []
    if args.logprob_threshold is not None:
        extra_server_args.extend(["--logprob-threshold", str(args.logprob_threshold)])
    if args.compression_ratio_threshold is not None:
        extra_server_args.extend(["--compression-ratio-threshold", str(args.compression_ratio_threshold)])
    if args.trace_tokens:
        extra_server_args.append("--trace-tokens")
    if args.periodic_lang_check_secs is not None:
        extra_server_args.extend(["--periodic-lang-check", str(args.periodic_lang_check_secs)])
    if args.audio_max_len is not None:
        extra_server_args.extend(["--audio-max-len", str(args.audio_max_len)])
    if args.frame_threshold is not None:
        extra_server_args.extend(["--frame-threshold", str(args.frame_threshold)])
    if args.beams is not None:
        extra_server_args.extend(["--beams", str(args.beams)])
    if args.silence_grammar_gate is not None:
        extra_server_args.append(
            "--silence-grammar-gate" if args.silence_grammar_gate else "--no-silence-grammar-gate"
        )
    if args.silence_hard_secs is not None:
        extra_server_args.extend(["--silence-hard-secs", str(args.silence_hard_secs)])

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
        print("\n[eval] 경로 A 테스트 시작 (파일별 서버 재시작)...")
        for audio_path in args.files:
            a_log = _server_log_path(audio_path, "A", 1)
            print(f"[eval] 서버 로그 → {a_log}")
            print(f"[eval] 경로 A 서버 기동 중 (포트 {SERVER_PORT})...")
            proc = start_server(args.model_dir, pcm_input=True, port=SERVER_PORT, warmup=warmup, lan=args.lan, diarization=args.diarization, sortformer_model=args.sortformer_model, extra_server_args=extra_server_args, server_log_file=a_log)
            try:
                if not wait_for_ready(base_url, proc):
                    print("[오류] 서버 ready 대기 시간 초과", file=sys.stderr)
                    continue
                print("[eval] 서버 준비 완료.")
                file_result = asyncio.run(eval_path_a(audio_path, base_url))
                if file_result is not None:
                    result.files.append(file_result)
                    _save_transcript(args.transcript_dir, file_result)
            finally:
                stop_server(proc)
                print("[eval] 경로 A 서버 종료.")

    # file_summaries: repeat > 1일 때 파일별 집계 결과 보관
    file_summaries: list = []

    if "C" in paths:
        from audio_device import vbcable_audio_context

        with vbcable_audio_context() as vbcable_ok:
            # provenance에 VBCable 상태 기록 + 콘솔 1줄 갱신
            _prov["vbcable_loopback"] = "ok" if vbcable_ok else "silent/failed"
            _diar_str2 = "on" if _prov["diarization"] else "off"
            _crt2 = _prov["decoder"]["compression_ratio_threshold"]
            _plc2 = _prov["decoder"]["periodic_lang_check"]
            print(
                f"[provenance] code={Path(_prov['whisperlivekit_file']).parent.parent.name}"
                f" branch={_prov['git_branch']}@{_prov['git_sha']}"
                f" beams={_prov['decoder']['beams']}"
                f" CRT={_crt2}"
                f" PLC={_plc2}"
                f" diar={_diar_str2}"
                f" vbcable={'ok' if vbcable_ok else 'FAIL'}"
            )
            if not vbcable_ok:
                print("[eval] 경고: VBCable 설정 실패. 경로 C를 건너뜁니다.", file=sys.stderr)
            else:
                print(f"\n[eval] 경로 C 테스트 시작 (파일별 서버 재시작, repeat={args.repeat})...")
                for audio_path in args.files:
                    runs: list = []
                    for rep in range(args.repeat):
                        rep_label = f"회차 {rep + 1}/{args.repeat}" if args.repeat > 1 else ""
                        c_log = _server_log_path(audio_path, "C", rep + 1)
                        print(f"[eval] 서버 로그 → {c_log}")
                        print(f"[eval] 경로 C 서버 기동 중 (포트 {SERVER_PORT}) {rep_label}...")
                        proc = start_server(args.model_dir, pcm_input=False, port=SERVER_PORT, warmup=warmup, lan=args.lan, diarization=args.diarization, sortformer_model=args.sortformer_model, extra_server_args=extra_server_args, server_log_file=c_log)
                        try:
                            if not wait_for_ready(base_url, proc):
                                print("[오류] 서버 ready 대기 시간 초과", file=sys.stderr)
                                continue
                            print("[eval] 서버 준비 완료.")
                            if args.repeat > 1:
                                print(f"  [C] {audio_path.name} 회차 {rep + 1}/{args.repeat}")
                            file_result = asyncio.run(eval_path_c(audio_path, base_url, args.wait))
                            result.files.append(file_result)
                            runs.append(file_result)
                            _save_transcript(args.transcript_dir, file_result, rep + 1)
                        finally:
                            stop_server(proc)
                            print("[eval] 경로 C 서버 종료.")

                    if args.repeat > 1 and runs:
                        agg = _aggregate_runs(runs)
                        file_summaries.append({
                            "audio_file": str(audio_path),
                            "runs": runs,
                            "agg": agg,
                        })

    print_summary(result, repeat=args.repeat, file_summaries=file_summaries if args.repeat > 1 else None)
    if result.files:
        print(f"\n[eval] 전사 결과 저장: {args.transcript_dir.resolve()}")

    # repeat > 1일 때 파일별 집계를 JSON에 추가
    json_file_summaries = []
    if args.repeat > 1 and file_summaries:
        for fs in file_summaries:
            agg = fs["agg"]
            json_file_summaries.append({
                "audio_file": fs["audio_file"],
                "repeat": args.repeat,
                "wer": agg["wer"],
                "seg_f1": agg["seg_f1"],
                "sentence_f1": agg["sentence_f1"],
            })

    # median 기반 경로 C 평균 (repeat > 1일 때)
    avg_wer_c_median = None
    avg_seg_f1_c_median = None
    avg_sentence_f1_c_median = None
    if args.repeat > 1 and file_summaries:
        wer_medians = [fs["agg"]["wer"]["median"] for fs in file_summaries if fs["agg"]["wer"]["median"] is not None]
        f1_medians = [fs["agg"]["seg_f1"]["median"] for fs in file_summaries if fs["agg"]["seg_f1"]["median"] is not None]
        sent_f1_medians = [
            fs["agg"]["sentence_f1"]["median"] for fs in file_summaries if fs["agg"]["sentence_f1"]["median"] is not None
        ]
        avg_wer_c_median = sum(wer_medians) / len(wer_medians) if wer_medians else None
        avg_seg_f1_c_median = sum(f1_medians) / len(f1_medians) if f1_medians else None
        avg_sentence_f1_c_median = sum(sent_f1_medians) / len(sent_f1_medians) if sent_f1_medians else None

    output_data: dict = {
        "timestamp": result.timestamp,
        "model_dir": result.model_dir,
        "paths_run": result.paths_run,
        "repeat": args.repeat,
        "provenance": _prov,
        "avg_wer_a": result.avg_wer_a,
        "avg_wer_c": result.avg_wer_c,
        "avg_seg_f1_a": result.avg_seg_f1_a,
        "avg_seg_f1_c": result.avg_seg_f1_c,
        "avg_sentence_f1_a": result.avg_sentence_f1_a,
        "avg_sentence_f1_c": result.avg_sentence_f1_c,
        "files": [asdict(f) for f in result.files],
    }
    if args.repeat > 1:
        output_data["file_summaries"] = json_file_summaries
        output_data["avg_wer_c_median"] = avg_wer_c_median
        output_data["avg_seg_f1_c_median"] = avg_seg_f1_c_median
        output_data["avg_sentence_f1_c_median"] = avg_sentence_f1_c_median

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(output_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[eval] 결과 저장: {args.output}")
    else:
        print("\n--- JSON ---")
        print(json.dumps(output_data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
