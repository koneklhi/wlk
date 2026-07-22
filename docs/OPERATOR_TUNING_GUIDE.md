# 배포 상황별 파라미터 튜닝 가이드 (Operator Tuning Guide)

> **대상 독자**: 폐쇄망 배포 PC 운영자 — 실제 배포 현장의 음성 상황(화자 수·언어 전환 패턴·발화 텀)에 맞춰
> 서버 시작 플래그를 조정하려는 사람. 코드 변경 없이 CLI 인자만으로 조정 가능한 knob과, 그것을 상황별로
> 묶은 프리셋(`--scenario`)을 정리한다.
> **범위(Phase A)**: 이 문서는 **터미널 startup 시점 제어**만 다룬다 — 서버를 기동할 때 CLI로 값을 정하면
> 그 세션(그 서버 프로세스가 살아있는 동안) 고정된다. 런타임 중 UI에서 바꾸거나 세션별로 다르게 주는
> 기능(Phase B)은 아직 없다 — §6 참조.
> **프리셋 수치의 성격**: 아래 프리셋 값은 **미검증 방향값 출발점**이다. 정밀 측정(경로 C 채택 확정
> 루틴)을 거치지 않았고, CLAUDE.md §3.8이 요구하는 정량 개선 근거도 없다 — 배포 PC에서 운영자가 실제
> 음성으로 들어보며 미세조정하는 것을 전제로 한 시작점이다.

---

## 1. 개요

WhisperLiveKit 기반 STT는 하나의 디코더 파라미터 세트로 모든 음성 상황에 동시에 최적일 수 없다.
예를 들어 침묵 경계에 의존해 문장을 끊는 로직은 **발화 텀이 긴 순차통역**(한 사람이 말을 마치고
쉬었다가 다음 사람이 말하는 상황)에서는 잘 동작하지만, **텀 없이 화자가 겹치거나 짧게 주고받는
상황**(bong1류 다화자 토론)에서는 침묵 신호 자체가 거의 뜨지 않아 화자·언어 신호에 더 의존해야
하고, 조기 확정을 억제하는 쪽으로 파라미터를 옮겨야 한다. 반대로 순차통역 상황에 다화자용 보수적
설정을 그대로 쓰면 불필요하게 지연이 커진다.

지금까지 이 트레이드오프는 코드 내 하드코딩 상수로만 존재했다(`tokens_alignment.py`,
`simul_whisper/backend.py`, `simul_whisper/align_att_base.py`, `audio_processor.py` 등에 흩어진 상수들).
Phase A는 이 상수들 중 문장 확정·화자 귀속·언어 재감지에 관여하는 9개 + 기존 `--frame-threshold`·
`--silence-hard-secs`를 **CLI 플래그로 승격**하고, 상황별로 묶어 적용하는 `--scenario` 프리셋을
추가했다. 코드 변경 없이 서버 기동 명령만으로 운영자가 상황에 맞춰 조정할 수 있게 하는 것이 목적이다.

**무회귀 보장**: `--scenario` 미지정 + 개별 플래그도 전부 미지정이면, 신규 필드가 모두 `None`이라
기존 마스터와 100% 동일하게 동작한다(각 소비 지점이 기존 하드코딩 상수로 폴백). 이 기능은 §3.1(폐쇄망)·
§3.2(한/영 두 언어 고정) 같은 불변 제약을 실전에서 더 잘 지키기 위한 **운영자 제어 기능**이며, 그 자체로
WER/F1 정량 개선을 주장하지 않는다.

---

## 2. 파라미터 방향 범례

각 knob이 무엇을 조정하며, 어느 방향으로 움직이면 어떤 상황에 유리한지 정리한다. "현재값"은 관련
플래그를 아무것도 안 줬을 때 폴백되는 기존 하드코딩 상수값이다.

| CLI 플래그 | 현재값(폴백) | 정의 위치 | ↑ 효과 | ↓ 효과 |
|---|---|---|---|---|
| `--lan ko\|en\|auto` (기존 플래그) | `auto` | `parse_args.py` | — | — (세션 언어모드 자체를 정하는 가장 큰 레버. `ko`/`en` 고정 시 코드스위칭 재감지 로직 전부 비활성, `auto`는 한↔영 자동전환 지원. CLAUDE.md §3.2 참조) |
| `--diarization`/`--no-diarization` (기존 플래그) | `True`(ON) | `parse_args.py` | — | — (화자분할 자체의 on/off. 다화자 상황엔 필수, 단일화자면 꺼서 오버헤드·오탐 여지를 줄일 수 있음) |
| `--frame-threshold` | `25`(프레임, 1프레임=0.02s) | `config.py:59` (`WhisperLiveKitConfig.frame_threshold`) | 보수적·저환각·고지연 (겹침·다화자 유리) | 저지연·고환각 위험 (텀이 긴 순차통역 유리) |
| `--min-real-silence-secs` | `0.4`s | `audio_processor.py:29` (`MIN_DURATION_REAL_SILENCE`) | 짧은 숨 무시 (겹침 유리) | 침묵마다 잘게 분리 (순차통역 유리) |
| `--vad-threshold` | `0.3` | `audio_processor.py:106` (Silero VAD `FixedVADIterator`) | 잡음을 발화로 오판하는 빈도 감소 (겹침·소음 환경 유리) | 더 민감하게 발화 감지 |
| `--silence-hard-secs` | `1.2`s (≤2.0s 상한 불변식) | `tokens_alignment.py:73` (`SILENCE_HARD_SECS`) | 문장 중간 강제분리 억제 (Case B 방지 쪽 여유) | 침묵을 빨리 안전망 분할로 간주 |
| `--pending-resolve-cap-secs` | `2.0`s | `tokens_alignment.py:79` (`PENDING_RESOLVE_CAP`) | 애매한 경계를 오래 보류 (겹침 유리) | 빨리 확정 |
| `--min-speaker-attribution-secs` | `0.5`s | `tokens_alignment.py:89` (`MIN_SPEAKER_ATTRIBUTION_SECS`) | 짧은 diar 세그먼트의 화자 플립을 억제 (겹침 상황 diar 노이즈 방어) | 짧은 발화도 화자전환으로 신뢰 (빠른 교대 포착) |
| `--finalize-grace-secs` | `2.0`s | `tokens_alignment.py:36` (`FINALIZE_GRACE_SECS`) | 확정을 늦춰 유보 (지연 도착 꼬리에 안전) | 즉시 확정 (지연은 짧아지나 유보 꼬리 놓칠 위험) |
| `--short-lang-reset-secs` | `0.5`s | `simul_whisper/backend.py:39` (`MIN_DURATION_SHORT_LANG_RESET`) | 긴 침묵에만 언어 재감지 | 짧은 침묵에도 재감지 (빠른 코드스위칭 유리) |
| `--script-anchor-n-words` | `3`단어 | `simul_whisper/backend.py:203` (`_SCRIPT_ANCHOR_N_WORDS`) | 연속 반대-스크립트 단어를 더 많이 요구 → 언어전환 오탐 감소 (노이즈 많은 겹침 상황 유리) | 적은 단어로도 전환 인정 → 빠른 전환을 즉시 포착 (오탐 위험↑) |
| `--new-speaker-max-keep-secs` | `5.0`s | `simul_whisper/backend.py:51` (`_NEW_SPEAKER_MAX_KEEP`) | 화자전환 시 재디코딩용 onset 문맥을 더 길게 보존 (빠른 교대에서 초반 단어 유실 방지 유리) | 문맥 짧게 유지 (환각 위험 감소 방향이나 초반 단어 유실 위험 상승 — Exp-171 이전 keep=4.5s 환각 전례 있음, 모니터 필요) |
| `--lang-detect-general-secs` | `2.0`s | `simul_whisper/align_att_base.py:50` (`LANG_DETECT_GENERAL_SECS`) | 보수적 재감지 (오탐↓) | eager (텀 긴 순차통역 유리, 오탐 위험↑). 화자전환 직후 eager 분기(1.5s+확신도 0.85 이상)는 이 값과 무관하게 별도 동작 |
| `--no-speech-threshold` | `0.5` | `simul_whisper/config.py:15` (`AlignAttConfig.nonspeech_prob`) | 무음 판정 기준이 엄격해짐(no-speech 확률이 더 커야 무음으로 걸림) → 세그먼트 디코딩이 잘 안 멈춤, "Thank you" 류 필러 환각 위험↑ | 무음 판정이 관대해짐(더 낮은 확률로도 무음 인정) → 세그먼트 디코딩이 쉽게 멈춰 필러 환각↓ (단, 작게 말한 실제 발화까지 잘릴 위험 상승) |

**정합성 노트**: `--frame-threshold`를 크게 올려 디코딩을 더 보수적으로 만들면(겹침·다화자 대응), 그만큼
확정까지 걸리는 시간도 늘어나므로 `--finalize-grace-secs`도 함께 키우는 편이 정합적이다 — 유예창이
디코딩 지평보다 짧으면 아직 안 나온 꼬리를 유예 없이 확정해버릴 수 있다.

**`--no-speech-threshold` 비고**: 위 표의 다른 9개 knob과 달리 `--scenario` 프리셋 대상이 아니다(개별
플래그로만 조정 가능, §3/§4 프리셋 매트릭스에는 반영되지 않음) — 필러 환각 대응이라는 단일 목적의
개별 노브로 승격됐다.

---

## 3. 상황별 매트릭스

| 상황(`--scenario`) | 설명 | 대표 데이터 | 목표 | 권장 `--lan` |
|---|---|---|---|---|
| `mono` | 단일화자·단일언어·연속낭독 | kor1~3 | 침묵 경계를 촘촘히 잡아 문장을 짧게 끊는다 | 콘텐츠 언어를 알면 `ko`/`en` 고정(재감지 오버헤드 제거), 불확실하면 `auto` |
| `dialogue` | 동일언어 2인 교대 | 동일언어 대담류(전용 테스트 데이터 미보유, 상황 정의 참고용) | 짧은 발화에서도 화자전환을 신뢰해 교대 경계를 잡는다 | `ko`/`en`(2인 모두 동일언어이므로 고정 권장) |
| `sequential` | 이언어 교대·텀 긺(순차통역) | kinno류 | 침묵 텀이 넉넉하므로 저지연·저보수 디코딩으로 빠르게 확정 | `auto`(한↔영 교대이므로 원칙적으로 필요) |
| `codeswitch` | 이언어 교대·텀 짧음 | ytn2 | 침묵이 잘 안 뜨므로 언어전환 재감지를 민감하게, 애매한 경계는 좀 더 보류 | `auto`(짧은 텀 코드스위칭 자체가 `auto`의 존재 이유) |
| `multi` | 다화자·텀 없이 겹침 | bong1 | 침묵 신호가 거의 없으므로 화자·스크립트 신호 + 보수적 확정에 의존 | `auto`(bong1처럼 두 언어 화자가 섞여 있으면 필수) |

### 핵심 긴장 — 텀 길이가 신호 선택을 가른다

이 5개 상황을 관통하는 축은 **발화 사이 텀(pause)의 유무·길이**다.

- **텀이 길수록**(`sequential`) 침묵(VAD pause) 신호에 안전하게 의존할 수 있다 — 한 사람이 말을
  마치고 침묵이 생긴 뒤 다음 사람이 말하므로, 침묵 경계만으로도 문장·화자 분리가 대체로 맞아떨어진다.
  이 여유를 이용해 `frame_threshold`를 낮추고 `min_real_silence_secs`도 낮춰 저지연으로 갈 수 있다.
- **텀이 짧거나 화자가 겹칠수록**(`codeswitch`, `multi`) 침묵이 거의 뜨지 않는다 — 이때 침묵에만
  의존하면 화자·언어 전환 경계를 놓친다. 대신 화자분할(diar) 신호, 스크립트(문자 체계) 전환 신호,
  그리고 애매한 경계를 더 오래 보류해 다음 맥락을 보고 판단하는 보수적 확정(`pending_resolve_cap_secs`↑,
  `finalize_grace_secs`↑, `frame_threshold`↑)에 더 의존해야 한다.

`mono`·`dialogue`는 이 축에서 비교적 예외적인 위치다 — 언어 전환 자체가 없거나(mono) 화자 수가
적어(dialogue) 신호가 단순하므로, 상대적으로 가벼운 조정만으로 충분하다.

---

## 4. 프리셋 값 테이블

값 SoT는 [whisperlivekit/scenario_presets.py](../whisperlivekit/scenario_presets.py)다. `—`는 그
프리셋이 해당 knob을 건드리지 않는다는 뜻(기본값 유지 = 위 §2 "현재값" 그대로).

| knob | `mono` | `dialogue` | `sequential` | `codeswitch` | `multi` |
|---|---|---|---|---|---|
| `frame_threshold` | `20` | — | `18` | — | `32` |
| `min_real_silence_secs` | `0.6` | — | `0.3` | — | `0.6` |
| `silence_hard_secs` | `1.8` | — | — | — | `2.0` |
| `vad_threshold` | — | — | — | — | `0.4` |
| `min_speaker_attribution_secs` | — | `0.4` | — | — | — |
| `finalize_grace_secs` | — | — | `1.2` | — | `2.8` |
| `pending_resolve_cap_secs` | — | — | — | `2.4` | `2.5` |
| `short_lang_reset_secs` | — | — | — | `0.4` | — |
| `lang_detect_general_secs` | — | — | — | — | `2.5` |
| `script_anchor_n_words` | — | — | — | — | — |
| `new_speaker_max_keep_secs` | — | — | — | — | — |

> **다시 강조: 이 값은 미검증 방향값 출발점이다.** 경로 C 채택 확정 측정(CLAUDE.md §4, N≥3)을 거치지
> 않았다 — 배포 PC에서 실제 음성으로 들어보며 미세조정하는 것을 전제로 한다. 특히 `mono`/`sequential`의
> `frame_threshold`를 낮춘 것과 `multi`의 `frame_threshold`·`finalize_grace_secs`를 크게 올린 것은
> §2 방향 범례 표의 논리를 따라 설계된 값이지 측정으로 확정된 값이 아니다.

---

## 5. 사용법

**프리셋만 적용**(가장 단순한 경우):

```powershell
python -m whisperlivekit.basic_server --scenario multi
```

**프리셋 + 개별 플래그로 특정 값만 override**: 명시한 개별 플래그가 항상 프리셋 값보다 우선한다.

```powershell
# multi 프리셋을 쓰되 frame_threshold만 40으로 더 보수적으로
python -m whisperlivekit.basic_server --scenario multi --frame-threshold 40
```

**우선순위**: 개별 플래그 > `--scenario` 프리셋 > 각 소비 지점의 기존 하드코딩 상수(둘 다 미지정 시).

**세션 언어모드(`--lan`)는 프리셋과 별개로 직교하게 지정한다** — §3의 "권장 `--lan`" 열 참조. 예를 들어
`codeswitch` 상황을 `--lan auto`와 함께 쓰려면:

```powershell
python -m whisperlivekit.basic_server --scenario codeswitch --lan auto
```

폐쇄망 배포 PC(venv 없음, 전용 Python)에서는 인터프리터를 직접 지정한다
([DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md) §4 참조):

```powershell
C:\Python312\python.exe -m whisperlivekit.basic_server --scenario multi
```

---

## 6. 향후 (Phase B — 이번 범위 밖)

Phase A는 터미널 startup 제어만 다룬다. 향후 검토 대상(미착수): 배포 UI에 상황 프리셋 셀렉터를 추가해
운영자가 서버 재기동 없이 화면에서 상황을 고를 수 있게 하는 것, `/asr` 연결에 `?scenario=` 같은 세션별
쿼리 오버라이드를 추가하는 것(단 SimulStreaming 엔진 싱글턴이 baked param을 갖는 구조라 완전한 세션별
런타임 전환은 엔진 재구성 또는 재시작이 필요할 수 있다는 제약이 있다), 그리고 이미 구현돼 있는
`/v1/listen`(Deepgram 호환)의 JSON 제어채널 패턴을 `/asr`에도 이식해 연결 후 메시지로 설정을 갱신하는
안이다.
