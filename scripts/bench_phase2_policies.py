"""Phase 2 정책 선정용 실측 벤치마크.

동일 음성 샘플(`test_data/sbs1.mp3`)을 SimulStreaming, LocalAgreement 두 정책에
같은 조건으로 돌려 WER·latency·확정 동작을 비교한다. 결과는
`.omc/benchmarks/phase2_policies_<UTC>.{md,json}` 로 저장한다.

재사용 인프라:
- whisperlivekit.test_harness.TestHarness (audio_processor 위에 얹은 in-process 하네스)
- whisperlivekit.metrics.compute_wer (워드-레벨 Levenshtein WER)
- whisperlivekit.benchmark.metrics.get_system_info (시스템 정보)

상세 계획: C:/Users/A040-000-0001/.claude/plans/stt-effervescent-alpaca.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# `whisperlivekit.benchmark.__init__`이 Unix 전용 `resource` 모듈을 import하는
# runner.py를 끌어와서 Windows에서 임포트 실패한다. 그래서 system_info는 인라인.
from whisperlivekit.metrics import compute_wer, normalize_text
from whisperlivekit.test_harness import TestHarness, load_audio_pcm


def get_system_info() -> Dict[str, Any]:
    """Windows 친화적 시스템 정보 — whisperlivekit.benchmark.metrics 패키지 import 회피용."""
    info: Dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cpu": platform.processor() or "unknown",
    }
    try:
        import torch
        if torch.cuda.is_available():
            info["accelerator"] = torch.cuda.get_device_name(0)
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["accelerator"] = "Apple Silicon (MPS)"
        else:
            info["accelerator"] = "CPU"
        info["torch_version"] = torch.__version__
    except ImportError:
        info["accelerator"] = "CPU"
    return info

DEFAULT_SAMPLE = REPO_ROOT / "test_data" / "sbs1.mp3"
DEFAULT_REFERENCE = REPO_ROOT / "test_data" / "sbs1.txt"
DEFAULT_OUT_DIR = REPO_ROOT / ".omc" / "benchmarks"
DEFAULT_MODEL_DIR = REPO_ROOT / "whisperlivekit" / "model" / "whisper-large-v3-turbo"
POLICIES = ("simulstreaming", "localagreement")


def english_match_ratio(hypothesis: str, reference: str) -> Dict[str, Any]:
    """한·영 혼용 평가용: reference에서 ASCII 영문 단어만 추려, hypothesis에 몇 개가 등장하는지.

    sbs1.txt의 영문 인용구가 hypothesis에 얼마나 잡혔는지 보는 단순 지표.
    """
    en_words_ref = re.findall(r"\b[A-Za-z][A-Za-z'\-]+\b", reference)
    if not en_words_ref:
        return {"ref_en_words": 0, "hyp_en_hits": 0, "match_ratio": 0.0, "ref_en_sample": []}
    hyp_norm = normalize_text(hypothesis)
    hyp_tokens = set(hyp_norm.split())
    hits = sum(1 for w in en_words_ref if w.lower() in hyp_tokens)
    return {
        "ref_en_words": len(en_words_ref),
        "hyp_en_hits": hits,
        "match_ratio": hits / len(en_words_ref),
        "ref_en_sample": en_words_ref[:10],
    }


def lang_distribution(speech_lines: List[Dict[str, Any]]) -> Dict[str, int]:
    """라인별 detected_language 카운트. SimulStreaming은 토큰별 detected_language를 노출."""
    counts: Dict[str, int] = {}
    for line in speech_lines:
        lang = line.get("detected_language") or "unknown"
        counts[lang] = counts.get(lang, 0) + 1
    return counts


async def run_policy(
    policy: str,
    sample_path: Path,
    audio_duration: float,
    reference_text: str,
    model_dir: Path,
    speed: float,
) -> Dict[str, Any]:
    """단일 정책 실행. 예외 발생 시 error 필드를 채워 반환."""
    harness_kwargs = {
        "model_dir": str(model_dir),
        "lan": "auto",
        "pcm_input": True,
        "backend": "whisper",
        "backend_policy": policy,
        "warmup_file": "",
    }
    print(f"\n=== {policy} 시작 ===", flush=True)
    print(f"  sample={sample_path.name}  duration={audio_duration:.1f}s  speed={speed}", flush=True)

    t_start = time.perf_counter()
    try:
        async with TestHarness(**harness_kwargs) as h:
            await h.feed(str(sample_path), speed=speed)
            await h.drain(max(5.0, audio_duration * 0.5))
            state = await h.finish(timeout=180)
            metrics = h.metrics
            metrics_dict = metrics.to_dict() if metrics is not None else {}
            committed = state.committed_text
            speech_lines = list(state.speech_lines)
            timing_valid = bool(state.timing_valid)
            timing_monotonic = bool(state.timing_monotonic)
            buffer_transcription = state.buffer_transcription
    except Exception as e:
        print(f"  [에러] {policy}: {e}", flush=True)
        traceback.print_exc()
        return {
            "policy": policy,
            "error": f"{type(e).__name__}: {e}",
            "processing_time_s": round(time.perf_counter() - t_start, 2),
        }

    t_elapsed = time.perf_counter() - t_start
    wer = compute_wer(reference_text, committed)
    cs = english_match_ratio(committed, reference_text)
    lang_dist = lang_distribution(speech_lines)
    rtf = t_elapsed / audio_duration if audio_duration > 0 else 0

    print(
        f"  [완료] WER={wer['wer']:.3f}  "
        f"lines={len(speech_lines)}  "
        f"avg_lat={metrics_dict.get('avg_latency_ms', 0):.0f}ms  "
        f"elapsed={t_elapsed:.1f}s",
        flush=True,
    )
    return {
        "policy": policy,
        "harness_kwargs": harness_kwargs,
        "processing_time_s": round(t_elapsed, 2),
        "rtf": round(rtf, 3),
        "wer": round(wer["wer"], 4),
        "wer_details": {
            "substitutions": wer["substitutions"],
            "insertions": wer["insertions"],
            "deletions": wer["deletions"],
            "ref_words": wer["ref_words"],
            "hyp_words": wer["hyp_words"],
        },
        "metrics": metrics_dict,
        "n_lines": len(speech_lines),
        "n_buffer_chars": len(buffer_transcription),
        "timing_valid": timing_valid,
        "timing_monotonic": timing_monotonic,
        "committed_text": committed,
        "buffer_at_end": buffer_transcription,
        "speech_lines": speech_lines,
        "lang_distribution": lang_dist,
        "code_switching": cs,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    w = lines.append

    meta = report["meta"]
    w(f"# Phase 2 정책 실측 벤치마크 — {meta['timestamp']}")
    w("")
    w(f"- 샘플: `{meta['sample']}` ({meta['audio_duration_s']:.1f}s)")
    w(f"- 참조: `{meta['reference']}`")
    w(f"- 모델: `{meta['model_dir']}`")
    w(f"- speed: {meta['speed']}  /  lan=auto  /  backend=whisper  /  pcm_input=True")
    w(f"- 시스템: {meta['system_info'].get('platform', '?')} | "
      f"{meta['system_info'].get('accelerator', '?')} | "
      f"py {meta['system_info'].get('python_version', '?')}")
    w("")

    results = report["results"]
    w("## 1. 요약 비교")
    w("")
    w("| 항목 | SimulStreaming | LocalAgreement |")
    w("|---|---|---|")
    sim = next((r for r in results if r["policy"] == "simulstreaming"), None)
    loc = next((r for r in results if r["policy"] == "localagreement"), None)

    def cell(r: Dict[str, Any], key: str, fmt: str = "{}") -> str:
        if r is None:
            return "—"
        if "error" in r:
            return f"❌ {r['error']}"
        if "." in key:
            head, tail = key.split(".", 1)
            val = r.get(head, {}).get(tail, "—")
        else:
            val = r.get(key, "—")
        try:
            return fmt.format(val)
        except Exception:
            return str(val)

    rows = [
        ("WER", "wer", "{:.3f}"),
        ("WER subs/ins/del", None, None),  # 특수 처리
        ("RTF", "rtf", "{:.3f}"),
        ("avg latency (ms)", "metrics.avg_latency_ms", "{:.1f}"),
        ("p95 latency (ms)", "metrics.p95_latency_ms", "{:.1f}"),
        ("n_transcription_calls", "metrics.n_transcription_calls", "{}"),
        ("n_tokens_produced", "metrics.n_tokens_produced", "{}"),
        ("n_lines (확정)", "n_lines", "{}"),
        ("buffer chars (비확정 잔여)", "n_buffer_chars", "{}"),
        ("processing_time (s)", "processing_time_s", "{:.1f}"),
        ("timing_valid", "timing_valid", "{}"),
        ("timing_monotonic", "timing_monotonic", "{}"),
        ("영문 매치 (hits/ref)", None, None),  # 특수 처리
        ("언어 분포 (라인별)", None, None),  # 특수 처리
    ]
    for label, key, fmt in rows:
        if label == "WER subs/ins/del":
            def sid(r):
                if r is None or "error" in r:
                    return "—"
                d = r["wer_details"]
                return f"{d['substitutions']} / {d['insertions']} / {d['deletions']}"
            w(f"| {label} | {sid(sim)} | {sid(loc)} |")
        elif label == "영문 매치 (hits/ref)":
            def cs(r):
                if r is None or "error" in r:
                    return "—"
                c = r["code_switching"]
                return f"{c['hyp_en_hits']} / {c['ref_en_words']} ({c['match_ratio']:.0%})"
            w(f"| {label} | {cs(sim)} | {cs(loc)} |")
        elif label == "언어 분포 (라인별)":
            def ld(r):
                if r is None or "error" in r:
                    return "—"
                return ", ".join(f"{k}:{v}" for k, v in sorted(r["lang_distribution"].items()))
            w(f"| {label} | {ld(sim)} | {ld(loc)} |")
        else:
            w(f"| {label} | {cell(sim, key, fmt)} | {cell(loc, key, fmt)} |")
    w("")

    for r in results:
        policy = r["policy"]
        w(f"## 2. {policy} 상세")
        w("")
        if "error" in r:
            w(f"❌ 실행 실패: `{r['error']}`")
            w("")
            continue
        w("### 2.1 committed_text 전문")
        w("")
        w("```")
        w(r["committed_text"] or "(empty)")
        w("```")
        w("")
        if r.get("buffer_at_end"):
            w("### 2.2 종료 시점 buffer (비확정 잔여)")
            w("")
            w("```")
            w(r["buffer_at_end"])
            w("```")
            w("")
        w("### 2.3 라인 타임라인")
        w("")
        w("| # | start | end | lang | text |")
        w("|---|---|---|---|---|")
        for i, line in enumerate(r["speech_lines"]):
            text = (line.get("text") or "").replace("|", "\\|").replace("\n", " ")
            if len(text) > 100:
                text = text[:97] + "..."
            w(f"| {i+1} | {line.get('start', '')} | {line.get('end', '')} | "
              f"{line.get('detected_language', '')} | {text} |")
        w("")
        cs = r["code_switching"]
        w("### 2.4 코드 스위칭 분석")
        w("")
        w(f"- reference 영문 단어 수: {cs['ref_en_words']}")
        w(f"- hypothesis 매치 수: {cs['hyp_en_hits']}")
        w(f"- 매치 비율: {cs['match_ratio']:.0%}")
        if cs["ref_en_sample"]:
            w(f"- reference 영문 단어 샘플(앞 10개): {', '.join(cs['ref_en_sample'])}")
        w("")

    w("## 3. 정성 평가 (사용자 직접 작성)")
    w("")
    w("> 보고서를 읽은 사용자가 이 섹션을 채워 Phase 2 정책을 확정한다.")
    w("")
    w("### 3.1 환각 인상")
    w("- [ ] 둘 다 환각 있음")
    w("- [ ] SimulStreaming만 환각 두드러짐")
    w("- [ ] LocalAgreement만 환각 두드러짐")
    w("- [ ] 둘 다 환각 거의 없음")
    w("- 메모:")
    w("")
    w("### 3.2 단어 유실 인상")
    w("- 메모:")
    w("")
    w("### 3.3 한·영 전환 자연스러움")
    w("- 메모:")
    w("")
    w("### 3.4 Phase 2 진행 정책 선택")
    w("- [ ] SimulStreaming")
    w("- [ ] LocalAgreement")
    w("- 이유:")
    w("")

    return "\n".join(lines) + "\n"


async def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 정책 실측 벤치마크")
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE,
                        help="음성 파일 경로 (default: test_data/sbs1.mp3)")
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE,
                        help="정답 텍스트 경로 (default: test_data/sbs1.txt)")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR,
                        help="로컬 모델 디렉토리")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="출력 디렉토리")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="재생 속도 (1.0=실시간)")
    parser.add_argument("--policies", nargs="+", default=list(POLICIES),
                        choices=list(POLICIES),
                        help="실행할 정책 목록 (default: 둘 다)")
    args = parser.parse_args()

    if not args.sample.exists():
        print(f"음성 파일 없음: {args.sample}", file=sys.stderr)
        return 1
    if not args.reference.exists():
        print(f"참조 파일 없음: {args.reference}", file=sys.stderr)
        return 1
    if not args.model_dir.exists():
        print(f"모델 디렉토리 없음: {args.model_dir}", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)

    pcm = load_audio_pcm(str(args.sample))
    audio_duration = len(pcm) / (16000 * 2)
    reference_text = args.reference.read_text(encoding="utf-8")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"[bench_phase2_policies] timestamp={timestamp}")
    print(f"  sample={args.sample} ({audio_duration:.1f}s)")
    print(f"  policies={args.policies}  speed={args.speed}")

    results: List[Dict[str, Any]] = []
    for policy in args.policies:
        result = await run_policy(
            policy=policy,
            sample_path=args.sample,
            audio_duration=audio_duration,
            reference_text=reference_text,
            model_dir=args.model_dir,
            speed=args.speed,
        )
        results.append(result)

    report = {
        "meta": {
            "timestamp": timestamp,
            "sample": str(args.sample.relative_to(REPO_ROOT)) if args.sample.is_relative_to(REPO_ROOT) else str(args.sample),
            "reference": str(args.reference.relative_to(REPO_ROOT)) if args.reference.is_relative_to(REPO_ROOT) else str(args.reference),
            "model_dir": str(args.model_dir.relative_to(REPO_ROOT)) if args.model_dir.is_relative_to(REPO_ROOT) else str(args.model_dir),
            "audio_duration_s": round(audio_duration, 2),
            "speed": args.speed,
            "system_info": get_system_info(),
        },
        "results": results,
    }

    json_path = args.out_dir / f"phase2_policies_{timestamp}.json"
    md_path = args.out_dir / f"phase2_policies_{timestamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"\n[완료] 보고서:")
    print(f"  - {md_path}")
    print(f"  - {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
