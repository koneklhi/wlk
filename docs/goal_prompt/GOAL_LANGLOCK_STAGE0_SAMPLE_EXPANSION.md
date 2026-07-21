# Goal Prompt — 언어잠금 환각 Stage 0 표본 확대 (+ 안전하면 Stage 1 섀도우까지)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md`(2026-07-21 인계, Stage 0 완료·GO 판정)가 "미결정"으로
> 남긴 다음 단계 중 **안 A(표본 확대, 추천)**를 실행해 가장 큰 미지수(단일언어 세션 오탐률)를 메운다.
> 결과가 안전하면(오탐 없음) **자율로 안 B(Stage 1 섀도우 판정)까지 이어서 진행**하고, 결과가 위험 신호를
> 보이면(단일언어 세션 발동) **즉시 멈추고 사용자 보고**한다 — 이 분기 자체가 목표의 핵심이다.
>
> **먼저 `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` 전체를 읽을 것.** 이 파일은 그 인계서를 전제로
> 압축 서술한다 — 배경·반증된 아이디어·과거 실험 제약(§3)을 반복하지 않는다.

---

## 0. 출발 지점 (세션 시작 시 반드시 재확인)

- **작업 위치**: `worktrees/bong1-eval-diagnostics/`, 브랜치 `exp/lang-lock-stage0` (오늘 확인 시점 HEAD
  `5466b87`). **main 워크트리 cwd에서 코드/스크립트 실행 금지** — 반드시 `cd
  worktrees/bong1-eval-diagnostics`로 이동 후 작업(CLAUDE.md 워크트리 규약, editable 설치 함정
  [[worktree-eval-import-resolution]]). 첫 명령으로
  `.venv\Scripts\python.exe -c "import whisperlivekit; print(whisperlivekit.__file__)"`를 실행해 워크트리
  경로가 찍히는지 확인한다.
- **master 상태 재확인**: `git log --oneline -5 master`로 최신 확인. 오늘(2026-07-21) 기준 master는
  `e4284cf`이며 인계서가 미커밋이라 적었던 "EXPERIMENTS.md stale 정정 2건"은 **이미 이 커밋에 포함돼
  해결됐다** — 별도로 재작업하지 않는다. `d4b7556`(분기점) 이후 master 변경은 `whisperlivekit/`·
  `scripts/eval.py` 어느 쪽도 건드리지 않았다(확인 완료 — 프론트/문서만) — 이 브랜치는 **재베이스 불필요**.
- **워크트리 작업트리 상태**: `git status`에 이전 회차 전사 산출물(`.omc/transcripts/bong1_C_R2~R10.txt`
  등)이 수정/미추적으로 남아 있다 — 이전 세션의 10회 소급 측정 잔재로, **코드 변경 아님**. 이번 세션 측정이
  덮어써도 무방하고, 새로 생기는 전사·로그를 §7 산출물 규칙대로 커밋하면 된다.
- **test_data 하드링크**: `kor1~3.wav`, `eng1.mp3`, `sbs1.mp3`, `ytn1.mp3`와 대응 정답 `.txt`가 이미 이
  워크트리에 존재 확인됨(§0 확인 완료) — 추가 하드링크 불필요.
- **VBCable·포트 확인 (측정 전 필수)**: 다른 세션이 CABLE Output을 캡처 중이면 측정이 오염된다
  ([[feedback-vbcable-overlap-check]]). 포트 8901을 배포 UI 세션이 점유하고 있을 수 있다(§6 함정4) — 점유
  프로세스 확인 후 진행. 문제 있으면 **작업을 멈추고 사용자에게 보고**(원격 조치 불가 항목).
- **uv 절대 금지**: `.venv\Scripts\python.exe`/`.venv\Scripts\ruff.exe` 직접 호출만
  ([[shared-venv-uv-run-concurrency-hazard]]).

---

## 1. 목표

1. **1차 목표(필수, 안 A)**: 단일언어 세션(`kor1~3` `--lan ko`, `eng1` `--lan en`) + auto held-out
   추가분(`sbs1`, `ytn1`)에서 `[SotLangProbe]` `p_opp` 신호의 **오탐률**을 측정한다 — 인계서 §7이 명시한
   "가장 큰 미지수". 코드 변경 없음, 순수 측정.
2. **2차 목표(조건부, 안 B)**: 1차 결과가 "안전"(§3 판정 기준)이면, 인계서 §4 "Stage 1을 하게 될 경우 설계
   요지"를 그대로 구현하되 **섀도우 모드만**(`would_fire` 로깅 전용, 실제 게이트 미적용) — 전 테스트셋에서
   발동 패턴을 관측한다. 실제 언어 재감지를 트리거하는 코드 경로는 이 세션에서 **활성화하지 않는다**.
3. 어느 경우든 Exp 번호를 부여해 기록하고(인계서 §7 "Exp 번호 미부여" 해소), 다음 세션이 이어받을 수 있게
   인계서를 갱신한다.

**하지 않는 것**: 실제 게이트 적용(`_apply_detected_language` 호출을 실전 트리거로 연결), master 머지,
언어잠금 이외의 이슈(§2-2 영어 단어 삽입/누락 축, `fix/samelang-no-refresh` 중복 가설 등 — 인계서 §7의
다른 미해결 항목) 착수.

---

## 2. 실행 순서 — 안 A (표본 확대)

### 2-1. 측정 (스크리닝 tier, `--repeat 1`, `--trace-tokens` 필수)

파일마다 **별도 eval.py 실행**(로그 1:1 대응 유지 — 인계서가 bong1/ytn2 R1을 그렇게 남겼다):

```bash
cd worktrees/bong1-eval-diagnostics

# ko 세션 3개 (각각 단독 실행)
.venv\Scripts\python.exe scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/kor1.wav --lan ko --repeat 1 \
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo \
  --compression-ratio-threshold 3.0 --trace-tokens \
  --output .omc/benchmarks/eval_kor1_stage0_R1.json
# kor2, kor3 동일 패턴 반복 (파일명·output만 교체)

# en 세션
.venv\Scripts\python.exe scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/eng1.mp3 --lan en --repeat 1 \
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo \
  --compression-ratio-threshold 3.0 --trace-tokens \
  --output .omc/benchmarks/eval_eng1_stage0_R1.json

# auto held-out 2개 (sbs1은 표준 테스트셋이지만 이번 Stage0 프로브 로그가 없어 재측정, ytn1은 held-out)
.venv\Scripts\python.exe scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/sbs1.mp3 test_data/ytn1.mp3 --lan auto --repeat 1 \
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo \
  --compression-ratio-threshold 3.0 --trace-tokens \
  --output .omc/benchmarks/eval_sbs1ytn1_stage0_R1.json
```

각 실행 전 서버 시작 로그의 provenance(`branch=exp/lang-lock-stage0@... vbcable=ok`)를 확인한다. 서버
로그 파일 경로(`.omc/server_logs/server_*.log`)를 실행마다 기록해둘 것 — 다음 단계 입력이다.

### 2-2. 프로브 분석 (`analyze_sot_lang_probe.py`, `--tau 0.97`)

단일언어 세션엔 알려진 실패 구간(target)이 없다 — **오탐 전수 목록**이 필요하므로 `--target` 없이
`--list-mismatch`로 돌려 전체 mismatch 이벤트를 뽑는다:

```bash
.venv\Scripts\python.exe scripts/analyze_sot_lang_probe.py --log <kor1 로그> --tau 0.97 --list-mismatch
# kor2, kor3, eng1, sbs1, ytn1 로그도 동일하게
```

각 파일에 대해 기록할 것:
- 발동(mismatch, `p_opp>=0.97`) 총 건수·버스트 수.
- **정상 전사 구간 발동**(=오탐) 건수 — bong1/ytn2 R1에서 0건이었던 것과 비교.
- 발동이 있다면 그 구간의 실제 전사(해당 `.omc/transcripts/` 또는 새로 생성될 전사 파일)를 대조해 "정당한
  전환 선행"(인계서 §2-3 "정당전환 선행" 범주)인지 진짜 오탐인지 판정.

### 2-3. LMR 소급 (있으면)

각 파일의 eval JSON에 대해 `scripts/backfill_lang_mismatch.py`로 LMR을 계산해 참고 지표로 남긴다(단일언어
세션은 정의상 `LMR_ko`/`LMR_en`가 거의 0이어야 정상 — 0이 아니면 그 자체가 신호).

---

## 3. 분기 판정 (핵심 — 자율 진행 여부를 여기서 결정한다)

**"안전" 판정 = 아래 전부 참**:
- ko/en 단일언어 세션(kor1~3, eng1) 어디에서도 **정상 전사 구간 발동이 0건**이거나, 발동이 전부 "정당전환
  선행"으로 명확히 설명됨(예: 실제로 그 구간에 code-switching이 있었던 경우 — 그러나 kor1~3/eng1은 설계상
  단일언어 낭독이므로 이 케이스가 나오면 그 자체를 의아하게 보고 전사를 재확인할 것).
- sbs1·ytn1(auto)에서 새로 발견되는 발동이 인계서 §2-3의 참양성 패턴(언어잠금 실패와 명백히 동시 발생)과
  일관됨 — 즉 Exp-160류 스퓨리어스 오탐 재현이 없음.

→ **안전하면 §4(안 B)로 자율 진행**. 사용자에게 중간 확인 요청하지 않는다(CLAUDE.md §4 자율 루프 원칙 —
구현→측정→기록은 자율, major 방향 전환만 보고).

**"위험" 판정 = 위 중 하나라도 거짓**(대표 우려 시나리오: kor1~3 어디선가 발동 — 인계서 §3 표 `Exp-189`
행이 경고한 "p=0.95~1.00 고신뢰 오탐이 실측됨" 패턴의 재현):

→ **안 B로 진행하지 않고 즉시 정지**. 이유: Stage 1 게이트 설계(τ, K/T 지속조건) 전체가 "단일언어 세션에서
발동 0건"이라는 전제 위에 서 있다(인계서 §2-3). 이 전제가 깨지면 게이트 파라미터를 임의로 더 보수적으로
튜닝해서 계속 진행하는 것이 아니라 — 그 자체가 설계 재검토가 필요한 **major 방향 전환**이므로 §6 보고
형식대로 사용자에게 수치·구간·전사 인용을 제시하고 판단을 구한다. §5(안 B 설계)는 시도하지 않는다.

---

## 4. 실행 순서 — 안 B (Stage 1 섀도우, §3 "안전" 판정 시에만)

인계서 §4 "Stage 1을 하게 될 경우 설계 요지"를 그대로 구현한다(이미 검토된 설계 — 재설계하지 않음):

- **트리거 지점**: `infer()` 첫 forward 직후(`align_att_base.py:449-460` 근처, 세션 시작 시 라인 재확인).
- **게이트(전부 AND, 섀도우 모드라 전부 로깅만)**: `cfg.language=="auto"` / `detected_language is not None`
  / `segments_len() >= 2.0s` / `p_opp >= τ`(0.97 근처, 스윕 여지) / 연속 K=3배치 AND T=1.0s 지속 / 쿨다운
  3.0s(`last_lang_switch_time` 재사용) / 다른 트리거 arm(`pending_language_switch`·`eager_lang_detect`) 진입
  중 아님 / refresh·new_speaker·긴침묵 시 증거 리셋.
- **섀도우 규칙(이번 세션의 핵심 제약)**: 게이트가 전부 만족돼도 `_apply_detected_language`를 **호출하지
  않는다** — `[Stage1Shadow] would_fire=True lang=... p_opp=... t=...` 형태로 로그만 남긴다. 실제 언어
  재감지·재확정을 트리거하는 코드는 이 세션에서 작성하지 않는다(인계서가 명시한 "적용은 별도" 원칙).
- **기각 조건 재확인**: 구현 도중 `cfg.language=="ko"/"en"`에서도 게이트가 만족되는 경로가 있으면(가드
  버그) 즉시 수정 — auto 전용이어야 한다.

### TDD
새 단위테스트로 게이트 각 조건(만족/불만족 케이스)을 검증한다. 실제 언어 재감지 동작을 바꾸지 않으므로
기존 회귀 테스트는 전부 그대로 통과해야 한다(행동 변경 0 확인이 이 단계의 성공 기준).

### 측정
전 테스트셋에서 `would_fire` 발동 카운트만 수집(behavior 변경이 없으므로 WER/F1 재측정은 불필요 — 이미
동일 코드로 측정된 §2 결과를 그대로 참조):
- auto: bong1(기존 로그 재사용 가능하면 재사용, 없으면 재측정) / ytn2 / sbs1 / ytn1
- ko: kor1~3
- en: eng1

---

## 5. 산출물

- `docs/research/SOT_LANG_PROBE_STAGE0.md`에 "§ 표본 확대(단일언어 세션 오탐률)" 절 추가 — 수치·판정.
- `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` 갱신: §7 "단일언어 세션 오탐률 전혀 모름" 항목을 결과로
  대체, §4 다음 단계 표에 "완료" 표시, 안 B까지 진행했다면 그 설계·would_fire 결과도 추가, 위험 판정으로
  멈췄다면 그 사실과 근거를 최상단에 명확히.
- `/log-experiment`로 `EXPERIMENTS_LOG.md` + `EXPERIMENTS.md` 빠른참조에 Exp-N 부여(다음 번호는
  `EXPERIMENTS.md`에서 확인). Stage 0 본편(LMR+SOT probe, 지금까지 미부여 상태)과 이번 표본 확대(+ 안 B)를
  같은 Exp 안에 서술할지 분리할지는 `/log-experiment` 스킬 관례를 따라 판단.
- 브랜치 `exp/lang-lock-stage0`에 커밋(**master 머지 금지** — 사용자 확인 후).
- 새로 생성된 `.omc/benchmarks/*.json`, `.omc/transcripts/*`, `.omc/server_logs/*`도 통상 관례대로 커밋.

---

## 6. 완료 보고 (사용자 복귀 시 제시)

1. **한 줄 결론**: 안전(안 B까지 완료) / 위험(§3에서 정지, 사용자 판단 대기) / 하니스 문제로 중단(§0 함정
   재발 등).
2. 정량표: 파일별 발동 건수·오탐 건수·LMR(있으면).
3. "위험" 분기라면: 문제 구간의 시각·전사 인용 + 왜 인계서 §2-3 전제가 깨졌다고 보는지.
4. "안전+안 B 완료" 분기라면: 섀도우 게이트 구현 요약 + 전 테스트셋 `would_fire` 카운트 + 코드 diff 위치.
5. 다음 세션 결정 사항: 안 B 결과를 실제 게이트 적용(behavior 변경)으로 이어갈지, 이번엔 여기서 종료(안
   C)할지 — 이 결정은 사용자 몫으로 명시.

---

## 7. 회귀·안전 수칙 (반드시 준수)

- 이 세션은 **무인 실행**(사용자 퇴근 중)이 전제다. §3 분기 외에는 중간 확인 없이 자율 진행하되, 다음
  상황은 **즉시 작업을 멈추고** 완료 보고에 상세히 남긴다(추측으로 임의 복구 금지): VBCable 무음/사망
  ([[vbcable-loopback-instability]]), 포트 충돌로 서버 기동 실패, `returncode=3` 등 venv 오염 의심 신호
  ([[shared-venv-uv-run-concurrency-hazard]] — 먼저 서버 로그로 원인 확인, 임의 `uv sync` 금지).
- 안 B 구현은 **행동 변경 0**이 성공 기준이다 — 실수로 `_apply_detected_language`를 실제 호출 경로에
  연결하면 auto 세션 전체의 언어 재감지 거동이 바뀐다. 커밋 전 `git diff`로 섀도우 로깅만 추가됐는지
  재확인.
- kor1/kor2/kor3의 화자분리 F1이 0.0%/100.0% 극단으로 나오는 것은 지표 산식 경계값 아티팩트이지 실패가
  아니다([[paired-ab-zero-firing-noise-control]] 계열 — 실제 화자분리 실패와 혼동하지 않는다).
- N=1(스크리닝) 결과만으로 "오탐률 확정"이라 쓰지 않는다 — §6 보고에 "스크리닝 1회 기준"임을 명시하고,
  후속 세션이 필요하면 채택확정(N≥3)을 제안한다.
