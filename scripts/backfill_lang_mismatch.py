#!/usr/bin/env python3
"""이미 측정된 벤치마크 JSON에 언어 불일치율(LMR)을 **소급 계산**하는 오프라인 도구.

`scripts/eval.py --output`으로 저장된 JSON의 `files[]`에는 `reference`(비언어 태그가 제거된
정답 텍스트)와 `transcription`(전사)이 그대로 들어 있다. LMR은 이 둘만 있으면 결정적으로
재계산되므로, 서버 기동·오디오 재생 없이 과거 측정을 그대로 다시 채점할 수 있다.

사용법::

    .venv\\Scripts\\python.exe scripts/backfill_lang_mismatch.py <bench.json> \\
        [--ref-file test_data/bong1.txt] [--output .omc/benchmarks/<새파일>.json]

``--ref-file``을 주면 문장 단위 지배 스크립트 뒤집힘 이벤트(정성 리포트용)까지 계산한다.
이때 **정답 판본 불일치를 assert로 강제 차단**한다 — 정답 파일은 워크트리마다 판본이 다를 수
있고(예: `분량이 조금 많은데` vs `분량이 조금 더 많은데`), 벤치 JSON의 `reference`와 다른
판본으로 이벤트를 뽑으면 정렬이 통째로 어긋나 조용히 잘못된 결과가 나오기 때문이다.

``--output``은 항상 **새 파일**에 쓴다 — 기존 측정 산출물을 in-place로 수정하지 않는다.
"""

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

_SCRIPTS_DIR = Path(__file__).parent
_ROOT_DIR = _SCRIPTS_DIR.parent
sys.path.insert(0, str(_ROOT_DIR))
sys.path.insert(0, str(_SCRIPTS_DIR))

from eval import parse_speaker_sentence_reference  # noqa: E402

from whisperlivekit.metrics import compute_language_flip_events, compute_language_mismatch  # noqa: E402

# 소급 집계 대상 지표(키, 표시명) — 콘솔 요약과 JSON aggregate가 같은 목록을 공유한다.
_AGG_KEYS = [("wer", "WER"), ("lmr_ko", "LMR_ko"), ("lmr_en", "LMR_en"), ("lmr_wer_pp", "LMR_wer_pp")]


def flatten_reference_sentences(parsed: dict) -> List[dict]:
    """parse_speaker_sentence_reference 결과의 blocks를 화자 태그가 붙은 평면 문장 리스트로 편다."""
    return [{"text": s, "speaker": b["speaker"]} for b in parsed["blocks"] for s in b["sentences"]]


def verify_reference_parity(parsed: dict, report: dict) -> None:
    """정답 파일 판본이 벤치 JSON의 `reference`와 동일한지 확인한다(불일치 시 즉시 중단).

    Raises:
        AssertionError: 하나라도 다르면 — 어느 회차가 어떻게 다른지 함께 알린다.
    """
    plain = parsed["plain_text"]
    for idx, file_result in enumerate(report.get("files") or []):
        reference = file_result.get("reference")
        if reference is None:
            continue
        assert reference == plain, (
            f"정답 판본 불일치: files[{idx}]({file_result.get('audio_file')})의 reference가 "
            f"--ref-file 파싱 결과와 다릅니다. 이 벤치 JSON을 만든 워크트리의 정답 파일을 지정하세요.\n"
            f"  JSON  길이 {len(reference)}자: ...{reference[:80]}...\n"
            f"  파일  길이 {len(plain)}자: ...{plain[:80]}..."
        )


def recompute_files(report: dict, ref_sentences: Optional[List[dict]] = None) -> List[dict]:
    """report["files"]를 순회하며 LMR을 재계산한 행 리스트를 만든다.

    Args:
        report: eval.py가 저장한 JSON dict.
        ref_sentences: 지정하면 문장 단위 뒤집힘 이벤트도 함께 계산한다
            (flatten_reference_sentences 결과 형태).

    Returns:
        ``[{"audio_file", "path", "wer", "lmr_ko", "lmr_en", "lmr_wer_pp",
            "lang_mismatch", "lang_flip_events"}, ...]``.
        정답(`reference`)이 없는 회차는 전부 None/빈 값으로 채운다.
    """
    rows: List[dict] = []
    for file_result in report.get("files") or []:
        reference = file_result.get("reference")
        transcription = (file_result.get("transcription") or "").strip()
        row = {
            "audio_file": file_result.get("audio_file"),
            "path": file_result.get("path"),
            "wer": file_result.get("wer"),
            "lmr_ko": None,
            "lmr_en": None,
            "lmr_wer_pp": None,
            "lang_mismatch": None,
            "lang_flip_events": None,
        }
        if reference is not None:
            m = compute_language_mismatch(reference, transcription)
            row["lmr_ko"] = m["lmr_ko"]
            row["lmr_en"] = m["lmr_en"]
            row["lmr_wer_pp"] = m["lmr_wer_pp"]
            row["lang_mismatch"] = m
            if ref_sentences is not None:
                row["lang_flip_events"] = compute_language_flip_events(ref_sentences, transcription)
        rows.append(row)
    return rows


def aggregate(rows: List[dict]) -> dict:
    """행 리스트에서 지표별 median/min/max/stdev를 낸다(값이 하나도 없으면 전부 None)."""
    out = {}
    for key, _label in _AGG_KEYS:
        vals = [r[key] for r in rows if r.get(key) is not None]
        if not vals:
            out[key] = {"median": None, "min": None, "max": None, "stdev": None}
        else:
            out[key] = {
                "median": statistics.median(vals),
                "min": min(vals),
                "max": max(vals),
                "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            }
    return out


def _pct(v: Optional[float]) -> str:
    return f"{v * 100:.2f}" if v is not None else "N/A"


def format_table(rows: List[dict], agg: dict) -> str:
    """콘솔 표(회차별 상세 + 집계 요약)를 문자열로 만든다."""
    lines = [
        f"{'R':>3s} {'WER%':>7s} {'LMR_ko%':>8s} {'LMR_en%':>8s} {'wer_pp':>7s} "
        f"{'ko_ok':>6s} {'ko→en':>6s} {'ko→ko':>6s} {'ko_del':>7s} {'en_del':>7s} {'ins≥3':>6s} {'maxIns':>7s} {'flips':>6s}",
        "-" * 108,
    ]
    for i, r in enumerate(rows, 1):
        m = r.get("lang_mismatch") or {}
        flips = r.get("lang_flip_events")
        flips_str = str(len(flips)) if flips is not None else "-"
        lines.append(
            f"{i:>3d} {_pct(r['wer']):>7s} {_pct(r['lmr_ko']):>8s} {_pct(r['lmr_en']):>8s} "
            f"{_pct(r['lmr_wer_pp']):>7s} "
            f"{m.get('ko_ok', '-'):>6} {m.get('ko_to_en', '-'):>6} {m.get('ko_to_ko', '-'):>6} "
            f"{m.get('ko_del', '-'):>7} {m.get('en_del', '-'):>7} "
            f"{m.get('ins_runs_ge3', '-'):>6} {m.get('max_ins_run', '-'):>7} {flips_str:>6s}"
        )

    lines.append("-" * 108)
    lines.append(f"{'지표':<12s} {'median':>9s} {'min':>9s} {'max':>9s} {'stdev':>9s}")
    for key, label in _AGG_KEYS:
        d = agg[key]
        lines.append(
            f"{label:<12s} {_pct(d['median']):>9s} {_pct(d['min']):>9s} "
            f"{_pct(d['max']):>9s} {_pct(d['stdev']):>9s}"
        )

    first = next((r["lang_mismatch"] for r in rows if r.get("lang_mismatch")), None)
    if first:
        lines.append(
            f"\n정답 통계: 총 {first['ref_words']}단어 "
            f"(KO {first['ko_ref_words']} / EN {first['en_ref_words']} / "
            f"기타 {first['ref_words'] - first['ko_ref_words'] - first['en_ref_words']})"
        )
    lines.append(
        "\n주의: LMR은 하한(lower bound)이다 — 정렬이 del+ins로 갈라진 뒤집힘 피해는 잡히지 않는다."
    )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="벤치마크 JSON에 언어 불일치율(LMR)을 소급 계산한다(서버·오디오 없음, 순수 오프라인)."
    )
    parser.add_argument("bench_json", type=Path, help="scripts/eval.py --output으로 저장한 JSON 경로")
    parser.add_argument(
        "--ref-file", type=Path, default=None,
        help="정답 파일(test_data/<name>.txt). 지정하면 문장 단위 뒤집힘 이벤트까지 계산한다. "
             "벤치 JSON의 reference와 판본이 다르면 assert로 즉시 중단.",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="재계산 결과를 저장할 **새** JSON 경로(기존 측정 산출물 in-place 수정 금지).",
    )
    args = parser.parse_args(argv)

    report = json.loads(args.bench_json.read_text(encoding="utf-8"))

    ref_sentences = None
    if args.ref_file is not None:
        parsed = parse_speaker_sentence_reference(args.ref_file.read_text(encoding="utf-8"))
        if parsed is None:
            print(
                f"[backfill] 오류: {args.ref_file}에 [spkN] 헤더가 없어 신형식으로 파싱할 수 없습니다.",
                file=sys.stderr,
            )
            return 1
        verify_reference_parity(parsed, report)
        ref_sentences = flatten_reference_sentences(parsed)

    rows = recompute_files(report, ref_sentences)
    agg = aggregate(rows)
    print(format_table(rows, agg))

    if args.output is not None:
        if args.output.resolve() == args.bench_json.resolve():
            print("[backfill] 오류: --output은 입력 JSON과 같을 수 없습니다(in-place 수정 금지).", file=sys.stderr)
            return 1
        args.output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source": str(args.bench_json),
            "ref_file": str(args.ref_file) if args.ref_file else None,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "files": rows,
            "aggregate": agg,
        }
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[backfill] 저장: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
