# -*- coding: utf-8 -*-
"""Stage 1 섀도우 게이트([Stage1Shadow] would_fire 로깅) 단위 테스트.

배경: 언어잠금 실패(잠긴 언어와 반대쪽으로 재정규화 확률이 튀는 순간)를 방출 **전에**
검출하는 신호(p_opp)에 게이트를 씌웠을 때 실제로 몇 번 발동하는지를 재는 계측이다.
**실제 언어 재감지는 트리거하지 않는다** — 게이트를 전부 통과해도 `_apply_detected_language`를
절대 호출하지 않고 `would_fire=True` 로깅만 한다(섀도우 모드).

게이트(전부 AND):
  G1 cfg.language == "auto"                              (ko/en 세션 원천 차단)
  G2 state.detected_language is not None
  G3 segments_len() >= STAGE1_MIN_SEGLEN
  G4 p_opp >= STAGE1_TAU (p_opp = 잠긴 언어의 반대쪽 재정규화 확률)
  G5 count >= STAGE1_MIN_BATCHES and (t_abs - first_t) >= STAGE1_MIN_DURATION
  G6 t_abs - state.last_lang_switch_time >= STAGE1_COOLDOWN_SECS
  G7 state.pending_language_switch is None and not state.eager_lang_detect

증거(count/first_t/lang)는 G3 또는 G4 불만족 시 리셋되고, refresh_segment()·
_apply_detected_language() 호출 시에도 리셋된다.

테스트는 두 계열의 고정체(fixture)를 재사용한다:
  - `tests.test_sot_lang_probe._fake_base` 계열(SimpleNamespace 이중체) — 세션요약/로그 형식 검증.
  - `test_timebase_refresh.py`/`test_lang_switch_wiring.py` 스타일의 `AlignAtt.__new__(AlignAtt)`
    실제 서브클래스 인스턴스 — `_stage1_shadow_gate`가 신규 메서드로 자동 상속되므로 별도
    바인딩 없이 그대로 호출 가능하고, `refresh_segment()`/`_apply_detected_language()` 같은
    기존 메서드와 상태를 공유하는 리셋 훅 검증에 적합하다.
"""

import logging
from types import SimpleNamespace

import torch

from tests.test_sot_lang_probe import _fake_base, _fake_tokenizer, _make_decoder  # noqa: F401
from whisperlivekit.simul_whisper import align_att_base
from whisperlivekit.simul_whisper.align_att_base import (
    STAGE1_COOLDOWN_SECS,
    STAGE1_MIN_BATCHES,
    STAGE1_MIN_DURATION,
    STAGE1_MIN_SEGLEN,
    STAGE1_SHADOW_ENABLED,
    STAGE1_TAU,
    AlignAttBase,
)
from whisperlivekit.simul_whisper.decoder_state import DecoderState
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt

LOGGER_NAME = "whisperlivekit.simul_whisper.align_att_base"


# ── 실제 서브클래스 기반 고정체 (test_timebase_refresh.py 스타일) ────────────────

def _make_model(language="auto", detected_language="en", seglen=2.5,
                 global_offset=0.0, cumulative=0.0,
                 last_lang_switch_time=-1_000.0, pending_language_switch=None,
                 eager_lang_detect=False):
    """모델 로드 없이 Stage1 섀도우 게이트만 테스트하기 위한 최소 AlignAtt 인스턴스.

    실제 서브클래스이므로 AlignAttBase의 신규 메서드(`_stage1_shadow_gate` 등)가
    별도 바인딩 없이 그대로 상속된다. `last_lang_switch_time`은 기본값을 아주 먼 과거로
    둬 G6(쿨다운)이 별도 지정 없이는 항상 통과하게 한다.
    """
    model = AlignAtt.__new__(AlignAtt)
    model.state = DecoderState()
    model.state.detected_language = detected_language
    model.state.global_time_offset = global_offset
    model.state.cumulative_time_offset = cumulative
    model.state.last_lang_switch_time = last_lang_switch_time
    model.state.pending_language_switch = pending_language_switch
    model.state.eager_lang_detect = eager_lang_detect
    model.cfg = SimpleNamespace(language=language, rewind_threshold=200)
    model.segments_len = lambda: seglen
    # 텐서·토크나이저 모델에 의존하는 메서드 → no-op(refresh_segment/_apply_detected_language용)
    model.init_tokens = lambda: None
    model.init_context = lambda: None
    model.create_tokenizer = lambda lang: None
    return model


def _make_model_growing_buffer(**kwargs):
    """seglen이 스텝마다 변하는 **실측 시퀀스** 재현용 고정체.

    `_make_model`은 seglen을 고정값으로 잠그지만, 실제 서버 로그의 프로브 버스트는
    버퍼가 자라는 구간에서 나오므로 t_abs와 seglen이 **함께** 증가한다. 여기서는
    `segments_len()`이 가변 속성(`_seglen`)을 읽게 만들어 `_feed_probe`가 스텝마다
    seglen을 지정할 수 있게 한다.
    """
    model = _make_model(**kwargs)
    model._seglen = kwargs.get("seglen", 2.5)
    model.segments_len = lambda: model._seglen
    return model


def _feed_probe(model, locked, p_opp, t_abs, seglen):
    """실측 프로브 1건을 흘려보낸다 — t_abs/seglen을 로그 값 그대로 재현.

    게이트는 t_abs = global_time_offset + cumulative_time_offset + segments_len() 으로
    시각을 계산하므로, 원하는 t_abs가 나오도록 global_time_offset을 역산해 넣는다.
    """
    model._seglen = seglen
    model.state.global_time_offset = t_abs - seglen - model.state.cumulative_time_offset
    if locked == "en":  # p_opp = 반대쪽(=ko) 확률
        model._stage1_shadow_gate(locked, p_opp, 1.0 - p_opp)
    else:               # locked == "ko" → p_opp = p_en
        model._stage1_shadow_gate(locked, 1.0 - p_opp, p_opp)


def _build_evidence(model, p_opp, offsets, p_field="p_ko"):
    """model에 연속 호출을 흘려보내 증거를 누적시킨다. 마지막 호출의 반환(로그) 관찰용."""
    for off in offsets:
        model.state.global_time_offset = off
        if p_field == "p_ko":
            model._stage1_shadow_gate(model.state.detected_language, p_opp, 1.0 - p_opp)
        else:
            model._stage1_shadow_gate(model.state.detected_language, 1.0 - p_opp, p_opp)


# ── #1 전 조건 만족 → would_fire=True 로그 1회 ───────────────────────────────

def test_all_gates_pass_fires_once(caplog):
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        # locked=en → p_opp는 p_ko. 0.5s 간격 3회 → count=3·dur=1.0(둘 다 문턱 충족)
        for off in (0.0, 0.5, 1.0):
            model.state.global_time_offset = off
            model._stage1_shadow_gate("en", 0.99, 0.01)

    lines = [r.getMessage() for r in caplog.records if "[Stage1Shadow] would_fire=True" in r.getMessage()]
    assert len(lines) == 1
    assert model._stage1_shadow_gate_state["would_fire"] == 1
    fields = dict(kv.split("=", 1) for kv in lines[0].split()[1:])
    assert fields["lang"] == "en"
    assert fields["k"] == "3"


# ── #2 G1 가드: cfg.language="ko"/"en" → 절대 미발동 ─────────────────────────

def test_g1_blocks_ko_locked_session():
    model = _make_model(language="ko", detected_language="ko", seglen=2.5)
    for off in (0.0, 0.5, 1.0):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("ko", 0.01, 0.99)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g1"] == 3


def test_g1_blocks_en_locked_session():
    model = _make_model(language="en", detected_language="en", seglen=2.5)
    for off in (0.0, 0.5, 1.0):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g1"] == 3


# ── #3 G2: detected_language=None → 미발동 ───────────────────────────────────

def test_g2_blocks_when_no_language_detected_yet():
    model = _make_model(language="auto", detected_language=None, seglen=2.5)
    model._stage1_shadow_gate(None, 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g2"] == 1


# ── #4 G3: seglen=1.02 (Exp-195 실측 최대값) → 미발동 (회귀 테스트) ─────────

def test_g3_blocks_at_exp195_max_observed_seglen():
    model = _make_model(language="auto", detected_language="en", seglen=1.02)
    model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g3"] == 1
    assert st["count"] == 0  # 증거도 리셋됨


# ── #5 G3: seglen=0.24 (실측 최빈값, 20/23건) → 미발동 ───────────────────────

def test_g3_blocks_at_exp195_modal_seglen():
    model = _make_model(language="auto", detected_language="en", seglen=0.24)
    model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g3"] == 1


# ── #6 G4: p_opp=0.96 (τ=0.97 미만) → 미발동 ─────────────────────────────────

def test_g4_blocks_below_tau():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    assert STAGE1_TAU == 0.97
    model._stage1_shadow_gate("en", 0.96, 0.04)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g4"] == 1
    assert st["count"] == 0  # 증거도 리셋됨


# ── #7 G5: K=2 (실측 최대 연속) → 미발동 ─────────────────────────────────────

def test_g5_blocks_at_max_observed_consecutive_k2():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    for off in (0.0, 0.5):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["count"] == 2
    assert st["blocked_by"]["g5"] >= 1


# ── #8 G5: K=3이나 지속 0.3s(10Hz) → 미발동 ──────────────────────────────────

def test_g5_blocks_k3_but_insufficient_duration():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    for off in (0.0, 0.15, 0.30):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["count"] == 3
    # G5는 3회 호출 모두에서 블록된다(1·2회차는 count<K, 3회차는 count=K이나 dur<T) — count=3이
    # G5 문턱(K와 T 둘 다)을 충족하는 순간에도 dur만 미달인 것이 이 테스트의 핵심이다.
    assert st["blocked_by"]["g5"] == 3


# ── #9 G6: 쿨다운 3.0s 이내 → 미발동 ──────────────────────────────────────────

def test_g6_blocks_within_cooldown():
    # t_abs(3번째) = global(1.0) + cumulative(0) + seglen(2.5) = 3.5
    # last_lang_switch_time=3.0 → diff=0.5 < STAGE1_COOLDOWN_SECS(3.0)
    model = _make_model(language="auto", detected_language="en", seglen=2.5,
                         last_lang_switch_time=3.0)
    for off in (0.0, 0.5, 1.0):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g6"] == 1


# ── #10 G7: pending_language_switch / eager_lang_detect → 각각 미발동 ───────

def test_g7_blocks_when_pending_language_switch_set():
    model = _make_model(language="auto", detected_language="en", seglen=2.5,
                         pending_language_switch=5.0)
    for off in (0.0, 0.5, 1.0):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g7"] == 1


def test_g7_blocks_when_eager_lang_detect_true():
    model = _make_model(language="auto", detected_language="en", seglen=2.5,
                         eager_lang_detect=True)
    for off in (0.0, 0.5, 1.0):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)
    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g7"] == 1


# ── #11 행동 불변식: 게이트 전부 통과해도 _apply_detected_language 미호출 ────

def test_would_fire_never_calls_apply_detected_language():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    calls = []
    model._apply_detected_language = lambda *a, **k: calls.append((a, k))

    for off in (0.0, 0.5, 1.0):
        model.state.global_time_offset = off
        model._stage1_shadow_gate("en", 0.99, 0.01)

    assert model._stage1_shadow_gate_state["would_fire"] == 1  # 게이트는 실제로 통과했다
    assert calls == []  # 그런데도 실제 언어 재감지는 절대 트리거되지 않는다


# ── #12 리셋: refresh_segment() 후 / p_opp 하락 후 증거 0 ────────────────────

def test_evidence_resets_on_refresh_segment():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    model.state.segments = []  # refresh_segment(complete=True) 내부 계산용
    model._stage1_shadow_gate("en", 0.99, 0.01)  # count=1로 증거 축적
    assert model._stage1_shadow_gate_state["count"] == 1

    model.refresh_segment(complete=True)

    st = model._stage1_shadow_gate_state
    assert st["count"] == 0
    assert st["first_t"] is None
    assert st["lang"] is None


def test_evidence_resets_on_apply_detected_language():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    model.state.segments = []
    model.state.lang_before_reset = None
    model._stage1_shadow_gate("en", 0.99, 0.01)
    assert model._stage1_shadow_gate_state["count"] == 1

    model._apply_detected_language("ko")

    st = model._stage1_shadow_gate_state
    assert st["count"] == 0
    assert st["first_t"] is None
    assert st["lang"] is None


def test_evidence_resets_when_p_opp_drops_below_tau():
    model = _make_model(language="auto", detected_language="en", seglen=2.5)
    model._stage1_shadow_gate("en", 0.99, 0.01)  # count=1
    assert model._stage1_shadow_gate_state["count"] == 1

    model._stage1_shadow_gate("en", 0.50, 0.50)  # p_opp=0.50 < TAU → G4 실패

    st = model._stage1_shadow_gate_state
    assert st["count"] == 0
    assert st["first_t"] is None


# ── #13 롤백 스위치: STAGE1_SHADOW_ENABLED=False → 아무 동작 없음 ───────────

def test_shadow_disabled_switch_skips_everything(monkeypatch, caplog):
    monkeypatch.setattr(align_att_base, "STAGE1_SHADOW_ENABLED", False)
    model = _make_model(language="auto", detected_language="en", seglen=2.5)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        for off in (0.0, 0.5, 1.0):
            model.state.global_time_offset = off
            model._stage1_shadow_gate("en", 0.99, 0.01)

    assert "[Stage1Shadow]" not in caplog.text
    assert not hasattr(model, "_stage1_shadow_gate_state")


def test_probe_constant_default_enabled():
    assert STAGE1_SHADOW_ENABLED is True


def test_gate_constants_match_handoff_values():
    """인계서 §4가 미리 정한 게이트 값 — Exp-195 오탐 23/23을 전부 걸러야 하는 값이다.

    단 `STAGE1_MIN_DURATION`만 인계서 초기값 1.0 → **0.8**로 완화됐다. 근거:
      - bong1의 확증된 참양성(정답 `bong1.txt:43` "플라스틱 말랑말랑한 것도 만들었죠"
        구간이 영어로 뒤집혀 방출된 언어잠금 실패)에 정확히 얹힌 프로브 버스트가
        t=92.16·k=4·**dur=0.96s**에서 T=1.0에 **40ms 차이로** 막혀 있었다.
      - 검증된 오프라인 리플레이 T 스윕 결과 T=0.8은 bong1 참양성 1건 + ytn1 1건만
        새로 통과시키고 ytn2·sbs1은 T=0.0까지 내려도 0건이다. 커버리지가 T=0.5~0.9에서
        동일하므로 0.8은 단일 관측에 맞춘 knife-edge 값이 아니다.
      - 알려진 오탐군(Exp-195 ko/en 로그 16건, G1 우회 리플레이)은 T를 0.0으로 내려도
        0건이다 — p_opp≥0.97을 통과하는 프로브의 최대 seglen이 1.02s로 G3(2.0) 문턱에
        0.98s 미달이라, 그 계열 차단은 **전적으로 G3 담당**이고 T는 기여분이 없다.
    """
    assert STAGE1_TAU == 0.97
    assert STAGE1_MIN_SEGLEN == 2.0
    assert STAGE1_MIN_BATCHES == 3
    assert STAGE1_MIN_DURATION == 0.8
    assert STAGE1_COOLDOWN_SECS == 3.0


# ── #14 Exp-195 실측 시퀀스 재현(seglen 0.24·K=1 × 23) → would_fire 총 0 ────

def test_exp195_observed_sequence_never_fires():
    model = _make_model(language="auto", detected_language="ko", seglen=0.24)
    for i in range(23):
        model.state.global_time_offset = float(i)
        # locked=ko 방향(Exp-195 실측과 동일) → p_opp = p_en
        model._stage1_shadow_gate("ko", 0.01, 0.99)

    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g3"] == 23


# ── #15 T=1.0→0.8 완화의 근거·행동 델타 회귀 (bong1 플라스틱/말랑말랑 참양성) ──
#
# bong1 정답 `test_data/bong1.txt:43`
#   "아니 그 (더듬) 플라스틱 말랑말랑한 것도 만들었죠 우리가 안전한 소품으로 물론."
# 이 구간에서 한국어로 시작했다가("아이 그" / "플라스틱 안색") 영어로 뒤집혀
#   "Plastic, sorry" / "Malang mal" / "ang an" / "awesome thing to make . We're going"
# 이 방출된, **확증된 언어잠금 실패(참양성)**다. 그 위에 정확히 얹혀 있던 p_opp 버스트가
# 아래 시퀀스이며, G3(seglen)·G4(p_opp)·K는 통과하고 오직 T=1.0에만 dur=0.96s로
# 40ms 차이로 막혀 있었다.

BONG1_PLASTIC_BURST = [
    # (t_abs, seglen, p_opp)  — locked="en"이므로 p_opp = p_ko
    (91.20, 4.36, 0.9797),
    (91.68, 4.84, 0.9945),
    (91.92, 5.08, 0.9896),
    (92.16, 5.32, 0.9996),
]


def test_bong1_plastic_true_positive_fires_at_new_duration(caplog):
    """확증된 bong1 참양성 버스트가 새 T=0.8에서 정확히 1회(k=4·dur=0.96s) 발동한다."""
    model = _make_model_growing_buffer(language="auto", detected_language="en")

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        for t_abs, seglen, p_opp in BONG1_PLASTIC_BURST:
            _feed_probe(model, "en", p_opp, t_abs, seglen)

    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 1
    assert st["count"] == 4
    # 1~3번째는 전부 G5에서 막힌다(1·2회차 count<K, 3회차 dur=0.72s<0.8)
    assert st["blocked_by"]["g5"] == 3

    lines = [r.getMessage() for r in caplog.records if "[Stage1Shadow] would_fire=True" in r.getMessage()]
    assert len(lines) == 1
    fields = dict(kv.split("=", 1) for kv in lines[0].split()[1:])
    assert fields["lang"] == "en"
    assert fields["k"] == "4"
    assert fields["t"] == "92.16"
    assert fields["dur"] == "0.96"


def test_bong1_plastic_true_positive_was_blocked_at_old_duration(monkeypatch):
    """동일 버스트가 구 T=1.0에서는 발동하지 않았다 — 이 커밋의 행동 델타 고정."""
    monkeypatch.setattr(align_att_base, "STAGE1_MIN_DURATION", 1.0)
    model = _make_model_growing_buffer(language="auto", detected_language="en")

    for t_abs, seglen, p_opp in BONG1_PLASTIC_BURST:
        _feed_probe(model, "en", p_opp, t_abs, seglen)

    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["count"] == 4
    assert st["blocked_by"]["g5"] == 4  # 마지막 k=4도 dur=0.96s < 1.0으로 탈락


# ── #16 알려진 오탐군(Exp-195 ko)은 T와 무관하게 G3가 전담 차단한다 ──────────

def test_exp195_ko_false_positives_blocked_by_g3_even_with_zero_duration(monkeypatch):
    """T를 0.0까지 내려도 Exp-195 ko 오탐군은 한 건도 통과하지 못한다.

    Exp-195 ko/en 세션 로그 16건을 G1을 일부러 우회해 리플레이해도 would_fire=0이었고,
    p_opp≥τ를 통과하는 프로브의 seglen은 최빈 0.24s·최대 1.02s로 G3(2.0)에 크게 미달한다.
    즉 이 오탐 계열의 유일한 방벽은 G3이며 T 완화는 오탐 보호를 깎지 않는다.
    """
    monkeypatch.setattr(align_att_base, "STAGE1_MIN_DURATION", 0.0)
    model = _make_model_growing_buffer(language="auto", detected_language="ko")

    # 실측 seglen 분포(최빈 0.24s, 최대 1.02s)를 K=2까지 연속으로 흘려보낸다
    for seglen in (0.24, 1.02):
        for k in range(2):
            _feed_probe(model, "ko", 0.99, 10.0 + k * 0.1, seglen)

    st = model._stage1_shadow_gate_state
    assert st["would_fire"] == 0
    assert st["blocked_by"]["g3"] == 4     # 4건 전부 G3에서 탈락
    assert st["blocked_by"]["g5"] == 0     # G5(K·T)까지 도달조차 못 한다
    assert st["count"] == 0                # 증거도 매번 리셋


# ── 세션 요약 로그([Stage1ShadowStats]) — [LangDriftStats] 포맷 불변 확인 ────

def test_shadow_stats_log_does_not_disturb_lang_drift_stats_format(caplog):
    """세션 요약이 기존 [LangDriftStats] 파서 호환 포맷을 건드리지 않는다."""
    fake = _fake_base(detected_language="en", language="auto")
    fake._log_lang_drift_stats = AlignAttBase._log_lang_drift_stats.__get__(fake)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        fake._log_lang_drift_stats()

    assert "[LangDriftStats] probes=0" in caplog.text


# ── 세션 요약 로그 — would_fire 불변인 채 blocked_by만 누적돼도 갱신 로그가 찍힌다 ──
# (실측 회귀 테스트: bong1/ytn2/sbs1/ytn1 4파일 전부 would_fire=0으로 세션 내내 고정되자
#  최초 1회 스냅샷 이후 누적된 blocked_by가 로그에 전혀 반영되지 않는 버그가 실제로 발견됐다.)

def test_shadow_stats_logs_again_when_only_blocked_by_changes(caplog):
    model = _make_model(language="auto", detected_language="en", seglen=0.24)
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        model._stage1_shadow_gate("en", 0.99, 0.01)  # G3 차단 1건째(seglen 미달)
        model._log_stage1_shadow_stats()
        model._stage1_shadow_gate("en", 0.99, 0.01)  # G3 차단 2건째 — would_fire는 여전히 0
        model._log_stage1_shadow_stats()

    lines = [r.getMessage() for r in caplog.records if "[Stage1ShadowStats]" in r.getMessage()]
    assert len(lines) == 2  # 총 호출수가 늘었으므로 두 번째도 반드시 다시 찍혀야 한다
    assert "would_fire=0 blocked_g1=0 blocked_g2=0 blocked_g3=1" in lines[0]
    assert "would_fire=0 blocked_g1=0 blocked_g2=0 blocked_g3=2" in lines[1]


# ── 실제 트리거 지점 배선 — _sot_lang_probe_impl이 stage1 게이트를 호출한다 ──

def test_sot_lang_probe_impl_wires_into_stage1_gate(monkeypatch):
    """infer()의 new_segment 프로브 경로(_sot_lang_probe_impl)가 locked/p_ko/p_en을
    계산한 직후 _stage1_shadow_gate로 넘긴다 — 실제 트리거 지점 배선 확인."""
    d = _make_decoder(detected_language="en", language="auto")
    d.segments_len = lambda: 2.5

    seen = []
    d._stage1_shadow_gate = lambda locked, p_ko, p_en: seen.append((locked, p_ko, p_en))

    logits = torch.randn(2, 4, 20, generator=torch.Generator().manual_seed(5))
    AlignAttBase._log_sot_lang_probe(d, logits)

    assert len(seen) == 1
    locked, p_ko, p_en = seen[0]
    assert locked == "en"
    assert 0.0 <= p_ko <= 1.0 and 0.0 <= p_en <= 1.0
