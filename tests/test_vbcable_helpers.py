"""scripts/vbcable_test.py 헬퍼 함수 유닛 테스트."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


# --- check_server_health ---

def test_check_server_health_connection_error():
    import urllib.error
    from vbcable_test import check_server_health
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("연결 실패")):
        with pytest.raises(RuntimeError, match="연결할 수 없습니다"):
            check_server_health("http://localhost:8000")


def test_check_server_health_not_ready():
    from vbcable_test import check_server_health
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"ready": false}'
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_response):
        with pytest.raises(RuntimeError, match="준비되지 않았습니다"):
            check_server_health("http://localhost:8000")


# --- find_reference ---

def test_find_reference_exists(tmp_path):
    from vbcable_test import find_reference
    audio = tmp_path / "test.mp3"
    audio.touch()
    ref = tmp_path / "test.txt"
    ref.write_text("안녕하세요", encoding="utf-8")
    assert find_reference(audio) == "안녕하세요"


def test_find_reference_missing(tmp_path):
    from vbcable_test import find_reference
    audio = tmp_path / "test.mp3"
    audio.touch()
    assert find_reference(audio) is None


# --- format_result ---

def test_format_result_standard():
    from vbcable_test import TestResult, format_result
    result = TestResult(
        audio_file="test_data/sbs1.mp3",
        transcription="안녕하세요",
        reference="안녕하세요",
        wer=0.0,
    )
    output = format_result(result, as_json=False)
    assert "sbs1.mp3" in output
    assert "안녕하세요" in output
    assert "0.0%" in output


def test_format_result_no_reference():
    from vbcable_test import TestResult, format_result
    result = TestResult(
        audio_file="test_data/sbs1.mp3",
        transcription="안녕하세요",
        reference=None,
        wer=None,
    )
    output = format_result(result, as_json=False)
    assert "WER" not in output
    assert "정답" not in output


def test_format_result_json():
    from vbcable_test import TestResult, format_result
    result = TestResult(
        audio_file="test_data/sbs1.mp3",
        transcription="안녕하세요",
        reference="안녕하세요",
        wer=0.085,
    )
    output = format_result(result, as_json=True)
    data = json.loads(output)
    assert data["wer"] == 0.085
    assert data["transcription"] == "안녕하세요"


# --- compute_wer_score ---

def test_compute_wer_score_arg_order():
    from vbcable_test import compute_wer_score
    with patch("whisperlivekit.metrics.compute_wer", return_value={"wer": 0.1}) as mock_wer:
        result = compute_wer_score("가나다", "나다라")
        mock_wer.assert_called_once_with("나다라", "가나다")
        assert result == 0.1
