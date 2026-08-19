"""CASE3 — script-agnostic 앵커 반복(필러 storm) 게이트 단위 테스트.

배경(확정된 근본원인, docs/GOAL_CASE_SENTENCE_QUALITY.md Req-3 사이클1 오프라인 oracle
디코드): 경계 리프레시 직후 <1s 컨텍스트기아 상태에서 발생하는 스트리밍 세금이 필러
storm(bong1 "thank you"×3, ytn2 "김정은"×4)을 유발한다. 기존 `_is_script_mismatch_filler`
(P2 게이트, backend.py)는 "detected_language와 반대 스크립트 + TTR 붕괴" 전제라 다음을
못 잡는다:
  - 같은 스크립트 안에서 발생하는 storm(예: seg_lang=en으로 정확히 감지된 채로 진행되는
    영어 필러 반복 — 스크립트 불일치 자체가 성립하지 않음).
  - "앵커 토큰 1개는 정확반복, 주변부(접미부)는 변주"되는 구조(ytn2 "김정은"+접미부 변주 —
    전체 TTR=0.809로 P2 게이트의 TTR 문턱(≤0.6)을 통과해버림).

`_find_anchor_repeat_storm`/`_update_anchor_repeat_window`(backend.py)는 스크립트·언어
무관하게 "최근 방출 단어 윈도우 안에서 앵커(1~2gram)가 gap-tolerant하게 비정상적으로
몰려 반복되는가"만 판정한다(§3.8: 특정 문구·언어 하드코딩 금지 — 구조만 본다).

CASE3-B(`_find_growing_repeat_storm`) — 위 게이트도 못 잡는 **성장형 프리픽스 루프**
(재시작마다 직전보다 한두 단어 더 나아가고 또 처음부터 다시 시작)를 맡는 독립 추가
경로. 실측 근거·임계값 근거는 backend.py 상수 주석 참조. 이 파일 §3에서 검증한다.

이 테스트는 세 레벨을 검증한다:
1. `_find_anchor_repeat_storm` 순수 함수 — 오탐 방지 케이스를 최우선으로 검증.
2. `SimulStreamingOnlineProcessor.process_iter` 배선 — 드롭 시 refresh_segment를
   호출하지 않고 기존 언어 재감지 arm 매커니즘만 재사용하는지.
3. `_find_growing_repeat_storm` 순수 함수 + 배선 — 성장형 루프 검출과, §1의 오탐
   방지 시나리오가 새 경로에서도 그대로 통과하는지.
"""

import logging
from unittest.mock import MagicMock

from whisperlivekit.simul_whisper.backend import (
    STALL_RECOVER_SEC,
    SimulStreamingOnlineProcessor,
    _find_anchor_repeat_storm,
    _find_growing_repeat_storm,
)

# ── 1. 순수 함수 단위 테스트 ────────────────────────────────────────────────────
#
# ── 1a. 오탐 방지(가장 중요) ────────────────────────────────────────────────────


def test_scattered_mention_across_document_not_flagged():
    """(a) 같은 고유명사가 문서 전체에 흩어져(간격 ~8단어) 재등장하는 경우는 storm이
    아니다 — gap(8단어 안팎)이 MAX_GAP(3)을 초과해 클러스터가 형성되지 않아야 한다."""
    filler_block = [f"단어{i}" for i in range(8)]
    words = []
    for _ in range(4):
        words.append("북한")
        words.extend(filler_block)
    # words: 북한 단어0..7 북한 단어0..7 북한 단어0..7 북한 단어0..7 (총 36단어, 윈도우 40 이내)
    assert _find_anchor_repeat_storm(words) is False


def test_normal_emphasis_repetition_three_times_not_flagged():
    """(b) 정상 강조 반복("네, 네, 알겠습니다"류) — 3회 이하는 드롭되면 안 됨."""
    words = ["네", "네", "네", "알겠습니다", "여러분"]
    assert _find_anchor_repeat_storm(words) is False


def test_normal_emphasis_repetition_two_times_not_flagged():
    words = ["네", "네", "알겠습니다"]
    assert _find_anchor_repeat_storm(words) is False


def test_normal_codeswitch_sentence_no_repeats_not_flagged():
    """(c) 반복이 없는 정상 코드스위칭 발화는 당연히 통과."""
    words = (
        "우리는 operational control transition 관련 진척을 검토했습니다 "
        "그리고 initial operational capability 평가 결과에 합의했습니다"
    ).split()
    assert _find_anchor_repeat_storm(words) is False


def test_normal_full_sentence_no_repeats_not_flagged():
    words = (
        "Minister Jung and I reviewed progress on the operational control "
        "transition and reached an agreement on the results of the evaluation"
    ).split()
    assert _find_anchor_repeat_storm(words) is False


# ── 1b. 실제 storm 재현(구조 기반, 문구 무관) ────────────────────────────────────


def test_english_filler_storm_with_actual_observed_words_flagged():
    """실측 관측 그대로("thank you"+변주 접미부) — bigram 앵커 storm."""
    words = (
        "close coordination on this topic thank you very much thank you "
        "thank very much everyone thank you"
    ).split()
    assert _find_anchor_repeat_storm(words) is True


def test_korean_anchor_storm_with_actual_observed_words_flagged():
    """실측 관측 그대로("김정은"+변주 접미부) — unigram 앵커 storm.

    P2 게이트(_is_script_mismatch_filler)는 이 구조를 못 잡는다: 같은 스크립트(ko/ko)
    이고 전체 TTR이 접미부 변주 덕에 붕괴하지 않기 때문(실측 TTR=0.809 > 0.6 문턱).
    """
    words = (
        "김정은 기자입니다 김정은 기자의 보도입니다 김정은 기자가 보도합니다 김정은 기자였습니다"
    ).split()
    assert _find_anchor_repeat_storm(words) is True


def test_storm_structure_generalizes_to_arbitrary_vocabulary():
    """구조 일반화 검증(§3.8) — 실측 문구("김정은"/"thank you")를 전혀 다른 임의의
    단어로 바꿔도 "앵커 정확반복 + 변주 접미부" 구조만 있으면 동일하게 detected돼야
    한다. 로직이 특정 문구에 의존한다면 이 테스트만 실패할 것."""
    words = (
        "체리안 소식통입니다 체리안 소식의 전달입니다 체리안 소식통이 전합니다 체리안 소식이었습니다"
    ).split()
    assert _find_anchor_repeat_storm(words) is True


def test_storm_structure_generalizes_english_arbitrary_vocabulary():
    """영어 어휘로도 구조만 맞으면 동일 검출(anchor="wonderful indeed")."""
    words = (
        "we discussed many topics wonderful indeed really wonderful indeed "
        "so wonderful indeed absolutely wonderful indeed"
    ).split()
    assert _find_anchor_repeat_storm(words) is True


# ── 2. process_iter 배선 테스트 ─────────────────────────────────────────────────


class _FakeToken:
    """process_iter가 요구하는 최소 토큰 인터페이스: .text / .detected_language
    (+ 스크립트-앵커 재감지 게이트가 읽는 .start/.end — span=0이라 T초 문턱 미발동)."""

    def __init__(self, text, detected_language="en", start=0.0, end=0.0):
        self.text = text
        self.detected_language = detected_language
        self.start = start
        self.end = end


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
    proc._script_anchor_streak = []
    proc._script_anchor_streak_start = None
    proc._script_anchor_streak_end = None

    model = MagicMock()
    model.cfg.language = "auto"
    model.state = MagicMock()
    model.state.detected_language = detected_language
    model.state.lang_before_reset = lang_before_reset
    model.state.first_timestamp = 1.0
    model.state.pending_language_switch = None
    # 스크립트-앵커 재감지 게이트는 기본 불확신(None)으로 스텁 — 이 파일은
    # AnchorRepeatFilter 자체를 검증하므로 재감지 전환이 개입하지 않게 한다.
    model.detect_current_language = MagicMock(return_value=None)
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


# 실측 필러(같은 스크립트, seg_lang=en으로 정확 감지된 채 진행 — P2 게이트가 원천적으로
# 대상 삼지 못하는 케이스) — 2단어씩 실측 배치 크기로 청킹.
_FILLER_WORDS = [
    "Thank", " you", " very", " much.", " Thank", " you", " very", " much",
    " for", " coming.", " Thank", " you.", " Thank", " you", " very", " much.",
]

_NORMAL_SENTENCE_WORDS = [
    "Minister", " Jung", " and", " I", " reviewed", " progress", " on",
    " the", " operational", " control", " transition", " and", " reached",
    " an", " agreement", " on", " the", " results.",
]

# 대칭 구조 검증용 — "김정은"류 구조를 임의 단어("체리안")로 치환.
_ANCHOR_STORM_WORDS_KO = [
    "체리안", " 소식통입니다.", " 체리안", " 소식의", " 전달입니다.",
    " 체리안", " 소식통이", " 전합니다.", " 체리안", " 소식이었습니다.",
]

_SCATTERED_MENTION_WORDS_KO = [
    "북한", " 관련", " 소식을", " 전해드립니다", " 오늘", " 아침", " 회의에서",
    " 논의된", " 내용은", " 다음과", " 같습니다", " 첫째", " 경제", " 협력",
    " 방안입니다", " 북한", " 측은", " 이에", " 대해", " 긍정적인", " 반응을",
    " 보였습니다", " 둘째", " 안보", " 문제도", " 논의됐습니다", " 북한",
    " 대표단은", " 신중한", " 입장을", " 유지했습니다", " 마지막으로", " 북한",
    " 경제", " 협력이", " 확대될", " 전망입니다",
]


def test_stall_watchdog_not_triggered_in_fixture():
    """(0) 픽스처가 stall watchdog을 발동하지 않는지 사전 확인."""
    proc = _make_processor()
    assert proc.end - proc._last_emit_end < STALL_RECOVER_SEC


def test_process_iter_drops_anchor_storm_without_touching_language_state():
    """(a) EN 필러가 실측처럼 2단어씩 여러 배치로 흘러들어와도, seg_lang=en으로
    "정확히" 감지된 채(=P2 스크립트 불일치 전제 자체가 성립 안 함) 진행되더라도,
    앵커 반복 밀도가 쌓이면 해당 배치에서 committed=[].

    사이클2 실측 회귀(bong1 WER 24.5%→113.3% catastrophic) 수정 반영 — 언어 재감지
    arm(detected_language=None 등)을 하지 않는다. 원인: 이 게이트는 언어전환과 무관하게
    같은 언어 중간발화에서도 발동할 수 있는데(이 테스트처럼 seg_lang=en 그대로), 재감지를
    arm하면 `_apply_detected_language`가 is_switch=False라도 무조건 컨텍스트를 초기화해
    (align_att_base.py `init_tokens()`/`init_context()`) 컨텍스트기아 재환각을 게이트
    스스로 유발하는 자기강화 루프가 됐다. 드롭만 하고 언어 상태는 그대로 둬야 한다."""
    proc = _make_processor(detected_language="en", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()  # 호출되면 안 됨(Exp-163 회귀 방지)

    batches = _chunked(_FILLER_WORDS, 2)
    results = _run_batches(proc, batches, detected_language="en")

    assert any(r == [] for r in results), "cross-batch 윈도우가 끝내 한 번도 드롭을 발동하지 않음"
    # 언어/컨텍스트 상태 무변경 확인(사이클2 회귀 수정 핵심) — 재감지 arm이 컨텍스트를
    # 반복 초기화해 storm을 스스로 재유발하는 것을 방지.
    assert proc.model.state.detected_language == "en"
    assert proc.model.state.first_timestamp == 1.0
    assert proc.model.state.lang_before_reset is None
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_drops_same_script_korean_anchor_storm():
    """(b) 같은 스크립트(ko/ko) storm — P2 게이트가 원천적으로 못 잡는 케이스를
    이 게이트가 잡아야 한다. 드롭 시에도 언어 상태는 그대로(사이클2 회귀 수정)."""
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(_ANCHOR_STORM_WORDS_KO, 2)
    results = _run_batches(proc, batches, detected_language="ko")

    assert any(r == [] for r in results), "cross-batch 윈도우가 끝내 한 번도 드롭을 발동하지 않음"
    assert proc.model.state.detected_language == "ko"
    assert proc.model.state.lang_before_reset is None
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_preserves_normal_codeswitch_sentence():
    """(c, 가장 중요) 반복 없는 정상 전체-영어 문장은 2단어씩 여러 배치로 나뉘어도,
    단 한 배치도 드롭되면 안 된다.

    스크립트-앵커 재감지 게이트(test_script_anchor_redetect.py) 도입 후 이 시나리오는
    지속 반전으로 재감지 대상이 된다 — 재감지가 en을 "확신"하면 전환+배치 드롭(재디코딩
    복구)이 새 정상 동작이므로, 이 테스트는 재감지를 불확신(None)으로 스텁해 본래
    목적(AnchorRepeatFilter의 정상 문장 오탐 방지)만 검증한다.
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()
    proc.model.detect_current_language = MagicMock(return_value=None)

    batches = _chunked(_NORMAL_SENTENCE_WORDS, 2)
    results = _run_batches(proc, batches, detected_language="en")

    assert all(len(r) == len(batch) for r, batch in zip(results, batches)), (
        "정상 코드스위칭 문장의 일부 배치가 오탐으로 드롭됨"
    )
    flat_committed = [t.text for r in results for t in r]
    assert flat_committed == _NORMAL_SENTENCE_WORDS
    assert proc.model.state.detected_language == "ko"
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_scattered_mention_not_dropped():
    """(d, 가장 중요) 문서 전반에 흩어진 재등장(간격 8단어 안팎)은 배치로 나뉘어
    흘러들어와도 드롭되면 안 된다."""
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(_SCATTERED_MENTION_WORDS_KO, 3)
    results = _run_batches(proc, batches, detected_language="ko")

    assert all(len(r) == len(batch) for r, batch in zip(results, batches)), (
        "문서 전반에 흩어진 재등장이 오탐으로 드롭됨"
    )
    assert proc.model.state.detected_language == "ko"
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_normal_korean_flow_unaffected():
    """(e) 기존 정상 한국어 흐름 회귀 없음 — 반복 없는 문장은 게이트 대상이 아님."""
    words = ["정경두", " 국방장관과", " 저는", " 전작권", " 전환과", " 관련한", " 진척을", " 검토했습니다"]
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(words, 2)
    results = _run_batches(proc, batches, detected_language="ko")

    assert all(len(r) == len(batch) for r, batch in zip(results, batches))
    assert proc.model.state.detected_language == "ko"
    proc.model.refresh_segment.assert_not_called()


# ── 3. CASE3-B 성장형 프리픽스 루프 게이트 ──────────────────────────────────────
#
# 실패 형태(이번 사이클 실측 ytn2/kor3/bong1): 디코더가 같은 구절을 매번 처음부터 다시
# 시작하되 직전보다 한두 단어 더 나아가고 또 재시작한다 — 각 반복이 직전 반복의 연장
# (상위집합)이라 §1 게이트가 겨냥한 "앵커 + 무관한 변주 접미부"와 구조가 다르다.
# 반복이 길어질수록 앵커 간격이 MAX_GAP(5)을 넘겨 클러스터가 형성되지 않고, 끝내는
# 40단어 윈도우 안에 앵커가 MIN_COUNT(4)회도 안 남아 판정 자체가 성립하지 않는다.


def _emitted(text):
    """실제 방출 형태(단어마다 선행 공백)로 변환 — 실측 배치 모양을 흉내낸다."""
    return [f" {w}" for w in text.split()]


# 실측 관측 그대로. 정답(정상 발화)은 마지막 줄 하나뿐이고 그 앞은 전부 재시작 환각이다.
_REGROW_TEXT_KO = (
    "이와 관련해서 "
    "한국군 사성장 한국군 사령관 "
    "이와 관련해서 한국군 사령관으로 조 "
    "이와 관련해서 한국군 사령관으로 조건 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작권 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작권 전환 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작권 전환을 하는 방향으로 상당한 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작권 전환을 하는 방향으로 상당한 진전 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작권 전환을 하는 방향으로 상당한 진전이 "
    "있었음에 합의를 했습니다 "
    "이와 관련해서 한국군 사령관으로 조건을 기초로 한 전작권 전환을 하는 방향으로 상당한 진전이 "
    "있었음에 합의를 했습니다"
)

# kor3형(단일 화자 연속 낭독)에서 관측된 두 번째 실패 형태 — 다른 구절이 1~3단어씩
# 길어지며 8회 재시작. 하나의 예시에 과적합되지 않았음을 확인하기 위한 두 번째 shape.
_REGROW_TEXT_KOR3 = (
    "원거리 타격과 "
    "원거리 타격과 기동전력 "
    "원거리 타격과 기동전력 강화를 위한 "
    "원거리 타격과 기동전력 강화를 위한 기동함대사 "
    "원거리 타격과 기동전력 강화를 위한 기동함대사 이하의 기동전달을 "
    "원거리 타격과 기동전력 강화를 위한 기동함대사 이하의 기동전달을 창설하고 첨단 "
    "원거리 타격과 기동전력 강화를 위한 기동함대사 이하의 기동전달을 창설하고 첨단 함정 장비 "
    "원거리 타격과 기동전력 강화를 위한 기동함대사 이하의 기동전달을 창설하고 첨단 함정 장비 "
    "운용의 전문성 고장과"
)

# 구조 일반화 검증용 — 위 두 실측 문구를 전혀 다른 무의미 어휘로 치환한 같은 shape.
_REGROW_TEXT_NONSENSE = (
    "글로프 바 "
    "글로프 바 튜링 "
    "글로프 바 튜링 미르마 "
    "글로프 바 튜링 미르마 젠토 "
    "글로프 바 튜링 미르마 젠토 카룬 다 "
    "글로프 바 튜링 미르마 젠토 카룬 다 헤스티 "
    "글로프 바 튜링 미르마 젠토 카룬 다 헤스티 올루 반 "
    "글로프 바 튜링 미르마 젠토 카룬 다 헤스티 올루 반 시크로 무"
)

# ko↔en 대칭(§3.8) — 영어에서도 같은 구조면 잡혀야 한다.
_REGROW_TEXT_EN = (
    "we have reached "
    "we have reached an agreement "
    "we have reached an agreement on the "
    "we have reached an agreement on the conditions based "
    "we have reached an agreement on the conditions based transfer of wartime "
    "we have reached an agreement on the conditions based transfer of wartime operational control "
    "we have reached an agreement on the conditions based transfer of wartime operational control "
    "authority today"
)


# ── 3a. 성장형 루프 검출(positive) ──────────────────────────────────────────────


def test_growing_prefix_loop_with_actual_observed_words_flagged():
    """(a) 실측 관측 그대로(ytn2 "이와 관련해서 …" 성장 루프) — 새 경로가 잡아야 한다.

    같은 입력에 대해 기존 경로(`_find_anchor_repeat_storm`)는 **잡지 못한다**는 것도
    함께 고정한다(이 테스트가 메우려는 사각지대의 정의). 실측 트레이스: 앵커
    "이와 관련해서"의 등장 간격이 6,5,5,8,7,9,8,12,13,16으로 성장해 ① 간격이 전부
    MAX_GAP(5) 초과라 클러스터 미형성 → ② 블록이 16단어까지 자라 40단어 윈도우 안에
    앵커가 3회 이하만 남아 MIN_COUNT(4) 미달(윈도우 escape).
    """
    words = _REGROW_TEXT_KO.split()
    assert _find_anchor_repeat_storm(words) is False  # 기존 경로 사각지대(회귀 감시)
    assert _find_growing_repeat_storm(words) is True


def test_growing_prefix_loop_second_real_shape_flagged():
    """(b) kor3형 — 다른 구절이 1~3단어씩 길어지며 8회 재시작하는 두 번째 실패 shape.

    하나의 예시(ytn2)에 과적합되지 않았음을 확인한다.
    """
    words = _REGROW_TEXT_KOR3.split()
    assert _find_anchor_repeat_storm(words) is False
    assert _find_growing_repeat_storm(words) is True


def test_growing_prefix_loop_generalizes_to_arbitrary_vocabulary():
    """(c) 구조 일반화 검증(§3.8) — 실측 문구를 전혀 다른 무의미 어휘로 바꿔도 같은
    구조면 동일하게 검출돼야 한다. 로직이 특정 문구에 의존한다면 이 테스트만 실패한다."""
    words = _REGROW_TEXT_NONSENSE.split()
    assert _find_growing_repeat_storm(words) is True


def test_growing_prefix_loop_generalizes_to_english():
    """(d) ko↔en 대칭 — 영어 어휘로도 구조만 맞으면 동일 검출."""
    words = _REGROW_TEXT_EN.split()
    assert _find_growing_repeat_storm(words) is True


# ── 3b. 오탐 방지(가장 중요) ────────────────────────────────────────────────────


def test_regrow_gate_does_not_flag_scattered_mention():
    """(e, 가장 중요) §1의 "북한" 흩어진 재등장 픽스처를 새 경로도 잡으면 안 된다.

    이 픽스처는 필러가 매 반복 동일해 **완전 주기 반복**(블록 길이 일정 + 블록 내용
    완전 일치)이 된다 — 새 경로가 lcp 성장 조건 없이 "블록 반복"만 봤다면 여기서
    오탐한다(실측 ablation으로 확인). 성장 조건이 이를 걸러낸다.
    """
    filler_block = [f"단어{i}" for i in range(8)]
    words = []
    for _ in range(4):
        words.append("북한")
        words.extend(filler_block)
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_exactly_periodic_block():
    """(f) 완전 주기 반복은 창을 가득 채워도 새 경로 대상이 아니다(의도된 제외).

    성장형 루프는 재시작마다 재현 길이가 **늘어나는** 것이 정의다. 길이가 전혀 변하지
    않는 완전 주기 반복은 열거·후렴 같은 정상 구조와 구조적으로 구분되지 않으므로
    이 경로가 맡지 않는다(짧은 주기 반복은 기존 gap-tolerant 경로 담당).
    """
    block = ["북한"] + [f"단어{i}" for i in range(8)]
    assert _find_growing_repeat_storm(block * 12) is False


def test_regrow_gate_does_not_flag_long_stem_anaphora_korean():
    """(g) 긴 스템 anaphora — 같은 6단어 구절로 문장을 시작하는 수사적 반복.

    각 반복이 스템만 재현하고 뒤는 매번 다른 내용이라 재현 길이(lcp)가 늘지 않는다.
    새 경로가 "블록 반복 + 높은 재현율"만 봤다면 여기서 오탐한다(ablation 확인).
    """
    words = (
        "대한민국 국방부 장관과 미합중국 국방부 장관은 첫째 합의했습니다 "
        "대한민국 국방부 장관과 미합중국 국방부 장관은 둘째 논의했습니다 "
        "대한민국 국방부 장관과 미합중국 국방부 장관은 셋째 검토했습니다"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_long_stem_anaphora_variable_length():
    """(h) 위와 같되 뒤 내용의 길이가 매번 달라 블록 길이가 흔들리는 경우.

    "블록 길이가 일정하지 않으면 성장"이라는 더 느슨한 판정을 썼다면 여기서 오탐한다 —
    실제 채택한 조건은 "재현 길이(lcp)가 증가"라서 통과한다.
    """
    words = (
        "대한민국 국방부 장관과 미합중국 국방부 장관은 첫째 합의했습니다 "
        "대한민국 국방부 장관과 미합중국 국방부 장관은 둘째로 이를 논의했습니다 "
        "대한민국 국방부 장관과 미합중국 국방부 장관은 셋째 검토"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_long_stem_anaphora_english():
    """(i) 영어 긴 스템 anaphora — ko↔en 대칭으로 오탐도 대칭 검증."""
    words = (
        "the secretary of defense and i agreed that we will "
        "the secretary of defense and i agreed that we should "
        "the secretary of defense and i agreed that we must"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_rhetorical_repetition():
    """(j) 문장 서두 2~3단어를 의도적으로 되쓰는 수사적 반복("그리고 이것은 …" ×2)."""
    words = (
        "그리고 이것은 우리가 반드시 지켜야 할 원칙입니다 "
        "그리고 이것은 우리가 반드시 기억해야 할 약속입니다 "
        "앞으로도 계속 이러한 노력을 이어가겠습니다"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_refrain():
    """(k) 후렴(같은 구절이 3회 되풀이되되 사이 내용이 매번 새로운 경우)."""
    words = (
        "함께 가면 길이 됩니다 오늘 우리가 그 길을 엽니다 "
        "함께 가면 길이 됩니다 내일 우리가 그 길을 걷습니다 "
        "함께 가면 길이 됩니다 모두가 그 길에 섭니다"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_enumeration():
    """(l) 열거("첫째 … 둘째 … 셋째 …" 같은 꼬리 구절 반복)."""
    words = (
        "첫째 경제 협력 방안을 논의했습니다 둘째 안보 협력 방안을 논의했습니다 "
        "셋째 문화 교류 방안을 논의했습니다 넷째 인적 교류 방안을 논의했습니다"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_speaker_disfluency():
    """(m) 화자 비유창성(더듬기·구절 재시작)은 결함이 아니다(CLAUDE.md §4 원본 발화 확인
    규칙) — 1~2회 짧은 되풀이는 성장 루프가 아니므로 드롭 대상이 아니다."""
    words = (
        "상당한 상당한 진전이 있었음에 합의를 했습니다 "
        "한국군 사성자 한국군 사령관으로 조건을 기초로 한 전작권 전환을 추진합니다"
    ).split()
    assert _find_growing_repeat_storm(words) is False


def test_regrow_gate_does_not_flag_normal_sentences():
    """(n) §1의 정상 문장 시나리오는 새 경로에서도 전부 통과."""
    codeswitch = (
        "우리는 operational control transition 관련 진척을 검토했습니다 "
        "그리고 initial operational capability 평가 결과에 합의했습니다"
    ).split()
    english = (
        "Minister Jung and I reviewed progress on the operational control "
        "transition and reached an agreement on the results of the evaluation"
    ).split()
    assert _find_growing_repeat_storm(codeswitch) is False
    assert _find_growing_repeat_storm(english) is False
    assert _find_growing_repeat_storm(["네", "네", "네", "알겠습니다", "여러분"]) is False


def test_regrow_gate_ignores_short_input():
    """(o) 입력이 지나치게 짧으면(블록 문턱 미달) 판정 자체가 성립하지 않는다."""
    assert _find_growing_repeat_storm([]) is False
    assert _find_growing_repeat_storm(["가", "나", "다"]) is False


# ── 3c. process_iter 배선 ───────────────────────────────────────────────────────


def test_process_iter_drops_growing_prefix_loop_without_touching_language_state(caplog):
    """(p) 성장형 루프가 배치로 흘러들어오면 해당 배치에서 committed=[]가 되고,
    **언어 재감지를 arm하지 않는다**.

    재감지 arm 금지는 하드 제약이다 — 사이클2 실측에서 이 게이트의 드롭 직후 재감지를
    arm하자 `_apply_detected_language`가 is_switch=False에도 컨텍스트를 매번 초기화해
    컨텍스트기아 재환각을 스스로 유발했고 bong1 WER 24.5%→113.3%로 붕괴했다. 새 경로도
    같은 드롭 지점을 공유하므로 동일하게 검증한다.

    caplog로 `[AnchorRegrowFilter]` 태그를 확인해 **새 경로가** 드롭시켰음을 고정한다
    (기존 경로가 우연히 잡아서 통과하는 위양성 테스트 방지).
    """
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    caplog.set_level(logging.WARNING, logger="whisperlivekit.simul_whisper.backend")
    batches = _chunked(_emitted(_REGROW_TEXT_KO), 2)
    results = _run_batches(proc, batches, detected_language="ko")

    assert any(r == [] for r in results), "성장형 루프가 끝내 한 번도 드롭되지 않음"
    assert "[AnchorRegrowFilter]" in caplog.text, "드롭이 새 경로에서 나오지 않음"
    assert proc.model.state.detected_language == "ko"
    assert proc.model.state.first_timestamp == 1.0
    assert proc.model.state.lang_before_reset is None
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_regrow_gate_rollback_switch(monkeypatch):
    """(q) 롤백 장치 — ANCHOR_REGROW_GATE_ENABLED=False면 새 경로가 완전히 무동작해
    변경 이전 동작으로 돌아간다."""
    monkeypatch.setattr(
        "whisperlivekit.simul_whisper.backend.ANCHOR_REGROW_GATE_ENABLED", False
    )
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(_emitted(_REGROW_TEXT_KO), 2)
    _run_batches(proc, batches, detected_language="ko")

    # 순수 함수 자체는 그대로 True를 반환한다(스위치는 배선 지점에서만 작동).
    assert _find_growing_repeat_storm(_REGROW_TEXT_KO.split()) is True
    proc.model.refresh_segment.assert_not_called()


def test_process_iter_regrow_gate_preserves_scattered_mention():
    """(r, 가장 중요) 새 경로 도입 후에도 §2(d)의 흩어진 재등장 시나리오는 드롭되면 안
    된다 — 배선 레벨에서도 회귀를 고정한다."""
    proc = _make_processor(detected_language="ko", lang_before_reset=None)
    proc.model.refresh_segment = MagicMock()

    batches = _chunked(_SCATTERED_MENTION_WORDS_KO, 3)
    results = _run_batches(proc, batches, detected_language="ko")

    assert all(len(r) == len(batch) for r, batch in zip(results, batches))
    proc.model.refresh_segment.assert_not_called()
