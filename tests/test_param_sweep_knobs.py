# -*- coding: utf-8 -*-
"""파라미터 스윕 캠페인(2026-08) Stage 0 하네스 단위 테스트.

검증 대상:
1. 신규 CLI knob 4종(min_silence_duration_ms·speech_pad_ms·quality_gate_reset_after·
   rewind_threshold)이 argparse → WhisperLiveKitConfig → 소비 지점까지 도달하는가.
2. **무회귀 불변식**: 전부 미지정이면 None → 기존 하드코딩 상수로 폴백.
3. **falsy 삼킴 방지**: 명시적 `0`이 `or` 폴백에 먹혀 기본값으로 되돌아가지 않는가.
   (기존 `getattr(...) or default` 패턴이 유발한 부류의 버그 — 신규 코드는 `is None`을 쓴다.)
4. `simul_whisper._sot_pos()`의 context 오프셋 보정 — Track C(max_context_tokens>0) 선행 조건.
5. `scripts/eval.py --server-arg` 패스스루가 provenance에 arm 식별자로 기록되는가.
"""

import sys
from pathlib import Path

import pytest

from whisperlivekit.config import WhisperLiveKitConfig
from whisperlivekit.parse_args import create_parser, parse_args
from whisperlivekit.simul_whisper.config import AlignAttConfig

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from eval import _probe_provenance  # noqa: E402

# 신규 스윕 knob과 각 소비 지점의 기존 하드코딩 상수(= 미지정 시 폴백돼야 하는 값)
_SWEEP_KNOBS = {
    "min_silence_duration_ms": 200,   # audio_processor FixedVADIterator
    "speech_pad_ms": 30,              # Silero VADIterator 기본값
    "quality_gate_reset_after": 5,    # AlignAttConfig (Exp-214로 기본값 3→5 변경, master 0217d66)
    "rewind_threshold": 200,          # AlignAttConfig
}


def _parse(monkeypatch, argv):
    """실제 parse_args() 경로를 그대로 태워 WhisperLiveKitConfig를 반환한다."""
    monkeypatch.setattr("sys.argv", ["prog"] + argv)
    return parse_args()


# ─── 1. 무회귀 — 미지정이면 전부 None ──────────────────────────────────────────

def test_sweep_knobs_default_to_none(monkeypatch):
    """아무 플래그도 안 주면 신규 필드가 전부 None이어야 한다(소비 지점이 기존 상수로 폴백)."""
    cfg = _parse(monkeypatch, [])
    for name in _SWEEP_KNOBS:
        assert getattr(cfg, name) is None, f"{name}의 기본값이 None이 아니다 — 무회귀 위반"


def test_alignatt_defaults_match_documented_constants():
    """AlignAttConfig 기본값이 스윕 계획서에 기록된 현재값과 일치하는지 고정한다."""
    cfg = AlignAttConfig()
    assert cfg.quality_gate_reset_after == _SWEEP_KNOBS["quality_gate_reset_after"]
    assert cfg.rewind_threshold == _SWEEP_KNOBS["rewind_threshold"]


# ─── 2. 명시 지정이 config까지 도달 ────────────────────────────────────────────

def test_sweep_knobs_reach_config(monkeypatch):
    cfg = _parse(monkeypatch, [
        "--min-silence-duration-ms", "400",
        "--speech-pad-ms", "100",
        "--quality-gate-reset-after", "8",
        "--rewind-threshold", "100",
    ])
    assert cfg.min_silence_duration_ms == 400
    assert cfg.speech_pad_ms == 100
    assert cfg.quality_gate_reset_after == 8
    assert cfg.rewind_threshold == 100


@pytest.mark.parametrize("flag,field", [
    ("--speech-pad-ms", "speech_pad_ms"),
    ("--min-silence-duration-ms", "min_silence_duration_ms"),
    ("--quality-gate-reset-after", "quality_gate_reset_after"),
    ("--rewind-threshold", "rewind_threshold"),
])
def test_explicit_zero_is_not_swallowed(monkeypatch, flag, field):
    """명시적 0이 falsy로 삼켜져 기본값으로 되돌아가면 안 된다.

    `getattr(args, k, None) or default` 패턴이 유발하는 조용한 되돌림을 막기 위한 회귀 테스트.
    """
    cfg = _parse(monkeypatch, [flag, "0"])
    assert getattr(cfg, field) == 0, f"{field}에 명시한 0이 삼켜졌다"


def test_from_namespace_would_drop_undeclared_fields():
    """WhisperLiveKitConfig에 필드를 선언하지 않으면 argparse 값이 조용히 사라진다.

    `--periodic-lang-check`가 죽은 플래그가 된 것과 같은 부류의 사고를 방지하는 가드.
    """
    class _NS:
        pass

    ns = _NS()
    ns.min_silence_duration_ms = 400
    ns.__dict__["definitely_not_a_config_field"] = 123
    cfg = WhisperLiveKitConfig.from_namespace(ns)
    assert cfg.min_silence_duration_ms == 400
    assert not hasattr(cfg, "definitely_not_a_config_field")


# ─── 3. AlignAttConfig 오버라이드 선택 로직 ────────────────────────────────────

@pytest.mark.parametrize("overrides,expect_qg,expect_rw", [
    ({}, 5, 200),                                              # 미지정 → 기본값 유지(Exp-214 이후 5)
    ({"quality_gate_reset_after": 8}, 8, 200),                 # 일부만 오버라이드
    ({"rewind_threshold": 100}, 5, 100),
    ({"quality_gate_reset_after": 999, "rewind_threshold": 400}, 999, 400),
])
def test_alignatt_partial_override(overrides, expect_qg, expect_rw):
    """None인 knob은 키 자체를 안 넘겨 AlignAttConfig 기본값이 살아남아야 한다."""
    cfg = AlignAttConfig(**overrides)
    assert cfg.quality_gate_reset_after == expect_qg
    assert cfg.rewind_threshold == expect_rw


# ─── 4. _sot_pos() context 오프셋 (Track C 선행 조건) ──────────────────────────

class _FakeContext:
    def __init__(self, token_ids):
        self._ids = list(token_ids)

    def is_empty(self):
        return not self._ids

    def as_token_ids(self):
        return list(self._ids)


class _FakeState:
    def __init__(self, sot_index, context):
        self.sot_index = sot_index
        self.context = context


def _sot_pos_of(sot_index, context):
    """AlignAtt._sot_pos를 상태만 갈아끼워 호출한다(모델 로딩 회피)."""
    from whisperlivekit.simul_whisper.simul_whisper import AlignAtt

    obj = object.__new__(AlignAtt)
    obj.state = _FakeState(sot_index, context)
    return AlignAtt._sot_pos(obj)


def test_sot_pos_without_context_is_unchanged():
    """context가 비면 오프셋 0 — 운영 기본값(max_context_tokens=0)에서 기존 동작과 동일."""
    assert _sot_pos_of(0, _FakeContext([])) == 0
    assert _sot_pos_of(2, _FakeContext([])) == 2
    assert _sot_pos_of(1, None) == 1


def test_sot_pos_shifts_by_context_length():
    """context가 있으면 그 길이만큼 뒤로 밀려야 한다 — 안 밀면 <|startofprev|> 위치를 읽는다."""
    assert _sot_pos_of(0, _FakeContext([50361, 1, 2, 3])) == 4
    assert _sot_pos_of(2, _FakeContext([50361, 1, 2, 3])) == 6


# ─── 5. eval.py --server-arg → provenance arm 식별자 ──────────────────────────

class _EvalArgs:
    """_probe_provenance가 읽는 필드만 갖춘 최소 네임스페이스."""

    def __init__(self, server_args=None):
        self.compression_ratio_threshold = 3.0
        self.logprob_threshold = None
        self.periodic_lang_check_secs = None
        self.diarization = True
        self.files = [Path("test_data/ytn2.mp3")]
        self.repeat = 1
        if server_args is not None:
            self.server_args = server_args


def test_provenance_records_server_args(tmp_path):
    prov = _probe_provenance(tmp_path, _EvalArgs(["--vad-threshold", "0.25"]))
    assert prov["server_args"] == ["--vad-threshold", "0.25"]


def test_provenance_server_args_defaults_to_empty(tmp_path):
    """--server-arg 미사용 run도 필드가 존재해야 원장 스키마가 깨지지 않는다."""
    prov = _probe_provenance(tmp_path, _EvalArgs())
    assert prov["server_args"] == []


def test_eval_cli_exposes_server_arg():
    """eval.py가 --server-arg를 실제 CLI로 노출하는지 확인한다.

    파서가 main() 안에 있어 직접 import할 수 없으므로 --help를 subprocess로 태워
    CLI 계약 자체를 검증한다(스윕 드라이버가 의존하는 유일한 진입점).
    """
    import os
    import subprocess

    # PYTHONIOENCODING=utf-8은 이 저장소의 eval.py 실행 규약이다(help/로그에 한글·em-dash 포함).
    # 스윕 드라이버도 동일하게 설정해야 cp949 콘솔에서 UnicodeEncodeError로 죽지 않는다.
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    out = subprocess.run(
        [sys.executable, str(_SCRIPTS_DIR / "eval.py"), "--help"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env,
    )
    assert out.returncode == 0, out.stderr
    assert "--server-arg" in out.stdout


def test_server_arg_precedence_is_last(monkeypatch):
    """서버 argparse는 같은 플래그가 중복되면 뒤쪽이 이긴다 — --server-arg가 마지막에 붙는 근거."""
    parser = create_parser()
    args = parser.parse_args(["--vad-threshold", "0.3", "--vad-threshold", "0.25"])
    assert args.vad_threshold == 0.25
