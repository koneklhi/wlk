# -*- coding: utf-8 -*-
"""시나리오 프리셋(scenario_presets) + 신규 CLI 튜닝 플래그 단위 테스트 (Phase A).

배포 음성 상황별 파라미터(--scenario mono/dialogue/sequential/codeswitch/multi)와
그 하위에서 개별 승격된 CLI 플래그(--min-real-silence-secs 등)의 우선순위·기본값
무회귀를 검증한다.

우선순위: 개별 플래그 > 프리셋(--scenario) > 소비 지점 기존 하드코딩 상수.
"""

import pytest

from whisperlivekit.parse_args import create_parser, parse_args
from whisperlivekit.scenario_presets import SCENARIO_PRESETS, apply_scenario_preset

# 시나리오 프리셋이 건드리는(그리고 이번 작업으로 CLI 승격된) 신규 필드 전체 목록.
_NEW_TUNING_FIELDS = [
    "min_real_silence_secs",
    "vad_threshold",
    "pending_resolve_cap_secs",
    "min_speaker_attribution_secs",
    "finalize_grace_secs",
    "short_lang_reset_secs",
    "script_anchor_n_words",
    "new_speaker_max_keep_secs",
    "lang_detect_general_secs",
]


def _parse(monkeypatch, argv):
    """실제 parse_args() 경로(sys.argv 파싱 → scenario 적용 → WhisperLiveKitConfig 변환)를
    그대로 태워 WhisperLiveKitConfig를 반환한다 — 프로덕션 배선을 그대로 검증하기 위해
    별도 파싱 로직을 재구현하지 않는다.
    """
    monkeypatch.setattr("sys.argv", ["prog"] + argv)
    return parse_args()


# ─── 1. --scenario 단독 지정 → 프리셋 필드 반영 ───────────────────────────────

def test_scenario_mono_applies_preset_fields(monkeypatch):
    config = _parse(monkeypatch, ["--scenario", "mono"])
    assert config.frame_threshold == 20
    assert config.min_real_silence_secs == 0.6
    assert config.silence_hard_secs == 1.8


def test_scenario_dialogue_applies_preset_fields(monkeypatch):
    config = _parse(monkeypatch, ["--scenario", "dialogue"])
    assert config.min_speaker_attribution_secs == 0.4


def test_scenario_sequential_applies_preset_fields(monkeypatch):
    config = _parse(monkeypatch, ["--scenario", "sequential"])
    assert config.frame_threshold == 18
    assert config.min_real_silence_secs == 0.3
    assert config.finalize_grace_secs == 1.2


def test_scenario_codeswitch_applies_preset_fields(monkeypatch):
    config = _parse(monkeypatch, ["--scenario", "codeswitch"])
    assert config.pending_resolve_cap_secs == 2.4
    assert config.short_lang_reset_secs == 0.4


def test_scenario_multi_applies_preset_fields(monkeypatch):
    config = _parse(monkeypatch, ["--scenario", "multi"])
    assert config.frame_threshold == 32
    assert config.min_real_silence_secs == 0.6
    assert config.vad_threshold == 0.4
    assert config.silence_hard_secs == 2.0
    assert config.pending_resolve_cap_secs == 2.5
    assert config.finalize_grace_secs == 2.8
    assert config.lang_detect_general_secs == 2.5


# ─── 2. 개별 플래그가 프리셋보다 우선 ─────────────────────────────────────────

def test_individual_flag_overrides_preset(monkeypatch):
    """--scenario mono --frame-threshold 99 → 개별 플래그(99)가 프리셋값(20)을 이긴다."""
    config = _parse(monkeypatch, ["--scenario", "mono", "--frame-threshold", "99"])
    assert config.frame_threshold == 99            # 개별 플래그 승리
    assert config.min_real_silence_secs == 0.6      # 나머지 프리셋 필드는 그대로 반영
    assert config.silence_hard_secs == 1.8


def test_individual_flag_overrides_preset_for_new_field(monkeypatch):
    """새로 승격한 필드 자체도 개별 플래그 우선순위가 지켜지는지 확인."""
    config = _parse(
        monkeypatch,
        ["--scenario", "codeswitch", "--pending-resolve-cap-secs", "9.9"],
    )
    assert config.pending_resolve_cap_secs == 9.9   # 개별 플래그(9.9) 승리, 프리셋(2.4) 아님
    assert config.short_lang_reset_secs == 0.4       # 나머지 프리셋 필드는 그대로 반영


# ─── 3. --scenario 미지정 시 전부 None + 기존 하드코딩 상수로 폴백 ────────────

def test_no_scenario_all_new_fields_none(monkeypatch):
    config = _parse(monkeypatch, [])
    for field in _NEW_TUNING_FIELDS:
        assert getattr(config, field) is None, f"{field} 는 --scenario 미지정 시 None이어야 함"


def test_no_scenario_consumption_points_match_hardcoded_constants():
    """소비 모듈을 직접 import해 기존 하드코딩 상수값이 그대로임을 확인(회귀 감시)."""
    from whisperlivekit.audio_processor import MIN_DURATION_REAL_SILENCE
    from whisperlivekit.simul_whisper.align_att_base import LANG_DETECT_GENERAL_SECS
    from whisperlivekit.simul_whisper.backend import (
        _NEW_SPEAKER_MAX_KEEP,
        _SCRIPT_ANCHOR_N_WORDS,
        MIN_DURATION_SHORT_LANG_RESET,
    )
    from whisperlivekit.tokens_alignment import (
        FINALIZE_GRACE_SECS,
        MIN_SPEAKER_ATTRIBUTION_SECS,
        PENDING_RESOLVE_CAP,
    )

    assert MIN_DURATION_REAL_SILENCE == 0.4
    assert PENDING_RESOLVE_CAP == 2.0
    assert MIN_SPEAKER_ATTRIBUTION_SECS == 0.5
    assert FINALIZE_GRACE_SECS == 2.0
    assert MIN_DURATION_SHORT_LANG_RESET == 0.5
    assert _NEW_SPEAKER_MAX_KEEP == 5.0
    assert _SCRIPT_ANCHOR_N_WORDS == 3
    assert LANG_DETECT_GENERAL_SECS == 2.0
    # vad_threshold(0.3)는 audio_processor.py 내부 리터럴(이름 붙은 모듈 상수가 없음) —
    # args 필드가 None임은 위 test_no_scenario_all_new_fields_none에서 이미 확인했다.


# ─── 4. 존재하지 않는 --scenario는 argparse 에러(choices 검증) ────────────────

def test_invalid_scenario_raises_system_exit(capsys):
    parser = create_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--scenario", "invalid"])
    capsys.readouterr()  # argparse가 stderr에 usage/에러를 출력 — 캡처만 하고 버림


# ─── 5. apply_scenario_preset 순수 함수 단위 테스트(파서 우회) ────────────────

class _Args:
    """SimpleNamespace 대용 — setattr 가능한 최소 속성 컨테이너."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_apply_scenario_preset_none_scenario_is_noop():
    args = _Args(scenario=None, frame_threshold=None)
    result = apply_scenario_preset(args)
    assert result is args
    assert args.frame_threshold is None


def test_apply_scenario_preset_unknown_scenario_is_noop():
    args = _Args(scenario="doesnotexist", frame_threshold=None)
    apply_scenario_preset(args)
    assert args.frame_threshold is None


def test_apply_scenario_preset_does_not_overwrite_explicit_value():
    args = _Args(scenario="mono", frame_threshold=99, min_real_silence_secs=None, silence_hard_secs=None)
    apply_scenario_preset(args)
    assert args.frame_threshold == 99          # 이미 명시된 값은 보존
    assert args.min_real_silence_secs == 0.6   # 미지정 필드만 프리셋으로 채움
    assert args.silence_hard_secs == 1.8


# ─── 6. --no-speech-threshold (개별 플래그, 프리셋 비대상) ────────────────────
# AlignAttConfig.nonspeech_prob CLI 승격 — 시나리오 프리셋(SCENARIO_PRESETS)에는
# 편입하지 않은 단독 노브라 위 _NEW_TUNING_FIELDS(프리셋이 건드리는 필드 목록)에는
# 넣지 않고 별도 테스트로 검증한다.

def test_no_speech_threshold_flag_sets_config(monkeypatch):
    config = _parse(monkeypatch, ["--no-speech-threshold", "0.3"])
    assert config.no_speech_threshold == 0.3


def test_no_speech_threshold_default_is_none(monkeypatch):
    config = _parse(monkeypatch, [])
    assert config.no_speech_threshold is None


def test_no_speech_threshold_not_in_any_scenario_preset():
    """개별 플래그 전용 노브임을 재확인 — 프리셋에 실수로 편입되면 이 테스트가 잡는다."""
    for scenario_name, preset in SCENARIO_PRESETS.items():
        assert "no_speech_threshold" not in preset, (
            f"scenario={scenario_name} 에 no_speech_threshold가 있으면 안 됨(개별 플래그 전용)"
        )


def test_scenario_presets_dict_keys_are_known_dest_names():
    """SCENARIO_PRESETS의 모든 키가 실제 parse_args CLI dest와 일치하는지 확인.

    dest 이름이 어긋나면 apply_scenario_preset이 존재하지 않는 속성을 조용히
    setattr해버려(getattr 기본값 None) 프리셋이 무음으로 무효화될 수 있다.
    """
    parser = create_parser()
    known_dests = {action.dest for action in parser._actions}
    for scenario_name, preset in SCENARIO_PRESETS.items():
        for key in preset:
            assert key in known_dests, f"scenario={scenario_name} 의 키 {key!r} 가 CLI dest에 없음"
