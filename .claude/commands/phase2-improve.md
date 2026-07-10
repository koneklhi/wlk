---
description: Phase 2 STT 성능 개선 반자율 루프 — 한 이터레이션마다 가설 수립·구현·측정·보고를 수행한다
---

# Phase 2 STT 성능 개선 루프 — 1 이터레이션

**목표 (우선순위 = 화자분리 F1 > WER > 문장분리 F1)**: 테스트 bong1·ytn2·sbs1에서 **① 화자전환 경계마다 줄분리 실현(화자분리 F1 — 목표치는 metric 구현 후 확정) → ② WER < 15% → ③ 문장분리 F1(nice-to-have, 게이트 아님)**. held-out 정량(ytn1·eng1) 회귀 없음 + 정성 sanity(kinno — 누락/환각·거친 화자/문장 분리만). **절대 금지 = Case B(한 단어/문장이 단어 중간에서 쪼개짐).** Case A(동일 화자 인접 문장 미분리)는 허용. 요구사항 정본 = [docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md).
(현재 2-F1 metric 미구현 — 신형식 파서 착지 전까지 단일 `seg_f1`을 화자분리 F1 근사로 해석; 착지 후 화자분리/문장분리 F1 분리 사용.)

---

## 0. ASSESS — 현재 상태 파악

다음 순서로 현황을 파악한다. **파악 없이 구현으로 건너뛰지 않는다.**

1. `EXPERIMENTS.md`의 최신 Exp 항목을 읽어 현재 채택 베이스라인 수치(WER median/max, 화자분리/문장분리 F1 — regime v2; 미구현 시 단일 `seg_f1`을 화자분리 F1 근사로)와 "다음 가설" 항목을 추출한다.
2. `.omc/benchmarks/` 디렉토리에서 가장 최근 JSON을 찾아 파일별 수치를 확인한다:
   ```powershell
   Get-ChildItem .omc\benchmarks\eval_*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 3
   ```
3. bong1 수치가 없으면(최초 측정 전) → **이번 이터레이션의 1순위는 bong1 베이스라인 확립**이다.
4. 목표 달성 여부를 파일별로 표로 정리:

   | 파일 | 화자분리 F1(경계 분리·1순위) | WER(2순위) | WER<15%? | Case B 有? | 문장분리 F1(참고·3순위) |
   |------|------|---------|----------|---------|---------|
   | bong1 | ? | ? | ? | ? | ? |
   | ytn2 | ? | ? | ? | ? | ? |
   | sbs1 | ? | ? | ? | ? | ? |
   | ytn1 (held-out 정량) | ? | ? | ? | ? | ? |
   | eng1 (held-out 정량) | ? | ? | ? | ? | ? |
   | kinno (held-out 정성) | 거친 확인 | 수치 불신 | — | ? | 거친 확인 |

   > 화자분리 F1 numeric은 2-F1 metric 구현 후에만 산출 — 그 전에는 전사 정독으로 "화자전환마다 줄분리됐는지"를 정성 확인한다.

5. **테스트 3종(bong1+ytn2+sbs1) 모두 ① 화자전환 경계 줄분리 실현(화자분리 F1 목표치) AND ② WER<15% 달성 + Case B 없음 확인 시** → 루프 종료 선언 후 held-out 최종 검증만 진행하고 사용자에게 목표 달성 보고. `/loop` 재호출 없이 종료. **문장분리 F1은 종료 게이트가 아니다**(nice-to-have).

---

## 1. PLAN — 가설 수립

직전 실험의 "다음 가설"을 출발점으로 삼는다. 동시에 아래 개선 방향 우선순위를 감안해 **하나의 구체적이고 검증 가능한 가설**을 선택한다.

### 개선 방향 우선순위 (ROADMAP §Phase 2 성능 개선 우선순위)

**1순위 — 스트리밍 단계 적극 개선:**
- 불필요한 단어/글자 삽입 감소 (반복 토큰 "바 바 바", 환각 삽입)
- 문장 끝맺음·확정 타이밍 개선 (조기/지연 확정 없이)
- 언어 전환 정확도 향상 (한↔영 짧은 텀 코드스위칭, 다화자)

**2순위 — 화자분할 과분할 완화:**
- Sortformer 파라미터 조정 (`compression-ratio-threshold`, `no_speech_threshold` 등)
- 화자전환 경계 신호 품질 개선

**후순위 — 모델 자체 한계 (단어 치환 오류 "육군"→"6군")**: Phase 2에서 직접 추적하지 않음.

### 가설 형식
```
가설: [무엇이 문제인가] → [어떤 변경을 하면 어떻게 개선될 것이라 예측하는가]
근거: [EXPERIMENTS.md 이전 결과 또는 코드 분석 근거]
대상 파일: [수정할 파일 경로]
예상 효과: [bong1/ytn2/sbs1 중 어디에서 화자분리 F1↑(화자전환 경계 분리) 또는 WER↓; 문장분리 F1↑는 부수]
```

**가설 결정 전 금지 사항**:
- 동일 이벤트 동일 이유로 이미 기각된 실험을 재시도하지 않는다 (EXPERIMENTS.md + PHASE2_EXPERIMENTS.md 아카이브 확인).
- 데이터 특화 하드코딩(특정 단어·구절 암기)은 일반화가 아니므로 금지.
- 변경 범위가 너무 크면 → 더 작게 쪼개서 하나씩.

---

## 2. IMPLEMENT — 구현 (워크트리 격리)

**main 브랜치에는 코드 편집 불가.** 반드시 feature 브랜치 + 워크트리에서 작업한다.

### 워크트리 준비

기존 실험 브랜치가 있으면 재사용한다. 새로 만들 경우:

```powershell
# 브랜치명 예: exp/phase2-[가설 키워드]
$branch = "exp/phase2-[키워드]"
git worktree add worktrees\$branch $branch 2>$null
if ($LASTEXITCODE -ne 0) {
    git branch $branch
    git worktree add worktrees\$branch $branch
}
# .venv Junction (패키지 변경 없으면 메인 공유)
if (-not (Test-Path "worktrees\$branch\.venv")) {
    cmd /c "mklink /J worktrees\$branch\.venv .venv"
}
```

### 변경 실행

- **외과적 변경 원칙**: 가설에 필요한 최소한의 코드만 수정한다. 범위를 벗어난 리팩터링 금지.
- 변경 후 간단한 단위 테스트 실행:
  ```powershell
  worktrees\[branch]\.venv\Scripts\python.exe -m pytest tests/ -x -q
  ```
  pytest 실패 시 → 수정 후 재시도. pytest가 통과하지 않으면 측정으로 넘어가지 않는다.

---

## 3. MEASURE — 측정 (경로 C, 2계층: 스크리닝 1회 / 채택 확정 3회)

**측정 기준 경로 = 경로 C (VBCable 루프백) 전용.** 경로 A는 개발 스모크용일 뿐 채택 판단에 사용하지 않는다.

**측정 시 cwd = 워크트리 경로**에서 실행해야 editable install이 올바른 코드를 바라본다. main에서 실행하면 메인 코드가 측정됨 — 주의.

**provenance 게이트 (필수)**: 측정 시작 직후 출력되는 `[provenance]` 줄에서 `code=<워크트리명>`, `branch=<해당 브랜치>`, 변경한 디코더 설정(beams/CRT 등)이 의도한 값으로 찍히는지 반드시 눈으로 확인한다. 기대 경로와 다르면 eval이 즉시 중단(fail-fast)된다 — 그 경우 cwd를 점검하고 재실행.

### ① 스크리닝 측정 (평소 기본 — 방향 탐색·catastrophic 회귀 감지)

```powershell
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
Set-Location worktrees\[branch]
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_exp_screen_$ts.json"
Set-Location ..\..\  # main으로 복귀
```
# ↑ --repeat 생략 = 1회. 수치는 '방향 신호'로만 해석, 미세 채택/기각 결론의 근거로 쓰지 않는다.

### ② 채택 확정 측정 (master 머지 직전에만 — N≥3회 반복)

```powershell
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
Set-Location worktrees\[branch]
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --repeat 3 `
  --output ".omc/benchmarks/eval_exp_candidate_$ts.json"
Set-Location ..\..\  # main으로 복귀
```

- **채택 확정 측정 도중 fail-fast 금지** — N=3회 전부 실행한다(② 단계 한정). 단 VBCable 무음 캡처(WER 100%)·포트 충돌 등 하니스 버그는 즉시 중단하고 수정 후 재시작.
- VBCable 루프백 불안정 의심 시: `scripts/vbcable_test.py` 실행 후 이상 있으면 Audiosrv 재시작 / PC 재부팅.

### 측정 소요 시간 예시
- 스크리닝 1회 (bong1+ytn2+sbs1, diar-ON): 약 6분 이상
- 채택 확정 3회 (동일): 약 18분 이상 — 백그라운드 실행 권장 (`run_in_background: true`).

---

## 4. ANALYZE — 분석

결과 JSON을 읽어 아래 항목을 정리한다:

```
파일별 결과 (우선순위 화자분리 F1 > WER > 문장분리 F1):
  bong1: 화자분리 F1=?  WER median/max/stdev = ? / ? / ?  문장분리 F1=?  Case B 有?=?  vs 베이스라인 Δ
  ytn2:  화자분리 F1=?  WER median/max/stdev = ? / ? / ?  문장분리 F1=?  Case B 有?=?  vs 베이스라인 Δ
  sbs1:  화자분리 F1=?  WER median/max/stdev = ? / ? / ?  문장분리 F1=?  Case B 有?=?  vs 베이스라인 Δ
  (kinno: 정성 sanity — 누락/환각·거친 화자/문장 분리만 확인, 수치 불신)
```
> 2-F1 metric 미구현 시: `seg_f1`을 화자분리 F1 근사로 쓰고, 문장분리·Case B는 전사 정독으로 판정.

### 채택 후보 조건 (우선순위 순 — [docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md) §4)

| # | 조건 | 판정 |
|---|------|------|
| ① | **화자전환 경계 분리(화자분리 F1) worst-case 미회귀** (1순위) | ✓ / ✗ |
| ② | 테스트 3종 WER max 미회귀 + median 회귀 ≤ +5pp (2순위) | ✓ / ✗ |
| ③ | **Case B(단어 중간 분절) 신규 발생 없음** (전사 정독·hard floor) | ✓ / ✗ |
| ④ | pytest 전부 통과 | ✓ / ✗ |
| ⑤ | 삽입 아티팩트(반복 토큰·환각·**한영 외 언어**) 악화 없음 (전사 JSON·경로 B 정성) | ✓ / ✗ |
| ⑥ | 채택 후보 시 held-out 정량(ytn1+eng1) catastrophic 회귀 없음 + 정성(kinno) 대규모 누락/환각 없음 | 측정 후 확인 |

> **문장분리 F1은 채택 게이트가 아니다**(nice-to-have) — 하락해도 기각 근거 아님(Case A 허용). 단 Precision↓이 Case B 때문이면 ③에서 걸린다.

**채택 우선순위**: **화자분리 F1 worst-case 미회귀(1순위) → WER max 미회귀 → WER median 개선(2순위) → 문장분리 F1(후순위)**.
최악 케이스가 터지는 설정은 median이 좋아도 기각. **Case B는 수치 무관 기각·수정.**

**목표 필수 기능 예외**: 위 ①~⑤ 게이트 미달이라도 그 변경이 §3.1·§3.2 등 핵심 불변 제약 달성에 필요한 기반 기능이면 자율 기각하지 말고 **사용자에게 채택 여부를 질의한다** (ⓐ목표 근거 ⓑ회귀 위치 ⓒ대안 구현 여지 함께 보고). 일반 WER/F1 개선 실험에는 해당 없음.

채택 후보 조건 미달 시 → 7. 기각 절차로 이동 (단 위 예외에 해당하면 자율 기각 대신 사용자 질의 먼저).

---

## 5. HELD-OUT 검증 (채택 후보만)

조건 ①~④ 모두 충족 시에만 held-out을 측정한다. (매번 돌리면 불필요한 시간 낭비)
held-out은 **단회(--repeat 생략)** 검증 — 일반화 catastrophic 회귀 여부만 확인하므로 3회 반복 불필요.

```powershell
$env:PYTHONIOENCODING = "utf-8"
Set-Location worktrees\[branch]
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/ytn1.mp3 test_data/eng1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0
Set-Location ..\..\
```

held-out에서 catastrophic 회귀 없으면 → 채택 후보 확정.

---

## 6. REPORT — 사용자에게 보고 + 승인 대기

아래 형식으로 정리해 사용자에게 제시한다. **사용자 승인 없이 채택/기각을 확정하거나 로그를 기록하지 않는다.**

```
## Exp-[N] 결과 보고 (채택 후보 / 기각)

**가설**: [한 줄]
**변경 파일**: [경로:라인]

### 테스트 세트 결과

| 파일  | 화자분리 F1(1순위) | WER median | WER max | 문장분리 F1(참고) | Case B? | vs 베이스라인 |
|-------|-----------|-----------|---------|-----------|---------|-------------|
| bong1 |           |           |         |           |         |             |
| ytn2  |           |           |         |           |         |             |
| sbs1  |           |           |         |           |         |             |

### Held-out 결과 (채택 후보만)

| 파일  | 화자분리 F1 | WER median | WER max | 문장분리 F1 | catastrophic? |
|-------|-----------|-----------|---------|-----------|---------------|
| ytn1 (정량) |     |           |         |           |               |
| eng1 (정량) |     |           |         |           |               |
| kinno (정성 sanity) | 거친 확인 | 수치 불신 | — | 거친 확인 | 누락/환각 有? |

### 채택 조건 판정

① F1 유의미 상승: ✓/✗ — [근거]
② WER 회귀 ≤+5pp: ✓/✗ — [수치]
③ pytest: ✓/✗
④ 아티팩트 미악화: ✓/✗ — [정성 관찰]
⑤ Held-out 회귀 없음: ✓/✗

**권고**: 채택 / 기각 / 수정 후 재시도
**이유**: [한 줄]
**다음 가설 예고**: [채택 시 다음 개선 방향 / 기각 시 대안]

→ 채택·기각 여부를 알려주세요. 채택 시 /log-experiment로 기록합니다.
```

---

## 7. 채택 시 후속 처리

사용자가 채택 확인 시:

1. `/log-experiment` 실행 → `EXPERIMENTS.md`에 Exp-N 항목 추가
2. 워크트리 브랜치를 main에 PR 또는 merge (사용자 지시에 따름)
3. 목표 달성 여부 재확인 → **미달성이면 루프 재진입**

---

## 8. 기각 시 후속 처리

기각 시:

1. 기각 이유와 관찰 사실을 `EXPERIMENTS.md`에 Exp-N(기각)으로 간략 기록 요청 (실패도 기록)
2. 워크트리 변경 롤백 또는 브랜치 삭제
3. 기각 원인을 감안해 다음 가설을 재수립 → **루프 재진입**

---

## 9. 루프 종료 조건

아래 중 하나 해당 시 루프를 종료한다:

- **목표 달성**: 테스트 3종 모두 ① 화자전환 경계 줄분리 실현(화자분리 F1 목표치) AND ② WER<15% + Case B 없음 (0단계에서 확인). *문장분리 F1은 종료 게이트 아님(nice-to-have).*
- **사용자 명시적 중단**: "이 방향은 그만"·"다른 Phase로 이동" 등 명시
- **3회 연속 기각 + 신규 가설 없음**: EXPERIMENTS.md(+PHASE2_EXPERIMENTS.md 아카이브)에서 시도 가능한 접근이 소진됨 → 사용자에게 방향 재설정 요청 후 종료

---

## 참조 파일

- [ROADMAP.md](../ROADMAP.md) — Phase 2 완료 기준·채택 규칙 상세
- [EXPERIMENTS.md](../EXPERIMENTS.md) — 실험 기록 및 최신 베이스라인 (Exp-001~130은 [PHASE2_EXPERIMENTS.md](../PHASE2_EXPERIMENTS.md) 아카이브)
- [docs/TESTING.md](../docs/TESTING.md) — 경로별 실행 명령 상세
- [.claude/commands/eval.md](eval.md) — eval.py 옵션 레퍼런스
- [.claude/commands/log-experiment.md](log-experiment.md) — 실험 기록 형식
