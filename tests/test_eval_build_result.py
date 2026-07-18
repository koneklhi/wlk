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


def test_build_result_unparseable_new_format_file_falls_back_to_old(tmp_path):
    """파일명이 신형식 규약대로 <stem>.txt여도 내용에 [spkN] 헤더가 없으면 파싱 실패하고
    (parse_speaker_sentence_reference가 None을 반환하면) 같은 파일을 구형식으로 폴백한다."""
    audio_path = tmp_path / "qux.mp3"
    (tmp_path / "qux.txt").write_text(OLD_FORMAT_TEXT, encoding="utf-8")
    hyp_sentences = ["the cat sat", "on the mat", "it was warm"]

    result = _build_result(audio_path, "the cat sat on the mat it was warm", hyp_sentences, "C")

    assert result.ref_format == "old"
    assert result.sentence_f1 is None
