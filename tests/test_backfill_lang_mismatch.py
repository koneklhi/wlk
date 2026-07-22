"""scripts/backfill_lang_mismatch.py 유닛 테스트 (서버·오디오 없음, 순수 오프라인).

`scripts/`는 패키지가 아니므로 sys.path에 추가해 임포트한다
(tests/test_eval_build_result.py와 동일 방식).
"""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from backfill_lang_mismatch import (  # noqa: E402
    aggregate,
    flatten_reference_sentences,
    format_table,
    main,
    recompute_files,
    verify_reference_parity,
)
from eval import parse_speaker_sentence_reference  # noqa: E402

REF_TEXT = """[spk1]
thank you minister

[spk2]
누가 주인공일까 이런 생각을
"""

REFERENCE = "thank you minister 누가 주인공일까 이런 생각을"

# 판본이 다른 정답(한 단어가 추가됨) — 실제로 워크트리마다 이런 미세 차이가 존재한다.
OTHER_VERSION_REF_TEXT = """[spk1]
thank you minister

[spk2]
누가 진짜 주인공일까 이런 생각을
"""

MINI_REPORT = {
    "files": [
        {
            "audio_file": "test_data/mini.mp3",
            "path": "C",
            "reference": REFERENCE,
            "transcription": "thank you minister Who is the one thought",
            "wer": 0.6,
        },
        {
            "audio_file": "test_data/mini.mp3",
            "path": "C",
            "reference": REFERENCE,
            "transcription": "thank you minister 누가 주인공일까 이런 생각을",
            "wer": 0.0,
        },
    ]
}


def test_recompute_files_produces_lmr_per_run():
    rows = recompute_files(MINI_REPORT)
    assert len(rows) == 2
    # 1회차: 한국어 4단어가 영어로 뒤집힘
    assert rows[0]["lang_mismatch"]["ko_to_en"] > 0
    assert rows[0]["lmr_ko"] > 0.0
    assert rows[0]["lmr_wer_pp"] > 0.0
    # 2회차: 완전 일치
    assert rows[1]["lmr_ko"] == 0.0
    assert rows[1]["lmr_en"] == 0.0
    assert rows[1]["lang_flip_events"] is None  # --ref-file 없이는 이벤트 미계산


def test_recompute_files_with_ref_sentences_adds_flip_events():
    parsed = parse_speaker_sentence_reference(REF_TEXT)
    rows = recompute_files(MINI_REPORT, flatten_reference_sentences(parsed))
    assert rows[0]["lang_flip_events"]  # 한국어 문장이 영어로 뒤집힘
    assert rows[0]["lang_flip_events"][0]["speaker"] == "spk2"
    assert rows[1]["lang_flip_events"] == []  # 완전 일치 회차는 이벤트 없음


def test_recompute_files_handles_missing_reference():
    report = {"files": [{"audio_file": "x.mp3", "path": "C", "reference": None, "transcription": "hi"}]}
    rows = recompute_files(report)
    assert rows[0]["lmr_ko"] is None
    assert rows[0]["lang_mismatch"] is None


def test_aggregate_and_table_render():
    rows = recompute_files(MINI_REPORT)
    agg = aggregate(rows)
    assert agg["lmr_ko"]["min"] == 0.0
    assert agg["lmr_ko"]["max"] > 0.0
    assert agg["lmr_ko"]["median"] is not None
    table = format_table(rows, agg)
    assert "LMR_ko" in table
    assert "하한" in table  # 하한(lower bound) 경고 문구


def test_aggregate_with_no_values():
    agg = aggregate([{"wer": None, "lmr_ko": None, "lmr_en": None, "lmr_wer_pp": None}])
    assert agg["lmr_ko"] == {"median": None, "min": None, "max": None, "stdev": None}


def test_verify_reference_parity_passes_for_matching_version():
    parsed = parse_speaker_sentence_reference(REF_TEXT)
    verify_reference_parity(parsed, MINI_REPORT)  # 예외 없이 통과


def test_verify_reference_parity_aborts_on_version_mismatch():
    """벤치 JSON의 reference와 다른 판본의 정답 파일을 주면 assert로 즉시 중단해야 한다.

    (메인 저장소와 워크트리의 test_data/*.txt 판본이 다른 실제 함정을 막는 가드다 —
    판본이 어긋난 채 정렬하면 조용히 잘못된 이벤트가 나온다.)
    """
    parsed = parse_speaker_sentence_reference(OTHER_VERSION_REF_TEXT)
    with pytest.raises(AssertionError, match="정답 판본 불일치"):
        verify_reference_parity(parsed, MINI_REPORT)


def test_main_end_to_end_writes_new_file(tmp_path, capsys):
    bench = tmp_path / "bench.json"
    bench.write_text(json.dumps(MINI_REPORT, ensure_ascii=False), encoding="utf-8")
    ref_file = tmp_path / "mini.txt"
    ref_file.write_text(REF_TEXT, encoding="utf-8")
    out = tmp_path / "backfilled.json"

    rc = main([str(bench), "--ref-file", str(ref_file), "--output", str(out)])
    assert rc == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["files"]) == 2
    assert payload["aggregate"]["lmr_ko"]["max"] > 0.0
    # 입력 JSON은 손대지 않는다(in-place 수정 금지).
    assert json.loads(bench.read_text(encoding="utf-8")) == MINI_REPORT
    assert "LMR_ko" in capsys.readouterr().out


def test_main_refuses_inplace_output(tmp_path):
    bench = tmp_path / "bench.json"
    bench.write_text(json.dumps(MINI_REPORT, ensure_ascii=False), encoding="utf-8")
    assert main([str(bench), "--output", str(bench)]) == 1
    assert json.loads(bench.read_text(encoding="utf-8")) == MINI_REPORT


def test_main_rejects_reference_without_speaker_headers(tmp_path):
    bench = tmp_path / "bench.json"
    bench.write_text(json.dumps(MINI_REPORT, ensure_ascii=False), encoding="utf-8")
    ref_file = tmp_path / "old.txt"
    ref_file.write_text("헤더 없는 구형식 정답\n", encoding="utf-8")
    assert main([str(bench), "--ref-file", str(ref_file)]) == 1
