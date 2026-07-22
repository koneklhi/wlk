#!/usr/bin/env python3
"""[SotLangProbe] 계측의 언어잠금 실패 예측력 측정 (오프라인 로그 분석 · Stage 0 GO/NO-GO).

배경: 선행 연구 `docs/research/TRANSLIT_LANGID_PROBE.md` 는 lang_id 를 음차 환각 재감지
트리거로 쓰는 설계에 NO-GO 를 냈다. 핵심 근거는 **선제성 부재**(0/11 이벤트) 였고,
그 한계로 "기존 로그에는 코드가 lang_id 를 *호출한* 지점(세션초입/eager/short-silence/
ScriptAnchor)의 성긴 프로브만 있다"는 계측 공백을 명시하며 §6 에서 **매 배치 연속 프로브**
계측을 후속 과제로 제안했다. `[SotLangProbe]` 가 바로 그 계측이다 — 이 스크립트는 그
연속 프로브가 선행 연구가 요구한 조건(문턱 존재 · 선제성 · 오탐 희소)을 만족하는지 측정한다.

측정하는 것:
  1. 신호별 판별력 — 표적 창(언어잠금 실패 구간) vs 대조 창(정상 전사)의 분포 분리.
  2. 선제성 — 실패가 커밋되기 *전에* 신호가 떴는가, 몇 배치/몇 초 전인가.
  3. 오탐 — mismatch 후보(반대언어 p>=문턱)가 어디서 발동하며 정당/오탐 중 무엇인가.

핵심 통계량은 **p_opp = 현재 잠긴 언어의 "반대쪽" 재정규화 확률** 이다
(locked=en → p_ko, locked=ko → p_en). 원시 p_ko 를 창끼리 비교하면 "어느 언어가
잠겨 있었나"에 교란되므로 p_opp 로 정규화한다. locked=None 프로브는 p_opp 미정의라
p_opp 통계에서 제외하되 resid/H_lang 등 잠금 무관 신호에는 포함한다.

표준 라이브러리만 사용. 입력 로그를 수정하지 않는 읽기 전용 분석.

사용법:
    python scripts/analyze_sot_lang_probe.py --log <서버로그.log> \
        --target "A:14.3-17.5" --target "B:112.2-117.4" \
        --control-window "plastic:86.0-93.0"

    python scripts/analyze_sot_lang_probe.py --log <ytn2 로그> --list-mismatch
"""
from __future__ import annotations

import argparse
import os
import re
import statistics
import sys
from dataclasses import dataclass, field

# --- 로그 마커 정규식 ----------------------------------------------------------
# RE_LANGSWITCH / RE_OUTPUT / RE_DETECTED / RE_SHORTSIL 은 `scripts/analyze_translit_langid.py`
# (브랜치 `exp/codeswitch-translit-probe`) 에서 검증된 패턴을 그대로 재사용한다. 그 파일은
# 이 브랜치의 워크트리에 없어(다른 워크트리에만 존재) import 가 불가능하므로 정의를 복제했다 —
# 패턴 문자열은 원본과 동일하게 유지할 것(로그 포맷이 바뀌면 양쪽을 함께 고쳐야 한다).
RE_LANGSWITCH = re.compile(r"\[LangSwitch\] 토크나이저 적용: (\w+) \(prev=(\w+|None), switch=(\w+)")
RE_OUTPUT = re.compile(r"align_att_base:Output:\s*(.*)$")
RE_DETECTED = re.compile(r"Detected language: (\w+) with p=([0-9.]+)")
RE_SHORTSIL = re.compile(r"\[ShortSilenceLangCheck\] 최근 ([0-9.]+)s → (\w+) \(p=([0-9.]+)\)")

# [SotLangProbe] 는 key=value 공백구분이라 필드 단위로 뽑는다.
RE_SOTPROBE = re.compile(r"\[SotLangProbe\] (.+)$")
RE_KV = re.compile(r"(\w+)=(-?[\w.+-]+)")
RE_DRIFTSTATS = re.compile(r"\[LangDriftStats\] (.+)$")

# 계측 코드(align_att_base.py)의 문턱 상수와 동일하게 유지한다.
MISMATCH_P = 0.9      # SOT_PROBE_MISMATCH_P
RESID_HIGH = 0.5      # SOT_PROBE_RESID_HIGH

FLOAT_FIELDS = ("t_abs", "seglen", "p_ko", "p_en", "p_abs_ko", "p_abs_en",
                "resid", "H_lang", "p_translate", "p_transcribe", "p_nospeech")


@dataclass
class Probe:
    lineno: int
    batch: int
    t_abs: float
    locked: str | None      # 'ko' | 'en' | None
    seglen: float
    vals: dict[str, float] = field(default_factory=dict)

    @property
    def p_opp(self) -> float | None:
        """잠긴 언어의 반대쪽 재정규화 확률. locked=None 이면 미정의."""
        if self.locked == "en":
            return self.vals.get("p_ko")
        if self.locked == "ko":
            return self.vals.get("p_en")
        return None


@dataclass
class Emission:
    lineno: int
    text: str
    t_abs: float | None     # 직전 프로브의 t_abs (근사)
    locked: str | None


@dataclass
class ParsedLog:
    path: str
    probes: list[Probe] = field(default_factory=list)
    emissions: list[Emission] = field(default_factory=list)
    switches: list[tuple[int, float | None, str, str, str]] = field(default_factory=list)
    detected: list[tuple[int, float | None, str, float]] = field(default_factory=list)
    shortsil: list[tuple[int, float | None, str, float]] = field(default_factory=list)
    driftstats: list[str] = field(default_factory=list)


def _parse_kv(payload: str) -> dict[str, str]:
    return {k: v for k, v in RE_KV.findall(payload)}


def parse_log(path: str) -> ParsedLog:
    """로그 1개를 훑어 프로브·방출·언어전환을 라인순으로 수집한다."""
    out = ParsedLog(path=path)
    last_t: float | None = None
    locked_now: str | None = None
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, start=1):
            m = RE_SOTPROBE.search(line)
            if m:
                kv = _parse_kv(m.group(1))
                vals: dict[str, float] = {}
                for f in FLOAT_FIELDS:
                    raw = kv.get(f)
                    if raw is None:
                        continue
                    try:
                        vals[f] = float(raw)
                    except ValueError:
                        continue  # 'nan' 등
                lk = kv.get("locked")
                lk = None if lk in (None, "None") else lk
                locked_now = lk
                t = vals.get("t_abs")
                if t is not None:
                    last_t = t
                out.probes.append(Probe(
                    lineno=i,
                    batch=int(kv.get("batch", "0")),
                    t_abs=t if t is not None else float("nan"),
                    locked=lk,
                    seglen=vals.get("seglen", float("nan")),
                    vals=vals,
                ))
                continue

            m = RE_LANGSWITCH.search(line)
            if m:
                out.switches.append((i, last_t, m.group(1), m.group(2), m.group(3)))
                continue

            m = RE_DETECTED.search(line)
            if m:
                out.detected.append((i, last_t, m.group(1), float(m.group(2))))
                continue

            m = RE_SHORTSIL.search(line)
            if m:
                out.shortsil.append((i, last_t, m.group(2), float(m.group(3))))
                continue

            m = RE_DRIFTSTATS.search(line)
            if m:
                out.driftstats.append(m.group(1).strip())
                continue

            m = RE_OUTPUT.search(line)
            if m:
                text = m.group(1).rstrip("\n")
                if not text.strip():
                    continue
                out.emissions.append(Emission(i, text.strip(), last_t, locked_now))
    return out


# --- 창(window) 처리 -----------------------------------------------------------

@dataclass
class Window:
    name: str
    start: float
    end: float

    def contains(self, t: float) -> bool:
        return self.start <= t <= self.end


def parse_window(spec: str) -> Window:
    """'NAME:START-END' (t_abs 초) 파싱."""
    try:
        name, rng = spec.split(":", 1)
        lo, hi = rng.split("-", 1)
        return Window(name.strip(), float(lo), float(hi))
    except Exception as e:
        raise SystemExit(f"[에러] 창 형식이 잘못됨: {spec!r} (기대: NAME:START-END)") from e


# --- 통계 ----------------------------------------------------------------------

def quantile(xs: list[float], q: float) -> float:
    """정렬된 표본에서 최근접 순위 분위수 (외부 의존성 없이)."""
    if not xs:
        return float("nan")
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[idx]


def describe(xs: list[float]) -> str:
    if not xs:
        return "n=0 (없음)"
    s = sorted(xs)
    return (f"n={len(s)} min={s[0]:.4f} q25={quantile(s, .25):.4f} "
            f"med={statistics.median(s):.4f} q75={quantile(s, .75):.4f} "
            f"q90={quantile(s, .90):.4f} max={s[-1]:.4f}")


def sweep_threshold(target: list[float], control: list[float]) -> list[tuple[float, int, int]]:
    """문턱별 (표적 검출수, 대조 발동수)를 낸다 — 분리 가능한 τ 가 있는지 본다."""
    rows = []
    for tau in (0.5, 0.7, 0.8, 0.9, 0.95, 0.97, 0.99, 0.995, 0.999):
        rows.append((tau,
                     sum(1 for x in target if x >= tau),
                     sum(1 for x in control if x >= tau)))
    return rows


# --- 리포트 --------------------------------------------------------------------

def signal_series(probes: list[Probe], key: str) -> list[float]:
    if key == "p_opp":
        return [p.p_opp for p in probes if p.p_opp is not None]
    return [p.vals[key] for p in probes if key in p.vals]


SIGNALS = ("p_opp", "resid", "H_lang", "p_abs_ko", "p_abs_en",
           "p_nospeech", "p_translate", "p_ko", "p_en")


def report_discrimination(targets: dict[str, list[Probe]], control: list[Probe],
                          extra_controls: dict[str, list[Probe]]) -> None:
    print("\n" + "=" * 78)
    print("## 1. 신호별 판별력 — 표적 창 vs 대조 창")
    print("=" * 78)
    tgt_all = [p for ps in targets.values() for p in ps]
    for key in SIGNALS:
        t = signal_series(tgt_all, key)
        c = signal_series(control, key)
        print(f"\n[{key}]")
        print(f"  표적(전체): {describe(t)}")
        print(f"  대조(그외): {describe(c)}")
        for cname, cps in extra_controls.items():
            print(f"  대조[{cname}]: {describe(signal_series(cps, key))}")
        for name, ps in targets.items():
            print(f"  표적[{name}]: {describe(signal_series(ps, key))}")
        if t and c:
            print(f"  문턱 스윕 (τ: 표적검출/{len(t)}, 대조발동/{len(c)}):")
            for tau, nt, nc in sweep_threshold(t, c):
                print(f"    τ>={tau:<6} 표적 {nt:3d}/{len(t):<3d} ({100*nt/len(t):5.1f}%)  "
                      f"대조 {nc:3d}/{len(c):<3d} ({100*nc/len(c):5.1f}%)")


def _emissions_between(log: ParsedLog, lo: int, hi: int) -> list[Emission]:
    """라인번호 (lo, hi) 사이의 방출. hi=None 이면 lo 직후 하나의 프로브 구간만."""
    return [e for e in log.emissions if lo < e.lineno < hi]


def report_preemption(log: ParsedLog, targets: dict[str, Window], lead_s: float,
                      tau: float) -> None:
    print("\n" + "=" * 78)
    print(f"## 2. 선제성 — 표적 창 시작 {lead_s:g}s 전부터의 신호 궤적 (τ={tau})")
    print("=" * 78)
    print("주: locked=None 구간은 p_opp 가 미정의라 원시 p_ko/p_en 을 함께 보여준다.")
    print("    잠금이 '적용되기 직전'의 프로브가 이미 반대 언어를 말하는지가 선제성의 핵심.")
    for name, w in targets.items():
        print(f"\n### 표적 {name}: t_abs {w.start}-{w.end}s")
        runup = [p for p in log.probes if (w.start - lead_s) <= p.t_abs <= w.end]
        if not runup:
            print("  (창 내 프로브 없음)")
            continue
        in_win_em = [e for e in log.emissions
                     if e.t_abs is not None and w.contains(e.t_abs)]
        first_em = in_win_em[0] if in_win_em else None
        first_em_t = first_em.t_abs if first_em else None
        first_fire = next((p for p in runup if p.p_opp is not None and p.p_opp >= tau), None)
        print(f"  창 내 첫 방출(=실패 커밋 시점): t={first_em_t}s "
              f"'{first_em.text if first_em else '—'}'")
        if first_fire is None:
            print(f"  ** τ={tau} 초과 p_opp 프로브가 창(+lead) 안에 없음 → 선제 검출 실패")
        else:
            print(f"  첫 p_opp τ 돌파: batch={first_fire.batch} t={first_fire.t_abs:.2f}s "
                  f"locked={first_fire.locked} p_opp={first_fire.p_opp:.4f} @L{first_fire.lineno}")
            if first_em_t is not None:
                lead = first_em_t - first_fire.t_abs
                verdict = "선제(이전)" if lead > 0 else ("동시" if lead == 0 else "지연(사후)")
                print(f"  → 첫 방출 대비 {lead:+.2f}s ({verdict})")
        # locked=None 도 포함해, '틀린 쪽 언어가 우세'한 최초 프로브 (잠금 적용 전 경보 가능성)
        lock_lang = first_fire.locked if first_fire else None
        if lock_lang:
            other = "p_ko" if lock_lang == "en" else "p_en"
            early = next((p for p in runup
                          if p.vals.get(other, 0.0) >= tau), None)
            if early is not None and first_em_t is not None:
                lead = first_em_t - early.t_abs
                print(f"  [잠금 무관] {other}>={tau} 최초: batch={early.batch} "
                      f"t={early.t_abs:.2f}s locked={early.locked} "
                      f"{other}={early.vals.get(other):.4f} → 첫 방출 대비 {lead:+.2f}s")
        print("  궤적 (batch t_abs locked p_opp p_ko p_en resid H_lang):")
        for idx, p in enumerate(runup):
            po = p.p_opp
            pos = f"{po:.4f}" if po is not None else " n/a  "
            mark = " <<<" if po is not None and po >= tau else ""
            print(f"    b{p.batch:<4d} t={p.t_abs:7.2f} lk={str(p.locked):<4} "
                  f"p_opp={pos} ko={p.vals.get('p_ko', float('nan')):.4f} "
                  f"en={p.vals.get('p_en', float('nan')):.4f} "
                  f"resid={p.vals.get('resid', float('nan')):.4f} "
                  f"H={p.vals.get('H_lang', float('nan')):.4f}{mark}")
            hi = runup[idx + 1].lineno if idx + 1 < len(runup) else p.lineno + 400
            for e in _emissions_between(log, p.lineno, hi):
                print(f"           └ Output: {e.text!r}")
            for s in log.switches:
                if p.lineno < s[0] < hi:
                    print(f"           └ LangSwitch → {s[2]} (prev={s[3]}, switch={s[4]})")


def report_lock_decisions(log: ParsedLog, tau: float) -> None:
    """언어잠금이 *적용되는 순간* 직전 프로브가 그 결정에 동의했는지 — veto 가능성 측정.

    실패 예방의 실제 개입 지점은 방출이 아니라 '잠금 결정'이다. 결정 직전 프로브가
    적용될 언어의 반대를 tau 이상으로 말하고 있었다면, 그 지점에서 veto/재감지가 가능했다.
    """
    print("\n" + "=" * 78)
    print(f"## 2b. 잠금 결정 시점의 프로브 동의 여부 (veto 가능성, τ={tau})")
    print("=" * 78)
    print("각 [LangSwitch] 직전 프로브의 '적용될 언어' 확률. 낮으면 그 잠금은 프로브와 배치된다.")
    n_dis = 0
    for lineno, _t, applied, prev, switched in log.switches:
        prior = [p for p in log.probes if p.lineno < lineno]
        if not prior:
            continue
        p = prior[-1]
        key_applied = f"p_{applied}"
        p_app = p.vals.get(key_applied)
        if p_app is None:
            continue
        disagree = p_app <= (1.0 - tau)
        if disagree:
            n_dis += 1
        flag = "  <<< 배치(veto 후보)" if disagree else ""
        print(f"  L{lineno:<6d} 적용={applied} (prev={prev}, switch={switched}) "
              f"| 직전 프로브 b{p.batch} t={p.t_abs:.2f} locked={p.locked} "
              f"p_{applied}={p_app:.4f}{flag}")
    print(f"\n  → 프로브와 배치되는 잠금 결정: {n_dis}/{len(log.switches)}")


def report_mismatch(log: ParsedLog, targets: dict[str, Window], tau: float,
                    context_em: int) -> None:
    print("\n" + "=" * 78)
    print(f"## 3. mismatch 후보 전수 (p_opp >= {tau}) — 정당/오탐 분류용")
    print("=" * 78)
    cands = [p for p in log.probes if p.p_opp is not None and p.p_opp >= tau]
    print(f"총 {len(cands)}건 (계측 코드 카운터와 대조할 것)\n")
    # 인접 배치를 하나의 '버스트'로 묶어 사람이 읽기 쉽게 한다.
    bursts: list[list[Probe]] = []
    for p in cands:
        if bursts and p.batch - bursts[-1][-1].batch <= 2:
            bursts[-1].append(p)
        else:
            bursts.append([p])
    print(f"연속 배치를 묶으면 {len(bursts)}개 버스트:\n")
    for bi, b in enumerate(bursts, 1):
        t0, t1 = b[0].t_abs, b[-1].t_abs
        tags = [n for n, w in targets.items()
                if any(w.contains(p.t_abs) for p in b)]
        tag = f" [표적 {','.join(tags)}]" if tags else ""
        ps = [p.p_opp for p in b if p.p_opp is not None]
        print(f"버스트 {bi}: batch {b[0].batch}-{b[-1].batch} t={t0:.2f}-{t1:.2f}s "
              f"locked={b[0].locked} n={len(b)} p_opp med={statistics.median(ps):.4f} "
              f"max={max(ps):.4f}{tag}")
        lo, hi = b[0].lineno, b[-1].lineno
        before = [e for e in log.emissions if e.lineno < lo][-context_em:]
        inside = [e for e in log.emissions if lo <= e.lineno <= hi]
        after = [e for e in log.emissions if e.lineno > hi][:context_em]
        print(f"    직전 방출: {' | '.join(repr(e.text) for e in before) or '—'}")
        print(f"    버스트 내: {' | '.join(repr(e.text) for e in inside) or '—'}")
        print(f"    직후 방출: {' | '.join(repr(e.text) for e in after) or '—'}")
        sw = [s for s in log.switches if lo - 40 <= s[0] <= hi + 40]
        if sw:
            print(f"    인접 LangSwitch: {[(s[2], f'prev={s[3]}', f'switch={s[4]}') for s in sw]}")
        print()


def report_resid(log: ParsedLog, targets: dict[str, list[Probe]], control: list[Probe]) -> None:
    print("\n" + "=" * 78)
    print(f"## 4. high_resid 문턱({RESID_HIGH}) 해석")
    print("=" * 78)
    allr = signal_series(log.probes, "resid")
    n_hi = sum(1 for x in allr if x >= RESID_HIGH)
    print(f"전체 프로브 resid: {describe(allr)}")
    print(f"  resid >= {RESID_HIGH}: {n_hi}/{len(allr)} ({100*n_hi/len(allr):.0f}%) "
          f"→ 문턱이 다수 배치를 통과시키면 판별력 없음")
    tgt = [p for ps in targets.values() for p in ps]
    tr = signal_series(tgt, "resid")
    cr = signal_series(control, "resid")
    print(f"  표적 resid: {describe(tr)}")
    print(f"  대조 resid: {describe(cr)}")
    if tr and cr:
        print("  표적을 가르는 다른 resid 문턱이 있는가 (표적검출 / 대조발동):")
        for tau in (0.45, 0.5, 0.55, 0.6, 0.7, 0.8, 0.9):
            nt = sum(1 for x in tr if x >= tau)
            nc = sum(1 for x in cr if x >= tau)
            print(f"    resid>={tau:<5} 표적 {nt:3d}/{len(tr):<3d} ({100*nt/len(tr):5.1f}%)  "
                  f"대조 {nc:3d}/{len(cr):<3d} ({100*nc/len(cr):5.1f}%)")
        print("  (표적 비율이 대조 비율보다 뚜렷이 높아야 판별력 있음)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True, help="분석할 서버 로그 파일 경로")
    ap.add_argument("--target", action="append", default=[],
                    help="표적 창 'NAME:START-END' (t_abs 초). 반복 가능")
    ap.add_argument("--control-window", action="append", default=[],
                    help="따로 보고할 대조 창 'NAME:START-END'. 반복 가능")
    ap.add_argument("--guard", type=float, default=3.0,
                    help="표적 창 앞뒤 이 초만큼은 대조에서 제외 (기본 3.0)")
    ap.add_argument("--lead", type=float, default=6.0,
                    help="선제성 분석에서 표적 시작 전 몇 초까지 볼지 (기본 6.0)")
    ap.add_argument("--tau", type=float, default=MISMATCH_P,
                    help=f"p_opp 발동 문턱 (기본 {MISMATCH_P} = 계측 코드 상수)")
    ap.add_argument("--context-em", type=int, default=3,
                    help="mismatch 버스트 앞뒤로 보여줄 방출 개수 (기본 3)")
    ap.add_argument("--list-mismatch", action="store_true",
                    help="mismatch 전수 열거만 수행 (표적 창 없이 오탐 스캔용)")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not os.path.exists(args.log):
        print(f"[에러] 로그 없음: {args.log}", file=sys.stderr)
        return 2

    log = parse_log(args.log)
    print(f"# 로그: {args.log}")
    print(f"# 프로브 {len(log.probes)}개 · 방출 {len(log.emissions)}개 · "
          f"LangSwitch {len(log.switches)}회 · Detected {len(log.detected)}회 · "
          f"ShortSilence {len(log.shortsil)}회")
    if log.probes:
        print(f"# t_abs 범위: {log.probes[0].t_abs:.2f} ~ {log.probes[-1].t_abs:.2f}s")
    locks = {"ko": 0, "en": 0, "none": 0}
    for p in log.probes:
        locks[p.locked if p.locked in ("ko", "en") else "none"] += 1
    print(f"# locked 분포: ko={locks['ko']} en={locks['en']} none={locks['none']}")
    if log.driftstats:
        print(f"# 최종 [LangDriftStats]: {log.driftstats[-1]}")

    targets = {w.name: w for w in (parse_window(s) for s in args.target)}
    ctrl_wins = {w.name: w for w in (parse_window(s) for s in args.control_window)}

    tgt_probes = {n: [p for p in log.probes if w.contains(p.t_abs)]
                  for n, w in targets.items()}
    control = [p for p in log.probes
               if not any(w.start - args.guard <= p.t_abs <= w.end + args.guard
                          for w in targets.values())]
    extra_ctrl = {n: [p for p in log.probes if w.contains(p.t_abs)]
                  for n, w in ctrl_wins.items()}

    if targets and not args.list_mismatch:
        for n, ps in tgt_probes.items():
            print(f"# 표적 {n}: 프로브 {len(ps)}개")
        print(f"# 대조(표적±{args.guard}s 제외): 프로브 {len(control)}개")
        report_discrimination(tgt_probes, control, extra_ctrl)
        report_preemption(log, targets, args.lead, args.tau)
        report_lock_decisions(log, args.tau)
        report_resid(log, tgt_probes, control)

    report_mismatch(log, targets, args.tau, args.context_em)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
