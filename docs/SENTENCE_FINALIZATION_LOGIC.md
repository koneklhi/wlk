# 문장 확정·분리 로직 레퍼런스 (Sentence Finalization Logic)

이 문서는 실시간 STT가 **한 문장(=`Segment`/line)을 언제·왜 확정(finalized)하고 분리(경계 생성)하는지**의
전체 로직과 파라미터를 기록한다. `finalize_trigger` 계측 필드(전사 결과·UI 배지)가 붙는 근거이며,
성능 개선 등으로 확정/분리 로직이 바뀌면 **이 문서도 같은 작업 단위에서 갱신**한다(하단 §7 갱신 규약).

> **값의 단일 진실원(SoT)은 코드 상수 정의 위치다.** 이 문서에 적힌 수치는 작성 시점 값이며,
> 각 값에 정의 위치(file:line)를 병기했다. 코드에서 값을 바꾸면 이 표의 수치도 함께 고친다.
> (과거 문서에 하드코딩된 임계치가 코드보다 뒤처져 방치된 사고가 있었다 — 그 재발 방지가 이 규약의 목적.)

---

## 1. 한눈에 — 경계 원인 3종(침묵·언어전환·화자전환) + 온점 형태소 분할, `finalize_trigger` 값 4종

**중요 구분**: "문장 경계를 *만드는* 원인"과 "`finalize_trigger`가 *내보내는 라벨*"은 개수가 다르다.

| finalize_trigger 값 | 분류 | 경계를 만드는가 |
|---|---|---|
| `language_switch` | **독립 경계 원인** | ✅ 한↔영 전환 마커가 줄을 닫음 |
| `speaker_change` | **독립 경계 원인** (diar ON 한정) | ✅ 화자 전환이 줄을 닫음 |
| `silence` | **독립 경계 원인** | ✅ 침묵(VAD pause) 토큰이 줄을 닫음 |
| `punctuation` | **조건부 독립 원인 + 라벨** | △ 온점 형태소 종결(§3.5, Exp-170~)이면 **독립 분할** / 침묵·화자경계로 닫힌 줄의 종결부호면 세분 라벨 |

즉 경계를 만드는 메커니즘은 **음향·마커 3종(침묵·언어전환·화자전환) + 온점 형태소 분할(§3.5)**이다.
`punctuation` 라벨은 두 경로로 붙는다: ① 온점 형태소 종결이 **독립적으로** 줄을 분할할 때(Exp-170~),
② 침묵/화자경계로 닫힌 세그먼트가 `.!?。！？`로 끝나 `silence`/`speaker_change` 대신 붙는 **세분 라벨**일 때.
전수 감사 결과 이 4개 값 외에 UI `lines[]` 경계를 만드는 다른 메커니즘은 없다(§6에 근거).

미확정으로 남는 경우(스트림 진행 중 마지막 줄, 종료 시 강제확정 없음)는 `finalize_trigger = null`.

---

## 2. 확정이 결정되는 최종 지점 (딱 두 함수)

세그먼트의 `finalized`/`finalize_trigger`는 오직 [tokens_alignment.py](../whisperlivekit/tokens_alignment.py)의 두 함수에서 세팅된다.

- **diarization ON** (기본값 `--diarization`): `TokensAlignment.get_lines_diarization()` — `tokens_alignment.py:266`~
- **diarization OFF**: `TokensAlignment.get_lines()`의 비-diar 루프 — `tokens_alignment.py:358`~

두 함수는 매 사이클 토큰 스트림으로부터 세그먼트를 재구성한다. 세그먼트를 닫거나 여는 것은
토큰 스트림에 섞여 들어오는 **3종 신호**(Silence 토큰 / LanguageSwitch 마커 / (diar)화자 변경)와,
**온점 형태소 종결**(`_punct_split_here`가 `sentence_boundary.is_genuine_sentence_end`로 판정 — §3.5)이다.
직렬화는 `Segment.to_dict()` (`timed_objects.py:186`)가 `finalized`/`completed`/`finalize_trigger`를 항상 방출.

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

> **언어 고정 세션에서는 이 트리거가 구조적으로 비활성이다(세션 언어 고정, 2026-07-17~).** 서버 전역 `--lan ko/en`
> 또는 세션 쿼리 `?language=ko/en`으로 `cfg.language != "auto"`인 세션에서는 아래 "arm되는 유일한 게이트"를 무장하는
> `_apply_detected_language` 호출 경로 5곳(①일반/게이트 감지·②주기 재감지·③짧은침묵 리셋·④화자전환 eager·⑤스크립트-앵커
> 재감지)과 간접 재-arm 3종(long-silence·ForeignLang·ScriptMismatch)이 **전부 `cfg.language=="auto"` 게이트/가드로 차단**된다
> (`backend.py` 각 경로의 `if self.model.cfg.language == "auto"` 가드 및 §3.5 짧은침묵 `end_silence` 분기 조건). 따라서 고정
> 세션에서는 `LanguageSwitch` 마커가 방출되지 않고, 그에 딸린 retract(§3.2 하단)·트림도 발생하지 않는다 — `finalize_trigger`에
> `language_switch`가 나타나지 않는다. auto 세션(생략 또는 `?language=auto`)에서만 아래 로직이 활성이다.

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
  5. **스크립트-앵커 재감지(Exp-175~)** `_apply_script_anchor_redetect` — `backend.py:576-618`
     (방출 토큰 스크립트가 잠긴 언어와 연속 N=3단어 또는 T=1.0s 반전 유지 시 재감지 창 2.0s·min_prob 0.90;
     다른 언어 확신 시에만 호출 + 해당 배치 드롭(재디코딩 복구), 같은 언어 재확정 시 no-op(Exp-169),
     불확신(None) 시 streak 유지 재시도. 1~4 트리거가 전부 미발동하는 무음·화자전환 없는 연속 코드스위칭
     구멍을 메움 — Exp-172 실측 근거. 롤백: `SCRIPT_ANCHOR_REDETECT_ENABLED=False`).
  6. 간접 재-arm(다음 infer가 전환을 재확인하도록 `detected_language=None`+`eager` 무장):
     long-silence(≥2.0s) 리셋 `backend.py:234-250`, ForeignLang("(speaking in foreign language)") `backend.py:484-495`, ScriptMismatch 드롭 `backend.py:508-522`.
- **파라미터**:
  - `LANG_SWITCH_KEEP_SECS = 2.5`초 (전환 시 유지 오디오: 감지창 2.0s+완충 0.5s) — `align_att_base.py:13`.
  - `MIN_DURATION_SHORT_LANG_RESET = 0.5`초 — `backend.py:37`.
  - `periodic_lang_check_secs` = 기본 `None`(비활성) — `parse_args.py`(CLI `--periodic-lang-check`).
  - `lang_restrict_koen = True` (한/영 2언어 고정) — `parse_args.py`(`--lang-restrict-koen`).
- **경계 직전/직후 잔존 오언어 텍스트 철회(retraction, Exp-171~174 머지 완료)**: `LanguageSwitch` 마커가
  `retract_from`(재디코딩 구간 시작 절대시각)·`prev_language`(전환 전 언어)를 실어 방출되면(`_apply_detected_language`가
  `is_switch`일 때 arm — `align_att_base.py:218-224`, 마커 부착은 `backend.py:623-627`), 마커가 `all_tokens`에
  append되기 *직전* `_insert_with_reattachment`가 `_retract_stale_language_tokens`를 호출해 diar 이벤트 지연
  동안 구언어 잠금으로 잘못 커밋된 텍스트를 제거한다 — 상세는 §4 표 참조. **경계 개수·위치는 불변** — 마커 자체를
  없애는 게 아니라 마커 앞의 잔존 텍스트만 사라진다.

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
- **경계-앵커 유지(damage B 수정, Exp-171~174 머지 완료)**: `new_speaker`의 `refresh_segment(complete=False)`가
  과거엔 고정 마지막 2청크만 유지해 화자전환 경계 앞쪽 오디오(서두)를 정책적으로 폐기했다. 이제
  `refresh_segment(complete=False, keep_secs=...)`로 `keep_secs = min(self.end - change_speaker.start +
  MARGIN(0.3s), MAX_KEEP(5.0s))`만큼(화자전환 시각부터 현재까지의 실제 경계 오디오 길이)을 유지한다 —
  `backend.py:48-49,322-324`. 유지 후 `global_time_offset`도 과거의 `change_speaker.start` 맹신 대신
  `self.end - segments_len()`(실제 유지 버퍼의 시작 절대시각)으로 재계산한다(`backend.py:340`; eager 언어
  감지가 `_apply_detected_language`를 통해 추가로 `_trim_segments_to_recent`를 호출할 수 있어 그 *이후*에
  계산). 이 재계산이 `refresh_segment` 자체의 `cumulative_time_offset` 승계 메커니즘을 우회하므로, 이중
  가산을 막기 위해 재계산 직후 `cumulative_time_offset`을 명시적으로 0.0 리셋한다.
- **침묵을 사이에 둔 화자전환의 라벨 손실 수정(Exp-187)**: 화자전환이 **침묵 없이 인접**한 경우만
  `tokens_alignment.py`의 `elif segment.speaker != closing.speaker:` 분기(병합 루프 §2)가 잡아
  `speaker_change`를 붙였다. 그러나 실제 화자전환은 대부분 짧은 침묵을 사이에 두고 일어나는데, 이
  경우 병합 루프가 먼저 도달하는 `elif segment.is_silence():` 분기가 화자 비교 없이 무조건
  `silence`/`punctuation`으로 라벨링해 화자전환 정보가 소실됐다(Exp-186이 관찰한 "diar `[NewSpeaker]`
  회차당 수십 건 vs `speaker_change` 트리거 1~4건"의 구조적 원인). 한편 `_apply_silence_grammar_gate`
  → `_gate_decide`는 **이미** `diar_mode and next_seg.speaker != closing.speaker`일 때 문법 판정을
  건너뛰고 강제 분할(`split_grammar`)하고 있었으나, 그 판정 결과가 TriggerAssign 단계로 전달되지
  않았다. 수정: `_apply_silence_grammar_gate`가 분할 결정 시 화자 불일치 여부를 `PuncSegment.
  speaker_boundary`(신규 필드, 내부 전용)에 스탬프하고, TriggerAssign의 `elif segment.is_silence():`
  분기가 `gate_pending` 다음으로 이 플래그를 확인해 `speaker_change`를 우선 배정한다(§3.4 우선순위
  language_switch > speaker_change > punctuation > silence를 코드가 실제로 반영하도록 정정). 순수
  라벨링 수정이라 **세그먼트 병합/분할 자체(경계 개수·위치)·WER·F1은 불변** — `finalize_trigger` 값과
  진단 로그(`branch=silence_speaker_boundary`)만 바뀐다. 테스트: `tests/test_finalize_trigger.py`
  `test_diar_speaker_change_across_silence_gets_speaker_change_trigger`(회귀 방지용
  `test_diar_same_speaker_across_silence_still_gets_silence_trigger`도 추가).
- **짧은 세그먼트 화자 오귀속(노이즈) 방지 — Case B 수정(Exp-188)**: kor1(단일화자 낭독) 실측에서
  Sortformer가 아주 짧은 텍스트 세그먼트(예 "강" — "소모 강요"의 "강요"가 잘린 자리)에만 순간적으로
  다른 화자를 귀속하는 것을 확인했다(`[SilenceGate]` 로그가 같은 침묵 위치에서 재계산 tick마다
  `speakers=(1,1)`→`(1,2)`로 플립 — diar 무상태 재계산 특성상 diarization 데이터가 더 들어올수록
  달라짐). `_gate_decide`의 화자불일치 분기(`diar_mode and next_seg.speaker != closing.speaker`)는
  이 노이즈를 진짜 화자전환과 구분하지 못해 문법상 미종결 단어("강")를 무조건 분할해 Case B를
  만들었다(§3.5 hard-fail). 수정: `get_lines_diarization()`의 화자 귀속 루프가 max-overlap **승자
  diar 세그먼트 자체의 길이**(`MIN_SPEAKER_ATTRIBUTION_SECS = 0.5s`, `tokens_alignment.py`)를 함께
  본다 — `concatenate_diar_segments()`가 동일화자 연속 조각만 병합하므로, 진짜 화자전환은 보통 여러
  조각에 걸쳐 이 문턱보다 길게 남는 반면 순간적 오분류(blip)는 앞뒤 동일화자 조각 사이에 낀 짧은
  조각 하나로 고립된다. 승자 diar 세그먼트가 이 문턱보다 짧고 직전 확정 화자와 다르면, 그 귀속을
  신뢰하지 않고 **직전 확정 화자를 승계**한다(ASR 텍스트 세그먼트 자체의 길이가 아니라 diar
  세그먼트 길이를 기준으로 삼은 이유: 정상적인 짧은 발화/단어는 흔해 텍스트 길이만으로는 노이즈와
  구분 불가 — 회귀 테스트 `test_diar_speaker_change_blocks_merge`가 이 구분을 검증). 순수 화자
  귀속 신뢰도 게이팅이라 정상적인(충분히 긴) 화자전환 로직·우선순위(§3.4)는 불변. 테스트:
  `tests/test_silence_grammar_gate.py::test_diar_short_segment_speaker_flip_does_not_force_case_b_split`.
- **긴 침묵 안전망의 단어 중간 분절 방지 — Case B 수정(Exp-190)**: `_gate_decide`(및 비-diar `_gate_intake_nondiar_silence`)의 `split_hard` 분기는 `d_eff >= SILENCE_HARD_SECS(1.2s)`이면 문법·화자·언어 판정을 **모두 건너뛰고 무조건 분할**하는 안전망이었다(diarization/문법 판정이 영영 pending에 머무는 것 방지). 그러나 kor1(낭독체) 실측에서 문장 중간의 긴 호흡 pause(예 "2040년" 뒤 3.59s)에도 그대로 발동해 미종결 어절을 단어 중간에서 강제분할하는 Case B("2040년 국방."⏎"환경을…")를 만들었다(`[SilenceGate] d_eff=3.59 last_word='2040년' speakers=(1,1) langs=('ko','ko') path=split_hard`). 임계값 상향(방향 A)은 실측 3.59s가 상한 2.0s(backend long-silence 리셋과의 불변식)를 넘어 불가. 수정(방향 B): `split_hard` 분기에 **문법-조건부 가드** 추가 — `should_split_after_silence(closing, next)`가 명백한 미종결(`False`)을 반환하면 하드 분할을 건너뛰고 아래 memo/pending/문법·화자·언어 경로로 폴백한다(§3.1). 종결어미(`True`)·영어 다음어절 미도착(`None`)은 기존대로 즉시 분할해 안전망을 유지하고, 무한 pending 방지는 `PENDING_RESOLVE_CAP(2.0s)`이 담당한다. 미종결 어절이 같은 화자·같은 언어면 병합(→ "국방환경을 고려한…" 보존), 화자/언어가 다르면 폴백 경로의 기존 분기가 여전히 분할한다. **분할을 새로 만들지 않고 제거만 하므로 신규 Case B를 유발할 수 없다.** 테스트: `tests/test_silence_grammar_gate.py::test_diar_hard_secs_does_not_split_mid_word_case_b`(RED→GREEN) + `test_diar_hard_secs_splits_when_sentence_final`(안전망 미무력화 회귀가드). **주의**: kor1 "소모 강요" 지점의 Case B는 이 split_hard가 아니라 화자오귀속(diar-flip) 유발 `split_grammar`(Exp-188 소관)로 이 수정 범위 밖.

### 3.4 `punctuation` — 라벨 의미 (두 경로)

`punctuation` 라벨은 두 경우에 붙는다:
1. **온점 형태소 종결이 독립적으로 줄을 분할**할 때(§3.5, Exp-170~) — 이 경우 punctuation은 **독립 경계 원인**이다.
2. **침묵(3.1)/화자경계(3.3)로 닫힌** 세그먼트의 텍스트가 종결부호로 끝날 때 — `silence`/`speaker_change`의 세분 라벨.

- 판정: `TimedText.has_punctuation()` — 텍스트 끝 문자가 `PUNCTUATION_MARKS = {. ! ? 。 ！ ？}`인지
  (`timed_objects.py:4,28-30`).
- **우선순위**(동시 발생 시): `language_switch` > `speaker_change` > `punctuation`(온점 형태소) > `silence`
  — diar 라벨 분기 `tokens_alignment.py:320-328`. 화자가 동시에 바뀌면 `speaker_change`가 온점보다 우선.
  **(Exp-187 이전엔 화자전환이 침묵을 사이에 두고 일어나면 이 우선순위가 지켜지지 않고 `silence`/
  `punctuation`으로 라벨이 밀렸다 — §3.3 "침묵을 사이에 둔 화자전환의 라벨 손실 수정" 참조. 현재는
  `speaker_boundary` 플래그로 정정돼 문서상 우선순위와 코드가 일치한다.)**

### 3.5 `punctuation`(온점 형태소 종결) — 독립 문장 경계 (Exp-170~)

Whisper가 찍는 마침표(`.`/`。`)를 문장 분할 신호로 쓰되, **진짜 종결과 거짓 마침표**(한국어 어간·조사 중간
온점, 영어 약어, 소수점)를 형태소로 판별해 분할한다. `?`/`!`는 1차 범위 제외(소수점·약어 위험이 없어 현행 (a)/(b) 유지).

- **판별기**: `whisperlivekit/sentence_boundary.py`(순수 함수). `is_genuine_sentence_end(closing_text, next_text)`가
  닫히는 세그먼트 누적 텍스트로 판정하고, 온점 앞 어절의 **스크립트(한글/라틴)**로 언어를 라우팅한다:
  - 한국어 `is_sentence_final_ko`: `KO_FINAL_SUFFIXES`(니다/어요/세요/구나/았다… 종결어미)로 끝나고
    `KO_EXCLUDE_SUFFIXES`(니까/으로/는데/다는… 연결어미·조사)로 끝나지 않으면 종결. **bare 단음절(군/네/다/까)은
    명사·조사 충돌로 제외**(오탐 방어 핵심 — "주한미군"·"저는" 미분할).
  - 영어 `is_abbreviation_en`(Mr/U.S/etc/단일대문자)이 **아니고**, 다음 어절이 대문자 시작일 때만 종결
    ("island. or"[소문자]는 미분할, "film. So"[대문자]는 분할).
  - 소수점: 종결 온점 직전 문자가 숫자면(서수·열거·소수) 분할 안 함. "3.1"은 토큰 병합상 `has_punctuation=False`라 구조적으로 안전.
- **분할 게이트**: `_punct_split_here(idx, start_idx)`(`tokens_alignment.py:169`)가 기존 (a)발화끝/(b)Silence
  (`_punct_split_justified`)에 (c) 온점 형태소 종결을 추가. `compute_punctuations_segments`(:213)가 호출.
- **diar 병합 생존**: 온점 형태소 분할 세그먼트에 `PuncSegment.punct_boundary=True`를 세팅해, 같은 화자여도
  병합 루프(`tokens_alignment.py:310`)가 재합침하지 않게 한다(병합조건·전파·라벨 3곳 일관). 라벨은 :326에서 `"punctuation"`.
- **비-diar 경로**: `_nondiar_punct_split_pending`(`tokens_alignment.py:357`)이 직전 줄이 종결 온점으로 끝나고
  다음 토큰이 새 문장을 열면 선-분할, `finalize_trigger="punctuation"`(:441).
- **파라미터**: §5 `KO_FINAL_SUFFIXES`/`KO_EXCLUDE_SUFFIXES`/`EN_ABBREV`(SoT=`sentence_boundary.py`).
- **측정(Exp-170)**: 출력 계층 전용이라 **WER 중립**(단어 시퀀스 불변). **구 regime**에서는 정답이 화자전환(문단)
  경계 기준이라 문장 분할을 credit 못 했으나(당시 채택 근거 = 목표·정성·WER 중립), **신 regime v2**는 신형식
  정답(`test_data/<name>.txt`, `[spkN]` 헤더 포함 canonical)의 화자 블록 내 줄바꿈으로 **문장분리 F1**을 별도 산출한다
  (측정·구현 계획 = [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md); 우선순위 화자분리 F1 > WER > 문장분리 F1).
- **[금지] Case B — 단어 중간 over-split**: 온점 형태소 분할이든 침묵(§3.1)·화자경계(§3.3) 과분할이든, 한
  단어/문장이 **단어 중간에서 쪼개져** 확정되면(예 "…지도를 올렸"⏎"습니다") **critical 실패**다(Exp-173 "단어 내부
  미세정적 오분할 방지" 계열). 원칙: under-split(미분리)은 허용, **단어중간 over-split은 금지** — 판별기
  (`sentence_boundary.py`)와 분할 게이트가 이를 방지해야 한다.

---

## 4. 경계에 "영향은 주되 생성하지 않는" 메커니즘

아래는 텍스트를 유예·이동·드롭·리셋할 뿐 **새 `lines[]` 경계를 만들지 않는다**(간접 영향만).
확정 트리거 로직을 바꿀 때 이들과의 상호작용을 반드시 검토한다.

| 메커니즘 | 위치 | 분류 | 영향 |
|---|---|---|---|
| 확정 유예 `_apply_finalize_grace` | `tokens_alignment.py:331-348` (`FINALIZE_GRACE_SECS=2.0`, `:20`) | 타이밍 수정자 | 침묵 직후 유예창 내 직전 세그먼트 `finalized`를 False로 되돌리고 trigger 무효화(None). 경계 위치 불변, 확정 타이밍만 조정 |
| 꼬리 재귀속(비-diar) `_reattach_tail_nondiar` | `tokens_alignment.py:312-329` (`TAIL_REATTACH_EPS=0.05`, `:19`) | 병합(이동) | 유보된 꼬리 단어를 침묵 앞 세그먼트로 되붙임. 경계 개수 불변 |
| 삽입 재귀속 `_insert_with_reattachment` | `tokens_alignment.py:81-103` (`TAIL_REATTACH_MAX_LOOKBACK_SECS=1.5`, `:25`) | 타이밍 수정자 | Silence 앞 꼬리 토큰 재정렬. is_boundary 만나면 중단(경계 넘김 금지) |
| 과거분 제거 `_prune` | `tokens_alignment.py:220-254` (`_DEFAULT_RETENTION_SECONDS=inf`, `:21`) | 제거됨(no-op) | 무제한 리텐션으로 변경(`300.0`→`inf` 패치)되어 상시 조기 반환 — 더 이상 세그먼트를 드롭하지 않음. 신규 경계 무관 |
| `filter_segments` | `whisperlivekit/filtering/__init__.py` | 드롭/치환 | CJK·가나·비음성주석·환각·구두점-only 세그먼트 드롭 + 단어 치환. 라인이 사라질 순 있으나 새 경계 생성 안 함 |
| `_append_terminal_punctuation` | `audio_processor.py:32-43` | 표시 수정자 | finalized 세그먼트 끝에 온점 부착(멱등, WER·경계 무영향) |
| 환각/반복 필터 (BatchRepeat/CrossBatch/단일음절/ScriptMismatch/AnchorStorm) | `backend.py:354-413, 448-465, 505-548` | 드롭 | 토큰/배치 드롭. Silence/LanguageSwitch 마커 미방출 → 경계 직접 생성 안 함(텍스트 억제로 간접 영향) |
| QualityGate (logprob/compression) | `align_att_base.py:592-645` (`quality_gate_reset_after=3`) | 드롭/디코더리셋 | 저품질 세그먼트 억제. refresh는 디코더 내부 상태만 리셋, 마커 미방출 |
| stall 복구 refresh | `backend.py:554-563` (`STALL_RECOVER_SEC=10.0`, `:41`) | 디코더리셋 | 마커 미방출 → 경계 직접 생성 안 함 |
| 버퍼 최대길이 트림 `audio_max_len` | config/`parse_args.py` (`--audio-max-len`) | 타이밍 수정자 | 디코더 버퍼 상한 — 타임스탬프 영향, 경계 미생성 |
| 스트림 종료 flush (SENTINEL/`_finish_transcription`) | `audio_processor.py:28,311-338,740-746` | flush | 남은 토큰 flush. **강제 finalize/경계 생성 없음** — 마지막 줄은 Silence/boundary가 없으면 `finalized=false`로 남음(트리거 null) |
| 언어전환 경계 철회 `_retract_stale_language_tokens` (Exp-171~174 머지 완료) | `tokens_alignment.py:141-178` (`RETRACT_EPS=0.05`, 잠정) | 드롭(구언어 잔존) | `LanguageSwitch` 마커 append 직전 `all_tokens` 꼬리를 역스캔해 `prev_language` 스탬프 텍스트 토큰 제거 — 구역1(`start≥boundary_t-EPS`): 언어매치만으로 제거, 구역2(하한~구역1 사이): +반대스크립트일 때만 제거. Silence/boundary 만나면 스캔 중단. 마커·경계 개수 불변, 마커 앞 잔존 텍스트만 사라짐 |

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
| `KO_FINAL_SUFFIXES` | 니다/어요/세요/구나/았다… | `sentence_boundary.py` | 한국어 종결어미(온점 형태소 분할, §3.5) |
| `KO_EXCLUDE_SUFFIXES` | 니까/으로/는데/다는… | `sentence_boundary.py` | 연결어미·조사 차단(오탐 방어) |
| `EN_ABBREV` | mr/us/un/etc… + 단일대문자 | `sentence_boundary.py` | 영어 약어 배제(온점 형태소 분할, §3.5) |
| 언어감지 문턱 | 일반 `2.0`s / eager `1.5`s+p≥0.85 | `align_att_base.py:225-235` | 전환 arm 조건 |
| `RETRACT_EPS`(Exp-171~, **잠정**) | `0.05`s | `tokens_alignment.py` | 철회 구역1/구역2 경계 지터 여유 — 추가 실측 후 보정 여지 |
| 철회 스캔 하한(Exp-174 정정) | `retract_floor`(재디코딩 창 시작) 우선, `None`이면 `boundary_t - LANG_SWITCH_KEEP_SECS - 1.0`s 폴백 | `tokens_alignment.py:_retract_stale_language_tokens` | 역방향 스캔 하한 — 재디코딩 불가능한 서두 토큰 철회 방지 |
| `SCRIPT_ANCHOR_REDETECT_ENABLED`(Exp-175~) | `True` | `backend.py:184` | 스크립트-앵커 재감지 게이트 롤백 플래그 |
| `_SCRIPT_ANCHOR_N_WORDS`(Exp-175~, **잠정**) | `3`단어 | `backend.py:185` | 반대-스크립트 연속 단어 문턱(Exp-172 실측; N=2 오트리거·N=4 미발동 스윕 확인) |
| `_SCRIPT_ANCHOR_T_SECS`(Exp-175~, **잠정**) | `1.0`s | `backend.py:186` | 반전 지속 시간 문턱(Exp-172 실측) |
| 스크립트-앵커 재감지 창(Exp-175~, **잠정**) | `2.0`s·p≥`0.90` | `backend.py:187-188` | 트리거 시 `detect_current_language` 창·확신 문턱 |
| `_NEW_SPEAKER_KEEP_MARGIN`(Exp-171~) | `0.3`s | `backend.py:48` | 화자전환 경계-앵커 유지 여유(damage B 수정) |
| `_NEW_SPEAKER_MAX_KEEP`(Exp-171~) | `5.0`s | `backend.py:49` | 화자전환 유지 오디오 상한(과거 keep=4.5 환각 전례 반영) |
| `MIN_SPEAKER_ATTRIBUTION_SECS`(Exp-188) | `0.5`s | `tokens_alignment.py` | 승자 diar 세그먼트가 이보다 짧고 직전 화자와 다르면 귀속 불신 → 직전 화자 승계(짧은 세그먼트 화자오귀속 노이즈 방지, §3.3) |
| `SILENCE_HARD_SECS`(Exp-176~; Exp-185→1.2; Exp-190 문법-조건부화) | `1.2`s (≤2.0 불변식) | `tokens_alignment.py` | 침묵 안전망 문턱 — d_eff≥이 값이면 하드 분할. Exp-190부터 `should_split_after_silence`가 미종결(False) 판정 시 이 분기를 건너뛰고 pending/문법 경로 폴백(단어 중간 분절 방지) |
| `PENDING_RESOLVE_CAP`(Exp-176~) | `2.0`s | `tokens_alignment.py` | 게이트가 B 도착을 기다리는 최대 시간(silence.end 기준) — 초과 시 문법 무관 분할확정(무한 pending 방지). Exp-190 이후 미종결 어절의 하드 분할 유예를 이 캡이 최종 보증 |

디코더 파라미터(간접 영향: 어떤 텍스트가 나오는지에 영향, 경계는 §3의 3신호가 전담) —
`frame_threshold`, `beams`, `logprob_threshold`, `compression_ratio_threshold` 등은
[docs/TESTING.md](TESTING.md)·`parse_args.py` 참조.

---

## 6. 전수 감사 결론 (판정 근거)

`{silence, punctuation, language_switch, speaker_change}`가 `finalize_trigger` 방출값의 **전부**임을 확인했다
(`tokens_alignment.py`의 문자열 리터럴 대입 지점 전수 grep). 실제 경계 생성 메커니즘은 **음향·마커 3종
(침묵·언어전환·화자전환) + 온점 형태소 종결(§3.5, Exp-170~)**이다. `punctuation`은 온점 형태소 분할이
독립적으로 줄을 닫거나(§3.5), 침묵/화자경계로 닫힌 줄이 종결부호로 끝날 때(§3.4) 붙는다. §4의 모든 메커니즘은
텍스트를 드롭·이동·유예·리셋할 뿐 경계 마커/세그먼트를 새로 만들지 않으므로 UI 경계를 생성하지 않는다.
**누락된 경계 생성 메커니즘: 없음.**

---

## 7. 갱신 규약 (이 문서를 최신으로 유지하는 법)

**아래 코드가 바뀌면 같은 작업 단위(커밋)에서 이 문서도 갱신한다.** 갱신 대상 절을 함께 표기:

| 바뀐 코드 | 갱신할 이 문서의 절 |
|---|---|
| `tokens_alignment.py`의 `finalize_trigger` 대입 지점·조건 (확정 로직) | §2, §3 (해당 트리거), §6 |
| `sentence_boundary.py` 판별기 목록·로직 (KO_FINAL/KO_EXCLUDE/EN_ABBREV·`is_genuine_sentence_end`·`_punct_split_here`) | §3.5, §5 |
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
