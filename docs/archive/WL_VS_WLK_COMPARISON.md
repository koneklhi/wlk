# WL vs WLK — 스트리밍 확정 정책·문장 분리 로직 비교 보고서

이 문서는 두 세대의 실시간 STT 엔진을 **코드 근거 기반**으로 비교한다.

- **WL (레거시 WhisperLive)** — 참조 코드 [`whisperlive_code/`](../whisperlive_code/). "LocalAgreement"라고 불리던 확정 정책 + 2단계 문장 분리.
- **WLK (현행 WhisperLiveKit)** — 본체 [`whisperlivekit/`](../whisperlivekit/) 패키지. **SimulStreaming / AlignAtt** 확정 정책 + `finalize_trigger` 기반 문장 분리.

세 축을 다룬다: ① 스트리밍 확정 정책, ② 문장 분리 로직(특히 **코드스위칭 한/영 혼용** 대응), ③ 배포 PC에서 관찰된 **WLK의 전문용어(군사) 인식 우위** 원인.

> **인용 주의**: 파일:라인은 작성 시점(2026-07-10) 현행 소스 기준이다. [docs/SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md)의 라인번호는 현행 `tokens_alignment.py`보다 ~90–110줄 뒤처져 있으므로, 이 보고서는 **실측 현행 라인번호**를 쓴다.

---

## 0. 개요 — 두 세대 한눈 비교

| 축 | WL (레거시 WhisperLive) | WLK (현행 WhisperLiveKit) |
|---|---|---|
| 추론 스택 | faster-whisper (CTranslate2) | reference OpenAI-Whisper 디코더 + 커스텀 스트리밍 |
| 모델 | whisper-large-v3-**turbo** fp16 | whisper-large-v3-**turbo** fp16 |
| 확정 정책 | (교과서 LocalAgreement 아님) **반복 N=10 + timestamp 안정성 + sliding offset** | **SimulStreaming / AlignAtt** (어텐션 유도) |
| 확정 판단 신호 | *텍스트 재현 안정성* (같은 출력 반복) | *어텐션 위치* (오디오 끝과의 프레임 거리) |
| 문장 분리 위치 | 서버(세그먼트 확정) → **클라이언트**(문장 조립) 2단계 | `tokens_alignment.py` 두 함수(`get_lines*`)에서 `finalize_trigger` 부여 |
| 경계 원인 | 종결부호 `.`/`?` · `forced` 플래그 · **언어전환(=spk 트릭)** | **침묵 · 언어전환 · 화자전환** 3종 + **온점 형태소 분할** |
| 화자분리(diarization) | 없음 (`spk` 필드를 언어코드로 전용) | Sortformer 실제 화자분리 (별도 채널) |
| 코드스위칭 핵심 | 언어 락 히스테리시스(3회) + 문장마다 리셋 | `LanguageSwitch` 1급 경계 마커 + stale 토큰 retraction + 필터 캐스케이드 |

**용어**
- **확정(commit) / floating(미확정) 영역**: 스트리밍 STT는 오디오가 계속 들어오므로, 더 이상 바뀌지 않을 텍스트("확정")와 다음 청크에서 바뀔 수 있는 꼬리("floating")를 나눈다. 두 엔진의 정책 차이는 결국 *"이 경계를 무슨 신호로 긋느냐"*다.
- **LocalAgreement(-2)**: 연속한 두 가설의 **최장 공통 접두(longest common prefix)**가 일치하면 그 부분을 확정하는 정책. "같은 단어가 두 번 연속 예측되면 믿는다."
- **SimulStreaming / AlignAtt**: Whisper 디코더의 **cross-attention**이 오디오의 어느 프레임을 보는지로 확정을 판단하는 정책. 어텐션이 아직 들어오지 않은 오디오 끝쪽을 보면 그 토큰은 유보한다.

---

## 1. WL의 확정 정책 — "LocalAgreement"의 실체

근거: [`whisperlive_code/server.py`](../whisperlive_code/server.py), [`transcriber.py`](../whisperlive_code/transcriber.py), [`whisper_1023.txt`](../whisperlive_code/whisper_1023.txt).

### 1.1 핵심 정정 — 교과서 LocalAgreement가 아니다

`whisperlive_code/`에는 `local_agreement` / 접두 일치 커밋 코드가 **전혀 없다**(grep 0건). WL은 LocalAgreement-2 대신 세 가지를 결합한 하이브리드로 확정한다: **① sliding commit offset, ② Whisper 자체 timestamp 종결, ③ 동일 출력 N=10 반복 확정** + **④ timestamp 안정성 강제완료**. "연속 가설의 일치"라는 개념은 살아 있지만, *토큰 단위 2회 일치*가 아니라 *세그먼트 단위 10회 반복*으로 구현돼 있다.

### 1.2 커밋 포인터 = 확정/floating 경계

확정/floating을 가르는 것은 스칼라 `self.timestamp_offset`(초 단위 커밋 포인터, `server.py:352`). 이 앞은 확정돼 재디코딩 대상에서 물리적으로 빠지고, 뒤는 매 루프 재전사되는 floating 영역이다. `get_audio_chunk_for_processing`(`server.py:438-456`)가 매 루프 포인터 이후만 잘라 넘긴다:

```python
samples_take = max(0, (self.timestamp_offset - self.frames_offset) * self.RATE)
input_bytes = self.frames_np[int(samples_take):].copy()
```

### 1.3 `update_segments` — 확정/미확정 판정

핵심은 `ServeClientFasterWhisper.update_segments`(`server.py:893-1009`). Whisper가 floating 구간을 자체 timestamp로 여러 sub-segment로 쪼개 돌려주면 WL은:

1. **마지막 직전 sub-segment = 확정** (`server.py:910-930`): 뒤에 다른 segment가 이미 시작됐으므로 더 바뀔 수 없다 → `completed=True`로 커밋, 커밋 포인터 전진.
2. **마지막 sub-segment = 항상 provisional** (`server.py:931-940`): 청크 끝에서 단어가 잘렸을 수 있으므로 `completed=False`로만 방출, 커밋 안 함.
3. **N=10 반복 확정** — WL식 "agreement" (`server.py:941-978`): floating 텍스트가 직전 루프와 동일하면 카운트, `same_output_threshold`(=10, [`whisper_1023.txt:24`](../whisperlive_code/whisper_1023.txt)) 초과 시 강제 커밋.

```python
if self.current_out.strip() == self.prev_out.strip() and self.current_out != "":
    self.same_output_count += 1
    ...
if self.same_output_count > self.same_output_threshold:   # 10회 초과
    self.text.append(self.current_out)
    self.transcript.append(self.format_segment(..., completed=False, forced=True))
    ...
    offset = min(duration, self.end_time_for_same_output)
```

> LocalAgreement-2가 *n=2*(두 번 연속 일치)로 확정하는 자리를, WL은 *N=10*(열 번 반복)·세그먼트 단위로 대체한 셈이다. 훨씬 보수적이고 지연이 크다.

### 1.4 timestamp 안정성 강제완료 (stall 감지)

[`transcriber.py`](../whisperlive_code/transcriber.py)에 "모델이 멈췄으니 확정" 감지기가 있다. 최근 4개 end-timestamp를 회전 큐에 넣고(`transcriber.py:649-654`), 큐가 차고 그 spread가 0.1s 미만이면 `timestamp_forced_completion`을 세운다(`transcriber.py:997-1012`):

```python
if -1 not in self.last_timestamp_rotation_queue:
    if max(self.last_timestamp_rotation_queue) - min(...) < self.last_timestamp_diff_threshold:  # 0.1s
        timestamp_forced_completion = True
```

이 플래그가 서버로 돌아와 `completed=True, forced=True` 세그먼트를 만들고 오프셋을 전진시킨다(`server.py:979-1003`). 즉 Whisper가 같은 종료 timestamp를 4번 반복 예측하면 발화 끝(침묵/stall 프록시)으로 본다.

---

## 2. WLK의 확정 정책 — SimulStreaming / AlignAtt

근거: [`whisperlivekit/simul_whisper/align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py), [`simul_whisper.py`](../whisperlivekit/simul_whisper/simul_whisper.py), [`backend.py`](../whisperlivekit/simul_whisper/backend.py), [`config.py`](../whisperlivekit/config.py), [`core.py`](../whisperlivekit/core.py).

### 2.1 기본 정책 선택

기본값 `backend_policy = "simulstreaming"`([`config.py:34`](../whisperlivekit/config.py)). 배선은 `core.py:166`(엔진)·`core.py:279`(세션 프로세서). LocalAgreement-2는 [`local_agreement/online_asr.py`](../whisperlivekit/local_agreement/online_asr.py)의 **대체 경로**로만 남아 있다(`--backend-policy localagreement`).

### 2.2 AlignAtt — 어텐션 유도 커밋

핵심은 `AlignAttBase.infer()`의 디코드 루프(`align_att_base.py:328-481`). 매 디코드 스텝마다 정렬 헤드의 cross-attention에서 **가장 많이 주목한 오디오 프레임**을 구하고(`align_att_base.py:399-400`, `argmax`), 그 프레임이 오디오 끝에 `frame_threshold`(기본 25프레임 ≈ 0.5s) 이내로 가까워지면 정지하고 **마지막 토큰을 버린다**(`align_att_base.py:433-440`):

```python
if content_mel_len - most_attended_frame <= (4 if is_last else self.cfg.frame_threshold):  # 25
    current_tokens = current_tokens[:, :-1]   # 오디오 끝을 보는 토큰은 유보
    break
```

즉 **어텐션이 아직 안정적으로 오디오 안쪽을 보는 토큰만 확정**하고, 끝을 보는 토큰은 다음 청크로 미룬다. 마지막 flush(`is_last`)에서만 여유를 4프레임으로 줄여 꼬리를 방출한다. (여기에 어텐션이 뒤로 크게 튀면 loop로 보고 되감는 rewind 가드 `align_att_base.py:413-431`도 있다.)

### 2.3 CIF fire 게이트 — 마지막 단어 유보

디코드 전 `fire_detected = self.fire_at_boundary(...)`(`align_att_base.py:347`)로 단어 경계를 판단한다. `_split_tokens`(`align_att_base.py:485-496`)가 이를 소비한다:

```python
if fire_detected or is_last:
    new_hypothesis = tokens_list                       # 전체 단어 커밋
else:
    split_words, split_tokens = self.tokenizer.split_to_word_tokens(tokens_list)
    if len(split_words) > 1:
        new_hypothesis = [... split_tokens[:-1] ...]   # 마지막 단어 유보
    else:
        new_hypothesis = []
```

기본 설정은 CIF 체크포인트가 없어(`--cif-ckpt-path` 기본 None, `parse_args.py:289-303`) `always_fire=True`가 된다. 단어가 중간에서 잘리는 위험이 있을 때 **마지막 단어를 유보("유보한 꼬리")**하고, 이 꼬리를 이후 문장정렬 계층(`_reattach_tail_nondiar` 등, §4.6)이 다시 붙인다. 이것이 §3.3(CLAUDE.md)의 **"단어 중간 분절(Case B) 절대 금지"**를 구조적으로 떠받치는 장치다.

### 2.4 품질 게이트 — suppress-only (재샘플링 없음)

디코드 후 `_quality_gate`(`align_att_base.py:456-458`, 구현 `:618-642`)가 avg-logprob < `logprob_threshold` 또는 compression-ratio > `compression_ratio_threshold`면 **그 가설을 통째로 버린다(suppress)**. WL과 달리 온도를 올려 재디코딩하지 않는다 — 이 차이가 §6의 핵심이다.

```python
num_generated = max(0, current_tokens.shape[1] - token_len_before)
if not is_last and self._quality_gate(new_hypothesis, sum_logprobs, num_generated):
    self._on_quality_suppressed(new_hypothesis)
    return []      # 재샘플링이 아니라 그냥 드롭
```

### 2.5 버퍼 트림

- 롤링 오디오 버퍼는 `audio_max_len`(배포 **15.0s**, `parse_args.py:272-279`; Exp-161에서 30→15로 축소, lag 안정화)까지 유지, 초과 시 오래된 세그먼트 폐기하며 절대 timestamp 앵커 유지(`simul_whisper.py:162-180`).
- 언어전환 시 `_trim_segments_to_recent(2.5s)`(`LANG_SWITCH_KEEP_SECS`, `align_att_base.py:14,177-196`) — 경계 근처만 재디코딩해 이미 확정한 구절 재방출을 막는다.

### 2.6 정책 대조 요약

| | LocalAgreement (개념/WL식 반복) | AlignAtt (WLK) |
|---|---|---|
| 확정 신호 | 텍스트 재현 안정성 | cross-attention 위치 |
| 판정 단위 | (WL) 세그먼트, 10회 반복 | 토큰/단어, 매 스텝 |
| 저품질 처리 | (WL) 온도 폴백 재샘플링 | **드롭(suppress)** |
| 꼬리 처리 | provisional로 재방출 | **유보 후 재부착** |

---

## 3. 문장 분리 로직 — WL (2단계)

근거: [`whisperlive_code/client.py`](../whisperlive_code/client.py), [`server.py`](../whisperlive_code/server.py), [`app.py`](../whisperlive_code/app.py).

WL의 문장화는 **서버(세그먼트 확정) → 클라이언트(문장 조립)** 2단계다. 클라이언트 `add_transcript_segmentation`(`client.py:280-386`)이 확정 세그먼트를 문장으로 묶는다. 경계는 세 조건에서 발생한다:

1. **종결부호 + completed 또는 forced 플래그** (`client.py:349-358`):
```python
if segment.forced or (content and content[-1] in ['.', '?'] and segment.completed):
    transcript_list.append(Segment(spk=segment.spk, content=tmp, completed=True))
```
종결부호는 **`.` 와 `?` 만** 인정한다.

2. **"화자" 변경 = 실제로는 언어 변경** (`client.py:335-343`): WL엔 화자분리가 없다. 서버가 `format_segment`에서 **언어코드**를 `lang`에 담고(`server.py:848-857`), 클라이언트가 이를 `Segment(spk=lang, ...)`로 저장한다(`client.py:303-306`). `app.py:77`가 `language, status = spk.value, ...`로 확인해준다. 따라서 WL의 "speaker change" 경계 = **한↔영 언어전환 경계**이며, 각 언어 덩어리를 확정해 올바른 번역 방향으로 라우팅한다.

3. **중복 트림** (연속 가설 정합의 클라이언트측 흔적): `check_repeat_with_last_segment` + `_fuzzy_substring_match`(`client.py:199-278`)가 재디코딩으로 다시 나온 앞부분을 퍼지 매칭으로 잘라내 중복을 막는다.

---

## 4. 문장 분리 로직 — WLK (3종 원인 + 온점 형태소 분할)

근거: [`whisperlivekit/tokens_alignment.py`](../whisperlivekit/tokens_alignment.py), [`sentence_boundary.py`](../whisperlivekit/sentence_boundary.py), [`audio_processor.py`](../whisperlivekit/audio_processor.py), [`timed_objects.py`](../whisperlivekit/timed_objects.py), 정본 [docs/SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md).

### 4.1 확정 지점 — 딱 두 함수, 라벨 4종

`Segment.finalized` / `finalize_trigger`는 오직 `TokensAlignment`의 두 함수에서만 세팅된다:
- **diarization ON**: `get_lines_diarization()` — 현행 `tokens_alignment.py:379-429`.
- **diarization OFF**: `get_lines()`의 비-diar 루프 — 현행 `tokens_alignment.py:478-562`.

`finalize_trigger` 라벨은 4종: `silence`, `language_switch`, `speaker_change`, `punctuation`(미확정 = `null`). **경계를 만드는 메커니즘은 3종(침묵·언어전환·화자전환) + 온점 형태소 분할**이다.

### 4.2 원인 1 — silence (침묵)

침묵 지속이 `MIN_DURATION_REAL_SILENCE`(=**0.4s**, UI 경계 문턱, `audio_processor.py:29`)를 넘으면 `_end_silence`가 `Silence` 토큰을 넣고(`audio_processor.py:201-219`), `get_lines()`가 현재 줄을 닫는다(`tokens_alignment.py:499-516`):
```python
seg.finalize_trigger = "punctuation" if seg.has_punctuation() else "silence"
```
VAD는 Silero `FixedVADIterator(threshold=0.3, min_silence_duration_ms=200)`(`audio_processor.py:122,124`). 200ms는 한 단어가 두 줄로 쪼개지지 않도록 100→200으로 올린 값이다.
> 주의: `backend.py:37`의 동명 상수 `MIN_DURATION_REAL_SILENCE=2`는 **디코더의 장침묵 리셋** 문턱이지 UI 경계가 아니다.

### 4.3 원인 2 — language_switch (한↔영 코드스위칭)

`_apply_detected_language`가 **실제 전환**을 감지하면(`prev_lang != lang`, `align_att_base.py:207-220`) `pending_language_switch`를 무장한다:
```python
if is_switch:
    self.state.pending_language_switch = self.state.global_time_offset + self.segments_len()
```
그러면 `process_iter`가 새 언어 첫 토큰 앞에 `LanguageSwitch` 마커를 주입하고(`backend.py:736-764`), `get_lines()`가 이를 경계로 소비한다(`tokens_alignment.py:517-525`):
```python
elif token.is_boundary():
    seg.finalize_trigger = "language_switch"
```
`LanguageSwitch`([`timed_objects.py:124-142`])는 텍스트 없이 `is_boundary()==True`만 가진, 프론트에 직렬화되지 않는 순수 분할점이다. 여기에 **retraction**(Exp-171~)이 결합된다: 전환 직전 diar 지연 중 잘못 커밋된 이전-언어 토큰을 `_retract_stale_language_tokens`(`tokens_alignment.py:141-198`)가 회수한다(경계 개수는 그대로, 텍스트만 교정).

### 4.4 원인 3 — speaker_change (diarization ON)

Sortformer(`nvidia/diar_streaming_sortformer_4spk-v2`, `config.py:73`)가 텍스트 없는 `SpeakerSegment`(`sortformer_backend.py:234-268`)를 만든다. 여기서 **두 채널**이 갈린다(혼동 주의):

- **채널 A — UI 화자 경계**: `get_lines_diarization()`가 각 세그먼트를 **시간 겹침(overlap) 최대** 화자에 귀속시키고(`tokens_alignment.py:389-396`), 인접 세그먼트를 같은 화자면 병합·다르면 분할한다. **UI 화자 경계를 실제로 만드는 것은 이 겹침 로직**이다. 라벨 우선순위(`tokens_alignment.py:411-422`): `language_switch > silence/punctuation > speaker_change > punctuation`.
- **채널 B — ChangeSpeaker → 디코더 refresh**: 화자가 바뀌면 `_update_diarization_state`가 `ChangeSpeaker`를 전사 큐에 넣고(`audio_processor.py:456-473`), `new_speaker()`(`backend.py:321-391`)가 **경계 오디오만 남겨 재디코딩**(`keep_secs`, `refresh_segment(complete=False)`)하고 그 구간 언어를 재감지한다. 즉 **ChangeSpeaker는 UI 경계를 직접 만들지 않고 디코더만 리프레시**하며, 새 화자 언어가 다르면 간접적으로 `language_switch` 경계를 유발할 수 있다.

### 4.5 4번째 메커니즘 — 온점 형태소 분할 (Exp-170~)

CLAUDE.md가 말하는 "온점 형태소 분할". 순수 함수 [`sentence_boundary.is_genuine_sentence_end`](../whisperlivekit/sentence_boundary.py)가 마침표가 **진짜 문장 종결**인지 형태소로 판별한다(`sentence_boundary.py:73-97`):
- **한국어**: 종결어미로 끝나야(`KO_FINAL_SUFFIXES` = 니다/십시오/어요/…/았다/었다, `sentence_boundary.py:11-17`) 하고, 연결어미·조사(`KO_EXCLUDE_SUFFIXES` = 니까/는데/으로/다는/…, `:20-25`)로 끝나면 **우선 차단**. 단음절(군/네/다)은 명사 충돌로 제외.
- **영어**: 약어·이니셜(`EN_ABBREV`: Mr/U.S/Gen/Col/Sgt/…)·소수점이면 분할 금지, 진짜 종결은 **다음 어절이 대문자로 시작할 때만**.
- **전역 가드**: 마침표 직전이 숫자면(`3.`, `1.`) 분할 안 함.

게이트 `_punct_split_here`(`tokens_alignment.py:263-278`)는 **마침표(`.`/`。`) 전용**이다(`?`/`!`는 음향 경로만 씀 — 소수점·약어 위험이 없기 때문). 과거 "마침표 + 큰 timestamp gap" 분기는 Exp-166에서 **제거**됐다 — 스트리밍 timestamp gap은 버퍼 트림/AlignAtt 유보로 신뢰 불가라서 실제 VAD Silence나 발화 끝만 음향 분할로 인정한다.

### 4.6 경계를 만들진 않지만 텍스트를 옮기는 장치

- **finalize grace**(`_apply_finalize_grace`, `tokens_alignment.py:459-476`): 침묵 확정 후 `FINALIZE_GRACE_SECS=2.0s` 안이면 직전 세그먼트 확정을 되돌려 유보 꼬리를 기다린다.
- **꼬리 재부착**(`_reattach_tail_nondiar` `tokens_alignment.py:432-449`, `_insert_with_reattachment` `:115-139`): §2.3의 AlignAtt 유보 단어를 Silence 앞 세그먼트에 다시 붙인다(`TAIL_REATTACH_EPS=0.05`, lookback 1.5s).

---

## 5. 코드스위칭(한/영) 대응 비교 — 핵심

두 세대 모두 "한 발화 안 한·영 혼용"에서 **단어 유실·환각·조기 확정**을 막으려 서로 다른 장치를 넣었다.

### 5.1 WL이 넣은 것 — 보수적 언어 락

1. **언어 {ko,en} 제한 detect** (`transcriber.py:1826-1839`): target_langs 밖 언어를 버리고, 확률 < 0.1이면 0.0으로(노이즈에 ko/en 강제 방지).
2. **언어 락 히스테리시스** (`language_cnt_threshold=3`, `server.py:766-776`): 같은 언어가 고신뢰(>0.9)로 **3회 연속** 감지돼야 그 언어를 디코더에 고정. 전환이 감지되면 카운트를 1로 리셋 → 짧은 전환 구간에서 flip-flop·단어 유실 방지.
```python
language=self.language if self.cnt >= self.language_cnt_threshold else None,   # server.py:749
```
3. **문장마다 언어 리셋** (`self.language=None; self.cnt=0`): 모든 확정 지점에서 락 해제 → 다음 발화가 다른 언어일 수 있게 함. 이것이 한/영 교대를 가능케 한다.
4. **언어전환 = 문장경계**: §3의 `spk`=언어 트릭으로 전환 시 문장을 끊어 번역 방향을 라우팅.

> WL 전략 요약: **락으로 flip-flop을 억제하다가 문장 경계에서 언어를 바꾼다.** 안전하지만 3회 확인만큼 지연이 있고, 화자분리가 없어 다화자 상황은 언어전환으로만 근사한다.

### 5.2 WLK가 넣은 것 — 능동적 전환 경계 + 경계 단어 보존

1. **`LanguageSwitch` 마커 = 1급 독립 경계 원인**(§4.3): 전환 지점에서 줄을 강제로 닫아 서로 다른 언어가 한 줄에 섞여 조기 확정되는 것을 막는다.
2. **전환 시 2.5s만 유지 재디코딩**(`LANG_SWITCH_KEEP_SECS`, §2.5): 경계를 국소화해 이미 맞게 확정한 앞 언어 구절의 재방출·오염을 막는다.
3. **stale-language retraction**(Exp-171~, §4.3): 전환 직전 잘못 커밋된 이전-언어 토큰을 회수해 경계 부근 오염을 정리한다.
4. **필터 캐스케이드**(`backend.py:635-711`): ForeignLang drop(ko/en 외 언어 토큰 제거)·ScriptMismatch filler drop·script-anchor 언어 재감지·anchor-repeat storm drop — 코드스위칭이 유발하는 환각/이물 언어를 다층으로 거른다.
5. **화자전환 시 경계 오디오만 언어 재감지**(`new_speaker`의 `since_offset`, §4.4): 다화자·다언어에서 이전 화자 언어가 새 화자로 번지지 않게 한다.

> WLK 전략 요약: **전환을 명시적 경계 신호로 승격**하고, 유보 꼬리·retraction·필터로 **경계 단어를 보존**한다. WL의 "락 후 경계" 대비 더 능동적이며, 실제 화자분리와 결합해 **다화자 코드스위칭**(bong1류)으로 확장된다.

### 5.3 대조

| | WL | WLK |
|---|---|---|
| 전환 감지 | 언어 detect + 3회 락 | 언어 detect + 즉시 `pending_switch` 무장 |
| 전환 시 경계 | 문장부호/forced 통해 간접 | `LanguageSwitch` **직접** 경계 |
| 경계 단어 보존 | 반복/퍼지 트림 | 유보 꼬리 재부착 + stale retraction |
| flip-flop 억제 | 히스테리시스 카운트(지연↑) | 필터 캐스케이드 + 2.5s 국소 재디코딩 |
| 다화자 | 불가(spk=언어) | Sortformer 화자분리와 결합 |

---

## 6. 전문용어(군사) 인식 차이 — 근거 기반 설명

배포 PC 실측에서 **WLK가 군/공군/육군 같은 전문용어를 WL보다 잘 인식**하는 경향이 관찰됐다. 직관적으로 "더 큰 모델" 또는 "더 풍부한 사전"을 떠올리기 쉽지만, 코드 근거는 다른 그림을 보여준다.

### 6.1 정정 1 — 모델은 동일 (원인 아님)

둘 다 **whisper-large-v3-turbo fp16**이다.
- WL: [`main.py:71`](../whisperlive_code/main.py) `faster_whisper_custom_model_path="models/faster-whisper-large-v3-turbo"`, `compute_type="float16"`(`server.py:613`).
- WLK: `--model_dir` 기본 `whisperlivekit/model/whisper-large-v3-turbo`(`parse_args.py:118-121`), reference Whisper 디코더 fp16.

turbo는 large-v3의 디코더 4층 프루닝 버전으로 **가중치 계열이 같다**. 모델 세대는 차이 원인이 아니다.
> **이력 각주**: WLK가 실제로 turbo를 돌린 것은 **Exp-158(2026-07-05)**부터다. 그 이전엔 `model_dir` 배선 버그로 표기(turbo)와 무관하게 `base`가 돌았다([docs/MASTER_CHANGES.md](MASTER_CHANGES.md), [EXPERIMENTS.md](../EXPERIMENTS.md) E5). 관찰이 그 이전이면 "WLK=base, WL=turbo"였을 수 있으나, **현행 답은 "동일 모델"**이다.

### 6.2 정정 2 — 사전이 아니다 (오히려 WLK가 비어 있음)

두 세대 다 거의 동일한 `WordCorrectionManager`(JSON 기본사전 + SQLite 사용자사전, 긴 키 우선)를 쓴다(WL `whisperlive_code/manager.py`, WLK `filtering/manager.py`). 그러나 **WLK의 사전은 비어 있다**: [`filtering/admin_replacement.json`](../whisperlivekit/filtering/admin_replacement.json) = `[]`, 사용자 DB 0행. WL이 쌓아둔 `6군→육군`류 ~1000개 리스트는 오류 패턴이 달라 **의도적으로 미이식**됐다([docs/PHASE3_WORD_REPLACEMENT_RESEARCH.md](PHASE3_WORD_REPLACEMENT_RESEARCH.md)). 즉 사후 대치가 원인이라면 WLK가 오히려 불리하다 — **빈 사전으로도 더 잘 잡는다는 사실 자체가 원인이 디코더 쪽임을 방증**한다.

### 6.3 정정 3 — 프롬프트/hotwords도 아니다

- WL: `initial_prompt`/`hotwords` 배선은 있으나 배포에서 **비활성**(`server.py:744` `self.initial_prompt=None`, `main.py:115` `hotwords=None`).
- WLK: `--init-prompt`/`--static-init-prompt` 훅은 있으나 **기본 None·라이브 미배선**(`parse_args.py:305-327`; [PHASE3_WORD_REPLACEMENT_RESEARCH.md](PHASE3_WORD_REPLACEMENT_RESEARCH.md)는 hotword/trie 바이어싱이 레거시 전용/미구현이라 명시).

양쪽 다 도메인 어휘 주입은 실질적으로 꺼져 있다 → 원인 아님.

### 6.4 진짜 원인 — 디코딩 전략 + 품질 게이트

**WL — 타이트 게이트 + 온도 폴백 재샘플링.** 배포 설정([`whisper_1023.txt:1-11`](../whisperlive_code/whisper_1023.txt)): `beam_size=7`, `temperature=[0.0,0.2,0.3,0.4,0.5]`, `compression_ratio_threshold=2.2`, `log_prob_threshold=-1.0`. 세그먼트가 게이트를 못 넘으면 다음 온도로 재디코딩하는데, **온도>0에서는 beam 1 greedy 샘플링으로 떨어진다**(`transcriber.py:1430-1442`):
```python
for temperature in options.temperatures:
    if temperature > 0:
        kwargs = {"beam_size": 1, "num_hypotheses": options.best_of,
                  "sampling_topk": 0, "sampling_temperature": temperature}
    else:
        kwargs = {"beam_size": options.beam_size, "patience": options.patience}
```
폴백은 `compression_ratio > 2.2` 또는 `avg_logprob < -1.0`에서 발동한다(`transcriber.py:1479-1496`). **희귀 군사용어는 본질적으로 avg_logprob가 낮다** → 이 타이트한 `-1.0` 게이트를 넘겨 **beam 1 greedy로 재샘플링**되고, 불확실하지만 맞는 희귀어가 더 흔한 일반어로 치환되기 쉽다. 큰 beam(7)은 여기서 도움이 안 된다 — 손실은 beam 폭이 아니라 폴백/게이트 단계에서 난다.

**WLK — 느슨한 게이트 + 결정론적 beam, 재샘플링 없음.** 배포 설정: `--beams=2`(`parse_args.py:255-261`), `--logprob-threshold=-2.0`(Exp-142, `:329-335`), `--compression-ratio-threshold=3.0`(`:337-343`). AlignAtt beam 디코더는 **온도 0 결정론적 단일 패스**이며(`backend.py:819-820`: beams>1이면 beam decoder), 게이트에 걸리면 **재샘플링이 아니라 드롭(suppress-only)**한다(§2.4, `align_att_base.py:456-458,618-642`). 게이트가 훨씬 느슨해(**CR 3.0 / logprob −2.0**) avg_logprob가 −2.0~−1.0인 **저신뢰-정답 용어가 그대로 살아남는다**.

**핵심 메커니즘 한 줄**: avg_logprob가 −2.0과 −1.0 사이인 맞는 군사용어는 → **WLK는 beam 출력 그대로 확정**, **WL은 플래그돼 greedy 재샘플링으로 흔한 단어로 치환**된다.

### 6.5 보조 요인 — 컨텍스트

- WLK: 15s 롤링 오디오 컨텍스트로 청크 경계를 가로질러 용어를 재-어텐션(§2.5).
- WL: `condition_on_previous_text`로 **자기 출력에 의존**한다. 한 번 오전사한 용어가 다음 창의 프롬프트로 되먹임돼 오류가 전파되고, 고온 폴백 시 `prompt_reset_on_temperature=0.8`로 용어 컨텍스트가 리셋된다. 부차적이지만 WL에 불리하게 작동한다.

### 6.6 정리표

| 요인 | WL | WLK | WLK 용어 인식에 기여? |
|---|---|---|---|
| 모델 | large-v3-turbo (faster-whisper) | large-v3-turbo (reference) | ✗ 동일 세대 |
| 디코더 구현 | CTranslate2 | reference + AlignAtt | △ 간접 |
| 폴백/게이트 | temp 사다리, **beam1 재샘플**, CR 2.2 / logprob −1.0 | **결정론 beam2, drop-only**, CR 3.0 / logprob −2.0 | ✅ **주원인** |
| 프롬프트/hotwords | 배선됐으나 비활성 | 훅만, 미배선 | ✗ |
| 단어대치 사전 | ~1000개 | **빈 사전** | ✗ (오히려 불리) |
| 컨텍스트 | 자기출력 conditioning | 롤링 15s 오디오 | △ 보조 |

---

## 7. 결론 요약

| 축 | WL | WLK | 대표 근거 |
|---|---|---|---|
| 확정 정책 | 반복 N=10 + timestamp 안정성(≈stall 감지) | AlignAtt 어텐션 유도 커밋 + 꼬리 유보 | `server.py:941-978` / `align_att_base.py:433-496` |
| 문장 분리 | 서버→클라 2단계, `.`/`?`·forced·언어전환 | 침묵·언어전환·화자전환 3종 + 온점 형태소 | `client.py:280-386` / `tokens_alignment.py:379-562` |
| 코드스위칭 | 언어 락 히스테리시스(3회) + 문장마다 리셋 | `LanguageSwitch` 1급 경계 + retraction + 필터 캐스케이드 | `server.py:766-776` / `backend.py:635-764` |
| 전문용어 우위 | (게이트 −1.0, 온도 재샘플로 희귀어 치환) | 느슨한 게이트(−2.0)·drop-only로 저신뢰 정답 보존 | `transcriber.py:1430-1496` / `align_att_base.py:618-642` |

**한 줄 결론**: WLK의 전문용어 우위는 더 큰 모델이나 더 큰 사전이 아니라, **재샘플링 없는 결정론적 beam + 훨씬 느슨한 품질 게이트**가 저신뢰-정답 도메인 용어를 그대로 통과시키는 데서 나온다. 문장 분리·코드스위칭 축에서도 WLK는 WL의 "반복·락 기반 보수적 확정"을 "어텐션·마커 기반 능동적 확정"으로 대체하면서, 유보 꼬리·retraction·실제 화자분리로 **다화자 코드스위칭**까지 확장했다.
