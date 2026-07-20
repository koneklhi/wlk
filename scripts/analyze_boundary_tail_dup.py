# -*- coding: utf-8 -*-
"""언어전환 경계 단어 유실(꼬리/서두) + 경계 중복 확정 진단 스크립트 (측정용, 코드 무수정).

`analyze_case1_boundaries.py`(서버로그 정규식 파싱 스타일) + `analyze_case3_hallucination.py`
(로그+전사 이중소스, 파일명 매칭)를 템플릿으로 삼는다. 표준 라이브러리만 사용하는 완전
오프라인 도구 — `whisperlivekit` 패키지나 `scripts/eval.py`를 import하지 않는다(기존
analyze_case*.py와 동일한 독립성 원칙).

`docs/goal_prompt/GOAL_BOUNDARY_TAIL_DUP.md` §3-2의 두 표적 지표를 산출한다:

  1. **경계별 누락 단어 수** — 정답(`test_data/<name>.txt`, `[spkN]` 헤더 canonical) 블록의
     언어(한/영 스크립트 다수결)가 인접 블록과 달라지는 지점을 "언어전환 경계"로 잡고, 그
     전후 윈도우(기본 8단어) 안의 정답 단어가 가설 전사에 살아있는지 Levenshtein 정렬로
     확인한다. 못 찾은(deletion) 단어를 "유실"로 集計하고, 경계 앞쪽(구언어 꼬리) vs 뒤쪽
     (신언어 서두)으로 나눈다. 서두 유실은 같은 로그의 `[RetractScan]` 이벤트(있으면)와
     순서 매칭해 ⓐ철회미복구(`removed>0`) / ⓑ미방출(`removed==0`)를 휴리스틱으로 태깅한다
     — **자동 태깅은 방향 신호**이며, 최종 계열 판정은 로그 원문(`[Retract]`/`[NewSpeaker]`
     세부 라인) 대조로 재확인하는 것을 권장한다(겉보기 패턴이 같아도 원인이 다를 수 있음 —
     GOAL 문서 §3-2-1 Exp-188/189 규율 준용).
  2. **인접 n-gram(2~4) 중복 재방출 카운트** — 전사(`[전사]` 섹션) 내에서 완전 인접(기본
     gap=0) 반복 n-gram을 자동 검출한다. 강조성 정상 반복("네, 네")을 보호하기 위해 n=1
     (단일 단어)은 기본 범위에서 제외한다.

사용:
    python scripts/analyze_boundary_tail_dup.py \
        --transcripts ".omc/transcripts/ytn2_C_R*.txt" ".omc/transcripts/bong1_C_R*.txt" \
        --logs ".omc/server_logs/server_ytn2_C_R*.log" ".omc/server_logs/server_bong1_C_R*.log" \
        --reference-dir test_data --per-file
"""

import argparse
import glob
import re
import statistics
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── 정답(`[spkN]` 헤더 canonical) 파싱 ──────────────────────────────────────
# eval.py의 parse_speaker_sentence_reference와 동일한 정규식/의미론이지만, 기존
# analyze_case*.py 관례(오프라인·무의존)를 지키기 위해 여기서 독립적으로 재구현한다.
_SPEAKER_HEADER_RE = re.compile(r"^\[(spk\d+)\]\s*$", re.MULTILINE)


def parse_speaker_blocks(ref_text: str) -> Optional[List[dict]]:
    """`[spkN]` 헤더 신형식 정답을 블록 리스트로 파싱한다. 헤더가 없으면 None.

    Returns:
        [{"speaker": str, "text": str}, ...] 문서 순서 보존, 블록 내 문장은 공백으로 합침
        (언어전환 경계는 블록 단위이므로 문장 분리는 이 스크립트의 관심사가 아니다).
    """
    headers = list(_SPEAKER_HEADER_RE.finditer(ref_text))
    if not headers:
        return None
    blocks = []
    for idx, m in enumerate(headers):
        speaker = m.group(1)
        start = m.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(ref_text)
        block_text = ref_text[start:end]
        sentences = [s.strip() for s in re.split(r"\n\s*\n", block_text) if s.strip()]
        blocks.append({"speaker": speaker, "text": " ".join(sentences)})
    return blocks


# ─── 단어 정규화(WER 정렬용) ──────────────────────────────────────────────────
# whisperlivekit.metrics.normalize_text와 동일 의미론(소문자화·NFC·구두점 제거·공백 정리).
# 패키지 import 없이 재구현(오프라인 독립성 유지).
def normalize_text(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^\w\s\-']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── 언어(스크립트) 판정 ──────────────────────────────────────────────────────
# tokens_alignment.py _is_opposite_script와 동일 철학(한글/라틴 문자 카운트 다수결).
# 런타임 코드를 import하지 않고 문자셋 카운트로 독립 재현한다.
_HANGUL_RE = re.compile(r"[가-힣]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def detect_block_language(text: str) -> Optional[str]:
    """텍스트의 한글/라틴 문자 수 다수결로 'ko'/'en'을 판정. 동률·둘 다 0이면 None(모호)."""
    hangul = len(_HANGUL_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    if hangul == 0 and latin == 0:
        return None
    if hangul > latin:
        return "ko"
    if latin > hangul:
        return "en"
    return None


# ─── 정답 언어전환 경계 계산 ──────────────────────────────────────────────────
@dataclass
class RefBoundary:
    boundary_idx: int
    before_block_idx: int
    after_block_idx: int
    before_speaker: str
    after_speaker: str
    before_lang: str
    after_lang: str
    before_word_start: int  # 정답 전역 단어 인덱스(포함) — 앞쪽 윈도우 시작
    before_word_end: int    # 경계 위치(=뒤쪽 블록 시작), 앞쪽 윈도우 끝(배타)
    after_word_end: int     # 뒤쪽 윈도우 끝(배타)
    before_window_words: List[str] = field(default_factory=list)
    after_window_words: List[str] = field(default_factory=list)


def compute_language_switch_boundaries(
    blocks: List[dict], window: int = 8,
) -> Tuple[List[str], List[RefBoundary]]:
    """블록 리스트에서 언어전환 경계를 찾는다.

    언어전환 경계 = 인접 블록의 판정 언어(detect_block_language)가 서로 다르고 둘 다
    None이 아닌 지점. 화자전환이 있어도 언어가 같으면(예: bong1 spk3→spk2 둘 다 en)
    경계로 세지 않는다 — 이 스크립트의 표적은 "언어전환"이지 "화자전환" 전부가 아니다.

    Returns:
        (전역 정답 단어 리스트, 경계 리스트). 윈도우는 항상 자기 블록 범위 안으로 clip되어
        인접하지 않은 블록까지 잘못 소급하지 않는다.
    """
    all_words: List[str] = []
    block_ranges: List[Tuple[int, int]] = []
    block_langs: List[Optional[str]] = []
    for b in blocks:
        words = normalize_text(b["text"]).split()
        start = len(all_words)
        all_words.extend(words)
        block_ranges.append((start, len(all_words)))
        block_langs.append(detect_block_language(b["text"]))

    boundaries: List[RefBoundary] = []
    for i in range(len(blocks) - 1):
        lang_a, lang_b = block_langs[i], block_langs[i + 1]
        if lang_a is None or lang_b is None or lang_a == lang_b:
            continue
        p = block_ranges[i][1]  # == block_ranges[i+1][0]
        before_start = max(block_ranges[i][0], p - window)
        after_end = min(block_ranges[i + 1][1], p + window)
        boundaries.append(RefBoundary(
            boundary_idx=len(boundaries),
            before_block_idx=i, after_block_idx=i + 1,
            before_speaker=blocks[i]["speaker"], after_speaker=blocks[i + 1]["speaker"],
            before_lang=lang_a, after_lang=lang_b,
            before_word_start=before_start, before_word_end=p, after_word_end=after_end,
            before_window_words=all_words[before_start:p],
            after_window_words=all_words[p:after_end],
        ))
    return all_words, boundaries


# ─── 정답↔가설 단어 정렬 (Levenshtein, 결측 판정용) ────────────────────────────
def align_ref_to_hyp(ref_words: List[str], hyp_words: List[str]) -> List[str]:
    """정답 단어별 정렬 상태를 반환한다: 'match'(그대로 존재) / 'sub'(다른 단어로 치환·
    오디코딩 가능성) / 'del'(가설에서 완전 누락 — 이 스크립트가 "유실"로 세는 대상).

    길이 = len(ref_words). whisperlivekit.metrics._align_words와 동일 DP+backtrace
    (동점 우선순위: diagonal > up(del) > left(ins))이나, 여기서는 hyp 위치 투영이 아니라
    ref 단어별 매치 여부가 필요해 별도로 구현한다.
    """
    n, m = len(ref_words), len(hyp_words)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
    for j in range(1, m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        ref_w = ref_words[i - 1]
        row = dp[i]
        prev_row = dp[i - 1]
        for j in range(1, m + 1):
            if ref_w == hyp_words[j - 1]:
                row[j] = prev_row[j - 1]
            else:
                row[j] = 1 + min(prev_row[j - 1], prev_row[j], row[j - 1])

    ops = [""] * n
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref_words[i - 1] == hyp_words[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            ops[i - 1] = "match"
            i -= 1
            j -= 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            ops[i - 1] = "sub"
            i -= 1
            j -= 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            ops[i - 1] = "del"
            i -= 1
        else:
            j -= 1  # insertion — ref 인덱스 소비 없음
    return ops


def boundary_missing_words(ops: List[str], boundary: RefBoundary) -> Dict[str, List[str]]:
    """경계 전후 윈도우에서 결측(del)/치환(sub) 단어를 뽑는다."""
    before_ops = ops[boundary.before_word_start:boundary.before_word_end]
    after_ops = ops[boundary.before_word_end:boundary.after_word_end]
    before_del = [w for w, o in zip(boundary.before_window_words, before_ops) if o == "del"]
    before_sub = [w for w, o in zip(boundary.before_window_words, before_ops) if o == "sub"]
    after_del = [w for w, o in zip(boundary.after_window_words, after_ops) if o == "del"]
    after_sub = [w for w, o in zip(boundary.after_window_words, after_ops) if o == "sub"]
    return {"before_del": before_del, "before_sub": before_sub, "after_del": after_del, "after_sub": after_sub}


# ─── 서버 로그 파싱 (언어전환 경계 이벤트) ─────────────────────────────────────
_RETRACTSCAN_RE = re.compile(
    r"\[RetractScan\] boundary_t=([\d.]+) prev_lang=(\S+) scanned=(\d+) removed=(\d+) stopped_by=(\S+)"
)
_RETRACT_REMOVE_RE = re.compile(r"\[Retract\] 철회: (.+) start=([\d.]+) prev_lang=(\S+)")
_LANGSWITCH_EMIT_RE = re.compile(r"\[LangSwitch\] 문장 경계 마커 방출 @ ([\d.]+)s \(lang=(\S+)\)")
_NEWSPEAKER_AFTER_RE = re.compile(
    r"\[NewSpeaker\] spk=(\S+) det_after=(\S+) \(eager_applied=(\S+)\) "
    r"keep_secs=([\d.]+) kept_segments_len=([\d.]+)s global_time_offset=([\-\d.]+)"
)


@dataclass
class RetractScanEvent:
    line_no: int
    boundary_t: float
    prev_lang: str
    scanned: int
    removed: int
    stopped_by: str


@dataclass
class LangSwitchEmitEvent:
    line_no: int
    boundary_t: float
    lang: str


@dataclass
class NewSpeakerAfterEvent:
    line_no: int
    det_after: str
    eager_applied: bool
    keep_secs: float
    kept_segments_len: float


@dataclass
class BoundaryLog:
    path: str
    retract_scans: List[RetractScanEvent] = field(default_factory=list)
    retract_removed: List[Tuple[int, str, str]] = field(default_factory=list)  # (line_no, text, prev_lang)
    lang_switch_emits: List[LangSwitchEmitEvent] = field(default_factory=list)
    new_speaker_afters: List[NewSpeakerAfterEvent] = field(default_factory=list)
    trace_tokens_on: bool = False


def parse_boundary_log(path: str, lines: List[str]) -> BoundaryLog:
    r = BoundaryLog(path=path)
    for i, line in enumerate(lines, start=1):
        if "[TraceTokens] DEBUG 레벨 로깅 활성화" in line:
            r.trace_tokens_on = True
            continue
        m = _RETRACTSCAN_RE.search(line)
        if m:
            r.retract_scans.append(RetractScanEvent(
                line_no=i, boundary_t=float(m.group(1)), prev_lang=m.group(2),
                scanned=int(m.group(3)), removed=int(m.group(4)), stopped_by=m.group(5),
            ))
            continue
        m = _RETRACT_REMOVE_RE.search(line)
        if m:
            text = m.group(1).strip()
            if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
                text = text[1:-1]
            r.retract_removed.append((i, text, m.group(3)))
            continue
        m = _LANGSWITCH_EMIT_RE.search(line)
        if m:
            r.lang_switch_emits.append(LangSwitchEmitEvent(
                line_no=i, boundary_t=float(m.group(1)), lang=m.group(2),
            ))
            continue
        m = _NEWSPEAKER_AFTER_RE.search(line)
        if m:
            r.new_speaker_afters.append(NewSpeakerAfterEvent(
                line_no=i, det_after=m.group(2), eager_applied=(m.group(3) == "True"),
                keep_secs=float(m.group(4)), kept_segments_len=float(m.group(5)),
            ))
            continue
    return r


# ─── 계열 분류 (ⓐ철회미복구 / ⓑ미방출 / 구언어꼬리 / 기타) ─────────────────────
_SERIES_RETRACT_UNRECOVERED = "ⓐ철회미복구"
_SERIES_NONEMIT = "ⓑ미방출"
_SERIES_OLD_LANG_TAIL = "구언어꼬리"
_SERIES_OTHER = "기타"
_SERIES_NORMAL = "정상"

ALL_SERIES = [
    _SERIES_RETRACT_UNRECOVERED, _SERIES_NONEMIT, _SERIES_OLD_LANG_TAIL,
    _SERIES_OTHER, _SERIES_NORMAL,
]


@dataclass
class BoundaryVerdict:
    boundary: RefBoundary
    missing: Dict[str, List[str]]
    series: List[str]
    evidence: List[str]


def classify_boundaries(
    boundaries: List[RefBoundary], ops: List[str], log: Optional[BoundaryLog],
) -> List[BoundaryVerdict]:
    """경계별 유실 계열을 휴리스틱으로 태깅한다.

    ⚠️ 자동 태깅은 방향 신호다 — RetractScan은 로그에 타임스탬프가 없어(Exp-172 확인)
    경계와의 매칭을 **순서(등장 순)**로만 근사한다. 이 파일들(ytn2/bong1)은 실측상 거의
    항상 언어가 엄격히 교대하고 RetractScan도 실제 전환마다 정확히 1건씩 발생하므로
    순서 매칭이 대체로 유효하지만, 카운트가 어긋나면(예: 전환이 아예 트리거 안 됨) 이후
    페어링이 밀리므로 evidence 문자열의 boundary_t/scanned/removed를 원문 로그와 대조해
    확정할 것.
    """
    retract_scans = log.retract_scans if log else []
    verdicts: List[BoundaryVerdict] = []
    for idx, boundary in enumerate(boundaries):
        missing = boundary_missing_words(ops, boundary)
        series: List[str] = []
        evidence: List[str] = []

        if missing["before_del"]:
            series.append(_SERIES_OLD_LANG_TAIL)
            evidence.append(f"before_del={missing['before_del']!r} (경계 이전 구언어 꼬리 — 신언어 재디코딩으로 원리상 복구 불가)")

        if missing["after_del"]:
            rs = retract_scans[idx] if idx < len(retract_scans) else None
            if rs is not None and rs.prev_lang == boundary.before_lang and rs.removed > 0:
                series.append(_SERIES_RETRACT_UNRECOVERED)
                evidence.append(
                    f"after_del={missing['after_del']!r} ~ RetractScan(line {rs.line_no}) "
                    f"boundary_t={rs.boundary_t} removed={rs.removed} stopped_by={rs.stopped_by}"
                )
            elif rs is not None and rs.prev_lang == boundary.before_lang and rs.removed == 0:
                series.append(_SERIES_NONEMIT)
                evidence.append(
                    f"after_del={missing['after_del']!r} ~ RetractScan(line {rs.line_no}) "
                    f"boundary_t={rs.boundary_t} removed=0 stopped_by={rs.stopped_by} "
                    "(철회 대상 자체가 없음 — 애초에 방출된 토큰이 없었을 가능성)"
                )
            else:
                series.append(_SERIES_OTHER)
                note = "이 경계에 순서상 대응하는 RetractScan 이벤트 없음(전환 자체 미발동 또는 언어 불일치 가능)"
                if rs is not None:
                    note = f"순서상 후보 RetractScan(line {rs.line_no})의 prev_lang={rs.prev_lang} != before_lang={boundary.before_lang}"
                evidence.append(f"after_del={missing['after_del']!r} — {note}")

        if not series:
            series.append(_SERIES_NORMAL)
        verdicts.append(BoundaryVerdict(boundary=boundary, missing=missing, series=series, evidence=evidence))
    return verdicts


# ─── 인접 n-gram 중복 재방출 탐지 ─────────────────────────────────────────────
_WORD_TOKEN_RE = re.compile(r"[A-Za-z']+|[가-힣]+")
DEFAULT_DUP_MIN_N = 2
DEFAULT_DUP_MAX_N = 4
DEFAULT_DUP_MAX_GAP = 0  # 0 = 완전 인접만(재디코딩 창 겹침 이중방출의 실측 특징)


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in _WORD_TOKEN_RE.findall(text)]


@dataclass
class DupRun:
    n: int
    start_word_idx: int
    end_word_idx: int
    repeat_count: int
    ngram: str


def find_adjacent_ngram_duplicates(
    words: List[str], min_n: int = DEFAULT_DUP_MIN_N, max_n: int = DEFAULT_DUP_MAX_N,
    max_gap: int = DEFAULT_DUP_MAX_GAP,
) -> List[DupRun]:
    """인접 n-gram(min_n~max_n) 중복 재방출을 탐지한다.

    analyze_case3_hallucination.find_ngram_repeat_runs와 알고리즘 골격은 같으나(큰 n부터
    소비해 하위 n-gram 이중계산 방지) 목적이 다르다 — 저 함수는 "환각 폭주"(min_run=3,
    gap-tolerant, 국소집중도 필터)를 잡고, 이 함수는 "재디코딩 창 겹침 이중방출"(실측:
    "It's just a It's just a rock", "Everyone Everyone here" — 완전 인접, 단 2회만
    반복돼도 증상)을 잡는다. min_n=2로 단일 단어 반복("네, 네" 등 정상 강조 발화, §3.8
    데이터 특화 아닌 일반 보호)을 기본 제외한다.
    """
    N = len(words)
    covered = [False] * N
    runs: List[DupRun] = []
    for n in range(max_n, min_n - 1, -1):
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
            if count >= 2:
                runs.append(DupRun(n=n, start_word_idx=cluster_start, end_word_idx=cur,
                                    repeat_count=count, ngram=" ".join(gram)))
                for k in range(cluster_start, cur):
                    covered[k] = True
                i = cur
            else:
                i += 1
    runs.sort(key=lambda r: r.start_word_idx)
    return runs


# ─── 전사 파일 로딩 ───────────────────────────────────────────────────────────
_TRIGGER_LINE_RE = re.compile(r"^\d+\.\s+(.*?)\s+⟨([^⟩]+)⟩\s*$", re.MULTILINE)


def load_transcript_sections(path: str) -> Dict[str, object]:
    """eval.py `_save_transcript` 포맷에서 [전사]/[문장별 확정 트리거] 섹션을 추출한다."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    m = re.search(r"\[전사\]\n(.*?)\n\n\[문장별 확정 트리거\]", content, re.DOTALL)
    if not m:
        # 구버전 전사(트리거 섹션 없음) 폴백
        m = re.search(r"\[전사\]\n(.*?)\n\n\[정답\]", content, re.DOTALL)
    transcript_text = m.group(1) if m else content
    triggers = [(text.strip(), trig) for text, trig in _TRIGGER_LINE_RE.findall(content)]
    lang_switch_line_count = sum(1 for _, trig in triggers if trig == "language_switch")
    return {"transcript_text": transcript_text, "triggers": triggers,
            "lang_switch_trigger_count": lang_switch_line_count}


# ─── 파일명 규칙 매칭 (analyze_case3_hallucination.py와 동일 관례) ──────────────
_LOG_NAME_RE = re.compile(r"server_(?P<stem>.+?)_(?P<path>[ABC])_R(?P<rep>\d+)_\d+_\d+\.log$")
_TXT_NAME_RE = re.compile(r"(?P<stem>.+?)_(?P<path>[ABC])_R(?P<rep>\d+)\.txt$")


def _extract_key(filename: str, pattern: re.Pattern) -> Optional[Tuple[str, str, str]]:
    m = pattern.search(filename.replace("\\", "/").rsplit("/", 1)[-1])
    if not m:
        return None
    return (m.group("stem"), m.group("path"), m.group("rep"))


# ─── 파일 단위 분석 ───────────────────────────────────────────────────────────
@dataclass
class FileAnalysis:
    stem: str
    path_type: str
    rep: str
    transcript_path: str
    log_path: Optional[str]
    reference_found: bool
    boundary_count: int = 0
    verdicts: List[BoundaryVerdict] = field(default_factory=list)
    dup_runs: List[DupRun] = field(default_factory=list)
    n_words: int = 0
    lang_switch_trigger_count: int = 0
    retract_scan_count: int = 0


def analyze_file(
    stem: str, path_type: str, rep: str, transcript_path: str, log_path: Optional[str],
    reference_dir: Path, window: int, dup_min_n: int, dup_max_n: int, dup_max_gap: int,
) -> FileAnalysis:
    sections = load_transcript_sections(transcript_path)
    hyp_words_align = normalize_text(sections["transcript_text"]).split()
    dup_words = tokenize(sections["transcript_text"])
    dup_runs = find_adjacent_ngram_duplicates(dup_words, min_n=dup_min_n, max_n=dup_max_n, max_gap=dup_max_gap)

    fa = FileAnalysis(
        stem=stem, path_type=path_type, rep=rep, transcript_path=transcript_path, log_path=log_path,
        reference_found=False, dup_runs=dup_runs, n_words=len(dup_words),
        lang_switch_trigger_count=sections["lang_switch_trigger_count"],
    )

    ref_path = reference_dir / f"{stem}.txt"
    if not ref_path.exists():
        return fa
    ref_text = ref_path.read_text(encoding="utf-8")
    blocks = parse_speaker_blocks(ref_text)
    if not blocks:
        return fa
    fa.reference_found = True

    ref_words, boundaries = compute_language_switch_boundaries(blocks, window=window)
    fa.boundary_count = len(boundaries)
    ops = align_ref_to_hyp(ref_words, hyp_words_align)

    log: Optional[BoundaryLog] = None
    if log_path:
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                log_lines = f.readlines()
            log = parse_boundary_log(log_path, log_lines)
            fa.retract_scan_count = len(log.retract_scans)
        except OSError as e:
            print(f"[skip-log] {log_path}: {e}", file=sys.stderr)

    fa.verdicts = classify_boundaries(boundaries, ops, log)
    return fa


# ─── 출력 ────────────────────────────────────────────────────────────────────
def _print_file_report(fa: FileAnalysis, detail: bool = True) -> None:
    label = f"[{fa.stem} {fa.path_type} R{fa.rep}]"
    print(label)
    print(f"  전사 단어수: {fa.n_words}")
    if not fa.reference_found:
        print("  정답 파일 없음 또는 [spkN] 헤더 파싱 실패 — 경계 분석 스킵(dup만 산출)")
    else:
        print(f"  언어전환 경계(정답 기준): {fa.boundary_count}개  "
              f"(전사 language_switch 트리거: {fa.lang_switch_trigger_count}건, "
              f"로그 RetractScan: {fa.retract_scan_count}건)")
        series_counter = Counter()
        for v in fa.verdicts:
            for s in v.series:
                series_counter[s] += 1
        print(f"  계열 분포: {dict(series_counter)}")
        if detail:
            for v in fa.verdicts:
                b = v.boundary
                print(f"    경계#{b.boundary_idx} {b.before_speaker}({b.before_lang})→"
                      f"{b.after_speaker}({b.after_lang})  series={v.series}")
                if v.missing["before_del"] or v.missing["after_del"]:
                    print(f"      before_del={v.missing['before_del']}  after_del={v.missing['after_del']}")
                if v.missing["before_sub"] or v.missing["after_sub"]:
                    print(f"      before_sub={v.missing['before_sub']}  after_sub={v.missing['after_sub']} "
                          "(치환 — 음차환각 등 스코프 밖 가능성, 별도 확인)")
                for e in v.evidence:
                    print(f"      evidence: {e}")
    print(f"  인접 n-gram 중복: {len(fa.dup_runs)}건")
    if detail:
        for run in fa.dup_runs:
            print(f"    [dup] word {run.start_word_idx}-{run.end_word_idx} n={run.n} "
                  f"×{run.repeat_count}  ngram={run.ngram!r}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="언어전환 경계 유실(꼬리/서두)+중복 진단 분석기")
    parser.add_argument("--transcripts", nargs="+", default=[], required=True,
                         help="전사 텍스트 경로(글로브 허용, .omc/transcripts/*_C_R*.txt)")
    parser.add_argument("--logs", nargs="*", default=[], help="서버 로그 경로(글로브 허용, 선택)")
    parser.add_argument("--reference-dir", type=Path, default=Path("test_data"),
                         help="정답 <stem>.txt가 있는 디렉터리 (기본: test_data)")
    parser.add_argument("--window", type=int, default=8, help="경계 전후 검사 윈도우(단어 수, 기본 8)")
    parser.add_argument("--dup-min-n", type=int, default=DEFAULT_DUP_MIN_N)
    parser.add_argument("--dup-max-n", type=int, default=DEFAULT_DUP_MAX_N)
    parser.add_argument("--dup-max-gap", type=int, default=DEFAULT_DUP_MAX_GAP)
    parser.add_argument("--per-file", action="store_true", help="파일별 상세 출력")
    args = parser.parse_args(argv)

    def _expand(patterns: List[str]) -> List[str]:
        paths: List[str] = []
        for pat in patterns:
            expanded = glob.glob(pat)
            paths.extend(expanded if expanded else [pat])
        return paths

    txt_paths = _expand(args.transcripts)
    log_paths = _expand(args.logs)

    log_by_key: Dict[Tuple[str, str, str], str] = {}
    for p in log_paths:
        key = _extract_key(p, _LOG_NAME_RE)
        if key:
            log_by_key[key] = p
        else:
            print(f"[경고] 로그 파일명 규칙 불일치(무시): {p}", file=sys.stderr)

    analyses: List[FileAnalysis] = []
    for p in txt_paths:
        key = _extract_key(p, _TXT_NAME_RE)
        if not key:
            print(f"[skip] 전사 파일명 규칙 불일치: {p}", file=sys.stderr)
            continue
        stem, path_type, rep = key
        log_path = log_by_key.get(key)
        if args.logs and not log_path:
            print(f"[경고] {p}: 대응하는 로그를 찾지 못함 — 로그기반 ⓐ/ⓑ 태깅 없이 진행", file=sys.stderr)
        try:
            fa = analyze_file(
                stem, path_type, rep, p, log_path, args.reference_dir,
                args.window, args.dup_min_n, args.dup_max_n, args.dup_max_gap,
            )
        except OSError as e:
            print(f"[skip] {p}: {e}", file=sys.stderr)
            continue
        analyses.append(fa)
        if args.per_file:
            _print_file_report(fa, detail=True)
            print()

    print("=" * 70)
    print(f"[전체 합계] {len(analyses)}개 (파일×회차)")
    total_boundaries = sum(fa.boundary_count for fa in analyses)
    print(f"  언어전환 경계 총합(정답 기준): {total_boundaries}")
    series_counter: Counter = Counter()
    for fa in analyses:
        for v in fa.verdicts:
            for s in v.series:
                series_counter[s] += 1
    for s in ALL_SERIES:
        if series_counter.get(s):
            print(f"    {s}: {series_counter[s]}건")
    dup_counts = [len(fa.dup_runs) for fa in analyses]
    if dup_counts:
        print(f"  인접 n-gram 중복 건수: 합계={sum(dup_counts)} "
              f"median={statistics.median(dup_counts):.1f} max={max(dup_counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
