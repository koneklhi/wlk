# Goal Prompt — 코드스위칭 구조 개선 5단계 자율 루프

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> Claude는 이 지시를 받으면 아래 **5단계를 순서대로** 구현·측정·채택/기각하며 자율 진행한다.
> 사용자 추가 입력 없이 진행하되, **단계 5 착수 직전 / 목표 달성 / 단계 소진 / §7의 보고 조건**에서만 보고한다.
> 상위 목표·측정 인프라·탐색 공간 백업은 [GOAL_WER15.md](GOAL_WER15.md)와 공유한다. **두 파일이 함께 주어지면 이 파일의 5단계가 우선한다.**

> ⚠️ **진행 상황 갱신 (2026-07-05)**: **단계 1~4는 완료/머지됨**(E2→E4). **단계 5는 진행 중** — 프로브 2a(RTF 0.128<0.5) 통과, 2b/2c 준비 중 `model_dir` 배선 버그 발견 → [GOAL_TURBO_MODEL_FIX.md](GOAL_TURBO_MODEL_FIX.md)에서 turbo 정상화 완료(Exp-158, ✅완료). **본문의 baseline(E2, base 기질)은 전부 무효** — 현재는 turbo 기질(E5), [EXPERIMENTS.md](../EXPERIMENTS.md) 참조. 2b/2c 재개는 held-out 측정 이후 별도 후속.

---

## 0. 배경 — 왜 이 5단계인가 (2026-07-02 병목 분석 결론)

E2까지의 파라미터 탐색(beam/CRT/logprob/PLC/nonspeech_prob — Exp-131~149)은 소진됐다.
코드 수준 분석으로 확인된 구조적 병목은 다음 4가지이며, 5단계는 이를 직접 공략한다.

1. **단일 언어 하드 조건화**: 디코딩 프롬프트가 `<|ko|>`/`<|en|>` 단일 토큰을 포함하고
   `all_language_tokens`가 매 스텝 suppress됨(`simul_whisper.py` `_init_state`) → 모델 스스로 전환 표현 불가.
   전환은 외부 감지 3경로(화자전환 / 침묵 / PLC)에 전적으로 의존.
2. **전환 액션의 세금 = 재디코딩 중복**: `_apply_detected_language`(`align_att_base.py`)가
   `init_tokens()`로 디코딩 상태를 지우면서 **오디오 버퍼(`state.segments`)는 유지** → 다음 `infer()`가
   버퍼 전체를 새 언어로 재디코딩 → **이미 방출된 단어가 구(phrase) 단위로 재방출**된다.
   `_filter_cross_batch_repetitions`는 직전 1단어 중복만 차단. **PLC 계열 전패(Exp-131/143/145)의
   실제 메커니즘은 "감지가 나쁨"이 아니라 "전환 세금"으로 추정** — 이 세금을 없애기 전엔 어떤 감지 개선도 공정 평가 불가.
3. **비음성 → 감지 오염 (bong1 worst-case 근본 원인, Exp-138 규명)**: 웃음·박수가 Silero VAD(0.3)를
   통과해 lang_id 감지 창을 오염 → 언어 오감지 → 환각 캐스케이드. E2(lang_restrict_koen)는 CJK만 막았고
   환각은 라틴/한글로 형태만 변경(Exp-139). `_check_no_speech`는 버퍼 전체 기준이라 혼재 시 희석·무력.
4. **배선 버그(신규 발견)**: `backend.py` `_check_short_silence_language`가 `create_tokenizer`+`init_context`만
   호출하고 **`init_tokens()`를 호출하지 않음** → `state.tokens[0]`의 SOT 언어 토큰이 옛 언어로 잔존 →
   **짧은 침묵 언어 전환이 감지만 되고 디코딩에 미적용**. Exp-143(PLC 배선 버그)과 동형의 2번째 배선 버그.

부수 결함(단계 1에서 함께 정리): `align_att_base.py`에 `detect_current_language`가 **2회 정의**되어
앞 정의(153행 부근)가 dead code. / Layer 1 주석 필터가 닫는 `]` 없는 `[LAUGHTER` 패턴 미차단(Exp-139 식별, 단계 2 범위).

---

## 1. 목표와 baseline

- **최종 목표**: 테스트 3파일(bong1+ytn2+sbs1) 경로 C **평균 WER < 15%** (GOAL_WER15와 동일).
- **이 루프의 목표**: 5단계를 순서대로 처리(채택 또는 근거 있는 기각)하고 각 단계에서 baseline을 갱신.

**현재 baseline (E2 master, Exp-142 채택 후 — 2026-07-01, ⚠️base 기질·무효 — turbo baseline은 EXPERIMENTS.md 참조)**:

| 파일 | WER median | WER max | 특성 |
|------|-----------|---------|------|
| bong1 | **37.5%** | 48.0% | 영어2+한국어2 다화자, 웃음/박수 비음성 구간 |
| ytn2  | **31.5%** | 36.0% | 한↔영 짧은 텀 코드스위칭 (순차통역) |
| sbs1  | **19.6%** | 22.6% | 한국어 중심, 중간 영어 인용 |
| **평균** | **29.5%** | — | 목표까지 -14.5pp |

단계 채택·머지 시 그 단계의 N=3 median/max가 **새 baseline**이 된다 (STATE 갱신 포함).

---

## 2. 진행 규율 (불변 — CLAUDE.md §3~4 준수)

- **세션 시작 즉시**: ① `EXPERIMENTS.md`(STATE)만 읽기 ② `git worktree list`로 미완료 워크트리 확인
  ③ 진행 중 단계가 있으면 그 지점부터 재개, 없으면 단계 1부터.
- **워크트리 필수**: main 브랜치 코드 편집 금지. 단계별 브랜치/워크트리(§3의 제안 명칭) + `.venv` Junction 공유
  (`cmd /c mklink /J .venv ..\..\.venv`), 측정은 반드시 **워크트리 cwd**에서 (import 경로 함정).
- **측정 2계층**: N=1 스크리닝(방향 신호) → 유망하면 N=3 확정. catastrophic(+20pp)이면 즉시 기각.
  provenance 첫 줄(`vbcable=ok` 포함) 육안 확인. diar-ON + CRT=3.0 + logprob=-2.0(기본값) 고정.
- **채택 우선순위**: ① max WER 미회귀 (bong1 ≤ 48.0 / ytn2 ≤ 36.0 / sbs1 ≤ 22.6, baseline 갱신 시 그 값)
  ② median 개선. **WER > F1** (F1 catastrophic ≈0% 반복 폭주만 원인 파악 후 결정).
- **held-out**: 채택 후보에 한해 ytn1+eng1 단회.
- **기록**: 단계마다 `/log-experiment`로 **Exp-150부터 순번** 부여 (한 단계가 여러 Exp 소비 가능).
- **epoch 게이트**: 단계 1·2는 실패 모드를 바꾸는 **구조 변경** — master 머지 시 STATE의 epoch 마커 +1
  (E2→E3→…) 및 이전 세대 파라미터 결론에 `[E?·재검증]` 부여. 단계 3~4는 규모에 따라 판단.
- **연동 문서**: 코드 변경과 동일 작업 단위로 CLAUDE.md §4 표의 문서 갱신
  (특히 구조 변경 머지 시 `docs/MASTER_CHANGES.md` — `/update-master-changes`).
- **§3.2 예외**: 언어 불변식 직결 기능이 정량 게이트 탈락 시 자율 기각 금지 — 사용자 질의.

---

## 3. 5단계 정의

### 단계 1 — 언어 전환 프로토콜 재설계 + SOT 배선 버그 수정 (제안 C+A, ytn2 축)

**브랜치 제안**: `exp/lang-switch-protocol`

**구현 스펙** (순서대로):

1. **부수 정리 (측정 불필요, 동작 불변)**: `align_att_base.py`의 중복 `detect_current_language` 중
   **앞 정의(153행 부근, min_prob=0.85 기본값 버전) 삭제** — 뒤 정의(225행 부근)가 실효 정의.
2. **전환 프로토콜 (A)**: `_apply_detected_language(lang)`를 다음 순서로 재작성 —
   - **오디오 절단**: `state.segments`에서 **최근 (감지창 window_secs + 완충 0.5s)초만 유지**하고 이전 샘플 제거.
     제거량만큼 `state.cumulative_time_offset += removed_len` 보정
     (`insert_audio`의 audio_max_len 트리밍 로직과 동일 방식 — `simul_whisper.py` 162~180행 참고).
     절단으로 **재디코딩 대상 = 전환 경계 오디오만** → 방출 완료분 재방출 원천 차단.
   - `create_tokenizer(lang)` → `init_tokens()` → `init_context()` (기존 유지), `last_attend_frame` 리셋 유지.
   - **LanguageSwitch 경계 이벤트**: `timed_objects.py`에 마커 타입 신설(예: `LanguageSwitch(Timed)`,
     `is_boundary()` 프로토콜). `backend.process_iter` 반환 토큰 스트림에 마커 삽입 →
     `audio_processor.transcription_processor` 통과 → `tokens_alignment.compute_punctuations_segments`에서
     **Silence와 동급의 문장 경계**로 처리. 하류 소비처 3곳 점검: tokens_alignment 분기 /
     translation_queue에는 미전달(skip) / FrontData 직렬화 제외(내부 신호 — SCHEMA_CHANGES 변경 없음 확인).
3. **배선 버그 수정 (C)**: `backend.py` `_check_short_silence_language`의
   `create_tokenizer + init_context + detected_language 대입`을 **위 재작성된 `_apply_detected_language` 호출로 교체**
   (절단 프로토콜 덕에 경량 리셋 의도를 유지하면서 SOT 언어 토큰이 실제 갱신됨).
4. **이중 리셋 조율**: `new_speaker` 경로(diar)와 언어 전환 경로가 연달아 발동할 때 중복 리셋 방지
   (예: `refresh_segment` 직후 N초 내 언어 전환은 절단 생략 — 이미 버퍼가 짧음).

**검증**:
- 단위 테스트: 전환 후 `state.tokens[0]`에 새 언어 토큰 존재 / 절단 후 `segments_len()` ≤ window+0.5s /
  마커가 tokens_alignment 경계로 소비되는지.
- **중복 방출 계측 로그**: 전환 직후 첫 배치와 직전 방출 단어들(마지막 5개)의 겹침 카운트를 WARNING 로그로 —
  before/after 비교 근거.
- 경로 C: N=1 → N=3. **F1 개선(언어 경계 신호 추가)과 ytn2 WER이 1차 관찰 대상.**

**채택 시 후속 (같은 단계 내 별도 Exp)**: **PLC 재평가** — 전환 세금 제거 후 PLC=2.0 / 4.0을
N=1 스크리닝 → 유망 시 N=3. 중복이 사라졌는데도 악화면 "감지 자체의 문제"로 확정하고 PLC 영구 종료.
**기각 시**: C(배선 수정)만 분리해 최소 중복 가드(전환 직후 첫 배치에 방출 단어 suffix 매칭 드롭)와 함께 재측정.
그래도 기각이면 원인 기록 후 단계 2로.

---

### 단계 2 — 감지 입력 정화: VAD-게이트 언어 감지 (제안 B, bong1 worst-case 축)

**브랜치 제안**: `exp/vad-gated-langid`

**사전 프로브 (구현 전, 저비용)**: 임시 로깅 패치로 경로 C 1회 실행 —
`detect_current_language` / `_detect_language_if_needed` 호출마다 (감지창 시각, top 언어, 확률)을 로그.
bong1 웃음 구간(전사 대조로 특정)에서 **오감지율**을 계측해 기준선 확보. 전사 무관 계측이라 빠름.

**구현 스펙**:

- **B-1 (핵심): lang_id 입력 마스킹** — `detect_current_language`에서 최근 창(1.5~2.0s) 오디오에
  Silero VAD를 512샘플(32ms) 단위로 적용해 speech 마스크 생성 → **speech 프레임만 이어붙인 오디오**로
  `lang_id` 수행. **speech 총량 < 0.3s면 감지 보류(None 반환 = 언어 유지)** — 비음성뿐인 창에서
  언어를 아예 판정하지 않는 것이 캐스케이드 차단의 핵심.
  - VAD 인스턴스: `TranscriptionEngine`의 `vac_session`(ONNX, CPU)을 `SimulStreamingOnlineProcessor`에
    주입해 `OnnxWrapper` **신규 인스턴스**(상태 분리) 생성. 세션 공유·상태 비공유.
- **B-2 (옵션 arm, 별도 Exp)**: 최근 1.0s VAD speech 비율 < 임계 시 해당 `infer()` 방출 억제.
  ⚠️ Exp-149 교훈(발화/비음성 분포 겹침) — Silero가 웃음을 speech로 볼 수 있어 **B-1 결과 확인 후에만**,
  보수적 임계로 시도. bong1 발화 드롭(catastrophic) 시 즉시 기각.
- **Layer 1 필터 보완 (소규모 동반 수정)**: `filtering/__init__.py` `_ANNOTATION_RE`에
  **세그먼트 끝에서 닫히지 않은 대괄호 주석** 패턴 추가(예: `\[[A-Z][A-Za-z_ .]*$` 수준으로 한정 —
  정상 텍스트 과잉 제거 금지, `tests/test_filtering.py`에 케이스 추가).

**검증**: 사전 프로브 재실행으로 오감지율 before/after → 경로 C N=1 → N=3.
**1차 관찰 대상 = bong1 max** (worst-case 게이트). held-out에서 eng1 회귀 감시 필수
(감지 보류가 초기 언어 감지를 늦출 수 있음 — `_detect_language_if_needed`의 2.0s 게이트와 상호작용 확인).

---

### 단계 3 — 화자 전환 리셋 조건부화 (제안 E, sbs1 F1·bong1 문맥 축)

**브랜치 제안**: `exp/conditional-speaker-reset`

**구현 스펙**: `backend.py` `new_speaker` —

- eager 감지 결과(`detect_current_language(window_secs=1.5, min_prob=0.85)`)가
  **현재 `detected_language`와 동일하면**: `refresh_segment` **생략**, `speaker` 라벨·`global_time_offset`만 갱신,
  `_last_emitted_word` 등 필터 상태 유지.
- **다르거나 None(불확신)이면**: 기존 리셋 경로 유지 (보수적 — 불확신 시 리셋이 안전).
- 단계 1 채택 시 언어가 다른 경우는 자연히 단계 1 프로토콜로 합류.

**검증**: 경로 C N=1 → N=3. **1차 관찰 = sbs1 F1 회복 + ytn2 미회귀**(진짜 전환 반응 지연이 없는지).
Exp-106(디바운스 기각 — 진짜 전환도 늦춤)과의 차별점이 유지되는지 전사 정성 대조로 확인.

---

### 단계 4 — 단어 단위 신뢰도 배관 + run 게이트 (제안 D, 게이트 정밀화)

**브랜치 제안**: `exp/token-logprob-gate`

**go/no-go 프로브 (구현 전 필수)**: 워크트리 임시 패치로 디코드 루프에서 (토큰, logprob) 쌍 로깅 →
경로 C 1회 → 전사 대조로 정상/환각 구간 구분 → **per-token logprob 분포 히스토그램**.
분포가 크게 겹치면 **이 단계 전체 스킵**(기록 후 단계 5로) — 배관 작업이 크므로 선분리 확인.

**구현 스펙** (go 판정 시):
- `simul_whisper.py` `_update_tokens` 경로에서 선택 토큰의 logprob 추출
  (beam 경로는 `BeamPyTorchInference`/`BeamSearchDecoder` 배관 필요 — 작업량 大 주의).
- `align_att_base._build_timestamped_words`에서 `ASRToken.probability`(**필드 기존재, 현재 미배관**)에 전달.
- 드롭 로직: `backend._filter_cross_batch_repetitions` 또는 filtering 계층에서
  **저확률 토큰 연속 run**(길이·임계 파라미터화) 단위 드롭. 배치 평균이 아닌 run 단위가 요점.

**검증**: 경로 C N=1 → N=3. **1차 관찰 = bong1 잔존 garbage 차단 + sbs1 오폭 없음(max 미회귀)** +
ytn2 F1(EN 블록 오폭 해소 여부).

---

### 단계 5 — 세그먼트 확정 시 2-pass 재전사 (제안 F) — ⛔ 자율 착수 금지

**major 방향 전환. 본 구현 착수 전 반드시 사용자 보고 + 합의 대기.**

**자율 허용 범위 = 사전 프로브까지** (Exp-137에 설계된 Spike 2, 코드 구조 변경 없음):
- **2a** RTF 마이크로벤치: large-v3-turbo·beam=2로 15/30/45s 고정 버퍼 오프라인 디코딩 → RTF.
- **2b** 동시 경합: 재전사 백그라운드 스레드 + live AlignAtt + Sortformer 동시 가동 → live RTF 증가분·peak VRAM.
- **2c** 언어 recall: `language=auto` 재전사로 ytn2 한↔영 발췌 → 영어 recall (Exp-001 누락 재현 여부).

프로브 결과와 함께 **보고 후 정지**. 게이트(단독 RTF<0.5 + live 안정 + 언어 해결 가능) 판정은 사용자와 합의.
(참고 구현 방향: 확정 이벤트 시 구간 PCM 링버퍼에서 오프라인 재전사 → validated 세그먼트 교체.
`audio_processor`에 PCM 링버퍼 신설 필요 — 현재 PCM은 소비 후 폐기됨.)

---

## 4. 단계 전환·기각 규칙

```
각 단계: 구현 → (프로브) → N=1 → [catastrophic? 즉시 기각] → N=3 → 채택/기각 확정
  → /log-experiment 기록 → 채택 시: master 머지 + baseline·STATE(epoch) 갱신 + held-out 단회
  → 다음 단계로

기각이어도 다음 단계로 진행한다. 단, 의존 관계:
  - 단계 1 기각 → PLC 재평가 스킵 (전환 세금 미해결 상태의 PLC 재실험은 무의미)
  - 단계 4 프로브 no-go → 단계 4 스킵
  - 단계 2 B-2는 B-1 채택 시에만

중간에 avg WER < 15% 달성 → 즉시 보고 후 종료 (잔여 단계는 권고로 기록).
5단계 소진 후 미달 → 결과 종합 + GOAL_WER15.md 탐색 공간에서 차기 후보 제시하며 보고.
```

---

## 5. 측정 명령 레퍼런스

```powershell
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$root = "c:\Users\A040-000-0001\Desktop\260605wlk\wlk"

# 워크트리 생성 (단계 시작 시)
git worktree add -b "exp/<단계브랜치>" "$root\worktrees\<단계브랜치>" master
Set-Location "$root\worktrees\<단계브랜치>"
cmd /c mklink /J .venv ..\..\.venv
.venv\Scripts\python.exe -c "import whisperlivekit; print('OK')"   # import 경로 확인

# ① 스크리닝 (N=1) — 반드시 워크트리 cwd에서
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir "$root\whisperlivekit\model\whisper-large-v3-turbo" `
  --files "$root\test_data\bong1.wav" "$root\test_data\ytn2.mp3" "$root\test_data\sbs1.mp3" `
  --diarization --sortformer-model "$root\whisperlivekit\model\sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --output "$root\.omc\benchmarks\eval_${ts}_<단계명>.json"

# ② 확정 (N=3): 위와 동일 + --repeat 3
# ③ held-out (채택 후보 한정, 단회): --files ytn1.mp3 eng1.mp3
```

---

## 6. 채택/기각 기준 (요약)

```
스크리닝(N=1): catastrophic(+20pp↑) 즉시 기각 / 개선 신호(-3pp↑) N=3 진행 / 미미(±3pp) 판단 기록 후 결정
확정(N=3):  ① max WER 미회귀 (현행 baseline max 기준)  ② median 개선
            WER > F1 우선. F1 폭주(≈0%)만 원인 파악 후 결정.
단계 1·2는 §3.2 불변식 직결 여지 있음 — 게이트 탈락 시 자율 기각 금지, 사용자 질의.
```

---

## 7. 보고 시점 (이때만 사용자 입력 대기)

1. **단계 5 착수 직전** (프로브 결과 첨부) — 합의 필수.
2. **목표 달성**: 평균 WER < 15%.
3. **5단계 소진**: 종합 결과 + 차기 방향 제시.
4. **§3.2 불변 제약 직결 기능의 게이트 탈락**.
5. **VBCable 사망**(재부팅 후에도 RMS < 0.01) / 하니스 버그로 측정 불능.

---

## 8. 참조

| 파일 | 용도 |
|------|------|
| `EXPERIMENTS.md` | **항상 먼저** — baseline·epoch·채택 이력 |
| `CLAUDE.md §3~4` | 설계 제약·측정 규칙·자율 루프 원칙 |
| `GOAL_WER15.md` | 측정 인프라 상세·탐색 공간 백업(단계 기각 시 대체 아이디어) |
| `whisperlivekit/simul_whisper/align_att_base.py` | `_apply_detected_language`·`detect_current_language`(중복 정의)·`infer()`·품질 게이트 |
| `whisperlivekit/simul_whisper/backend.py` | `_check_short_silence_language`(배선 버그)·`new_speaker`·cross-batch 필터 |
| `whisperlivekit/simul_whisper/simul_whisper.py` | `_init_state`(suppress 목록)·`lang_id`·`insert_audio`(트리밍 참고) |
| `whisperlivekit/tokens_alignment.py` | 문장 경계 조립(`compute_punctuations_segments`) |
| `whisperlivekit/audio_processor.py` | VAC·Silence 이벤트·ChangeSpeaker 디스패치 |
| `whisperlivekit/filtering/__init__.py` | Layer 1 필터(`_ANNOTATION_RE` 보완 대상) |
| `whisperlivekit/timed_objects.py` | `ASRToken.probability`(미배관)·마커 타입 신설 위치 |
| `EXPERIMENTS_LOG.md` | 필요한 Exp만 `grep "Exp-NNN"` (특히 138·139·142~149) |
