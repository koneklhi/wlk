# 문장 확정·분리 로직 레퍼런스 (Sentence Finalization Logic)

이 문서는 실시간 STT가 **한 문장(=`Segment`/line)을 언제·왜 확정(finalized)하고 분리(경계 생성)하는지**의
전체 로직과 파라미터를 기록한다. `finalize_trigger` 계측 필드(전사 결과·UI 배지)가 붙는 근거이며,
성능 개선 등으로 확정/분리 로직이 바뀌면 **이 문서도 같은 작업 단위에서 갱신**한다(하단 §7 갱신 규약).

> **값의 단일 진실원(SoT)은 코드 상수 정의 위치다.** 이 문서에 적힌 수치는 작성 시점 값이며,
> 각 값에 정의 위치(file:line)를 병기했다. 코드에서 값을 바꾸면 이 표의 수치도 함께 고친다.
> (과거 문서에 하드코딩된 임계치가 코드보다 뒤처져 방치된 사고가 있었다 — 그 재발 방지가 이 규약의 목적.)

---

## 1. 한눈에 — 경계 원인은 3종, `finalize_trigger` 값은 4종

**중요 구분**: "문장 경계를 *만드는* 원인"과 "`finalize_trigger`가 *내보내는 라벨*"은 개수가 다르다.

| finalize_trigger 값 | 분류 | 경계를 만드는가 |
|---|---|---|
| `language_switch` | **독립 경계 원인** | ✅ 한↔영 전환 마커가 줄을 닫음 |
| `speaker_change` | **독립 경계 원인** (diar ON 한정) | ✅ 화자 전환이 줄을 닫음 |
| `silence` | **독립 경계 원인** | ✅ 침묵(VAD pause) 토큰이 줄을 닫음 |
| `punctuation` | **라벨** (침묵/화자경계로 닫힌 줄의 텍스트가 종결부호로 끝날 때) | ❌ 독립 원인 아님 — 침묵/화자경계가 만든 줄에 붙는 세분 라벨 |

즉 **실제 분할 신호는 3개**(침묵·언어전환·화자전환)이고, `punctuation`은 그중 침묵/화자경계로 닫힌
세그먼트가 `.!?。！？`로 끝나면 `silence`/`speaker_change` 대신 붙는 **세분 라벨**이다.
전수 감사 결과 이 4개 외에 UI `lines[]` 경계를 만드는 다른 메커니즘은 없다(§6에 근거).

미확정으로 남는 경우(스트림 진행 중 마지막 줄, 종료 시 강제확정 없음)는 `finalize_trigger = null`.

---

## 2. 확정이 결정되는 최종 지점 (딱 두 함수)

세그먼트의 `finalized`/`finalize_trigger`는 오직 [tokens_alignment.py](../whisperlivekit/tokens_alignment.py)의 두 함수에서 세팅된다.

- **diarization ON** (기본값 `--diarization`): `TokensAlignment.get_lines_diarization()` — `tokens_alignment.py:266`~
- **diarization OFF**: `TokensAlignment.get_lines()`의 비-diar 루프 — `tokens_alignment.py:358`~

두 함수는 매 사이클 토큰 스트림으로부터 세그먼트를 재구성한다. 세그먼트를 실제로 닫거나 여는 것은
토큰 스트림에 섞여 들어오는 **3종 신호**(Silence 토큰 / LanguageSwitch 마커 / (diar)화자 변경)뿐이다.
직렬화는 `Segment.to_dict()` (`timed_objects.py:185`)가 `finalized`/`completed`/`finalize_trigger`를 항상 방출.

---

## 3. 독립 경계 원인 3종 — 상세 로직 + 파라미터

### 3.1 `silence` — 침묵(VAD pause) 경계

- **신호 생성**: 침묵 지속시간이 임계 초과일 때만 `Silence` 토큰을 `state.new_tokens`에 넣는다.
  `audio_processor._end_silence()` → `audio_processor.py:213-214`.
- **경계 소비(확정)**:
  - 비-diar: `get_lines()`에서 `current_line_tokens`를 닫아 `finalized=True` 커밋 — `tokens_alignment.py:374`.
    라벨: `finalize_trigger = "punctuation" if seg.has_punctuation() else "silence"` (`tokens_alignment.py:377`).
  - diar: `compute_punctuations_segments`가 Silence에서 앞 세그먼트를 닫음(`tokens_alignment.py:173`~),
    병합 루프에서 다음이 침묵이면 `"punctuation"`/`"silence"` 라벨 부여(`tokens_alignment.py:299-300`).
- **VAD**: Silero VAC `FixedVADIterator(threshold=0.3)` — `audio_processor.py:120,122`. `--no-vac`이면 첫 청크 초기 침묵만.
- **파라미터**:
  - `MIN_DURATION_REAL_SILENCE = 0.4`초 — **UI 침묵 경계를 만드는 실제 문턱** (`audio_processor.py:29`).
  - VAC `threshold = 0.3` (`audio_processor.py:120,122`).

> ⚠️ **동명이의 상수 주의**: backend에도 `MIN_DURATION_REAL_SILENCE = 2`(`backend.py:36`)가 있으나
> 이건 **디코더 long-silence 리셋** 문턱(2초↑이면 디코더 refresh + 언어 재감지)이지 UI 경계 문턱이 아니다.
> UI Silence 토큰은 이미 0.4초에서 생성된다.

### 3.2 `language_switch` — 한↔영 코드스위칭 경계

- **신호 생성**: `state.pending_language_switch`가 arm돼 있고 이번 배치에 토큰이 있으면, 첫 토큰 앞에
  `LanguageSwitch` 마커 삽입 — `backend.py:573-595`. 이 마커는 `is_boundary()==True`, 텍스트 없음,
  FrontData로 직렬화 안 됨(분할 지점으로만 소비) — `timed_objects.py:124-139`.
- **경계 소비**: 비-diar `get_lines()`의 `elif token.is_boundary()` — `tokens_alignment.py:392-395`
  (`finalize_trigger = "language_switch"`). diar 경로는 `hard_boundary` 세그먼트로 전달돼 병합 루프에서 `"language_switch"`.
- **arm되는 유일한 게이트**: `_apply_detected_language()`의 `is_switch = prev_lang is not None and prev_lang != lang`
  일 때만 `pending_language_switch` 설정 — `align_att_base.py:200-202`. 최초 감지(prev=None)는 arm 안 함.
- **`_apply_detected_language`를 호출하는 진입점(=전환 후보) 전부**:
  1. 일반/게이트 감지 `_detect_language_if_needed` — `align_att_base.py:235` (문턱 `2.0`초, eager면 `1.5`초+p≥0.85, `:225-235`).
  2. 주기 재감지 `_maybe_periodic_lang_check` — `align_att_base.py:239-256` (간격 `periodic_lang_check_secs` = **기본 None=비활성**; 재감지창 2.0s·min_prob 0.90; 최소 재전환 간격 3.0s).
  3. 짧은 침묵 언어 리셋 `_check_short_silence_language` — `backend.py:258-271` (침묵 `≥ MIN_DURATION_SHORT_LANG_RESET`, lang==auto, detected_language 존재; 재감지창 1.5s·min_prob 0.90).
  4. 화자전환 eager 감지 `new_speaker` — `backend.py:282-326` (window 1.5s·min_prob 0.85, 경계 이후 오디오만).
  5. 간접 재-arm(다음 infer가 전환을 재확인하도록 `detected_language=None`+`eager` 무장):
     long-silence(≥2.0s) 리셋 `backend.py:234-250`, ForeignLang("(speaking in foreign language)") `backend.py:484-495`, ScriptMismatch 드롭 `backend.py:508-522`.
- **파라미터**:
  - `LANG_SWITCH_KEEP_SECS = 2.5`초 (전환 시 유지 오디오: 감지창 2.0s+완충 0.5s) — `align_att_base.py:13`.
  - `MIN_DURATION_SHORT_LANG_RESET = 0.5`초 — `backend.py:37`.
  - `periodic_lang_check_secs` = 기본 `None`(비활성) — `parse_args.py`(CLI `--periodic-lang-check`).
  - `lang_restrict_koen = True` (한/영 2언어 고정) — `parse_args.py`(`--lang-restrict-koen`).

### 3.3 `speaker_change` — 화자 전환 경계 (diarization ON 한정)

- **신호 생성**: diarization 백엔드(sortformer)는 `SpeakerSegment`만 생성(텍스트/경계마커 없음) —
  `whisperlivekit/diarization/sortformer_backend.py:254-270`. `all_diarization_segments`에 누적.
- **경계 소비**: `get_lines_diarization()`에서 각 텍스트 세그먼트에 시간 겹침 최대 화자 부여(`tokens_alignment.py:271-283`)
  후, 인접 세그먼트를 **같은 화자·non-hard_boundary면 병합, 다르면 분리** — `tokens_alignment.py:288-303`.
  화자가 바뀌어 새 세그먼트가 열리면 닫히는 세그먼트에 `finalize_trigger = "speaker_change"` — `tokens_alignment.py:302`.
- **별개 신호(디코더용)**: `audio_processor._update_diarization_state`가 화자 변화 시 `ChangeSpeaker`를
  transcription 큐로 전달(`audio_processor.py:463-471`) → `backend.new_speaker()`가 디코더 refresh + 언어 재감지.
  즉 ChangeSpeaker는 **UI 경계를 직접 만들지 않고**, UI 화자 경계는 위 겹침 로직이 만든다.
- **파라미터**: 화자분할 백엔드 `--diarization-backend sortformer`, 모델 `--sortformer-model <.nemo>`.
  기본 `--diarization` = ON (`parse_args.py`). diarization OFF면 이 트리거는 발생하지 않는다.

### 3.4 `punctuation` — 침묵/화자경계로 닫힌 줄의 종결부호 세분 라벨

- **독립 원인 아님**. 침묵(3.1)/화자경계(3.3)로 닫힌 세그먼트의 텍스트가 종결부호로 끝나면 붙는다.
- 판정: `TimedText.has_punctuation()` — 텍스트 끝 문자가 `PUNCTUATION_MARKS = {. ! ? 。 ！ ？}`인지
  (`timed_objects.py:4,28-30`).
- 온점 자체의 분할(`compute_punctuations_segments` + `_punct_split_justified`)은 **뒤에 Silence/발화끝이
  있어야만** 발동하도록 축소돼 있어(갭 기반 분기는 Exp-166에서 제거, `tokens_alignment.py:150-166`) 독립 경계를
  만들지 못한다 — 같은 화자·non-hard_boundary 인접 세그먼트는 병합 루프에서 다시 합쳐진다(`tokens_alignment.py:289`).
- **우선순위**(동시 발생 시): `language_switch` > `speaker_change` > `punctuation` > `silence`.
  종결부호가 있으면 침묵 동반이어도 `punctuation`으로 라벨(자연스러운 끝맺음을 드러내기 위함).

---

## 4. 경계에 "영향은 주되 생성하지 않는" 메커니즘

아래는 텍스트를 유예·이동·드롭·리셋할 뿐 **새 `lines[]` 경계를 만들지 않는다**(간접 영향만).
확정 트리거 로직을 바꿀 때 이들과의 상호작용을 반드시 검토한다.

| 메커니즘 | 위치 | 분류 | 영향 |
|---|---|---|---|
| 확정 유예 `_apply_finalize_grace` | `tokens_alignment.py:331-348` (`FINALIZE_GRACE_SECS=2.0`, `:20`) | 타이밍 수정자 | 침묵 직후 유예창 내 직전 세그먼트 `finalized`를 False로 되돌리고 trigger 무효화(None). 경계 위치 불변, 확정 타이밍만 조정 |
| 꼬리 재귀속(비-diar) `_reattach_tail_nondiar` | `tokens_alignment.py:312-329` (`TAIL_REATTACH_EPS=0.05`, `:19`) | 병합(이동) | 유보된 꼬리 단어를 침묵 앞 세그먼트로 되붙임. 경계 개수 불변 |
| 삽입 재귀속 `_insert_with_reattachment` | `tokens_alignment.py:81-103` (`TAIL_REATTACH_MAX_LOOKBACK_SECS=1.5`, `:25`) | 타이밍 수정자 | Silence 앞 꼬리 토큰 재정렬. is_boundary 만나면 중단(경계 넘김 금지) |
| 과거분 제거 `_prune` | `tokens_alignment.py:105-136` | 드롭(과거) | 오래된 세그먼트 제거. 신규 경계 무관 |
| `filter_segments` | `whisperlivekit/filtering/__init__.py` | 드롭/치환 | CJK·가나·비음성주석·환각·구두점-only 세그먼트 드롭 + 단어 치환. 라인이 사라질 순 있으나 새 경계 생성 안 함 |
| `_append_terminal_punctuation` | `audio_processor.py:32-43` | 표시 수정자 | finalized 세그먼트 끝에 온점 부착(멱등, WER·경계 무영향) |
| 환각/반복 필터 (BatchRepeat/CrossBatch/단일음절/ScriptMismatch/AnchorStorm) | `backend.py:354-413, 448-465, 505-548` | 드롭 | 토큰/배치 드롭. Silence/LanguageSwitch 마커 미방출 → 경계 직접 생성 안 함(텍스트 억제로 간접 영향) |
| QualityGate (logprob/compression) | `align_att_base.py:592-645` (`quality_gate_reset_after=3`) | 드롭/디코더리셋 | 저품질 세그먼트 억제. refresh는 디코더 내부 상태만 리셋, 마커 미방출 |
| stall 복구 refresh | `backend.py:554-563` (`STALL_RECOVER_SEC=10.0`, `:41`) | 디코더리셋 | 마커 미방출 → 경계 직접 생성 안 함 |
| 버퍼 최대길이 트림 `audio_max_len` | config/`parse_args.py` (`--audio-max-len`) | 타이밍 수정자 | 디코더 버퍼 상한 — 타임스탬프 영향, 경계 미생성 |
| 스트림 종료 flush (SENTINEL/`_finish_transcription`) | `audio_processor.py:28,311-338,740-746` | flush | 남은 토큰 flush. **강제 finalize/경계 생성 없음** — 마지막 줄은 Silence/boundary가 없으면 `finalized=false`로 남음(트리거 null) |

---

## 5. 파라미터 표 (문장 확정/분리 직접 영향)

값 SoT는 정의 위치. 코드 변경 시 이 표를 함께 갱신.

| 파라미터 | 현재값 | 정의 위치 | 역할 |
|---|---|---|---|
| `MIN_DURATION_REAL_SILENCE` (audio) | `0.4`s | `audio_processor.py:29` | UI 침묵 경계 생성 문턱 |
| VAC `threshold` | `0.3` | `audio_processor.py:120,122` | Silero VAD 민감도 |
| `MIN_DURATION_REAL_SILENCE` (backend) | `2`s | `backend.py:36` | 디코더 long-silence 리셋(경계 아님) |
| `FINALIZE_GRACE_SECS` | `2.0`s | `tokens_alignment.py:20` | 침묵 후 확정 유예창 |
| `TAIL_REATTACH_EPS` | `0.05`s | `tokens_alignment.py:19` | 꼬리 재귀속 지터 여유 |
| `TAIL_REATTACH_MAX_LOOKBACK_SECS` | `1.5`s | `tokens_alignment.py:25` | 삽입 재귀속 최대 소급 |
| `LANG_SWITCH_KEEP_SECS` | `2.5`s | `align_att_base.py:13` | 전환 시 유지 오디오 |
| `MIN_DURATION_SHORT_LANG_RESET` | `0.5`s | `backend.py:37` | 짧은 침묵 언어 리셋 문턱 |
| `STALL_RECOVER_SEC` | `10.0`s | `backend.py:41` | stall 복구 refresh |
| `periodic_lang_check_secs` | `None`(비활성) | `parse_args.py` `--periodic-lang-check` | 주기 언어 재감지 간격 |
| `PUNCTUATION_MARKS` | `. ! ? 。 ！ ？` | `timed_objects.py:4` | `punctuation` 라벨 판정 |
| 언어감지 문턱 | 일반 `2.0`s / eager `1.5`s+p≥0.85 | `align_att_base.py:225-235` | 전환 arm 조건 |

디코더 파라미터(간접 영향: 어떤 텍스트가 나오는지에 영향, 경계는 §3의 3신호가 전담) —
`frame_threshold`, `beams`, `logprob_threshold`, `compression_ratio_threshold` 등은
[docs/TESTING.md](TESTING.md)·`parse_args.py` 참조.

---

## 6. 전수 감사 결론 (판정 근거)

`{silence, punctuation, language_switch, speaker_change}`가 `finalize_trigger` 방출값의 **전부**임을 확인했다
(`tokens_alignment.py`의 문자열 리터럴 대입 지점 전수 grep). 실제 경계 생성 원인은 3종(침묵·언어전환·화자전환)이며
`punctuation`은 침묵/화자경계로 닫힌 줄의 세분 라벨이다. §4의 모든 메커니즘은 텍스트를 드롭·이동·유예·리셋할 뿐
Silence/LanguageSwitch 마커나 SpeakerSegment 경계를 새로 만들지 않으므로 UI 경계를 생성하지 않는다.
**누락된 경계 생성 메커니즘: 없음.**

---

## 7. 갱신 규약 (이 문서를 최신으로 유지하는 법)

**아래 코드가 바뀌면 같은 작업 단위(커밋)에서 이 문서도 갱신한다.** 갱신 대상 절을 함께 표기:

| 바뀐 코드 | 갱신할 이 문서의 절 |
|---|---|
| `tokens_alignment.py`의 `finalize_trigger` 대입 지점·조건 (확정 로직) | §2, §3 (해당 트리거), §6 |
| 새 트리거 종류 추가/제거 (예: `end_of_stream` 도입) | §1 표, §3(신설 절), §6, 그리고 UI 라벨(`live_transcription.js` `TRIGGER_LABELS`)·`docs/SCHEMA_CHANGES.md` |
| 경계 신호 생성 조건 변경 (Silence 토큰 문턱, LanguageSwitch arm 진입점, 화자경계 로직) | §3 해당 절 |
| §5 파라미터 상수의 **값** 변경 | §5 표(현재값), 그리고 그 값을 언급한 §3 본문 |
| §4 메커니즘(grace/재귀속/필터/QualityGate 등)의 경계 영향 방식 변경 | §4 표 |

> 검증: 값을 바꾼 뒤 `grep`으로 이 문서에서 옛 수치가 남아있지 않은지 확인.
> 트리거 라벨을 추가/변경하면 반드시 [live_transcription.js](../whisperlivekit/web/live_transcription.js)의
> `TRIGGER_LABELS`, [docs/SCHEMA_CHANGES.md](SCHEMA_CHANGES.md), [scripts/eval.py](../scripts/eval.py)의
> 전사 기록과 **동기화**한다(계측 계약이 한 세트로 움직여야 분석이 깨지지 않는다).

관련: 계측 필드 스키마 → [docs/SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) ·
전사 산출물 → [docs/TESTING.md](TESTING.md) · 실험 기록 → [EXPERIMENTS.md](../EXPERIMENTS.md)
