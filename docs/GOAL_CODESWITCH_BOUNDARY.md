# Goal Prompt — 코드스위칭 경계 3증상 수정 루프 (Stage 0 계측부터)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> Exp-171(언어전환 경계 철회 + 화자전환 서두유실 수정, master `a14d028`) 채택 이후에도 실사용 테스트에서
> 잔존하는 세 증상을 다루는 루프다. **①·②는 근본원인이 코드 레벨에서 이미 확정**됐고(아래 §1),
> ③은 계측으로 범인 경로를 특정해야 한다.
>
> ⚠️ **진행 규율 — 이 루프는 자율 루프가 아니다**: 사용자 결정에 따라 **각 Stage 종료 = 사용자
> 보고·상의 체크포인트**다. Stage 완료 시 결과를 보고하고 **정지**한다. 다음 Stage 착수는 사용자
> 상의 후에만 진행한다(기존 GOAL 문서들의 자율 진행 규율을 이 문서에서는 의도적으로 오버라이드).
> Stage 내부의 구현→측정→분석은 CLAUDE.md §4 자율 루프대로 진행해도 된다.

---

## 0. 현재 상태 / baseline (2026-07-08, Exp-171 채택 후)

- **master = Epoch 5 (E5, turbo 기질)**. 최근 채택: Exp-167(문장꼬리분리) → Exp-168(CASE2 서두유실:
  스크립트 불일치 게이트+since_offset) → Exp-170(온점 형태소 분할) → Exp-171(경계 철회+keep_secs).
- **게이트(max)**: [EXPERIMENTS.md](../EXPERIMENTS.md) STATE 상단 확정 게이트를 따른다
  (작성 시점: bong1≤30.5% / ytn2≤34.5% / sbs1≤16.1%, Exp-161 N=3 기준 — STATE가 갱신되면 STATE 우선).
  Exp-171 채택 확정치(참고): bong1 28.1/max43.5(R2 이상치) · ytn2 18.7/max18.7 · sbs1 13.1/max15.5.
- **잔존 증상 (사용자 실사용 보고, 2026-07-08)**:
  1. **① 코드스위칭 전면부(서두) 유실** — 언어가 바뀌는 순간 새 언어 발화의 서두가 오번역·유실.
  2. **② 한↔영이 문장 경계 없이 붙음** — 한국어 뒤 영어(또는 반대)가 같은 line으로 이어져 출력.
  3. **③ 문장 중간부 단어 유실** — 문장 중간의 정상 단어가 전사에서 누락.

---

## 1. 근본원인 (이미 규명 완료 — 재조사 불필요)

### ①·② = 같은 뿌리 (코드 확정, 가설 아님)

- `LanguageSwitch` 마커(문장경계)는 `_apply_detected_language`의
  `is_switch = prev_lang is not None and prev_lang != lang`일 때만 arm된다
  ([align_att_base.py](../whisperlivekit/simul_whisper/align_att_base.py) `:207, :218-224`).
- 이를 호출하는 상시 경로 `_detect_language_if_needed`는 **`detected_language is None`일 때만 동작**
  (`align_att_base.py:229-233`). 즉 **최초 언어 확정 후에는 상시 재감지가 없다.**
- 중간 재감지 트리거는 4종뿐: 짧은침묵(≥0.5s, `backend.py:262-281`) · 긴침묵(≥2.0s, `backend.py:242-259`)
  · 화자전환 eager(`new_speaker`, diar) · PLC(**기본 None 비활성** — Exp-160에서 ytn2 방송환각으로 껐음).
- → **무음·화자전환 없는 연속 코드스위칭**("…입니다 This is…"처럼 같은 화자가 붙여 발화)에서는 넷 다
  미발동 → `detected_language` 첫 언어 고착 → 마커 미생성 → **경계 없이 같은 line에 쌓임(②)**
  (`tokens_alignment.py:520-536`) + 구언어 잠금 동안 새 언어 서두가 오디코드/유실(**①**).
- 경계 소비(하류: diar/비-diar 마커→줄닫기)는 정상. **결손은 마커 생성(arm) 한 곳뿐.**
- 부수: `Segment.detected_language`가 첫 토큰 언어만 취함(`timed_objects.py:181`) — 마커가 줄을 언어별로
  쪼개면 대체로 해소되는 종속 증상.

### ③ = 다수 드롭 경로 후보 (계측으로 범인 특정 필요)

우선순위 후보 (전부 [backend.py](../whisperlivekit/simul_whisper/backend.py) /
[align_att_base.py](../whisperlivekit/simul_whisper/align_att_base.py)):
1. **CrossBatchFilter 정확일치 드롭** `backend.py:441-443` — 자연발화 정당 연속중복("네 네")을 무조건 제거.
2. **AnchorRepeatFilter storm 배치 통째 드롭** `backend.py:560-583`, `:127-166`.
3. **`_split_tokens` held 단어 + refresh/버퍼트림 소실** — `align_att_base.py:489`(마지막 단어 유보),
   `refresh_segment`가 held/pending 폐기(`:132, :155`), `insert_audio` 롤링버퍼 슬라이딩
   (`simul_whisper.py:162-180`).
4. **loop-detection / rewind가 infer 산출 폐기** `align_att_base.py:358-364, 410-425`.
5. **retraction boundary_t 오차** — `_retract_stale_language_tokens` 구역1 무조건 철회가 정당 토큰 pop
   (`tokens_alignment.py:172-173`).
6. QualityGate(`align_att_base.py:452-454`)는 기본 None(비활성)일 가능성 — 로그 유무로 우선 배제.

**의존관계**: ③은 ①② 수정에 종속 — Stage 1의 재감지가 트림·retraction churn을 바꾸므로 ③ 거동이
변한다. **한 번에 수정 금지, 반드시 Stage 1 채택 후 재계측 위에서 ③을 다룬다.**

### 회귀 교훈 (반드시 준수)

- **Exp-160**: PLC(주기 확률 재감지)를 켜면 lang_id 확률 진동이 스퓨리어스 전환 → 트림+재디코딩 →
  ytn2 방송클로징 환각. **순수 확률 기반 주기 체크 재도입 금지** — 실제 출력 스크립트 근거 트리거만.
- **Exp-163**: 드롭 시 `refresh_segment` 호출은 재환각+정렬 교란. **새 게이트에서 refresh 금지.**
- **Exp-169**: 드롭 후 언어 재감지 arm이 같은 언어 재확정 시에도 컨텍스트를 지워 자기강화 루프
  (bong1 113% catastrophic). **`_apply_detected_language`는 실제 다른 언어 확신 시에만 호출.**
- **Exp-166**: `LANG_SWITCH_KEEP_SECS` 스윕만으로는 서두 유실 미완화(문제를 이동시킬 뿐).

---

## 2. 공통 측정 규약

- 경로 C(VBCable)만, diar-ON(Sortformer + `--compression-ratio-threshold 3.0`), turbo, beam=2, PLC=None.
- **테스트셋 = bong1 + ytn2 + sbs1** (새 음성 파일 미도입 — 사용자 결정. ytn2가 무휴지 코드스위칭 대표).
- 스크리닝 `--repeat 1`(방향 신호) → 채택확정 `--repeat 3`(max 1순위, fail-fast 금지) →
  held-out(ytn1+eng1) 단회. 매 측정 provenance 첫 줄(`vbcable=ok`) 육안 확인.
- 측정 명령은 [.claude/commands/eval.md](../.claude/commands/eval.md) 기본 사용법 + **`--trace-tokens`**
  (서버에 전달됨, `eval.py:435-439,530-531` — 서버 로그에 TokenTrace/RetractScan 등 진단 태그 기록).
- 워크트리 규약: 코드 수정 Stage는 새 워크트리 + 메인 `.venv` Junction 공유(`mklink /J .venv ..\..\.venv`),
  **`uv run`/`uv sync` 금지**, 측정·import는 cwd=워크트리. Stage 0(코드 무변경)은 main cwd 측정 가능.
- 하니스 버그(VBCable 무음/사망, 포트 충돌)는 즉시 중단·수리
  ([vbcable-loopback-instability] — `verify_loopback` 진단, 재부팅/Audiosrv 재시작 복구).

---

## 3. 단계 정의

### Stage 0 — 재현·계측 (코드 변경 없음) 【최우선·이번 착수】

**성격**: 계측 전용, master 그대로. 브랜치·워크트리 불필요.

**실행**:
1. VBCable 상태 확인 → `--trace-tokens` + `--repeat 1`로 테스트셋 3파일 측정, 서버 로그
   (`.omc/server_logs/`)와 전사(`.omc/transcripts/`) 확보.
2. **①② 후보 구간 포착**: `detected_language` 고착 중 반대 스크립트 토큰이 연속 방출됐는데
   `[LangSwitch]` arm 로그가 없는 배치 구간을 정답 전사와 대조해 목록화. 각 구간의
   **단어수·지속시간 분포**를 산출 — Stage 1 임계값(N단어/T초)의 실측 근거.
3. **③ 범인 귀속**: `[TokenTrace] infer→`(`backend.py:516`) 대비 `emit→`(`:637`) diff로 배치별
   순유실 단어를 산출하고, 같은 타임스탬프 창의 드롭 태그와 조인해 경로별 귀속:
   `[CrossBatchFilter]` `[AnchorRepeatFilter]` `[ScriptMismatchFilter]` `[BatchRepeatFilter]`
   `[HallucinationFilter]` `[Retract]/[RetractScan]` `[UTF-8 Fix] Dropping` `[Loop Detection]`
   `[QualityGate]`. 정답 정렬로 유실 단어가 **정당 콘텐츠 vs 필러/환각**인지 라벨링 —
   **경로별 집계**로 본다(특정 문구 암기 금지, §3.8).

**산출물**: (a) ①② 후보 구간 목록(파일·시각·구간 단어수·지속시간), (b) ③ 경로별 유실 기여도 표,
(c) 정당 콘텐츠 유실의 최다 기여 경로 지목(또는 "특정 불가" 판정).

**완료 기준**: 3파일 각각 유실→경로 귀속 표 존재 + ①② 후보 구간 ≥1건 실측 포착(ytn2에서 못 잡으면
그 사실 자체 + 재현 조건 재검토를 보고). **③ 범인이 특정 안 되면 Stage 2는 착수하지 않는다.**

**→ 사용자 보고 후 정지.** Stage 1 착수 여부와 N·T 임계값을 상의해 결정.

### Stage 1 — ①② 수정: 스크립트-앵커 재감지 【Stage 0 상의 후 착수】

**브랜치**: `exp/script-anchor-redetect` (새 워크트리) · **성격**: 신규 게이트 1개(기존 경로 무변경)

**설계** (세부는 Stage 0 실측으로 보정):
- **트리거**: 실제 방출 토큰 스크립트가 잠긴 `detected_language`와 **연속 N단어 또는 T초** 반전 유지 시.
  판정은 `_is_opposite_script`(`tokens_alignment.py:61-72`, TTR 게이트 없는 순수 스크립트) 재사용 —
  기존 `_is_script_mismatch_filler`(TTR≤0.6 반복 전제)가 정상 전환을 통과시키던 사각지대를 메움.
  같은 스크립트 배치가 섞이면 streak 리셋(1~2단어 정상 삽입 "I think 그건" 오탐 방어).
- **동작**: 트리거 시 `detect_current_language(window_secs=2.0, min_prob=0.90)` 재감지 →
  **다른 언어 확신 시에만** `_apply_detected_language(new_lang)`(2.5s 트림+마커 arm+retract arm 기존
  메커니즘 재사용) + 해당 배치 `timestamped_words=[]` 드롭(마커가 다음 신언어 배치 앞으로 정확히 이연;
  `backend.py:608-609` 가드 활용). 드롭한 서두는 트림이 남긴 경계 오디오 재디코딩으로 복구(①),
  구언어 오스탬프 잔존은 retraction 구역2가 정리(②). **`refresh_segment` 호출 금지(Exp-163),
  같은 언어 재확정 시 아무것도 안 함(Exp-169).**
- **삽입점**: `backend.py` `process_iter` ScriptMismatch 블록 직후(`:558` 뒤)·AnchorRepeat(`:560`) 앞 —
  `decoded_text`/`seg_lang` 재계산 불필요. 신규 상태 `self._script_anchor_streak`은 `__init__` 초기화 +
  silence 리셋 블록·`new_speaker`·기존 게이트 arm 직후에 리셋 합류.
- **Exp-160 면역 논거**: 이 트리거는 lang_id **확률**이 아니라 **출력 스크립트의 지속 반전**에만 반응.
  ytn2 스퓨리어스 전환 당시 출력은 계속 한글이었으므로 streak이 쌓이지 않아 미발동.
- ko↔en 대칭, 특정 문구·데이터 특화 하드코딩 없음(§3.8).

**유닛테스트**: 신규 `tests/test_script_anchor_redetect.py`(`test_lang_redetect.py` MagicMock 관례) —
N-1 미발동/N 발동, 중간 같은스크립트 삽입 리셋, `detect_current_language`=None 시 미적용,
트리거 시 배치 드롭+`pending_language_switch` set, en↔ko 대칭, silence/new_speaker 후 streak 리셋.

**채택 게이트 (hard)**: ① ytn2 방송클로징 환각·bong1 필러 storm 재발 0건 ② Stage 0 후보 구간에서
`[LangSwitch]` 마커 방출·경계 분할 실제 발생(정성) ③ 테스트셋 WER max 미회귀 ④ held-out 미회귀.
F1 변동은 §3.3 지표한계 감안(WER 우선). **①②는 §3.2 불변 제약 직결 — 게이트 애매 시 자율 기각 금지,
결과·대안 보고 후 사용자 질의**(CLAUDE.md §4).

**롤백**: 신규 게이트 조기 return 플래그 1개로 무력화 가능(기존 경로 무변경) — 격리 용이.

**→ 측정·정성 결과 사용자 보고 후 정지.** 채택(머지) 여부 상의.

### Stage 2 — ③ 계측기반 수정 【Stage 1 채택 + 재계측 후, 상의 후 착수】

**브랜치**: 범인 경로별 독립 브랜치·독립 커밋·플래그 격리.

- Stage 1 적용 상태에서 **재계측**(Stage 0 방법 재사용) — 재감지 churn이 ③을 바꿨는지 먼저 확인.
  `[RetractScan] removed`가 유의 증가했으면 retraction 하한/`RETRACT_EPS` 보수화를 수정에 포함.
- Stage 0/재계측이 특정한 **최다 기여 경로만** 최소수정. 후보별 방향:
  - CrossBatchFilter → `word == prev` 무조건 드롭에 **시간갭 조건** 추가(`_last_emit_end` 대비 갭이
    크면 별개 발화로 보존) 또는 연속 드롭 횟수 상한.
  - AnchorRepeatFilter → storm 앵커만 제거하고 나머지 보존하는 부분 드롭(언어 재감지 arm 금지 유지).
  - held 단어/UTF-8/loop·rewind → 로그로 "held 후 미재방출 vs 완전 폐기" 구분 후 개별 대응.
- 채택 게이트·보고는 Stage 1과 동일 프로토콜.

---

## 4. 보고 시점 (사용자 입력 대기 지점)

1. **Stage 0 완료** — 후보 구간·귀속 표 보고, Stage 1 착수·N/T 상의. (필수 정지)
2. **Stage 1 측정 완료** — 정량+정성 보고, 채택/머지 상의. (필수 정지)
3. **Stage 2 착수 전 재계측 결과** — ③ 범인 확정 보고, 수정 방향 상의. (필수 정지)
4. 그 외 catastrophic 회귀·하니스 버그·설계 전제 붕괴 시 즉시 보고.

## 5. 기록·연동 문서 (채택 시 동일 작업 단위)

- 각 Stage 종료 시 `/log-experiment` — EXPERIMENTS_LOG 전체 서술 + EXPERIMENTS.md 빠른참조 1행
  (Exp-160/163/169 회귀 교훈 대비 결과 포함).
- Stage 1 채택 시: [docs/SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) §3.2
  (`_apply_detected_language` 진입점 4종→5종에 "스크립트-앵커 재감지" 추가)·§5(N·T·streak 상수 행 추가).
- Stage 2 채택 시: 같은 문서 §4 표(해당 필터 행 갱신).
- master 머지 후 `/update-master-changes`. epoch 판단은 Exp-168/171 전례(경계 서브시스템 수정 = E5 유지)
  를 따르되 STATE 세대경계 규칙으로 최종 판단.
