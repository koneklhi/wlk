# -*- coding: utf-8 -*-
"""Task 2: Segment.to_dict() React 호환 별칭 검증.

completed = finalized 와 동일 값
lang = detected_language (detected_language 있을 때만)
"""

from whisperlivekit.timed_objects import ASRToken, Segment


def make_token(start: float, end: float, text: str) -> ASRToken:
    return ASRToken(start=start, end=end, text=text)


def test_completed_alias_when_finalized_true():
    """finalized=True인 Segment의 to_dict()에 completed=True 포함."""
    seg = Segment.from_tokens([make_token(0.0, 1.0, '확정')])
    assert seg is not None
    seg.finalized = True
    d = seg.to_dict()
    assert 'completed' in d, "to_dict()에 'completed' 키가 없습니다"
    assert d['completed'] is True, f"completed가 True가 아닙니다: {d['completed']}"


def test_completed_alias_when_finalized_false():
    """finalized=False인 Segment의 to_dict()에 completed=False 포함."""
    seg = Segment.from_tokens([make_token(0.0, 1.0, '진행중')])
    assert seg is not None
    assert seg.finalized is False
    d = seg.to_dict()
    assert 'completed' in d, "to_dict()에 'completed' 키가 없습니다"
    assert d['completed'] is False, f"completed가 False가 아닙니다: {d['completed']}"


def test_lang_alias_when_detected_language_present():
    """detected_language 있는 Segment의 to_dict()에 lang=동일값 포함."""
    seg = Segment.from_tokens([make_token(0.0, 1.0, 'hello')])
    assert seg is not None
    seg.detected_language = 'en'
    d = seg.to_dict()
    assert 'lang' in d, "to_dict()에 'lang' 키가 없습니다"
    assert d['lang'] == 'en', f"lang 값이 'en'이 아닙니다: {d['lang']}"
    assert d['lang'] == d['detected_language'], "lang과 detected_language 값이 다릅니다"


def test_lang_alias_absent_when_no_detected_language():
    """detected_language 없는 Segment의 to_dict()에 lang 키 없음."""
    seg = Segment.from_tokens([make_token(0.0, 1.0, '언어없음')])
    assert seg is not None
    d = seg.to_dict()
    assert 'lang' not in d, f"detected_language 없는데 'lang' 키가 존재합니다: {d}"
    assert 'detected_language' not in d, f"detected_language가 예기치 않게 존재합니다: {d}"
