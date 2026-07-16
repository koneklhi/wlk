# 코드스위칭 실시간 전사 설계 보고서

> **범위**: 현재 `master` 브랜치에 머지된 STT 파이프라인이 **① WER(전사 정확도) ② 문장 분리/확정 ③ 한↔영 코드스위칭**을 각각 어떤 로직으로 처리하는지 코드 레벨로 정리한다. 값·라인의 단일 진실원(SoT)은 코드다 — 본문 `file:line`은 작성 시점 실측값이며, 개념 레퍼런스는 [SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md)·[MASTER_CHANGES.md](../MASTER_CHANGES.md), 시행착오는 [../../EXPERIMENTS_LOG.md](../../EXPERIMENTS_LOG.md)에 있다.
>
> **핵심 배경**: 상위 라이브러리 `whisperlivekit 0.2.20`을 벤더링하고 디코딩 정책을 **SimulStreaming(AlignAtt)** 으로 고정했다. AlignAtt 실출력 토큰엔 **구두점이 없어** 구두점 기반 확정이 원천적으로 안 되고, 언어가 한 번 잠기면 고착되는 성질이 있다 — 아래 로직들은 대부분 이 두 성질에 대한 대응이다.

## 0. 전체 구조 — 3레이어 파이프라인

전사 한 사이클은 세 레이어를 통과한다. 어느 레이어에서 개입하는지가 각 로직의 성격을 규정한다.

| 레이어 | 파일 | 무엇을 하나 | 개입 시점 |
|---|---|---|---|
| **디코더 레이어** | `simul_whisper/align_att_base.py`, `simul_whisper.py` | 로짓/가설 조작, 언어 감지·전환, 품질 게이트, DRY | 토큰이 커밋되기 **전** |
| **배치/후처리 레이어** | `simul_whisper/backend.py` `process_iter` | 방출 배치 단위 필터·게이트·언어전환 마커 삽입 | 토큰 방출 **직후** |
| **정렬/표시 레이어** | `tokens_alignment.py`, `filtering/__init__.py` | 세그먼트 재구성·문장 경계·철회·정규식 필터·사전 교정 | UI 라인 생성 시 |

> **중요 사실 두 가지 (설계 함정)**
> 1. `filtering/hallucination.json`은 현재 **빈 배열 `[]`** 이다 → 부분문자열 기반 환각 드롭은 현재 **무동작(no-op)**. 런타임 환각 억제는 전적으로 디코더 게이트 + 배치 storm/스크립트 게이트 + 정규식이 담당한다.
> 2. 배포 서버는 `basic_server.py` → `parse_args()`의 **argparse 기본값**으로 뜬다. `WhisperLiveKitConfig`의 **dataclass 기본값**(`config.py:56-70`)은 일부(logprob·CRT·beams·audio_max_len) 값이 다르며, 프로그램적으로 `WhisperLiveKitConfig()`를 argparse 없이 만들면 **QualityGate가 조용히 비활성**된다. 운영 기준값은 항상 `parse_args.py`다.

---

## 1. 코드스위칭 처리 로직 (한↔영)

코드스위칭 처리의 목표는 "한 발화 안에서 언어가 바뀌는 순간을 제때 감지해 ① 새 언어 토크나이저로 전환하고 ② 문장 경계를 긋되 ③ 전환 경계의 서두 단어를 잃지도 중복하지도 않는 것"이다. 아래 7개 메커니즘이 이 문제를 층층이 방어한다.

### 1.1 언어 감지·전환 코어 — `align_att_base.py`

**감지 프로브** `detect_current_language(window_secs=1.5, min_prob=0.90, since_offset=None)` (`align_att_base.py:284-324`)
- `@torch.no_grad()`로 감싼 **순수·무상태** 프로브. no_grad는 필수 — 없으면 turbo 인코더 forward가 autograd 그래프를 보존해 0.2s→32s(~160배)로 폭주하며 실시간 stall을 일으킨다(Exp-158 사고).
- 버퍼 오디오를 이어붙여 최근 `window_secs`만 슬라이스, `lang_id` 실행, **top 언어의 확률 ≥ `min_prob`일 때만** 반환하고 아니면 `None`(불확신 → 전환 안 함).
- `since_offset` 하한 당김(`:310-312`): 지정 시 그 이전 오디오를 배제한다(상한 `window_secs`는 유지). 화자전환 직후 새 화자 오디오가 짧을 때 "무조건 마지막 window_secs" 슬라이스가 **직전 화자 오디오로 지배돼 오판**하는 것을 막는 핵심 파라미터(§1.6).

**전환 코어** `_apply_detected_language(lang, skip_trim=False)` (`align_att_base.py:198-231`)
- 현재 언어는 `state.detected_language`에 보관. 전환 판정(`:205-207`):
  ```python
  prev_lang = self.state.detected_language or self.state.lang_before_reset
  self.state.lang_before_reset = None            # consume-once
  is_switch = prev_lang is not None and prev_lang != lang
  ```
  `lang_before_reset`은 상태 리셋(new_speaker·ForeignLang·스크립트불일치 게이트)이 `detected_language`를 `None`으로 지운 뒤에도 **직전 언어를 1회 이월**해, 리셋 직후의 진짜 전환을 여전히 감지 가능하게 한다.
- **전환 시 재디코딩 트림**(`:209-210`): `is_switch`이고 `skip_trim=False`면 `_trim_segments_to_recent(LANG_SWITCH_KEEP_SECS=2.5)` (상수 `:14`, "감지창 2.0s + 완충 0.5s"). 버퍼 앞부분을 버리고 ~2.5s만 남긴 뒤 `cumulative_time_offset`을 누적 → 다음 `infer()`가 **전환 경계 오디오만 재디코딩**한다. 이것이 "전환 세금"(이미 방출한 구절의 재방출)을 제거하는 핵심.
- 토크나이저/디코더는 전환 여부와 무관하게 리셋: `create_tokenizer(lang)` → `init_tokens()`(SOT 언어토큰 갱신) → `init_context()`.
- **마커 arm**(`is_switch`일 때만, `:218-228`):
  ```python
  self.state.pending_language_switch = global_time_offset + segments_len()  # 재디코딩 시작 절대시각(=버퍼 끝)
  self.state.pending_retract_from    = pending_language_switch
  self.state.pending_prev_language   = prev_lang
  self.state.pending_retract_floor   = pending_language_switch - segments_len()  # 트림된 버퍼의 시작(재디코딩 가능 하한)
  ```
- 최초 감지(`prev_lang is None`)나 `skip_trim=True`는 트림도 마커 arm도 하지 않는다.

### 1.2 언어전환 마커 + 경계 철회(retraction) — Exp-171/174

**마커** `LanguageSwitch` (`timed_objects.py:124-142`): 텍스트 없는 내부 경계 마커(`is_boundary()==True`), **FrontData로 직렬화 안 됨**(스키마 무변). 필드: `detected_language`(전환 후 언어)·`retract_from`(철회 재디코딩 구간 시작 절대시각)·`prev_language`(철회 대상=전환 전 언어)·`retract_floor`(철회 하한=트림 버퍼 시작).

**마커 삽입** `process_iter` (`backend.py:735-764`): `pending_language_switch`가 arm된 상태에서 **새 전환후 배치가 실제로 나올 때만** 첫 토큰 앞에 마커를 붙이고 4개 `pending_*`를 클리어한다. 재디코딩이 아무것도 못 내면 마커도 철회도 없다(안전한 실패 모드).

**2구역 철회 규칙** `_retract_stale_language_tokens(boundary_t, prev_lang, redecode_floor)` (`tokens_alignment.py:141-198`): 마커가 `all_tokens`에 편입되는 순간(`_insert_with_reattachment:128-132`) 호출돼, 꼬리부터 역스캔하며 diar 이벤트 지연 동안 **구언어로 잘못 커밋된 텍스트**를 제거한다.
- **구역1** (`start ≥ boundary_t − RETRACT_EPS`): 텍스트 토큰이고 `detected_language == prev_lang`이면 **무조건 철회**(재디코딩이 대체할 구간).
- **구역2** (`[하한, boundary_t − EPS)`): `_is_opposite_script(text, prev_lang)`가 **추가로 참일 때만** 철회(혼합 스크립트 토큰은 보수적으로 보존).
- Silence/boundary 만나면 스캔 **즉시 중단**(경계 넘지 않음). `RETRACT_EPS=0.05`(프레임 양자화 여유).

**`retract_floor` 정정** (Exp-174, `b283cc8`): 하한 선택(`:160-163`)
```python
lower_bound = redecode_floor if redecode_floor is not None else boundary_t - LANG_SWITCH_KEEP_SECS - 1.0
```
트림이 버퍼 앞을 버렸으므로 트림 시작 이전 토큰은 **재디코딩으로 재현 불가**하다. 철회가 그 아래까지 내려가면 대체물 없이 서두 토큰을 지워 **순유실**이 난다(bong1 "You don't understand" 4단어 유실이 이 버그였음). `retract_floor`(= 재디코딩 창 시작)를 마커에 실어 하한으로 쓰면 창 이전 서두는 보존하고 창 안의 진짜 오언어 중복만 철회한다. `else` 분기는 이 필드가 없는 구마커용 폴백.

### 1.3 언어 재감지 트리거 5종 (`_apply_detected_language` 진입점)

전환 후보는 아래 5개 경로에서만 발생한다:

| # | 트리거 | 조건 | 위치 |
|---|---|---|---|
| 1 | 짧은 침묵 리셋 `_check_short_silence_language` | 침묵 ≥ `MIN_DURATION_SHORT_LANG_RESET=0.5s` + lang=auto | `backend.py:625-627` |
| 2 | 긴 침묵 리셋 | 침묵 ≥ 2.0s → `detected_language=None`+eager arm(간접 재감지) | `backend.py` long-silence 블록 |
| 3 | 화자전환 eager `new_speaker` | window 1.5s·p≥0.85, 경계 이후 오디오만(§1.6) | `backend.py:321-391` |
| 4 | 주기 재감지 `_maybe_periodic_lang_check` (PLC) | **기본 None=비활성** | `align_att_base.py:281` |
| 5 | **스크립트-앵커 재감지** (§1.4, 최신) | 출력 스크립트가 N=3단어/T=1.0s 반전 | `backend.py:576-616` |

**PLC가 기본 비활성인 이유(Exp-160)**: PLC=4.0은 확률 기반 주기 체크라 ytn2에서 스퓨리어스 전환을 일으켜 방송 클로징 환각("Thank you"류)을 유발했다. 트리거 1~4로 커버되지 않는 "무음·화자전환 없는 연속 코드스위칭"이 §1.4의 존재 이유다.

### 1.4 스크립트-앵커 재감지 게이트 (Exp-175, 최신 머지 `cf0cd2c`) — `backend.py`

**해결하는 구멍**: 위 트리거 1~4는 전부 침묵이나 화자전환을 전제한다. 둘 다 없이 언어만 바뀌면(ytn2형 무휴지 전환) 구언어가 고착돼 새 언어 서두가 오디코드/유실되고 `LanguageSwitch` 마커도 안 생겨 한↔영이 같은 줄에 접착된다.

**동작**: `lang_id` 확률이 아니라 **실제 방출 토큰의 스크립트가 잠긴 언어와 지속 반전**하는지를 본다(→ Exp-160 스퓨리어스 전환에 면역: 스퓨리어스 전환은 한글을 계속 방출하므로 반전 streak가 안 쌓인다).
- 상수(`:184-188`): `SCRIPT_ANCHOR_REDETECT_ENABLED=True`(롤백 플래그)·`_SCRIPT_ANCHOR_N_WORDS=3`·`_SCRIPT_ANCHOR_T_SECS=1.0`·재감지창 `2.0s`·min_prob `0.90`.
- `_update_script_anchor_streak` (`:537-574`): 배치 끝 누적 판정. `_is_opposite_script`(TTR 없는 순수 스크립트, tokens_alignment)면 streak 누적, 숫자·기호는 중립 스킵, **잠긴 스크립트가 섞이면 리셋**("I think 그건"류 정상 삽입 오탐 방어). `len(streak) ≥ 3` **또는** 지속 `≥ 1.0s`면 발동.
- `_apply_script_anchor_redetect` (`:576-616`): 발동 시 `detect_current_language(2.0, 0.90)` 프로브 →
  - `None`(불확신): 미적용, **streak 유지**(다음 배치 재시도).
  - 같은 언어 재확정: **no-op + streak 리셋**(Exp-169 재환각 루프 방지 — `refresh_segment` 미호출).
  - 다른 언어 확신: `_apply_detected_language(new_lang)` 위임(§1.1의 트림+마커+retract_floor 재사용) + **해당 배치 드롭 `[]`**. 트림이 남긴 경계 오디오 재디코딩으로 서두 복구.
- 삽입점: `process_iter` ScriptMismatchFilter **직후**·AnchorRepeatFilter **앞**(확신 전환이 먼저 이기고, 불확신 배치만 storm 검사로 흘러감).
- 실측: diar `[NewSpeaker]`(1~2s 지연)보다 **선제** 발동, 발동 전수 정당(오탐 0), Exp-172 확정 유실 사례 직접 복구. N 스윕으로 N=2 오트리거·N=4 미발동 확인 → N=3 유지.

### 1.5 스크립트 불일치 필러 게이트 (Exp-168 `8aeb5a2`) — `backend.py`

EN→KO 전환 직후 "Thank you"류 필러가 실제 한국어 발화를 통째로 삼키는 현상을 차단한다. 기존 4개 필터(§2)는 "완전동일반복" 또는 "한국어 전용" 전제라 "영어+변주" 필러를 원리상 통과시켰다(특히 `BatchRepeatFilter`가 `[가-힣]` 매치라 한글 0개 영어 필러엔 진입 못 함 — 결정적 사각지대).
- `_is_script_mismatch_filler(text, detected_language)` (`:69-89`): **특정 문구 하드코딩 없음**. `detected_language`와 **순수 반대 스크립트**로만 구성 + 단어 ≥ `_SCRIPT_MISMATCH_MIN_WORDS=6` + type-token ratio ≤ `_SCRIPT_MISMATCH_TTR_THRESHOLD=0.6`(붕괴한 TTR = 반복 시그니처)면 필러 판정. 정상 코드스위칭은 TTR가 높아 통과(오탐 방어).
- `_update_script_mismatch_streak` (`:480-511`): 실측 배치가 1~3토큰뿐이라 단일배치 판정 불가 → cross-batch 누적(cap 40단어). 정상 콘텐츠 재개 시 streak 클리어.
- 발동(`:656-675`): `[ScriptMismatchFilter]` 로그 후 ForeignLang과 동일 arm(재감지 무장) + **배치 드롭**. `refresh_segment` 미호출(Exp-163 회귀 교훈).

### 1.6 화자전환 eager 감지 `since_offset` (Exp-168 `0fed0d5`) — `backend.py:321-391`

`new_speaker`가 화자전환 경계시각의 **버퍼 상대 오프셋**을 계산해 `since_offset`으로 전달(`:336-339`):
```python
boundary_offset = change_speaker.start - self.model.global_time_offset
eager = self.model.detect_current_language(1.5, 0.85, since_offset=boundary_offset)
```
이 시점 `global_time_offset`은 아직 현재 버퍼 시작 절대시각이므로 `boundary_offset`은 "이 버퍼 안에서 화자가 바뀐 위치". 이를 `since_offset`으로 넘겨 **전환 이전 오디오를 감지 창에서 배제** → 1.5s 창이 직전 화자 오디오로 지배되지 않음. 함께: `refresh_segment(complete=False, keep_secs=min(end−change_speaker.start+0.3, 5.0))`로 화자전환 경계 서두 유지(고정 `[-2:]` 컷 폐기, `_NEW_SPEAKER_KEEP_MARGIN=0.3`·`_NEW_SPEAKER_MAX_KEEP=5.0`), `global_time_offset`을 `end−segments_len()`으로 재계산 + `cumulative_time_offset=0.0` 리셋(이중가산 방지).

### 1.7 언어 고정 `lang_restrict_koen` (기본 True)

`--lang-restrict-koen`(`parse_args.py:385-390`, 기본 True) → 언어 감지 후보를 **{ko, en}으로 제한**. 텍스트 필터가 아니라 lang-id 제약으로, 제3언어 오감지가 오언어 환각을 seed하는 것을 원천 차단(CLAUDE.md §3.2 한/영 고정 불변 제약 직결).

---

## 2. WER 개선 로직 (환각·반복 억제)

WER 회귀의 주범은 반복 아티팩트(`바 바 바`)·언어 고착 환각·필러 storm이다. upstream 기본값만으론 WER 100%를 넘겼다(sbs1 108.3%). 개입 레이어별로 정리한다.

### 2.1 디코더 레이어 (토큰 커밋 전)

**DRY penalty** `_apply_dry_penalty` (`align_att_base.py:571-616`, 호출 `:390`) — script-agnostic. text-generation-webui DRY 샘플러 이식. 디코딩 중 이미 나온 verbatim 접미를 찾아 그것을 **연장할 토큰의 로짓을 지수적으로 페널티**(`penalty = 1.0 × 2.0^(length−2)`, length≥2). 하드 드롭이 아닌 소프트 억제 — 토큰이 커밋되기도 전에 반복 루프를 꺾는다.

**QualityGate** `_quality_gate` (`align_att_base.py:618-642`, 호출 `:456`, **`not is_last`일 때만**):
- avg-logprob 게이트: 세그먼트 평균 logprob `< -2.0`이면 **가설 전체 억제**(Exp-142 채택).
- compression-ratio 게이트: `compression_ratio(text) > 3.0`이면 억제(언어 무관 반복 백스톱).
- `_on_quality_suppressed` (`:653-671`): 억제가 **구두점-only가 아닐 때만** streak 카운트(구두점-only는 refresh가 다음 문장 첫 음절을 버리므로 제외 — Exp-154 안전장치). streak가 `quality_gate_reset_after=3` 도달 시 `refresh_segment(complete=True)`.

**no-speech 게이트** `_check_no_speech` (`simul_whisper.py:338-345`, 세그먼트 시작만): SOT 인덱스 로짓 softmax의 no_speech 확률 `> nonspeech_prob=0.5`면 세그먼트 무방출(비음성 구간 환각 억제).

### 2.2 배치 레이어 `_filter_cross_batch_repetitions` (`backend.py:419-478`)

upstream `_filter_repetitions`는 단일 `update()` 배치 내부만 봐서 토큰이 1개씩 오는 스트리밍의 **배치 경계 반복**을 놓쳤다. 순서대로:

| 필터 | 성격 | 조건·동작 | 위치 |
|---|---|---|---|
| `[BatchRepeatFilter]` | **한국어 전용** | `[가-힣]` 단어 ≥4 + 최빈 ≥4 → 배치 드롭 + 하드리셋 | `:422-435` |
| `[LeadingPunctFilter]` | script-agnostic | 직전 방출이 종결부호면 이번 배치 선두 중복 구두점 제거 | `:442-446` |
| `[DashFilter]` | script-agnostic | 순수 대시 토큰(`- – —`) 스킵 | `:453-455` |
| `[HallucinationFilter]` | script-agnostic | `_max_char_run ≥ _CHAR_RUN_THRESHOLD=4` → 토큰 스킵, streak `_HALLUCINATION_RESET_THRESHOLD=5` 시 refresh | `:456-470` |
| `[CrossBatchFilter]` | script-agnostic | 직전 방출 단어와 **완전 동일**하면 드롭 | `:471-473` |

### 2.3 앵커 반복 storm 게이트 (Exp-169 `dc0dc35`) — `_find_anchor_repeat_storm` (`backend.py:128-167`)

`[BatchRepeatFilter]`(한국어 전용)·스크립트불일치(방향 게이트)의 사각지대를 메우는 **script-agnostic** 필러 storm 게이트.
- 상수(`:122-125`): 롤링 창 `40단어`·최소 `4회`·gap 허용 `5단어`·국소집중도 `≥0.6`.
- 최근 40단어에서 2gram→1gram 앵커별 등장위치를 모아, gap-tolerant 클러스터의 최대 크기 `≥4` **그리고** `클러스터/총등장 ≥0.6`(국소집중도)이면 storm. 집중도 조건이 "문서 전반에 흩어져 재등장하는 고유명사(북한)"와 "한 지점에 몰린 필러 storm"을 구분한다.
- `_update_anchor_repeat_window` (`:513-530`): 배치 단어를 잠정 추가해 판정, storm이면 **단어를 커밋하지 않고** `True`(storm 소스가 창을 오염시켜 재발동하지 않게).
- **결정적 설계 — 언어/컨텍스트 상태 무변경**: 드롭 경로(`:691-711`)는 `detected_language=None`·`refresh_segment`를 **의도적으로 호출하지 않는다**. 이 게이트는 같은 언어 발화 중에도 발동할 수 있는데(bong1 en 고정 중), 재감지를 arm하면 `_apply_detected_language`가 `is_switch=False`여도 `init_tokens/init_context`로 컨텍스트를 지워 **자기강화 재환각 루프**(bong1 WER 24.5%→113.3%)를 만든다. 그래서 배치만 드롭하고 컨텍스트는 그대로 둔다(단 `_script_anchor_streak`는 리셋). 이것이 §1.4 스크립트-앵커 게이트(전환 arm)와 이 게이트(드롭 전용)의 비대칭성이다.

### 2.4 표시 레이어 `filter_segments` (`filtering/__init__.py:105-157`, 호출 `audio_processor.py:575`)

- `_CJK_KANA_RE` (**언어 특화**, `:12-20`/`:130`): CJK 한자·히라가나·가타카나 **한 글자라도** 있으면 **세그먼트 통삭제**(`[CJKDrop]`). 한/영 환경이므로 한자·가나는 정의상 오언어 환각. **한글(U+AC00–D7A3)은 클래스 밖**이라 정상 한국어는 미발동. 가장 공격적(임계 없는 통삭제).
- `_ANNOTATION_RE` (`:24-33`/`:127`): `(웃음)`·`[MUSIC]`·`♪` 등 닫힌 주석 + **안 닫힌** 비음성 주석(`(speaking…`, `[LAUGHTER`)까지 제거. 키워드 시작·ASCII 영문까지만 매칭해 **뒤 한글 보존**(과잉제거 방지).
- 유령온점 collapse(`:143-144`): `". ."`·`".."` → `". "`, 선두 홀온점 제거. QG-억제→재디코딩 이음매의 중복 온점 정리.
- 빈/구두점-only 드롭(`:147-149`), 단어 교정 사전(`:151-152`, `WordCorrectionManager` — `admin_replacement.json` + SQLite 동적 갱신, 즉시 반영).

### 2.5 stall 복구 워치독 (`backend.py:713-727`)

배치가 토큰 0개인데 오디오가 `STALL_RECOVER_SEC=10.0s` 이상 진행하면 AlignAtt가 non-fire 고착으로 보고 `refresh_segment(complete=True)` 강제(연속 30s+ 무침묵 발화의 total dropout 방지 — recall 안전장치, QualityGate와 별개).

### 2.6 디코더 파라미터 (운영=`parse_args.py` 기본값)

| 파라미터 | 운영 기본값 | 근거 |
|---|---|---|
| `--beams` | **2** (`:259`) | Exp-080, greedy 대비 WER 개선 |
| `--frame-threshold` | **25** (`:250`, 1프레임=0.02s) | 스트리밍은 버퍼 끝 25프레임(0.5s) 전에 멈춰 미완성 단어 회피(마지막 청크만 4) |
| `--audio-max-len` | **15.0** (`:275`) | Exp-161, 30.0→15.0, sbs1 lag 41s→2s대 + 3파일 WER 개선 |
| `--logprob-threshold` | **-2.0** (`:332`) | Exp-142, QualityGate avg-logprob |
| `--compression-ratio-threshold` | **3.0** (`:340`) | Exp-104, 반복 백스톱 |
| `--periodic-lang-check` | **None(비활성)** (`:376-382`) | Exp-160, 스퓨리어스 전환→환각 |
| `--lang-restrict-koen` | **True** (`:385-390`) | 한/영 고정 |
| `nonspeech_prob` | **0.5** (CLI 없음, `config.py:15`) | AlignAttConfig 기본 |

> ⚠️ **함정**: logprob·CRT·beams·audio_max_len은 argparse↔dataclass 기본값이 **불일치**. QualityGate는 CLI/배포 경로에서만 활성(lp=-2.0/cr=3.0)이고, `WhisperLiveKitConfig()`를 argparse 없이 만들면 `None/None`→**게이트 조용히 비활성**. `nonspeech_prob`은 CLI 오버라이드 자체가 없다.

### 2.7 VAD 튜닝 (Exp-173 `2b900a4`) — `audio_processor.py:117-124`

VAC 생성부 단일 지점(분기는 ONNX↔JIT 폴백일 뿐 파라미터 동일): `FixedVADIterator(threshold=0.3, min_silence_duration_ms=200)`. `min_silence`를 **100→200ms**로 올렸다. 원 목표는 단어 내부 미세정적(~0.1s 숨·조음 휴지)이 발화를 분할해 한 단어가 두 줄로 쪼개지는 것 방지였으나, 실제 이득은 **청크 경계가 길어지며 반복/더듬거림형 환각이 줄어든 것**으로 확인(bong1 worst 46.8→37.2%). 의미론(`silero_vad_iterator.py:231,274-283`): `min_silence_samples=3200`(200ms)이라 sub-200ms 딥은 세그먼트를 닫지 않음 → 조기 refresh·반쪽단어 재디코딩 없음.

### 2.8 WER 트레이드오프 — "verified" 유실 리스크

avg-logprob 게이트는 **가설 전체**를 억제하므로, 음향적으로 어려운 정당 단어(고유명사·잡음 속 영어 기술어 "verified")가 세그먼트 평균 logprob를 -2.0 아래로 끌어내리면 통째로 드롭될 수 있다(recall/삭제오류 비용). 코드 자신이 이를 계측한다(`align_att_base.py:629-632` — 억제 텍스트를 로깅해 "정상 한국어 오폐기율" 측정). 같은 통삭제 리스크: `_CJK_KANA_RE`(정당 한자 고유명사)·`ScriptMismatchFilter`(TTR≤0.6면 정당 ≥6단어 영어 삽입도 클립 가능). 완화책: `is_last` 예외(최종 flush 미게이트), 구두점-only streak 제외, 0.6/TTR/MIN_WORDS 임계 튜닝, storm 게이트 무상태 설계.

---

## 3. 문장 분리 로직

목표는 **한 문장씩 확정·분리**하되 **화자가 바뀌는 순간엔 반드시 화자 분리**(정답 스크립트가 화자전환 기준 줄바꿈). AlignAtt 출력엔 구두점이 없으므로, 경계 신호는 음향·마커에서 찾고 여기에 온점 형태소 분할을 더한다.

### 3.1 확정이 결정되는 두 함수

세그먼트의 `finalized`/`finalize_trigger`는 오직 `tokens_alignment.py`의 두 함수에서 세팅: diar ON = `get_lines_diarization()` (`:379~`), diar OFF = `get_lines()`의 비-diar 루프. (레퍼런스 문서의 `:266`은 stale — 코드 성장으로 현재 `:379`.)

### 3.2 경계 원인 3종 + 온점 형태소 분할

경계를 **만드는** 메커니즘은 **음향·마커 3종(침묵·언어전환·화자전환) + 온점 형태소 분할**이다.

| 원인 | 신호 생성 | 소비(확정) |
|---|---|---|
| **침묵** | `MIN_DURATION_REAL_SILENCE=0.4s` 초과 시 `Silence` 토큰(`audio_processor.py:29,215`) | 세그먼트 닫고 `silence`/`punctuation` 라벨 |
| **언어전환** | `pending_language_switch` arm 시 `LanguageSwitch` 마커(§1.2) | `hard_boundary` 세그먼트 → `language_switch` |
| **화자전환** (diar) | sortformer `SpeakerSegment` | 시간겹침 최대 화자 부여 후 화자 바뀌면 `speaker_change` |
| **온점 형태소** (§3.3) | Whisper 온점 + 형태소 종결 판정 | `punct_boundary` 세그먼트 → `punctuation` |

### 3.3 온점 형태소 판별기 — `sentence_boundary.py` (Exp-170 신설)

Whisper가 찍는 마침표를 문장 분할 신호로 쓰되 **진짜 종결과 거짓 마침표**(한국어 어간·조사 중간 온점, 영어 약어, 소수점)를 형태소로 구분하는 **순수·무상태** 모듈. `?`/`!`는 1차 범위 제외(소수점·약어 위험 없어 현행 (a)/(b) 유지).
- `KO_FINAL_SUFFIXES`(`:11-17`): 니다/십시오/어요/세요/구나/았다… 종결어미. **bare 단음절(군/네/다/까)은 명사·조사 충돌로 제외**(오탐 방어 핵심 — "주한미군"의 "군" 미분할).
- `KO_EXCLUDE_SUFFIXES`(`:20-25`): 니까/는데/으로/다는… 연결어미·조사. **우선 적용해 veto**(동형 종결어미 오탐 차단).
- `EN_ABBREV`(`:27-34`): mr/dr/us/un/etc… ~90개 + 단일 이니셜 + `U.S`형 대문자.
- `is_genuine_sentence_end(closing_text, next_text)`(`:73-97`): ① 종결 온점 직전이 숫자면 서수/소수 → 미분할(전역 가드) ② 마지막 어절 스크립트로 라우팅 — 한글이면 `is_sentence_final_ko`(자족적), 영어면 약어 아니고 **다음 어절이 대문자 시작일 때만** 종결("film. So"=분할, "island. or"=미분할).

### 3.4 정렬 레이어 분할 — `tokens_alignment.py`

- `_punct_split_justified(idx)`(`:245-261`): **갭 기반 (c)분기 제거 후**(Exp-167) 남은 (a)(b)만 — (a) 발화 끝 / (b) 다음이 실제 `Silence` 토큰. 온점+일반토큰은 **갭 크기 무관하게 미분할**(스트리밍 토큰 갭은 실제 음향 침묵과 다르므로 VAD Silence·발화끝만 신뢰).
- `_punct_split_here(idx, start_idx)`(`:263-278`): (a)/(b) 단락 후, 닫히는 텍스트가 `.`/`。`로 끝나면 `is_genuine_sentence_end`로 (c) 판정 추가.
- `compute_punctuations_segments`(`:280-320`): Silence→침묵 세그먼트, boundary→`hard_boundary=True`, 온점 종결→온점 포함해 닫고 `punct_boundary=True`.

### 3.5 diar 병합 생존 — `PuncSegment` (`timed_objects.py:208-211`)

`hard_boundary`·`punct_boundary` 두 내부 전용 플래그(to_dict 미방출). diar 병합 루프(`:401-423`)는 **같은 화자 + non-hard + non-punct일 때만** 재병합 → `punct_boundary=True`가 **같은 화자 턴 안의 온점 분할도 병합에서 생존**시킨다. 라벨 우선순위: `language_switch > silence/punctuation > speaker_change > punct(punctuation) > fallback speaker_change`.

### 3.6 꼬리 재귀속 + finalize 유예 (Exp-167, CASE1)

AlignAtt가 문장 마지막 음절을 유보했다가 Silence 마커 **뒤**에 늦게 방출해 다음 줄 선두로 오분류되는 문제 대응:
- `_insert_with_reattachment`(`:115-139`): 새 토큰 start가 후행 Silence의 **start**보다 앞서면 그 앞에 삽입. `TAIL_REATTACH_EPS=0.05s`(지터)·`TAIL_REATTACH_MAX_LOOKBACK_SECS=1.5s`(먼 침묵 넘어 병합 금지 상한). **boundary는 절대 넘지 않음**.
- `_apply_finalize_grace`(`:459-476`): 마지막이 침묵·직전이 텍스트면 `FINALIZE_GRACE_SECS=2.0s` 유예창 안에서 `finalized=False`·trigger=None으로 유보(늦은 꼬리 도착 대기). 발화 재개하면 스킵.
- 유령온점 collapse(`filtering/__init__.py:140-149`): 재귀속 이음매 중복 온점 정리 + 구두점-only 세그먼트 드롭.

### 3.7 `finalize_trigger` 계측 (라벨 4종)

`Segment.finalize_trigger`는 `to_dict`가 항상 방출(`None` 포함). 값은 정확히 4종: `language_switch`·`speaker_change`·`punctuation`·`silence`(진행 중 마지막 줄·유예창은 `null`). UI 배지(`web/live_transcription.js:69` `TRIGGER_LABELS` = 침묵/종결/언어전환/화자전환) + 전사 기록(`scripts/eval.py`)이 한 세트로 동기화된다(SENTENCE_FINALIZATION_LOGIC.md §7 갱신 규약).

> **참고 — 알려진 잔존 증상(문장 중간 분리)**: 같은 화자·같은 언어 발화 도중 짧은 pause만으로 문장이 중간에서 잘리는 사례(ytn2 "operational.  control", "이와 관련.  해서")가 관측된다. 원인은 §3.2 침묵 경계가 **문법적 완결 여부와 무관하게** 무조건 세그먼트를 닫고(§3.1 Silence 소비), §3.3 온점 판별기가 **Silence 경로엔 연결되지 않은** 데 있다(온점 형태소 판별은 온점이 있을 때만·§3.4). `MIN_DURATION_REAL_SILENCE=0.4s` 문턱 부근 VAD 민감도(Exp-167 잔존 갈래)도 관여. 별도 조사·설계 대상(WER·코드스위칭 무회귀 제약).

---

## 4. `process_iter` 파이프라인 순서 (전체 통합) — `backend.py:618-780`

게이트 순서는 load-bearing이다:

1. **짧은 침묵 언어 체크**(`:625-627`) — 짧은 pause 후 재감지
2. **`infer()`**(`:629`) — 디코딩 → `timestamped_words`
3. **ForeignLang 필터**(`:631-654`) — `(speaking in foreign language` 방출 시 재감지 arm + 토큰 제거
4. **스크립트 불일치 필러 게이트**(`:656-675`, §1.5) — 발동 시 재감지 arm + 앵커 streak 리셋 + 배치 드롭
5. **스크립트-앵커 재감지 게이트**(`:677-682`, §1.4) — 확신 전환 시 `_apply_detected_language` + 배치 드롭; 불확신이면 통과
6. **앵커 반복 storm 게이트**(`:684-711`, §2.3) — storm 시 배치 드롭만(재감지 arm 안 함), 앵커 streak 리셋
7. **stall 복구 워치독**(`:713-727`, §2.5)
8. **pending-language 가드**(`:729-731`) — 최초 토큰인데 `detected_language=None`이면 버퍼링
9. **cross-batch 반복 필터**(`:733`, §2.2)
10. **LanguageSwitch 마커 삽입**(`:735-764`, §1.2) — arm 시 마커 prepend + `pending_*` 클리어
11. **방출 기록**(`:766-777`)

철회(`_retract_stale_language_tokens`, §1.2)는 `process_iter` 밖 — 방출된 마커가 `TokensAlignment._insert_with_reattachment`로 편입될 때 발동.

---

## 5. 파라미터 표 (SoT = 코드)

| 파라미터 | 값 | 위치 | 역할 |
|---|---|---|---|
| `MIN_DURATION_REAL_SILENCE`(audio) | 0.4s | `audio_processor.py:29` | UI 침묵 경계 |
| `MIN_DURATION_REAL_SILENCE`(backend) | 2s | `backend.py:36` | 디코더 long-silence 리셋(경계 아님) |
| VAC threshold / min_silence | 0.3 / 200ms | `audio_processor.py:122` | Silero VAD 민감도·최소침묵(Exp-173) |
| `LANG_SWITCH_KEEP_SECS` | 2.5s | `align_att_base.py:14` | 전환 시 유지 오디오 |
| `MIN_DURATION_SHORT_LANG_RESET` | 0.5s | `backend.py:37` | 짧은 침묵 언어 리셋 |
| `RETRACT_EPS` (잠정) | 0.05s | `tokens_alignment.py` | 철회 구역 지터 여유 |
| 철회 하한 | `retract_floor` 우선, 폴백 `boundary_t−KEEP−1.0` | `tokens_alignment.py:160` | 서두유실 방지(Exp-174) |
| `_SCRIPT_ANCHOR_N_WORDS`/`_T_SECS` (잠정) | 3단어 / 1.0s | `backend.py:185-186` | 스크립트-앵커 재감지 문턱(Exp-172 실측) |
| 스크립트-앵커 재감지 창 | 2.0s·p≥0.90 | `backend.py:187-188` | 재감지 프로브 |
| `_SCRIPT_MISMATCH_MIN_WORDS`/`_TTR` | 6단어 / 0.6 | `backend.py:64-66` | 필러 게이트 |
| 앵커 storm 창/최소/gap/집중도 | 40/4/5/0.6 | `backend.py:122-125` | storm 게이트 |
| `FINALIZE_GRACE_SECS` | 2.0s | `tokens_alignment.py` | 확정 유예 |
| `TAIL_REATTACH_EPS`/`MAX_LOOKBACK` | 0.05s / 1.5s | `tokens_alignment.py` | 꼬리 재귀속 |
| `STALL_RECOVER_SEC` | 10.0s | `backend.py:42` | stall 복구 |
| beams/frame_threshold/audio_max_len | 2 / 25 / 15.0 | `parse_args.py:259,250,275` | 디코더 |
| logprob/CRT/PLC | −2.0 / 3.0 / None | `parse_args.py:332,340,376` | 품질 게이트·주기재감지 |
| `KO_FINAL/EXCLUDE_SUFFIXES`·`EN_ABBREV` | (목록) | `sentence_boundary.py:11,20,27` | 온점 형태소 분할 |

---

## 6. 알려진 한계 / 후속 백로그 (Exp-175 탐사 산출물)

상세: [BACKLOG_CODESWITCH_FOLLOWUP.md](../backlog/BACKLOG_CODESWITCH_FOLLOWUP.md). 우선순위 순:
1. **미방출형 전환 서두 유실(최우선)**: 구언어 잠금 중 디코더가 서두를 **아예 방출 안 함**(비-fire) → 반전 streak 자체가 없어 §1.4로 원리상 포착 불가(ytn2 "There is more work"·sbs1 "From a satellite image" 실측). 제안: 재디코딩 창 하한을 마지막 방출 토큰 끝으로 당기거나 경량 비-fire 워치독.
2. **①′ locked-lang 음차 환각**: 반대 언어를 잠긴 언어 음차로 환각(bong1 "말랑말랑"→"mallang mallang") — 출력 스크립트 반전이 없어 §1.4 스코프 밖. 제안: 저신뢰+lang-id 확률 경합 보조 트리거(단 Exp-160 스퓨리어스 리스크 주의).
3. **세션초입 buffer 유실**: 언어 미확정(감지 문턱 2.0s 대기) 동안 서두 유실(sbs1 3/3).
4. **bong1 필러/웃음 환각**: AnchorRepeatFilter 가변 변주구 사각지대(Exp-169) + 웃음 전용 비-ASR 분류기(Exp-165) 별도 루프.
5. **문장 중복 재방출(dup)**: 재디코딩 창 겹침 시 문장 단위 중복 — 철회 규칙을 전환 경계 밖 재디코딩 일반으로 확장 검토.
6. **문장 중간 분리(§3.7 참고)**: 같은 화자·언어 발화 도중 짧은 pause로 문장 중간 절단 — 침묵 경계가 문법 완결과 무관하게 닫는 정책 + 온점 판별기 미연결이 원인. 별도 조사 진행 중.

---

## 7. 참고

- 개념 레퍼런스: [SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md)(문장 확정·§7 갱신 규약) · [MASTER_CHANGES.md](../MASTER_CHANGES.md)(upstream 대비 변경) · 시행착오 [../../EXPERIMENTS_LOG.md](../../EXPERIMENTS_LOG.md)(Exp-167~175).
- **라인번호 정정**: `SENTENCE_FINALIZATION_LOGIC.md`의 일부 `file:line`은 코드 성장으로 뒤처짐(예: `get_lines_diarization` 문서 :266 → 실측 :379, `_punct_split_here` 문서 :169 → :263). 본 보고서 수치는 세 Explore 에이전트의 master 워킹트리 실측값.
- 핵심 파일: `simul_whisper/{backend,align_att_base,decoder_state,simul_whisper}.py` · `tokens_alignment.py` · `sentence_boundary.py` · `timed_objects.py` · `filtering/__init__.py` · `audio_processor.py` · `parse_args.py` · `config.py`.
