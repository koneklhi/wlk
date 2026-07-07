# -*- coding: utf-8 -*-
"""CASE2 코드스위칭 서두유실 진단 로그 분석기 (측정용, 코드 무수정).

`.omc/server_logs/server_*.log`(또는 임의 서버 로그)를 파싱해 언어전환(코드스위칭) 경계
부근에서 관측되는 위험 신호를 집계한다. 표준 라이브러리만 사용한다. analyze_case1_boundaries.py와
동일한 스타일(정규식 기반 라인 파싱 + 집계)을 따른다.

⚠️ 범위와 한계: 이 스크립트는 **서버 로그만** 분석한다. 실제 단어 유실 여부(정답 대비 확정)는
로그만으로는 확인할 수 없다 — 유실된 단어는 대개 어떤 필터도 발동시키지 않고 조용히 결측되므로
로그에 직접적인 흔적을 남기지 않는다. 여기서 집계하는 지표는 전부 **간접 위험 신호(proxy)**이며,
실제 유실 여부·양상은 benchmark JSON의 reference와 transcription을 직접 대조해야 확정된다
(CASE2 조사 2단계에서 수행한 방식 — eval_*.json의 "files[]" 중 audio_file이 ytn2인 항목 참고).

⚠️ **로그 채집 전제조건(3단계 확장에서 확인된 함정)**: 아래 신호 대부분(LangSwitch·SwitchTaxMeasure
의 일부, EndSilence·NewSpeaker·LangDetectDeferred·FirstTimestamp 전부)은 backend.py·
align_att_base.py 로거가 INFO 이상(일부는 DEBUG)으로 열려 있어야 로그에 나온다. basic_server.py는
이 두 로거를 **`--trace-tokens`가 켜졌을 때만** DEBUG로 올린다 — 꺼진 채 측정하면 root logger가
WARNING으로 두 로거를 억제해 아래 신호가 전부 "0"으로 나온다. 이는 "감지 안 됨(dormant)"이 아니라
"애초에 로그가 없음"이며, 과거 라운드의 오판 원인 후보 중 하나이기도 하다. 이 스크립트는 각 로그에
"[TraceTokens] DEBUG 레벨 로깅 활성화" 라인이 있는지 자동 확인해 없으면 경고를 출력한다.

집계 대상 이벤트 (backend.py / align_att_base.py 로그 문자열 기준):

  신호 1 — tensor mismatch / 처리 예외 (backend.py SimulStreamingOnlineProcessor.process_iter):
    "SimulStreaming processing error: {msg}" → 매 반복(iteration) 예외 발생 시 1회. 해당 반복에서
    나올 예정이던 토큰이 전부 유실된다(except 절이 빈 리스트 반환). 메시지가
    "size of tensor a (N) must match ... tensor b (M) ... dimension (D)" 형태면 N/M/D를 추출해
    **연쇄(cascade) 탐지**에 쓴다 — 과거(CASE1 중간 개발판, e210465 이전) 관측된 실패 양상은 b가
    고정된 채 a가 반복마다 고정폭(step)만큼 증가하며 회복 없이 반복되는 것이었다(예: 8→12→16→20…,
    다음 장문 침묵 전까지 최대 수십 회 반복 — 그 구간 전사가 통째로 소실됨). logger.exception이라
    항상 ERROR 레벨로 찍혀 --trace-tokens 유무와 무관하게 항상 보인다.

  신호 2 — 언어전환 보호경로 가동 여부 + 전환세금(재방출) (align_att_base.py _apply_detected_language):
    "[LangSwitch] 토크나이저 적용: {lang} (prev={prev}, switch={bool}, skip_trim={bool})" → switch=True인
    경우만 실제 "전환"으로 처리되어 _trim_segments_to_recent(LANG_SWITCH_KEEP_SECS=2.5)가 실행되고
    pending_language_switch가 arm된다. switch=False는 "최초 감지"로 취급되어 트림도 마커도 없다 —
    diarization ON 환경에서 이 경로가 실제로 얼마나 **가동(engage)**되는지 자체가 핵심 지표다.
    "[LangSwitch] 문장 경계 마커 방출 @ {t}s (lang={lang})" → 마커 실제 방출 시각(오디오 상대 초).
    "[SwitchTaxMeasure] 전환 직후 배치 {overlap}/{total} 단어가 직전 tail과 겹침 (tail={list})" →
    전환 직후 첫 배치가 직전(구언어) 방출 tail과 겹치는 정도. overlap/total 비율이 높을수록 "새
    배치가 옛 내용 재방출로 채워짐 = 새 언어의 진짜 서두는 아직 안 나왔을 가능성"의 프록시로 삼는다.
    "[LangSwitch] 전환 전 오디오 {removed}s 절단 (유지 {kept}s)" → DEBUG 레벨(로그 레벨에 따라
    없을 수 있음). 남아있으면 실제 트림량을 알려준다(유지량이 짧으면 서두 절단 위험 상승).

  신호 3 — broken-run 격리 (align_att_base.py infer의 "Output:" + 신호1의 tensor mismatch):
    "Output: {text}" → infer() 정상 완료 시 매번 1회. 한 로그에 이 라인이 0개면 그 회차는 서버가
    전사를 단 한 번도 완료 못한 것 — tensor mismatch 캐스케이드나 turbo stall 등으로 오염된 런일
    가능성이 높다. tensor_mismatch_count > 0 인 로그도 마찬가지로 "무효(broken)"로 분리한다. 과거
    라운드가 "언어전환 감지 경로가 전부 dormant"라고 오판한 원인이 바로 이걸 안 나눈 것이었다 —
    유효 런과 분리 집계해야 실제 신호를 볼 수 있다.

  신호 4 — 침묵 분기 히스토그램 (backend.py end_silence):
    "[EndSilence] dur={d}s branch={long|short|none} det_lang={x} lang_before_reset={y}" →
    매 end_silence() 호출마다 어느 분기(장침묵≥2.0s / 단침묵 언어재확인 / 해당없음)를 탔는지와
    그 시점 언어 상태 스냅샷.
    "[EndSilence] long-silence 리셋 직전(폐기 예정): det_lang={x}→None lang_before_reset={y}→None" →
    long 분기에서만 나온다. y(lang_before_reset)가 "None"이 아니면 진짜 뭔가(직전 화자전환에서
    승계된 언어 등)가 폐기된 것 — 긴 침묵이 "그냥 재감지 허용"이 아니라 "미처리 전환판정을 조용히
    버리는" 지점일 수 있다는 가설의 직접 증거.

  신호 5 — 부트스트랩 교착 사이클 (align_att_base.py _detect_language_if_needed / infer):
    "[LangDetectDeferred] 감지 보류: first_timestamp=None, eager_lang_detect=False (segments_len={s}s)"
    → DEBUG 레벨. 언어감지가 "아직 first_timestamp가 없어서" 매 infer() 호출마다 보류되는 이벤트.
    "[FirstTimestamp] 최초 설정: {t}s (segments_len={s}s)" → first_timestamp가 실제로 설정된 시점.
    이 스크립트는 두 이벤트를 "리셋 경계"(EndSilence의 long 분기 / NewSpeaker) 기준으로 사이클로
    나눠, 한 사이클 안에서 감지보류가 1회 이상 발생했는데 그 사이클이 끝날 때까지(다음 리셋 또는
    파일 끝) first_timestamp가 한 번도 안 잡힌 경우를 "교착(stuck)"으로 자동 플래그한다. 같은
    사이클 안에서 발생한 LangSwitch switch=True/False 발동 횟수도 사이클(리셋 타입)별로 함께
    집계해 "각 분기에서 전환이 실제로 얼마나 발동했는지"를 answer 한다.

  보조 신호 — 기타 유실/리셋 인접 이벤트(있으면 카운트만 — CASE2 판정에 단독으로 쓰이진 않음):
    "[CrossBatchFilter] 반복 제거: {word} (prev={prev})" — 배치 경계 단일 단어 반복 제거.
    `_last_emitted_word`는 언어전환(is_switch=True) 시 리셋되지 않는 코드 갭이 있다(코드 조사 결과,
    __init__/장침묵/화자전환/배치반복드롭/환각리셋/stall복구 시에만 리셋됨) — 이 이벤트가 전환
    직후 발생하면 새 언어 첫 단어가 구언어 단어와 우연히 일치해 삭제됐을 위험을 뜻한다.
    "[BatchRepeatFilter] 배치 내 반복 {word} ×{n} — 배치 드롭+리셋" — 배치 전체 폐기.
    "[HallucinationFilter] 환각 루프 임계치 초과 — context 리셋" — 강제 refresh(세그먼트 절단 동반).
    "SimulStreaming stall recovery: {sec}s without output" — 무출력 워치독 강제 refresh.
    "[ForeignLang] '(speaking in foreign language)' 감지" — 외국어 환각 감지, 해당 텍스트 드롭.

사용:
    python scripts/analyze_case2_frontloss.py .omc/server_logs/server_ytn2_C_*.log
    python scripts/analyze_case2_frontloss.py path/to/one.log path/to/two.log --per-file
    python scripts/analyze_case2_frontloss.py path/to/*.log --include-broken  # broken도 합계에 포함
"""

import argparse
import glob
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Windows 콘솔/리다이렉트 기본 코드페이지(cp949 등)에서 한글·em-dash 등이 깨지거나
# UnicodeEncodeError로 죽는 것을 방지 — 표준 라이브러리만 사용하는 진단 스크립트이므로
# 여기서 직접 보정한다(analyze_case1_boundaries.py는 출력에 비-ASCII 문자가 없어 문제가 없었음).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── 로그 라인 패턴 ──────────────────────────────────────────────────────────
_PROC_ERROR_RE = re.compile(r"SimulStreaming processing error:\s*(.+)$")
_TENSOR_SIZE_RE = re.compile(
    r"size of tensor a \((\d+)\) must match the size of tensor b \((\d+)\) at non-singleton dimension (\d+)"
)

_LANGSWITCH_APPLY_RE = re.compile(
    r"\[LangSwitch\] 토크나이저 적용: (\S+) \(prev=(\S+), switch=(True|False), skip_trim=(True|False)\)"
)
_LANGSWITCH_MARKER_RE = re.compile(r"\[LangSwitch\] 문장 경계 마커 방출 @ ([\d.]+)s \(lang=(\S+)\)")
_LANGSWITCH_TRIM_RE = re.compile(r"\[LangSwitch\] 전환 전 오디오 ([\d.]+)s 절단 \(유지 ([\d.]+)s\)")

_SWITCHTAX_OVERLAP_RE = re.compile(
    r"\[SwitchTaxMeasure\] 전환 직후 배치 (\d+)/(\d+) 단어가 직전 tail과 겹침 \(tail=(\[.*\])\)"
)
_SWITCHTAX_NOOVERLAP_RE = re.compile(r"\[SwitchTaxMeasure\] 전환 직후 배치 겹침 없음 \(tail=(\[.*\])\)")

_CROSSBATCH_DROP_RE = re.compile(r"\[CrossBatchFilter\] 반복 제거: (.+) \(prev=(.+)\)\s*$")
_BATCHREPEAT_DROP_RE = re.compile(r"\[BatchRepeatFilter\] 배치 내 반복 (.+) ×(\d+) — 배치 드롭\+리셋")
_HALLUC_RESET_RE = re.compile(r"\[HallucinationFilter\] 환각 루프 임계치 초과 — context 리셋 \(count=(\d+)\)")
_STALL_RECOVER_RE = re.compile(r"SimulStreaming stall recovery: ([\d.]+)s without output")
_FOREIGNLANG_RE = re.compile(r"\[ForeignLang\] '\(speaking in foreign language\)' 감지")

_TAIL_WORD_RE = re.compile(r"'([^']*)'")

# ─── 3단계 확장 로그 패턴 (broken-run 격리 / 침묵분기 히스토그램 / 부트스트랩 교착) ─────────
_OUTPUT_LINE_RE = re.compile(r"\bOutput: ")
_TRACE_TOKENS_ON_RE = re.compile(r"\[TraceTokens\] DEBUG 레벨 로깅 활성화")

_ENDSILENCE_ENTRY_RE = re.compile(
    r"\[EndSilence\] dur=([\d.]+)s branch=(long|short|none) det_lang=(\S+) lang_before_reset=(\S+)"
)
_ENDSILENCE_LONGRESET_RE = re.compile(
    r"\[EndSilence\] long-silence 리셋 직전\(폐기 예정\): det_lang=(\S+)→None lang_before_reset=(\S+)→None"
)

_NEWSPEAKER_BEFORE_RE = re.compile(r"\[NewSpeaker\] spk=(\S+)→(\S+) det_before=(\S+) eager=(\S+)")
_NEWSPEAKER_AFTER_RE = re.compile(r"\[NewSpeaker\] spk=(\S+) det_after=(\S+) \(eager_applied=(\S+)\)")

_LANGDETECT_DEFERRED_RE = re.compile(
    r"\[LangDetectDeferred\] 감지 보류: first_timestamp=None, eager_lang_detect=False \(segments_len=([\d.]+)s\)"
)
_FIRST_TIMESTAMP_RE = re.compile(r"\[FirstTimestamp\] 최초 설정: ([\d.]+)s \(segments_len=([\d.]+)s\)")

# overlap/total 비율이 이 값 이상이면 "새 배치 대부분이 재방출" 고위험으로 플래그.
HIGH_OVERLAP_RATIO = 0.6
# 절단 후 유지 오디오가 이 값(초) 미만이면 "과도한 절단" 위험으로 플래그.
LOW_KEEP_SECS = 1.0


def _parse_tail(tail_str: str) -> List[str]:
    return _TAIL_WORD_RE.findall(tail_str)


@dataclass
class TensorMismatchEvent:
    line_no: int
    message: str
    tensor_a: Optional[int] = None
    tensor_b: Optional[int] = None
    dim: Optional[int] = None


@dataclass
class SwitchTaxEvent:
    line_no: int
    overlap: int
    total: int
    tail: List[str] = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.overlap / self.total if self.total else 0.0


@dataclass
class FileResult:
    """로그 한 파일을 파싱한 원시 이벤트 모음. 라인 번호는 이 파일 내부 기준이다."""
    path: str
    n_lines: int = 0
    tensor_events: List[TensorMismatchEvent] = field(default_factory=list)
    other_error_events: List[TensorMismatchEvent] = field(default_factory=list)
    apply_true: List[int] = field(default_factory=list)   # switch=True로 적용된 라인
    apply_false: List[int] = field(default_factory=list)  # switch=False(최초감지)로 적용된 라인
    markers: List[Tuple[int, float, str]] = field(default_factory=list)  # (line_no, sec, lang)
    trims: List[Tuple[int, float, float]] = field(default_factory=list)  # (line_no, removed, kept)
    switch_tax: List[SwitchTaxEvent] = field(default_factory=list)       # overlap>0만
    switch_tax_clean: int = 0                                            # overlap==0 카운트
    cross_batch_drops: List[Tuple[int, str, str]] = field(default_factory=list)
    batch_repeat_drops: List[Tuple[int, str, int]] = field(default_factory=list)
    halluc_resets: List[int] = field(default_factory=list)
    stall_recoveries: List[Tuple[int, float]] = field(default_factory=list)
    foreign_lang_hits: List[int] = field(default_factory=list)

    # --- 3단계 확장: broken-run 격리 ---
    output_count: int = 0          # "Output: ..." 라인 수(align_att_base.infer 정상완료)
    trace_tokens_on: bool = False  # "[TraceTokens] DEBUG 레벨 로깅 활성화" 라인 존재 여부

    # --- 3단계 확장: 침묵 분기 히스토그램 ---
    endsilence_events: List[Tuple[int, float, str, str, str]] = field(default_factory=list)
    # (line_no, duration, branch, det_lang, lang_before_reset) — end_silence() 진입 시점 스냅샷
    endsilence_long_resets: List[Tuple[int, str, str]] = field(default_factory=list)
    # (line_no, det_lang_before, lang_before_reset_before) — long 분기에서 None으로 덮이기 직전 값

    # --- 3단계 확장: 부트스트랩 교착 ---
    lang_detect_deferred: List[Tuple[int, float]] = field(default_factory=list)  # (line_no, segments_len)
    first_timestamp_events: List[Tuple[int, float, float]] = field(default_factory=list)
    # (line_no, first_timestamp_value, segments_len)
    new_speaker_before: List[Tuple[int, str, str, str, str]] = field(default_factory=list)
    # (line_no, spk_from, spk_to, det_before, eager)
    new_speaker_after: List[Tuple[int, str, str, str]] = field(default_factory=list)
    # (line_no, spk, det_after, eager_applied)
    # 사이클(리셋 경계) 분석용 통합 이벤트 스트림 — 반드시 로그에 나온 순서 그대로 append 한다.
    # kind ∈ {"reset_long_silence", "reset_new_speaker", "deferred", "first_timestamp",
    #         "switch_true", "switch_false"}
    state_events: List[Tuple[int, str]] = field(default_factory=list)


def parse_log(path: str, lines: List[str]) -> FileResult:
    """로그 라인 시퀀스를 CASE2 신호 집계 구조로 변환한다."""
    r = FileResult(path=path, n_lines=len(lines))
    for i, line in enumerate(lines, start=1):
        if _TRACE_TOKENS_ON_RE.search(line):
            r.trace_tokens_on = True
            continue

        if _OUTPUT_LINE_RE.search(line):
            r.output_count += 1
            continue

        m = _PROC_ERROR_RE.search(line)
        if m:
            msg = m.group(1).strip()
            mt = _TENSOR_SIZE_RE.search(msg)
            if mt:
                r.tensor_events.append(TensorMismatchEvent(
                    line_no=i, message=msg,
                    tensor_a=int(mt.group(1)), tensor_b=int(mt.group(2)), dim=int(mt.group(3)),
                ))
            else:
                r.other_error_events.append(TensorMismatchEvent(line_no=i, message=msg))
            continue

        m = _LANGSWITCH_APPLY_RE.search(line)
        if m:
            is_switch = m.group(3) == "True"
            (r.apply_true if is_switch else r.apply_false).append(i)
            r.state_events.append((i, "switch_true" if is_switch else "switch_false"))
            continue

        m = _LANGSWITCH_MARKER_RE.search(line)
        if m:
            r.markers.append((i, float(m.group(1)), m.group(2)))
            continue

        m = _LANGSWITCH_TRIM_RE.search(line)
        if m:
            r.trims.append((i, float(m.group(1)), float(m.group(2))))
            continue

        m = _SWITCHTAX_OVERLAP_RE.search(line)
        if m:
            r.switch_tax.append(SwitchTaxEvent(
                line_no=i, overlap=int(m.group(1)), total=int(m.group(2)), tail=_parse_tail(m.group(3)),
            ))
            continue

        if _SWITCHTAX_NOOVERLAP_RE.search(line):
            r.switch_tax_clean += 1
            continue

        m = _CROSSBATCH_DROP_RE.search(line)
        if m:
            r.cross_batch_drops.append((i, m.group(1).strip(), m.group(2).strip()))
            continue

        m = _BATCHREPEAT_DROP_RE.search(line)
        if m:
            r.batch_repeat_drops.append((i, m.group(1).strip(), int(m.group(2))))
            continue

        m = _HALLUC_RESET_RE.search(line)
        if m:
            r.halluc_resets.append(i)
            continue

        m = _STALL_RECOVER_RE.search(line)
        if m:
            r.stall_recoveries.append((i, float(m.group(1))))
            continue

        if _FOREIGNLANG_RE.search(line):
            r.foreign_lang_hits.append(i)
            continue

        m = _ENDSILENCE_ENTRY_RE.search(line)
        if m:
            r.endsilence_events.append((i, float(m.group(1)), m.group(2), m.group(3), m.group(4)))
            continue

        m = _ENDSILENCE_LONGRESET_RE.search(line)
        if m:
            r.endsilence_long_resets.append((i, m.group(1), m.group(2)))
            r.state_events.append((i, "reset_long_silence"))
            continue

        m = _NEWSPEAKER_BEFORE_RE.search(line)
        if m:
            r.new_speaker_before.append((i, m.group(1), m.group(2), m.group(3), m.group(4)))
            r.state_events.append((i, "reset_new_speaker"))
            continue

        m = _NEWSPEAKER_AFTER_RE.search(line)
        if m:
            r.new_speaker_after.append((i, m.group(1), m.group(2), m.group(3)))
            continue

        m = _LANGDETECT_DEFERRED_RE.search(line)
        if m:
            r.lang_detect_deferred.append((i, float(m.group(1))))
            r.state_events.append((i, "deferred"))
            continue

        m = _FIRST_TIMESTAMP_RE.search(line)
        if m:
            r.first_timestamp_events.append((i, float(m.group(1)), float(m.group(2))))
            r.state_events.append((i, "first_timestamp"))
            continue

    return r


def _nearest_distance(line_no: int, anchors: List[int]) -> Optional[int]:
    """anchors(라인 번호 목록) 중 line_no와 가장 가까운 것과의 거리(라인 수)를 반환."""
    if not anchors:
        return None
    return min(abs(a - line_no) for a in anchors)


def detect_cascades(events: List[TensorMismatchEvent]) -> List[dict]:
    """tensor_b가 동일한 채 tensor_a가 파싱 순서대로 고정폭 증가하는 연쇄를 탐지한다.

    과거(CASE1 중간 개발판, e210465 이전) ytn2 로그에서 관측된 실패 양상 — 언어전환 직후 한 번
    촉발되면 b는 고정(관측값 4), a는 반복마다 동일한 step(관측값 +4)만큼 늘며 회복 없이 반복됨
    (반복마다 그 iteration 출력 전체가 소실됨). events는 호출측에서 반드시 **단일 파일** 것만
    순서대로 넘겨야 한다 — 여러 파일의 이벤트를 이어붙이면 서로 무관한 이벤트가 인접한 것처럼
    섞여 오탐 연쇄가 생긴다. 길이 ≥3 연쇄만 보고한다.
    """
    cascades: List[dict] = []
    run: List[TensorMismatchEvent] = []
    step: Optional[int] = None

    def flush():
        if len(run) >= 3:
            cascades.append({
                "start_line": run[0].line_no,
                "end_line": run[-1].line_no,
                "length": len(run),
                "tensor_b": run[0].tensor_b,
                "a_first": run[0].tensor_a,
                "a_last": run[-1].tensor_a,
                "step": step,
            })

    for ev in events:
        if ev.tensor_a is None or ev.tensor_b is None:
            flush()
            run, step = [], None
            continue
        if not run:
            run = [ev]
            continue
        prev = run[-1]
        cur_step = ev.tensor_a - prev.tensor_a
        if ev.tensor_b == prev.tensor_b and cur_step > 0 and (step is None or cur_step == step):
            step = cur_step
            run.append(ev)
        else:
            flush()
            run, step = [ev], None
    flush()
    return cascades


def analyze_bootstrap_cycles(state_events: List[Tuple[int, str]]) -> List[dict]:
    """리셋(장침묵/화자전환) 경계로 로그를 사이클로 나누고, 각 사이클의 언어감지 보류(deferred)
    횟수·first_timestamp 설정 여부·전환(switch) 발동 횟수를 집계한다.

    사이클 경계: "reset_long_silence"(end_silence 장침묵 분기 — first_timestamp를 None으로
    되돌림) 또는 "reset_new_speaker"(화자전환 — 마찬가지로 None으로 되돌림). 두 이벤트 모두
    새 사이클의 시작점이며, 그 사이클이 끝날 때까지(다음 리셋 또는 파일 끝) deferred가 1회
    이상 발생했는데 first_timestamp가 한 번도 안 잡혔으면 "stuck"(교착)으로 표시한다.

    state_events는 호출측에서 반드시 **단일 파일** 것만 로그 등장 순서대로 넘겨야 한다
    (detect_cascades와 동일 이유 — 파일을 섞으면 무관한 리셋 사이 이벤트가 한 사이클로
    잘못 묶인다).
    """
    cycles: List[dict] = []
    cur = {
        "reset_type": "initial", "start_line": 1,
        "deferred_count": 0, "first_ts_set": False,
        "switch_true": 0, "switch_false": 0,
    }

    def close(end_line: int):
        cur["end_line"] = end_line
        cur["stuck"] = cur["deferred_count"] > 0 and not cur["first_ts_set"]
        cycles.append(cur)

    last_line = 1
    for line_no, kind in state_events:
        last_line = line_no
        if kind in ("reset_long_silence", "reset_new_speaker"):
            close(line_no)
            cur = {
                "reset_type": kind, "start_line": line_no,
                "deferred_count": 0, "first_ts_set": False,
                "switch_true": 0, "switch_false": 0,
            }
        elif kind == "deferred":
            cur["deferred_count"] += 1
        elif kind == "first_timestamp":
            cur["first_ts_set"] = True
        elif kind == "switch_true":
            cur["switch_true"] += 1
        elif kind == "switch_false":
            cur["switch_false"] += 1
    close(last_line)
    return cycles


def summarize(r: FileResult) -> Dict:
    """단일 FileResult에서 신호 1~5(+보조 신호)를 집계한다. 반드시 파일 1개 단위로 호출한다."""
    switch_anchor_lines = (
        [ln for ln, _, _ in r.markers] + r.apply_true + [ev.line_no for ev in r.switch_tax]
    )
    proximities = [
        d for d in (_nearest_distance(ev.line_no, switch_anchor_lines) for ev in r.tensor_events)
        if d is not None
    ]
    cascades = detect_cascades(r.tensor_events)
    high_overlap = [e for e in r.switch_tax if e.ratio >= HIGH_OVERLAP_RATIO]
    low_keep_trims = [(ln, removed, kept) for ln, removed, kept in r.trims if kept < LOW_KEEP_SECS]

    # --- 신호 3: broken-run 판정 ---
    # trace_tokens_on=False면 Output 라인 자체가 로거 레벨에 막혀 안 나온다(정상 런이어도 0건) —
    # 이걸 "전사 실패"로 오분류하지 않도록 별도 사유로 분리하되 마찬가지로 무효(제외 대상) 처리한다.
    broken_reasons = []
    if not r.trace_tokens_on:
        broken_reasons.append("trace-tokens 꺼짐(계측 로그 없음 — Output 포함 전 신호 유실)")
    elif r.output_count == 0:
        broken_reasons.append("Output 라인 0개(전사 완료 없음)")
    if r.tensor_events:
        broken_reasons.append(f"tensor mismatch {len(r.tensor_events)}건")
    is_broken = bool(broken_reasons)

    # --- 신호 4: 침묵 분기 히스토그램 ---
    branch_counts = Counter(branch for _, _, branch, _, _ in r.endsilence_events)
    long_reset_discarded = sum(1 for _, _, lbr in r.endsilence_long_resets if lbr != "None")
    long_reset_noop = sum(1 for _, _, lbr in r.endsilence_long_resets if lbr == "None")

    # --- 신호 5: 부트스트랩 교착 사이클 ---
    cycles = analyze_bootstrap_cycles(r.state_events)
    stuck_cycles = [c for c in cycles if c["stuck"]]
    stuck_by_reset_type = Counter(c["reset_type"] for c in stuck_cycles)
    switch_by_reset_type: Dict[str, Dict[str, int]] = {}
    for c in cycles:
        bucket = switch_by_reset_type.setdefault(c["reset_type"], {"switch_true": 0, "switch_false": 0})
        bucket["switch_true"] += c["switch_true"]
        bucket["switch_false"] += c["switch_false"]

    return {
        "n_lines": r.n_lines,
        "tensor_mismatch_count": len(r.tensor_events),
        "other_error_count": len(r.other_error_events),
        "cascades": cascades,
        "tensor_proximity_to_switch_lines": proximities,
        "switch_apply_true": len(r.apply_true),
        "switch_apply_false": len(r.apply_false),
        "marker_count": len(r.markers),
        "markers": r.markers,
        "trims": r.trims,
        "low_keep_trims": low_keep_trims,
        "switch_tax_overlap_count": len(r.switch_tax),
        "switch_tax_clean_count": r.switch_tax_clean,
        "switch_tax_high_overlap": high_overlap,
        "cross_batch_drops": r.cross_batch_drops,
        "batch_repeat_drops": r.batch_repeat_drops,
        "halluc_resets": len(r.halluc_resets),
        "stall_recoveries": r.stall_recoveries,
        "foreign_lang_hits": len(r.foreign_lang_hits),

        # 신호 3
        "output_count": r.output_count,
        "trace_tokens_on": r.trace_tokens_on,
        "is_broken": is_broken,
        "broken_reasons": broken_reasons,
        "path": r.path,

        # 신호 4
        "endsilence_branch_counts": dict(branch_counts),
        "endsilence_long_reset_discarded": long_reset_discarded,
        "endsilence_long_reset_noop": long_reset_noop,

        # 신호 5
        "deferred_count": len(r.lang_detect_deferred),
        "first_timestamp_count": len(r.first_timestamp_events),
        "first_timestamp_events": r.first_timestamp_events,
        "cycles": cycles,
        "stuck_cycles": stuck_cycles,
        "stuck_by_reset_type": dict(stuck_by_reset_type),
        "switch_by_reset_type": switch_by_reset_type,
        "bootstrap_deadlock": len(stuck_cycles) > 0,

        # 화자전환 원시 이벤트(상세 출력용)
        "new_speaker_before": r.new_speaker_before,
        "new_speaker_after": r.new_speaker_after,
    }


_AGG_SUM_KEYS = (
    "n_lines", "tensor_mismatch_count", "other_error_count",
    "switch_apply_true", "switch_apply_false", "marker_count",
    "switch_tax_overlap_count", "switch_tax_clean_count", "halluc_resets", "foreign_lang_hits",
    "output_count", "deferred_count", "first_timestamp_count",
    "endsilence_long_reset_discarded", "endsilence_long_reset_noop",
)
_AGG_LIST_KEYS = (
    "cascades", "tensor_proximity_to_switch_lines", "markers", "trims", "low_keep_trims",
    "switch_tax_high_overlap", "cross_batch_drops", "batch_repeat_drops", "stall_recoveries",
    "cycles", "stuck_cycles",
)


def aggregate(summaries: List[Dict]) -> Dict:
    """파일별 summarize() 결과를 하나의 합계로 병합한다.

    라인 번호에 의존하는 하위 분석(연쇄, 최근접 거리, 사이클)은 파일별로 이미 계산된 결과이므로
    **리스트를 이어붙이기만** 한다(재계산 금지 — 서로 다른 파일의 원시 이벤트를 한 시퀀스로
    합쳐 재탐지하면 무관한 이벤트가 인접한 것처럼 섞여 오탐 연쇄를 만든다).
    """
    agg: Dict = {k: 0 for k in _AGG_SUM_KEYS}
    for k in _AGG_LIST_KEYS:
        agg[k] = []
    for s in summaries:
        for k in _AGG_SUM_KEYS:
            agg[k] += s[k]
        for k in _AGG_LIST_KEYS:
            agg[k] += s[k]

    branch_totals: Counter = Counter()
    stuck_totals: Counter = Counter()
    switch_totals: Dict[str, Counter] = {}
    for s in summaries:
        branch_totals.update(s["endsilence_branch_counts"])
        stuck_totals.update(s["stuck_by_reset_type"])
        for reset_type, counts in s["switch_by_reset_type"].items():
            switch_totals.setdefault(reset_type, Counter())
            switch_totals[reset_type].update(counts)
    agg["endsilence_branch_counts"] = dict(branch_totals)
    agg["stuck_by_reset_type"] = dict(stuck_totals)
    agg["switch_by_reset_type"] = {k: dict(v) for k, v in switch_totals.items()}
    agg["bootstrap_deadlock"] = any(s["bootstrap_deadlock"] for s in summaries)
    return agg


def _print_summary(label: str, s: Dict, detail: bool = True) -> None:
    print(label)
    print(f"  {'lines':<34s}: {s['n_lines']}")
    print(f"  {'tensor_mismatch_count':<34s}: {s['tensor_mismatch_count']}")
    print(f"  {'other_error_count':<34s}: {s['other_error_count']}")
    print(f"  {'cascade_count(len>=3)':<34s}: {len(s['cascades'])}")
    if detail:
        for c in s["cascades"]:
            print(f"    [cascade] line {c['start_line']}-{c['end_line']} len={c['length']} "
                  f"b={c['tensor_b']} a:{c['a_first']}->{c['a_last']} step=+{c['step']}")
    if s["tensor_proximity_to_switch_lines"]:
        avg = sum(s["tensor_proximity_to_switch_lines"]) / len(s["tensor_proximity_to_switch_lines"])
        print(f"  {'tensor↔switch 최근접거리(라인,평균)':<34s}: {avg:.1f} "
              f"(n={len(s['tensor_proximity_to_switch_lines'])})")
    else:
        print(f"  {'tensor↔switch 최근접거리(라인,평균)':<34s}: N/A (switch 이벤트 없음)")
    print(f"  {'switch_apply True/False':<34s}: {s['switch_apply_true']}/{s['switch_apply_false']}"
          "  (switch=True만 실제 트림+마커 arm — dormant 여부 지표)")
    print(f"  {'marker_count(문장경계 마커 방출)':<34s}: {s['marker_count']}")
    if detail:
        for ln, sec, lang in s["markers"]:
            print(f"    line {ln}: @ {sec:.2f}s lang={lang}")
        for ln, removed, kept in s["trims"]:
            print(f"    [trim] line {ln}: 절단 {removed:.2f}s / 유지 {kept:.2f}s")
    print(f"  {'switch_tax overlap>0 / clean(=0)':<34s}: "
          f"{s['switch_tax_overlap_count']}/{s['switch_tax_clean_count']}")
    print(f"  {'  高overlap(>=' + str(int(HIGH_OVERLAP_RATIO * 100)) + '%) 건수':<34s}: "
          f"{len(s['switch_tax_high_overlap'])}")
    if detail:
        for e in s["switch_tax_high_overlap"]:
            print(f"    line {e.line_no}: {e.overlap}/{e.total} ({e.ratio:.0%}) tail={e.tail}")
        for ln, removed, kept in s["low_keep_trims"]:
            print(f"    [aggressive-trim] line {ln}: 절단 {removed:.2f}s / 유지 {kept:.2f}s(<{LOW_KEEP_SECS}s)")
    print(f"  {'cross_batch_drops(단일단어 반복제거)':<34s}: {len(s['cross_batch_drops'])}")
    if detail:
        for ln, word, prev in s["cross_batch_drops"]:
            print(f"    line {ln}: {word} (prev={prev})")
    print(f"  {'batch_repeat_drops(배치 전체드롭)':<34s}: {len(s['batch_repeat_drops'])}")
    print(f"  {'hallucination_resets':<34s}: {s['halluc_resets']}")
    print(f"  {'stall_recoveries':<34s}: {len(s['stall_recoveries'])}")
    print(f"  {'foreign_lang_hits':<34s}: {s['foreign_lang_hits']}")

    # --- 신호 4: 침묵 분기 히스토그램 ---
    bc = s["endsilence_branch_counts"]
    print(f"  {'EndSilence 분기(long/short/none)':<34s}: "
          f"{bc.get('long', 0)}/{bc.get('short', 0)}/{bc.get('none', 0)}")
    print(f"  {'  long분기 lang_before_reset 폐기(값有/None)':<34s}: "
          f"{s['endsilence_long_reset_discarded']}/{s['endsilence_long_reset_noop']}")

    # --- 신호 5: 부트스트랩 교착 ---
    print(f"  {'LangDetectDeferred(감지보류) 총횟수':<34s}: {s['deferred_count']}")
    print(f"  {'FirstTimestamp 최초설정 총횟수':<34s}: {s['first_timestamp_count']}")
    print(f"  {'교착(stuck) 사이클 수':<34s}: {len(s['stuck_cycles'])}  by_reset_type={s['stuck_by_reset_type']}")
    print(f"  {'부트스트랩 교착 플래그':<34s}: {'[!] YES' if s['bootstrap_deadlock'] else 'no'}")
    print(f"  {'리셋타입별 switch(True/False) 발동':<34s}: {s['switch_by_reset_type']}")
    if detail:
        for c in s.get("stuck_cycles", []):
            print(f"    [stuck] line {c['start_line']}-{c['end_line']} reset={c['reset_type']} "
                  f"deferred={c['deferred_count']} switch(T/F)={c['switch_true']}/{c['switch_false']}")


def _print_broken_files(summaries: List[Dict]) -> None:
    broken = [s for s in summaries if s["is_broken"]]
    if not broken:
        print(f"[broken-run 격리] 무효 로그 없음 (전체 {len(summaries)}개 파일 모두 유효)")
        return
    print(f"[broken-run 격리] 무효 로그 {len(broken)}/{len(summaries)}개 — 아래는 기본 합계에서 제외됨:")
    for s in broken:
        print(f"  - {s['path']}: {', '.join(s['broken_reasons'])} (output_count={s['output_count']})")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CASE2 코드스위칭 서두유실 진단 로그 분석기")
    parser.add_argument("logs", nargs="+", help="서버 로그 파일 경로(글로브 허용)")
    parser.add_argument("--per-file", action="store_true", help="파일별 상세도 함께 출력")
    parser.add_argument(
        "--include-broken", action="store_true",
        help="broken(무효) 로그도 합계 집계에 포함(기본: 제외 후 별도 보고).",
    )
    args = parser.parse_args(argv)

    paths: List[str] = []
    for pat in args.logs:
        expanded = glob.glob(pat)
        paths.extend(expanded if expanded else [pat])

    summaries: List[Dict] = []
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError as e:
            print(f"[skip] {path}: {e}", file=sys.stderr)
            continue
        r = parse_log(path, lines)
        s = summarize(r)
        summaries.append(s)
        if not s["trace_tokens_on"]:
            print(
                f"[경고] {path}: '[TraceTokens] DEBUG 레벨 로깅 활성화' 라인이 없음 — "
                "이 로그는 --trace-tokens 없이 수집됐을 수 있고, 그 경우 LangSwitch/EndSilence/"
                "NewSpeaker/LangDetectDeferred/FirstTimestamp 신호가 전부 유실된다. "
                "아래 '0건'을 '미발동'으로 오독하지 말 것 — eval.py에 --trace-tokens를 추가했는지 먼저 확인.",
                file=sys.stderr,
            )
        if args.per_file:
            _print_summary(f"[{path}]", s, detail=True)
            print()

    print("=" * 70)
    _print_broken_files(summaries)
    print("=" * 70)

    target_summaries = summaries if args.include_broken else [s for s in summaries if not s["is_broken"]]
    suffix = "" if args.include_broken else ", broken 제외"
    label = f"[유효 로그 합계]  ({len(target_summaries)}/{len(summaries)}개 파일{suffix})"
    _print_summary(label, aggregate(target_summaries), detail=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
