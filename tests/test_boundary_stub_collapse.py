"""언어경계 유령 stub 붕괴(collapse) 단위 테스트 — Exp-209.

배경(ytn1 20회 실측, N=37 플래그):
  DUP    32% — 직전 줄과 텍스트 겹침(전수가 PREV 쪽. NEXT 쪽 0건이라 백엔드
                텍스트커버 가드가 구조적으로 못 잡는다) → 드롭
  HALLUC 46% — 교차언어 환각 → 병합(거짓 줄바꿈만 제거)
  LEGIT  22% — 정상 단어가 오분할된 것(`of`|`Korea`) → 병합(절대 드롭 금지)

정답이 런타임에 없으므로 HALLUC/LEGIT는 구분할 수 없다. 따라서 **드롭은 텍스트
동일성으로 증명되는 DUP에만** 적용하고 나머지는 후방 병합한다(Exp-208 원리 재사용).
"""
from whisperlivekit.timed_objects import PuncSegment
from whisperlivekit.tokens_alignment import BOUNDARY_STUB_MAX_WORDS, TokensAlignment


def _make_alignment():
    class _Args:
        diarization = True

    class _State:
        new_tokens = []
        new_diarization = []
        new_translation = []
        new_tokens_buffer = []
        new_translation_buffer = None

    return TokensAlignment(_State(), _Args(), sep="")


def _seg(text, start, end, speaker=1, trigger=None, lang=None, hard=False):
    s = PuncSegment(start=start, end=end, text=text, speaker=speaker)
    s.finalize_trigger = trigger
    s.detected_language = lang
    s.hard_boundary = hard
    return s


def _texts(segs):
    return [s.text for s in segs]


# ── DUP → 드롭 ────────────────────────────────────────────────────────────────

def test_dup_stub_is_dropped():
    """직전 줄과 텍스트가 겹치는 stub은 드롭된다(실측 'First.' 계열)."""
    ta = _make_alignment()
    segs = [
        _seg("I want to first thank Minister Jung.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg("First.", 13.0, 13.1, 1, "language_switch", "en", hard=True),
        _seg("우선 오늘 안보협의회 회의를 주관해 주신", 13.2, 17.0, 1, None, "ko"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert _texts(out) == [
        "I want to first thank Minister Jung.",
        "우선 오늘 안보협의회 회의를 주관해 주신",
    ]


def test_dup_stub_does_not_alter_previous_text():
    """드롭은 순수 제거 — 직전 줄 텍스트를 건드리지 않는다."""
    ta = _make_alignment()
    prev = _seg("...for hosting today's Security Consultative Meeting.", 10.0, 13.0, 1, "punctuation", "en")
    segs = [prev, _seg("Meeting.", 13.0, 13.1, 1, "language_switch", "en", hard=True)]
    out = ta._collapse_boundary_stubs(segs)
    assert len(out) == 1
    assert out[0].text == "...for hosting today's Security Consultative Meeting."


def test_korean_dup_stub_is_dropped():
    """한국어 중복도 동일하게 처리(실측 R9 '감사합니다.' — 직전 줄이 같은 말로 끝남)."""
    ta = _make_alignment()
    segs = [
        _seg("이번 안보협의회는 지난 반세기 동안 큰 역할을 한 것에 대해 감사합니다.", 30.0, 40.0, 1, "silence", "ko"),
        _seg("감사합니다.", 40.2, 40.4, 1, "language_switch", "ko", hard=True),
        _seg("The United States remains fully committed...", 41.0, 46.0, 2, None, "en"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert len(out) == 2
    assert out[0].text.endswith("감사합니다.")
    assert out[1].text.startswith("The United States")


def test_stopword_only_overlap_is_not_dup(monkeypatch):
    """기능어('the')만 겹치는 건 중복 증거가 아니다 — 드롭이 아니라 병합해야 한다.

    실측 R18: 직전 줄 'The first of all, I would like to thank Minister Zheng...' +
    stub 'The President:.' — 내용어 'president'는 직전 줄에 없다. 단순 단어겹침으로
    판정하면 'the' 때문에 DUP 로 오판해 **중복이 아닌 텍스트를 삭제**하게 된다.
    """
    ta = _make_alignment()
    segs = [
        _seg("The first of all, I would like to thank Minister Zheng for hosting today's meeting.",
             10.0, 16.0, 1, "punctuation", "en"),
        _seg("The President:.", 16.2, 16.4, 1, "language_switch", "en", hard=True),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert len(out) == 1
    assert out[0].text.endswith("The President:.")   # 드롭이 아니라 병합


# ── 비-DUP → 후방 병합 (LEGIT 보존이 핵심) ───────────────────────────────────

def test_legit_stub_is_merged_backward_not_dropped():
    """정답 단어(Korea)는 절대 사라지면 안 된다 — 직전 줄에 병합된다."""
    ta = _make_alignment()
    segs = [
        _seg("The United States remains fully committed to the defense of the Republic of.",
             40.0, 49.0, 2, "silence", "en"),
        _seg("Korea.", 49.2, 49.3, 2, "language_switch", "en", hard=True),
        _seg("미국은 대한민국 방위에 여전히 확고한 의지를 갖고 있습니다.", 50.0, 55.0, 1, None, "ko"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert len(out) == 2
    assert "Korea." in out[0].text          # 단어 유실 없음
    assert out[1].text.startswith("미국은")   # 다음 줄은 그대로


def test_halluc_stub_is_merged_backward():
    """환각도 드롭이 아니라 병합 — 정답 없이는 LEGIT과 구분 불가하므로 보수적으로."""
    ta = _make_alignment()
    segs = [
        _seg("...prosperity on the Korean Peninsula and in the broader Indo-Pacific region.",
             60.0, 69.0, 2, "punctuation", "en"),
        _seg("Han.", 69.5, 69.6, 2, "language_switch", "en", hard=True),
        _seg("한미동맹은 철통과도 같습니다.", 70.0, 72.0, 2, None, "ko"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert len(out) == 2
    assert out[0].text.endswith("Han.")


def test_merge_extends_previous_segment_end():
    """병합 시 직전 세그먼트의 end가 stub 끝까지 확장된다."""
    ta = _make_alignment()
    segs = [
        _seg("...the Republic of.", 40.0, 49.0, 2, "silence", "en"),
        _seg("Korea.", 49.2, 49.4, 2, "language_switch", "en", hard=True),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert out[0].end == 49.4


def test_merge_inherits_stub_finalize_trigger():
    """병합 후 그 줄을 닫은 계기는 stub 쪽 경계다 — trigger를 승계한다."""
    ta = _make_alignment()
    segs = [
        _seg("...the Republic of.", 40.0, 49.0, 2, "silence", "en"),
        _seg("Korea.", 49.2, 49.4, 2, "language_switch", "en", hard=True),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert out[0].finalize_trigger == "language_switch"


def test_collapse_is_idempotent():
    """두 번 적용해도 결과가 같아야 한다(호출 지점이 매 틱 반복되므로)."""
    ta = _make_alignment()
    segs = [
        _seg("I want to first thank Minister Jung.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg("First.", 13.0, 13.1, 1, "language_switch", "en", hard=True),
        _seg("우선 오늘 안보협의회 회의를", 13.2, 17.0, 1, None, "ko"),
    ]
    once = ta._collapse_boundary_stubs(segs)
    twice = ta._collapse_boundary_stubs(once)
    assert _texts(once) == _texts(twice)


# ── 손대면 안 되는 경우 ───────────────────────────────────────────────────────

def test_different_speaker_is_untouched():
    """화자가 다르면 진짜 화자경계일 수 있다 — 병합·드롭 모두 금지(화자분리 F1 보호)."""
    ta = _make_alignment()
    segs = [
        _seg("Thank you very much.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg("네.", 13.2, 13.3, 2, "language_switch", "ko", hard=True),
        _seg("다음 질문 드리겠습니다.", 14.0, 16.0, 2, None, "ko"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert _texts(out) == _texts(segs)


def test_long_segment_is_untouched():
    """stub 길이 상한을 넘으면 정상 문장이므로 손대지 않는다."""
    ta = _make_alignment()
    long_text = " ".join(["word"] * (BOUNDARY_STUB_MAX_WORDS + 3)) + "."
    segs = [
        _seg("Previous sentence here.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg(long_text, 13.2, 15.0, 1, "language_switch", "en", hard=True),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert _texts(out) == _texts(segs)


def test_non_boundary_stub_is_untouched():
    """언어전환 경계로 닫힌 stub이 아니면 대상이 아니다(짧은 정상 발화 보호)."""
    ta = _make_alignment()
    segs = [
        _seg("안녕하십니까.", 0.0, 1.5, 1, "punctuation", "ko"),
        _seg("네.", 2.0, 2.2, 1, "silence", "ko"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert _texts(out) == _texts(segs)


def test_stub_without_previous_text_segment_is_untouched():
    """직전 텍스트 세그먼트가 없으면 병합 대상이 없다 — 그대로 둔다(서두 보호)."""
    ta = _make_alignment()
    segs = [
        _seg("Yeah.", 0.5, 0.6, 1, "language_switch", "en", hard=True),
        _seg("안녕하십니까.", 1.0, 2.5, 1, None, "ko"),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert _texts(out) == _texts(segs)


def test_silence_segment_is_not_a_merge_target():
    """침묵 세그먼트는 병합 대상이 아니다 — 그 앞 텍스트 세그먼트로 붙는다."""
    from whisperlivekit.timed_objects import SilentSegment
    ta = _make_alignment()
    sil = SilentSegment(start=49.0, end=49.2, text="", speaker=-2)
    segs = [
        _seg("...the Republic of.", 40.0, 49.0, 2, "silence", "en"),
        sil,
        _seg("Korea.", 49.2, 49.4, 2, "language_switch", "en", hard=True),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert "Korea." in out[0].text
    assert all(s.text != "Korea." for s in out[1:])


# ── 롤백 플래그 ───────────────────────────────────────────────────────────────

def test_rollback_flag_disables_collapse(monkeypatch):
    import whisperlivekit.tokens_alignment as ta_mod
    monkeypatch.setattr(ta_mod, "BOUNDARY_STUB_COLLAPSE_ENABLED", False)
    ta = _make_alignment()
    segs = [
        _seg("I want to first thank Minister Jung.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg("First.", 13.0, 13.1, 1, "language_switch", "en", hard=True),
    ]
    out = ta._collapse_boundary_stubs(segs)
    assert _texts(out) == _texts(segs)


# ── 배선(wiring) 검증 — get_lines() 경유로 실제 적용되는지 ──────────────────

def test_collapse_is_wired_into_get_lines_diarization():
    """유닛 15개는 메서드를 직접 호출한다 — 훅이 실제로 살아있는지는 별개 문제다.

    get_lines(diarization=True) 를 통과시켜 조립 결과에 collapse 가 반영되는지 확인한다.
    (측정에서 0건이 나왔을 때 '발동 안 함'인지 '대상 없음'인지 가르는 근거이기도 하다.)
    """
    ta = _make_alignment()
    segs = [
        _seg("I want to first thank Minister Jung.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg("First.", 13.0, 13.1, 1, "language_switch", "en", hard=True),
        _seg("우선 오늘 안보협의회 회의를 주관해 주신", 13.2, 17.0, 1, None, "ko"),
    ]
    ta.get_lines_diarization = lambda audio_time=None, flush=False: (segs, "")
    lines, _buf, _tr = ta.get_lines(diarization=True, audio_time=20.0)
    texts = [s.text for s in lines if not s.is_silence()]
    assert "First." not in texts          # 훅이 살아있으면 stub 이 사라진다
    assert any(t.startswith("I want to first thank") for t in texts)


def test_collapse_runs_before_translation_attachment():
    """드롭할 stub 에 번역을 붙이지 않는다(LLM 호출 낭비 방지)."""
    ta = _make_alignment()
    translated = []
    ta.add_translation = lambda seg: translated.append(seg.text)
    segs = [
        _seg("I want to first thank Minister Jung.", 10.0, 13.0, 1, "punctuation", "en"),
        _seg("First.", 13.0, 13.1, 1, "language_switch", "en", hard=True),
    ]
    ta.get_lines_diarization = lambda audio_time=None, flush=False: (segs, "")
    ta.get_lines(diarization=True, translation=True, audio_time=20.0)
    assert "First." not in translated
