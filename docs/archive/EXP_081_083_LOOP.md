# Exp-081/082/083 자동 루프 Goal Prompt

## 목표
WER 30% 미만 달성을 위해 **A → B → C** 순서로 단계별 실험 수행.
각 단계는 경로 C 기준 N≥3회 반복 측정 후 자동 판단.

---

## 입력 (현재 상태)

**베이스라인 (Exp-080)**: WER median 31.4%, max 38.7%, F1 78.1%, stdev 1.2%
**목표**: WER 30% 미만
**Gap**: 1.4%p

**측정 파일**: sbs1.mp3, ytn1.mp3
**평가 경로**: 경로 C (VBCable 루프백)
**측정 방식**: `/eval --repeat 3` (N=3)

---

## 단계 A: Exp-081 (beam_size=3)

**요구사항**:
1. 워크트리 생성: `phase4/exp-081-beam3` (또는 EnterWorktree 사용)
2. 코드 변경:
   - `whisperlivekit/parse_args.py`: `--beams` 기본값 2 → 3
3. 실행: `/eval` (경로 C, N=3회)
4. 결과 분석:
   - sbs1/ytn1 각각 WER median/min/max/stdev 기록
   - 베이스라인(median 31.4%, max 38.7%) 대비 비교
   - F1 76.2%/80.0% 회귀 확인
5. 판단:
   - **채택**: median ≥ 30% (즉, ≥ 1.4%p 개선) AND max 회귀 ≤ +5%p
   - **진행**: 위 조건 무관하게 B로 자동 이동
6. 기록: `/log-experiment` (제목: "beam_size=3")

---

## 단계 B: Exp-082 (nonspeech_prob 상향)

**목적**: 세그먼트 시작 시 침묵 오감지 억제로 무음 환각 감소.
**가설**: `AlignAttConfig.nonspeech_prob` 0.5 → 0.6으로 올리면 침묵 구간에서 Whisper가 생성한 토큰을 더 적극적으로 스킵해 WER 감소.
**참고**: `compression_ratio_threshold`는 SimulStreaming 백엔드에 미적용(구 local_agreement 배치 전용) — Candidate B 재설계.
**변경 파일**: `whisperlivekit/simul_whisper/config.py` `nonspeech_prob: float = 0.5` → `0.6`

**요구사항**:
1. 워크트리 생성: `phase4/exp-082-nonspeech06`
2. 코드 변경:
   - `whisperlivekit/simul_whisper/config.py`: `nonspeech_prob: float = 0.5` → `0.6`
3. 실행: `/eval` (경로 C, N=3회)
4. 결과 분석:
   - Exp-080 베이스라인 기준으로 median/max/stdev 비교
   - F1 회귀 여부 확인
5. 판단:
   - **채택**: median 개선 AND max 회귀 ≤ +5%p
   - **진행**: 결과 무관 C로 자동 이동
6. 기록: `/log-experiment` (제목: "nonspeech_prob=0.6")

---

## 단계 C: Exp-083 (audio_max_len 축소)

**목적**: 세그먼트 최대 길이 단축으로 컨텍스트 누적 드리프트 억제.
**가설**: `audio_max_len` 20.0 → 15.0으로 줄이면 긴 음성 구간에서 누적되는 컨텍스트 오류가 줄어 WER 개선.
**참고**: `no_speech_threshold`는 SimulStreaming에서 `AlignAttConfig.nonspeech_prob`에 해당 — Exp-082에서 이미 검증.
**변경 파일**: `whisperlivekit/simul_whisper/config.py` `audio_max_len: float = 20.0` → `15.0`

**요구사항**:
1. 워크트리 생성: `phase4/exp-083-maxlen15`
2. 코드 변경:
   - `whisperlivekit/simul_whisper/config.py`: `audio_max_len: float = 20.0` → `15.0`
3. 실행: `/eval` (경로 C, N=3회)
4. 결과 분석:
   - Exp-080 베이스라인 기준으로 median/max/stdev 비교
   - F1 회귀 여부 확인
5. 판단:
   - **채택**: median 개선 AND max 회귀 ≤ +5%p
   - **완료**: 최종 결과 보고
6. 기록: `/log-experiment` (제목: "audio_max_len=15")

---

## 채택 판정 기준 (각 단계마다)

### 채택 조건 (모두 충족)
1. ① 경로 C WER median이 직전 베이스라인 대비 **≥ 1%p 개선** OR **목표(30%) 달성**
2. ② WER max 회귀 **≤ +5%p**
3. ③ F1 회귀 **없음** (즉, 76.2% & 80.0% 유지)
4. ④ pytest 유닛 테스트 **전부 통과**

### 기각 조건
- ① ~ ④ 중 하나라도 불충족 → **기각**
- 단, **다음 단계로는 계속 진행** (A 기각이어도 B 실행)

### 최종 채택 우선순위 (3단계 모두 완료 후)
1. **1순위**: A/B/C 중 max(최악 케이스) 미회귀 + median 개선 → **채택**
2. **2순위**: 모두 미달 → **기각**, master에 통합 안 함
3. **목표 조기 달성**: 중간에 WER 30% 미만 달성 → 해당 실험 채택, 이후 단계 스킵 가능

---

## 실행 방식

### 옵션 1: 메인 세션에서 수동 트리거
```
1. 이 파일 읽기 (현재)
2. "A 실행해줘" 요청 → Claude가 Exp-081 워크트리/변경/eval 수행
3. 결과 검토
4. "B 실행해줘" 요청
5. 마찬가지로 진행
```

### 옵션 2: 자동 루프 (Agent/Workflow 사용)
- 세 단계를 순차 Agent로 자동 실행
- 각 단계 완료 후 메인 세션에 결과 보고
- 사용자 개입 없이 A → B → C 완성

---

## 보고 형식 (각 단계 완료 후)

```markdown
## Exp-0XY 결과

### 측정 수치 (경로 C, N=3)

| 파일 | R1 | R2 | R3 | median | min | max | stdev |
|------|----|----|----|----|---|----|------|
| sbs1 | | | | | | | |
| ytn1 | | | | | | | |

### 베이스라인 대비

- sbs1 median: XY% → Z% (Δ...)
- sbs1 max: ...
- ytn1: ...
- F1: 유지 / 회귀

### 판정

**채택** / **기각** — 이유: ①~④ 충족 여부

### 다음 단계
B로 이동
```

---

## 주의사항

- **CLAUDE.md 워크트리 규약 준수**: 메인 세션은 main 워크트리, subagent는 절대 경로 지정
- **PHASE2_EXPERIMENTS.md 항상 참조**: Exp-081 시작 전 현재 기록 확인
- **fail-fast 금지**: 첫 회차 나쁘더라도 N=3 전부 측정 (분산이 판단 근거)
- **하드코딩 제한** (CLAUDE.md §3.8): 범용 개선만, 한국어/영어 특화 제외
- **pytest 통과 확인**: `/eval` 전에 또는 후에 `pytest tests/` 실행
