"""SimulStreamingOnlineProcessor._filter_cross_batch_repetitions 유닛 테스트.

cross-batch 반복 아티팩트("바 바 바", "-그 -그") 제거 로직만 격리하여 테스트한다.
실제 모델 로드 없이 ASRToken 리스트를 직접 주입한다.
"""

from unittest.mock import MagicMock
from whisperlivekit.timed_objects import ASRToken


def _make_processor():
    """모델 로드 없이 _filter_cross_batch_repetitions 메서드만 테스트하기 위한 최소 프로세서 생성."""
    from whisperlivekit.simul_whisper.backend import SimulStreamingOnlineProcessor

    asr = MagicMock()
    asr.tokenizer = None
    asr.use_full_mlx = False

    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc._last_emitted_word = None
    proc._filter_cross_batch_repetitions = SimulStreamingOnlineProcessor._filter_cross_batch_repetitions.__get__(proc)
    return proc


def _tok(text: str) -> ASRToken:
    return ASRToken(start=0.0, end=0.1, text=text)


# ─────────────────────────────────────────────
# 기본 동작
# ─────────────────────────────────────────────

def test_no_repetition_unchanged():
    proc = _make_processor()
    tokens = [_tok("안녕"), _tok("하세요"), _tok("반갑습니다")]
    result = proc._filter_cross_batch_repetitions(tokens)
    assert [t.text for t in result] == ["안녕", "하세요", "반갑습니다"]
    assert proc._last_emitted_word == "반갑습니다"


def test_within_batch_consecutive_removed():
    """배치 내 "바 바 바" → "바" 하나만 남김."""
    proc = _make_processor()
    tokens = [_tok("바"), _tok("바"), _tok("바")]
    result = proc._filter_cross_batch_repetitions(tokens)
    assert [t.text for t in result] == ["바"]
    assert proc._last_emitted_word == "바"


def test_cross_batch_repeat_removed():
    """직전 배치 마지막 단어 = 이번 배치 첫 단어 → 제거."""
    proc = _make_processor()
    # 배치 1
    proc._filter_cross_batch_repetitions([_tok("한"), _tok("도"), _tok("동쪽")])
    # 배치 2 첫 토큰이 "동쪽" 반복
    result = proc._filter_cross_batch_repetitions([_tok("동쪽"), _tok("이"), _tok("라")])
    assert result[0].text == "이"
    assert [t.text for t in result] == ["이", "라"]


def test_cross_batch_different_word_kept():
    """직전 배치 마지막과 다른 단어 → 그대로 유지."""
    proc = _make_processor()
    proc._filter_cross_batch_repetitions([_tok("동쪽")])
    result = proc._filter_cross_batch_repetitions([_tok("이"), _tok("라")])
    assert [t.text for t in result] == ["이", "라"]


def test_gr_gr_pattern():
    """-그 -그 패턴 제거."""
    proc = _make_processor()
    tokens = [_tok("-그"), _tok("-그"), _tok("-그"), _tok("래서")]
    result = proc._filter_cross_batch_repetitions(tokens)
    assert [t.text for t in result] == ["-그", "래서"]


def test_empty_tokens_no_crash():
    proc = _make_processor()
    result = proc._filter_cross_batch_repetitions([])
    assert result == []
    assert proc._last_emitted_word is None


def test_last_emitted_word_updated():
    """필터 후 _last_emitted_word가 마지막 방출 단어로 갱신됨."""
    proc = _make_processor()
    proc._filter_cross_batch_repetitions([_tok("첫"), _tok("번째")])
    assert proc._last_emitted_word == "번째"


def test_reset_clears_memory():
    """_last_emitted_word를 None으로 재설정하면 이전 단어 기억 사라짐."""
    proc = _make_processor()
    proc._filter_cross_batch_repetitions([_tok("동쪽")])
    proc._last_emitted_word = None  # long silence 리셋 시뮬레이션
    result = proc._filter_cross_batch_repetitions([_tok("동쪽"), _tok("에서")])
    assert [t.text for t in result] == ["동쪽", "에서"]


def test_whitespace_stripped_comparison():
    """토큰 text에 앞뒤 공백이 있어도 같은 단어로 인식."""
    proc = _make_processor()
    proc._filter_cross_batch_repetitions([_tok(" 바 ")])
    result = proc._filter_cross_batch_repetitions([_tok("바")])
    assert result == []


def test_mixed_ko_en_no_false_positive():
    """한/영 혼용에서 다른 단어는 제거되지 않음."""
    proc = _make_processor()
    tokens = [_tok("from"), _tok("a"), _tok("satellite"), _tok("image")]
    result = proc._filter_cross_batch_repetitions(tokens)
    assert [t.text for t in result] == ["from", "a", "satellite", "image"]
