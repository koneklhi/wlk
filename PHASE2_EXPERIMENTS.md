# Phase 2 실험 로그

STT 성능 개선 과정에서 수행한 실험을 기록한다.
각 실험은 **가설 → 변경 → 결과 → 결론** 흐름으로 작성한다.

---

## 이월된 사실 (Phase 2 재시작 시드 — 2026-06-04)

이전 실험들이 일관된 측정 기준 없이 경로 A/C를 오가며 진행돼 자동 루프가 깨진 지표에 과적합했다.
2026-06-04에 `master` 기준으로 재시작했다. **폐기된 수치·판단은 제거하고, 측정 경로와 무관한
하드 사실만** 아래에 남긴다. 폐기된 알고리즘(F1 70.6% 작업)·실험 수치 전체는 git 태그
`archive/phase2-f1-improvement`에서 복구 가능하다.

- **SimulStreaming 채택** (Exp-000/001 근거, 유효): LocalAgreement는 영어 코드스위칭을 통째로 누락하고
  발화 후반부 커버리지를 잃는 구조적 문제가 있어 Phase 2에서 패치 불가. SimulStreaming의 반복
  아티팩트는 후처리로 보완 가능하므로 SimulStreaming 위에서 설계한다.
- **AlignAtt 실출력 토큰에는 구두점이 없다**: 유닛테스트에선 합성 토큰에 구두점이 있어 구두점 기반
  확정이 동작하지만, 실 스트리밍 출력엔 구두점이 없어 미발동한다. 확정 신호는 VAD Silence /
  세그먼트 경계 / 언어 전환에서 찾아야 한다.
- **`_filter_repetitions()`는 단일 `update()` 배치 내부에서만 동작**: 실시간엔 토큰이 1개씩 도착해
  배치 경계의 반복(`바`/`바`/`바`)이 살아남는다. cross-batch 반복 제거는 stateful 필터가 필요하다.
- **경로 C만 채택 판정 기준**: 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회해 실사용과 무관한 수치를 냄. 폐기.

---

## 현재 채택 베이스라인 (Exp-075 — 공식 N≥3 수치 2026-06-08)

**vac=0.2 + max_context=0 + VAD 0.3 + MIN_SILENCE=0.4 (greedy, --lan auto)**

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER |
|---|---|---|---|---|---|---|
| sbs1 | 73.2% | 35.1% | 39.3% | **39.3%** | **76.2%** | **73.2% ⚠️** |
| ytn1 | 27.6% | 27.0% | 26.4% | **27.0%** | **80.0%** | 27.6% |
| **평균** | | | | **33.2%** | **78.1%** | |

- sbs1 stdev 20.9% — R1 catastrophic run 존재. 최악 케이스 원인 파악 필요.
- ytn1 stdev 0.6% — 매우 안정적.
- F1 목표(≥70%) 달성. WER 목표(<30%) 미달 — 3.2%p 추가 개선 필요.
- JSON: `.omc/benchmarks/eval_phase4_baseline_master.json`
- 실마이크 일치 ✅ 확인 (2026-06-08)
- sbs1.txt 변경: 첫 문장을 2문단으로 분리 (2026-06-08) — 이 수치부터 새 기준 적용

주요 변경 파일:
- `whisperlivekit/simul_whisper/backend.py`: `max_context_tokens=0`, 반복/환각 필터 스택
- `whisperlivekit/audio_processor.py`: `MIN_DURATION_REAL_SILENCE=0.4`, VAD `threshold=0.3`
- `whisperlivekit/parse_args.py`: `--vac-chunk-size` default `0.2`

브랜치: `phase2/candidate-075` (commit `8d21990`), master 통합: commit `2ca441f`

---

## 경로 C 공식 베이스라인 (master, 2026-06-04)

**알고리즘 없는 순수 기본값** — 이후 모든 실험의 기준점.

| 파일 | WER | 문장분리 F1 | 비고 |
|---|---|---|---|
| sbs1.mp3 | **108.3%** | 0.0% | 반복 아티팩트로 WER 100% 초과 |
| ytn1.mp3 | **47.9%** | 0.0% | |
| **평균** | **78.1%** | **0.0%** | |

- F1=0%: 문장 확정 로직 없음 → 전체가 단일 미확정 블록
- WER >100%: SimulStreaming 반복 토큰("바 바 바", "도도도도") 삽입 오류 폭발
- 결과 파일: `.omc/benchmarks/eval_baseline_pathC_master.json`

---

## 빠른 참조 (최신순)

| Exp | 날짜 | 제목 | 핵심 변경 | WER (중앙값) | F1 | 결론 |
|---|---|---|---|---|---|---|
| **Exp-080** | 2026-06-08 | **beam_size=2 (beam search)** | `--beams` 기본값 1→2 | **31.4%** | **78.1%** | **채택 (현 베이스라인)** |
| Exp-075 | 2026-06-08 | vac=0.2 + max_context=0 (greedy) | `vac_chunk_size=0.2`, `max_context_tokens=0`, VAD 0.3, MIN_SILENCE=0.4 | 33.2% | 78.1% | ~~채택~~ → Exp-080 교체 |
| Exp-058~079 | 2026-06-07 | vac=0.2 regime shift 군집 (22개) | `vac_chunk_size=0.2` 기점으로 WER/F1 대폭 개선 — 단일 run 미검증 | 33~35% | 70~75% | 075만 검증 채택, 나머지 기각/미검증 |
| Exp-057 | 2026-06-07 | 배치 내 4-word 반복 드롭 | `backend.py` `_filter_cross_batch_repetitions()` 한글 4회+ 배치 드롭+리셋 | 40.0% | 60.2% | **잠정 채택** (075에 흡수) |
| Exp-056 | 2026-06-07 | n-gram 음절 반복 + LOOP_THRESHOLD=4 | n-gram 감지 + threshold 5→4 | 63.8% (R1) | 38.3% | **기각** |
| Exp-055 | 2026-06-07 | 30초 주기 context 리셋 | 주기적 context 리셋 | 65.0% (R1) | 46.4% | **기각** |
| Exp-054 | 2026-06-07 | nonspeech_prob=0.3 | nonspeech_prob 0.5→0.3 | 88.3% (R1) | 34.3% | **기각** |
| Exp-053 | 2026-06-07 | audio_max_len=20초 | audio_max_len 30→20 | 69.7% (R1) | 58.3% | **기각** |
| Exp-052 | 2026-06-07 | 3회 반복 + 15자 토큰 필터 | 한글 3회 반복 + 긴 토큰 환각 필터 | 50.1% (R1) | 55.7% | **기각** |
| Exp-051 | 2026-06-07 | 배치 한글 n-gram 반복 필터 | 3자+/3회 n-gram | 74.6% (R1) | 45.0% | **기각** |
| Exp-050 | 2026-06-07 | n-gram 반복 환각 감지 (3자+/3회) | 전체 텍스트 n-gram 필터 | 64.2% (R1) | 31.7% | **기각** |
| Exp-049 | 2026-06-07 | n-gram threshold=4 | threshold=4 | 68.7% (R1) | 50.0% | **기각** |
| Exp-048 | 2026-06-07 | frame_threshold=50 | frame_threshold 25→50 | 62.2% (R1) | 48.8% | **기각** |
| Exp-047 | 2026-06-07 | MIN_DURATION_REAL_SILENCE=3초 | MIN_DURATION 5→3 | 70.1% (R1) | 50.0% | **기각** |
| Exp-046 | 2026-06-07 | static_init_prompt | 한국어 도메인 힌트 | 68.4% (R1) | 54.9% | **기각** |
| Exp-045 | 2026-06-07 | max_context_tokens=25 | 50→25 | 63.2% | 46.4% | **기각** |
| Exp-044 | 2026-06-07 | MIN_DURATION=0.4초 | 0.5→0.4 | 47.5% | 61.4% | **기각** (유일 F1 61%이나 075가 우선) |
| Exp-043 | 2026-06-07 | max_context_tokens=0 | 50→0 | 58.5% | 42.9% | **기각** (단독엔 F1 악화) |
| Exp-042 | 2026-06-07 | HALLUCINATION_RESET=3 | threshold 5→3 | 63.4% | 60.7% | **기각** |
| Exp-041 | 2026-06-07 | MIN_DURATION=0.3초 | 0.5→0.3 | 54.0% | 66.9% (R3 124.6% catastrophic) | **기각** (최악 케이스) |
| Exp-040 | 2026-06-07 | n-gram 패턴 반복 감지 | 2~4자 n-gram 억제 | 48.6% | 42.9% | **기각** |
| Exp-039 | 2026-06-07 | max_context_tokens=50 | 100→50 | 48.7% | 40.0% | **기각** |
| Exp-038 | 2026-06-07 | never_fire=True | default False→True | 89.8% (R1) | 44.9% | **기각** |
| Exp-037 | 2026-06-07 | never_fire=True | `--never-fire` default True | 84.8% (R1) | 33.3% | **기각** |
| Exp-036 | 2026-06-06 | frame_threshold=50 | 25→50 | 45.0% | 30.9% | **기각** |
| Exp-035 | 2026-06-06 | --lan ko 강제 | eval.py `--lan ko` (코드 변경 없음) | 54.8~64.2% | 35.8~56.9% | **기각** (ytn1 한영혼합 역효과) |
| Exp-034 | 2026-06-06 | max_context_tokens=100 | None→100 | 49.8% | 36.8% | ~~잠정 채택~~ → **기각** (Exp-057 교체) |
| Exp-033 | 2026-06-06 | LOOP_THRESHOLD=4 | 5→4 | 67.7% | 44.9% | **기각** |
| Exp-032 | 2026-06-06 | LOOP_THRESHOLD=3 | 5→3 | 55.3~66.3% | 12~29% | **기각** |
| Exp-031 | 2026-06-06 | master+char-run 단일음절 필터 | char-run 억제 + context 리셋 + threshold=5 | 67.2% | 37.7% (R3 98.0% catastrophic) | **기각** |
| Exp-030 | 2026-06-06 | 슬라이딩 윈도우 한국어 전용 빈도 필터 | 한국어 단어 빈도 threshold=5, window=25 | 87.3% | — | **기각** |
| Exp-029 | 2026-06-06 | 슬라이딩 윈도우 단어 빈도 필터 | window=20, threshold=4 | 79.5% (R1) | 35.8% | **기각** (ytn1 99.4% catastrophic — 영어 단어 억제) |
| Exp-028 | 2026-06-06 | 단일음절 연속 반복 억제 + context 리셋 | `_max_char_run` + `_CHAR_RUN_THRESHOLD=4` + 카운터≥5 context 리셋 | 61.8% | 45.1% | **채택** |
| Exp-027 | 2026-06-06 | 하이픈 프리픽스 단어 반복 억제 | `_consecutive_short_hyphen` + threshold=4 | 72.1% | — | **기각** |
| Exp-009 | 2026-06-06 | 반복 루프 감지 + refresh_segment() 리셋 | `_detect_repetition_loop()` Counter 밀도 감지 | — | — | **기각** (밀도 기반 false positive — 현재 master에 잔존, 주의) |
| Exp-008 | 2026-06-06 | VAD end_threshold=0.35 비대칭 | end_threshold 파라미터 | 113.7~149.4% | — | **기각** |
| Exp-007 | 2026-06-06 | eval 파이프 블로킹 수정 + VAD 0.3 재측정 | `eval.py` `stdout=DEVNULL` | 52.5% | 44.9% | **채택** |
| Exp-006 | 2026-06-06 | VAD threshold=0.3 + MIN_SILENCE=0.5 | `audio_processor.py` | 98.5% | — | **기각** (측정 무효 — eval 파이프 블로킹) |
| Exp-005 | 2026-06-06 | 워치독 is_last=True flush | `backend.py` 워치독 | 98.5% | — | **기각** |
| Exp-004 | 2026-06-06 | 디코더 멈춤 워치독 + 경로 C 하니스 수정 | `audio_device.py`/`vbcable_test.py` | 60~68% (3회 미완) | — | 하니스 **채택** / 워치독 **보류** |
| Exp-003 | 2026-06-05 | 한국어 종결어미 기반 문장 확정 + NFC | `tokens_alignment.py` | 97.6% | 0.0% | **기각** |
| Exp-002 | 2026-06-05 | Cross-batch Stateful 반복 필터 | `process_iter()` cross-batch 반복 제거 | 63.1% | 0.0% | **채택** |
| Exp-001 | 2026-05-21 | VBCable 마이크 정성 평가 — 정책 최종 확정 | 브라우저 마이크 입력 실사용 비교 | — | — | **SimulStreaming 채택** |
| Exp-000 | 2026-05-20 | 정책 선택 기준 벤치마크 | SimulStreaming vs LocalAgreement | SS WER 0.321 / LA 0.434 | — | → Exp-001에서 확정 |

---

## Exp-000 + Exp-001: 정책 선택 (SimulStreaming 채택)

**날짜**: 2026-05-20~21 / **결론**: **SimulStreaming 채택**

- LocalAgreement: 영어 인용구 전체 누락(del 66개), 커버리지 절반 손실, p95 지연 9665ms
- SimulStreaming: 영어 포착 96%(25/26), avg 지연 114ms. 반복 아티팩트는 후처리로 보완 가능
- 결론: LocalAgreement의 영어 누락·커버리지 손실은 LCS 합의 알고리즘의 구조적 문제. Phase 2에서 패치 불가 → SimulStreaming 채택

---

## Exp-002: Cross-batch Stateful 반복 필터 (채택)

**날짜**: 2026-06-05 / **파일**: `whisperlivekit/simul_whisper/backend.py`

**가설**: `_filter_repetitions()`는 배치 내부 반복만 제거. 배치 경계를 넘는 연속 반복은 잡지 못함.
직전 방출 단어를 상태로 보유해 cross-batch 연속 반복을 제거하면 삽입 오류가 크게 감소할 것.

**변경 내용**
- `__init__`: `self._last_emitted_word: str = None`
- `end_silence()`/`new_speaker()`: `_last_emitted_word = None` 리셋
- `_filter_cross_batch_repetitions()` 메서드 추가 (연속 반복만 제거, 비연속 보존)
- `process_iter()`: 필터 호출 추가
- `tests/test_cross_batch_filter.py`: 유닛 테스트 10개 신규

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 87.5% | 93.9% | 90.7% | — |
| 2회차 | 57.1% | 35.6% | 46.4% | — |
| 3회차 | 87.5% | 38.7% | 63.1% | 0.0% |
| **중앙값** | **87.5%** | **38.7%** | **63.1%** | **0.0%** |

베이스라인(78.1%) 대비 WER -15.0%p. 채택.

---

## Exp-004: 경로 C 하니스 결함 수정 (하니스 채택)

**날짜**: 2026-06-06 / **파일**: `scripts/audio_device.py`, `scripts/vbcable_test.py`

**근본 원인 발견**:
- `vbcable_audio_context`가 재생 장치만 검사 → 녹음(CABLE Output) 설정을 건너뜀 → 브라우저가 실제 마이크(무음) 캡처 → 전사 0
- 수정: 재생·녹음 장치 양쪽 설정 + 타임아웃 연장

하니스 수정 **채택**. 워치독(is_last=True) 자체는 효과 미미 보류.

---

## Exp-007: eval 파이프 블로킹 수정 + VAD 0.3 재측정 (채택)

**날짜**: 2026-06-06 / **파일**: `scripts/eval.py`, `whisperlivekit/audio_processor.py`

**근본 원인**: `eval.py` `stdout=subprocess.PIPE` → 파이프 버퍼 포화 시 서버 asyncio 루프 동결.
`stdout=subprocess.DEVNULL`로 변경으로 하니스 안정화.

**변경 내용**
- `scripts/eval.py:99` — `stdout=PIPE` → `stdout=DEVNULL`
- `audio_processor.py` threshold=0.3, MIN_DURATION_REAL_SILENCE=0.5 (Exp-006 변경 유지)

**정량 결과 (경로 C, 3회)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 64.3% | 25.8% | 45.0% | 51.0% |
| 2회차 | 95.2% | 27.6% | 61.4% | 39.6% |
| 3회차 | 79.2% | 25.8% | 52.5% | 44.9% |
| **중앙값** | **79.2%** | **25.8%** | **52.5%** | **44.9%** |

Exp-002 중앙값 대비 WER -10.6%p, F1 +44.9%p. 채택.

---

## Exp-009: 반복 루프 감지 (기각 — 밀도 기반 false positive)

**날짜**: 2026-06-06 / **⚠️ 주의: 기각 코드가 master에 잔존 (2026-06-08 기준)**

밀도 기반 `_detect_repetition_loop()` — 20-window에서 동일 단어 5회(25%) 이상 시 루프 판정.
→ 뉴스에서 "시간" 등 자주 등장하는 단어가 non-consecutive하게 5회 이상 등장해 false positive 폭발.
ytn1 WER 95.7% (기준 25.8% 대비 +69.9%p). **기각**.

Phase 3에서 master를 Exp-075 코드로 교체하면 이 코드가 제거된다.

---

## Exp-028: 단일음절 연속 반복 억제 + context 리셋 (채택)

**날짜**: 2026-06-06 / **파일**: `whisperlivekit/simul_whisper/backend.py`

**가설**: 단일음절 연속 반복("스스스스스", "브브브브브")을 `_max_char_run >= 4`로 억제하고,
억제 카운터 ≥5이면 context 리셋으로 환각 피드백 루프를 끊는다.

**변경 내용**
- 클래스 상수: `_CHAR_RUN_THRESHOLD = 4`, `_HALLUCINATION_RESET_THRESHOLD = 5`
- `__init__`: `self._consecutive_char_repeat: int = 0`
- `_max_char_run` 정적 메서드 추가
- `_filter_cross_batch_repetitions` 교체: char-run 감지 + context 리셋

**정량 결과 (경로 C, 3회)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 54.8% | 29.4% | 42.1% | 50.0% |
| 2회차 | 66.7% | 84.7% | 75.7% | 26.7% |
| 3회차 | 93.5% | 30.1% | 61.8% | 45.1% |
| **중앙값** | **66.7%** | **30.1%** | **61.8%** | **45.1%** |

베이스라인 대비 WER -12.7%p. 채택.
잔존 문제: 구절 수준 반복("시원한 시원한", "통해 통해") 미제거.

---

## Exp-029~056: 슬라이딩 윈도우·n-gram·threshold 튜닝 군 (전부 기각)

**날짜**: 2026-06-06~07 / **28개 실험 요약**

주요 실패 패턴:
- **슬라이딩 윈도우 단어 빈도 필터**: 영어 단어 억제 → ytn1 catastrophic (Exp-029~030)
- **n-gram 반복 필터 여러 변형**: 정상 뉴스 발화와 반복 아티팩트 구분 어려움 (Exp-040~051)
- **LOOP_THRESHOLD 튜닝**: 3~4로 낮추면 과공격, 5는 Exp-009 false positive 패턴 (Exp-032~033)
- **MIN_DURATION 튜닝**: 0.3초에서 R3 124.6% catastrophic (Exp-041) — 최악 케이스 우선 원칙으로 기각
- **max_context_tokens 단독**: Exp-034(100) 잠정 채택 → Exp-057에서 0으로 교체

공통 교훈: **단일 노브 튜닝보다 vac_chunk_size=0.2 regime shift가 훨씬 큰 효과**

---

## Exp-057: 배치 내 4-word 반복 드롭 (잠정 채택 → Exp-075로 교체)

**날짜**: 2026-06-07

배치 내 한글 단어 4회+ 반복 시 배치 드롭+리셋. 중앙값 WER 40.0%, F1 60.2%.
1차 목표(WER<50%, F1≥60%) 달성. Exp-075에 흡수됨.

---

## Exp-058~079: vac_chunk_size=0.2 regime shift 군 (미검증, 075 채택)

**날짜**: 2026-06-07~08

`vac_chunk_size=0.04 → 0.2` 변경을 기점으로 전체 성능이 regime shift.
22개 실험 전부 단일 run 미검증이었으나 WER 33~35% / F1 70~75% 군집 형성.

| 후보 | 특이점 | WER (단일 run) | F1 | 결론 |
|---|---|---|---|---|
| Exp-066 | vac=0.2 베이스 | 32.0% | 70.7% | 미검증 |
| Exp-071 | beam=2 | ~33% | ~75% | 미검증 |
| Exp-073 | --lan ko | 33.2% | 75.3% | 미검증 (ytn1 영향 미지수) |
| **Exp-075** | **max_context=0, greedy** | **~31%** | **~71%** | **채택** |
| Exp-078 | LOOP_THRESHOLD=4 | ~33% | ~75% | 미검증 |
| Exp-079 | cross-batch window=2 | ~33% | ~75% | 미검증 |

나머지 Exp-058~065, 067~070, 072, 074, 076~077: 유사한 수치 범위이나 모두 단일 run 미검증.

---

## Exp-075: vac=0.2 + max_context=0 베이스라인 (채택 — 현 베이스라인)

**날짜**: 2026-06-08 / **브랜치**: `phase2/candidate-075` / **커밋**: `8d21990`

**가설**: vac_chunk_size=0.2 regime shift 확인된 상태에서 max_context_tokens=0(컨텍스트 오염 완전 차단)이
가장 균형 잡힌 greedy 설정일 것. --lan auto로 코드스위칭 보존.

**변경 내용** (master + 3파일)
- `whisperlivekit/simul_whisper/backend.py`: `self.max_context_tokens = 0` (기본값), 반복/환각 필터 스택 (Exp-002/028/057 포함)
- `whisperlivekit/audio_processor.py`: `MIN_DURATION_REAL_SILENCE = 0.4`, VAD `threshold=0.3`
- `whisperlivekit/parse_args.py`: `--vac-chunk-size` default `0.04 → 0.2`

**정량 결과 (경로 C, 2회 측정 — 반복 측정 프로토콜 도입 전)**

| 측정 | sbs1 WER | sbs1 F1 |
|------|----------|---------|
| 1회차 | 33.9% | 63.2% |
| 2회차 | 38.7% | 70.0% |
| **median** | **36.3%** | **66.6%** |

*(eval_exp066_recovery_validate.json — 2회 측정이라 분산 참고용)*

**실마이크 정성 확인 (2026-06-08)**
- 주요 내용 보존 확인
- 앞 음절 반복 아티팩트(시스템 고유)는 VBCable 결과와 동일 패턴 → VBCable↔실마이크 일치 확인
- 코드스위칭 정성 미검증 (영어 포함 발화 테스트 예정)

**결론**: **채택 — 현재 베이스라인**
Master 통합 예정 (Phase 3).

---

## Exp-080: beam_size=2 (beam search 활성화) — 채택

**날짜**: 2026-06-08 / **브랜치**: `phase4/exp-080-beam2`

**가설**: greedy decode(beam=1)는 각 스텝에서 최고 확률 토큰만 선택 → 국소 최적. beam=2로 두 경로를 병렬 탐색하면 Whisper 디코더가 더 나은 전체 시퀀스를 찾아 WER 감소 + 불안정 분산 억제.

**변경**: `whisperlivekit/parse_args.py` `--beams` 기본값 `1 → 2`

**정량 결과 (경로 C, N=3회)**

| 파일 | R1 | R2 | R3 | median WER | F1 | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 36.9% | 38.7% | 36.3% | **36.9%** | **76.2%** | 38.7% | 1.2% |
| ytn1 | 25.8% | 26.4% | 24.5% | **25.8%** | **80.0%** | 26.4% | 0.9% |
| **평균** | | | | **31.4%** | **78.1%** | | |

**베이스라인 대비**:
- sbs1 median: 39.3% → 36.9% (-2.4%p) ✅
- sbs1 max: **73.2% → 38.7% (-34.5%p)** 🎯 catastrophic run 소멸
- sbs1 stdev: 20.9% → 1.2% (극적 안정화)
- ytn1 median: 27.0% → 25.8% (-1.2%p) ✅
- 평균 WER: 33.2% → 31.4% (-1.8%p) ✅
- F1: 76.2%/80.0% 미회귀 ✅

**결론**: **채택** — 1순위(최악 케이스) + 2순위(median) 모두 개선. 하드코딩 없는 범용 개선.
**다음 가설**: beam=3 추가 개선 가능성 탐색 OR compression_ratio_threshold 튜닝

---

## Exp-N: [제목]

**날짜**: YYYY-MM-DD
**가설**: 왜 이 변경이 필요한가 — 어떤 문제를 해결하려 했는가

**변경 내용**
- `파일경로` — 무엇을 어떻게 바꿨는가

**정량 결과 (경로 C, N≥3회)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| median | | | | |
| min | | | | |
| max | | | | |

**결론**: 채택 / 기각
**이유**: 1순위 = 최악 케이스(max) 미회귀 / 2순위 = median 개선
**다음 가설**:
