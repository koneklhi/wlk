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


# --- collect_ws_finalized (WS 병행 검증) ---

def _frame(**payload) -> str:
    return json.dumps(payload, ensure_ascii=False)


def test_collect_ws_finalized_snapshot_and_diff():
    """snapshot(lines)과 diff(new_lines) 양쪽에서 확정 세그먼트를 모은다."""
    from vbcable_test import collect_ws_finalized
    frames = [
        _frame(type="snapshot", lines=[{"id": 0, "speaker": 1, "text": "첫 문장", "finalized": True}]),
        _frame(type="diff", new_lines=[{"id": 1, "speaker": 2, "text": "둘째 문장", "completed": True}]),
    ]
    assert collect_ws_finalized(frames) == {"0": "첫 문장", "1": "둘째 문장"}


def test_collect_ws_finalized_last_write_wins():
    """같은 id 가 자라며 다시 오면 마지막 판만 남는다 (delta 배열 재조립 없이)."""
    from vbcable_test import collect_ws_finalized
    frames = [
        _frame(lines=[{"id": 0, "speaker": 1, "text": "자라는", "finalized": True}]),
        _frame(lines=[{"id": 0, "speaker": 1, "text": "자라는 문장입니다", "finalized": True}]),
    ]
    assert collect_ws_finalized(frames) == {"0": "자라는 문장입니다"}


def test_collect_ws_finalized_skips_unfinalized_and_silence():
    from vbcable_test import collect_ws_finalized
    frames = [
        _frame(lines=[
            {"id": 0, "speaker": 1, "text": "미확정", "finalized": False},
            {"id": 1, "speaker": -2, "text": "침묵", "finalized": True},
            {"id": 2, "speaker": 1, "text": "", "finalized": True},
        ]),
        "이건 JSON 이 아니다",
    ]
    assert collect_ws_finalized(frames) == {}


# --- ws_dom_warnings ---

def test_ws_dom_warnings_clean():
    from vbcable_test import ws_dom_warnings
    rows = [{"text": "서버가 확정한 문장입니다"}]
    assert ws_dom_warnings(rows, {"0": "서버가 확정한 문장입니다"}) == []


def test_ws_dom_warnings_detects_drop():
    """서버는 보냈는데 화면에 없다 = 프런트가 삼킨 것."""
    from vbcable_test import ws_dom_warnings
    warnings = ws_dom_warnings([{"text": "다른 내용"}], {"0": "화면에서 사라진 문장"})
    assert len(warnings) == 1 and "누락" in warnings[0]


def test_ws_dom_warnings_detects_duplicate():
    """Exp-181/182 의 growing-prefix 중복 시그니처."""
    from vbcable_test import ws_dom_warnings
    rows = [{"text": "중복된 확정 문장"}, {"text": "중복된 확정 문장"}]
    warnings = ws_dom_warnings(rows, {"0": "중복된 확정 문장"})
    assert len(warnings) == 1 and "중복" in warnings[0]


def test_ws_dom_warnings_ignores_short_fragments():
    """짧은 조각은 우연 일치가 잦아 경고하지 않는다."""
    from vbcable_test import ws_dom_warnings
    assert ws_dom_warnings([{"text": "무관"}], {"0": "네"}) == []


# --- dist_staleness ---

def _make_app_tree(root: Path, dist_mtime: float, src_mtime: float) -> None:
    (root / "frontend" / "app" / "src").mkdir(parents=True)
    (root / "frontend" / "static").mkdir(parents=True)
    src = root / "frontend" / "app" / "src" / "main.tsx"
    src.write_text("x", encoding="utf-8")
    dist = root / "frontend" / "static" / "index.html"
    dist.write_text("<html></html>", encoding="utf-8")
    import os
    os.utime(src, (src_mtime, src_mtime))
    os.utime(dist, (dist_mtime, dist_mtime))


def test_dist_staleness_fresh(tmp_path):
    from vbcable_test import dist_staleness
    _make_app_tree(tmp_path, dist_mtime=2000, src_mtime=1000)
    assert dist_staleness(tmp_path) is None


def test_dist_staleness_stale(tmp_path):
    """소스가 dist 보다 최신이면 측정 전에 막는다 — 소스와 다른 UI 를 재는 것을 방지."""
    from vbcable_test import dist_staleness
    _make_app_tree(tmp_path, dist_mtime=1000, src_mtime=2000)
    msg = dist_staleness(tmp_path)
    assert msg and "pnpm build" in msg


def test_dist_staleness_missing_dist(tmp_path):
    from vbcable_test import dist_staleness
    (tmp_path / "frontend" / "app" / "src").mkdir(parents=True)
    msg = dist_staleness(tmp_path)
    assert msg and "dist 가 없습니다" in msg


def test_dist_staleness_no_source_tree(tmp_path):
    """배포 PC 는 frontend/app 소스가 없다 — 검사 불가이므로 통과시킨다."""
    from vbcable_test import dist_staleness
    assert dist_staleness(tmp_path) is None


# --- compute_wer_score ---

def test_compute_wer_score_arg_order():
    from vbcable_test import compute_wer_score
    with patch("whisperlivekit.metrics.compute_wer", return_value={"wer": 0.1}) as mock_wer:
        result = compute_wer_score("가나다", "나다라")
        mock_wer.assert_called_once_with("나다라", "가나다")
        assert result == 0.1
