"""단계 1 — 언어 전환 프로토콜/경계 마커 단위 테스트 (모델 불필요)."""
from whisperlivekit.timed_objects import ASRToken, LanguageSwitch, Silence


def test_language_switch_marker_flags():
    m = LanguageSwitch(start=1.0, end=1.0, detected_language="en")
    assert m.is_boundary() is True
    assert m.is_silence() is False
    assert m.text == ""


def test_asrtoken_and_silence_not_boundary():
    t = ASRToken(start=0.0, end=0.1, text="hi")
    assert t.is_boundary() is False
    s = Silence(start=0.0, end=0.5)
    assert s.is_boundary() is False


def _make_alignment():
    """실제 State/args 없이 TokensAlignment를 최소 구성."""
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
    return ta


def test_boundary_splits_segments_without_silence_segment():
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.2, text="안녕", detected_language="ko"),
        ASRToken(start=0.2, end=0.4, text="하세요", detected_language="ko"),
        LanguageSwitch(start=0.5, end=0.5, detected_language="en"),
        ASRToken(start=0.6, end=0.8, text="hello", detected_language="en"),
        ASRToken(start=0.8, end=1.0, text="world", detected_language="en"),
    ]
    segs = ta.compute_punctuations_segments()
    # 경계로 2개 세그먼트 분할, 침묵 세그먼트(speaker=-2)는 없어야 함
    assert len(segs) == 2
    assert not any(s.is_silence() for s in segs)
    assert segs[0].text == "안녕하세요"
    assert segs[1].text == "helloworld"


def test_boundary_marker_never_in_segment_text():
    ta = _make_alignment()
    ta.all_tokens = [
        ASRToken(start=0.0, end=0.2, text="a"),
        LanguageSwitch(start=0.3, end=0.3),
        ASRToken(start=0.4, end=0.6, text="b"),
    ]
    segs = ta.compute_punctuations_segments()
    joined = "".join(s.text or "" for s in segs)
    assert joined == "ab"  # 마커 text('')가 세그먼트에 섞이지 않음
