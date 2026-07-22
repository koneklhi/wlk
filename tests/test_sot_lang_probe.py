# -*- coding: utf-8 -*-
"""SOT 위치 언어/태스크 사후분포 계측([SotLangProbe]/[LangDriftStats]) 단위 테스트.

배경: detected_language가 en에 고착된 채 한국어 오디오가 들어오면 Whisper가
off-manifold 상태에서 translate 매니폴드로 사영돼 한국어 발화를 영어로 번역·음차
출력한다(bong1 10회 중 5회). 그 실패를 예측할 수 있는 신호가 존재하는지를
**추가 forward 0회 / 디코딩 행동 변경 0**으로 확인하기 위한 계측이다.

핵심 불변식(가장 중요): 프로브는 infer()가 직후 재사용하는 logits 텐서를
**in-place로 절대 건드리지 않는다**. lang_id()가 자기 forward 결과에
logits[:, mask] = -inf를 하는 것과 달리, 여기 logits는 호출 직후
logits[:, -1, :]로 디코딩에 다시 쓰이기 때문이다.
"""

import logging
import types
from types import SimpleNamespace

import torch

from whisperlivekit.simul_whisper import align_att_base
from whisperlivekit.simul_whisper.align_att_base import (
    SOT_LANG_PROBE_ENABLED,
    AlignAttBase,
)
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt

LOGGER_NAME = "whisperlivekit.simul_whisper.align_att_base"

# ── 소형 가짜 어휘 ────────────────────────────────────────────────────────────
V = 20
LANG_IDS = (10, 11, 12, 13)
LANG_CODES = ("en", "ko", "ja", "zh")
EN_ID, KO_ID = 10, 11
TRANSLATE_ID, TRANSCRIBE_ID, NO_SPEECH_ID = 15, 16, 17

PROB_KEYS = (
    "p_ko", "p_en", "p_abs_ko", "p_abs_en", "resid", "H_lang",
    "p_translate", "p_transcribe", "p_nospeech",
)


class _FakeContext:
    def __init__(self, token_ids=()):
        self._ids = list(token_ids)

    def is_empty(self):
        return not self._ids

    def as_token_ids(self):
        return list(self._ids)


def _fake_tokenizer(no_speech=NO_SPEECH_ID):
    return SimpleNamespace(
        all_language_tokens=LANG_IDS,
        all_language_codes=LANG_CODES,
        translate=TRANSLATE_ID,
        transcribe=TRANSCRIBE_ID,
        no_speech=no_speech,
    )


def _make_decoder(context_ids=(), sot_index=0, lang_restrict_koen=True,
                  no_speech=NO_SPEECH_ID, detected_language="en", language="auto"):
    """_read_sot_posteriors 단위 테스트용 최소 AlignAtt 인스턴스(모델 없음)."""
    d = AlignAtt.__new__(AlignAtt)
    d.tokenizer = _fake_tokenizer(no_speech=no_speech)
    d.cfg = SimpleNamespace(lang_restrict_koen=lang_restrict_koen, language=language)
    d.state = SimpleNamespace(
        context=_FakeContext(context_ids),
        sot_index=sot_index,
        detected_language=detected_language,
        global_time_offset=0.0,
        cumulative_time_offset=0.0,
    )
    return d


def _logits(n_pos=4, beam=2, seed=0):
    g = torch.Generator().manual_seed(seed)
    return torch.randn(beam, n_pos, V, generator=g)


# ── ① sot_pos 계산: context 없음 → sot_index 그대로 ──────────────────────────

def test_sot_pos_equals_sot_index_when_context_empty():
    d = _make_decoder(context_ids=(), sot_index=0)
    info = d._read_sot_posteriors(_logits())
    assert info is not None
    assert info["ctx_len"] == 0
    assert info["sot_pos"] == d.state.sot_index == 0


# ── ② sot_pos 계산: context 있으면 ctx_len만큼 보정 ──────────────────────────

def test_sot_pos_shifted_by_context_length():
    """--max-context-tokens>0 / --static-init-prompt 시 sot는 context 뒤에 온다.

    state.sot_index는 context 길이를 반영하지 않으므로(기존 잠재 버그, 이번엔 미수정)
    신규 코드가 스스로 ctx_len을 더해 방어적으로 계산해야 한다.
    """
    d = _make_decoder(context_ids=(101, 102, 103), sot_index=0)
    logits = _logits(n_pos=6)
    info = d._read_sot_posteriors(logits)
    assert info is not None
    assert info["ctx_len"] == 3
    assert info["sot_pos"] == 3

    # 실제로 위치 3의 분포를 읽었는지 수치로 확인(위치 0이 아니라)
    expected = logits[0, 3, :].float().softmax(dim=-1)
    assert abs(info["p_abs_ko"] - expected[KO_ID].item()) < 1e-6
    assert abs(info["p_abs_en"] - expected[EN_ID].item()) < 1e-6
    expected_task = logits[0, 4, :].float().softmax(dim=-1)
    assert abs(info["p_translate"] - expected_task[TRANSLATE_ID].item()) < 1e-6


# ── ③ (최중요) logits 텐서 in-place 미오염 ────────────────────────────────────

def test_logits_tensor_is_not_mutated():
    """호출 전후로 logits가 비트 단위로 동일해야 한다.

    infer()는 이 호출 직후 같은 텐서를 logits[:, -1, :]로 재사용한다 —
    lang_id()처럼 -inf 마스킹을 하면 디코딩이 즉시 오염된다.
    """
    d = _make_decoder()
    logits = _logits(n_pos=5, beam=3, seed=7)
    before = logits.clone()

    info = d._read_sot_posteriors(logits)

    assert info is not None
    assert torch.equal(logits, before), "프로브가 logits를 in-place로 수정했다"
    assert torch.isfinite(logits).all(), "logits에 -inf가 주입됐다"


def test_logits_not_mutated_even_via_log_wrapper():
    """상위 래퍼(_log_sot_lang_probe) 경로에서도 텐서가 보존된다."""
    d = _make_decoder()
    d.segments_len = lambda: 1.0
    logits = _logits(seed=3)
    before = logits.clone()

    AlignAttBase._log_sot_lang_probe(d, logits)

    assert torch.equal(logits, before)


# ── ④ 반환 dict 필드·확률 범위·재정규화 합 ───────────────────────────────────

def test_returned_dict_has_all_fields_and_valid_probabilities():
    d = _make_decoder()
    info = d._read_sot_posteriors(_logits(seed=11))

    assert info is not None
    for k in PROB_KEYS:
        assert k in info, f"필드 누락: {k}"
    for k in ("p_ko", "p_en", "p_abs_ko", "p_abs_en", "p_translate",
              "p_transcribe", "p_nospeech"):
        assert 0.0 <= info[k] <= 1.0, f"{k}={info[k]} 가 [0,1] 밖"
    # resid = 1 - p_abs_ko - p_abs_en (부동소수 여유)
    assert -1e-6 <= info["resid"] <= 1.0 + 1e-6
    assert abs(info["resid"] - (1.0 - info["p_abs_ko"] - info["p_abs_en"])) < 1e-6
    # H_lang: 언어 토큰 집합(4종) 엔트로피(nats) → [0, ln4]
    assert 0.0 <= info["H_lang"] <= torch.log(torch.tensor(float(len(LANG_IDS)))).item() + 1e-6


def test_p_ko_p_en_renormalized_to_one_under_koen_restrict():
    """S1은 lang_id(lang_restrict_koen=True)와 동일 방식 → p_ko + p_en ≈ 1."""
    d = _make_decoder(lang_restrict_koen=True)
    info = d._read_sot_posteriors(_logits(seed=21))
    assert abs(info["p_ko"] + info["p_en"] - 1.0) < 1e-6


def test_p_ko_p_en_use_full_language_set_when_restrict_off():
    """lang_restrict_koen=False면 lang_id와 동일하게 전체 언어 토큰으로 재정규화된다."""
    d = _make_decoder(lang_restrict_koen=False)
    info = d._read_sot_posteriors(_logits(seed=21))
    assert info["p_ko"] + info["p_en"] < 1.0  # ja/zh 질량이 분모에 포함됨


def test_absolute_mass_differs_from_renormalized():
    """S2의 존재 이유: 재정규화 확률만으로는 절대확신 여부를 구분할 수 없다."""
    d = _make_decoder()
    logits = torch.full((1, 4, V), -20.0)
    logits[0, 0, EN_ID] = 0.0     # 언어 토큰 중엔 en 우세
    logits[0, 0, KO_ID] = -6.0
    logits[0, 0, 5] = 12.0        # 그러나 절대질량은 비언어 토큰이 독식
    info = d._read_sot_posteriors(logits)

    assert info["p_en"] > 0.99            # 재정규화하면 "en 확신"처럼 보이지만
    assert info["p_abs_en"] < 0.01        # 절대질량은 미미하고
    assert info["resid"] > 0.98           # 잔차가 거의 전부다(off-manifold 신호)


# ── ⑤ 범위 밖 / 미지원 폴백 ──────────────────────────────────────────────────

def test_returns_none_when_task_position_out_of_range():
    """sot_pos+1이 시퀀스 길이를 넘으면 None(방어)."""
    d = _make_decoder()
    assert d._read_sot_posteriors(torch.randn(1, 1, V)) is None


def test_returns_none_when_context_pushes_sot_out_of_range():
    d = _make_decoder(context_ids=(1, 2, 3, 4, 5), sot_index=0)
    assert d._read_sot_posteriors(_logits(n_pos=4)) is None


def test_returns_none_for_non_3d_logits():
    """비-new_segment 경로처럼 [beam, V] 2D가 오면 계측하지 않는다."""
    d = _make_decoder()
    assert d._read_sot_posteriors(torch.randn(1, V)) is None
    assert d._read_sot_posteriors(None) is None


def test_p_nospeech_is_none_when_tokenizer_has_no_nospeech():
    d = _make_decoder(no_speech=None)
    info = d._read_sot_posteriors(_logits())
    assert info is not None
    assert info["p_nospeech"] is None


def test_base_default_implementation_returns_none_for_mlx_fallback():
    """base 기본 구현은 None — MLX 경로가 전 위치 logits를 주는지 미확인이므로 안전 폴백."""
    dummy = SimpleNamespace()
    assert AlignAttBase._read_sot_posteriors(dummy, _logits()) is None


# ── ⑥ 롤백 스위치 ────────────────────────────────────────────────────────────

def test_probe_disabled_skips_instrumentation(monkeypatch):
    """SOT_LANG_PROBE_ENABLED=False → _read_sot_posteriors 자체를 부르지 않는다."""
    monkeypatch.setattr(align_att_base, "SOT_LANG_PROBE_ENABLED", False)
    calls = []
    fake = SimpleNamespace(_read_sot_posteriors=lambda logits: calls.append(logits))

    AlignAttBase._log_sot_lang_probe(fake, _logits())

    assert calls == []
    assert not hasattr(fake, "_sot_lang_probe_stats")


def test_drift_stats_disabled_emits_nothing(monkeypatch, caplog):
    monkeypatch.setattr(align_att_base, "SOT_LANG_PROBE_ENABLED", False)
    fake = SimpleNamespace(cfg=SimpleNamespace(language="auto"))
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        AlignAttBase._log_lang_drift_stats(fake)
    assert "[LangDriftStats]" not in caplog.text


def test_probe_constant_default_enabled():
    assert SOT_LANG_PROBE_ENABLED is True


# ── ⑦ 로그 포맷 / 세션 요약 카운터 ───────────────────────────────────────────

def _fake_base(detected_language="en", language="auto"):
    fake = SimpleNamespace(
        state=SimpleNamespace(
            detected_language=detected_language,
            global_time_offset=10.0,
            cumulative_time_offset=0.5,
        ),
        cfg=SimpleNamespace(language=language),
    )
    fake.segments_len = lambda: 2.25
    fake._sot_probe_stats = types.MethodType(AlignAttBase._sot_probe_stats, fake)
    fake._sot_lang_probe_impl = types.MethodType(AlignAttBase._sot_lang_probe_impl, fake)
    return fake


def _info(**over):
    base = {
        "p_ko": 0.02, "p_en": 0.98, "p_abs_ko": 0.001, "p_abs_en": 0.05,
        "resid": 0.949, "H_lang": 0.31, "p_translate": 0.004,
        "p_transcribe": 0.91, "p_nospeech": 0.12, "sot_pos": 0, "ctx_len": 0,
    }
    base.update(over)
    return base


def test_probe_log_line_is_key_value_parsable(caplog):
    fake = _fake_base()
    fake._read_sot_posteriors = lambda logits: _info()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        AlignAttBase._log_sot_lang_probe(fake, "logits")

    lines = [r.getMessage() for r in caplog.records if "[SotLangProbe]" in r.getMessage()]
    assert len(lines) == 1
    line = lines[0]
    fields = dict(kv.split("=", 1) for kv in line.split()[1:])
    for key in ("t_abs", "batch", "locked", "seglen", "p_ko", "p_en", "p_abs_ko",
                "p_abs_en", "resid", "H_lang", "p_translate", "p_transcribe",
                "p_nospeech", "lang_locked"):
        assert key in fields, f"로그 필드 누락: {key} ({line})"
    # t_abs = global + cumulative + segments_len (토큰 절대 타임스탬프와 동일 좌표계)
    assert fields["t_abs"] == "12.75"
    assert fields["locked"] == "en"
    assert fields["lang_locked"] == "False"


def test_probe_log_records_lang_locked_for_fixed_session(caplog):
    """--lan ko/en 고정 세션에서도 계측은 켜두되 lang_locked=True로 구분한다."""
    fake = _fake_base(detected_language="ko", language="ko")
    fake._read_sot_posteriors = lambda logits: _info()

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        AlignAttBase._log_sot_lang_probe(fake, "logits")

    assert "lang_locked=True" in caplog.text


def test_probe_log_formats_missing_nospeech_as_nan(caplog):
    fake = _fake_base()
    fake._read_sot_posteriors = lambda logits: _info(p_nospeech=None)

    with caplog.at_level(logging.DEBUG, logger=LOGGER_NAME):
        AlignAttBase._log_sot_lang_probe(fake, "logits")

    assert "p_nospeech=nan" in caplog.text


def test_stats_accumulate_mismatch_and_offmanifold_counts():
    fake = _fake_base(detected_language="en")
    # ① 잠긴 언어(en)와 반대쪽(ko)이 0.95 → mismatch 후보, resid/translate도 높음
    fake._read_sot_posteriors = lambda logits: _info(
        p_ko=0.95, p_en=0.05, resid=0.8, p_translate=0.3)
    AlignAttBase._log_sot_lang_probe(fake, "logits")
    # ② 정상(en 확신) → 카운트 증가 없음
    fake._read_sot_posteriors = lambda logits: _info(
        p_ko=0.01, p_en=0.99, resid=0.01, p_translate=0.001)
    AlignAttBase._log_sot_lang_probe(fake, "logits")

    stats = fake._sot_lang_probe_stats
    assert stats["probes"] == 2
    assert stats["locked_en"] == 2 and stats["locked_ko"] == 0
    assert stats["mismatch_candidates"] == 1
    assert stats["high_resid"] == 1
    assert stats["high_translate"] == 1
    assert abs(stats["max_resid"] - 0.8) < 1e-9


def test_probe_returning_none_does_not_count():
    """미지원(None) 반환은 카운터를 만들지도 올리지도 않는다."""
    fake = _fake_base()
    fake._read_sot_posteriors = lambda logits: None
    AlignAttBase._log_sot_lang_probe(fake, "logits")
    assert getattr(fake, "_sot_lang_probe_stats", {"probes": 0})["probes"] == 0


def test_probe_exception_is_swallowed():
    """계측 실패가 디코딩을 막지 않는다."""
    fake = _fake_base()

    def boom(logits):
        raise RuntimeError("boom")

    fake._read_sot_posteriors = boom
    AlignAttBase._log_sot_lang_probe(fake, "logits")  # 예외 전파 없음


def test_drift_stats_emits_zero_firing_control(caplog):
    """probes=0 회차도 명시적으로 남긴다(0-firing = 노이즈 대조군)."""
    fake = _fake_base()
    fake._log_lang_drift_stats = types.MethodType(AlignAttBase._log_lang_drift_stats, fake)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        fake._log_lang_drift_stats()

    assert "[LangDriftStats] probes=0" in caplog.text


def test_drift_stats_dedups_unchanged_counters(caplog):
    fake = _fake_base()
    fake._log_lang_drift_stats = types.MethodType(AlignAttBase._log_lang_drift_stats, fake)
    fake._read_sot_posteriors = lambda logits: _info()

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        fake._log_lang_drift_stats()          # probes=0 → 1줄
        fake._log_lang_drift_stats()          # 변화 없음 → 생략
        AlignAttBase._log_sot_lang_probe(fake, "logits")
        fake._log_lang_drift_stats()          # probes=1 → 1줄

    lines = [r.getMessage() for r in caplog.records if "[LangDriftStats]" in r.getMessage()]
    assert len(lines) == 2
    assert "probes=0" in lines[0] and "probes=1" in lines[1]


# ── ⑧ infer() 배선: is_last에서 요약, new_segment에서 프로브 ─────────────────

def test_infer_emits_drift_summary_on_is_last(caplog):
    """infer(is_last=True)는 (조기 반환 경로여도) 세션 요약을 1회 남긴다."""
    from whisperlivekit.simul_whisper.decoder_state import DecoderState

    d = AlignAtt.__new__(AlignAtt)
    d.state = DecoderState()
    d.state.segments = []       # 조기 반환 경로
    d.cfg = SimpleNamespace(language="auto")

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        assert AlignAtt.infer(d, is_last=True) == []

    assert "[LangDriftStats] probes=0" in caplog.text
