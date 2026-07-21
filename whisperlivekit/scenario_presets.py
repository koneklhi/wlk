"""배포 음성 상황별 파라미터 프리셋 (Phase A — 방향값, 배포 PC서 미세조정 대상).

각 프리셋은 명시한 필드만 기본값에서 shift한다. 값은 미검증 출발점이다.
"""

SCENARIO_PRESETS = {
    "mono": {  # 단일화자·단일언어·연속낭독 (kor1~3 등)
        "frame_threshold": 20,
        "min_real_silence_secs": 0.6,
        "silence_hard_secs": 1.8,
    },
    "dialogue": {  # 동일언어 2인 교대
        "min_speaker_attribution_secs": 0.4,
    },
    "sequential": {  # 이언어 교대·텀 긺 (순차통역, kinno류)
        "frame_threshold": 18,
        "min_real_silence_secs": 0.3,
        "finalize_grace_secs": 1.2,
    },
    "codeswitch": {  # 이언어 교대·텀 짧음 (ytn2)
        "pending_resolve_cap_secs": 2.4,
        "short_lang_reset_secs": 0.4,
    },
    "multi": {  # 다화자·텀 없이 겹침 (bong1)
        "frame_threshold": 32,
        "min_real_silence_secs": 0.6,
        "vad_threshold": 0.4,
        "silence_hard_secs": 2.0,
        "pending_resolve_cap_secs": 2.5,
        "finalize_grace_secs": 2.8,
        "lang_detect_general_secs": 2.5,
    },
}


def apply_scenario_preset(args):
    """args.scenario가 지정되면, args의 해당 필드가 아직 None(미지정)인 것에만 프리셋 값을 채운다.

    이미 사용자가 개별 플래그로 명시한 값(None이 아닌 값)은 절대 덮어쓰지 않는다 — 우선순위:
    개별 플래그 > 프리셋 > 기본상수.
    """
    scenario = getattr(args, "scenario", None)
    if not scenario:
        return args
    preset = SCENARIO_PRESETS.get(scenario)
    if preset is None:
        return args
    for key, value in preset.items():
        if getattr(args, key, None) is None:
            setattr(args, key, value)
    return args
