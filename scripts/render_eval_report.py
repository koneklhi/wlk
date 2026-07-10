#!/usr/bin/env python3
"""STT 평가 결과(전사 vs 정답)를 단어 단위로 색깔 하이라이트하는 자체완결 HTML 리포트 생성기.

`.omc/benchmarks/*.json`(scripts/eval.py 산출물)의 `files[]`를 읽어, 회차별 전사와 정답을
difflib 기반으로 정렬해 삭제/삽입/치환을 시각화하고, 문장별 확정 트리거(silence/punctuation/
speaker_change/language_switch)를 칩으로 표시하며, 단어 중간 분절(Case B)을 자동 탐지해
굵은 빨강 테두리로 강조한다.

사용법:
    python scripts/render_eval_report.py <json경로...> [--output PATH] [--title STR]

설계 원칙(docs 계획 참조):
- whisperlivekit을 import하지 않는다(`whisperlivekit/__init__.py`가 torch 체인을 즉시 로드
  하므로, 가벼운 리포트 생성기가 이를 끌고 오면 안 된다). normalize_text 로직은 로컬 재구현.
- 신규 의존성 0 — 표준 라이브러리만 사용.
- 외부 리소스 요청 0 — 생성된 HTML은 폰트/스크립트/CDN 없이 완전히 자체완결.

파일 구조: (A) 순수 diff·정규화 로직 → (B) 데이터 로딩·그룹핑 → (C) HTML 렌더링.
"""

import argparse
import difflib
import html
import json
import re
import sys
import unicodedata
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# --- 공용 타입 --------------------------------------------------------------

Tok = namedtuple("Tok", "display key")

# kind: "eq"(일치) | "del"(정답에만 있음) | "ins"(전사에만 있음=환각) | "sub"(치환).
# ref_start/ref_end/hyp_start/hyp_end는 각각 ref_toks/hyp_toks 전체 스트림 기준 절대 인덱스
# 구간([start, end))이다 — detect_case_b가 hyp_line 경계와 겹치는지 확인하는 데 쓰인다.
DiffSpan = namedtuple("DiffSpan", "kind ref_toks hyp_toks ref_start ref_end hyp_start hyp_end")

# LineSpan.start/end: 이 줄이 차지하는 hyp 전체 토큰 스트림상의 [start, end) 인덱스 구간.
LineSpan = namedtuple("LineSpan", "text trigger start end")

_OPCODE_KIND = {"equal": "eq", "delete": "del", "insert": "ins", "replace": "sub"}


# ---------------------------------------------------------------------------
# (A) 순수 diff·정규화 로직 (whisperlivekit import 없음)
# ---------------------------------------------------------------------------


def _normalize_text(text: str) -> str:
    """WER 비교용 정규화: 소문자화 → NFC 정규화 → 구두점 제거(단어/공백/하이픈/아포스트로피 보존) → 공백축약.

    whisperlivekit/metrics.py의 normalize_text와 완전히 동일한 로직(테스트에서 파리티 검증).
    """
    text = text.lower()
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[^\w\s\-']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str) -> List[Tok]:
    """공백 분리 후 각 조각의 표시(display)/정규화 키(key) 쌍을 만든다.

    순수 구두점 조각(정규화 후 key가 빈 문자열, 예 "...")은 별도 diff 대상이 되지 않도록
    직전 토큰의 display에 접착된다(예: "hello ... world" -> ["hello ...", "world"]).
    직전 토큰이 없으면(선두 구두점) key가 빈 문자열인 채로 독립 토큰이 된다.
    """
    toks: List[Tok] = []
    for raw in text.split():
        key = _normalize_text(raw)
        if key == "" and toks:
            prev = toks[-1]
            toks[-1] = Tok(display=f"{prev.display} {raw}", key=prev.key)
        else:
            toks.append(Tok(display=raw, key=key))
    return toks


def diff_tokens(ref_toks: List[Tok], hyp_toks: List[Tok]) -> List[DiffSpan]:
    """SequenceMatcher(정규화 key 기준)로 ref/hyp 토큰을 정렬해 eq/del/ins/sub 4종 span으로 나눈다.

    정렬 키는 정규화된 key를 쓰되(WER 채점과 시각적으로 어긋나지 않게), span에는 원문 그대로의
    display를 보존한 Tok을 담는다 — 대소문자만 다른 경우는 key가 같으므로 sub가 아니라 eq로
    처리된다. ref_toks/hyp_toks가 모두 비어 있으면 빈 리스트를 반환한다.
    """
    ref_keys = [t.key for t in ref_toks]
    hyp_keys = [t.key for t in hyp_toks]
    matcher = difflib.SequenceMatcher(a=ref_keys, b=hyp_keys, autojunk=False)
    spans: List[DiffSpan] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        spans.append(
            DiffSpan(
                kind=_OPCODE_KIND[tag],
                ref_toks=ref_toks[i1:i2],
                hyp_toks=hyp_toks[j1:j2],
                ref_start=i1,
                ref_end=i2,
                hyp_start=j1,
                hyp_end=j2,
            )
        )
    return spans


def detect_case_b(diff_spans: List[DiffSpan], line_spans: List[LineSpan]) -> List[dict]:
    """치환(sub) opcode 중 정답 1토큰이 hyp_line 경계에서 여러 토큰으로 쪼개진 경우(Case B,
    단어 중간 분절 — 예 "올렸"+"습니다")를 탐지한다. CLAUDE.md §3.3 hard-fail 요구사항 직결이므로
    옵션이 아니라 필수 범위다(sbs1 실측 베이스라인에서 재현됨).

    다음 조건을 모두 만족해야 flag한다(오탐 방지):
    1. sub opcode이고 정답 쪽이 정확히 1토큰이며 hyp 쪽이 2토큰 이상이어야 한다(1:1 치환은
       단순 WER 오류이지 구조적 단어분절이 아니므로 제외).
    2. hyp 토큰들 사이의 내부 경계 중 적어도 하나가 실제 hyp_line 시작점과 정확히 겹쳐야
       한다(같은 줄 내부의 단순 인식 오류와 구분).
    3. hyp 토큰들의 key를 이어붙이면 정답 토큰의 key와 정확히 일치해야 한다(다른 말로
       오인식된 경우와 "진짜 그 단어가 쪼개진 경우"를 구분).

    Returns:
        [{"ref_token": str, "hyp_tokens": [str, ...], "hyp_start": int, "hyp_end": int}, ...]
    """
    line_start_indices = {ls.start for ls in line_spans if ls.start > 0}
    hits: List[dict] = []
    for span in diff_spans:
        if span.kind != "sub":
            continue
        if len(span.ref_toks) != 1 or len(span.hyp_toks) < 2:
            continue
        boundary_positions = range(span.hyp_start + 1, span.hyp_end)
        if not any(pos in line_start_indices for pos in boundary_positions):
            continue
        ref_key = span.ref_toks[0].key
        concatenated = "".join(t.key for t in span.hyp_toks)
        if concatenated != ref_key:
            continue
        hits.append(
            {
                "ref_token": span.ref_toks[0].display,
                "hyp_tokens": [t.display for t in span.hyp_toks],
                "hyp_start": span.hyp_start,
                "hyp_end": span.hyp_end,
            }
        )
    return hits


# ---------------------------------------------------------------------------
# (B) 데이터 로딩·그룹핑
# ---------------------------------------------------------------------------


@dataclass
class FileGroup:
    """같은 오디오 파일(basename)에 대한 여러 회차(run)를 묶은 그룹."""

    display_name: str
    runs: List[dict] = field(default_factory=list)
    summary: Optional[dict] = None


def _normalize_audio_key(audio_file: str) -> str:
    """역슬래시를 정규화하고 basename만 남긴 그룹핑 키(윈도우 경로 vs 유닉스 경로 혼용 대응)."""
    return Path(audio_file.replace("\\", "/")).name


def load_reports(paths) -> List[dict]:
    """여러 JSON 파일을 로드해 dict 리스트로 반환한다(파일 하나당 dict 하나, 원본 구조 그대로)."""
    reports = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            reports.append(json.load(f))
    return reports


def group_files(reports: List[dict]) -> List[FileGroup]:
    """여러 report(JSON dict)의 files[]를 오디오 파일 basename 기준으로 그룹핑한다.

    등장 순서를 보존하고, file_summaries[](repeat>1일 때만 존재)를 같은 키로 매칭해 부착한다.
    여러 report를 넘기면(테스트셋+held-out JSON 등) 같은 파일의 run들이 순서대로 이어붙는다.
    """
    groups: Dict[str, FileGroup] = {}
    order: List[str] = []
    for report in reports:
        summaries_by_key = {}
        for s in report.get("file_summaries") or []:
            summaries_by_key[_normalize_audio_key(s["audio_file"])] = s
        for file_result in report.get("files") or []:
            key = _normalize_audio_key(file_result["audio_file"])
            if key not in groups:
                groups[key] = FileGroup(display_name=key)
                order.append(key)
            groups[key].runs.append(file_result)
            if key in summaries_by_key:
                groups[key].summary = summaries_by_key[key]
    return [groups[k] for k in order]


def build_hyp_layout(hyp_lines):
    """hyp_lines(줄별 {"text", "trigger"})를 줄 단위로 토큰화해 이어붙이고, 각 줄의 토큰 인덱스
    구간 + 트리거 라벨을 계산한다.

    반환된 hyp_toks가 diff_tokens()에 넘길 hyp 전체 토큰 스트림의 단일 소스다 — transcription
    문자열을 별도로 다시 tokenize()하지 않는다. 그렇게 하면 줄 경계에서 tokenize()의 "순수
    구두점 접착" 동작이 (줄 전체를 한 번에 토큰화할 때와) 갈라질 수 있는 불일치를 원천 차단한다.
    """
    all_toks: List[Tok] = []
    spans: List[LineSpan] = []
    for line in hyp_lines or []:
        text = line.get("text") or ""
        trigger = line.get("trigger")
        toks = tokenize(text)
        start = len(all_toks)
        all_toks.extend(toks)
        end = len(all_toks)
        spans.append(LineSpan(text=text, trigger=trigger, start=start, end=end))
    return all_toks, spans


# ---------------------------------------------------------------------------
# (C) HTML 렌더링
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """html.escape 래퍼(quote=True) — 전사/정답에 포함될 수 있는 `<script>` 등을 안전하게 이스케이프."""
    return html.escape(text, quote=True)


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value * 100:.1f}%" if value is not None else "N/A"


def _slugify(name: str) -> str:
    """파일명을 HTML id/앵커로 안전하게 쓸 수 있는 슬러그로 변환한다(영숫자·_·- 외엔 _로 치환)."""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", name)


def _render_trigger_chip(trigger: Optional[str]) -> str:
    """확정 트리거 칩 하나를 <span>+줄바꿈(<br>)으로 렌더링한다. trigger가 None/빈 값이면 "none"으로
    표시한다. render_diff()의 두 플러시 지점(메인 루프 중간 / 잔여 줄 마무리)이 동일 로직을
    공유하도록 추출한 헬퍼 — 문장 경계마다 실제 줄바꿈이 나오게 하는 지점이 한 곳으로 모인다.
    """
    trig_label = trigger or "none"
    return f'<span class="trigger trigger--{trig_label}">⟨{_esc(trig_label)}⟩</span><br>\n'


def render_diff(diff_spans: List[DiffSpan], line_spans: List[LineSpan], case_b_hits: Optional[List[dict]] = None) -> str:
    """diff_spans + line_spans를 하나의 연속 HTML 플로우로 렌더링한다(2단 컬럼이 아닌 track-changes 스타일).

    hyp 관점(무엇이 전사됐는지)을 기본 흐름으로 삼는다: eq는 평문, del(정답에만 있음)은 취소선,
    ins(전사에만 있음=환각)은 강조, sub(치환)는 ref/hyp을 나란히 보여준다. detect_case_b가 찾은
    span은 굵은 빨강 테두리(.caseb)를 추가로 두른다. 각 hyp_line이 끝나는 지점마다 확정 트리거
    칩을 삽입한다 — 정확히 토큰 사이에 끼워 넣지 않고, 그 줄의 마지막 토큰을 포함하는 span이
    끝난 직후 배치한다(대부분의 줄 경계는 긴 eq run 내부에 있어 실질적으로 정확한 위치이고,
    Case B처럼 sub span 내부에 경계가 있는 드문 경우도 재구성된 단어 블록 바로 뒤에 붙는다).
    """
    case_b_hyp_starts = {c["hyp_start"] for c in (case_b_hits or [])}
    parts: List[str] = []
    line_ptr = 0
    n_lines = len(line_spans)

    def _flush_chips_up_to(hyp_pos: int) -> None:
        nonlocal line_ptr
        while line_ptr < n_lines and line_spans[line_ptr].end <= hyp_pos:
            parts.append(_render_trigger_chip(line_spans[line_ptr].trigger))
            line_ptr += 1

    for span in diff_spans:
        if span.kind == "eq":
            text = " ".join(t.display for t in span.hyp_toks)
            if text:
                parts.append(f'<span class="eq">{_esc(text)}</span> ')
        elif span.kind == "del":
            text = " ".join(t.display for t in span.ref_toks)
            if text:
                parts.append(f'<span class="del">{_esc(text)}</span> ')
        elif span.kind == "ins":
            text = " ".join(t.display for t in span.hyp_toks)
            if text:
                parts.append(f'<span class="ins">{_esc(text)}</span> ')
        elif span.kind == "sub":
            ref_text = " ".join(t.display for t in span.ref_toks)
            hyp_text = " ".join(t.display for t in span.hyp_toks)
            caseb_cls = " caseb" if span.hyp_start in case_b_hyp_starts else ""
            parts.append(
                f'<span class="sub{caseb_cls}">'
                f'<span class="sub-ref">{_esc(ref_text)}</span>'
                f'<span class="sub-hyp">{_esc(hyp_text)}</span>'
                f"</span> "
            )
        _flush_chips_up_to(span.hyp_end)

    # 잔여 줄 전부 플러시(예: 마지막 span 이후에도 아직 표시 안 된 트리거가 남아있는 경우).
    while line_ptr < n_lines:
        parts.append(_render_trigger_chip(line_spans[line_ptr].trigger))
        line_ptr += 1

    return "".join(parts)


def render_run_section(file_result: dict, run_index: int) -> str:
    """FileResult(asdict) dict 하나(=1 회차)를 렌더링한다."""
    reference = file_result.get("reference")
    hyp_lines = file_result.get("hyp_lines")
    transcription = file_result.get("transcription") or ""

    if hyp_lines:
        hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    else:
        hyp_toks = tokenize(transcription)
        line_spans = []

    if reference is not None:
        ref_toks = tokenize(reference)
        diff_spans = diff_tokens(ref_toks, hyp_toks)
        case_b_hits = detect_case_b(diff_spans, line_spans)
    else:
        # 정답이 아예 없으면(비교 불가) 전부 "eq"(평문)로 렌더링한다 — hallucination(ins) 취급하면
        # "정답이 없어서 비교 못 함"이 "전부 환각"으로 오독될 수 있으므로 구분한다.
        diff_spans = (
            [DiffSpan(kind="eq", ref_toks=[], hyp_toks=hyp_toks, ref_start=0, ref_end=0, hyp_start=0, hyp_end=len(hyp_toks))]
            if hyp_toks
            else []
        )
        case_b_hits = []

    diff_html = render_diff(diff_spans, line_spans, case_b_hits)

    ref_format_label = {"new": "신형식", "old": "구형식", None: "정답없음"}.get(file_result.get("ref_format"), "정답없음")
    caseb_note = f' <span class="caseb-flag">Case B ×{len(case_b_hits)}</span>' if case_b_hits else ""

    return (
        '<div class="run">'
        f'<div class="run-metrics">R{run_index} [{_esc(file_result.get("path") or "")}] '
        f'WER {_fmt_pct(file_result.get("wer"))} | '
        f'화자F1 {_fmt_pct(file_result.get("seg_f1"))} | '
        f'문장F1 {_fmt_pct(file_result.get("sentence_f1"))} | {ref_format_label}'
        f"{caseb_note}</div>"
        f'<div class="diff">{diff_html}</div>'
        "</div>"
    )


def render_file_section(group: FileGroup) -> str:
    """같은 오디오 파일의 여러 회차(run)를 한 <details> 섹션에 순서대로 묶는다(회차간 편차 비교 목적).

    기본 open 상태 — 앵커 이동·Ctrl+F가 항상 동작하도록.
    """
    anchor_id = f"file-{_slugify(group.display_name)}"
    runs_html = "".join(render_run_section(r, i + 1) for i, r in enumerate(group.runs))

    summary_extra = ""
    if group.summary:
        agg = group.summary

        def _agg_str(key: str) -> str:
            d = agg.get(key) or {}
            med, mn, mx = d.get("median"), d.get("min"), d.get("max")
            if med is None:
                return "N/A"
            return f"median {_fmt_pct(med)} [min {_fmt_pct(mn)} / max {_fmt_pct(mx)}]"

        summary_extra = (
            '<div class="file-summary">'
            f"{_esc(str(agg.get('repeat', '')))}회 반복 — "
            f"WER {_agg_str('wer')} | 화자F1 {_agg_str('seg_f1')} | 문장F1 {_agg_str('sentence_f1')}"
            "</div>"
        )

    return (
        f'<details class="file-section" id="{anchor_id}" open>'
        f"<summary>{_esc(group.display_name)} ({len(group.runs)}회차)</summary>"
        f"{summary_extra}"
        f"{runs_html}"
        "</details>"
    )


def render_summary_table(groups: List[FileGroup]) -> str:
    """파일별 WER/화자분리 F1/문장분리 F1(요약 있으면 median, 없으면 첫 run 값) + 앵커 링크 표."""
    rows = []
    for g in groups:
        anchor_id = f"file-{_slugify(g.display_name)}"
        if g.summary:
            wer = (g.summary.get("wer") or {}).get("median")
            seg_f1 = (g.summary.get("seg_f1") or {}).get("median")
            sentence_f1 = (g.summary.get("sentence_f1") or {}).get("median")
        elif g.runs:
            wer = g.runs[0].get("wer")
            seg_f1 = g.runs[0].get("seg_f1")
            sentence_f1 = g.runs[0].get("sentence_f1")
        else:
            wer = seg_f1 = sentence_f1 = None

        rows.append(
            f'<tr><td><a href="#{anchor_id}">{_esc(g.display_name)}</a></td>'
            f"<td>{_fmt_pct(wer)}</td><td>{_fmt_pct(seg_f1)}</td><td>{_fmt_pct(sentence_f1)}</td>"
            f"<td>{len(g.runs)}</td></tr>"
        )

    return (
        '<table class="summary-table">'
        "<thead><tr><th>파일</th><th>WER</th><th>화자분리 F1</th><th>문장분리 F1</th><th>회차</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def render_legend() -> str:
    """색상·기호 범례(고정 HTML, 데이터 의존 없음).

    스와치에 쓰는 클래스(eq/del/ins/sub/sub-ref/sub-hyp/sub.caseb/trigger)는 `_CSS`에서
    `.legend` 셀렉터도 함께 매치하도록 스코프를 넓혀 놨다 — 여기서 만든 마크업이 실제로
    색이 입혀지려면 그 CSS 확장과 짝이 맞아야 한다.
    """
    # (스와치 HTML, 굵은 라벨, 한국어 설명) — eq(일치)부터 caseb까지 실제 진단 색상을 그대로 재사용.
    items = [
        ('<span class="eq">일치 예시</span>', "일치", "정답과 전사가 같음(정상)."),
        ('<span class="del">삭제 예시</span>', "삭제", "정답에만 있고 전사에서는 빠진 단어(누락)."),
        ('<span class="ins">삽입 예시</span>', "삽입", "전사에만 있고 정답에는 없는 단어(환각으로 추정)."),
        (
            '<span class="sub"><span class="sub-ref">정답</span><span class="sub-hyp">전사</span></span>',
            "치환",
            "정답과 다른 단어로 인식됨(취소선=정답, 옆 글자=실제 전사).",
        ),
        (
            '<span class="sub caseb"><span class="sub-ref">정답</span><span class="sub-hyp">전사</span></span>',
            "Case B",
            '한 단어/문장이 단어 중간에서 쪼개짐(예: "올렸"⏎"습니다"). '
            "치명적 오류로 간주한다 — 원인을 반드시 수정해야 하는 대상(hard-fail).",
        ),
        (
            '<span class="trigger trigger--silence">⟨silence⟩</span>',
            "확정 트리거",
            "문장이 확정된 원인: silence=침묵, punctuation=구두점, "
            "speaker_change=화자전환, language_switch=언어전환(none=미표기).",
        ),
    ]
    rows = "".join(
        '<div class="legend-item">'
        f'<span class="legend-swatch">{swatch}</span>'
        f'<span class="legend-label">{_esc(label)}</span>'
        f'<span class="legend-desc">{desc}</span>'
        "</div>"
        for swatch, label, desc in items
    )
    return f'<div class="legend"><div class="legend-title">범례(표시 기호 설명)</div>{rows}</div>'


_CSS = """
:root {
  --bg: #ffffff; --fg: #1a1a1a; --muted: #666666; --border: #dddddd;
  --card-bg: #f7f7f7; --eq: #1a1a1a; --del: #c0392b; --ins-bg: #d6e9ff; --ins-fg: #1a5fb4;
  --sub-bg: #fff3cd; --sub-fg: #7a5c00; --caseb: #c0392b; --chip-bg: #eeeeee; --chip-fg: #444444;
  --link: #1a5fb4;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #17181a; --fg: #e8e8e8; --muted: #9a9a9a; --border: #3a3a3a;
    --card-bg: #212225; --eq: #e8e8e8; --del: #ff8a80; --ins-bg: #133a5c; --ins-fg: #82b1ff;
    --sub-bg: #4a3f1a; --sub-fg: #ffd54f; --caseb: #ff5252; --chip-bg: #2a2b2e; --chip-fg: #cfcfcf;
    --link: #82b1ff;
  }
}
* { box-sizing: border-box; }
body {
  background: var(--bg); color: var(--fg); margin: 0; padding: 1.5rem;
  font-family: -apple-system, "Segoe UI", "Malgun Gothic", sans-serif; line-height: 1.7;
}
h1 { font-size: 1.4rem; margin: 0 0 0.25rem; }
.meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 1rem; }
a { color: var(--link); }
.legend {
  border: 1px solid var(--border); border-radius: 6px; background: var(--card-bg);
  padding: 0.8rem 1rem; margin: 1rem 0; font-size: 0.95rem; color: var(--fg);
}
.legend-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 0.4rem; }
.legend-item {
  display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0;
  border-top: 1px solid var(--border);
}
.legend-item:first-of-type { border-top: none; }
.legend-swatch { flex: 0 0 auto; }
.legend-label { flex: 0 0 auto; min-width: 4.5rem; font-weight: 700; }
.legend-desc { color: var(--fg); }
table.summary-table { border-collapse: collapse; width: 100%; margin: 1rem 0 2rem; font-size: 0.9rem; }
table.summary-table th, table.summary-table td { border: 1px solid var(--border); padding: 0.4rem 0.6rem; text-align: left; }
table.summary-table thead { background: var(--card-bg); }
details.file-section { border: 1px solid var(--border); border-radius: 6px; margin-bottom: 1rem; background: var(--card-bg); }
details.file-section summary { cursor: pointer; font-weight: 600; padding: 0.6rem 0.8rem; }
.file-summary { padding: 0 0.8rem 0.5rem; color: var(--muted); font-size: 0.85rem; }
.run { border-top: 1px solid var(--border); padding: 0.6rem 0.8rem; }
.run-metrics { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.4rem; }
.caseb-flag { color: var(--caseb); font-weight: 700; }
.diff { font-size: 0.95rem; word-break: keep-all; }
.diff .eq, .legend .eq { color: var(--eq); }
.diff .del, .legend .del { color: var(--del); text-decoration: line-through; opacity: 0.85; }
.diff .ins, .legend .ins { background: var(--ins-bg); color: var(--ins-fg); border-radius: 3px; padding: 0 2px; }
.diff .sub, .legend .sub { background: var(--sub-bg); color: var(--sub-fg); border-radius: 3px; padding: 0 2px; }
.diff .sub .sub-ref, .legend .sub .sub-ref { text-decoration: line-through; opacity: 0.75; margin-right: 0.3em; }
.diff .sub.caseb, .legend .sub.caseb { border: 2px solid var(--caseb); font-weight: 700; }
.diff .trigger, .legend .trigger {
  display: inline-block; background: var(--chip-bg); color: var(--chip-fg); border-radius: 999px;
  font-size: 0.75rem; padding: 0.05rem 0.5rem; margin: 0 0.2rem; vertical-align: middle;
}
"""


def render_document(title: str, groups: List[FileGroup], generated_at: str = "") -> str:
    """전체 자체완결 HTML 문서를 렌더링한다(DOCTYPE + 인라인 <style> + body, 외부 요청 0).

    prefers-color-scheme로 라이트/다크 모두 대응. <details>는 기본 open이라 별도 JS 없이도
    앵커 이동과 Ctrl+F가 항상 동작한다.
    """
    body = (
        f"<h1>{_esc(title)}</h1>"
        f'<div class="meta">생성 시각: {_esc(generated_at)}</div>'
        f"{render_legend()}"
        f"{render_summary_table(groups)}"
        + "".join(render_file_section(g) for g in groups)
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        f"<title>{_esc(title)}</title>"
        f"<style>{_CSS}</style>"
        f"</head><body>{body}</body></html>"
    )


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: python scripts/render_eval_report.py <json경로...> [--output PATH] [--title STR]."""
    parser = argparse.ArgumentParser(
        description="STT 평가 결과(.omc/benchmarks/*.json)를 단어 단위 색깔 하이라이트 HTML로 렌더링한다."
    )
    parser.add_argument("json_paths", nargs="+", type=Path, help="scripts/eval.py --output으로 저장한 JSON 파일 경로(들)")
    parser.add_argument("--output", type=Path, default=None, help="출력 HTML 경로(기본: .omc/transcripts/eval_report_<타임스탬프>.html)")
    parser.add_argument("--title", type=str, default="STT 평가 리포트", help="리포트 제목")
    args = parser.parse_args(argv)

    try:
        reports = load_reports(args.json_paths)
    except OSError as e:
        print(f"[render_eval_report] 오류: JSON 파일을 읽을 수 없습니다: {e}", file=sys.stderr)
        return 1

    groups = group_files(reports)
    if not groups:
        print("[render_eval_report] 경고: 렌더링할 파일 결과가 없습니다.", file=sys.stderr)

    output_path = args.output
    if output_path is None:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        output_path = Path(".omc/transcripts") / f"eval_report_{ts}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    html_doc = render_document(args.title, groups, generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
    output_path.write_text(html_doc, encoding="utf-8")
    print(f"[render_eval_report] 리포트 생성: {output_path} (파일 {len(groups)}개, 총 {sum(len(g.runs) for g in groups)}회차)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
