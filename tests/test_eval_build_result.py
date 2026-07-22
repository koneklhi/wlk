"""scripts/eval.py의 _build_result 신형식/구형식/무정답 3-way 분기 통합 테스트.

정답 파일은 항상 `<stem>.txt` 하나이며, 내용에 `[spkN]` 헤더가 있으면 신형식,
없으면 구형식(빈 줄 경계)으로 판별된다. tmp_path에 합성 정답 파일을 배치해
실제 서버·오디오 없이 분기 로직만 검증한다.
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from eval import _build_result  # noqa: E402

NEW_FORMAT_TEXT = """[spk1]
the cat sat

on the mat

[spk2]
it was warm
"""

OLD_FORMAT_TEXT = """the cat sat

on the mat

it was warm
"""


def test_build_result_new_format_populates_speaker_and_sentence_fields(tmp_path):
    """정답 파일(<stem>.txt)에 [spkN] 헤더가 있으면 신형식으로 파싱하고, seg_f1은 화자경계 F1을,
    sentence_f1은 블록 내부 문장경계 F1을 각각 나타내야 한다."""
    audio_path = tmp_path / "foo.mp3"
    (tmp_path / "foo.txt").write_text(NEW_FORMAT_TEXT, encoding="utf-8")
    hyp_sentences = ["the cat sat", "on the mat", "it was warm"]

    result = _build_result(audio_path, "the cat sat on the mat it was warm", hyp_sentences, "C")

    assert result.ref_format == "new"
    assert result.wer == 0.0
    assert result.seg_f1 == 1.0  # 화자경계(spk1→spk2 전환 1개) F1
    assert result.seg_precision == 1.0
    assert result.seg_recall == 1.0
    assert result.ref_sentences == 2  # len(blocks) — spk1, spk2
    assert result.hyp_sentences == 3  # non-empty hyp 문장 수
    assert result.sentence_f1 == 1.0  # spk1 블록 내부(문장 2개) 경계 F1
    assert result.sentence_precision == 1.0
    assert result.sentence_recall == 1.0


def test_build_result_old_format_fallback_when_no_new_format_file(tmp_path):
    """정답 파일(<stem>.txt)에 [spkN] 헤더가 없으면 구형식(빈 줄 경계)으로 완전히 동일하게 폴백한다."""
    audio_path = tmp_path / "bar.mp3"
    (tmp_path / "bar.txt").write_text(OLD_FORMAT_TEXT, encoding="utf-8")
    hyp_sentences = ["the cat sat", "on the mat", "it was warm"]

    result = _build_result(audio_path, "the cat sat on the mat it was warm", hyp_sentences, "C")

    assert result.ref_format == "old"
    assert result.wer == 0.0
    assert result.seg_f1 == 1.0
    assert result.ref_sentences == 3
    assert result.hyp_sentences == 3
    assert result.sentence_f1 is None
    assert result.sentence_precision is None
    assert result.sentence_recall is None


def test_build_result_no_reference_at_all(tmp_path):
    """정답 파일이 전혀 없으면(신형식도 구형식도) 오늘과 동일하게 전부 None."""
    audio_path = tmp_path / "baz.mp3"
    hyp_sentences = ["hello world"]

    result = _build_result(audio_path, "hello world", hyp_sentences, "C")

    assert result.ref_format is None
    assert result.reference is None
    assert result.wer is None
    assert result.seg_f1 is None
    assert result.seg_precision is None
    assert result.seg_recall is None
    assert result.sentence_f1 is None
    assert result.sentence_precision is None
    assert result.sentence_recall is None


# ── 언어 불일치율(LMR) 필드 ────────────────────────────────────────────────

LMR_NEW_FORMAT_TEXT = """[spk1]
thank you minister

[spk2]
누가 주인공일까 이런 생각을 제가 제일 많이 했어요
"""

# 비언어 태그((웃음) 등)가 섞인 정답 — 파서 출구에서 이미 제거되므로 LMR 분모에 들어가면 안 된다.
LMR_TAGGED_FORMAT_TEXT = """[spk1]
(웃음) 누가 주인공일까 (박수) 이런 생각을 (환호)
"""

REAL_KO_HYP = "Who is the one who is the one who"


def test_build_result_new_format_populates_lmr_fields(tmp_path):
    """신형식 분기에서 lmr_ko/lmr_en/lmr_wer_pp/lang_mismatch/lang_flip_events가 모두 채워진다."""
    audio_path = tmp_path / "lmr.mp3"
    (tmp_path / "lmr.txt").write_text(LMR_NEW_FORMAT_TEXT, encoding="utf-8")
    hyp_sentences = ["thank you minister", REAL_KO_HYP]

    result = _build_result(audio_path, "thank you minister " + REAL_KO_HYP, hyp_sentences, "C")

    assert result.ref_format == "new"
    assert result.lang_mismatch is not None
    assert result.lmr_ko is not None and result.lmr_ko > 0.0
    assert result.lmr_wer_pp is not None and result.lmr_wer_pp > 0.0
    assert result.lmr_en == 0.0  # 영어 문장은 그대로 맞았다
    assert result.lang_mismatch["ko_to_en"] > 0
    # 문장 단위 뒤집힘 이벤트(정성 리포트 전용) — 화자 정보가 함께 실린다.
    assert result.lang_flip_events
    assert result.lang_flip_events[0]["ref_script"] == "KO"
    assert result.lang_flip_events[0]["hyp_script"] == "EN"
    assert result.lang_flip_events[0]["speaker"] == "spk2"


def test_build_result_nonverbal_tags_excluded_from_lmr_denominator(tmp_path):
    """정답의 (웃음)(박수)(환호) 태그는 파서 출구에서 이미 제거되므로 LMR 분모에 산입되지 않는다.

    end-to-end 증명: 태그를 뺀 실질 단어 수(4)와 ko_ref_words가 정확히 일치해야 한다.
    (신규 지표가 _strip_nonverbal_tags를 다시 호출해 이중 적용하는 실수도 함께 막는다.)
    """
    audio_path = tmp_path / "tagged.mp3"
    (tmp_path / "tagged.txt").write_text(LMR_TAGGED_FORMAT_TEXT, encoding="utf-8")

    result = _build_result(audio_path, REAL_KO_HYP, [REAL_KO_HYP], "C")

    assert result.reference == "누가 주인공일까 이런 생각을"
    assert result.lang_mismatch["ref_words"] == 4
    assert result.lang_mismatch["ko_ref_words"] == 4  # 태그 3개가 남아 있었다면 7이 됐을 것
    assert "웃음" not in result.reference
    assert result.lang_mismatch["ko_ok"] == 0


def test_build_result_old_format_also_populates_lmr(tmp_path):
    """구형식 폴백 경로에서도 LMR은 채워진다(단, 문장 단위 flip 이벤트는 신형식 전용이라 None)."""
    audio_path = tmp_path / "oldlmr.mp3"
    (tmp_path / "oldlmr.txt").write_text("누가 주인공일까 이런 생각을\n\nthank you minister\n", encoding="utf-8")

    result = _build_result(
        audio_path, "Who is the one thank you minister", ["Who is the one", "thank you minister"], "C"
    )

    assert result.ref_format == "old"
    assert result.lang_mismatch is not None
    assert result.lmr_ko is not None and result.lmr_ko > 0.0
    assert result.lang_flip_events is None


def test_build_result_no_reference_leaves_lmr_none(tmp_path):
    """정답이 없으면 LMR 필드도 전부 None(0.0이 아님)."""
    result = _build_result(tmp_path / "none.mp3", "hello world", ["hello world"], "C")
    assert result.lmr_ko is None
    assert result.lmr_en is None
    assert result.lmr_wer_pp is None
    assert result.lang_mismatch is None
    assert result.lang_flip_events is None


def test_build_result_unparseable_new_format_file_falls_back_to_old(tmp_path):
    """파일명이 신형식 규약대로 <stem>.txt여도 내용에 [spkN] 헤더가 없으면 파싱 실패하고
    (parse_speaker_sentence_reference가 None을 반환하면) 같은 파일을 구형식으로 폴백한다."""
    audio_path = tmp_path / "qux.mp3"
    (tmp_path / "qux.txt").write_text(OLD_FORMAT_TEXT, encoding="utf-8")
    hyp_sentences = ["the cat sat", "on the mat", "it was warm"]

    result = _build_result(audio_path, "the cat sat on the mat it was warm", hyp_sentences, "C")

    assert result.ref_format == "old"
    assert result.sentence_f1 is None
