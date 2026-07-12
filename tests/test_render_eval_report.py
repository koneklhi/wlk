"""scripts/render_eval_report.py 단위 테스트.

TDD 순서(Red-Green-Refactor): 정규화 파리티 → 토큰화 → diff 코어 → HTML 이스케이프 →
그룹핑 → hyp 레이아웃/트리거 → Case B → 문서 스모크.

import 관용구는 tests/test_eval_build_result.py를 그대로 따른다.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from render_eval_report import (  # noqa: E402
    _CSS,
    DiffSpan,
    FileGroup,
    _esc,
    _normalize_text,
    build_hyp_layout,
    detect_case_b,
    diff_tokens,
    group_files,
    load_reports,
    main,
    render_diff,
    render_document,
    render_file_section,
    render_legend,
    render_run_section,
    tokenize,
)


def _make_file_result(
    audio_file,
    path="C",
    wer=0.1,
    seg_f1=0.5,
    sentence_f1=None,
    transcription="",
    reference=None,
    hyp_lines=None,
    ref_format="new",
):
    """scripts/eval.py의 FileResult(asdict)와 동일한 형태의 합성 dict을 만드는 테스트 헬퍼."""
    return {
        "audio_file": audio_file,
        "transcription": transcription,
        "reference": reference,
        "wer": wer,
        "path": path,
        "seg_f1": seg_f1,
        "seg_precision": seg_f1,
        "seg_recall": seg_f1,
        "ref_sentences": 1,
        "hyp_sentences": 1,
        "hyp_lines": hyp_lines,
        "sentence_f1": sentence_f1,
        "sentence_precision": sentence_f1,
        "sentence_recall": sentence_f1,
        "ref_format": ref_format,
    }


# ---------------------------------------------------------------------------
# 카테고리 1: 정규화 파리티 (whisperlivekit.metrics.normalize_text와 동치 검증)
# ---------------------------------------------------------------------------


def test_normalize_text_matches_metrics_module():
    """로컬 _normalize_text가 whisperlivekit.metrics.normalize_text와 동일한 결과를 내야 한다.

    이 테스트에서만 heavy import(whisperlivekit)를 허용한다 — scripts/render_eval_report.py
    본체 코드는 절대 whisperlivekit을 import하지 않는다.
    """
    from whisperlivekit.metrics import normalize_text as reference_normalize

    samples = [
        "Hello World!",
        "안녕하세요, 반갑습니다.",
        "code-switching 예시 in 한 문장",
        "  extra   whitespace  ",
        "UPPER lower MiXeD",
        "숫자 123 and punctuation!!! ???",
        "it's a test's apostrophe-hyphen case",
        "",
    ]
    for s in samples:
        assert _normalize_text(s) == reference_normalize(s), f"mismatch for {s!r}"


# ---------------------------------------------------------------------------
# 카테고리 2: 토큰화 (display/key 분리, 순수 구두점 접착, NFC 보존)
# ---------------------------------------------------------------------------


def test_tokenize_splits_display_and_key():
    """공백으로 분리된 각 조각은 원문 그대로의 display와 정규화된 key를 함께 가진다."""
    toks = tokenize("Hello World")
    assert [t.display for t in toks] == ["Hello", "World"]
    assert [t.key for t in toks] == ["hello", "world"]


def test_tokenize_preserves_display_casing_and_punctuation():
    """display는 원문 그대로(대소문자·구두점 보존)이고, key만 정규화된다."""
    toks = tokenize("Hello, World!")
    assert toks[0].display == "Hello,"
    assert toks[0].key == "hello"
    assert toks[1].display == "World!"
    assert toks[1].key == "world"


def test_tokenize_glues_pure_punctuation_to_previous_token():
    """순수 구두점만으로 이뤄진 조각(정규화 후 key가 빈 문자열)은 직전 토큰에 접착된다."""
    toks = tokenize("hello ... world")
    assert len(toks) == 2
    assert toks[0].key == "hello"
    assert "..." in toks[0].display
    assert toks[1].display == "world"
    assert toks[1].key == "world"


def test_tokenize_preserves_nfc_korean():
    """한글 토큰의 key가 NFC 정규화된 형태로 보존된다(자모 분리형 입력도 NFC로 합쳐짐)."""
    decomposed = unicodedata.normalize("NFD", "안녕하세요")
    toks = tokenize(decomposed)
    assert len(toks) == 1
    assert toks[0].key == "안녕하세요"


def test_tokenize_empty_text_returns_empty_list():
    """빈 문자열·공백만 있는 문자열은 빈 토큰 리스트를 반환한다."""
    assert tokenize("") == []
    assert tokenize("   ") == []


# ---------------------------------------------------------------------------
# 카테고리 3: diff 코어 (동일/치환/삭제/삽입/한영혼용/casing-only/빈 텍스트 극단)
# ---------------------------------------------------------------------------


def test_diff_tokens_all_equal():
    ref = tokenize("the cat sat")
    hyp = tokenize("the cat sat")
    spans = diff_tokens(ref, hyp)
    assert len(spans) == 1
    assert spans[0].kind == "eq"
    assert [t.display for t in spans[0].hyp_toks] == ["the", "cat", "sat"]


def test_diff_tokens_substitution():
    ref = tokenize("the cat sat")
    hyp = tokenize("the dog sat")
    spans = diff_tokens(ref, hyp)
    kinds = [s.kind for s in spans]
    assert kinds == ["eq", "sub", "eq"]
    sub = spans[1]
    assert [t.display for t in sub.ref_toks] == ["cat"]
    assert [t.display for t in sub.hyp_toks] == ["dog"]


def test_diff_tokens_deletion():
    """정답에만 있고 전사에 없는 단어 = 삭제(del). hyp 쪽 구간은 비어 있다(hyp_start==hyp_end)."""
    ref = tokenize("the quick cat sat")
    hyp = tokenize("the cat sat")
    spans = diff_tokens(ref, hyp)
    dels = [s for s in spans if s.kind == "del"]
    assert len(dels) == 1
    assert [t.display for t in dels[0].ref_toks] == ["quick"]
    assert dels[0].hyp_toks == []
    assert dels[0].hyp_start == dels[0].hyp_end


def test_diff_tokens_insertion():
    """전사에만 있고 정답에 없는 단어(환각) = 삽입(ins). ref 쪽 구간은 비어 있다."""
    ref = tokenize("the cat sat")
    hyp = tokenize("the cat really sat")
    spans = diff_tokens(ref, hyp)
    ins = [s for s in spans if s.kind == "ins"]
    assert len(ins) == 1
    assert [t.display for t in ins[0].hyp_toks] == ["really"]
    assert ins[0].ref_toks == []


def test_diff_tokens_korean_english_mixed():
    """한영 혼용 문장에서 일부 구간만 치환돼도 정확히 해당 구간만 sub로 잡힌다."""
    ref = tokenize("오늘 code switching 테스트 입니다")
    hyp = tokenize("오늘 code switching 검증 입니다")
    spans = diff_tokens(ref, hyp)
    kinds = [s.kind for s in spans]
    assert "sub" in kinds
    sub = next(s for s in spans if s.kind == "sub")
    assert [t.display for t in sub.ref_toks] == ["테스트"]
    assert [t.display for t in sub.hyp_toks] == ["검증"]


def test_diff_tokens_casing_only_treated_as_equal():
    """대소문자만 다른 경우 key가 동일하므로 sub가 아니라 eq로 처리된다(display는 원문 보존)."""
    ref = tokenize("Hello World")
    hyp = tokenize("HELLO world")
    spans = diff_tokens(ref, hyp)
    assert len(spans) == 1
    assert spans[0].kind == "eq"
    assert [t.display for t in spans[0].hyp_toks] == ["HELLO", "world"]


def test_diff_tokens_both_empty():
    assert diff_tokens([], []) == []


def test_diff_tokens_empty_ref_all_insert():
    hyp = tokenize("hello world")
    spans = diff_tokens([], hyp)
    assert len(spans) == 1
    assert spans[0].kind == "ins"
    assert [t.display for t in spans[0].hyp_toks] == ["hello", "world"]


def test_diff_tokens_empty_hyp_all_delete():
    ref = tokenize("hello world")
    spans = diff_tokens(ref, [])
    assert len(spans) == 1
    assert spans[0].kind == "del"
    assert [t.display for t in spans[0].ref_toks] == ["hello", "world"]


# ---------------------------------------------------------------------------
# 카테고리 4: HTML 이스케이프
# ---------------------------------------------------------------------------


def test_esc_escapes_script_tags():
    """전사·정답에 <script> 등이 포함돼도 태그로 해석되지 않도록 이스케이프한다."""
    assert _esc("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_esc_escapes_ampersand_and_quotes():
    assert _esc("a & b \"c\" 'd'") == "a &amp; b &quot;c&quot; &#x27;d&#x27;"


# ---------------------------------------------------------------------------
# 카테고리 5: 그룹핑 (9run→3파일, 순서보존, summary 부착, 여러 JSON 병합, 역슬래시 정규화)
# ---------------------------------------------------------------------------


def test_group_files_groups_nine_runs_into_three_files():
    """repeat=3 testset처럼 9개 run(파일 3종 x 3회차)이 파일 3개로 그룹핑된다."""
    files = []
    for name in ["bong1.wav", "ytn2.mp3", "sbs1.mp3"]:
        for _rep in range(3):
            files.append(_make_file_result(f"test_data\\{name}"))
    report = {"files": files}

    groups = group_files([report])

    assert len(groups) == 3
    assert all(len(g.runs) == 3 for g in groups)


def test_group_files_preserves_order():
    """그룹 순서는 files[] 안에서 처음 등장한 순서를 따른다."""
    files = [
        _make_file_result("test_data\\bong1.wav"),
        _make_file_result("test_data\\ytn2.mp3"),
        _make_file_result("test_data\\bong1.wav"),
        _make_file_result("test_data\\sbs1.mp3"),
    ]
    groups = group_files([{"files": files}])
    assert [g.display_name for g in groups] == ["bong1.wav", "ytn2.mp3", "sbs1.mp3"]


def test_group_files_attaches_summary():
    """file_summaries[]가 있으면(repeat>1) 같은 오디오 파일 basename 기준으로 그룹에 부착된다."""
    files = [_make_file_result("test_data\\bong1.wav", wer=w) for w in (0.3, 0.29, 0.42)]
    summary = {
        "audio_file": "test_data\\bong1.wav",
        "repeat": 3,
        "wer": {"median": 0.3, "min": 0.29, "max": 0.42, "stdev": 0.07},
        "seg_f1": {"median": 0.5, "min": 0.5, "max": 0.62, "stdev": 0.07},
        "sentence_f1": {"median": 0.23, "min": 0.1, "max": 0.27, "stdev": 0.09},
    }
    report = {"files": files, "file_summaries": [summary]}

    groups = group_files([report])

    assert len(groups) == 1
    assert groups[0].summary == summary


def test_group_files_merges_multiple_json_reports():
    """테스트셋 JSON + held-out JSON처럼 여러 report를 하나로 합쳐도 같은 파일은 같은 그룹에 모인다."""
    report_a = {"files": [_make_file_result("test_data\\bong1.wav"), _make_file_result("test_data\\ytn2.mp3")]}
    report_b = {"files": [_make_file_result("test_data\\ytn1.mp3"), _make_file_result("test_data\\eng1.mp3")]}

    groups = group_files([report_a, report_b])

    assert [g.display_name for g in groups] == ["bong1.wav", "ytn2.mp3", "ytn1.mp3", "eng1.mp3"]
    assert all(len(g.runs) == 1 for g in groups)


def test_group_files_normalizes_backslashes():
    """윈도우 역슬래시 경로와 유닉스 슬래시 경로가 같은 파일이면 같은 그룹으로 합쳐진다."""
    files = [
        _make_file_result("test_data\\bong1.wav"),
        _make_file_result("test_data/bong1.wav"),
    ]
    groups = group_files([{"files": files}])
    assert len(groups) == 1
    assert len(groups[0].runs) == 2


def test_load_reports_reads_json_files(tmp_path):
    """load_reports가 여러 JSON 파일 경로를 읽어 dict 리스트로 반환한다."""
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    p1.write_text('{"files": [], "timestamp": "t1"}', encoding="utf-8")
    p2.write_text('{"files": [], "timestamp": "t2"}', encoding="utf-8")

    reports = load_reports([p1, p2])

    assert len(reports) == 2
    assert reports[0]["timestamp"] == "t1"
    assert reports[1]["timestamp"] == "t2"


# ---------------------------------------------------------------------------
# 카테고리 6: hyp 레이아웃/트리거 (줄 시작 토큰 인덱스, 트리거 라벨 위치)
# ---------------------------------------------------------------------------


def test_build_hyp_layout_computes_line_token_ranges():
    """각 hyp_line의 [start, end) 토큰 인덱스 구간이 누적으로 정확히 계산된다."""
    hyp_lines = [
        {"text": "the cat sat", "trigger": "silence"},
        {"text": "on the mat", "trigger": "punctuation"},
    ]
    hyp_toks, spans = build_hyp_layout(hyp_lines)

    assert len(hyp_toks) == 6
    assert len(spans) == 2
    assert (spans[0].start, spans[0].end) == (0, 3)
    assert (spans[1].start, spans[1].end) == (3, 6)


def test_build_hyp_layout_preserves_trigger_labels():
    """트리거 라벨(silence/punctuation/speaker_change/language_switch/None)이 그대로 보존된다."""
    hyp_lines = [
        {"text": "hello", "trigger": "speaker_change"},
        {"text": "world", "trigger": None},
    ]
    _, spans = build_hyp_layout(hyp_lines)
    assert spans[0].trigger == "speaker_change"
    assert spans[1].trigger is None


def test_build_hyp_layout_empty_hyp_lines_returns_empty():
    hyp_toks, spans = build_hyp_layout([])
    assert hyp_toks == []
    assert spans == []


def test_build_hyp_layout_tokens_match_per_line_tokenize():
    """전체 토큰 스트림은 각 줄을 tokenize()한 결과를 순서대로 이어붙인 것과 동일해야 한다."""
    hyp_lines = [{"text": "hello world", "trigger": "silence"}, {"text": "foo", "trigger": None}]
    hyp_toks, _spans = build_hyp_layout(hyp_lines)
    expected = tokenize("hello world") + tokenize("foo")
    assert hyp_toks == expected


# ---------------------------------------------------------------------------
# 카테고리 7: Case B(단어 중간 분절) 자동 탐지 — CLAUDE.md §3.3 hard-fail 요구사항 직결
# ---------------------------------------------------------------------------


def test_detect_case_b_flags_real_word_split_pattern():
    """sbs1 실측 베이스라인에서 재현된 실제 패턴: 정답 '올렸습니다'가 hyp_line 경계에서
    '올렸.' + '습니다.'로 쪼개진 경우를 flag해야 한다(방금 측정에서 R1/R2 재현됨)."""
    ref_toks = tokenize("뒤집어 놓은 지도를 올렸습니다. 브런슨")
    hyp_lines = [
        {"text": "뒤집어 놓은 지도를 올렸.", "trigger": "silence"},
        {"text": "습니다.", "trigger": "punctuation"},
        {"text": "브런슨", "trigger": "silence"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)

    hits = detect_case_b(diff_spans, line_spans)

    assert len(hits) == 1
    assert hits[0]["ref_token"] == "올렸습니다."
    assert hits[0]["hyp_tokens"] == ["올렸.", "습니다."]


def test_detect_case_b_flags_ascii_word_split_pattern():
    """영문 합성 예시로 동일 로직을 검증한다(가독성/디버깅 용이)."""
    ref_toks = tokenize("before understand after")
    hyp_lines = [
        {"text": "before under", "trigger": "silence"},
        {"text": "stand after", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)

    hits = detect_case_b(diff_spans, line_spans)

    assert len(hits) == 1
    assert hits[0]["ref_token"] == "understand"
    assert hits[0]["hyp_tokens"] == ["under", "stand"]


def test_detect_case_b_ignores_boundary_between_two_already_separate_words():
    """정답에서 이미 별개인 두 단어('바' '있습니다')가 줄 경계에서 갈라져도, 둘 다 정답과
    독립적으로 EQ 매칭되므로 sub span조차 생기지 않는다 — 정상 조기 분리(Case A)는 flag 안 함.
    실측 sbs1 패턴 기반("비유한 바 있습니다")."""
    ref_toks = tokenize("비유한 바 있습니다 그러면서")
    hyp_lines = [
        {"text": "비유한 바.", "trigger": "silence"},
        {"text": "있습니다. 그러면서", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)

    hits = detect_case_b(diff_spans, line_spans)

    assert hits == []


def test_detect_case_b_ignores_1to1_substitution_across_boundary():
    """줄 경계를 가로지르는 오인식이 있어도 1:1 치환(정답 1토큰 vs hyp 1토큰)이면 애초에
    "여러 토큰으로 쪼개짐" 조건에 해당하지 않으므로 flag하지 않는다 — 단순 WER 오류와
    단어분절 구조 버그를 구분. 실측 sbs1 패턴 기반("선을 걷었습니다" -> "선을. 그었습니다.")."""
    ref_toks = tokenize("없다고 선을 걷었습니다 그러면서")
    hyp_lines = [
        {"text": "없다고 선을.", "trigger": "silence"},
        {"text": "그었습니다. 그러면서", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)

    hits = detect_case_b(diff_spans, line_spans)

    assert hits == []


def test_detect_case_b_ignores_multi_token_sub_not_at_line_boundary():
    """정답 1토큰이 hyp 여러 토큰으로 쪼개져 이어붙이면 복원되더라도, 그 경계가 줄 경계가
    아니라 같은 줄 내부라면(단순 인식 오류) flag하지 않는다."""
    ref_toks = tokenize("before understand after")
    hyp_lines = [
        {"text": "before under stand after", "trigger": "silence"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)

    hits = detect_case_b(diff_spans, line_spans)

    assert hits == []


def test_detect_case_b_ignores_concatenation_mismatch_at_line_boundary():
    """줄 경계와 정확히 겹치는 다중토큰 치환이라도, 이어붙인 결과가 정답 토큰과 다르면
    (진짜 그 단어가 쪼개진 게 아니라 다른 말로 오인식된 경우) flag하지 않는다."""
    ref_toks = tokenize("hello combination world")
    hyp_lines = [
        {"text": "hello combo", "trigger": "silence"},
        {"text": "nation world", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)

    hits = detect_case_b(diff_spans, line_spans)

    assert hits == []


# ---------------------------------------------------------------------------
# 카테고리 8: 문서 스모크 (외부 URL 없음, DOCTYPE/style/dark-mode, 앵커-섹션 id 일치)
# ---------------------------------------------------------------------------


def test_render_diff_wraps_equal_deleted_inserted_tokens_and_trigger_chip():
    ref = tokenize("the quick cat sat")
    hyp_lines = [{"text": "the cat really sat", "trigger": "silence"}]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref, hyp_toks)

    html_out = render_diff(diff_spans, line_spans)

    assert 'class="eq"' in html_out
    assert 'class="del"' in html_out  # "quick"은 정답에만 있음
    assert 'class="ins"' in html_out  # "really"는 전사에만 있음(환각)
    assert "trigger--silence" in html_out


def test_render_diff_wraps_substituted_tokens_with_ref_and_hyp_and_trigger_chip():
    ref = tokenize("the cat sat")
    hyp_lines = [{"text": "the dog sat", "trigger": "punctuation"}]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref, hyp_toks)

    html_out = render_diff(diff_spans, line_spans)

    assert 'class="sub"' in html_out
    assert 'class="sub-ref"' in html_out and "cat" in html_out
    assert 'class="sub-hyp"' in html_out and "dog" in html_out
    assert "trigger--punctuation" in html_out


def test_render_diff_marks_case_b_span_with_caseb_class():
    ref_toks = tokenize("before understand after")
    hyp_lines = [
        {"text": "before under", "trigger": "silence"},
        {"text": "stand after", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)
    case_b_hits = detect_case_b(diff_spans, line_spans)
    assert case_b_hits  # 사전 조건: Case B가 실제로 탐지돼야 함

    html_out = render_diff(diff_spans, line_spans, case_b_hits)

    assert "caseb" in html_out


def test_render_diff_escapes_html_in_tokens():
    """전사·정답에 <script> 등이 섞여 있어도 렌더링 결과에 원문 태그가 그대로 노출되지 않는다."""
    ref = tokenize("<script>alert(1)</script> world")
    hyp_lines = [{"text": "<script>alert(1)</script> world", "trigger": "silence"}]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref, hyp_toks)

    html_out = render_diff(diff_spans, line_spans)

    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_render_run_section_handles_missing_reference_without_crashing():
    """정답이 아예 없는 파일(reference=None)도 예외 없이 렌더링되고, 전체가 환각(ins) 취급되지
    않아야 한다(비교 불가 상태이지 실제 삽입 오류가 아니므로)."""
    file_result = _make_file_result(
        "test_data\\kinno.mp3",
        reference=None,
        ref_format=None,
        wer=None,
        seg_f1=None,
        transcription="hello world",
        hyp_lines=[{"text": "hello world", "trigger": "silence"}],
    )

    html_out = render_run_section(file_result, 1)

    assert "hello world" in html_out
    assert 'class="del"' not in html_out
    assert 'class="ins"' not in html_out


def test_render_file_section_has_anchor_id_and_wraps_all_runs():
    """같은 파일의 여러 회차가 한 <details> 섹션에 순서대로 묶이고, id가 파일명 기반 슬러그다."""
    runs = [
        _make_file_result(
            "test_data\\bong1.wav", transcription="a b",
            hyp_lines=[{"text": "a b", "trigger": "silence"}], reference="a b",
        ),
        _make_file_result(
            "test_data\\bong1.wav", transcription="c d",
            hyp_lines=[{"text": "c d", "trigger": "silence"}], reference="c d",
        ),
    ]
    group = FileGroup(display_name="bong1.wav", runs=runs)

    html_out = render_file_section(group)

    assert 'id="file-bong1_wav"' in html_out
    assert html_out.count('class="run"') == 2


def _sample_groups():
    runs_bong1 = [
        _make_file_result(
            "test_data\\bong1.wav", transcription="hello world",
            hyp_lines=[{"text": "hello world", "trigger": "silence"}], reference="hello world",
        )
    ]
    runs_ytn1 = [
        _make_file_result(
            "test_data\\ytn1.mp3", transcription="foo bar",
            hyp_lines=[{"text": "foo bar", "trigger": "punctuation"}], reference="foo baz",
        )
    ]
    return [
        FileGroup(display_name="bong1.wav", runs=runs_bong1),
        FileGroup(display_name="ytn1.mp3", runs=runs_ytn1),
    ]


def test_render_document_has_no_external_urls():
    """생성된 HTML은 외부 리소스 요청이 0이어야 한다(폐쇄망 원칙) — http(s):// URL이 없어야 함."""
    doc = render_document("테스트 리포트", _sample_groups(), generated_at="2026-07-10 12:00")
    assert "http://" not in doc
    assert "https://" not in doc


def test_render_document_has_doctype_style_and_dark_mode():
    doc = render_document("테스트 리포트", _sample_groups(), generated_at="2026-07-10 12:00")
    assert doc.lstrip().lower().startswith("<!doctype html")
    assert "<style" in doc
    assert "prefers-color-scheme" in doc


def test_render_document_anchor_ids_match_summary_hrefs():
    """요약표의 모든 앵커 링크(href="#...")가 실제 파일 섹션의 id와 일치해야 한다."""
    doc = render_document("테스트 리포트", _sample_groups(), generated_at="2026-07-10 12:00")

    hrefs = set(re.findall(r'href="#([^"]+)"', doc))
    ids = set(re.findall(r'id="([^"]+)"', doc))

    assert hrefs
    assert hrefs <= ids


def test_main_writes_report_to_output_path(tmp_path):
    report = {
        "files": [
            _make_file_result(
                "test_data\\bong1.wav", transcription="hello world",
                hyp_lines=[{"text": "hello world", "trigger": "silence"}], reference="hello world",
            )
        ]
    }
    json_path = tmp_path / "report.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    output_path = tmp_path / "out.html"

    rc = main([str(json_path), "--output", str(output_path), "--title", "테스트"])

    assert rc == 0
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "bong1.wav" in content
    assert content.lstrip().lower().startswith("<!doctype html")


def test_main_returns_nonzero_for_missing_json_file(tmp_path):
    missing = tmp_path / "does_not_exist.json"

    rc = main([str(missing), "--output", str(tmp_path / "out.html")])

    assert rc == 1


# ---------------------------------------------------------------------------
# 카테고리 9: 범례 CSS 스코프 버그 수정 + 내용 보강 + 문장 경계 줄바꿈
# ---------------------------------------------------------------------------


def test_render_legend_covers_all_mark_categories():
    """일치/삭제/삽입/치환/Case B 라벨 텍스트와 실제 클래스 스와치가 모두 포함돼야 한다."""
    legend_html = render_legend()

    for label in ("일치", "삭제", "삽입", "치환", "Case B"):
        assert label in legend_html, f"missing label: {label}"
    for cls in ('class="eq"', 'class="del"', 'class="ins"', 'class="sub"', "caseb"):
        assert cls in legend_html, f"missing class swatch: {cls}"


def test_render_legend_explains_all_four_trigger_meanings():
    """트리거 칩 4가지 라벨(silence/punctuation/speaker_change/language_switch)의 한국어 의미가
    범례에 전부 설명돼 있어야 한다."""
    legend_html = render_legend()

    for meaning in ("침묵", "구두점", "화자전환", "언어전환"):
        assert meaning in legend_html, f"missing trigger meaning: {meaning}"


def test_render_legend_has_heading():
    """범례 맨 앞에 헤딩이 있어야 한다."""
    assert "범례" in render_legend()


def test_render_legend_case_b_marked_as_critical():
    """Case B 설명에는 "치명적" 같은 한국어 경고 문구가 명시적으로 들어가야 한다(기존 영어
    "hard-fail" 단어만으로는 사용자가 심각성을 놓칠 수 있음 — 이 문구는 수정 전 코드엔 없다)."""
    assert "치명적" in render_legend()


def test_css_styles_marks_inside_legend():
    """_CSS의 마킹 셀렉터(del/ins/sub/sub-ref/sub.caseb/trigger)가 `.legend` 안에서도 매치돼야
    한다 — render_legend()가 만드는 스와치가 `.diff` 밖(.legend 안)에 있어서 지금은 스타일이
    전혀 먹지 않는 회귀를 방지하는 가드."""
    for selector in (".legend .del", ".legend .ins", ".legend .sub", ".legend .trigger"):
        assert selector in _CSS, f"missing selector: {selector}"


def test_render_document_includes_legend_heading():
    """render_document() 통합 결과에도 범례 헤딩이 포함돼야 한다."""
    doc = render_document("테스트 리포트", _sample_groups(), generated_at="2026-07-10 12:00")
    assert "범례" in doc


def test_render_diff_inserts_line_break_after_trigger_chip():
    """두 문장짜리 hyp_lines를 렌더링하면 각 트리거 칩 바로 뒤에 <br>이 와야 한다(지금은 공백만
    붙어서 전체 전사가 한 문단으로 이어짐)."""
    ref = tokenize("the cat sat on the mat")
    hyp_lines = [
        {"text": "the cat sat", "trigger": "silence"},
        {"text": "on the mat", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref, hyp_toks)

    html_out = render_diff(diff_spans, line_spans)

    chip_line_breaks = re.findall(r"⟩</span><br>", html_out)
    assert len(chip_line_breaks) == 2


def test_render_diff_line_break_after_case_b_block():
    """Case B로 여러 hyp 토큰이 하나의 sub 블록으로 병합된 경우에도, 그 뒤에 오는 트리거 칩에
    줄바꿈이 살아있어야 한다."""
    ref_toks = tokenize("before understand after")
    hyp_lines = [
        {"text": "before under", "trigger": "silence"},
        {"text": "stand after", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref_toks, hyp_toks)
    case_b_hits = detect_case_b(diff_spans, line_spans)
    assert case_b_hits  # 사전 조건: Case B가 실제로 탐지돼야 함

    html_out = render_diff(diff_spans, line_spans, case_b_hits)

    assert re.search(r"⟩</span><br>", html_out)


# ---------------------------------------------------------------------------
# 카테고리 10: eq/ins span이 여러 hyp_line 경계를 가로지를 때 칩·줄바꿈이 뭉치는 버그 수정
# ---------------------------------------------------------------------------


def test_diff_tokens_merges_three_sentence_lines_into_single_eq_span():
    """3개 hyp_line 텍스트를 이어붙인 것이 정답과 정확히 일치하면, difflib이 이를 hyp_line
    경계를 무시한 채 hyp 토큰 전체를 가로지르는 단 하나의 eq span으로 묶는다 — 이것이
    render_diff()가 반드시 처리해야 하는 전제 상황임을 diff_tokens() 레벨에서 확정한다."""
    ref = tokenize("song what did you think 누가 주인공일까 The thought that")
    hyp_lines = [
        {"text": "song what did you think", "trigger": "silence"},
        {"text": "누가 주인공일까", "trigger": "language_switch"},
        {"text": "The thought that", "trigger": "silence"},
    ]
    hyp_toks, _line_spans = build_hyp_layout(hyp_lines)
    spans = diff_tokens(ref, hyp_toks)

    assert len(spans) == 1
    assert spans[0].kind == "eq"


def test_render_diff_splits_eq_span_at_each_hyp_line_boundary():
    """3문장이 정답과 정확히 일치해 diff_spans가 eq 하나로 묶여도, render_diff()는 각
    hyp_line 경계마다 텍스트를 끊고 그 자리에서 트리거 칩+<br>을 즉시 삽입해야 한다 —
    칩 3개가 전부 맨 뒤에 뭉쳐 나오면 안 되고, 각 줄 텍스트 사이사이에 끼어야 한다."""
    ref = tokenize("song what did you think 누가 주인공일까 The thought that")
    hyp_lines = [
        {"text": "song what did you think", "trigger": "silence"},
        {"text": "누가 주인공일까", "trigger": "language_switch"},
        {"text": "The thought that", "trigger": "silence"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = diff_tokens(ref, hyp_toks)
    assert len(diff_spans) == 1 and diff_spans[0].kind == "eq"  # 사전 조건(버그 재현 전제)

    html_out = render_diff(diff_spans, line_spans)

    # 칩 3개가 모두 생성돼야 한다.
    chip_line_breaks = re.findall(r"⟩</span><br>", html_out)
    assert len(chip_line_breaks) == 3

    # 각 줄의 텍스트와 그 줄의 트리거 칩이 나오는 순서를 검증한다: line0 텍스트 -> silence 칩
    # -> line1 텍스트 -> language_switch 칩 -> line2 텍스트 -> 마지막 silence 칩.
    idx_line0_text = html_out.index("think")
    idx_chip1 = html_out.index("trigger--silence")
    idx_line1_text = html_out.index("주인공일까")
    idx_chip2 = html_out.index("trigger--language_switch")
    idx_line2_text = html_out.index("thought")
    idx_chip3 = html_out.index("trigger--silence", idx_chip1 + 1)

    assert idx_line0_text < idx_chip1 < idx_line1_text < idx_chip2 < idx_line2_text < idx_chip3

    # 칩들이 한꺼번에 뭉쳐 나오지 않는다는 것을 명시적으로 확인: 첫 칩과 둘째 칩 사이에
    # 둘째 줄 텍스트("주인공일까")가 반드시 끼어 있어야 한다(뭉치면 idx_chip2 < idx_line1_text가 됨).
    assert idx_chip1 < idx_line1_text


def test_render_diff_splits_ins_span_at_each_hyp_line_boundary():
    """ins(전사에만 있음=환각) span이 여러 hyp_line에 걸쳐도 동일하게 줄 경계마다 쪼개져야
    한다 — 정답이 비어 있어(reference 없음) 전체가 하나의 ins span으로 처리되는 상황을 재현."""
    hyp_lines = [
        {"text": "hello world", "trigger": "silence"},
        {"text": "foo bar", "trigger": "punctuation"},
    ]
    hyp_toks, line_spans = build_hyp_layout(hyp_lines)
    diff_spans = [
        DiffSpan(kind="ins", ref_toks=[], hyp_toks=hyp_toks, ref_start=0, ref_end=0, hyp_start=0, hyp_end=len(hyp_toks))
    ]

    html_out = render_diff(diff_spans, line_spans)

    chip_line_breaks = re.findall(r"⟩</span><br>", html_out)
    assert len(chip_line_breaks) == 2
    idx_line0_text = html_out.index("world")
    idx_chip1 = html_out.index("trigger--silence")
    idx_line1_text = html_out.index("foo")
    assert idx_line0_text < idx_chip1 < idx_line1_text
