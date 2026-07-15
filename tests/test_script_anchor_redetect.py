"""스크립트-앵커 재감지 게이트(GOAL_SCRIPT_ANCHOR_REDETECT) — 단위 테스트.

무음·화자전환 없는 연속 코드스위칭에서 기존 재감지 트리거 4종(짧은침묵·긴침묵·
화자전환 eager·PLC)이 전부 미발동해 구언어가 고착되는 구멍(Exp-172 실측)을 메우는
신규 게이트를 검증한다.

트리거: 실제 방출 토큰의 스크립트가 잠긴 detected_language와 연속 N단어(기본 3)
또는 T초(기본 1.0) 반전 유지 시 → detect_current_language(2.0s, 0.90) 재감지 →
다른 언어 확신 시에만 _apply_detected_language + 해당 배치 드롭(마커는
_apply_detected_language가 arm, backend.py process_iter가 다음 신언어 배치 앞에 방출).

관례는 tests/test_lang_redetect.py의 MagicMock 방식을 따른다.
"""

from unittest.mock import MagicMock

import whisperlivekit.simul_whisper.backend as backend_module
from whisperlivekit.simul_whisper.backend import (
    _ACRONYM_MAX_ALLCAPS_LEN,
    _ACRONYM_MAX_SINGLE_LEN,
    _SCRIPT_ANCHOR_N_WORDS,
    _SCRIPT_ANCHOR_T_SECS,
    MIN_DURATION_REAL_SILENCE,
    SimulStreamingOnlineProcessor,
    _is_acronym_like_latin,
)
from whisperlivekit.timed_objects import ASRToken, ChangeSpeaker


def _tok(text, start=0.0, end=0.1):
    return ASRToken(start, end, text)


def _make_processor(locked_lang="en", language="auto"):
    """모델 로드 없이 최소 프로세서 생성 (test_lang_redetect.py 관례)."""
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc.buffer = []
    proc.end = 0.0
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc._consecutive_char_repeat = 0
    proc._short_silence_check_at = 0.0
    proc._recent_emitted_words = []
    proc._script_mismatch_streak = []
    proc._anchor_repeat_window = []
    proc._script_anchor_streak = []
    proc._script_anchor_streak_start = None
    proc._script_anchor_streak_end = None

    model = MagicMock()
    model.cfg.language = language
    model.state = MagicMock()
    model.state.detected_language = locked_lang
    model.detect_current_language = MagicMock(return_value=None)
    model.segments_len = MagicMock(return_value=2.0)
    proc.model = model
    return proc


# ── 트리거 문턱 (N단어 / T초) ────────────────────────────────────────────────

def test_streak_below_n_no_trigger():
    """(1) 반대 스크립트 N-1단어(짧은 span)로는 재감지 미발동."""
    proc = _make_processor(locked_lang="en")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3)]
    assert _SCRIPT_ANCHOR_N_WORDS == 3  # 테스트 전제(기본값) 확인
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()


def test_streak_n_words_triggers_redetect():
    """(2) 반대 스크립트 연속 N단어(기본 3) 도달 시 재감지 호출(2.0s/0.90)."""
    proc = _make_processor(locked_lang="en")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    proc._apply_script_anchor_redetect(tokens)
    proc.model.detect_current_language.assert_called_once_with(window_secs=2.0, min_prob=0.90)


def test_streak_t_secs_triggers_redetect():
    """(3) N 미달이어도 반전 지속 T초(기본 1.0) 경과 시 재감지 호출."""
    proc = _make_processor(locked_lang="en")
    assert _SCRIPT_ANCHOR_T_SECS == 1.0  # 테스트 전제(기본값) 확인
    tokens = [_tok(" 안녕", 0.0, 0.5), _tok(" 하세요", 1.0, 1.1)]  # span 1.1s >= 1.0s
    proc._apply_script_anchor_redetect(tokens)
    proc.model.detect_current_language.assert_called_once_with(window_secs=2.0, min_prob=0.90)


def test_same_script_token_resets_streak():
    """(4) 같은 스크립트 토큰이 섞이면 streak 리셋 — "I think 그건"류 정상 삽입 오탐 방어."""
    proc = _make_processor(locked_lang="en")
    tokens = [
        _tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3),
        _tok(" and", 0.4, 0.5),  # 잠긴 언어(en) 스크립트 → 리셋
        _tok(" 반갑", 0.6, 0.7),
    ]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()
    assert len(proc._script_anchor_streak) == 1  # 마지막 "반갑"만 잔존


def test_neutral_tokens_skipped_not_reset():
    """(5) 숫자·기호만인 토큰은 스크립트 중립 — streak에 넣지도, 리셋하지도 않음."""
    proc = _make_processor(locked_lang="en")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 123", 0.2, 0.3), _tok(" 하세요", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()
    assert len(proc._script_anchor_streak) == 2  # 중립 토큰 제외 2단어


def test_cross_batch_accumulation():
    """(6) streak은 배치 경계를 넘어 누적된다 (Exp-172: 3~4단어 · 2배치)."""
    proc = _make_processor(locked_lang="en")
    proc._apply_script_anchor_redetect([_tok(" 안녕", 0.0, 0.1)])
    proc.model.detect_current_language.assert_not_called()
    proc._apply_script_anchor_redetect([_tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)])
    proc.model.detect_current_language.assert_called_once()


# ── 재감지 결과 처리 ─────────────────────────────────────────────────────────

def test_redetect_none_keeps_streak_no_apply():
    """(7) detect_current_language=None(불확신) → 미적용 + streak 유지 + 배치 통과."""
    proc = _make_processor(locked_lang="en")
    proc.model.detect_current_language = MagicMock(return_value=None)
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model._apply_detected_language.assert_not_called()
    assert len(proc._script_anchor_streak) == 3


def test_same_lang_reconfirm_noop_resets_streak():
    """(8) 재감지 결과 = 잠긴 언어 → no-op(Exp-169: _apply_detected_language 호출 금지) + streak 리셋."""
    proc = _make_processor(locked_lang="en")
    proc.model.detect_current_language = MagicMock(return_value="en")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model._apply_detected_language.assert_not_called()
    assert proc._script_anchor_streak == []


def test_switch_confirmed_applies_and_drops_batch():
    """(9) 다른 언어 확신 → _apply_detected_language(new_lang) + 배치 드롭 + streak 리셋.

    마커 arm(pending_language_switch)·2.5s 트림·retract arm·retract_floor 계산은
    _apply_detected_language(실코드, Exp-174 이후 메커니즘)에 위임한다 — 여기서는
    위임 호출과 배치 드롭만 검증한다.
    """
    proc = _make_processor(locked_lang="en")
    proc.model.detect_current_language = MagicMock(return_value="ko")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == []
    proc.model._apply_detected_language.assert_called_once_with("ko")
    assert proc._script_anchor_streak == []


def test_symmetric_ko_locked_en_switch():
    """(10) ko↔en 대칭: ko 잠금 중 라틴 streak → en 전환도 동일 동작."""
    proc = _make_processor(locked_lang="ko")
    proc.model.detect_current_language = MagicMock(return_value="en")
    tokens = [_tok(" thank", 0.0, 0.1), _tok(" you", 0.2, 0.3), _tok(" all", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == []
    proc.model._apply_detected_language.assert_called_once_with("en")
    assert proc._script_anchor_streak == []


# ── 게이트 비활성 조건 ───────────────────────────────────────────────────────

def test_kill_switch_disables_gate(monkeypatch):
    """(11) 무력화 플래그(SCRIPT_ANCHOR_REDETECT_ENABLED=False) 시 완전 무동작."""
    monkeypatch.setattr(backend_module, "SCRIPT_ANCHOR_REDETECT_ENABLED", False)
    proc = _make_processor(locked_lang="en")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()
    assert proc._script_anchor_streak == []


def test_no_locked_language_no_trigger():
    """(12) detected_language=None(최초 감지 전)이면 게이트 미동작."""
    proc = _make_processor(locked_lang=None)
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()


def test_fixed_language_no_trigger():
    """(13) language=auto가 아니면(고정 언어) 게이트 미동작."""
    proc = _make_processor(locked_lang="en", language="en")
    tokens = [_tok(" 안녕", 0.0, 0.1), _tok(" 하세요", 0.2, 0.3), _tok(" 여러분", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()


# ── streak 리셋 합류 지점 ────────────────────────────────────────────────────

def test_long_silence_resets_streak():
    """(14) 긴침묵 리셋 블록에서 streak 리셋 (기존 _script_mismatch_streak 리셋과 동일 위치)."""
    proc = _make_processor(locked_lang="en")
    proc._script_anchor_streak = ["안녕", "하세요"]
    proc._script_anchor_streak_start = 1.0
    proc._script_anchor_streak_end = 1.5
    proc.end_silence(silence_duration=MIN_DURATION_REAL_SILENCE, offset=0.0)
    assert proc._script_anchor_streak == []
    assert proc._script_anchor_streak_start is None


def test_new_speaker_resets_streak():
    """(15) 화자전환(new_speaker)에서 streak 리셋."""
    proc = _make_processor(locked_lang="en")
    proc.end = 13.0
    proc.model.global_time_offset = 10.0
    proc._script_anchor_streak = ["안녕", "하세요"]
    proc._script_anchor_streak_start = 11.0
    proc._script_anchor_streak_end = 11.5
    proc.new_speaker(ChangeSpeaker(speaker=1, start=12))
    assert proc._script_anchor_streak == []
    assert proc._script_anchor_streak_start is None


def test_script_mismatch_gate_fire_resets_streak():
    """(16) ScriptMismatchFilter 발동 직후 streak 리셋 합류 (process_iter 경유)."""
    proc = _make_processor(locked_lang="ko")
    proc._script_anchor_streak = ["와"]
    proc._script_anchor_streak_start = 0.0
    proc._script_anchor_streak_end = 0.1
    # ko 잠금 + 순수 라틴 반복(6단어, TTR=2/6≤0.6) → ScriptMismatchFilter 발동
    storm = [_tok(" thank", 0.0, 0.1), _tok(" you", 0.1, 0.2)] * 3
    proc.model.infer = MagicMock(return_value=storm)
    result, _ = proc.process_iter()
    assert result == []
    assert proc._script_anchor_streak == []


def test_anchor_repeat_gate_fire_resets_streak():
    """(17) AnchorRepeatFilter 발동 직후 streak 리셋 합류 — 드롭된(미방출) storm 단어가
    streak에 남아 다음 배치에서 오발동하지 않도록.

    storm 텍스트는 TTR>0.6(ScriptMismatchFilter 통과 — 16단어 중 고유 10 = 0.625)이면서
    2-gram 앵커 "thank you"가 gap≤5로 4회 반복(AnchorRepeatFilter 발동)하도록 구성.
    재감지는 불확신(None)이라 본 게이트는 미적용 상태에서 AnchorRepeatFilter까지 흘러간다.
    """
    proc = _make_processor(locked_lang="ko")
    proc.model.detect_current_language = MagicMock(return_value=None)
    words = (" thank you very much thank you for coming thank you all today"
             " thank you everyone here").split()
    storm = [_tok(" " + w, i * 0.1, i * 0.1 + 0.05) for i, w in enumerate(words)]
    proc.model.infer = MagicMock(return_value=storm)
    result, _ = proc.process_iter()
    assert result == []
    assert proc._script_anchor_streak == []


# ── 약어/철자낭독 가드 (GOAL_SCRIPTANCHOR_ACRONYM_GUARD) ─────────────────────
#
# 한국어 낭독 중 영문 약어 철자 낭독("GP·GOP") 방출이 재감지 streak을 오염시켜
# ko→en 오전환 + 전환 트림으로 직전 오디오 비가역 폐기를 일으키는 사각지대(Exp-179
# 규명)를 메우는 가드. 낱글자 철자낭독·ALL-CAPS 약어 덩어리라는 표기 속성만으로
# 라틴 토큰을 증거 집계에서 중립 스킵한다(소문자 자연 영단어·두문자 대문자는
# 기존대로 산입 — Exp-175 커버리지 보존).

def test_acronym_helper_single_letter():
    """(18) 낱글자(길이<=_ACRONYM_MAX_SINGLE_LEN)는 구두점 유무와 무관하게 약어로 판정."""
    assert _ACRONYM_MAX_SINGLE_LEN == 2  # 테스트 전제(초안값) 확인
    assert _is_acronym_like_latin("G") is True
    assert _is_acronym_like_latin("P") is True
    assert _is_acronym_like_latin("A.") is True  # 구두점 제거 후 길이 1


def test_acronym_helper_allcaps_chunk():
    """(19) 전부대문자 && 길이<=_ACRONYM_MAX_ALLCAPS_LEN 은 약어 덩어리로 판정."""
    assert _ACRONYM_MAX_ALLCAPS_LEN == 6  # 테스트 전제(초안값) 확인
    assert _is_acronym_like_latin("GOP") is True
    assert _is_acronym_like_latin("GPGOP") is True
    assert _is_acronym_like_latin("NATO") is True
    assert _is_acronym_like_latin("AI") is True


def test_acronym_helper_natural_word_not_acronym():
    """(20) 길이>=3인 소문자 자연 단어·두문자 대문자 단어는 약어 판정에서 제외."""
    assert _is_acronym_like_latin("There") is False
    assert _is_acronym_like_latin("goes") is False
    assert _is_acronym_like_latin("work") is False
    assert _is_acronym_like_latin("Thank") is False


def test_acronym_helper_short_natural_word_known_limitation():
    """(20b) 알려진 한계: 길이<=2인 자연 단어("is"/"to"/"of")도 규칙①(길이 기준)에
    걸려 약어로 판정된다 — 스펙(GOAL 문서 §2 P1)이 낱글자 판정을 케이스 구분 없이
    길이만으로 정의하기 때문(초안값). 결과적으로 streak 산입에서 중립 스킵되지만
    리셋은 하지 않으므로 실사용 영향은 "카운트 지연"에 그친다(§4 게이트 4c 오스킵
    감사 대상 — Stage 1/3 ytn2 로그로 실측 검증)."""
    assert _is_acronym_like_latin("is") is True
    assert _is_acronym_like_latin("to") is True
    assert _is_acronym_like_latin("of") is True


def test_acronym_helper_allcaps_too_long_not_acronym():
    """(21) 전부대문자여도 길이가 상한을 넘으면(일반 ALL-CAPS 강조 단어 등) 약어 아님."""
    assert _is_acronym_like_latin("ABCDEFG") is False  # 7자 > 6


def test_acronym_helper_no_letters_not_acronym():
    """(22) 알파벳이 전혀 없으면(숫자만) False — 별도로 중립 스킵되는 경로와 구분."""
    assert _is_acronym_like_latin("123") is False


def test_single_letter_spellout_skipped_no_trigger():
    """(23) ko 잠금 중 낱글자 철자낭독(G/P/G) 연속 방출 — streak 미산입·재감지 미호출."""
    proc = _make_processor(locked_lang="ko")
    tokens = [_tok(" G", 0.0, 0.1), _tok(" P", 0.2, 0.3), _tok(" G", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()
    assert proc._script_anchor_streak == []


def test_allcaps_acronym_chunk_skipped_no_trigger():
    """(24) ko 잠금 중 ALL-CAPS 약어 덩어리(GOP/GPGOP/AI) 연속 방출 — streak 미산입."""
    proc = _make_processor(locked_lang="ko")
    tokens = [_tok(" GOP", 0.0, 0.1), _tok(" GPGOP", 0.2, 0.3), _tok(" AI", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()
    assert proc._script_anchor_streak == []


def test_natural_english_words_still_trigger_with_guard_on():
    """(25) 가드 ON이어도 길이>=3 자연 영단어 3연속은 기존대로 재감지 발동(Exp-175 커버리지 보존)."""
    proc = _make_processor(locked_lang="ko")
    proc.model.detect_current_language = MagicMock(return_value="en")
    tokens = [_tok(" There", 0.0, 0.1), _tok(" goes", 0.2, 0.3), _tok(" more", 0.4, 0.5)]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == []
    proc.model.detect_current_language.assert_called_once_with(window_secs=2.0, min_prob=0.90)
    proc.model._apply_detected_language.assert_called_once_with("en")


def test_acronym_mixed_with_natural_words_only_natural_counted():
    """(26) 약어+자연단어 혼합 배치 — 약어는 스킵되고 자연단어만 카운트되어 발동."""
    proc = _make_processor(locked_lang="ko")
    tokens = [
        _tok(" GOP", 0.0, 0.1),   # 스킵(약어) — 카운트 안 됨
        _tok(" There", 0.2, 0.3),  # 1
        _tok(" goes", 0.4, 0.5),   # 2
        _tok(" more", 0.6, 0.7),   # 3 → 발동
    ]
    proc._apply_script_anchor_redetect(tokens)
    proc.model.detect_current_language.assert_called_once()
    assert len(proc._script_anchor_streak) == 3  # 약어 토큰은 streak에 없음


def test_acronym_skip_does_not_reset_existing_streak():
    """(27) 약어 토큰은 중립 스킵 — 이미 쌓인 자연단어 streak을 리셋하지 않는다."""
    proc = _make_processor(locked_lang="ko")
    proc._apply_script_anchor_redetect([_tok(" There", 0.0, 0.1), _tok(" goes", 0.2, 0.3)])
    proc.model.detect_current_language.assert_not_called()
    assert len(proc._script_anchor_streak) == 2
    # 약어 토큰 삽입 — streak 유지(리셋도 산입도 안 함)
    proc._apply_script_anchor_redetect([_tok(" GOP", 0.4, 0.5)])
    proc.model.detect_current_language.assert_not_called()
    assert len(proc._script_anchor_streak) == 2
    # 세 번째 자연단어로 발동
    proc._apply_script_anchor_redetect([_tok(" more", 0.6, 0.7)])
    proc.model.detect_current_language.assert_called_once()


def test_hangul_word_still_resets_streak_with_acronym_in_between():
    """(28) 약어 스킵과 무관하게 한글(잠긴 스크립트) 단어는 여전히 streak을 리셋한다."""
    proc = _make_processor(locked_lang="ko")
    tokens = [
        _tok(" GOP", 0.0, 0.1),    # 스킵(약어)
        _tok(" There", 0.2, 0.3),  # 1
        _tok(" 그리고", 0.4, 0.5),  # 잠긴 스크립트(ko) → 리셋
    ]
    result = proc._apply_script_anchor_redetect(tokens)
    assert result == tokens
    proc.model.detect_current_language.assert_not_called()
    assert proc._script_anchor_streak == []


def test_acronym_guard_kill_switch_restores_legacy_counting(monkeypatch):
    """(29) SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED=False 시 약어도 기존대로 streak 산입(완전 기존 동작)."""
    monkeypatch.setattr(backend_module, "SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED", False)
    proc = _make_processor(locked_lang="ko")
    tokens = [_tok(" GOP", 0.0, 0.1), _tok(" GPGOP", 0.2, 0.3), _tok(" AI", 0.4, 0.5)]
    proc._apply_script_anchor_redetect(tokens)
    proc.model.detect_current_language.assert_called_once_with(window_secs=2.0, min_prob=0.90)
