# -*- coding: utf-8 -*-
"""`scripts/analyze_boundary_tail_dup.py` 유닛테스트.

`tests/test_analyze_case3_hallucination.py`와 동일 패턴 — `scripts/`는 패키지가 아니므로
`sys.path`에 추가해 임포트한다. 로그 정규식 테스트는 실측 스모크 측정(kinno, 2026-07-19,
`--trace-tokens`)에서 그대로 채집한 실제 로그 라인 포맷을 사용한다(가상의 포맷 아님).
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from analyze_boundary_tail_dup import (  # noqa: E402
    BoundaryLog,
    RefBoundary,
    RetractScanEvent,
    align_ref_to_hyp,
    boundary_missing_words,
    classify_boundaries,
    compute_language_switch_boundaries,
    detect_block_language,
    find_adjacent_ngram_duplicates,
    load_transcript_sections,
    main,
    normalize_text,
    parse_boundary_log,
    parse_speaker_blocks,
    tokenize,
)

# ── normalize_text ───────────────────────────────────────────────────────────


def test_normalize_text_lowercases_and_strips_punctuation():
    assert normalize_text("Hello, World!") == "hello world"


def test_normalize_text_keeps_korean_and_strips_period():
    assert normalize_text("안녕하세요.") == "안녕하세요"


def test_normalize_text_collapses_whitespace():
    assert normalize_text("a   b\n\nc") == "a b c"


# ── detect_block_language ────────────────────────────────────────────────────


def test_detect_block_language_korean():
    assert detect_block_language("안녕하세요 반갑습니다") == "ko"


def test_detect_block_language_english():
    assert detect_block_language("Hello there my friend") == "en"


def test_detect_block_language_ambiguous_numbers_only_is_none():
    assert detect_block_language("123 456") is None


def test_detect_block_language_tie_is_none():
    assert detect_block_language("ab 가나") is None  # 라틴 2자 vs 한글 2자 동률


# ── parse_speaker_blocks ─────────────────────────────────────────────────────


def test_parse_speaker_blocks_basic():
    ref_text = "[spk1]\nHello there.\n\n[spk2]\n안녕하세요.\n"
    blocks = parse_speaker_blocks(ref_text)
    assert blocks == [
        {"speaker": "spk1", "text": "Hello there."},
        {"speaker": "spk2", "text": "안녕하세요."},
    ]


def test_parse_speaker_blocks_no_header_returns_none():
    assert parse_speaker_blocks("그냥 빈 줄 경계만 있는 구형식 텍스트\n\n다음 문단") is None


def test_parse_speaker_blocks_multi_paragraph_joined_with_space():
    ref_text = "[spk1]\nFirst sentence.\n\nSecond sentence.\n\n[spk2]\n다음 화자.\n"
    blocks = parse_speaker_blocks(ref_text)
    assert blocks[0] == {"speaker": "spk1", "text": "First sentence. Second sentence."}


# ── compute_language_switch_boundaries ───────────────────────────────────────


def test_boundaries_alternating_languages():
    """ytn2 구조 축소판 — en/ko/en 3블록이면 경계 2개, 언어가 정확히 교대해야 한다."""
    ref_text = (
        "[spk1]\nHello there my friend.\n\n"
        "[spk2]\n안녕하세요 반갑습니다.\n\n"
        "[spk1]\nNice to meet you too.\n"
    )
    blocks = parse_speaker_blocks(ref_text)
    words, boundaries = compute_language_switch_boundaries(blocks, window=8)
    assert len(boundaries) == 2
    assert (boundaries[0].before_lang, boundaries[0].after_lang) == ("en", "ko")
    assert (boundaries[1].before_lang, boundaries[1].after_lang) == ("ko", "en")
    assert words == normalize_text(
        "Hello there my friend. 안녕하세요 반갑습니다. Nice to meet you too."
    ).split()


def test_no_boundary_when_adjacent_blocks_share_language():
    """bong1 구조 축소판 — spk3(en)→spk2(en) 화자전환은 있지만 언어는 같으면 경계 아님."""
    ref_text = (
        "[spk1]\nThis is the first speaker talking now.\n\n"
        "[spk2]\nThis is the second speaker also in English.\n\n"
        "[spk3]\n한국어 화자가 여기서 말합니다 감사합니다.\n"
    )
    blocks = parse_speaker_blocks(ref_text)
    words, boundaries = compute_language_switch_boundaries(blocks, window=8)
    assert len(boundaries) == 1
    assert boundaries[0].before_block_idx == 1
    assert boundaries[0].after_block_idx == 2


def test_window_clips_to_own_block_range_for_short_block():
    """짧은 중간 블록(1단어)은 윈도우가 그 블록 밖(인접하지 않은 블록)까지 넘어가면 안 된다."""
    ref_text = (
        "[spk1]\nOne two three four five six seven eight nine ten eleven twelve.\n\n"
        "[spk2]\n짧게.\n\n"
        "[spk1]\nThirteen fourteen fifteen sixteen seventeen eighteen.\n"
    )
    blocks = parse_speaker_blocks(ref_text)
    words, boundaries = compute_language_switch_boundaries(blocks, window=8)
    assert len(boundaries) == 2
    assert boundaries[0].after_window_words == ["짧게"]
    assert boundaries[1].before_window_words == ["짧게"]


def test_window_respects_configured_size():
    ref_text = "[spk1]\none two three four five six seven eight nine ten.\n\n[spk2]\n가.\n"
    blocks = parse_speaker_blocks(ref_text)
    _, boundaries = compute_language_switch_boundaries(blocks, window=3)
    assert boundaries[0].before_window_words == ["eight", "nine", "ten"]


# ── align_ref_to_hyp ──────────────────────────────────────────────────────────


def test_align_all_match():
    assert align_ref_to_hyp(["a", "b", "c"], ["a", "b", "c"]) == ["match", "match", "match"]


def test_align_detects_deletion():
    assert align_ref_to_hyp(["a", "b", "c"], ["a", "c"]) == ["match", "del", "match"]


def test_align_detects_substitution():
    assert align_ref_to_hyp(["a", "b", "c"], ["a", "x", "c"]) == ["match", "sub", "match"]


def test_align_empty_hyp_marks_all_deleted():
    assert align_ref_to_hyp(["a", "b"], []) == ["del", "del"]


def test_align_real_boundary_tail_example():
    """배포 제보 재현 축소판: "안녕하세요 반갑습니다"에서 "반갑습니다"만 유실."""
    ref = normalize_text("안녕하세요 반갑습니다").split()
    hyp = normalize_text("안녕하세요").split()
    assert align_ref_to_hyp(ref, hyp) == ["match", "del"]


# ── boundary_missing_words ────────────────────────────────────────────────────


def test_boundary_missing_words_splits_before_and_after():
    boundary = RefBoundary(
        boundary_idx=0, before_block_idx=0, after_block_idx=1,
        before_speaker="spk1", after_speaker="spk2", before_lang="ko", after_lang="en",
        before_word_start=0, before_word_end=2, after_word_end=5,
        before_window_words=["안녕하세요", "반갑습니다"],
        after_window_words=["nice", "to", "meet"],
    )
    # ops 길이 = before(2) + after(3) = 5
    ops = ["match", "del", "match", "del", "match"]
    missing = boundary_missing_words(ops, boundary)
    assert missing["before_del"] == ["반갑습니다"]
    assert missing["after_del"] == ["to"]


# ── parse_boundary_log (실측 로그 포맷 그대로) ─────────────────────────────────
# 아래 라인들은 2026-07-19 kinno 스모크 측정(server_kinno_C_R1_20260719_203733.log)에서
# 그대로 채집한 실제 로그 문자열이다(가상 포맷 아님) — 타임스탬프 없는 `LEVEL:logger:msg`
# 형식이 실측 확인됨(Exp-172 서술과 일치).
_REAL_LOG_LINES = [
    "INFO:whisperlivekit.basic_server:[TraceTokens] DEBUG 레벨 로깅 활성화 "
    "(backend + align_att_base + tokens_alignment + sentence_boundary + filtering)\n",
    "INFO:whisperlivekit.simul_whisper.align_att_base:[LangSwitch] 토크나이저 적용: "
    "ko (prev=None, switch=False, skip_trim=False)\n",
    "INFO:whisperlivekit.simul_whisper.align_att_base:[LangSwitch] 토크나이저 적용: "
    "en (prev=ko, switch=True, skip_trim=False)\n",
    "INFO:whisperlivekit.simul_whisper.backend:[NewSpeaker] spk=0→1 det_before=ko eager=en\n",
    "INFO:whisperlivekit.simul_whisper.backend:[NewSpeaker] spk=1 det_after=en "
    "(eager_applied=True) keep_secs=0.59 kept_segments_len=0.96s global_time_offset=36.39\n",
    "INFO:whisperlivekit.simul_whisper.backend:[LangSwitch] 문장 경계 마커 방출 @ 37.01s (lang=en)\n",
    "INFO:whisperlivekit.tokens_alignment:[Retract] 철회: \"You don't understand\" "
    "start=76.20 prev_lang=ko\n",
    "INFO:whisperlivekit.tokens_alignment:[RetractScan] boundary_t=76.20 prev_lang=ko "
    "scanned=9 removed=4 stopped_by=lower_bound\n",
]


def test_parse_boundary_log_flags_trace_tokens_on():
    r = parse_boundary_log("fake.log", _REAL_LOG_LINES)
    assert r.trace_tokens_on is True


def test_parse_boundary_log_extracts_retract_scan():
    r = parse_boundary_log("fake.log", _REAL_LOG_LINES)
    assert len(r.retract_scans) == 1
    rs = r.retract_scans[0]
    assert rs.boundary_t == 76.20
    assert rs.prev_lang == "ko"
    assert rs.scanned == 9
    assert rs.removed == 4
    assert rs.stopped_by == "lower_bound"


def test_parse_boundary_log_extracts_retract_removed_text_without_quotes():
    r = parse_boundary_log("fake.log", _REAL_LOG_LINES)
    assert len(r.retract_removed) == 1
    line_no, text, prev_lang = r.retract_removed[0]
    assert text == "You don't understand"
    assert prev_lang == "ko"


def test_parse_boundary_log_extracts_new_speaker_after():
    r = parse_boundary_log("fake.log", _REAL_LOG_LINES)
    assert len(r.new_speaker_afters) == 1
    ns = r.new_speaker_afters[0]
    assert ns.det_after == "en"
    assert ns.eager_applied is True
    assert ns.keep_secs == 0.59
    assert ns.kept_segments_len == 0.96


def test_parse_boundary_log_extracts_lang_switch_emit():
    r = parse_boundary_log("fake.log", _REAL_LOG_LINES)
    assert len(r.lang_switch_emits) == 1
    ev = r.lang_switch_emits[0]
    assert ev.boundary_t == 37.01
    assert ev.lang == "en"


def test_parse_boundary_log_zero_removed_case():
    lines = [
        "INFO:whisperlivekit.tokens_alignment:[RetractScan] boundary_t=42.39 prev_lang=en "
        "scanned=3 removed=0 stopped_by=lower_bound\n",
    ]
    r = parse_boundary_log("fake.log", lines)
    assert r.retract_scans[0].removed == 0
    assert r.retract_scans[0].scanned == 3


# ── classify_boundaries ────────────────────────────────────────────────────────


def _rb(before_words, after_words, before_lang="ko", after_lang="en"):
    return RefBoundary(
        boundary_idx=0, before_block_idx=0, after_block_idx=1,
        before_speaker="spk1", after_speaker="spk2",
        before_lang=before_lang, after_lang=after_lang,
        before_word_start=0, before_word_end=len(before_words),
        after_word_end=len(before_words) + len(after_words),
        before_window_words=before_words, after_window_words=after_words,
    )


def test_classify_retract_unrecovered_when_removed_gt_zero():
    """ⓐ — RetractScan이 실제로 토큰을 철회했고(removed>0) 그 결과 정답 단어가 유실됐다."""
    boundary = _rb(["안녕"], ["you", "don't", "understand"], before_lang="ko", after_lang="en")
    ops = ["match", "del", "del", "del"]
    log = BoundaryLog(path="x", retract_scans=[
        RetractScanEvent(line_no=10, boundary_t=5.0, prev_lang="ko", scanned=9, removed=4, stopped_by="lower_bound"),
    ])
    verdicts = classify_boundaries([boundary], ops, log)
    assert verdicts[0].series == ["ⓐ철회미복구"]


def test_classify_nonemit_when_removed_zero():
    """ⓑ — 같은 prev_lang의 RetractScan은 있지만 removed=0(철회 대상 자체가 없었음)인데도 유실."""
    boundary = _rb(["안녕"], ["there", "is", "more", "work"], before_lang="ko", after_lang="en")
    ops = ["match", "del", "del", "del", "del"]
    log = BoundaryLog(path="x", retract_scans=[
        RetractScanEvent(line_no=10, boundary_t=5.0, prev_lang="ko", scanned=0, removed=0, stopped_by="silence"),
    ])
    verdicts = classify_boundaries([boundary], ops, log)
    assert verdicts[0].series == ["ⓑ미방출"]


def test_classify_old_language_tail_independent_of_log():
    """구언어꼬리 — 경계 이전(before) 유실은 로그 없이도(None) 태깅된다."""
    boundary = _rb(["안녕하세요", "반갑습니다"], ["nice", "to", "meet", "you"], before_lang="ko", after_lang="en")
    ops = ["match", "del", "match", "match", "match", "match"]
    verdicts = classify_boundaries([boundary], ops, None)
    assert verdicts[0].series == ["구언어꼬리"]


def test_classify_other_when_no_matching_retract_scan():
    """기타 — after_del은 있는데 대응하는 RetractScan을 못 찾음(로그 없음 또는 리스트 비어있음)."""
    boundary = _rb(["match_word"], ["lost_word"], before_lang="ko", after_lang="en")
    ops = ["match", "del"]
    log = BoundaryLog(path="x", retract_scans=[])
    verdicts = classify_boundaries([boundary], ops, log)
    assert verdicts[0].series == ["기타"]


def test_classify_other_when_prev_lang_mismatch():
    """기타 — 순서상 후보 RetractScan은 있으나 prev_lang이 경계의 before_lang과 다름(오정렬 신호)."""
    boundary = _rb(["match_word"], ["lost_word"], before_lang="ko", after_lang="en")
    ops = ["match", "del"]
    log = BoundaryLog(path="x", retract_scans=[
        RetractScanEvent(line_no=1, boundary_t=1.0, prev_lang="en", scanned=1, removed=1, stopped_by="lower_bound"),
    ])
    verdicts = classify_boundaries([boundary], ops, log)
    assert verdicts[0].series == ["기타"]


def test_classify_normal_when_nothing_missing():
    boundary = _rb(["a"], ["b"], before_lang="ko", after_lang="en")
    ops = ["match", "match"]
    verdicts = classify_boundaries([boundary], ops, None)
    assert verdicts[0].series == ["정상"]


def test_classify_can_tag_both_old_lang_tail_and_retract_in_same_boundary():
    """한 경계에서 앞쪽(구언어꼬리)·뒤쪽(ⓐ) 유실이 동시에 발생할 수 있다(배포 제보의 두 증상 공존 케이스)."""
    boundary = _rb(["반갑습니다"], ["nice"], before_lang="ko", after_lang="en")
    ops = ["del", "del"]
    log = BoundaryLog(path="x", retract_scans=[
        RetractScanEvent(line_no=1, boundary_t=1.0, prev_lang="ko", scanned=1, removed=1, stopped_by="lower_bound"),
    ])
    verdicts = classify_boundaries([boundary], ops, log)
    assert set(verdicts[0].series) == {"구언어꼬리", "ⓐ철회미복구"}


# ── find_adjacent_ngram_duplicates ────────────────────────────────────────────


def test_detects_adjacent_trigram_duplicate():
    """실측 bong1 패턴: "It's just a It's just a rock" — 3-gram이 완전 인접 2회."""
    words = tokenize("It's just a It's just a rock")
    runs = find_adjacent_ngram_duplicates(words, min_n=2, max_n=4, max_gap=0)
    assert len(runs) == 1
    assert runs[0].n == 3
    assert runs[0].repeat_count == 2
    assert runs[0].ngram == "it's just a"


def test_unigram_repeat_excluded_by_default_min_n():
    """min_n=2 기본값 — 단일 단어 반복("네, 네" 등 정상 강조 발화)은 잡지 않는다(§3.8 보호)."""
    words = tokenize("네 네 정말 좋습니다")
    runs = find_adjacent_ngram_duplicates(words, min_n=2, max_n=4, max_gap=0)
    assert runs == []


def test_no_false_positive_when_gap_present_and_max_gap_zero():
    """기본 max_gap=0(완전 인접만) — 사이에 다른 단어가 끼면 중복으로 잡지 않는다."""
    words = tokenize("thank you very much thank you")
    runs = find_adjacent_ngram_duplicates(words, min_n=2, max_n=4, max_gap=0)
    assert runs == []


def test_no_false_positive_on_normal_varied_text():
    words = tokenize("President Obama and I discussed the denuclearization of North Korea")
    runs = find_adjacent_ngram_duplicates(words, min_n=2, max_n=4, max_gap=0)
    assert runs == []


def test_larger_n_consumes_before_smaller_n_no_double_count():
    words = tokenize("everyone here everyone here")
    runs = find_adjacent_ngram_duplicates(words, min_n=2, max_n=4, max_gap=0)
    assert len(runs) == 1
    assert runs[0].n == 2
    assert sum(r.end_word_idx - r.start_word_idx for r in runs) == len(words)


def test_unigram_included_when_min_n_lowered_to_one():
    words = tokenize("everyone everyone here")
    runs = find_adjacent_ngram_duplicates(words, min_n=1, max_n=4, max_gap=0)
    assert len(runs) == 1
    assert runs[0].n == 1
    assert runs[0].ngram == "everyone"


# ── load_transcript_sections ──────────────────────────────────────────────────


def test_load_transcript_sections_extracts_transcript_and_triggers():
    content = (
        "파일: test_data\\ytn2.mp3\n경로: C | 회차: R1 | 정답형식: 신형식\n"
        "WER: 18.2% | 화자분리F1: 76.2% | 문장분리F1: N/A\n\n"
        "[전사]\nHello there. 안녕하세요.\n\n"
        "[문장별 확정 트리거]\n"
        "1. Hello there.  ⟨language_switch⟩\n"
        "2. 안녕하세요.  ⟨-⟩\n\n"
        "[정답]\nHello there. 안녕하세요.\n"
    )
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        sections = load_transcript_sections(path)
    finally:
        os.remove(path)
    assert sections["transcript_text"] == "Hello there. 안녕하세요."
    assert sections["lang_switch_trigger_count"] == 1
    assert sections["triggers"] == [("Hello there.", "language_switch"), ("안녕하세요.", "-")]


# ── main() 스모크 테스트 (임시 파일로 CLI 통합 확인) ────────────────────────────


def test_main_runs_end_to_end_with_reference_log_and_transcript(tmp_path):
    ref_dir = tmp_path / "test_data"
    ref_dir.mkdir()
    (ref_dir / "toy.txt").write_text(
        "[spk1]\nHello there my friend.\n\n[spk2]\n안녕하세요 반갑습니다.\n", encoding="utf-8",
    )

    txt = tmp_path / "toy_C_R1.txt"
    txt.write_text(
        "파일: test_data/toy.mp3\n경로: C | 회차: R1 | 정답형식: 신형식\n"
        "WER: 10.0% | 화자분리F1: 100.0% | 문장분리F1: N/A\n\n"
        "[전사]\nHello there my friend. 안녕하세요.\n\n"
        "[문장별 확정 트리거]\n"
        "1. Hello there my friend.  ⟨language_switch⟩\n"
        "2. 안녕하세요.  ⟨-⟩\n\n"
        "[정답]\nHello there my friend. 안녕하세요 반갑습니다.\n",
        encoding="utf-8",
    )

    log = tmp_path / "server_toy_C_R1_20260719_100000.log"
    log.write_text(
        "INFO:whisperlivekit.tokens_alignment:[RetractScan] boundary_t=3.0 prev_lang=en "
        "scanned=0 removed=0 stopped_by=silence\n",
        encoding="utf-8",
    )

    rc = main([
        "--transcripts", str(txt),
        "--logs", str(log),
        "--reference-dir", str(ref_dir),
        "--per-file",
    ])
    assert rc == 0


def test_main_requires_transcripts_argument():
    import pytest
    with pytest.raises(SystemExit):
        main([])


def test_main_handles_missing_reference_gracefully(tmp_path):
    """정답 파일이 없으면 경계 분석은 건너뛰고 dup 산출만 하되 에러로 죽지 않아야 한다."""
    txt = tmp_path / "noref_C_R1.txt"
    txt.write_text(
        "파일: test_data/noref.mp3\n경로: C | 회차: R1 | 정답형식: 신형식\nWER: N/A\n\n"
        "[전사]\nThank you thank you very much\n\n"
        "[문장별 확정 트리거]\n1. Thank you thank you very much  ⟨-⟩\n\n[정답]\n(정답 없음)\n",
        encoding="utf-8",
    )
    rc = main(["--transcripts", str(txt), "--reference-dir", str(tmp_path / "nope"), "--per-file"])
    assert rc == 0


# ── Exp-192 재조정 신규 태그 파서 ─────────────────────────────────────────────
# 아래 라인들은 boundary_reconcile.py / tokens_alignment.py / align_att_base.py의
# logger 포맷 문자열과 동기 — 실제 코드 출력과의 일치 여부는 아래 end-to-end
# caplog 테스트가 별도로 고정한다(포맷 드리프트 가드).

_RECONCILE_LOG_LINES = [
    "INFO:whisperlivekit.tokens_alignment:[RetractScan] boundary_t=12.40 prev_lang=ko "
    "scanned=2 removed=1 stopped_by=lower_bound zones=z1:0,z2opp:0,z2same:1\n",
    "INFO:whisperlivekit.tokens_alignment:[Reconcile] arm boundary_t=12.40 prev_lang=ko "
    "new_lang=en floor=10.00 tombstones=1\n",
    "INFO:whisperlivekit.tokens_alignment:[Replace] 대체: ' 미니스터.' start=11.90 "
    "dstart=-0.10 boundary_t=12.40 zone=zone2_samescript\n",
    "INFO:whisperlivekit.tokens_alignment:[Reconcile] resolve reason=d1 boundary_t=12.40 "
    "cut=12.00 covered=1 restored=0 replaced=1\n",
    "INFO:whisperlivekit.tokens_alignment:[Restore] 복원: ' 반갑습니다' start=11.00 "
    "dstart=NA boundary_t=15.00 zone=zone2_samescript\n",
    "INFO:whisperlivekit.tokens_alignment:[Reconcile] resolve reason=d3 boundary_t=15.00 "
    "cut=NA covered=0 restored=1 replaced=0\n",
    "INFO:whisperlivekit.tokens_alignment:[Replace] 늦은 대체(late): ' 미니스터.' start=11.90 "
    "dstart=-0.10 boundary_t=12.40 zone=zone2_samescript\n",
    "INFO:whisperlivekit.tokens_alignment:[TimeDedup] action=drop text=\" It's\" start=12.50 "
    "dstart=0.00 boundary_t=12.40\n",
    "INFO:whisperlivekit.tokens_alignment:[TimeDedup] action=supersede text=' In.' start=13.00 "
    "dstart=0.05 boundary_t=12.40 new_text=' In' new_start=13.05\n",
    "INFO:whisperlivekit.tokens_alignment:[TimeDedup] action=inherit_id new_text=' In' "
    "start=13.00 dstart=0.05 boundary_t=12.40\n",
    "INFO:whisperlivekit.simul_whisper.align_att_base:[LangSwitch] dynamic keep=3.80s "
    "(buffer_end=20.00 last_emit_end=16.50)\n",
    "INFO:whisperlivekit.simul_whisper.align_att_base:[LangSwitch] dynamic keep=2.50s "
    "(buffer_end=20.00 last_emit_end=None)\n",
]


def test_parse_retract_scan_with_zones_suffix_still_compatible():
    """[RetractScan] 말미 zones 필드 추가 후에도 기존 파서가 그대로 매칭된다."""
    r = parse_boundary_log("fake.log", _RECONCILE_LOG_LINES)
    assert len(r.retract_scans) == 1
    assert r.retract_scans[0].removed == 1
    assert r.retract_scans[0].stopped_by == "lower_bound"


def test_parse_reconcile_arm_and_resolve():
    r = parse_boundary_log("fake.log", _RECONCILE_LOG_LINES)
    assert len(r.reconcile_arms) == 1
    arm = r.reconcile_arms[0]
    assert (arm.boundary_t, arm.prev_lang, arm.new_lang, arm.floor, arm.tombstones) == \
        (12.40, "ko", "en", 10.00, 1)
    assert len(r.reconcile_resolves) == 2
    d1 = r.reconcile_resolves[0]
    assert (d1.reason, d1.cut, d1.covered, d1.restored, d1.replaced) == ("d1", 12.00, 1, 0, 1)


def test_parse_resolve_cut_na_means_full_restore():
    r = parse_boundary_log("fake.log", _RECONCILE_LOG_LINES)
    d3 = r.reconcile_resolves[1]
    assert d3.reason == "d3"
    assert d3.cut is None  # 신언어 무도착 → 전량 복원
    assert d3.restored == 1


def test_parse_restore_and_replace_token_events():
    r = parse_boundary_log("fake.log", _RECONCILE_LOG_LINES)
    kinds = [ev.kind for ev in r.reconcile_tokens]
    assert "restore" in kinds and "replace" in kinds and "replace_late" in kinds
    restore = next(ev for ev in r.reconcile_tokens if ev.kind == "restore")
    assert restore.text == " 반갑습니다"
    assert restore.dstart is None  # NA
    assert restore.zone == "zone2_samescript"
    replace = next(ev for ev in r.reconcile_tokens if ev.kind == "replace")
    assert replace.text == " 미니스터."
    assert replace.dstart == -0.10
    assert replace.boundary_t == 12.40


def test_parse_timededup_events_including_quoted_apostrophe():
    r = parse_boundary_log("fake.log", _RECONCILE_LOG_LINES)
    drop = next(ev for ev in r.reconcile_tokens if ev.kind == "dedup_drop")
    assert drop.text == " It's"  # 이중따옴표 repr(어포스트로피 포함)도 벗겨진다
    assert drop.dstart == 0.00
    sup = next(ev for ev in r.reconcile_tokens if ev.kind == "dedup_supersede")
    assert sup.text == " In."
    assert sup.boundary_t == 12.40
    inh = next(ev for ev in r.reconcile_tokens if ev.kind == "dedup_inherit_id")
    assert inh.text == " In"
    assert inh.start == 13.00


def test_parse_dynamic_keep_events():
    r = parse_boundary_log("fake.log", _RECONCILE_LOG_LINES)
    assert len(r.dynamic_keeps) == 2
    assert r.dynamic_keeps[0].keep_secs == 3.80
    assert r.dynamic_keeps[0].last_emit_end == 16.50
    assert r.dynamic_keeps[1].last_emit_end is None  # 폴백 발동 케이스


def test_classify_attaches_reconcile_status_without_changing_series():
    """재조정 상태(복원됨/대체됨)는 별도 필드로만 붙는다 — series는 before 이력과 호환."""
    from analyze_boundary_tail_dup import ReconcileResolveEvent
    boundary = _rb(["안녕"], ["you", "don't", "understand"], before_lang="ko", after_lang="en")
    ops = ["match", "del", "del", "del"]
    log = BoundaryLog(path="x", retract_scans=[
        RetractScanEvent(line_no=10, boundary_t=5.0, prev_lang="ko", scanned=9, removed=4,
                         stopped_by="lower_bound"),
    ], reconcile_resolves=[
        ReconcileResolveEvent(line_no=12, reason="d1", boundary_t=5.0, cut=5.3,
                              covered=2, restored=3, replaced=1),
    ])
    verdicts = classify_boundaries([boundary], ops, log)
    assert verdicts[0].series == ["ⓐ철회미복구"]  # 기존 계열 판정 불변
    assert verdicts[0].reconcile_status == "혼합(복원+대체)"
    assert any("reconcile resolve" in e for e in verdicts[0].evidence)


def test_parser_matches_actual_reconcile_log_format_end_to_end(caplog):
    """포맷 드리프트 가드: 실제 코드(tokens_alignment+boundary_reconcile)가 찍는 로그를
    caplog로 채집해 파서에 넣어도 이벤트가 추출돼야 한다 — 테스트 상수 라인과 실코드
    포맷이 어긋나면 여기서 잡힌다."""
    import logging

    from whisperlivekit.timed_objects import ASRToken, LanguageSwitch
    from whisperlivekit.tokens_alignment import TokensAlignment

    class _Args:
        diarization = False

    class _State:
        new_tokens = []
        new_diarization = []
        new_translation = []
        new_tokens_buffer = []
        new_translation_buffer = None

    ta = TokensAlignment(_State(), _Args(), sep="")
    ta.all_tokens = [ASRToken(start=11.9, end=12.3, text=" 미니스터.", detected_language="ko")]
    marker = LanguageSwitch(start=12.4, end=12.4, detected_language="en",
                            retract_from=12.4, prev_language="ko", retract_floor=10.0)
    with caplog.at_level(logging.INFO, logger="whisperlivekit.tokens_alignment"):
        ta._insert_with_reattachment([
            marker,
            ASRToken(start=12.0, end=12.4, text=" Minister", detected_language="en"),
            ASRToken(start=12.8, end=12.9, text=" of", detected_language="en"),
        ])
    lines = [f"INFO:{rec.name}:{rec.getMessage()}\n" for rec in caplog.records]
    parsed = parse_boundary_log("generated.log", lines)
    assert len(parsed.retract_scans) == 1 and parsed.retract_scans[0].removed == 1
    assert len(parsed.reconcile_arms) == 1 and parsed.reconcile_arms[0].tombstones == 1
    assert len(parsed.reconcile_resolves) == 1 and parsed.reconcile_resolves[0].reason == "d1"
    assert any(ev.kind == "replace" and ev.text == " 미니스터." for ev in parsed.reconcile_tokens)
