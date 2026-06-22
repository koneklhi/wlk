# Exp-088 — 한·영 스크립트 전환 경계 Goal Prompt

## 목표

**한·영 코드 스위칭 데이터(ytn1, ytn2)에서 F1 ≥ 0.80** 달성.

- ytn1 F1 median ≥ 0.80, **worst ≥ 0.75** (현재 worst 0.571 → 개선)
- ytn2 F1 median ≥ 0.80 (held-out 검증)
- sbs1 F1 회귀 없음 (≥ 0.762), eng1 false split 0건 유지

---

## 입력 (현재 상태)

**베이스라인 (Exp-087)** — 경로 C N=3, `.omc/benchmarks/eval_fix2_partialskip_3.json`:

| 파일 | WER median | WER max | F1 median | F1 worst |
|------|-----------|---------|-----------|---------|
| sbs1 | 17.9% | 17.9% | 0.762 | 0.762 |
| ytn1 | 23.3% | 44.8% | 0.80 | 0.571 |

ytn2 베이스라인 없음 (이번 실험에서 처음 측정).

**핵심 문제**: ytn1 정답 경계 8개 전부가 한↔영 스위칭 지점인데, 현재 경계 트리거는 무음(≥0.4s)뿐.
최악 회차에서 스위칭 지점에 중복 재전사가 발생해 WER 44.8%, F1 0.571 폭락.

---

## 전략 — Exp-088 (스크립트 전환 경계)

emit된 토큰 텍스트의 문자 체계(한글/라틴)를 실시간 분류해, 지속적 전환(N≥2 토큰 AND ≥4 글자)
감지 시 line 경계를 소급 주입하고 직전 문장을 확정(validated_segments)한다.

- 신규 모듈: `whisperlivekit/script_switch.py` (~80줄)
- glue: `whisperlivekit/tokens_alignment.py` `get_lines()` 비-diar 분기 (+~15줄)
- 진단 계측: `scripts/eval.py` + `whisperlivekit/metrics.py` 소폭 수정
- 테스트: `tests/test_script_switch_boundary.py` (신규, TDD 선작성)

상세 설계 → `C:\Users\A040-000-0001\.claude\plans\roadmap-md-phase-2-lucky-valiant.md`

---

## 워크트리 규약 (필수)

- **브랜치/워크트리**: `phase2/exp-088-script-switch-boundary`
- **메인 세션은 main 워크트리에 머문다.** subagent만 워크트리 절대 경로에서 작업.
- 워크트리 생성 후 모든 코드 편집·pytest·eval은 **워크트리 절대 경로에서** 수행.
- 측정 전 반드시 import 경로 검증: `python -c "import whisperlivekit; print(whisperlivekit.__file__)"`
  → 워크트리 경로가 나와야 함 (editable 설치 함정).

---

## 실행 단계

### Step 0 — 진단 계측 + 베이스라인 재측정

워크트리에서 아래 두 파일 소폭 수정:

1. **`scripts/eval.py`**
   - `FileResult` dataclass (L42–53): `hyp_lines: Optional[list] = None` 필드 추가
   - `_build_result()` (L161–172): `hyp_lines=hyp_sentences` 전달 (~3줄)
   - JSON 직렬화는 기존 `asdict` 처리

2. **`whisperlivekit/metrics.py`** `compute_segmentation()` (L145–204)
   - 내부 계산값(`ref_bounds`, `projected`, `used`)을 `boundary_detail` 키로 반환 딕셔너리에 추가 (~10줄)
   - 기존 반환 키 불변 — 기존 테스트 회귀 없음

3. **베이스라인 재측정**: `python scripts/eval.py --repeat 3 test_data/sbs1.mp3 test_data/ytn1.mp3`
   → JSON 저장 후 `hyp_lines`로 ytn1 8개 스위칭 지점별 실패 모드 분류:
   - ① 병합(무경계) ② 위치 오차 ③ 중복 재전사 동반 ④ 영어→한글 음차 오전사
   - ④번이 관측되면 결과 보고에 포함 (Candidate B 필요성 판단 데이터)

### Step 1 — 테스트 선작성

`tests/test_script_switch_boundary.py` 신규 작성 (~180줄).
패턴 참고: `tests/test_cross_batch_filter.py` (모델 무관 토큰 주입 방식).
`get_lines()` 호출 시 `audio_time` 인자 필수.

필수 케이스:
- ko-only 연속 → split 0
- en-only 연속 → split 0
- ko→en→ko 교차 → 경계 2개
- 문장 내 라틴 1토큰 "SCM" → split 0 (hysteresis)
- 라틴 2토큰 "Thank you" 후 복귀 → 독립 라인 생성
- 숫자·구두점 끼임 → run 미단절 (중립 토큰)
- Silence + 전환 같은 배치 → 빈 세그먼트 없음
- Silence 먼저 → 이중 경계 없음
- 1글자 노이즈 → split 0 (MIN_CHARS)
- 소급 분리 (1차 호출 1라인 → 2차 호출 2라인)
- `classify_script` 단위 케이스 (한글 완성자, 자모, 라틴, 숫자, 혼합)

### Step 2 — 구현

1. **신규 파일**: `whisperlivekit/script_switch.py` (~80줄)
   ```python
   SWITCH_MIN_TOKENS = 2
   SWITCH_MIN_CHARS = 4

   def classify_script(text: str) -> str:
       # 'hangul' | 'latin' | 'neutral'
       # 한글 우선: 한글 글자 있으면 'hangul', 아니면 A-Za-z 있으면 'latin', 아니면 'neutral'

   class ScriptSwitchDetector:
       def reset(self) -> None: ...
       def feed(self, text: str) -> Optional[int]:
           # 전환 확정 시 run 길이(≥1) 반환, 아니면 None
           # 반환값 = current_line_tokens에서 잘라낼 후미 토큰 수
   ```

2. **glue** `whisperlivekit/tokens_alignment.py` `get_lines()` 비-diar 분기 (+~15줄)
   - `__init__`: `self._script_detector = ScriptSwitchDetector()` 추가
   - Silence 분기 (L240–242): flush 후 `self._script_detector.reset()` 호출
   - else 분기 (L252–253): `self.current_line_tokens.append(token)` 뒤
     ```python
     run_len = self._script_detector.feed(token.text)
     if run_len and 0 < run_len < len(self.current_line_tokens):
         split_idx = len(self.current_line_tokens) - run_len
         self.validated_segments.append(
             Segment.from_tokens(self.current_line_tokens[:split_idx])
         )
         self.current_line_tokens = self.current_line_tokens[split_idx:]
     ```

3. **pytest** `tests/` 전부 통과 확인 후 다음 단계.

### Step 3 — 경로 C 측정 (N=3)

**fail-fast 금지** — 첫 회차가 나빠도 N=3 전부 측정.
하니스 버그(VBCable 미설정, 포트 충돌, 무음 캡처)는 즉시 중단·수정 후 재시작.

```
python scripts/eval.py --repeat 3 \
    test_data/sbs1.mp3 test_data/ytn1.mp3 test_data/eng1.mp3
```

eng1은 영어 단일 발화 false split 감시용 — **분리 발생 0건이어야 함**.

**채택 후보 조건** (모두 충족):
1. ytn1 F1 median ≥ 0.80, **worst ≥ 0.75** ← 핵심 목표
2. sbs1 F1 ≥ 0.762 (회귀 없음)
3. WER max 회귀 ≤ +5%p (1순위: 최악 케이스 미회귀)
4. pytest 전부 통과
5. eng1 false split 0건

**기각 판정** (하나라도): ytn1 worst < 0.70, sbs1 F1 하락, WER max +5%p 초과, eng1 false split 발생.

### Step 4 — ytn2 held-out 검증 (채택 후보 통과 시)

ytn2.txt 포맷 확인 (빈 줄 블록 ✓, 10블록 en/ko 교차 9 경계).

```
python scripts/eval.py --repeat 1 test_data/ytn2.mp3
```

**ytn2 목표**: F1 ≥ 0.80 — ytn1 과적합 점검.
- 통과 → 채택 확정
- 미달 → 결과·원인과 함께 보고 후 사용자 판단

### Step 5 — 기록·보고

`/log-experiment` 슬래시 커맨드로 `PHASE2_EXPERIMENTS.md`에 Exp-088 기록.
실패해도 기록 (기각 이유 포함).

**최종 보고 후 사용자가 채택/기각 결정** → 채택 시 master 통합.

---

## 채택 기준 요약

| 지표 | 기준 | 베이스라인 |
|------|------|-----------|
| ytn1 F1 median | ≥ 0.80 | 0.80 |
| ytn1 F1 worst | **≥ 0.75** | **0.571** |
| ytn2 F1 median | ≥ 0.80 | 미측정 |
| sbs1 F1 | ≥ 0.762 | 0.762 |
| WER max 회귀 | ≤ +5%p | — |
| eng1 false split | 0건 | — |
| pytest | 전부 통과 | — |

**1순위: worst-case 미회귀 + ytn2 ≥ 0.80 달성.**
median만 좋고 worst가 catastrophic하면 기각.

---

## 보고 형식

각 Step 완료 후 아래 형식으로 보고:

```markdown
## Exp-088 Step N 결과

### 측정 수치 (경로 C, N=3)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | R1 F1 | R2 F1 | R3 F1 | median | worst |
|------|--------|--------|--------|--------|-----|-------|-------|-------|--------|-------|
| sbs1 | | | | | | | | | | |
| ytn1 | | | | | | | | | | |
| eng1 | false splits: 0/N | | | | | | | | | |

### 베이스라인 대비

- ytn1 F1 worst: 0.571 → __ (목표 ≥ 0.75)
- ytn1 WER max: 44.8% → __
- sbs1 F1: 0.762 → __ (회귀 여부)

### ytn1 스위칭 8지점 회수 현황

| 경계 | 언어 방향 | 베이스 실패 모드 | Exp-088 상태 |
|------|----------|----------------|-------------|
| 1 | KO→EN | | |
| ... | | | |

### 판정

**채택 후보** / **기각** — 이유: 조건 ①~⑤ 충족 여부

### 다음 단계

Step N+1 / ytn2 검증 / 기록·보고
```

---

## 주의사항

- **CLAUDE.md 워크트리 규약**: 메인 세션 cwd = main, subagent = 워크트리 절대 경로
- **import 경로 검증 먼저** — `python -c "import whisperlivekit; print(whisperlivekit.__file__)"` 로 워크트리 경로 확인
- **fail-fast 금지**: 첫 회차 나쁘더라도 N=3 전부 측정 (분산이 데이터)
- **하드코딩 제한** (CLAUDE.md §3.8): 모듈 상수(`SWITCH_MIN_TOKENS`, `SWITCH_MIN_CHARS`)는 CLI 노출 및 데이터 튜닝 금지
- **diarization 분기 불변**: `get_lines_diarization()` 경로는 수정하지 않음
- **빈 세그먼트 방지**: `split_idx`가 0 또는 `len(current_line_tokens)`이면 분리 스킵
- **Step 0 ④ 관측 시**: "영어→한글 음차 오전사"가 많으면 별도 보고 (Candidate B 논의 트리거)
