# Goal Prompt — auto 모드 한국어 전사 후속조치 3단계 순차 루프 (무인 자율 루프)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: `docs/research/AUTO_MODE_KOREAN_PERF_ANALYSIS_20260718.md`(Exp-186)가 발견한 3가지 개선
> 표적을 **우선순위 순서대로(Stage 1→2→3) 순차** 진행한다 — 화자분리 F1 > WER > 문장분리 F1
> 우선순위 원칙에 따라 Stage 1(speaker_change 트리거 손실)이 가장 중요하다.
>
> ⚠️ **진행 규율 — 완전 자율 (사용자 장시간 부재 가정)**:
> - **모든 중간 판단(구현 세부·임계값 선택·재측정 여부·스크리닝 기각/재시도)은 자율 결정**하고 근거를 기록한다.
> - CLAUDE.md §4 "게이트 애매 시 사용자 질의"는 이 루프에서 **"판단 보류 + 각 Stage 보고서에 질의 항목 축적"**으로 대체한다.
> - **각 Stage 종료 시 = 그 Stage만의 채택 권고/기각/보류 + 다음 Stage로 자동 진행**(중단하지 않음). 단, 어느
>   Stage에서든 **§3.1/§3.2 불변 제약과 무관한 catastrophic 회귀**가 나오면 그 Stage만 기각 권고로 전환하고
>   다음 Stage로 계속 진행한다(하나가 막혀도 전체 루프를 멈추지 않는다).
> - **master 머지는 절대 하지 않는다** — 각 Stage 끝날 때마다 해당 브랜치에 커밋만 남기고, **전체 3-Stage 완료
>   후 최종 통합 보고서에서 한 번에** 사용자에게 머지 여부를 묻는다.
> - **유일한 사용자 질문 = 최종 통합 보고서의 머지 여부(Stage별로).**

---

## 0. 출발 지점 (2026-07-18, 반드시 먼저 읽을 것)

- **master = `ec4684e`**(Epoch 5, turbo). 이 goal이 참조하는 모든 발견은 이 커밋 기준.
- **선행 조사**: [docs/research/AUTO_MODE_KOREAN_PERF_ANALYSIS_20260718.md](../research/AUTO_MODE_KOREAN_PERF_ANALYSIS_20260718.md)
  (Exp-186, `EXPERIMENTS_LOG.md`에서 `grep "Exp-186"`으로도 전체 서술 확인 가능) — **각 Stage 착수 전 해당 절을
  반드시 읽는다**(Stage 1→§3.1, Stage 2→§3.2, Stage 3→§3.3/§3.7).
- **관찰용 디버그 로그가 이미 별도 브랜치에 준비돼 있다**: `feat/debug-diagnostics-logging`(커밋 `67a58ad`,
  master `ec4684e`에서 분기, **아직 master 미머지**) — `[TriggerAssign]`(finalize_trigger 배정 5분기),
  `[FinalizeGrace]`, `[CloseLine]`, `[SentenceBoundary]`(온점 판정 규칙명), `[HallucinationDrop]`/
  `[WordCorrection]`을 전부 기존 `--trace-tokens` 플래그로 켤 수 있다(신규 CLI 플래그 없음). **모든 Stage의
  작업 워크트리는 master가 아니라 이 브랜치에서 분기한다** — 그래야 새 로그가 바로 보인다.
- **원본 측정 산출물**: `.omc/benchmarks/eval_auto_kordebug_20260718_1216.json` · 시각화
  `.omc/transcripts/eval_report_auto_kordebug.html` · 전사 `.omc/transcripts/{stem}_C_R{1,2,3}.txt`
  (파일: bong1/ytn2/sbs1/kor1/kor2/kor3/ytn1/kinno) · 서버 로그(이번엔 신규 로그 태그 없음, pre-existing
  태그만) `.omc/server_logs/server_{stem}_C_R{n}_20260718_1[2-3]*.log`.
- **공용 워크트리·venv 규약(반드시 준수)**: 새 워크트리 생성 시 `.venv`는 메인 저장소 Junction 공유
  (`mklink /J .venv ..\..\.venv`) — 새로 만들지 않는다. `uv run`/`uv sync`/`uv pip`/`uv add` 등 **절대 금지**
  ([[shared-venv-uv-run-concurrency-hazard]]) — lint는 `.venv\Scripts\ruff.exe`, 테스트는
  `.venv\Scripts\python.exe -m pytest` 직접 호출. **측정은 반드시 cwd=워크트리에서**
  ([[worktree-eval-import-resolution]] editable 설치 함정 — `python -c "import whisperlivekit;
  print(whisperlivekit.__file__)"`로 워크트리 경로가 찍히는지 먼저 확인).
- **측정 정본**: 경로 C만, provenance 육안 확인(`branch=…@… vbcable=ok`), 스크리닝=`--repeat 1`(방향 신호),
  채택확정=`--repeat 3`(fail-fast 금지, median+min/max/stdev). diar-ON(Sortformer, CRT=3.0), `--lan auto`
  (이 3개 Stage는 전부 auto 모드 문제이므로 `--lan auto`가 기본 — Stage 3에서 kor1 단독 재현 시에도 auto 유지).
  파일: 표준 auto 세트(bong1/ytn2/sbs1) + kor1/kor2/kor3(auto로) + held-out ytn1 + 정성 kinno.
- **채택 우선순위(변경 없음)**: 화자분리 F1 worst-case 미회귀 → WER max 미회귀 → WER median 개선 →
  문장분리 F1(후순위). **Case B(단어 중간 분절) 0건은 수치 무관 hard-fail 게이트.**

---

## Stage 1 — [최우선] speaker_change 확정 트리거 손실 원인 규명

**근거**: Exp-186 §3.1 — bong1(정답 화자전환 14회)에서 diarizer(`[NewSpeaker]`)는 회차당 26~27회
화자전환을 감지하는데 실제 `speaker_change` 확정 트리거는 회차당 1~4회뿐. 원인 후보를 좁히지 못한 채
"구조적 손실"로만 규명됨 — 이 Stage가 그 손실 경로를 구체적으로 특정한다.

### 1-1. 준비
- 워크트리: `feat/debug-diagnostics-logging`에서 분기 → 브랜치 `exp/speaker-change-trigger-loss`,
  워크트리 `worktrees/speaker-change-trigger-loss`.
- 재현 측정: `--lan auto --diarization --sortformer-model ... --compression-ratio-threshold 3.0
  --trace-tokens --repeat 3`로 **bong1 단독** 최소 3회(§0 규약대로 cwd=워크트리, provenance 확인).
  이번엔 `[TriggerAssign]`/`[FinalizeGrace]`/`[CloseLine]`이 서버 로그에 찍힌다 — Exp-186과 달리
  **이게 이 Stage의 1차 데이터**.

### 1-2. 분석 (자율 진행 — 순서 예시, 발견에 따라 조정 가능)
1. diarizer `[NewSpeaker]` 이벤트 26~27건 각각에 대해, 그 시점 이후 가장 가까운
   `[TriggerAssign]` 로그를 시간 정렬로 매칭한다 — 매칭된 항목의 `branch=`(hard_boundary/
   gate_pending/silence/speaker_change/punct_boundary/else)를 집계한다.
2. `branch=gate_pending`(보류, trigger 미설정)로 흡수된 비율이 높다면 — 그 세그먼트가 나중에
   `finalized`로 전환되는지, 전환된다면 그때의 trigger가 무엇으로 바뀌는지(§`tokens_alignment.py`
   게이트 보류 해소 경로, `_apply_silence_grammar_gate`) 추적한다.
3. `speaker != closing.speaker`인데도 `branch=silence`나 `branch=punct_boundary`로 먼저 걸려
   `speaker_change`에 못 미치는 경우(분기 순서상 `hard_boundary`→`silence`→`speaker_change`→
   `punct_boundary` 순으로 우선순위가 걸려 있음, `tokens_alignment.py` 587~608행 부근)가 있는지
   확인 — **분기 우선순위 자체가 손실의 구조적 원인일 가능성**을 최우선 가설로 다룬다.
4. Exp-186 부수 발견(마지막 `else` fallback 분기가 로직상 도달 불가능해 보임)을 이번 로그로
   검증 — `branch=else(fallback)`가 실제로 0건인지 확인.
5. ytn2/sbs1/ytn1(2화자, `language_switch`가 대리 역할을 하는 구조)도 동일 방식으로 참고 대조해,
   bong1처럼 "화자·언어가 상관 없는" 다화자 환경에서 이 손실이 일반적인지 확인한다.

### 1-3. 조치
- 손실 지점이 **분기 우선순위/조건 문제**로 특정되면: 최소한의 수정(분기 순서 조정 또는
  `speaker != closing.speaker`를 더 이른 우선순위로) 구현 → 유닛테스트(TDD) → 짝지음 A/B
  스크리닝(bong1+ytn2+sbs1, `--repeat 1`) → 유망하면 채택확정(`--repeat 3`) + held-out(ytn1 단회).
- 손실 지점이 **diarizer 자체의 화자 귀속 오류**(예: 과분할된 diar 이벤트가 진짜 전환이 아님)로
  판명되면: 코드 수정 없이 규명만 하고 다음 가설로 넘긴다(억지로 고치지 않는다 — 과잉설계 방지).
- 어느 쪽이든 **Case B 0건·기존 채택 게이트 무회귀**를 확인.

### 1-4. Stage 1 산출물
- `EXPERIMENTS_LOG.md` Exp-N(다음 번호) + `EXPERIMENTS.md` 빠른참조 1행(`/log-experiment`).
- 브랜치 `exp/speaker-change-trigger-loss`에 커밋(머지 안 함).
- 다음 Stage로 자동 진행.

---

## Stage 2 — [hard-fail 우선순위] kor1 Case B(단어 중간 분절) 수정

**근거**: Exp-186 §3.2 — kor1에서 "국방 환경을"→"국방환경."+"을", "소모 강요"→"강."+"요 등"으로
분절, 트리거 전부 `silence`, R1·R2 동일 위치 재현. `SILENCE_HARD_SECS=1.2`(Exp-185, 이미 master)
적용 후에도 kor1은 미해소 — kor3와는 다른 사례.

### 2-1. 준비
- 워크트리: `feat/debug-diagnostics-logging`에서 분기(Stage 1 브랜치와 별개, **Stage 1 결과가 코드
  변경을 냈다면 그 브랜치 위에 쌓을지 독립으로 둘지는 이 시점에 자율 판단** — 화자분리 관련 코드와
  문장경계 관련 코드가 실제로 겹치는지 diff로 확인 후 결정) → 브랜치 `exp/kor1-caseb-fix`.
- 재현 측정: kor1 단독 `--lan auto --repeat 3 --trace-tokens`(diar-ON, CRT=3.0) — 이번엔
  `[SentenceBoundary]`/`[CloseLine]`/`[SilenceGate]`가 전부 로그에 찍힌다.

### 2-2. 분석
1. Case B가 발생한 정확한 오디오 시각대("국방 환경을"·"소모 강요" 부근)의 `[SilenceGate]` 로그를
   찾아 `d_eff`(무음 길이), `decision`, `path`를 확인 — 실제 무음 길이가 얼마인지, 그게 왜 분할
   결정으로 이어졌는지.
2. 같은 구간의 `[SentenceBoundary]` 로그로 `should_split_after_silence`/`is_genuine_sentence_end`가
   무엇을 반환했는지 확인 — "환경을"이 종결어미 판정에 걸린 게 아니라 **애초에 무음 게이트가 그
   지점에서 하드 분할을 결정**했다면(Exp-178에서 kor3에 규명했던 것과 동일 계열 — 낭독체 호흡
   pause가 `SILENCE_HARD_SECS` 안전망을 우회/도달하는 경우), 그 무음 길이가 정확히 얼마인지
   측정한다.
3. 가설: 이 지점의 실제 호흡 pause 길이가 `SILENCE_HARD_SECS=1.2`보다 짧아 안전망은 안 걸렸지만,
   문법-조건부 게이트(`should_split_after_silence`)가 "환경을"의 "을"을 다음 발화로 오분류(예:
   한국어 조사 "을"이 `_last_word` 추출에서 독립 단어처럼 취급돼 `is_sentence_final_ko`가 아닌
   경로로 흘러 분할 허용)했을 가능성을 우선 검증 — `_last_word`/조사 처리 로직(`sentence_boundary.py`)
   확인.
4. `kor1_C_R1.txt`/`kor1_C_R2.txt`의 정확한 재현 위치(두 회차 공통)를 오디오 파형/디코더 타임스탬프로
   대조해, 실제 acoustic 특이점(짧은 들숨 등)이 있는지도 확인.

### 2-3. 조치
- 원인이 특정되면(무음게이트 임계·조사 처리 로직 등) 최소 수정 구현 → 유닛테스트(TDD, 이 정확한
  단어 분절 케이스를 회귀 테스트로 고정) → 짝지음 A/B 스크리닝(kor1 단독 반복 + auto 표준세트
  bong1/ytn2/sbs1 무회귀 확인) → 유망하면 채택확정 N=3(kor1 + auto 표준세트) + ko 테스트셋
  (kor2/kor3, `--lan ko`)도 무회귀 확인(§3.7 교차비교 감안 — ko 모드에 영향 없어야 함).
- **hard-fail 게이트이므로**: Case B가 0건이 될 때까지가 목표. 완전 해소가 어려우면 최소한 발생
  조건을 좁혀 빈도를 낮추고, 잔존 사례는 다음 가설로 명시.

### 2-4. Stage 2 산출물
- `/log-experiment`로 Exp 기록.
- 브랜치 `exp/kor1-caseb-fix`에 커밋(머지 안 함).
- 다음 Stage로 자동 진행.

---

## Stage 3 — kor1 순수 한국어 구간 언어오검출(ko→en) 원인 조사

**근거**: Exp-186 §3.3/§3.7 — kor1(순수 한국어)에서 `[ShortSilenceLangCheck]`가 `en (p=0.99)`
같은 고신뢰도로 오검출, WER과 상관(회차별 오검출 0/7/14회 ↔ WER 22.2/43.9/48.0%). auto vs
`--lan ko`(Exp-185) 교차비교로 **이 취약점이 kor2/kor3엔 없고 kor1에만 국한**됨이 확인됨 — 핵심
질문은 "왜 kor1만".

### 3-1. 준비
- 워크트리: `feat/debug-diagnostics-logging`(+ Stage 1/2 결과 반영 여부는 자율 판단)에서 분기 →
  브랜치 `exp/kor1-lang-misdetect`.
- 재현 측정: kor1 단독 `--lan auto --repeat 5`(변동성이 크므로 이 Stage만 예외적으로 5회 —
  오검출 발생 회차를 더 많이 확보하기 위함) `--trace-tokens`.

### 3-2. 분석
1. 오검출이 발생한 회차와 안 한 회차(R1=0회처럼) 각각에서, 오검출 시점의
   `[ShortSilenceLangCheck]` 직전 1.5초 구간이 오디오상 어느 텍스트에 해당하는지 특정한다
   (`.omc/transcripts/kor1_C_R{n}.txt` 타임스탬프 대조 — 새로 `--trace-tokens` 로그의
   시각과 정렬).
2. kor2/kor3(오검출 0건)와 kor1의 **같은 화자·비슷한 낭독 스타일**인데 왜 차이가 나는지 —
   가설 후보: ⓐ 특정 단어의 발음/억양이 우연히 영어처럼 들리는 acoustic 특이점(1번에서 특정한
   텍스트 구간이 반복되면 이 가설 강화), ⓑ `min_prob` 임계값(현재 0.85, `backend.py`
   `new_speaker`/`_check_short_silence_language` 부근)이 짧은 침묵 구간(1.5s)에서 표본이 적어
   불안정, ⓒ kor1 특정 구간의 무음 길이 분포가 다른 파일과 달라 재확인 트리거 빈도 자체가 다름.
   **가설을 임의로 늘리지 말고 로그 근거로 좁혀간다.**
3. Case B(Stage 2)와 언어오검출이 같은 지점(예: "국방 환경을" 부근)에서 겹치는지도 확인 — 겹친다면
   두 실패모드가 같은 acoustic 원인을 공유할 가능성.

### 3-3. 조치
- 원인이 **재확인 임계값·표본 크기 문제**로 특정되면: 파라미터 조정(예: `min_prob` 상향 또는
  최근 윈도우 길이 조정) 스윕 → 짝지음 A/B(kor1 반복 + auto 표준세트 + kor2/kor3 무회귀) →
  유망하면 채택확정.
- 원인이 **kor1 파일 고유의 acoustic 특이점**(일반화 안 되는 데이터 특화 문제)으로 판명되면:
  §3.8 "데이터 특화 하드코딩 금지" 원칙상 **이 파일만을 위한 수정은 하지 않는다** — 규명만 하고
  일반화 가능한 개선안이 있다면만 제안, 없으면 "관찰 완료·수정 보류"로 보고한다.

### 3-4. Stage 3 산출물
- `/log-experiment`로 Exp 기록.
- 브랜치 `exp/kor1-lang-misdetect`에 커밋(머지 안 함).

---

## 4. 최종 통합 보고서 (3-Stage 전부 종료 후, 사용자에게 제시)

1. **Stage별 한 줄 결론**: 채택 권고 / 기각 권고 / 판단 유보(3줄).
2. 각 Stage의 정량 표(짝지음 A/B + 채택확정 N=3 + held-out) + 채택 게이트 판정.
3. 각 Stage의 정성 핵심(원인 규명 결과 + 수정 전/후 전사 인용, 있다면).
4. 브랜치 목록(머지 대기): `exp/speaker-change-trigger-loss`, `exp/kor1-caseb-fix`,
   `exp/kor1-lang-misdetect` (+ 기반 `feat/debug-diagnostics-logging`, 커밋 `67a58ad`) — 서로
   독립인지 순차 의존인지 명시.
5. **사용자 질문**: 각 브랜치를 master에 머지할지(Stage별 개별 확인 가능하게 정리).
6. 미해결·후속 제안(있다면).

## 5. 회귀 교훈 (반드시 준수, 기존 STATE 이월 핵심사실과 정합)

- 모든 Stage에서 **auto 표준세트(bong1/ytn2/sbs1) + ko 테스트셋(kor2/kor3, `--lan ko`) 무회귀**를
  확인한다 — kor1 표적 수정이 다른 파일·다른 언어모드를 회귀시키면 안 된다(§3.8 범용 개선 원칙).
- Case B는 어느 Stage에서도 **신규 발생 0건**이 하드 게이트 — Stage 1(화자분리)이나 Stage 3(언어)
  수정이 우연히 새 Case B를 만들면 그 즉시 원인 조사·수정 우선.
- Exp-186 §3.4(단일화자 파일 화자F1 all-or-nothing 아티팩트)를 kor1/kor2/kor3 결과 해석에 항상
  적용한다 — 화자F1 0%가 "화자오분류"가 아닐 수 있음을 매 판정마다 재확인.
- 데이터 특화 하드코딩 금지(§3.8) — kor1 전용 임시방편(특정 단어·구절 예외처리)은 최후 수단으로만,
  근거를 실험 기록에 남긴다.
