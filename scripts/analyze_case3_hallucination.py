# -*- coding: utf-8 -*-
"""CASE3 환각 폭주 진단 분석기 (측정용, 코드 무수정).

`analyze_case2_frontloss.py`(서버로그 파싱 패턴)를 참고하되, CASE3는 "환각이 실제로
최종 출력에 남았는가"를 직접 셀 수 있어야 하므로 **서버 로그 + 전사(transcript) 텍스트**를
함께 분석한다.

핵심 방법론(중요 — 두 데이터 소스의 역할이 다르다):
  - **서버 로그**(`.omc/server_logs/server_*.log`)는 "필터가 개입을 시도한 이벤트"만
    남긴다 — QualityGate 억제, ScriptMismatchFilter/ForeignLang/BatchRepeatFilter 드롭 등.
    이 로그에 잡힌 텍스트는 **최종 출력에서 이미 제거된** 것들이다.
  - **전사(transcript) 텍스트**(`.omc/transcripts/*.txt`)는 모든 필터를 통과해 **실제로
    사용자가 보는 최종 출력**이다. 여기서 검출되는 반복 시퀀스(예: "Thank you"가 4연속)는
    **어떤 필터도 못 잡은(=현재 방어선의 사각지대) 환각**이다.
  → 따라서 "환각 발생률"의 1차 지표는 **전사 텍스트의 반복 n-gram 카운트**(사용자에게
    실제로 노출된 환각)이고, 서버 로그 카운트는 "기존 방어선이 몇 번 개입을 시도했는가"
    라는 보조 지표다. 둘을 같이 봐야 "방어선이 잡아낸 것 vs 뚫고 나온 것"을 구분할 수 있다.

⚠️ 범위와 한계: 전사 텍스트는 `scripts/eval.py`가 `hyp_sentences`를 공백으로 이어붙인
평문(flatten)이라 타임스탬프·화자 경계 정보가 없다(MEMORY `eval-transcript-txt-flattening`
참고). 따라서 "이 반복 시퀀스가 정확히 몇 초 지점에서 어떤 화자전환과 관련됐는가"는 전사만
으로는 확정할 수 없다 — 그건 서버 로그의 `[NewSpeaker]`/`[EndSilence]` 이벤트와 **파일
단위(세밀한 위치 아님)**로만 상호참조 가능하다. 아래 "게이트 커버리지" 절은 이 한계 안에서
"이 로그 파일에 화자전환 자체가 있었는가"·"Req-2 게이트(ScriptMismatchFilter)가 이 로그에서
몇 번 발동했는가"만 답한다.

집계 대상 신호:

  A. 전사 기반 — 반복 환각 시퀀스 (언어 무관, 특정 문구 하드코딩 없음, §3.8 준수):
     `find_ngram_repeat_runs`: 단어를 1~4-gram으로 나눠 **연속(non-overlapping) 동일
     n-gram이 min_run(기본 3)회 이상 반복**되는 구간을 탐지한다(큰 n부터 우선 소비해
     겹치는 하위 n-gram 이중 계산 방지). 예: "thank you thank you thank you" → n=2,
     repeat_count=3. 이 반복 구간에 포함된 단어 수 합계 / 전체 단어 수 = 반복 단어 비율.
     `sliding_ttr_collapse`: 슬라이딩 윈도우(기본 20단어, step 10)의 타입-토큰 비율이
     문턱(기본 0.6 — backend.py `_SCRIPT_MISMATCH_TTR_THRESHOLD`와 동일 철학) 이하로
     붕괴한 구간을 탐지한다. n-gram 반복 탐지가 못 잡는 "느슨한 변주"(완전동일은 아니지만
     어휘가 몇 개로 좁게 맴도는) 반복까지 보조로 잡는다.

  B. 로그 기반 — 기존 방어선 개입 이벤트(모두 `backend.py` 로그 문자열 기준):
     `[ScriptMismatchFilter] lang=%s 반대스크립트 반복 세그먼트 드롭: ...` (Exp-168 P2 게이트)
     `[ForeignLang] '(speaking in foreign language)' 감지` + `드롭 텍스트: ...`
     `[BatchRepeatFilter] 배치 내 반복 %r ×%d — 배치 드롭+리셋`
     `[HallucinationFilter] 환각 루프 임계치 초과 — context 리셋 (count=%d)`
     `[CrossBatchFilter] 반복 제거: %r (prev=%r)`
     `[QualityGate] avg_logprob %.3f < %.3f — suppressing: ...`
     `[QualityGate] compression_ratio %.2f > %.2f — suppressing: ...`
     `[QualityGate] %d consecutive suppressions — refresh_segment`
     `SimulStreaming stall recovery: %.1fs without output`
     `[NewSpeaker] spk=%s→%s det_before=%s eager=%s` / `[NewSpeaker] spk=%s det_after=%s (eager_applied=%s)`
       — Req-2 게이트가 실제 통과하는 유일한 진입로(`new_speaker()`) 호출 여부/횟수.
         화자전환이 없는 파일(예: sbs1, 확인된 단일화자)은 이 이벤트가 0건이며, 이는
         "게이트가 못 잡음"이 아니라 "게이트가 애초에 호출될 수 없는 구조"임을 뜻한다.

사용:
    python scripts/analyze_case3_hallucination.py \
        --logs ".omc/server_logs/server_bong1_C_*.log" \
        --transcripts ".omc/transcripts/bong1_C_R*.txt"
    python scripts/analyze_case3_hallucination.py --transcripts ".omc/transcripts/*.txt" --per-file
"""

import argparse
import glob
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── 전사(transcript) 반복 탐지 파라미터 ────────────────────────────────────────
# backend.py `_WORD_TOKEN_PATTERN`과 동일 철학(언어 무관 — 라틴 알파벳 단어 or 한글 어절
# 단위 토큰화). 구두점/숫자는 반복판정에서 제외한다(구두점 변주로 반복이 은폐되는 것 방지).
_WORD_TOKEN_PATTERN = re.compile(r"[A-Za-z']+|[가-힣]+")
DEFAULT_MAX_NGRAM = 4
DEFAULT_MIN_REPEAT_RUN = 3
# 실측(bong1 웃음구간 "Thank you very much. Thank you. Thank you The Rock.")에서 확인된 필러
# 패턴 — 반복되는 n-gram 사이에 짧은 변주(예: "very much")가 끼어 완전 무간격(gap=0)
# 인접이 아닌 경우가 실제로 더 흔하다(Req-2 조사에서도 "매회 다른 변주"로 이미 관측됨).
# 따라서 같은 n-gram의 다음 occurrence가 gap(중간 비반복 단어 수) 이내에 있으면 같은
# storm으로 묶는다. 너무 크면 문단 전체에 걸쳐 자연스럽게 재등장하는 정상 어구까지
# 오탐할 위험이 있어 작은 값으로 제한한다(오탐 방지 우선, §3.8 일반화 원칙).
DEFAULT_MAX_GAP = 3
DEFAULT_TTR_WINDOW = 20
DEFAULT_TTR_STEP = 10
DEFAULT_TTR_THRESHOLD = 0.6  # backend.py _SCRIPT_MISMATCH_TTR_THRESHOLD와 동일값(철학 일치)

# 실측(bong1) 오탐 사례에서 확인된 함정: 흔한 기능어(예: 영어 "the")는 gap-tolerant
# 클러스터링만으로는 문단 전체에 걸쳐 자연스럽게 재등장하는 것과 국소 환각 폭주를
# 구분 못한다("the"가 28단어 중 5회 뭉쳐 나온 것은 정상 — 문서 전체 28회 중 일부일 뿐).
# 반대로 진짜 환각(예: "김정은"류 반복)은 해당 n-gram의 전체 등장이 **거의 전부 이
# 클러스터 안에 집중**된다(문서 다른 곳엔 안 나타남). 이 비율(local concentration =
# 클러스터 반복횟수 / 문서 전체 등장횟수)이 낮으면(즉 이 단어/구가 문서 전반에 흔함)
# 오탐으로 보고 storm에서 제외한다. 특정 단어 하드코딩이 아니라 문서 내부 통계만
# 사용하므로 언어·어휘 무관(§3.8 준수).
DEFAULT_MIN_CONCENTRATION = 0.5

# 로그↔전사 상호참조: NewSpeaker 없이 발생한 드롭/환각은 "화자전환-무관"으로 분류.
NEAR_SPEAKER_CHANGE_LINE_WINDOW = 30  # 이 라인 수 이내에 NewSpeaker가 있으면 "인접"으로 분류


def tokenize(text: str) -> List[str]:
    """언어 무관 단어 토큰화(소문자화). 구두점/숫자 제거."""
    return [w.lower() for w in _WORD_TOKEN_PATTERN.findall(text)]


@dataclass
class RepeatRun:
    n: int
    start_word_idx: int
    end_word_idx: int  # 배타적 상한
    repeat_count: int
    ngram: str

    @property
    def n_words_consumed(self) -> int:
        return self.end_word_idx - self.start_word_idx


def _global_ngram_counts(words: List[str], n: int) -> Counter:
    """words 전체(커버 상태 무관)에서 길이 n 슬라이딩 n-gram의 전체 등장 횟수."""
    return Counter(tuple(words[k:k + n]) for k in range(len(words) - n + 1))


def find_ngram_repeat_runs(
    words: List[str], max_n: int = DEFAULT_MAX_NGRAM, min_run: int = DEFAULT_MIN_REPEAT_RUN,
    max_gap: int = DEFAULT_MAX_GAP, min_concentration: float = DEFAULT_MIN_CONCENTRATION,
) -> List[RepeatRun]:
    """단어 리스트에서 반복되는 n-gram 구간(gap-tolerant + 국소집중도 필터)을 찾는다.

    n=max_n부터 내림차순으로 스캔하고, 이미 탐지된 구간의 단어는 "소비됨"으로 표시해
    더 작은 n으로 재탐지하지 않는다(예: "thank you"×3을 n=2로 잡았으면 그 구간을 다시
    n=1 "thank"×3, "you"×3 으로 이중 계산하지 않음). 특정 언어·문구 하드코딩 없음(§3.8).

    같은 n-gram의 다음 occurrence가 `max_gap` 단어 이내(비반복 단어 최대 개수)에 있으면
    같은 반복 클러스터로 묶는다(무간격 완전인접만 요구하면 실측 필러의 흔한 변주
    — 예: "Thank you|very much|Thank you|Thank you" — 를 놓친다).

    국소집중도 필터: 클러스터의 반복횟수가 그 n-gram의 **문서 전체 등장횟수**의
    `min_concentration` 비율 미만이면 storm에서 제외한다. 흔한 기능어(예: 영어 "the")는
    문서 전체에 걸쳐 자연스럽게 여러 번 나타나다 우연히 몇 개가 가까이 모일 수 있는데,
    이런 경우는 그 단어 전체 등장 중 일부만 이 클러스터에 속한다(집중도 낮음) — 진짜
    환각 필러(예: 특정 고유명사·구문이 반복 구간에만 몰림, 문서 다른 곳엔 없음)와 다르다.
    """
    N = len(words)
    covered = [False] * N
    runs: List[RepeatRun] = []
    for n in range(max_n, 0, -1):
        global_counts = _global_ngram_counts(words, n)
        i = 0
        while i + n <= N:
            if any(covered[i:i + n]):
                i += 1
                continue
            gram = tuple(words[i:i + n])
            cluster_start = i
            cur = i + n
            count = 1
            while True:
                search_limit = min(N, cur + max_gap + n)
                found = None
                j = cur
                while j + n <= search_limit:
                    if not any(covered[j:j + n]) and tuple(words[j:j + n]) == gram:
                        found = j
                        break
                    j += 1
                if found is None:
                    break
                count += 1
                cur = found + n
            total_in_doc = global_counts.get(gram, count)
            concentration = count / total_in_doc if total_in_doc else 1.0
            if count >= min_run and concentration >= min_concentration:
                runs.append(RepeatRun(
                    n=n, start_word_idx=cluster_start, end_word_idx=cur, repeat_count=count,
                    ngram=" ".join(gram),
                ))
                for k in range(cluster_start, cur):
                    covered[k] = True
                i = cur
            else:
                i += 1
    runs.sort(key=lambda r: r.start_word_idx)
    return runs


def sliding_ttr_collapse(
    words: List[str], window: int = DEFAULT_TTR_WINDOW, step: int = DEFAULT_TTR_STEP,
    threshold: float = DEFAULT_TTR_THRESHOLD,
) -> List[dict]:
    """슬라이딩 윈도우 타입-토큰 비율이 threshold 이하로 붕괴하는 구간을 찾는다.

    n-gram 정확반복 탐지(find_ngram_repeat_runs)가 놓치는 "느슨한 변주"(어휘가 몇 개
    안에서 맴도는) 반복까지 보조로 잡는 목적. window보다 단어가 적으면 빈 리스트 반환.
    """
    N = len(words)
    if N < window:
        return []
    collapsed = []
    i = 0
    while i + window <= N:
        chunk = words[i:i + window]
        ttr = len(set(chunk)) / len(chunk)
        if ttr <= threshold:
            collapsed.append({"start_word_idx": i, "end_word_idx": i + window, "ttr": ttr})
        i += step
    return collapsed


def summarize_transcript(text: str, max_n: int = DEFAULT_MAX_NGRAM,
                          min_run: int = DEFAULT_MIN_REPEAT_RUN, max_gap: int = DEFAULT_MAX_GAP,
                          min_concentration: float = DEFAULT_MIN_CONCENTRATION,
                          ttr_window: int = DEFAULT_TTR_WINDOW, ttr_step: int = DEFAULT_TTR_STEP,
                          ttr_threshold: float = DEFAULT_TTR_THRESHOLD) -> Dict:
    words = tokenize(text)
    runs = find_ngram_repeat_runs(words, max_n=max_n, min_run=min_run, max_gap=max_gap,
                                   min_concentration=min_concentration)
    ttr_windows = sliding_ttr_collapse(words, window=ttr_window, step=ttr_step, threshold=ttr_threshold)
    repeated_words = sum(r.n_words_consumed for r in runs)
    n_words = len(words)
    overall_ttr = len(set(words)) / n_words if n_words else None
    return {
        "n_words": n_words,
        "overall_ttr": overall_ttr,
        "repeat_runs": runs,
        "storm_count": len(runs),
        "max_repeat_count": max((r.repeat_count for r in runs), default=0),
        "repeated_word_total": repeated_words,
        "repeated_word_ratio": (repeated_words / n_words) if n_words else None,
        "ttr_collapsed_windows": ttr_windows,
    }


# ─── 서버 로그 파싱 ────────────────────────────────────────────────────────────
_SCRIPT_MISMATCH_RE = re.compile(r"\[ScriptMismatchFilter\] lang=(\S+) 반대스크립트 반복 세그먼트 드롭: (.*)$")
_FOREIGNLANG_DETECT_RE = re.compile(r"\[ForeignLang\] '\(speaking in foreign language\)' 감지")
_FOREIGNLANG_DROPPED_RE = re.compile(r"\[ForeignLang\] 드롭 텍스트: (.*)$")
_BATCHREPEAT_RE = re.compile(r"\[BatchRepeatFilter\] 배치 내 반복 (.+) ×(\d+) — 배치 드롭\+리셋")
_HALLUC_RESET_RE = re.compile(r"\[HallucinationFilter\] 환각 루프 임계치 초과 — context 리셋 \(count=(\d+)\)")
_CROSSBATCH_RE = re.compile(r"\[CrossBatchFilter\] 반복 제거: (.+) \(prev=(.+)\)\s*$")
_QG_LOGPROB_RE = re.compile(r"\[QualityGate\] avg_logprob ([\-\d.]+) < ([\-\d.]+) — suppressing: (.*)$")
_QG_CR_RE = re.compile(r"\[QualityGate\] compression_ratio ([\d.]+) > ([\d.]+) — suppressing: (.*)$")
_QG_REFRESH_RE = re.compile(r"\[QualityGate\] (\d+) consecutive suppressions — refresh_segment")
_STALL_RE = re.compile(r"SimulStreaming stall recovery: ([\d.]+)s without output")
_NEWSPEAKER_BEFORE_RE = re.compile(r"\[NewSpeaker\] spk=(\S+)→(\S+) det_before=(\S+) eager=(\S+)")
_NEWSPEAKER_AFTER_RE = re.compile(r"\[NewSpeaker\] spk=(\S+) det_after=(\S+) \(eager_applied=(\S+)\)")
_TRACE_TOKENS_ON_RE = re.compile(r"\[TraceTokens\] DEBUG 레벨 로깅 활성화")
_OUTPUT_LINE_RE = re.compile(r"\bOutput: ")
_TENSOR_MISMATCH_RE = re.compile(r"SimulStreaming processing error:")


@dataclass
class DropEvent:
    line_no: int
    kind: str
    detail: str


@dataclass
class LogResult:
    path: str
    n_lines: int = 0
    trace_tokens_on: bool = False
    output_count: int = 0
    tensor_mismatch_count: int = 0
    drop_events: List[DropEvent] = field(default_factory=list)
    quality_gate_suppressions: int = 0
    quality_gate_refreshes: List[int] = field(default_factory=list)
    stall_recoveries: List[float] = field(default_factory=list)
    cross_batch_drops: int = 0
    new_speaker_lines: List[int] = field(default_factory=list)
    new_speaker_eager_applied: int = 0


def parse_log(path: str, lines: List[str]) -> LogResult:
    r = LogResult(path=path, n_lines=len(lines))
    for i, line in enumerate(lines, start=1):
        if _TRACE_TOKENS_ON_RE.search(line):
            r.trace_tokens_on = True
            continue
        if _OUTPUT_LINE_RE.search(line):
            r.output_count += 1
            continue
        if _TENSOR_MISMATCH_RE.search(line):
            r.tensor_mismatch_count += 1
            continue

        m = _SCRIPT_MISMATCH_RE.search(line)
        if m:
            r.drop_events.append(DropEvent(i, "script_mismatch", m.group(2).strip()))
            continue

        if _FOREIGNLANG_DETECT_RE.search(line):
            r.drop_events.append(DropEvent(i, "foreign_lang_detect", ""))
            continue
        m = _FOREIGNLANG_DROPPED_RE.search(line)
        if m:
            r.drop_events.append(DropEvent(i, "foreign_lang_dropped_text", m.group(1).strip()))
            continue

        m = _BATCHREPEAT_RE.search(line)
        if m:
            r.drop_events.append(DropEvent(i, "batch_repeat", f"{m.group(1).strip()} x{m.group(2)}"))
            continue

        m = _HALLUC_RESET_RE.search(line)
        if m:
            r.drop_events.append(DropEvent(i, "hallucination_reset", f"count={m.group(1)}"))
            continue

        m = _CROSSBATCH_RE.search(line)
        if m:
            r.cross_batch_drops += 1
            continue

        m = _QG_LOGPROB_RE.search(line)
        if m:
            r.quality_gate_suppressions += 1
            r.drop_events.append(DropEvent(i, "quality_gate_logprob", m.group(3).strip()))
            continue
        m = _QG_CR_RE.search(line)
        if m:
            r.quality_gate_suppressions += 1
            r.drop_events.append(DropEvent(i, "quality_gate_cr", m.group(3).strip()))
            continue
        m = _QG_REFRESH_RE.search(line)
        if m:
            r.quality_gate_refreshes.append(int(m.group(1)))
            continue

        m = _STALL_RE.search(line)
        if m:
            r.stall_recoveries.append(float(m.group(1)))
            continue

        if _NEWSPEAKER_BEFORE_RE.search(line):
            r.new_speaker_lines.append(i)
            continue
        m = _NEWSPEAKER_AFTER_RE.search(line)
        if m:
            if m.group(3) == "True":
                r.new_speaker_eager_applied += 1
            continue
    return r


def _nearest_distance(line_no: int, anchors: List[int]) -> Optional[int]:
    if not anchors:
        return None
    return min(abs(a - line_no) for a in anchors)


def summarize_log(r: LogResult) -> Dict:
    is_broken = r.tensor_mismatch_count > 0
    broken_reasons = [f"tensor mismatch {r.tensor_mismatch_count}건"] if is_broken else []
    if r.trace_tokens_on and r.output_count == 0:
        is_broken = True
        broken_reasons.append("Output 라인 0개(전사 완료 없음)")

    proximities = [
        (_nearest_distance(ev.line_no, r.new_speaker_lines), ev)
        for ev in r.drop_events
    ]
    near = [ev for d, ev in proximities if d is not None and d <= NEAR_SPEAKER_CHANGE_LINE_WINDOW]
    far_or_none = [ev for d, ev in proximities if d is None or d > NEAR_SPEAKER_CHANGE_LINE_WINDOW]

    by_kind = Counter(ev.kind for ev in r.drop_events)

    return {
        "path": r.path,
        "n_lines": r.n_lines,
        "trace_tokens_on": r.trace_tokens_on,
        "output_count": r.output_count,
        "tensor_mismatch_count": r.tensor_mismatch_count,
        "is_broken": is_broken,
        "broken_reasons": broken_reasons,
        "new_speaker_call_count": len(r.new_speaker_lines),
        "new_speaker_eager_applied": r.new_speaker_eager_applied,
        "drop_events_total": len(r.drop_events),
        "drop_events_by_kind": dict(by_kind),
        "drop_events_near_speaker_change": len(near),
        "drop_events_speaker_change_unrelated": len(far_or_none),
        "quality_gate_suppressions": r.quality_gate_suppressions,
        "quality_gate_refresh_count": len(r.quality_gate_refreshes),
        "cross_batch_drops": r.cross_batch_drops,
        "stall_recovery_count": len(r.stall_recoveries),
        "script_mismatch_drop_count": by_kind.get("script_mismatch", 0),
        "foreign_lang_drop_count": by_kind.get("foreign_lang_detect", 0),
        "batch_repeat_drop_count": by_kind.get("batch_repeat", 0),
        "hallucination_reset_count": by_kind.get("hallucination_reset", 0),
        "drop_events": r.drop_events,
    }


# ─── 파일명 규칙 매칭 (로그 ↔ 전사 상호참조용) ───────────────────────────────────
_LOG_NAME_RE = re.compile(r"server_(?P<stem>.+?)_(?P<path>[ABC])_R(?P<rep>\d+)_\d+_\d+\.log$")
_TXT_NAME_RE = re.compile(r"(?P<stem>.+?)_(?P<path>[ABC])_R(?P<rep>\d+)\.txt$")


def _extract_key(filename: str, pattern: re.Pattern) -> Optional[Tuple[str, str, str]]:
    m = pattern.search(filename.replace("\\", "/").rsplit("/", 1)[-1])
    if not m:
        return None
    return (m.group("stem"), m.group("path"), m.group("rep"))


def _load_transcript_text(path: str) -> str:
    """eval.py `_save_transcript` 포맷에서 [전사] 섹션만 추출한다."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    m = re.search(r"\[전사\]\n(.*?)\n\n\[정답\]", content, re.DOTALL)
    return m.group(1) if m else content


def _print_transcript_summary(label: str, s: Dict, detail: bool = True) -> None:
    print(label)
    print(f"  {'단어수':<30s}: {s['n_words']}")
    ttr_str = f"{s['overall_ttr']:.3f}" if s["overall_ttr"] is not None else "N/A"
    print(f"  {'전체 TTR(고유/전체)':<30s}: {ttr_str}")
    print(f"  {'반복시퀀스(storm) 수':<30s}: {s['storm_count']}")
    print(f"  {'최대 반복횟수':<30s}: {s['max_repeat_count']}")
    ratio_str = f"{s['repeated_word_ratio']:.3f}" if s["repeated_word_ratio"] is not None else "N/A"
    print(f"  {'반복단어 비율':<30s}: {ratio_str} ({s['repeated_word_total']}/{s['n_words']}단어)")
    print(f"  {'TTR붕괴 윈도우 수':<30s}: {len(s['ttr_collapsed_windows'])}")
    if detail:
        for run in s["repeat_runs"]:
            print(f"    [storm] word {run.start_word_idx}-{run.end_word_idx} "
                  f"n={run.n} ×{run.repeat_count}  ngram={run.ngram!r}")
        for w in s["ttr_collapsed_windows"]:
            print(f"    [ttr-collapse] word {w['start_word_idx']}-{w['end_word_idx']} ttr={w['ttr']:.3f}")


def _print_log_summary(label: str, s: Dict, detail: bool = True) -> None:
    print(label)
    print(f"  {'lines':<34s}: {s['n_lines']}  trace_tokens_on={s['trace_tokens_on']}")
    print(f"  {'tensor_mismatch_count':<34s}: {s['tensor_mismatch_count']}")
    print(f"  {'NewSpeaker 호출횟수(게이트 진입로)':<34s}: {s['new_speaker_call_count']} "
          f"(eager_applied={s['new_speaker_eager_applied']})")
    print(f"  {'drop_events 합계':<34s}: {s['drop_events_total']}  by_kind={s['drop_events_by_kind']}")
    print(f"  {'  ScriptMismatchFilter(Req-2 게이트)':<34s}: {s['script_mismatch_drop_count']}")
    print(f"  {'  ForeignLang':<34s}: {s['foreign_lang_drop_count']}")
    print(f"  {'  BatchRepeatFilter':<34s}: {s['batch_repeat_drop_count']}")
    print(f"  {'  HallucinationFilter(문자반복) 리셋':<34s}: {s['hallucination_reset_count']}")
    print(f"  {'  QualityGate 억제/강제refresh':<34s}: {s['quality_gate_suppressions']}/{s['quality_gate_refresh_count']}")
    print(f"  {'  CrossBatchFilter':<34s}: {s['cross_batch_drops']}")
    print(f"  {'  stall recovery':<34s}: {s['stall_recovery_count']}")
    print(f"  {'drop 이벤트 화자전환 인접/무관':<34s}: {s['drop_events_near_speaker_change']}/"
          f"{s['drop_events_speaker_change_unrelated']}  (창={NEAR_SPEAKER_CHANGE_LINE_WINDOW}라인)")
    if detail:
        for ev in s["drop_events"]:
            print(f"    line {ev.line_no} [{ev.kind}]: {ev.detail[:120]!r}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CASE3 환각 폭주 진단 분석기")
    parser.add_argument("--logs", nargs="*", default=[], help="서버 로그 경로(글로브 허용)")
    parser.add_argument("--transcripts", nargs="*", default=[], help="전사 텍스트 경로(글로브 허용)")
    parser.add_argument("--per-file", action="store_true", help="파일별 상세 출력")
    parser.add_argument("--max-ngram", type=int, default=DEFAULT_MAX_NGRAM)
    parser.add_argument("--min-repeat-run", type=int, default=DEFAULT_MIN_REPEAT_RUN)
    parser.add_argument("--max-gap", type=int, default=DEFAULT_MAX_GAP,
                         help="반복 n-gram 사이 허용 간격(단어 수, gap-tolerant 클러스터링)")
    parser.add_argument("--min-concentration", type=float, default=DEFAULT_MIN_CONCENTRATION,
                         help="클러스터 반복횟수/문서전체등장횟수 최소 비율(낮으면 흔한 기능어 오탐으로 제외)")
    parser.add_argument("--ttr-window", type=int, default=DEFAULT_TTR_WINDOW)
    parser.add_argument("--ttr-step", type=int, default=DEFAULT_TTR_STEP)
    parser.add_argument("--ttr-threshold", type=float, default=DEFAULT_TTR_THRESHOLD)
    args = parser.parse_args(argv)

    if not args.logs and not args.transcripts:
        parser.error("--logs 또는 --transcripts 중 최소 하나는 지정해야 한다.")

    def _expand(patterns: List[str]) -> List[str]:
        paths: List[str] = []
        for pat in patterns:
            expanded = glob.glob(pat)
            paths.extend(expanded if expanded else [pat])
        return paths

    log_paths = _expand(args.logs)
    txt_paths = _expand(args.transcripts)

    log_summaries: List[Dict] = []
    for path in log_paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            print(f"[skip] {path}: {e}", file=sys.stderr)
            continue
        r = parse_log(path, lines)
        s = summarize_log(r)
        log_summaries.append(s)
        if not s["trace_tokens_on"]:
            print(
                f"[경고] {path}: '[TraceTokens] DEBUG 레벨 로깅 활성화' 라인이 없음 — "
                "NewSpeaker 진입 카운트 등 info/debug 신호가 유실됐을 수 있다(warning급 신호"
                "(QualityGate/ScriptMismatchFilter/ForeignLang/BatchRepeat/HallucinationReset)는"
                "레벨과 무관하게 항상 보인다).",
                file=sys.stderr,
            )
        if args.per_file:
            _print_log_summary(f"[log:{path}]", s, detail=True)
            print()

    txt_summaries: List[Dict] = []
    for path in txt_paths:
        try:
            text = _load_transcript_text(path)
        except OSError as e:
            print(f"[skip] {path}: {e}", file=sys.stderr)
            continue
        s = summarize_transcript(
            text, max_n=args.max_ngram, min_run=args.min_repeat_run, max_gap=args.max_gap,
            min_concentration=args.min_concentration,
            ttr_window=args.ttr_window, ttr_step=args.ttr_step, ttr_threshold=args.ttr_threshold,
        )
        s["path"] = path
        txt_summaries.append(s)
        if args.per_file:
            _print_transcript_summary(f"[transcript:{path}]", s, detail=True)
            print()

    # ─── 로그↔전사 파일명 매칭 (참고용 상호참조) ─────────────────────────────────
    log_by_key = {}
    for s in log_summaries:
        key = _extract_key(s["path"], _LOG_NAME_RE)
        if key:
            log_by_key.setdefault(key, []).append(s)
    txt_by_key = {}
    for s in txt_summaries:
        key = _extract_key(s["path"], _TXT_NAME_RE)
        if key:
            txt_by_key.setdefault(key, []).append(s)

    matched_keys = sorted(set(log_by_key) & set(txt_by_key))
    if matched_keys:
        print("=" * 70)
        print(f"[로그↔전사 상호참조] {len(matched_keys)}개 (stem, path, rep) 쌍 매칭됨")
        for key in matched_keys:
            stem, path_type, rep = key
            log_s = log_by_key[key][0]
            txt_s = txt_by_key[key][0]
            print(f"  {stem} {path_type} R{rep}: "
                  f"전사 storm={txt_s['storm_count']}(최대×{txt_s['max_repeat_count']}) | "
                  f"로그 NewSpeaker호출={log_s['new_speaker_call_count']} "
                  f"ScriptMismatch드롭={log_s['script_mismatch_drop_count']} "
                  f"ForeignLang드롭={log_s['foreign_lang_drop_count']}")
            if log_s["new_speaker_call_count"] == 0 and txt_s["storm_count"] > 0:
                print("    → 이 회차는 화자전환(new_speaker) 자체가 없었음 — "
                      "잔존 환각은 Req-2 게이트 진입로 밖(화자전환-무관) 발생으로 분류.")
            elif log_s["new_speaker_call_count"] > 0 and log_s["script_mismatch_drop_count"] == 0 and txt_s["storm_count"] > 0:
                print("    → 화자전환은 있었으나 ScriptMismatchFilter 미발동 — "
                      "게이트 진입은 됐지만 조건(반대스크립트+TTR붕괴) 미충족으로 통과했을 가능성.")

    # ─── 전체 합계 ────────────────────────────────────────────────────────────
    print("=" * 70)
    if log_summaries:
        print(f"[로그 합계] {len(log_summaries)}개 파일")
        total_script_mismatch = sum(s["script_mismatch_drop_count"] for s in log_summaries)
        total_foreign = sum(s["foreign_lang_drop_count"] for s in log_summaries)
        total_batch_repeat = sum(s["batch_repeat_drop_count"] for s in log_summaries)
        total_halluc_reset = sum(s["hallucination_reset_count"] for s in log_summaries)
        total_qg = sum(s["quality_gate_suppressions"] for s in log_summaries)
        total_newspeaker = sum(s["new_speaker_call_count"] for s in log_summaries)
        print(f"  ScriptMismatchFilter(Req-2 게이트) 드롭 총합: {total_script_mismatch}")
        print(f"  ForeignLang 드롭 총합               : {total_foreign}")
        print(f"  BatchRepeatFilter 드롭 총합          : {total_batch_repeat}")
        print(f"  HallucinationFilter(문자반복) 리셋 총합: {total_halluc_reset}")
        print(f"  QualityGate 억제 총합               : {total_qg}")
        print(f"  NewSpeaker 호출 총합(게이트 진입로)  : {total_newspeaker}")
    if txt_summaries:
        print(f"[전사 합계] {len(txt_summaries)}개 파일")
        storm_counts = [s["storm_count"] for s in txt_summaries]
        max_repeats = [s["max_repeat_count"] for s in txt_summaries]
        ratios = [s["repeated_word_ratio"] for s in txt_summaries if s["repeated_word_ratio"] is not None]
        print(f"  파일당 반복시퀀스(storm) 수: 합계={sum(storm_counts)} "
              f"median={statistics.median(storm_counts):.1f} max={max(storm_counts)}")
        print(f"  파일당 최대 반복횟수(worst-case): {max(max_repeats) if max_repeats else 0}")
        if ratios:
            print(f"  반복단어 비율: median={statistics.median(ratios):.3f} max={max(ratios):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
