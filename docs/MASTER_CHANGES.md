# master 최종본 — upstream 대비 전체 변경 요약

> **이 문서의 목적**: `whisperlivekit` upstream 0.2.20 대비 **현재 master 브랜치에 반영된 모든 변경**을
> 도메인별로 증류해 설명한다. 실험 시행착오는 3계층에 있다 — [../EXPERIMENTS.md](../EXPERIMENTS.md)(STATE·요약/epoch), [../EXPERIMENTS_LOG.md](../EXPERIMENTS_LOG.md)(LOG·Exp-131~ 서술), [../PHASE2_EXPERIMENTS.md](../PHASE2_EXPERIMENTS.md)(ARCHIVE·Exp-001~130).
> 이 문서는 master의 **최종 상태만** 담는다.
>
> **갱신 주기**: 채택 실험을 master에 머지한 직후 `/update-master-changes` 슬래시 커맨드로 갱신한다.

> ⚠️ **플래그 (2026-07-05)**: `model_dir` 배선 버그로 이 문서가 서술하는 STT 모델 표기(turbo)와 실측 기준(base, Exp-158 이전 전체)이 불일치했음이 확인됨(Exp-158). 두 수정(model_dir 배선 + no_grad stall)은 master에 머지됨(`9e3217e`) — 이 문서 전체를 `/update-master-changes`로 재실행해 turbo 기질(E5) 기준으로 갱신 필요(후속 작업).

---

## 1. 개요

### 상위 라이브러리 / 베이스라인

| 항목 | 값 |
|---|---|
| 상위 라이브러리 | [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) (Quentin Fuxa) |
| 벤더링 버전 | `0.2.20` (in-tree 사본, `pyproject.toml` `version` 참조) |
| 복구 방법 | `pip download whisperlivekit==0.2.20` 또는 upstream 태그 `v0.2.20` diff |
| 우리 변경 표식 | `whisperlivekit/` 내 **한글 주석** 포함 파일 = 우리가 수정한 파일 (CLAUDE.md 규약) |
| 신규 추가 모듈 | `filtering/`, `llm_translation/`, `metrics.py`, `scripts/eval.py` 등 |
| STT 모델 | `whisper-large-v3-turbo` (로컬 경로 `whisperlivekit/model/whisper-large-v3-turbo/`) |

### 변경 목적

기존 upstream은 일반 목적 실시간 STT 라이브러리다. 우리 시스템은:
- **한국어 / 영어 두 언어**만 처리하는 폐쇄망 환경 (§3.1/§3.2)
- **코드스위칭** (한↔영 혼용 발화) 처리
- **문장 단위 확정** → React UI 연동 + 번역 트리거
- **번역·필터링·사전 교정** 기능 통합

upstream 기본값만으로는 반복 아티팩트(`바 바 바`), 언어 고착, WER 100% 초과가 발생했다.
아래 변경들이 이를 해소한다.

---

## 2. 현재 채택 베이스라인 수치 (Exp-179 — 2026-07-15, E5 turbo·diar-ON)

> **채택 기준** (CLAUDE.md §4): **1순위 = max(최악 케이스) 미회귀, 2순위 = median 개선**.
> 수치는 경로 C(VBCable 루프백) **채택 확정(N≥3) 반복 측정 결과** — `median / max / stdev`.
> 현행 regime: **테스트 = bong1+ytn2+sbs1(diar-ON, Sortformer, CRT=3.0, PLC=None, turbo)**,
> **held-out = ytn1+eng1(단회) + kinno(정성 sanity)**. 중간 채택 이력은 [../EXPERIMENTS.md](../EXPERIMENTS.md) 참조.
> JSON: 워크트리 `session-start-lang-probe/.omc/benchmarks/eval_confirm_{test3_N3,kor_N3,kinno_N3,heldout}.json`.

| 파일 | 설정 | WER median | WER max | stdev | 화자분리 F1 med | 문장분리 F1 med |
|---|---|---|---|---|---|---|
| bong1 | diar-on | **34.4%** | 39.9%\* | 5.9% | 60.5% | 23.1% |
| ytn2 | diar-on | **17.7%** | 30.0% | 7.9% | 72.7% | N/A |
| sbs1 | diar-on | **10.1%** | 15.5% | 3.5% | 80.0% | 84.2% |
| kinno (정성 sanity, 게이팅 제외) | diar-on | 31.7% | 39.4%\*\* | 4.6% | 71.0% | 40.0% |
| ytn1 (held-out, 단회) | diar-on | **12.3%** | — | — | 73.7% | 50.0% |
| eng1 (held-out, 단회) | diar-on | **2.9%** | — | — | 100.0% | 100.0% |

\* bong1 max 39.9는 기존 필러/웃음 환각 변동 모드(Exp-159/168/171/174 반복 관측) — 해당 3회차 전부 프로브 발동 0회(코드 경로 master 동일)로 Exp-179 변경과 무관.
\*\* kinno는 Exp-177(N=3) max 72.0%였던 catastrophic이 본 라운드에서 미재현(단 프로브 발동 0회라 개선 귀속은 불가).
> 신규 진단 데이터 **kor1~3**(한국어 단독 낭독체, 정식 테스트셋 미편입): kor1 44.4/46.2%(프로브 표적 — OFF 51.5/62.0 대비 개선), kor2 95.8%(§8 철자낭독 결함 지배), kor3 68.9%.

**참고: upstream 0.2.20 기본값 (Exp-000 베이스라인, 2026-06-04)**

| 파일 | WER | F1 | 비고 |
|---|---|---|---|
| sbs1 | 108.3% | 0.0% | 반복 아티팩트로 WER >100% |
| ytn1 | 47.9% | 0.0% | — |

---

## 3. STT 전사 품질 변경

### 3-1. 디코딩 정책 — SimulStreaming 채택 (Exp-000/001)

| 항목 | upstream 기본값 | 우리 변경 |
|---|---|---|
| 백엔드 정책 | LocalAgreement (기본값) | **SimulStreaming(AlignAtt+CIF)** 고정 |
| 근거 | LocalAgreement는 영어 코드스위칭을 통째로 누락하고 발화 후반부 커버리지를 잃는 구조적 문제 | SimulStreaming의 반복 아티팩트는 후처리로 보완 가능 |

설정: [`parse_args.py`](../whisperlivekit/parse_args.py) `--backend-policy` 기본값 = `simulstreaming`.

---

### 3-2. 반복 / 환각 억제 필터 (Exp-002/028/057/086/090)

upstream `_filter_repetitions()`는 **단일 `update()` 배치 내부**에서만 동작해, 토큰이 1개씩 도착하는
실시간 스트리밍에서 배치 경계 반복(`바/바/바`)이 살아남았다.

**추가된 필터 (모두 [`simul_whisper/backend.py`](../whisperlivekit/simul_whisper/backend.py))**:

| 필터 | 상수 / 파라미터 | 동작 | 도입 |
|---|---|---|---|
| Cross-batch 동일 단어 필터 | `_last_emitted_word` | 직전 방출 단어와 동일하면 드롭 | Exp-002 |
| 단일음절 연속 반복 억제 | `_CHAR_RUN_THRESHOLD = 4` (max_char_run ≥ 4) | 연속 n회 이상 시 context 리셋 (`_HALLUCINATION_RESET_THRESHOLD = 5`) | Exp-028 |
| 배치 내 4-word 반복 드롭 | `_filter_cross_batch_repetitions()` | 한글 4회 이상 연속 반복 토큰 제거 후 context 리셋 | Exp-057 |
| 온점/대시 시각 버그 수정 | `LeadingPunctFilter`, `DashFilter` | 선두 온점·대시 아티팩트 제거 | Exp-086 |
| `_detect_repetition_loop` 제거 | 전체 제거 (−34줄) | 밀도 기반 false positive였던 Exp-009 잔재 청산 | Exp-090 |

또한 디코더 **stall(멈춤) 복구**: 오디오가 `STALL_RECOVER_SEC = 10.0`초 이상 진행했는데 토큰 미방출 시
`refresh_segment()` 강제 호출로 복구. (`backend.py` 상단 상수)

---

### 3-3. 불완전 UTF-8 토큰 부분 emit 차단 (Exp-087)

| 항목 | upstream | 우리 변경 |
|---|---|---|
| 동작 | 미완성(`�`) 단어도 바로 방출 → 선두 음절 중복 발생 | `_build_timestamped_words()` — `�` 포함 단어 emit 스킵 |
| 파일 | [`simul_whisper/align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py) | 동일 |
| 효과 | sbs1 선두-중복 6/6 run 완전 소멸, WER **43.0% → 20.6%** | — |

---

### 3-4. 디코딩 파라미터 튜닝 (Exp-075/080)

upstream 기본값에서 아래 파라미터를 변경했다:

| 파라미터 | upstream 기본값 | 우리 값 | 파일 / 옵션 | 도입 |
|---|---|---|---|---|
| `--beams` (beam_size) | 1 (greedy) | **2** | [`parse_args.py`](../whisperlivekit/parse_args.py) `default=2` | Exp-080 |
| `--vac-chunk-size` | 0.1s | **0.2s** | `parse_args.py` `default=0.2` | Exp-075 |
| `max_context_tokens` | None | **0** | `AlignAttConfig` / `--max-context-tokens 0` | Exp-075 |
| VAD threshold | 0.5 | **0.3** | [`audio_processor.py`](../whisperlivekit/audio_processor.py) VAD 설정 | Exp-007 |
| MIN_DURATION_REAL_SILENCE (오디오 레벨) | 0.5s | **0.4s** | `audio_processor.py:29` | Exp-075 |

> `MIN_DURATION_REAL_SILENCE = 0.4` (audio_processor) — VAD Silence 토큰을 transcription queue에 넣는 기준.
> `MIN_DURATION_REAL_SILENCE = 2` (backend.py:36) — 언어 재감지를 트리거하는 기준(별도 임계값).

beam_size=2 효과: WER **33.2% → 31.4%** (Exp-080), 이후 누적 개선으로 현재 14.6%.

---

### 3-5. 품질 게이트 추가 (Exp-104)

upstream에 없는 두 게이트를 새로 추가했다 ([`parse_args.py`](../whisperlivekit/parse_args.py)):

| 게이트 | 옵션 | 기본값 | 역할 |
|---|---|---|---|
| avg-logprob 게이트 | `--logprob-threshold` | **-2.0** (Exp-142 채택) | 낮은 신뢰도 세그먼트 억제. E2 코드에서 bong1/ytn2/sbs1 WER 전부 개선 확인 (실제 플래그명은 `--logprob-threshold`, dest=`logprob_threshold`) |
| compression-ratio 게이트 | `--compression-ratio-threshold` | **3.0** (Exp-104 채택) | 반복 세그먼트 억제. 언어 무관 반복 환각 백스톱으로 안전. |

> avg-logprob 게이트: E1 Exp-104에서 기각됐으나 E2(lang_restrict_koen 도입 후) Exp-142에서 -2.0으로 재검증, 채택. E1 결론은 epoch 상이로 적용 불가(§4 epoch 게이트).
> compression-ratio 3.0은 언어 무관 반복 환각 백스톱으로 안전 — 유지.

---

### 3-6. 언어 재감지 / 코드스위칭 대응 (Exp-093/101/105)

upstream의 **언어 TRIPLE-LOCK** 문제 해소:
- `detected_language` 한 번 결정 → 이후 변경 불가
- `first_timestamp` 게이트 통과 후 재감지 비활성
- 결과: 한↔영 코드스위칭 시 언어 고착 → 잘못된 토크나이저로 전사

**Exp-093 — 침묵 기반 재감지** ([`backend.py:36,85-105`](../whisperlivekit/simul_whisper/backend.py)):
- `MIN_DURATION_REAL_SILENCE = 2` (upstream 5→2)
- 2초 이상 침묵(`long_silence`) 시 `detected_language = None`, `first_timestamp = None` 리셋 → 다음 청크에서 강제 재감지
- 효과: ytn1 max WER **108.0% → 22.7%** (catastrophic 완전 제거)

**Exp-101 — 짧은 pause 후 최근 창 재감지** ([`backend.py`](../whisperlivekit/simul_whisper/backend.py), [`align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py)):
- `MIN_DURATION_SHORT_LANG_RESET = 0.5s` — 0.5초 이상 침묵 후 1.5초 오디오 누적 시 `detect_current_language(window_secs=1.5, min_prob=0.90)` 호출
- `_check_short_silence_language()` — 언어 변경 감지 시 경량 리셋 (버퍼 유지, context 유지)
- `detect_current_language()` — `align_att_base.py` 신규 메서드. 최근 window_secs 오디오만 슬라이싱해 언어 감지 (화자 전환 시 이전 화자 오디오 배제)

**Exp-105 — 주기적 재감지 + ForeignLang 즉시 트리거** ([`align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py), [`backend.py`](../whisperlivekit/simul_whisper/backend.py)):
- `_maybe_periodic_lang_check(audio_end_secs)` — 4.0s마다 (`--periodic-lang-check 4.0`) 최근 2.0s 창 언어 감지, 히스테리시스 3s
- `_FOREIGN_LANG_PATTERN = re.compile(r'\(speaking in foreign language', re.IGNORECASE)` — 이 패턴 방출 시 `detected_language = None` 즉시 리셋
- 관련 설정 필드: `AlignAttConfig.periodic_lang_check_secs`, `decoder_state.last_periodic_lang_check`, `decoder_state.last_lang_switch_time`
- 권장 실행: `--periodic-lang-check 4.0` (기본값=None, 비활성)

**Exp-104 — diar-off `first_timestamp` 조건부 게이트 복원** ([`align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py)):
- diarization-spike 브랜치가 eager 재감지를 위해 `first_timestamp` 게이트를 전면 제거했다가 diar-off에서 ytn1 156% 폭주 유발
- 수정: `elif eager_lang_detect` (diar-on 전용) / `else: return` (diar-off silence는 first_timestamp까지 보류)

---

### 3-6b. 언어 전환 프로토콜 재설계 + SOT 배선버그 수정 (Exp-150, E3)

3-6의 재감지가 **감지**는 하되 전환 실행에 두 결함이 있었다:
- **전환 세금**: `_apply_detected_language`가 디코딩 상태만 리셋하고 오디오 버퍼는 유지 → 버퍼 전체가 새 언어로 재디코딩되어 방출 완료 단어가 재방출.
- **SOT 배선버그**: `_check_short_silence_language`가 `create_tokenizer`+`init_context`만 호출하고 `init_tokens()`를 누락 → SOT 언어 토큰이 옛 언어로 잔존, 감지만 되고 디코딩 미적용.

**변경** ([`align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py), [`backend.py`](../whisperlivekit/simul_whisper/backend.py), [`timed_objects.py`](../whisperlivekit/timed_objects.py), [`tokens_alignment.py`](../whisperlivekit/tokens_alignment.py)):
- `_apply_detected_language(lang, skip_trim)`: 진짜 전환(prev≠new) 시 `_trim_segments_to_recent(LANG_SWITCH_KEEP_SECS=2.5)`로 전환 경계 오디오만 남기고 절단(`cumulative_time_offset` 보정) → 재디코딩 대상 최소화(전환 세금 제거). 이어 `init_tokens()`(SOT 갱신)/`init_context()`.
- `_check_short_silence_language`가 위 메서드로 위임 → SOT 언어토큰 실제 갱신.
- `LanguageSwitch` 마커(`timed_objects.py`, `is_boundary()=True`, `text=''`): 전환 시 `process_iter`가 삽입 → `tokens_alignment`가 침묵 세그먼트 없이 문장 경계로 소비. 번역 큐 미전달, FrontData 직렬화 제외(**스키마 무변**).
- 중복 `detect_current_language`(dead code) 제거. `decoder_state.pending_language_switch` 필드 추가.

**효과 / 적용 범위**: diar-OFF 대조에서 SOT 수정이 반복루프 폭주(ytn2 135%→53%, avg -24.6pp)를 차단 — §3.2 한/영 강제 catastrophic 방지. **diar-ON(기본 운영)에서는 `new_speaker`가 언어전환을 선점해 트림/마커 경로가 미발동(dormant)**했음(WER 변산 내 중립); 정합 groundwork로 유지 → **Exp-153이 배선으로 활성화(아래 E4)**. **Epoch E2→E3.**

**연계 잠복버그 수정 (Exp-151, `8b83403`)**: 위 발견에서 드러난 master 기존 결함 2건 수정.
- `refresh_segment(complete=True)`가 `global_time_offset`을 미승계 → mid-stream refresh(QualityGate·환각필터·stall) 후 타임스탬프 드리프트 → 문장경계 F1 저하. **수정**: 버려진 오디오 길이만큼 `global_time_offset` 승계(`old_segments_len - segments_len()` + `cumulative_time_offset`) 후 cumulative 리셋. WER 무관, F1 정합 회복.
- `_maybe_periodic_lang_check`가 버퍼상대시간(`segments_len`)을 시계로 써서 PLC 미발동 → 절대 스트림 시각(`global_time_offset + segments_len()`)으로 수정. PLC=None 기본이라 운영 무영향.
- diar-ON N=3 무회귀(avg 26.9%, 전 파일 max 게이트 내). 단위테스트 `tests/test_timebase_refresh.py`.

**diar-ON 배선 활성화 (Exp-153, `dc312bb`, E3→E4)**: 위 트림/마커가 diar-ON에서 dormant였던 2원인 배선.
- **원인 A** — `new_speaker`가 `detected_language=None` 리셋 **후** `_apply_detected_language` 호출 → `prev_lang`이 항상 None → `is_switch` 영구 False. **수정**: `decoder_state`(+`mlx/decoder_state`)에 `lang_before_reset` 필드, 리셋 전 언어 보존(연속 화자전환 or-체이닝), `_apply_detected_language`가 `detected_language or lang_before_reset`로 폴백(consume-once, `end_silence` long서 clear).
- **원인 B** — `get_lines_diarization` 병합 루프가 같은 화자면 무조건 재병합 → 전환 경계 소실. **수정**: `PuncSegment.hard_boundary`(to_dict 미직렬화 → **스키마 무변**), boundary 세그먼트서 True, 병합 조건 `and not segments[-1].hard_boundary` + 병합 시 승계.
- **효과(N=3 diar-ON)**: 전환경계 단어보존 획득(§3.2/Q4), ytn2 worst-case WER 29.1→26.1·stdev 0.5로 안정화. 단 재디코딩 오버랩서 filler 환각 신규(ytn2 en→ko "You know, in Bukhpil"류 R1-3 일관·bong1 R3 "sorry"×9)·마커 과분할로 F1 하락(2차 지표). WER(1차) 게이트 통과·eng1 무회귀 → **채택(사용자 결정, 게이트 혼합)**. **Epoch E3→E4.** 단위테스트 `tests/test_lang_switch_wiring.py`(14). 후속: filler 튜닝(`LANG_SWITCH_KEEP_SECS` 오버랩 축소)·Exp-154 PLC 재평가.

---

### 3-6c. 스크립트-앵커 재감지 게이트 (Exp-175, E5)

**upstream/기존 동작**: 언어 재감지 트리거 4종(짧은침묵≥0.5s·긴침묵≥2.0s·화자전환 eager·PLC=기본 None 비활성)이
**무음·화자전환 없는 연속 코드스위칭**에서 전부 미발동 → 구언어 고착 → 새 언어 서두 오디코드/유실(Exp-172에서
bong1 "You don't understand" 4단어 유실로 실측 확정) + `LanguageSwitch` 마커 미생성으로 한↔영 같은 line 접착.

**우리 변경** ([`backend.py`](../whisperlivekit/simul_whisper/backend.py) 단일 파일 + 테스트):
- 실제 방출 토큰의 스크립트가 잠긴 `detected_language`와 **연속 N=3단어 또는 T=1.0s 반전 유지**(Exp-172 실측 임계) 시
  `detect_current_language(2.0s, p≥0.90)` 재감지 트리거 — `_update_script_anchor_streak`/`_apply_script_anchor_redetect`.
- **다른 언어 확신 시에만** `_apply_detected_language`(트림+마커 arm+retract arm+retract_floor — Exp-174 메커니즘 재사용)
  + 해당 배치 드롭(트림이 남긴 경계 오디오 재디코딩으로 복구). 같은 언어 재확정 시 no-op(Exp-169 재환각 루프 방지),
  불확신(None) 시 streak 유지 재시도. `refresh_segment` 미호출(Exp-163 회귀 교훈).
- 판정은 `tokens_alignment._is_opposite_script` 재사용(TTR 게이트 없는 순수 스크립트, ko↔en 대칭·§3.8 하드코딩 없음).
  같은 스크립트 토큰이 섞이면 streak 리셋("I think 그건"류 정상 삽입 오탐 방어), 숫자·기호는 중립 스킵.
- 삽입점: `process_iter` ScriptMismatchFilter 직후·AnchorRepeatFilter 앞. streak 리셋 합류: 긴침묵·`new_speaker`·기존
  게이트 발동 직후. 롤백 플래그 `SCRIPT_ANCHOR_REDETECT_ENABLED`(모듈 상수). 출력 스크립트 반전에만 반응하므로
  확률 기반 주기 체크(PLC)의 스퓨리어스 전환(Exp-160)에 면역.

**성능/이유**: 짝지음 master↔브랜치 A/B 18런으로 **WER 완전 중립** 확인(발동 희소, 미발동 시 수동 관찰자) —
성격은 "평상시 중립 + 방출형 코드스위칭 서두유실 모드 제거"(§3.8 worst-case 우선). 발동 회차 전수 정당(오탐 0,
eng1 영어 단일언어 포함), Exp-172 확정 유실 사례 직접 복구 실측, diar 이벤트(1~2s 지연)보다 선제 발동.
N 스윕: N=2 오트리거(정상 2단어 삽입) 실증·N=4 미발동(커버리지 상실) → N=3 유지.

**핵심 파일**: [`backend.py:170-188`](../whisperlivekit/simul_whisper/backend.py)(상수)·`:532-618`(메서드 3개)·`:682`(삽입점),
단위테스트 `tests/test_script_anchor_redetect.py`(17). **도입 Exp-175** (머지 `c3302a2`). 파라미터 상세는
[SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) §3.2 진입점 5·§5 표(잠정 태그).

---

### 3-6d. 세션 초입 언어 프로브 (Exp-179, E5)

**upstream/기존 동작**: `--lan auto`에서 언어감지가 `first_timestamp`(첫 토큰 커밋)를 기다리는 동안 토크나이저가
`<|en|>` 기본값으로 고정([`whisper/tokenizer.py:389`](../whisperlivekit/whisper/tokenizer.py) `language or "en"`).
한국어 단독 음성은 en 디코드가 garbage("The President"·"Thank you" 스톰)→QualityGate 억제→커밋 불가→감지 영구 보류의
**콜드스타트 데드락**에 빠져, QG streak refresh·long-silence 리셋이 서두 오디오를 반복 폐기 — 세션 서두 25~71s 통유실
(kor1 실측 WER 45~62%, 탈출 시점 확률적). long-silence 리셋이 `detected_language`를 초기화하므로 세션 중간 재진입도 가능.

**우리 변경** ([`align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py) `_detect_language_if_needed` 보류 분기):
- 미감지+미커밋 상태에서 **오디오 2.0s 누적 시 커밋 없이 `lang_id` 감지 시도, p≥`SESSION_START_LANG_MIN_PROB`(0.85)일 때만 적용**.
  미달이면 다음 infer 사이클 재시도(무조건 적용 폴백 없음 — 기존 커밋 기반 경로가 폴백). 롤백 플래그
  `SESSION_START_LANG_PROBE_ENABLED`. 로그 `[SessionStartLangProbe]`. first_timestamp/eager 기존 경로 무변경.
  no_grad 이중 보호(infer 데코레이터 + `lang_id` 자체) — Exp-158 유형 사고 방지 회귀 테스트 포함.

**성능/이유**: 표적 kor1 med 51.5→44.4%·max 62.0→46.2%(서두 2문장 복구), 발동 전수 정당(확정 라운드 ko×8·en×1, 오적용 0),
미발동 시 코드 경로 master 동일(구조적 무회귀 — bong1/ytn2/kinno 전 회차 미발동). held-out ytn1 12.3/eng1 2.9% 미회귀.
long-silence 리셋 후 재발동으로 중간 데드락 재진입도 방어(kor2 실측). 단위테스트 `tests/test_session_start_lang_probe.py`(10).
**도입 Exp-179** (머지 `27f3f3c`).

---

### 3-7. 문장 확정 + 종료 부호 (Exp-104)

| 항목 | 파일 | 동작 |
|---|---|---|
| Silence 토큰 기반 문장 확정 | [`tokens_alignment.py`](../whisperlivekit/tokens_alignment.py) | Silence 신호 수신 시 현재 세그먼트 `finalized = True` 마킹 |
| `get_lines()` / `get_lines_diarization()` | `tokens_alignment.py` | React UI에 보낼 라인 목록 반환 — `finalized` 상태 포함 |
| 확정 세그먼트 종료 마침표 부착 | [`audio_processor.py`](../whisperlivekit/audio_processor.py) `results_formatter` | 확정된 세그먼트 끝에 마침표 폴백 부착 (진짜 온점은 보존). WER 무영향 (`normalize_text` 구두점 제거) |

---

### 3-8. 화자분할 / Sortformer 연동 (Exp-102/104)

upstream whisperlivekit에는 `new_speaker()` → `refresh_segment()` 뼈대가 있으나 **ChangeSpeaker enqueue 로직이 없어 비활성** 상태였다.

**Exp-102 — 죽은 경로 활성화**:
- [`audio_processor.py`](../whisperlivekit/audio_processor.py) `_update_diarization_state()` 끝에 화자 변화 감지 → `ChangeSpeaker` enqueue 추가
- [`backend.py`](../whisperlivekit/simul_whisper/backend.py) `new_speaker()` — `detected_language = None`, `first_timestamp = None` 리셋 (Exp-093 silence 재감지와 동일 패턴)
- [`diarization/sortformer_backend.py`](../whisperlivekit/diarization/sortformer_backend.py) `_load_model()` — `os.path.isfile()` 분기로 로컬 `.nemo` 파일 직접 로드 지원 (폐쇄망 오프라인)
- [`config.py`](../whisperlivekit/config.py) `sortformer_model` 필드, [`parse_args.py`](../whisperlivekit/parse_args.py) `--sortformer-model` 옵션 추가

**Exp-104 — `new_speaker` Round 2 경계 재디코딩**:
- `new_speaker()`: `process_iter(is_last=True)` flush 생략 + `refresh_segment(complete=False)` (경계 오디오 유지) + `detect_current_language(1.5, 0.85)` 즉시 재감지

사용 예시: `--diarization --sortformer-model <경로>/sortformer-4spk-v2.nemo`
상세는 [DIARIZATION_SPIKE.md](research/DIARIZATION_SPIKE.md) 참조.

---

### 3-9. 진단 인프라 (Exp-105 Round 0)

| 기능 | 옵션 | 파일 |
|---|---|---|
| TokenTrace — 토큰 단계별 디버그 로그 | `--trace-tokens` | [`backend.py`](../whisperlivekit/simul_whisper/backend.py), [`basic_server.py`](../whisperlivekit/basic_server.py) |
| QualityGate 텍스트 잘림 제거 | (상시 적용) | `align_att_base.py` `%.200s` |

---

### 3-10. 세션 라인 리텐션 무제한화 (로컬 패치, 2026-07-13)

[`tokens_alignment.py`](../whisperlivekit/tokens_alignment.py)의 `_DEFAULT_RETENTION_SECONDS`(5분 →
무제한, `300.0`→`float("inf")`)를 벤더링된 upstream 코드에 로컬 패치했다. upstream을 재설치/업데이트하면
이 패치가 사라지므로 재적용이 필요하다.

- **혼동 주의**: ASR 디코더 버퍼 트리밍(`--buffer_trimming_sec`, 별개 15초 메커니즘,
  [`parse_args.py`](../whisperlivekit/parse_args.py))과는 무관한 별개 메커니즘이다 — 전자는 디코더
  오디오 버퍼 트리밍, 후자(이번 변경)는 서버가 보관하는 확정 라인(`lines[]`) 히스토리 보존 기간이다.
- **트레이드오프**: 서버 메모리/CPU/대역폭이 세션 길이에 비례해 무제한 증가한다.

---

## 4. 필터링 / 단어 교정

> **이식 기준**: [../CLAUDE.md](../CLAUDE.md) §3.5/§3.6 — `whisperlive_code/`에서 **그대로 이식**, 임의 개선 금지.

| 모듈 | 파일 | 동작 |
|---|---|---|
| 환각 문장·단어 제거 | [`filtering/__init__.py`](../whisperlivekit/filtering/__init__.py) | `hallucination.json` 목록에 매칭되는 문장·단어를 전사 결과에서 제거 |
| 비음성 주석 제거 (`_ANNOTATION_RE`) | `filtering/__init__.py` | `(웃음)` `[MUSIC]` 등 닫힌 주석 + **안 닫힌** 비음성 주석(`(speaking…`, `[LAUGHTER`)까지 제거. 키워드 시작·ASCII 영문까지만 매칭해 뒤 한글 보존(과잉제거 방지). (Exp-152, `6df4416`) |
| 단어 교정 사전 | [`filtering/manager.py`](../whisperlivekit/filtering/manager.py) `WordCorrectionManager` | `admin_replacement.json` (기본 사전) + SQLite DB (`user_replacement.db`) 동적 갱신. 갱신 즉시 반영 |
| 기본 사전 파일 | [`filtering/hallucination.json`](../whisperlivekit/filtering/hallucination.json), [`filtering/admin_replacement.json`](../whisperlivekit/filtering/admin_replacement.json) | 환각 목록 / 기본 단어 교정 테이블 |

**동적 Glossary 갱신**: `WordCorrectionManager`는 SQLite를 폴링해 운용 중 사전 추가/삭제가 가능하다.
변경 즉시 다음 전사부터 반영된다.

---

## 5. 번역 파이프라인

> **이식 기준**: [../CLAUDE.md](../CLAUDE.md) §3.4 — 문장 확정 시 번역 수행, `whisperlive_code/` 구조 그대로.

| 모듈 | 파일 | 동작 |
|---|---|---|
| 번역기 | [`llm_translation/translator.py`](../whisperlivekit/llm_translation/translator.py) | `LlamaTranslator` (llama.cpp) / `OllamaTranslator` (Ollama). 환경별 분기 |
| 번역 관리자 | [`llm_translation/manager.py`](../whisperlivekit/llm_translation/manager.py) `TranslationManager` | 확정 세그먼트 수신 시 비차단 번역 캐시. 번역 결과를 세그먼트에 부착 |
| 번역 트리거 | [`audio_processor.py`](../whisperlivekit/audio_processor.py) | 문장 `finalized = True` 시점에 번역 큐에 enqueue |

**환경별 엔드포인트** (상세: [DEPLOYMENT_OFFLINE.md §5](DEPLOYMENT_OFFLINE.md)):
- 배포: `gpt-oss-20b` @ `llama.cpp:2010` (2026-07-16~ **기본값**)
- 개발: `qwen2.5:7b` @ `Ollama:11434` (재정의 필요)

---

## 6. 스키마 / React 호환

upstream `Segment.to_dict()`는 React UI 스키마와 필드명이 달랐다.

**변경 파일**: [`timed_objects.py`](../whisperlivekit/timed_objects.py) `Segment.to_dict()`

| upstream 필드 | 추가된 alias | 역할 |
|---|---|---|
| `finalized` | `'completed': self.finalized` | React 기존 `completed` 키 호환 |
| `detected_language` | `'lang': self.detected_language` | React 기존 `lang` 키 호환 |

두 필드를 병렬로 직렬화해 **React 측 코드 변경 없이** 기존 UI와 호환된다.
상세 스키마 변경 히스토리: [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md).

---

## 7. eval 하니스 / 메트릭

upstream에는 정량 평가 도구가 없었다. 아래 모듈을 새로 추가했다.

| 파일 | 역할 |
|---|---|
| [`scripts/eval.py`](../scripts/eval.py) | 경로 C(VBCable) / 경로 A(파일) WER + 문장분리 F1 측정. `--repeat N`(기본 1; 채택 확정 시 3) median/min/max/stdev 집계. `--paths`, `--files`, `--diarization`, `--sortformer-model`, `--trace-tokens`, `--periodic-lang-check`, `--audio-max-len`, `--frame-threshold`, `--beams`(Exp-161/162 진단용 패스스루) 옵션 지원. **서버 stdout/stderr를 `.omc/server_logs/server_<stem>_<path>_R<rep>_<ts>.log`로 회차별 항상 저장(Exp-153; Q1 필터 기여도 계측용, `PYTHONIOENCODING=utf-8`)** |
| [`whisperlivekit/metrics.py`](../whisperlivekit/metrics.py) | `compute_wer()` (정규화 WER), 문장분리 F1 (`_align_words`, Levenshtein 기반) |
| [`scripts/vbcable_test.py`](../scripts/vbcable_test.py) | 경로 C 브라우저 자동화 (VBCable 루프백을 브라우저 마이크로 노출, 음원 재생 → 캡처) |
| [`scripts/audio_device.py`](../scripts/audio_device.py) | VBCable 오디오 장치 자동 설정 / 측정 후 복원 |

**측정 기준** (CLAUDE.md §4 — 2계층):
- 경로 C만 채택/기각 판정에 사용 (경로 A는 빠른 회귀 체크용)
- **① 스크리닝(평소) = --repeat 1** (방향 신호); **② 채택 확정(머지 직전) = --repeat 3** → median + min/max/stdev 기준으로 판단
- **1순위: max(최악 케이스) 미회귀, 2순위: median 개선** (② 단계 기준)

---

## 8. 향후 개선점 (TODO)

### 단기 (다음 실험 후보 — 상세: [BACKLOG_CODESWITCH_FOLLOWUP.md](backlog/BACKLOG_CODESWITCH_FOLLOWUP.md), Exp-175 탐사 산출물)

- **ScriptAnchorRedetect 철자낭독 오발동 가드**(최우선, Exp-179 신규 규명): 한국어 문장 내 영문 약어 철자 낭독("GP·GOP")이
  Latin 3단어 streak을 만들어 §3-6c 게이트가 ko→en 오전환 + **전환 트림 9.7~12s 오디오 폐기** + 복귀 전환 + 재디코딩
  중복 확정 폭주(kor2 WER 70~101%). 약어 철자 시퀀스(무모음 대문자 연쇄 등) streak 산입 제외 또는 재감지 적용 전 트림 억제 검토.
- **재디코딩 중복 확정 churn**(kor2/kor3 실측): 전환/refresh 후 같은 문장 프리픽스가 누진 재확정(×3~5회) — Exp-177 Bug1
  (타임스탬프 재앵커) 계열, [GOAL_BOUNDARY_QG_PRESERVE.md](goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md)와 연계.
- **Case B — SILENCE_HARD_SECS 낭독체 pause 우회**(kor3 실측): 단어 중간 0.8s+ 호흡이 문법 게이트(Exp-176)를 우회해
  단어 중간 분절("통합."⏎"하고") — 안전망 정책 재검토.
- **미방출형 전환 서두 유실**: 구언어 잠금 중 디코더 비-fire로 반전 streak 자체가 없어 3-6c 게이트
  스코프 밖(ytn2 "There is more work"·sbs1 "From a satellite image" 실측). 재디코딩 창 하한을 마지막 방출 토큰
  끝으로 당기거나 경량 비-fire 워치독 검토.
- **①′ locked-lang 음차 환각**: 반대 언어 발화가 잠긴 언어 음차로 환각 디코딩(bong1 "mallang mallang") —
  스크립트 반전이 없어 3-6c로 원리상 포착 불가. 저신뢰+언어확률 경합 보조 트리거 별도 설계(Exp-160 스퓨리어스 리스크 주의).
- **bong1 필러/웃음 환각(C안)**: AnchorRepeatFilter 가변 변주구 사각지대(Exp-169) + 웃음 전용 비-ASR 분류기(Exp-165 결론) 별도 루프.
- **eng1 F1=0%**: 단일 화자 영어 발화가 단일 세그먼트로 처리되어 문장분리 F1이 0. 별도 접근 방법 필요 (예: 무음 감지 기반 분할, 또는 평가 지표 재정의).
- **측정 프로토콜**: 3파일 배치 N=3 후미 파일의 부하성 상승(Exp-175 분리 실증) — 파일 순서 로테이션 또는 파일별 격리 측정 검토. sbs1 저빈도 stall(첫 40s 무출력, Exp-168/175 관측)은 별도 근본 대응 후보.

### 중기 (다음 Phase)

- **diarization → finalized 마킹 완전 연결**: ChangeSpeaker 경로는 활성화됐으나 화자분할 기반 finalized 마킹이 아직 완전히 React까지 연결되지 않음. ([SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) §6 참조)
- **번역 React 연결 완성**: `TranslationManager`는 구현됐으나 번역 결과의 실시간 React 반영 경로가 Phase 4+ 작업으로 남아 있음. ([DEPLOYMENT_OFFLINE.md §5](DEPLOYMENT_OFFLINE.md) 참조)
- **§3 도메인 서술 백필**: 이 문서의 §3-6b 이후 채택분 중 Exp-158(turbo 기질 전환)·160(PLC 기본 None)·161(audio_max_len 15.0)·167/168/170/171/173/174가 도메인 섹션에 미반영 — §2 수치는 최신이나 서술 백필 필요(이력 자체는 [../EXPERIMENTS.md](../EXPERIMENTS.md)에 완비).

### 장기 / 설계 제약 (§3.8)

- **백엔드 우선 개선**: 추가 후처리 필터보다 VAD 전처리, 오디오 전처리, 디코더 파라미터(beam_size, nonspeech_prob 등) 개선 우선.
- **범용성 유지**: 특정 테스트 파일(sbs1/ytn1)에 과적합되는 개선 금지. ytn2(held-out)를 정기 검증에서 제외하여 일반화 데이터 가치 보존.
- **폐쇄망 패키징**: 배포 환경 오프라인 설치 절차 미완. ([docs/OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) 참조)
- **하드코딩 제한**: 특정 언어·패턴 특화 하드코딩 신규 추가 금지 (CLAUDE.md §3.8). 기존 Exp-002/028/057 베이스라인 필터는 유지하되 같은 방식 확장 금지.

---

## 9. 갱신 규약

채택 실험을 master에 머지한 직후 아래 절차를 따른다:

1. `/update-master-changes` 슬래시 커맨드 실행 (Claude가 문서 갱신)
2. 갱신 대상:
   - §2 베이스라인 수치 (최신 path C N≥3 결과로 교체)
   - 해당 도메인 섹션 (§3~§7) — `upstream → 변경 → 이유 → 파일 → Exp-N` 형식 유지
   - §8 TODO — 해결된 항목 제거 + 새 "다음 가설" 추가
3. **시행착오는 여기에 적지 않는다** — 실험 상세는 [../EXPERIMENTS.md](../EXPERIMENTS.md) 소관.
4. 갱신 후 커밋 메시지: `docs: MASTER_CHANGES.md — Exp-N 채택 반영` 형식.
