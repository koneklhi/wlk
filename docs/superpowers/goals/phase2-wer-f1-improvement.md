# Phase 2 자율 개선 루프 — WER 감소 우선 → 문장 분리 F1 60%+

> **[2026-06-23 업데이트 / 2026-06-30 측정 정책 갱신]** 측정 세트·우선순위는 **CLAUDE.md §3.8 현행 regime**을 따른다:
> 테스트(채택/기각) = bong1 + ytn2 + sbs1 (화자분할 ON; **평소 스크리닝 `--repeat 1`**, 채택 확정 시 `--repeat 3`), held-out(일반화) = ytn1 + eng1 단회, **ytn2·bong1 공동 최우선**.
> 문장 분리 F1 기준: 정답 빈 줄 = 화자전환 경계(1순위 필수) + 온점분리 경계(2순위 선택). primary F1=화자전환 경계, secondary F1=온점 경계 — metric 구현 후속.
> 아래 Phase A/B 목표·측정 프로토콜 구조는 유지하되, 데이터 세트와 측정 명령은 위 regime 적용.

## 초기 상태 (2026-06-05 — 역사적, Phase 2 착수 시점)

> ⚠️ 아래는 문장 확정 로직 도입 **이전**의 출발 베이스라인이다. Phase 3/4가 머지된 **현재 수치는
> [EXPERIMENTS.md](../../../EXPERIMENTS.md)(활성 로그)의 최신 Exp 항목**을 참조한다.

- 브랜치: `master`
- 기준 베이스라인 (경로 C, 1회 측정):
  - sbs1.mp3: WER **108.3%**, F1 **0.0%**
  - ytn1.mp3: WER **47.9%**, F1 **0.0%**
  - 평균: WER **78.1%**, F1 **0.0%**
- WER 100% 초과 원인: SimulStreaming의 cross-batch 반복 토큰("바 바 바", "도도도도") — 현재 `_filter_repetitions()`는 단일 배치 내에서만 동작해 배치 경계의 반복이 그대로 축적됨
- F1 0.0% 원인: 문장 확정 로직 없음 → 전체가 단일 미확정 블록

---

## 목표 수치 (경로 C 기준, 채택 확정 N≥3회 반복 측정 — 최악 케이스 미회귀 1순위)

| 지표 | 1차 목표 | 상용화 목표 |
|---|---|---|
| 평균 WER | < 50% (단기) | **< 30%** (상용 STT 수준) |
| sbs1 WER | < 60% | < 35% |
| ytn2 WER | < 25% | < 20% |
| bong1 WER | 측정 예정 | < 30% |
| 문장 분리 F1 (avg) | **≥ 60%** | ≥ 70% |

> WER < 30% 근거: 한국어 실시간 STT 상용 서비스(Naver Clova, Kakao i) 기준
> 코드스위칭(한·영 혼용) 및 실시간 조건에서 25-35%가 실용 하한.
> 현 WER 고점의 핵심 원인은 반복 아티팩트(모델 한계 아님)이므로 알고리즘으로 개선 가능.

---

## 핵심 제약 (반드시 준수)

1. **폐쇄망 오프라인**: 런타임 네트워크 호출 절대 금지 (HF Hub, PyPI, GitHub 등)
2. **외과적 변경**: `whisperlivekit/` 본체 수정 최소화. 가능하면 새 모듈로 분리.
3. **한국어/영어 양쪽 커버**: 어느 한 언어만 개선되는 변경은 채택 금지
4. **측정 기준**: 경로 C(VBCable)만 사용. 경로 A(PCM 파일 주입) 폐기.
5. **채택 우선순위**: 1순위 = 최악 케이스(max) 미회귀, 2순위 = median 개선. 최악 케이스가 catastrophic하게 발생하면 median보다 원인 파악·해결을 먼저.

---

## 작업 순서: WER 먼저, F1 다음

### Phase A — WER 개선 (F1보다 먼저)

WER이 높으면 F1 평가 자체가 의미 없다. 반복 토큰이 삽입되면 단어 경계가 무너져 F1 계산도 오염됨.

#### A-1. Cross-batch stateful 반복 필터 (최우선)

**문제**: `whisperlivekit/simul_whisper/simul_whisper.py`의 `_filter_repetitions()`은 단일 `update()` 호출 내부에서만 중복을 제거함. 실시간에서 토큰은 1개씩 도착하므로 배치 경계("바"/다음배치/"바")는 통과됨.

**접근 방향**:
- `whisperlivekit/tokens_alignment.py`의 `TokensAlignment` 클래스 또는 `SimulStreamingOnlineProcessor`에 **상태를 유지하는** 반복 필터를 추가
- 직전 N개 토큰의 텍스트를 메모리에 보유, 새 토큰이 직전 동일 단어의 연속이면 제거
- 한국어는 음절 단위 반복("바 바 바"), 단어 단위 반복("-그 -그 -그") 두 가지를 모두 처리해야 함
- 삭제는 `new_tokens`에서 조용히 수행 — `all_tokens`에 누적되기 전에 필터링

**목표**: sbs1 WER 108% → 60% 이하 (반복 토큰 삽입이 주 원인이므로 50%+ 개선 가능)

#### A-2. Silence 기반 조기 확정 + 반복 억제 (A-1 이후)

**문제**: VAD silence 감지 후에도 이전 음절 반복이 계속 생성됨. silence 확인 즉시 현재 세그먼트를 확정하면 반복 토큰이 쌓일 여지가 줄어듦.

**접근 방향**:
- `whisperlivekit/tokens_alignment.py`의 `get_lines()` 내 `Silence` 토큰 처리 로직 참조
- 긴 silence(≥ 0.5초) 감지 시 `current_line_tokens`를 즉시 `validated_segments`로 이동
- 이를 통해 F1 향상도 함께 달성 가능

#### A-3. 확정 후 중복 억제 (A-2 이후)

- 확정된 `validated_segments`의 마지막 단어와 새로 들어오는 토큰의 첫 단어가 동일하면 제거
- Whisper의 context bleeding 현상 억제

---

### Phase B — 문장 분리 F1 개선 (WER < 50% 달성 후)

#### B-1. Silence 기반 문장 확정 (기본)

**현재 코드**: `tokens_alignment.py get_lines()`는 `Silence` 토큰을 받으면 `current_line_tokens`를 `validated_segments`로 이동함. 문제는 `Silence` 토큰이 얼마나 자주, 어느 조건에서 생성되는지.

**접근 방향**:
- `whisperlivekit/silero_vad_iterator.py`에서 VAD silence 판단 임계값 확인
- silence 지속 시간 임계치 조정 (너무 짧으면 과분할, 너무 길면 미분할)
- `--lan auto` 언어 감지가 VAD와 상호작용하는 방식 확인

#### B-2. 한국어 종결어미 기반 확정 (B-1 이후)

- 한국어 문장 끝 패턴 감지: `-ㅂ니다`, `-습니다`, `-요`, `-거든요`, `-거죠`, `-네요` 등
- 특정 단어 하드코딩 금지 — 규칙 기반(정규표현식) 또는 어미 패턴 리스트
- silence 없이도 문장 종결이 명확하면 확정 가능

#### B-3. 언어 전환 경계 확정 (B-2 이후)

- 한국어 → 영어 또는 영어 → 한국어 전환 시 문장 경계로 처리
- `ASRToken`의 `language` 또는 `detected_language` 속성 활용 (있을 경우)

---

## 측정 프로토콜 (반드시 준수)

### 실행 명령

```powershell
# ① 스크리닝(기본) — 방향 탐색·catastrophic 회귀 감지
uv run python scripts/eval.py \
  --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --output .omc/benchmarks/eval_YYYYMMDD_HHMM_expN.json
# ↑ --repeat 생략 = 1회. 수치는 방향 신호로만 해석한다.

# ② 채택 확정(머지 직전에만) — N≥3회 반복 + median/분산 자동 집계
uv run python scripts/eval.py \
  --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --repeat 3 \
  --output .omc/benchmarks/eval_YYYYMMDD_HHMM_expN.json

# 경로 A 회귀 확인 (코드 변경 후 빠른 스모크용)
uv run python scripts/eval.py \
  --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --paths A
```

### 측정 규칙 — 2계층 (필수)

- **① 스크리닝(평소)**: `--repeat 1`(기본값) — 방향 탐색·catastrophic 회귀 감지. 1회 수치는 방향 신호로만 해석하고 채택/기각 결론의 근거로 쓰지 않는다.
- **② 채택 확정(머지 직전)**: `eval.py --repeat 3 --files test_data/bong1.mp3 test_data/ytn2.mp3 test_data/sbs1.mp3` — **median + 분산(min/max/stdev)**으로 최종 판단.
- **채택 확정 시 fail-fast 금지**: 첫 회차가 나빠도 중단하지 않고 N회 전부 측정한다 (분산이 곧 데이터).
  단, VBCable 미설정·포트 충돌·무음 캡처 등 *하니스 버그*는 즉시 멈추고 고친다(분산이 아니라 결함).
- 회차 격리: eval.py가 파일당 서버 1회 기동 후 N회 세션(/asr 연결마다 전사 상태 새로 생성)으로 자동 처리.

---

## 채택/기각 규칙

**채택 조건** (모두 충족; 채택 확정 3회 측정 기준):
1. 경로 C **median** WER이 이전 베이스라인 대비 감소 (Phase A) 또는 F1이 상승 (Phase B)
2. **최악 케이스(max/p95) 미회귀** — median이 좋아도 catastrophic run이 늘면 기각 (분산 축소가 1급 목표)
3. WER 회귀 ≤ +5%p (F1 개선 중 WER이 악화되지 않아야 함)
4. `pytest tests/` 전부 통과
5. bong1·ytn2·sbs1 중 일부만 개선되고 나머지가 ≥ 5%p 악화 → 기각 (과적합)

**기각 즉시**:
- 어느 한 언어(한국어 or 영어)의 커버리지가 의미 있게 하락
- 반복 아티팩트가 sbs1보다 악화

---

## 실험 기록 규칙

1. 각 실험 완료 후 `EXPERIMENTS.md`에 Exp-N 항목 추가
   - 형식: 가설 → 변경 내용(파일:라인) → 측정 결과(3회 수치 + 중앙값) → 결론
2. 채택 실험은 커밋 후 다음 실험의 베이스라인으로 사용
3. 기각 실험도 기록 (같은 실수 반복 방지)
4. 실험 결과 JSON은 `.omc/benchmarks/eval_YYYYMMDD_HHMM_expN.json`으로 저장

---

## 주요 파일 색인

| 역할 | 경로 |
|---|---|
| 문장 확정 + 토큰 정렬 | `whisperlivekit/tokens_alignment.py` |
| SimulStreaming 핵심 디코더 | `whisperlivekit/simul_whisper/simul_whisper.py` |
| SimulStreaming 온라인 프로세서 | `whisperlivekit/simul_whisper/backend.py` |
| VAD silence 감지 | `whisperlivekit/silero_vad_iterator.py` |
| 타이밍 객체 (ASRToken, Silence) | `whisperlivekit/timed_objects.py` |
| 평가 스크립트 | `scripts/eval.py` |
| VBCable 브라우저 자동화 | `scripts/vbcable_test.py` |
| 실험 로그 | `EXPERIMENTS.md` (활성; Exp-001~130 `PHASE2_EXPERIMENTS.md` 아카이브) |
| 설계 제약 | `CLAUDE.md` |

---

## 루프 진행 방식

```
while avg_WER > 30% or avg_F1 < 60%:
    1. EXPERIMENTS.md 직전 실험 결과 확인
    2. 가설 수립 (위 접근 방향 중 우선순위 순)
    3. 외과적 코드 변경 (최소 범위)
    4. pytest 통과 확인
    5. 경로 C eval.py 실행 (스크리닝 1회; 채택 후보 확정 시 3회) → 중앙값 계산
    6. 채택/기각 판단
    7. EXPERIMENTS.md 기록 + 채택이면 git commit
    8. 다음 루프
```

현재 WER이 목표에 매우 멀리 있으므로, **먼저 A-1(cross-batch 반복 필터)부터 시작**한다.
A-1만으로 sbs1 WER이 60% 이하로 떨어지면 Phase B로 전환 가능.
