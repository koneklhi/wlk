"""P2 — 언어-출력 스크립트 불일치 억제 게이트 단위 테스트.

배경(확정된 근본원인): EN→KO 언어전환 경계 직후 "Thank you"류 영어 필러 환각이
폭주해 KO 문장 전체를 삼킨다. 기존 필터가 전부 무력화되는 이유:
- avg_logprob: 영어 최빈 구문이라 모델이 고신뢰로 생성 → 억제 못함.
- compression_ratio: 필러가 매번 조금씩 변주("very much"/"so much"/"everyone"...)돼
  임계 미달.
- BatchRepeatFilter(backend.py)는 한국어 전용 정규식이라 영어 필러는 진입 자체를 못함.
- CrossBatchFilter는 완전 동일 인접단어만 제거 — 변주 구문은 통과.

P2 게이트: detected_language와 반대 스크립트로만 구성되고 타입-토큰 비율이 붕괴한
(=반복/변주 시그니처) 세그먼트를 드롭한다. 특정 문구("thank you" 등) 하드코딩 없이
구조적 시그니처(스크립트 불일치 + TTR)만 사용(§3.8).

이 테스트는 두 레벨을 검증한다:
1. `_is_script_mismatch_filler` 순수 함수 — 임계값·오탐 방지 로직 자체.
2. `SimulStreamingOnlineProcessor.process_iter` 배선 — 드롭 시 refresh_segment를
   호출하지 않고 기존 언어 재감지 arm 매커니즘(ForeignLang과 동일)만 재사용하는지.
"""

from unittest.mock import MagicMock

from whisperlivekit.simul_whisper.backend import (
    STALL_RECOVER_SEC,
    SimulStreamingOnlineProcessor,
    _is_script_mismatch_filler,
)

# ── 1. 순수 함수 단위 테스트 ────────────────────────────────────────────────────

def test_english_filler_repetition_flagged_when_detected_ko():
    """EXPERIMENTS_LOG 실측 관측 그대로: EN 필러 반복, detected_language='ko' → 억제 대상."""
    text = (
        "Thank you very much. Thank you very much for coming. "
        "Thank you. Thank you very much."
    )
    assert _is_script_mismatch_filler(text, "ko") is True


def test_english_filler_repetition_flagged_when_detected_ko_variant():
    """실측 변주 사례 — "so much"/"everyone" 식으로 조금씩 바뀌는 필러도 잡아야 함."""
    text = (
        "close coordination on this topic Thank you very much. Thank you. "
        "Thank very much, everyone. Thank you"
    )
    assert _is_script_mismatch_filler(text, "ko") is True


def test_korean_filler_repetition_flagged_when_detected_en():
    """대칭 방향(일반화) — 한글 필러 반복이 detected_language='en'일 때도 억제되어야 함."""
    text = "감사합니다 감사합니다 정말 감사합니다 여러분 감사합니다 감사합니다"
    assert _is_script_mismatch_filler(text, "en") is True


def test_normal_full_english_sentence_not_flagged_when_detected_ko():
    """가장 중요한 오탐 방지 케이스 — 반복 없는 정상 코드스위칭 영어 문장은 걸러지면 안 됨."""
    text = (
        "Minister Jung and I reviewed progress on the operational control "
        "transition and reached an agreement on the results of the evaluation "
        "of the initial operational capability."
    )
    assert _is_script_mismatch_filler(text, "ko") is False


def test_normal_full_korean_sentence_not_flagged_when_detected_en():
    """대칭 오탐 방지 — 반복 없는 정상 한국어 문장은 detected_language='en'이어도 통과."""
    text = "정경두 국방장관과 저는 전작권 전환과 관련한 진척을 검토했습니다"
    assert _is_script_mismatch_filler(text, "en") is False


def test_short_english_ack_not_flagged():
    """짧은 정상 발화(단어 수 부족)는 통계적으로 판단 불가 → 통과(오탐 방지)."""
    assert _is_script_mismatch_filler("Thank you very much.", "ko") is False


def test_matching_script_not_flagged():
    """detected_language와 스크립트가 애초에 일치하면(한글 있는 한국어 세그먼트) 검사 대상 아님."""
    text = "감사합니다 감사합니다 감사합니다 감사합니다 감사합니다"
    assert _is_script_mismatch_filler(text, "ko") is False


def test_mixed_script_not_flagged():
    """코드스위칭 자연 발화(양쪽 스크립트 혼재)는 '전체가 반대 스크립트' 조건 자체를 충족 못해 통과."""
    text = "우리는 operational control transition 관련 진척을 검토했습니다"
    assert _is_script_mismatch_filler(text, "ko") is False


def test_unsupported_language_not_flagged():
    """ko/en 이외 언어 값은 게이트 대상이 아님(§3.2 두 언어 고정과 별개의 방어적 no-op)."""
    text = "Thank you very much. Thank you very much. Thank you very much."
    assert _is_script_mismatch_filler(text, "fr") is False
    assert _is_script_mismatch_filler(text, None) is False


# ── 2. process_iter 배선 테스트 ─────────────────────────────────────────────────
#
# 실측(ytn2 스크리닝, .omc/server_logs) 확인 결과 실시간 배치는 보통 1~3 토큰 단위로
# 방출된다(TokenTrace 로그) — "Thank you very much." 같은 완결 문장이 통째로 한
# infer() 호출에서 나오는 경우는 드물다. 순수 함수 `_is_script_mismatch_filler`를
# 배치 1개에만 적용하면 MIN_WORDS=6 문턱을 거의 못 넘어 사실상 무력화된다. 그래서
# process_iter는 배치를 건너 누적되는 streak(`_script_mismatch_streak`)에 대해
# 판정한다 — 아래 테스트는 실측 그대로 작은 배치를 여러 번 흘려보내 cross-batch
# 누적이 실제로 동작하는지 검증한다.

class _FakeToken:
    """process_iter가 요구하는 최소 토큰 인터페이스: .text / .detected_language."""

    def __init__(self, text, detected_language="en"):
        self.text = text
        self.detected_language = detected_language


def _make_processor(detected_language="ko", lang_before_reset=None):
    proc = SimulStreamingOnlineProcessor.__new__(SimulStreamingOnlineProcessor)
    proc.asr = MagicMock()
    proc.asr.use_full_mlx = False
    proc.buffer = []
    proc._last_emitted_word = None
    proc._last_emit_end = 0.0
    proc.end = 1.0  # end - _last_emit_end = 1.0 < STALL_RECOVER_SEC → stall watchdog 미발동
    proc._consecutive_char_repeat = 0
    proc._short_silence_check_at = 0.0
    proc._recent_emitted_words = []
    proc._script_mismatch_streak = []
    proc._anchor_repeat_window = []

    model = MagicMock()
    model.cfg.language = "auto"
    model.state = MagicMock()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = lang_before_reset
    model.state.first_timestamp = 1.0
    model.state.pending_language_switch = None
    proc.model = model
    return proc


def _chunked(words, size):
    return [words[i:i + size] for i in range(0, len(words), size)]


def _run_batches(proc, word_batches, detected_language):
    """word_batches의 각 배치를 순서대로 별도 infer() 호출 결과로 흘려보내며
    process_iter를 반복 호출. (committed, dropped_call_index) 튜플 리스트 반환."""
    proc.model.infer = MagicMock(
        side_effect=[
            [_FakeToken(w, detected_language=detected_language) for w in batch]
            for batch in word_batches
        ]
    )
    results = []
    for _ in word_batches:
        committed, _ = proc.process_iter(is_last=False)
        results.append(committed)
    return results


# 실측 필러(EXPERIMENTS_LOG 인용) — 2단어씩 실측 배치 크기로 청킹.
_FILLER_WORDS = [
    "Thank", " you", " very", " much.", " Thank", " you", " very", " much",
    " for", " coming.", " Thank", " you.", " Thank", " you", " very", " much.",
]

_NORMAL_SENTENCE_WORDS = [
    "Minister", " Jung", " and", " I", " reviewed", " progress", " on",
    " the", " operational", " control", " transition", " and", " reached",
    " an", " agreement", " on", " the", " results.",
]


def test_stall_watchdog_not_triggered_in_fixture():
    """(0) 픽스처가 stall watchdog을 발동하지 않는지 사전 확인."""
    proc = _make_processor()
    assert proc.end - proc._last_emit_end < STALL_RECOVER_SEC


def test_process_iter_drops_filler_and_arms_relanguage_detection():
    """(a) EN 필러가 실측처럼 2단어씩 여러 배치로 흘러들어와도, 반복 시그니처가
    쌓이면 해당 배치에서 committed=[] + 재감지 arm(기존 매커니즘 재사용)."""
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()  # 호출되면 안 됨(Exp-163 회귀 방지)

    batches = _chunked(_FILLER_WORDS, 2)
    results = _run_batches(proc, batches, detected_language="en")

    # 초반 배치는 streak이 MIN_WORDS 미만이라 그대로 통과, 이후 어느 배치에서
    # 반드시 드롭(빈 리스트)이 발생해야 한다 — 그렇지 않으면 게이트가 cross-batch
    # 환경에서 사실상 무력화된 것.
    assert any(r == [] for r in results), "cross-batch streak이 끝내 한 번도 드롭을 발동하지 않음"
    assert proc.model.state.detected_language is None
    assert proc.model.state.first_timestamp is None
    assert proc.model.state.eager_lang_detect is True
    assert proc.model.state.lang_before_reset == "ko"
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_symmetric_korean_filler_dropped_when_detected_en():
    """(b) 대칭 방향 — 한글 필러가 2단어씩 배치로 흘러들어와도 동일하게 억제·arm."""
    words = [
        "감사합니다", " 감사합니다", " 정말", " 감사합니다", " 여러분",
        " 감사합니다", " 감사합니다", " 정말로", " 감사합니다", " 감사합니다",
    ]
    proc = _make_processor(detected_language="en", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(words, 2)
    results = _run_batches(proc, batches, detected_language="ko")

    assert any(r == [] for r in results), "cross-batch streak이 끝내 한 번도 드롭을 발동하지 않음"
    assert proc.model.state.detected_language is None
    assert proc.model.state.lang_before_reset == "en"
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_preserves_normal_codeswitch_sentence():
    """(c, 가장 중요) 반복 없는 정상 전체-영어 문장은 2단어씩 여러 배치로 나뉘어도,
    detected_language='ko' 상태에서 단 한 배치도 드롭되면 안 된다."""
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(_NORMAL_SENTENCE_WORDS, 2)
    results = _run_batches(proc, batches, detected_language="en")

    assert all(len(r) == len(batch) for r, batch in zip(results, batches)), (
        "정상 코드스위칭 문장의 일부 배치가 오탐으로 드롭됨"
    )
    flat_committed = [t.text for r in results for t in r]
    assert flat_committed == _NORMAL_SENTENCE_WORDS
    # 정상 방출이므로 언어 상태를 건드리면 안 됨
    assert proc.model.state.detected_language == "ko"
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_normal_korean_flow_unaffected():
    """(d) 기존 정상 한국어 흐름 회귀 없음 — 스크립트 일치 세그먼트는 게이트 대상이 아님."""
    words = ["정경두", " 국방장관과", " 저는", " 전작권", " 전환과", " 관련한", " 진척을", " 검토했습니다"]
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(words, 2)
    results = _run_batches(proc, batches, detected_language="ko")

    assert all(len(r) == len(batch) for r, batch in zip(results, batches))
    assert proc.model.state.detected_language == "ko"
    proc.model.refresh_segment.assert_not_called()
