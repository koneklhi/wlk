#!/usr/bin/env python3
"""폐쇄망 경로 C 자동 전사/평가 스크립트 (drop-in audio → transcribe/compare).

음성 파일 또는 폴더를 받아 경로 C(VBCable 루프백)로 master 최선 설정 STT를 돌리고:
  - 같은 stem의 정답 .txt가 있으면 → WER + 문장분리 F1 계산 후 콘솔 출력 + 리포트 .txt 저장
  - 정답 .txt가 없으면 → 전사 결과만 로컬 .txt로 저장

scripts/eval.py의 검증된 함수를 재사용한다(서버 기동·VBCable 재생·metric).
경로 C이므로 VBCable 드라이버 + playwright(chromium) + comtypes 가 설치돼 있어야 한다.

사용 예:
    python scripts/closed_test.py test_data/sbs1.mp3
    python scripts/closed_test.py test_data/            # 폴더 일괄
    python scripts/closed_test.py my.wav --repeat 3     # 반복 측정(분산)
    python scripts/closed_test.py my.wav --no-diarization
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from eval import (  # noqa: E402
    SERVER_PORT,
    WARMUP_FILE,
    _aggregate_runs,
    eval_path_c,
    start_server,
    stop_server,
    wait_for_ready,
)

# master 최선 기본값 (docs/MASTER_CHANGES.md Exp-105 / CLAUDE.md §4)
DEFAULT_MODEL_DIR = "whisperlivekit/model/whisper-large-v3-turbo"
DEFAULT_SORTFORMER = "whisperlivekit/model/sortformer-4spk-v2.nemo"
DEFAULT_COMPRESSION_RATIO = 3.0
DEFAULT_PERIODIC_LANG_CHECK = 4.0
DEFAULT_OUT_DIR = "transcripts"
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg"}


def _fmt_pct(v) -> str:
    return f"{v * 100:.1f}%" if v is not None else "N/A"


def collect_audio_files(target: Path) -> list:
    if target.is_dir():
        files = sorted(p for p in target.iterdir() if p.suffix.lower() in AUDIO_EXTS)
        if not files:
            print(f"[오류] 폴더에 오디오 파일 없음: {target}", file=sys.stderr)
            sys.exit(1)
        return files
    if target.is_file():
        return [target]
    print(f"[오류] 경로 없음: {target}", file=sys.stderr)
    sys.exit(1)


def save_report(out_dir: Path, audio_path: Path, runs: list, has_ref: bool) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{audio_path.stem}_{ts}.txt"
    lines = [
        f"# audio : {audio_path}",
        f"# time  : {ts}",
        f"# runs  : {len(runs)}",
        f"# ref   : {'있음 (WER/F1 계산)' if has_ref else '없음 (전사만 저장)'}",
    ]
    if has_ref:
        agg = _aggregate_runs(runs)
        w, f = agg["wer"], agg["seg_f1"]
        lines.append(f"# WER   : median={_fmt_pct(w['median'])} min={_fmt_pct(w['min'])} max={_fmt_pct(w['max'])} stdev={_fmt_pct(w['stdev'])}")
        lines.append(f"# F1    : median={_fmt_pct(f['median'])} min={_fmt_pct(f['min'])} max={_fmt_pct(f['max'])}")
    lines.append("")
    for i, r in enumerate(runs):
        lines.append(f"===== 회차 {i + 1}/{len(runs)} =====")
        if has_ref:
            lines.append(f"[WER {_fmt_pct(r.wer)} | F1 {_fmt_pct(r.seg_f1)}]")
        lines.append((r.transcription or "").strip())
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def run_one(audio_path, base_url, *, repeat, wait, warmup, model_dir, diarization,
            sortformer_model, extra_server_args, out_dir) -> None:
    has_ref = audio_path.with_suffix(".txt").exists()
    tag = "정답 있음 → WER/F1" if has_ref else "정답 없음 → 전사 저장"
    print(f"\n[closed_test] ▶ {audio_path.name}  ({tag})")
    runs = []
    for rep in range(repeat):
        print(f"[closed_test]   서버 기동(포트 {SERVER_PORT}) 회차 {rep + 1}/{repeat} ...")
        proc = start_server(
            model_dir, pcm_input=False, port=SERVER_PORT, warmup=warmup, lan="auto",
            diarization=diarization, sortformer_model=sortformer_model,
            extra_server_args=extra_server_args,
        )
        try:
            if not wait_for_ready(base_url, proc):
                print("[오류] 서버 ready 시간 초과", file=sys.stderr)
                continue
            result = asyncio.run(eval_path_c(audio_path, base_url, wait))
            runs.append(result)
            if has_ref:
                print(f"[closed_test]   → WER {_fmt_pct(result.wer)} | F1 {_fmt_pct(result.seg_f1)}")
            else:
                preview = (result.transcription or "").strip()[:100]
                print(f"[closed_test]   → 전사 {len(result.transcription or '')}자: {preview}")
        finally:
            stop_server(proc)
    if not runs:
        print(f"[경고] {audio_path.name}: 결과 없음 (VBCable/서버 확인)", file=sys.stderr)
        return
    out_path = save_report(out_dir, audio_path, runs, has_ref)
    if has_ref and repeat > 1:
        agg = _aggregate_runs(runs)
        print(f"[closed_test] ✓ {audio_path.name}  WER median {_fmt_pct(agg['wer']['median'])} | F1 median {_fmt_pct(agg['seg_f1']['median'])}  → {out_path}")
    else:
        print(f"[closed_test] ✓ {audio_path.name} 저장 → {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(
        description="폐쇄망 경로 C 자동 전사/평가 (음성 → 정답 있으면 비교, 없으면 전사 저장).",
    )
    p.add_argument("target", type=Path, help="음성 파일 또는 폴더 경로")
    p.add_argument("--repeat", type=int, default=1, help="반복 횟수(분산 확인용, 채택판단=3). 기본 1")
    p.add_argument("--wait", type=int, default=15, help="경로 C 재생 완료 후 대기(초). 기본 15")
    p.add_argument("--model-dir", default=DEFAULT_MODEL_DIR, help=f"Whisper 모델 디렉터리. 기본 {DEFAULT_MODEL_DIR}")
    p.add_argument("--out-dir", type=Path, default=Path(DEFAULT_OUT_DIR), help=f"전사/리포트 저장 폴더. 기본 {DEFAULT_OUT_DIR}/")
    p.add_argument("--no-diarization", action="store_true", help="화자분할 끄기(기본은 master 설정대로 ON)")
    p.add_argument("--sortformer-model", default=DEFAULT_SORTFORMER, help=f"Sortformer .nemo 로컬 경로. 기본 {DEFAULT_SORTFORMER}")
    p.add_argument("--compression-ratio-threshold", type=float, default=DEFAULT_COMPRESSION_RATIO, help="반복 환각 게이트. 기본 3.0. 0이면 비활성")
    p.add_argument("--periodic-lang-check", type=float, default=DEFAULT_PERIODIC_LANG_CHECK, help="주기적 언어재감지(초). 기본 4.0. 0이면 비활성")
    args = p.parse_args()

    diarization = not args.no_diarization
    sortformer_model = args.sortformer_model if diarization else ""

    extra = []
    if args.compression_ratio_threshold and args.compression_ratio_threshold > 0:
        extra += ["--compression-ratio-threshold", str(args.compression_ratio_threshold)]
    if args.periodic_lang_check and args.periodic_lang_check > 0:
        extra += ["--periodic-lang-check", str(args.periodic_lang_check)]

    audio_files = collect_audio_files(args.target)
    warmup = WARMUP_FILE if Path(WARMUP_FILE).exists() else str(audio_files[0])
    base_url = f"http://localhost:{SERVER_PORT}"

    print(f"[closed_test] 대상 {len(audio_files)}개 | diarization={'ON' if diarization else 'OFF'} | repeat={args.repeat}")
    if diarization and not Path(sortformer_model).exists():
        print(f"[경고] sortformer 모델 없음: {sortformer_model} (폐쇄망 로컬 .nemo 경로를 --sortformer-model 로 지정)", file=sys.stderr)

    from audio_device import vbcable_audio_context

    with vbcable_audio_context() as vbcable_ok:
        if not vbcable_ok:
            print("[오류] VBCable 설정 실패 — 경로 C 불가. VBCable 드라이버/장치 확인.", file=sys.stderr)
            sys.exit(2)
        for audio_path in audio_files:
            run_one(
                audio_path, base_url, repeat=args.repeat, wait=args.wait, warmup=warmup,
                model_dir=args.model_dir, diarization=diarization,
                sortformer_model=sortformer_model, extra_server_args=extra, out_dir=args.out_dir,
            )

    print("\n[closed_test] 완료.")


if __name__ == "__main__":
    main()
