# -*- coding: utf-8 -*-
"""CASE1 문장 꼬리 분리 위험도 로그 분석기 (측정용, 코드 무수정).

`.omc/server_logs/server_*.log`(또는 임의 서버 로그)를 파싱해 침묵 경계별로
꼬리 오귀속(CASE1) 위험 신호를 집계한다. 표준 라이브러리만 사용한다.

집계 대상 이벤트 (audio_processor / align_att_base 로그 문자열 기준):
  - "+ Silence of = {d}s ... | last_end = {e} |"  →  완료된 침묵 경계
      · lag  = 같은 로그 라인의 "lag={l}s" (전사 지연)
      · dur  = 침묵 길이 {d}
      · last_end = 마지막 커밋 토큰 end {e}
  - "[QualityGate] ... suppressing: {text}"        →  세그먼트 억제
  - "[QualityGate] N consecutive suppressions — refresh_segment"  →  세그먼트 리프레시

경계별 지표(모두 프록시 — 로그에서 직접 관측 가능한 값으로 정의):
  - zero_emission_rate   : 직전 경계 대비 last_end가 전진하지 않은 경계 비율
                           (침묵 사이 구간에서 커밋 토큰 없음 = 사실상 무방출).
  - qg_refresh_cooccur_rate : 직전 경계~현재 경계 사이에 refresh_segment가
                           발생한 경계 비율 (리프레시는 타임스탬프 과소평가 →
                           꼬리 start가 침묵 앞으로 찍혀 오귀속 유발).
  - ordering_risk_rate   : lag ≥ 침묵 길이(dur)인 경계 비율. 전사 지연이 침묵
                           간격을 넘으면, 침묵 마커가 먼저 커밋된 뒤 유보 꼬리가
                           도착 → Silence 뒤로 밀리는 CASE1 순서 역전 위험.

사용:
    python scripts/analyze_case1_boundaries.py .omc/server_logs/server_*.log
    python scripts/analyze_case1_boundaries.py path/to/one.log path/to/two.log
"""

import argparse
import glob
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional

# ─── 로그 라인 패턴 ──────────────────────────────────────────────────────────
_SILENCE_DONE_RE = re.compile(r"Silence of = ([\d.]+)s")
_LAG_RE = re.compile(r"lag=([\d.]+)s")
_LAST_END_RE = re.compile(r"last_end = ([\d.]+)")
_SUPPRESS_RE = re.compile(r"\[QualityGate\].*suppressing:\s*(.*)$")
_REFRESH_RE = re.compile(r"\[QualityGate\].*consecutive suppressions.*refresh_segment")


@dataclass
class Boundary:
    """완료된 침묵 경계 하나에 대한 파싱 결과."""
    dur: float
    lag: Optional[float]
    last_end: Optional[float]
    suppress_texts: List[str] = field(default_factory=list)  # 직전 경계~현재 사이 억제 텍스트
    refresh_count: int = 0                                    # 직전 경계~현재 사이 refresh 수


def parse_log(lines: List[str]) -> List[Boundary]:
    """로그 라인 시퀀스를 침묵 경계 리스트로 변환한다."""
    boundaries: List[Boundary] = []
    pending_suppress: List[str] = []
    pending_refresh = 0
    for line in lines:
        m_ref = _REFRESH_RE.search(line)
        if m_ref:
            pending_refresh += 1
            continue
        m_sup = _SUPPRESS_RE.search(line)
        if m_sup:
            pending_suppress.append(m_sup.group(1).strip())
            continue
        m_sil = _SILENCE_DONE_RE.search(line)
        if m_sil:
            dur = float(m_sil.group(1))
            m_lag = _LAG_RE.search(line)
            m_le = _LAST_END_RE.search(line)
            boundaries.append(Boundary(
                dur=dur,
                lag=float(m_lag.group(1)) if m_lag else None,
                last_end=float(m_le.group(1)) if m_le else None,
                suppress_texts=pending_suppress,
                refresh_count=pending_refresh,
            ))
            pending_suppress = []
            pending_refresh = 0
    return boundaries


def summarize(boundaries: List[Boundary]) -> dict:
    """경계 리스트에서 세 위험 지표를 집계한다."""
    total = len(boundaries)
    if total == 0:
        return {"total": 0}

    zero_emission = 0
    qg_refresh = 0
    ordering_risk = 0
    prev_last_end: Optional[float] = None
    for b in boundaries:
        # zero_emission: last_end가 직전 경계 대비 전진하지 않음
        if b.last_end is not None and prev_last_end is not None and b.last_end <= prev_last_end + 1e-6:
            zero_emission += 1
        if b.last_end is not None:
            prev_last_end = b.last_end
        # refresh 동시발생
        if b.refresh_count > 0:
            qg_refresh += 1
        # 순서 역전 위험: lag >= 침묵 길이
        if b.lag is not None and b.lag >= b.dur:
            ordering_risk += 1

    return {
        "total": total,
        "zero_emission_rate": zero_emission / total,
        "qg_refresh_cooccur_rate": qg_refresh / total,
        "ordering_risk_rate": ordering_risk / total,
        "zero_emission": zero_emission,
        "qg_refresh": qg_refresh,
        "ordering_risk": ordering_risk,
    }


def _print_table(label: str, stats: dict) -> None:
    if stats.get("total", 0) == 0:
        print(f"{label:<40s}  (침묵 경계 0개 — 파싱 결과 없음)")
        return
    print(f"{label}")
    print(f"  {'total_boundaries':<26s}: {stats['total']}")
    print(f"  {'zero_emission_rate':<26s}: {stats['zero_emission_rate']:.3f}"
          f"  ({stats['zero_emission']}/{stats['total']})")
    print(f"  {'qg_refresh_cooccur_rate':<26s}: {stats['qg_refresh_cooccur_rate']:.3f}"
          f"  ({stats['qg_refresh']}/{stats['total']})")
    print(f"  {'ordering_risk_rate':<26s}: {stats['ordering_risk_rate']:.3f}"
          f"  ({stats['ordering_risk']}/{stats['total']})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CASE1 침묵 경계 위험도 분석기")
    parser.add_argument("logs", nargs="+", help="서버 로그 파일 경로(글로브 허용)")
    parser.add_argument("--per-file", action="store_true", help="파일별 표도 함께 출력")
    args = parser.parse_args(argv)

    paths: List[str] = []
    for pat in args.logs:
        expanded = glob.glob(pat)
        paths.extend(expanded if expanded else [pat])

    all_boundaries: List[Boundary] = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            print(f"[skip] {path}: {e}", file=sys.stderr)
            continue
        bounds = parse_log(lines)
        all_boundaries.extend(bounds)
        if args.per_file:
            _print_table(f"[{path}]  ({len(bounds)} boundaries)", summarize(bounds))
            print()

    print("=" * 60)
    _print_table("[ALL FILES 합계]", summarize(all_boundaries))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
