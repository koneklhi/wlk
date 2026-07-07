# -*- coding: utf-8 -*-
"""CASE3 환각 폭주 진단 스크립트(`scripts/analyze_case3_hallucination.py`) 유닛테스트.

가짜 서버로그/전사 텍스트로 반복 카운트·로그 파싱·상호참조 로직을 검증한다.
`scripts/`는 패키지가 아니므로 `sys.path`에 추가해 임포트한다(`scripts/eval.py`와
동일한 방식).
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from analyze_case3_hallucination import (  # noqa: E402
    find_ngram_repeat_runs,
    main,
    parse_log,
    sliding_ttr_collapse,
    summarize_log,
    summarize_transcript,
    tokenize,
)

# ── tokenize ────────────────────────────────────────────────────────────────

def test_tokenize_lowercases_and_strips_punctuation():
    words = tokenize("Thank you! Thank you.")
    assert words == ["thank", "you", "thank", "you"]


def test_tokenize_handles_korean_and_mixed():
    words = tokenize("네, 감사합니다. Thank you 감사합니다")
    assert words == ["네", "감사합니다", "thank", "you", "감사합니다"]


# ── find_ngram_repeat_runs ───────────────────────────────────────────────────

def test_detects_bigram_repeat_storm():
    """"thank you" 4연속 반복 — n=2, repeat_count=4로 탐지되어야 한다."""
    words = tokenize("Thank you thank you thank you thank you")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3)
    assert len(runs) == 1
    run = runs[0]
    assert run.n == 2
    assert run.repeat_count == 4
    assert run.ngram == "thank you"


def test_detects_unigram_repeat_run_language_agnostic():
    """단일 단어 반복(언어 무관 — 한글 어절 반복도 동일하게 잡혀야 함, 특정 문구 하드코딩 없음)."""
    words = tokenize("아 아 아 아 진짜")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3)
    assert len(runs) == 1
    assert runs[0].n == 1
    assert runs[0].repeat_count == 4
    assert runs[0].ngram == "아"


def test_no_false_positive_on_normal_varied_text():
    """반복이 없는 정상 문장은 storm으로 잡히면 안 된다(오탐 방지, 가장 중요)."""
    words = tokenize(
        "President Obama and I discussed the denuclearization of North Korea "
        "and reaffirmed our commitment to a strong alliance"
    )
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3)
    assert runs == []


def test_min_run_threshold_respected():
    """반복이 min_run 미만이면 storm으로 잡지 않는다(2회 반복은 통과)."""
    words = tokenize("Thank you thank you")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3)
    assert runs == []


def test_larger_n_consumes_before_smaller_n_no_double_count():
    """n=2 반복이 먼저 소비되면 그 구간이 n=1 반복으로 이중 계산되지 않는다."""
    words = tokenize("thank you thank you thank you")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3)
    assert len(runs) == 1
    assert runs[0].n == 2
    total_consumed = sum(r.n_words_consumed for r in runs)
    assert total_consumed == len(words)  # 전체 6단어가 정확히 한 번씩만 run에 귀속


def test_gap_tolerant_detects_interrupted_filler_storm():
    """실측 bong1 웃음구간 패턴 재현: "Thank you very much. Thank you. Thank you The Rock."
    — "thank you" 반복 사이에 "very much"(2단어) 변주가 끼어 무간격(gap=0)이 아니다.
    gap-tolerant 클러스터링(기본 max_gap=3)이 이를 하나의 storm(count=3)으로 묶어야 한다.
    """
    words = tokenize("Thank you very much. Thank you. Thank you The Rock.")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3, max_gap=3)
    assert len(runs) == 1
    run = runs[0]
    assert run.ngram == "thank you"
    assert run.repeat_count == 3


def test_gap_tolerant_respects_max_gap_limit():
    """간격이 max_gap을 넘으면 같은 클러스터로 묶지 않는다(오탐 방지 — 자연스러운 재등장과 구분)."""
    # "thank you" 두 occurrence 사이에 5단어 간격(max_gap=3 초과) → 별도 취급, storm 미달(count<3)
    words = tokenize("Thank you one two three four five thank you")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3, max_gap=3)
    assert runs == []


def test_concentration_filter_suppresses_naturally_recurring_common_word():
    """실측 bong1 오탐 재현: 흔한 기능어("the")가 문서 전체에 걸쳐 자연스럽게 반복되면서
    우연히 일부가 gap-tolerant 클러스터 조건을 만족해도, 그 단어의 문서 전체 등장 중
    클러스터가 차지하는 비율(국소집중도)이 낮으면 storm으로 보고하지 않아야 한다.
    (실측: "the"가 문서 곳곳에 흩어져 총 28회 등장, 그중 5회만 우연히 국소적으로 모임.)
    """
    words = tokenize(
        "the the the apple banana cherry date fig the grape hill ink jelly kelp "
        "the lime mango nectarine orange papaya the quince raspberry strawberry tomato umbrella the vector"
    )
    runs = find_ngram_repeat_runs(words, max_n=1, min_run=3, max_gap=3, min_concentration=0.5)
    assert runs == []


def test_concentration_filter_keeps_locally_concentrated_rare_word():
    """실측 ytn2 진짜 환각 재현: "김정은"류 반복은 문서 다른 곳엔 전혀 안 나타나고
    거의 전부가 이 클러스터 안에 몰려있다(국소집중도 높음) — storm으로 유지돼야 한다.
    """
    words = tokenize("zibbo zibbo zibbo apple banana cherry date fig grape kiwi lemon mango")
    runs = find_ngram_repeat_runs(words, max_n=1, min_run=3, max_gap=3, min_concentration=0.5)
    assert len(runs) == 1
    assert runs[0].ngram == "zibbo"
    assert runs[0].repeat_count == 3


def test_two_separate_storms_both_detected():
    words = tokenize("Thank you thank you thank you okay 감사합니다 감사합니다 감사합니다")
    runs = find_ngram_repeat_runs(words, max_n=4, min_run=3)
    assert len(runs) == 2
    ngrams = {r.ngram for r in runs}
    assert "thank you" in ngrams
    assert "감사합니다" in ngrams


# ── sliding_ttr_collapse ─────────────────────────────────────────────────────

def test_ttr_collapse_detected_for_narrow_vocabulary_window():
    words = (["thank", "you", "so", "much"] * 6)  # 24 단어, 고유어 4개뿐 → TTR 낮음
    collapsed = sliding_ttr_collapse(words, window=20, step=10, threshold=0.6)
    assert len(collapsed) >= 1
    assert all(w["ttr"] <= 0.6 for w in collapsed)


def test_ttr_collapse_not_triggered_for_varied_text():
    words = [f"word{i}" for i in range(30)]  # 전부 고유어
    collapsed = sliding_ttr_collapse(words, window=20, step=10, threshold=0.6)
    assert collapsed == []


def test_ttr_collapse_empty_when_shorter_than_window():
    words = ["a", "b", "c"]
    assert sliding_ttr_collapse(words, window=20, step=10) == []


# ── summarize_transcript ─────────────────────────────────────────────────────

def test_summarize_transcript_aggregates_storms_and_ratio():
    text = "Thank you thank you thank you very much 감사합니다"
    s = summarize_transcript(text, max_n=4, min_run=3)
    assert s["storm_count"] == 1
    assert s["max_repeat_count"] == 3
    assert s["repeated_word_total"] == 6  # "thank you" x3 = 6 단어
    assert s["n_words"] == 9
    assert s["repeated_word_ratio"] == 6 / 9


def test_summarize_transcript_empty_text():
    s = summarize_transcript("", max_n=4, min_run=3)
    assert s["n_words"] == 0
    assert s["storm_count"] == 0
    assert s["overall_ttr"] is None
    assert s["repeated_word_ratio"] is None


# ── parse_log / summarize_log ────────────────────────────────────────────────

_FAKE_LOG_LINES = [
    "2026-07-07 10:00:00 - INFO - [TraceTokens] DEBUG 레벨 로깅 활성화 (backend + align_att_base)\n",
    "2026-07-07 10:00:01 - DEBUG - Output: 안녕하세요\n",
    "2026-07-07 10:00:02 - INFO - [NewSpeaker] spk=0→1 det_before=en eager=en\n",
    "2026-07-07 10:00:02 - INFO - [NewSpeaker] spk=1 det_after=en (eager_applied=True)\n",
    "2026-07-07 10:00:03 - WARNING - [ScriptMismatchFilter] lang=ko 반대스크립트 반복 세그먼트 드롭: Thank you thank you thank you\n",
    "2026-07-07 10:00:04 - DEBUG - Output: 정경두 국방장관과 저는\n",
    "2026-07-07 10:00:10 - WARNING - [QualityGate] avg_logprob -2.500 < -2.000 — suppressing: This is the sky\n",
    "2026-07-07 10:00:11 - WARNING - [QualityGate] 5 consecutive suppressions — refresh_segment\n",
    "2026-07-07 10:00:12 - WARNING - SimulStreaming stall recovery: 12.3s without output (end=42.3s) — forcing segment refresh.\n",
    "2026-07-07 10:00:13 - INFO - [CrossBatchFilter] 반복 제거: 'you' (prev='you')\n",
    "2026-07-07 10:00:14 - WARNING - [BatchRepeatFilter] 배치 내 반복 '아' ×4 — 배치 드롭+리셋\n",
    "2026-07-07 10:00:15 - WARNING - [HallucinationFilter] 환각 루프 임계치 초과 — context 리셋 (count=5)\n",
    "2026-07-07 10:00:16 - WARNING - [ForeignLang] '(speaking in foreign language)' 감지 → 즉시 언어재감지 트리거\n",
    "2026-07-07 10:00:16 - WARNING - [ForeignLang] 드롭 텍스트: (speaking in foreign language)\n",
]


def test_parse_log_extracts_all_event_kinds():
    r = parse_log("fake.log", _FAKE_LOG_LINES)
    assert r.trace_tokens_on is True
    assert r.output_count == 2
    assert r.tensor_mismatch_count == 0
    assert len(r.new_speaker_lines) == 1
    assert r.new_speaker_eager_applied == 1
    assert r.quality_gate_suppressions == 1
    assert len(r.quality_gate_refreshes) == 1
    assert len(r.stall_recoveries) == 1
    assert r.cross_batch_drops == 1
    kinds = [ev.kind for ev in r.drop_events]
    assert "script_mismatch" in kinds
    assert "batch_repeat" in kinds
    assert "hallucination_reset" in kinds
    assert "foreign_lang_detect" in kinds
    assert "foreign_lang_dropped_text" in kinds
    assert "quality_gate_logprob" in kinds


def test_summarize_log_counts_by_kind_and_near_speaker_change():
    r = parse_log("fake.log", _FAKE_LOG_LINES)
    s = summarize_log(r)
    assert s["new_speaker_call_count"] == 1
    assert s["script_mismatch_drop_count"] == 1
    assert s["foreign_lang_drop_count"] == 1
    assert s["batch_repeat_drop_count"] == 1
    assert s["hallucination_reset_count"] == 1
    assert s["is_broken"] is False
    # ScriptMismatchFilter(line 5)는 NewSpeaker(line 3) 근처 → 인접으로 분류돼야 함
    assert s["drop_events_near_speaker_change"] >= 1


def test_summarize_log_flags_broken_on_tensor_mismatch():
    lines = list(_FAKE_LOG_LINES) + [
        "2026-07-07 10:00:20 - ERROR - SimulStreaming processing error: size of tensor a (8) "
        "must match the size of tensor b (4) at non-singleton dimension 1\n",
    ]
    r = parse_log("fake.log", lines)
    s = summarize_log(r)
    assert s["tensor_mismatch_count"] == 1
    assert s["is_broken"] is True


def test_no_new_speaker_calls_when_file_has_no_speaker_change():
    """sbs1처럼 화자전환이 아예 없는 로그 — new_speaker_call_count=0이어야 하며,
    이는 '게이트가 못 잡음'이 아니라 '게이트 진입로 자체가 없음'을 뜻한다(문서화된 구분).
    """
    lines = [
        "2026-07-07 10:00:00 - INFO - [TraceTokens] DEBUG 레벨 로깅 활성화\n",
        "2026-07-07 10:00:01 - DEBUG - Output: 안녕하세요\n",
        "2026-07-07 10:00:02 - WARNING - [QualityGate] avg_logprob -2.500 < -2.000 — suppressing: Thank you\n",
    ]
    r = parse_log("fake.log", lines)
    s = summarize_log(r)
    assert s["new_speaker_call_count"] == 0
    assert s["script_mismatch_drop_count"] == 0


# ── main() 스모크 테스트 (임시 파일로 CLI 통합 확인) ─────────────────────────────

def test_main_runs_end_to_end_on_transcript_only(tmp_path):
    txt = tmp_path / "bong1_C_R1.txt"
    txt.write_text(
        "파일: test_data/bong1.wav\n경로: C | 회차: R1\nWER: 25.0% | F1: 50.0%\n"
        "\n[전사]\nThank you thank you thank you very much\n"
        "\n[정답]\n(정답 없음)\n",
        encoding="utf-8",
    )
    rc = main(["--transcripts", str(txt), "--per-file"])
    assert rc == 0


def test_main_runs_end_to_end_on_log_and_transcript_matched_pair(tmp_path):
    log = tmp_path / "server_bong1_C_R1_20260707_100000.log"
    log.write_text("".join(_FAKE_LOG_LINES), encoding="utf-8")
    txt = tmp_path / "bong1_C_R1.txt"
    txt.write_text(
        "파일: test_data/bong1.wav\n경로: C | 회차: R1\nWER: 25.0% | F1: 50.0%\n"
        "\n[전사]\nThank you thank you thank you\n"
        "\n[정답]\n(정답 없음)\n",
        encoding="utf-8",
    )
    rc = main(["--logs", str(log), "--transcripts", str(txt), "--per-file"])
    assert rc == 0


def test_main_requires_at_least_one_source():
    import pytest
    with pytest.raises(SystemExit):
        main([])
