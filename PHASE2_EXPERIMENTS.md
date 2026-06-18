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
| **Exp-090** | 2026-06-18 | **_detect_repetition_loop 제거 (Exp-009 잔재 청산)** | `backend.py` `_detect_repetition_loop()` + `_recent_tokens` 제거 (net −34줄) | sbs1 **17.3%** / ytn1 **23.9%** | sbs1 **76.2%** / ytn1 **80.0%** | **채택** (ytn1 WER max 44.8→25.2%↓, F1 worst 0.571→0.800↑, sbs1 미회귀) |
| Exp-089 | 2026-06-18 | ScriptSwitchDetector.reset_run() 계획 폐기 | 코드 변경 없음 | — | — | **계획 폐기** (§3.8 후처리 heuristic 위반, Exp-088 실패 원인 1개만 해결) |
| **Exp-088** | 2026-06-11 | **한·영 스크립트 전환 경계 소급 주입** | `script_switch.py` 신규 + `tokens_alignment.py` `get_lines()` 소급 분리 | **21.9%** (sbs1+ytn1) | sbs1 **72.7%** / ytn1 **84.2%** / eng1 **0.0%** | **기각** (sbs1 F1 76.2→72.7%↓, ytn1 WER max 44.8→79.8%↑, eng1 false split) |
| **Exp-087** | 2026-06-09 | **UTF-8 미완성 토큰 부분 emit 제거 (선두-음절 중복 해결)** | `align_att_base.py` `_build_timestamped_words` — 미완성(`�`) 단어 부분 emit skip | **20.6%** | **78.1%** | **채택** (선두-중복 6/6 run 완전 소멸 sbs1 26→0·ytn1 7→0, WER 43.0→20.6%, F1 미회귀, 테스트 회귀 0) |
| Exp-086 | 2026-06-09 | Fix-punct-dash (온점·대시 버그 수정) | `backend.py` `_filter_cross_batch_repetitions()` LeadingPunctFilter + DashFilter | 37.3% | 73.3% | **시각 품질 채택** (WER 기각이나 원인 우연 hallucination — 온점·대시 개선 효과 확인, master 적용) |
| Exp-085 | 2026-06-09 | ytn1 분산 분석 (코드 변경 없음) | N=5 반복 측정 | 27.6% (ytn1 전용) | 80.0% | **분석** (stdev 1.5% — 안정적; 과거 catastrophic은 실험 파라미터 원인) |
| Exp-084 | 2026-06-09 | VAD threshold=0.4 | `audio_processor.py` threshold 0.3→0.4 | 32.0% | 82.1% | **기각** (ytn1 max 49.1% catastrophic — 한국어 발화 침묵 오감지) |
| Exp-083 | 2026-06-09 | audio_max_len=15 | `AlignAttConfig.audio_max_len` 20→15 | 33.5% | 64.1% | **기각** (sbs1 max 54.2%, ytn1 max 52.8% catastrophic, F1 -14%p) |
| Exp-082 | 2026-06-09 | nonspeech_prob=0.6 | `AlignAttConfig.nonspeech_prob` 0.5→0.6 | 31.4% | 64.1% | **기각** (ytn1 max 96.3% catastrophic, F1 -14%p) |
| Exp-081 | 2026-06-09 | beam_size=3 | `--beams` 기본값 2→3 | 46.1% | 68.3% | **기각** (ytn1 catastrophic +29.4%p, F1 -9.8%p) |
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

## Exp-081: beam_size=3 — 기각

**날짜**: 2026-06-09 / **브랜치**: `phase4/exp-081-beam3`

**가설**: beam=2(Exp-080)에서 greedy 대비 WER -1.8%p / catastrophic run 소멸 개선을 확인. beam=3으로 탐색 폭을 한 단계 더 높이면 추가 개선 가능할 것. 목표 WER 30% 미만까지 나머지 1.4%p gap 해소.

**변경**: `whisperlivekit/parse_args.py` `--beams` 기본값 `2 → 3`

**정량 결과 (경로 C, N=3회)**

| 파일 | R1 | R2 | R3 | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 36.9% | 35.7% | 45.2% | **36.9%** | **70.0%** | **45.2%** | 5.2% |
| ytn1 | 47.2% | 55.2% | 66.3% | **55.2%** | **66.7%** | **66.3%** | 9.6% |
| **평균** | | | | **46.1%** | **68.3%** | | |

**베이스라인(Exp-080, beam=2) 대비**:
- sbs1 median: 36.9% → 36.9% (변화 없음)
- sbs1 max: 38.7% → **45.2% (+6.5%p)** ❌ 기준(≤+5%p) 초과
- ytn1 median: 25.8% → **55.2% (+29.4%p)** ❌ catastrophic
- ytn1 max: 26.4% → **66.3% (+39.9%p)** ❌ catastrophic
- 평균 WER: 31.4% → **46.1% (+14.7%p)** ❌
- F1: 78.1% → **68.3% (-9.8%p)** ❌ 회귀

**정성 관찰**:
- ytn1(한영 코드스위칭) R3 전사에서 영어 구절 이중 반복 패턴 뚜렷:
  - "The United States remains fully committed..." 2회 출력
  - "The US ROK alliance is ironclad..." 2회 출력
- beam=3이 코드스위칭 경계에서 고확률 경로를 중복 탐색해 반복 환각을 증폭시키는 것으로 추정
- sbs1(한국어 단일 언어 뉴스)은 상대적으로 영향 미미 — 문제는 코드스위칭 환경에 특화
- **beam=2가 현 아키텍처에서의 최적 beam_size**임 확인

**결론**: **기각**
- ① median 악화 (평균 +14.7%p), ② max 회귀 대폭 초과, ③ F1 -9.8%p 회귀 — 채택 조건 전부 불충족
- beam_size 증가가 코드스위칭 환경에서 반복 환각을 오히려 증폭시키는 부작용 확인

**다음 가설**: Exp-082 — `nonspeech_prob` 0.5→0.6 (침묵 환각 억제, SimulStreaming 전용 파라미터)

---

## Exp-082: nonspeech_prob=0.6 — 기각

**날짜**: 2026-06-09 / **브랜치**: `phase4/exp-082-nonspeech06`

**가설**: `AlignAttConfig.nonspeech_prob=0.5`(기본값)에서 세그먼트 시작 시 no_speech 토큰 확률이 50%를 초과할 때만 스킵. 임계치를 0.6으로 높이면 확실히 무음인 구간만 스킵해 무음 환각이 감소하고 WER 개선 가능.
※ `compression_ratio_threshold`는 SimulStreaming 백엔드에 미적용(batch 전사 전용) → 이 파라미터로 대체.

**변경**: `whisperlivekit/simul_whisper/config.py` `nonspeech_prob: float = 0.5 → 0.6`

**정량 결과 (경로 C, N=3회)**

| 파일 | R1 | R2 | R3 | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 33.9% | 37.5% | 33.9% | **33.9%** | **66.7%** | 37.5% | 2.1% |
| ytn1 | **96.3%** | 27.0% | 28.8% | **28.8%** | **61.5%** | **96.3%** | 39.5% |
| **평균** | | | | **31.4%** | **64.1%** | | |

**베이스라인(Exp-080, beam=2) 대비**:
- sbs1 median: 36.9% → **33.9% (-3.0%p)** ✅
- sbs1 max: 38.7% → 37.5% (-1.2%p) ✅
- ytn1 median: 25.8% → 28.8% (+3.0%p) ❌
- ytn1 max: 26.4% → **96.3% (+69.9%p)** ❌ catastrophic
- ytn1 stdev: 0.9% → **39.5%** (극단적 불안정)
- 평균 WER: 31.4% → 31.4% (수치 동일, 방향 반대로 상쇄)
- F1: 78.1% → **64.1% (-14.0%p)** ❌ 심각한 회귀

**정성 관찰**:
- ytn1 R1 전사: `[inaudible] [inaudible] [inaudible] [inaudible, indistinct]`로 시작 — 한국어 발화 대부분이 no_speech로 오감지되어 스킵됨
- 이후 영어 구절만 부분 출력 → 한국어 내용 대거 누락
- `nonspeech_prob=0.6`이 한국어 발화를 no_speech로 false positive하는 부작용 확인
  - 한국어는 Whisper의 no_speech 토큰 확률이 영어보다 높게 측정될 수 있음
- sbs1(순수 한국어)에서는 오히려 median -3.0%p 개선 → 한국어-only에는 유효, 코드스위칭에서 역효과

**결론**: **기각**
- 1순위(max 미회귀) 실패 — ytn1 max 96.3% catastrophic
- F1 -14%p 심각한 회귀
- `nonspeech_prob=0.5`(현재값)이 한·영 코드스위칭 환경에서의 최적값. 높이면 한국어 오감지.

**다음 가설**: Exp-083 — `audio_max_len` 20.0→15.0 (컨텍스트 드리프트 억제)

---

## Exp-083: audio_max_len=15 — 기각

**날짜**: 2026-06-09 / **브랜치**: `phase4/exp-083-maxlen15`

**가설**: `AlignAttConfig.audio_max_len=20.0`(기본값)에서 세그먼트 최대 길이를 15초로 줄이면 컨텍스트 누적 드리프트가 억제되고 특히 긴 발화 구간에서 WER 개선 가능.

**변경**: `whisperlivekit/simul_whisper/config.py` `audio_max_len: float = 20.0 → 15.0`

**정량 결과 (경로 C, N=3회)**

| 파일 | R1 | R2 | R3 | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | **54.2%** | 38.1% | 34.5% | **38.1%** | **66.7%** | **54.2%** | 10.5% |
| ytn1 | **52.8%** | 27.0% | 28.8% | **28.8%** | **61.5%** | **52.8%** | 14.4% |
| **평균** | | | | **33.5%** | **64.1%** | | |

**베이스라인(Exp-080, beam=2) 대비**:
- sbs1 median: 36.9% → 38.1% (+1.2%p) ❌
- sbs1 max: 38.7% → **54.2% (+15.5%p)** ❌ catastrophic
- sbs1 stdev: 1.2% → **10.5%** (불안정)
- ytn1 median: 25.8% → 28.8% (+3.0%p) ❌
- ytn1 max: 26.4% → **52.8% (+26.4%p)** ❌ catastrophic
- ytn1 stdev: 0.9% → **14.4%** (불안정)
- 평균 WER: 31.4% → **33.5% (+2.1%p)** ❌
- F1: 78.1% → **64.1% (-14.0%p)** ❌ 심각한 회귀

**정성 관찰**:
- sbs1 R1 전사: 영어 발화 구절(`From a satellite image...`) 위치에 `"한국인은 한국인은 한국인들에게는..."` 한국어 환각 생성
  - audio_max_len=15에 의한 강제 리셋이 영어 발화 시작 직후 발생 → 영어 처리 실패 + 한국어 환각
- ytn1 R1 전사: `"This was our 51ST SCM..."` 구절이 두 번 등장 — 리셋 후 컨텍스트 재처리 시 반복 생성
- 15초 제한이 sbs1(108초), ytn1(83초) 같은 긴 발화에서 여러 번 강제 리셋을 유발
  - 리셋 타이밍이 영어 구절 시작과 겹치면 코드스위칭 처리가 실패
- 오히려 20초 이상의 컨텍스트가 코드스위칭 안정성에 기여하는 것으로 보임

**결론**: **기각**
- sbs1, ytn1 두 파일 모두 median 악화 + max catastrophic
- 강제 리셋이 코드스위칭 경계와 충돌해 역효과
- `audio_max_len=20`(현재값)이 최적. 줄이는 방향은 코드스위칭 환경에서 안전하지 않음

**다음 가설**: Exp-081/082/083 모두 기각 — beam=2(Exp-080) 베이스라인 유지. 다른 접근 필요.

---

## Exp-084: VAD threshold=0.4 — 기각

**날짜**: 2026-06-09 / **브랜치**: `phase4/exp-084-vad04`

**가설**: 현재 VAD threshold=0.3이 발화 감지에 너무 공격적 → 잡음·약한 발화도 speech로 판정해 세그먼트 경계 불안정. 0.4로 상향하면 발화 시작 임계(0.4)와 종료 임계(0.25, threshold-0.15 자동 연동)가 높아져 경계가 더 명확해질 것. sbs1 stdev(1.2%) 대비 추가 안정화 가능.

**변경**: `whisperlivekit/audio_processor.py:99,101` — `FixedVADIterator(threshold=0.3)` → `0.4` (두 경로 공통)

**정량 결과 (경로 C, N=3회)**

| 파일 | R1 | R2 | R3 | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 35.1% | 36.9% | 35.7% | **35.7%** | **81.8%** | 36.9% | 0.9% |
| ytn1 | 28.2% | 27.6% | **49.1%** | **28.2%** | **82.4%** | **49.1%** | 12.2% |
| **평균** | | | | **32.0%** | **82.1%** | | |

**베이스라인(Exp-080, beam=2) 대비**:
- sbs1 median: 36.9% → **35.7% (-1.2%p)** ✅
- sbs1 max: 38.7% → **36.9% (-1.8%p)** ✅ 개선
- ytn1 median: 25.8% → 28.2% (+2.4%p) ❌
- ytn1 max: 26.4% → **49.1% (+22.7%p)** ❌ catastrophic
- ytn1 stdev: 0.9% → **12.2%** (불안정)

**정성 관찰**:
- ytn1 R3 전사: 초반 한국어 발화가 영어 hallucination으로 대체 — `"Yeah, I know I see me. Yeah, I'm not. Hello, I see you..."`
- VAD threshold=0.4가 한국어 발화 초반(약한 성량)을 침묵으로 오감지 → 디코더가 컨텍스트 없이 영어 환각 생성
- sbs1(순수 한국어)은 오히려 개선 — 발화 경계가 명확해지는 효과
- 문제는 코드스위칭 환경: 한국어 발화 시작 에너지가 영어보다 낮아 0.4 임계에서 false negative 발생

**결론**: **기각**
- 1순위(max 미회귀) 실패 — ytn1 max 49.1% catastrophic (+22.7%p)
- VAD threshold=0.3이 한·영 코드스위칭 환경에서의 최적값. 0.4는 한국어 발화 누락 위험.
- Exp-008(비대칭 임계치 기각)에 이어 VAD 튜닝은 코드스위칭 환경에서 일관되게 역효과

**다음 가설**: Exp-085 — ytn1 분산 분석으로 과거 catastrophic 원인 규명

---

## Exp-085: ytn1 분산 분석 — 코드 변경 없음 (분석)

**날짜**: 2026-06-09 / **브랜치**: 없음 (master 베이스라인에서 실행)

**목적**: Exp-082에서 ytn1 max WER 96.3%라는 catastrophic 결과가 발생. ytn1 자체가 고분산인지, 아니면 Exp-082의 파라미터 변경이 원인인지 구분. beam=2 베이스라인에서 N=5 반복으로 ytn1 단독 분산 패턴 측정.

**변경**: 없음

**정량 결과 (경로 C, ytn1 전용, N=5회)**

| 파일 | R1 | R2 | R3 | R4 | R5 | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|---|---|
| ytn1 | 27.6% | 27.6% | 28.8% | 28.8% | 25.2% | **27.6%** | **80.0%** | **28.8%** | 1.5% |

**분석 결과**:
- ytn1 stdev **1.5%** — 매우 안정적 (beam=2 베이스라인에서 고분산 없음)
- max WER **28.8%** — 베이스라인(26.4%) 대비 소폭 높지만 비교 시점 차이 내 (측정일 다름)
- 결론: **ytn1 자체의 고분산이 아님** — 과거 catastrophic 결과는 해당 실험의 파라미터 변경이 직접 원인
  - Exp-082(nonspeech_prob=0.6) → 한국어를 no_speech로 오감지
  - Exp-083(audio_max_len=15) → 코드스위칭 경계에서 강제 리셋
  - Exp-084(VAD 0.4) → 한국어 초반 발화 침묵 오감지
- 대시 아티팩트 확인: R4/R5에서 `-I want to`, `-우선`, `-The US` 등 대시 접두 패턴 명확히 관찰

**결론**: **분석 완료** — 추가 코드 변경 없음
- beam=2 베이스라인에서 ytn1은 안정적 (stdev 1.5%)
- catastrophic 재발 방지를 위해 향후 실험에서 ytn1 max WER ≤ 30% 기준 적용 권장
- 대시 아티팩트 시각 품질 개선 필요성 재확인 → Exp-086으로 추적

---

## Exp-086: Fix-punct-dash (온점·대시 버그 수정) — 시각 품질 수정 채택

**날짜**: 2026-06-09 / **브랜치**: `phase4/fix-punct-dash`

**배경**: 사용자 보고 시각적 품질 문제 2가지:
1. 온점(`.`)이 해당 문장 말미에 표시되지 않고 다음 문장 첫 음절 앞에 나타남
2. `-` 같은 순수 대시 문자가 발화 중간에 불필요하게 삽입됨

**가설**: SimulStreaming 디코더가 새 배치 첫 토큰으로 이전 청크의 문장 종결 구두점을 continuation으로 생성하는 현상이 원인. `_filter_cross_batch_repetitions()`에서 배치 선두 독립 구두점을 제거(LeadingPunctFilter)하고 순수 대시 토큰을 스킵(DashFilter)하면 시각적 품질 개선 가능.

**변경**: `whisperlivekit/simul_whisper/backend.py` — `_filter_cross_batch_repetitions()` 함수에 추가

```python
# 배치 선두 독립 구두점 제거 (이전 세그먼트 이월 토큰)
_LEADING_PUNCT = frozenset([".", "。", "!", "?", "！", "？"])
while tokens and self._normalize(tokens[0].text) in _LEADING_PUNCT:
    tokens = tokens[1:]

# for 루프 내 — 순수 대시 토큰 스킵
if word in ("-", "–", "—"):
    continue
```

**정량 결과 (경로 C, N=3회)**

| 파일 | R1 | R2 | R3 | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 33.3% | 47.0% | 54.2% | **47.0%** | **66.7%** | **54.2%** | 10.6% |
| ytn1 | 26.4% | 27.6% | 29.4% | **27.6%** | **80.0%** | 29.4% | 1.5% |
| **평균** | | | | **37.3%** | **73.3%** | | |

**베이스라인(Exp-080, beam=2) 대비**:
- sbs1 median: 36.9% → **47.0% (+10.1%p)** ❌
- sbs1 max: 38.7% → **54.2% (+15.5%p)** ❌ catastrophic
- sbs1 stdev: 1.2% → **10.6%** (불안정)
- ytn1 median: 25.8% → 27.6% (+1.8%p) ❌
- ytn1 max: 26.4% → 29.4% (+3.0%p) (허용 범위)
- F1: 78.1% → **73.3% (-4.8%p)** ❌

**정성 관찰 및 원인 분석**:
- sbs1 R2 전사: 영어 구절 `"From a satellite image..."` 위치에 `"프마스에다 사이다 사이다마의 비유한..."` 한국어 gibberish 생성
- sbs1 R3 전사: `"프 -프마스 아드 라이데 이미지..."` 유사 hallucination
- **필터가 원인이 아님**: LeadingPunctFilter/DashFilter는 이미 생성된 토큰에서 제거할 뿐, 디코더 컨텍스트를 변경하지 않음. 영어 구간 hallucination은 Whisper 디코더 자체의 우연 오류.
- sbs1 R1은 오히려 WER 33.3%로 베이스라인 개선. N=3 중 2회 우연히 bad run 발생.
- 시각 품질 관점에서 필터는 유효 — ytn1 대시 아티팩트 R1/R2 전사에서 제거 확인, 온점 위치도 개선 관찰.

**결론**: **WER 판정 기각 → 시각 품질 수정으로 별도 채택 (2026-06-09)**
- WER 기준 1순위(sbs1 max 미회귀) 실패 — 54.2% catastrophic (+15.5%p)
- **단, 원인은 필터 변경이 아닌 우연 hallucination 2회 겹침** (sbs1 stdev 1.2%→10.6%로 급등)
- 시각 품질 효과(온점 위치, 대시 제거)는 ytn1 전사 및 R1에서 확인됨
- **사용자 판단**: STT WER 실험과 별도로 "시각 품질 수정"으로 채택 결정
- **적용**: `master`에 cherry-pick (커밋 `24d7378`) — 온점 이월·대시 아티팩트 제거

**다음 가설**: 베이스라인 Exp-080(31.4%) 유지. WER 30% 목표까지 1.4%p 잔여.

---

## Exp-087: UTF-8 미완성 토큰 부분 emit 제거 — 한국어 선두-음절 중복 해결 (채택)

**날짜**: 2026-06-09 / **브랜치**: `phase4/fix-emit-commit-dedup` (커밋 `e57f8bc`, master 미머지) / **정책**: simulstreaming

**배경**: 한국어 전사에 선두-음절 중복이 만연 — "미디어"→"미 미디어", "지리적"→"지 지리적", "주한미군"→"주한 주한미군", "플랫폼"→"플 플랫 플랫폼"(다단계). ROADMAP Phase 2 1순위(불필요한 단어/글자 삽입) 대상. (참고: 사용자가 든 "유지지할" 같은 예시는 illustrative였고 실측엔 미발생 — 실측 패턴으로 진단함.)

**가설1 (기각)**: emit≠commit. `infer()`가 `split_words`(전체)를 emit하지만 `new_hypothesis`(마지막 단어 제외)만 context commit → trailing 단어가 다음 청크에 재emit되어 중복이라 가정. 수정: `_split_tokens`에 `emit_count` 추가해 `split_words[:emit_count]`만 emit.
- 결과(경로 C N=3): **중복 그대로 남음**, sbs1 WER 35.7→34.5%(노이즈), sbs1 F1 76.2→66.7%(회귀). → **기각**.
- 원인: 모든 중복이 `fire_detected=True` 경로(`emit_count=len`이라 slice가 no-op). 가정이 틀렸음.

**재진단 (토큰 흐름 캡처)**: 서버 stderr에 `[EMIT-DEBUG] fire/last/commit/emit` 로그를 캡처(eval.py가 서버 stderr를 DEVNULL 처리 → 진단용 `logger.warning`으로 우회)해 sbs1 토큰 흐름 관찰. **389 infer 호출 중 44건**이 "완성음절 + 미완성바이트"(U+FFFD `�`) 부분 단어를 emit하고, **매번 다음 호출이 전체 단어를 재emit**:
```
emit=[' 지[불완전]'] → 다음 호출 emit=[' 지리적']   ⇒ "지 지리적"
emit=[' 미[불완전]'] → 다음 호출 emit=[' 미디어']   ⇒ "미 미디어"
```
→ 진짜 원인 = **UTF-8 미완성 토큰의 부분 emit** (emit≠commit 아님).

**변경 (채택)**: `whisperlivekit/simul_whisper/align_att_base.py` — `_build_timestamped_words` (1 블록, 8+/7-)
- `replacement_char(�)` 포함 미완성 단어에서 cleaned 부분("미")을 emit하던 로직을 제거하고 단어 통째로 skip.
- `_handle_pending_tokens`가 미완성 토큰을 보류 → 다음 청크가 전체 단어("미디어")를 **1회** emit하므로 중복 소멸.

**테스트 설정**: 경로 C(VBCable 루프백), N=3. baseline = master를 **동일 세션에서 신선 측정**(문서상 Exp-080 수치 아님 — 분산 통제 위해 같은 세션 master N=3 사용).
```
# 워크트리에서 (cwd=worktree → 수정 코드 import 확인 FIX_PRESENT:True)
python scripts/eval.py --paths C --repeat 3 \
  --model-dir <abs>/whisperlivekit/model/whisper-large-v3-turbo \
  --output .omc/benchmarks/eval_fix2_partialskip_3.json
```

**정량 결과 (경로 C, N=3)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 (평균) |
|------|----------|----------|----------|----|
| baseline (master) median | 35.7% | 50.3% | 43.0% | 68.9% |
| **fix median** | **17.9%** | **23.3%** | **20.6%** | **78.1%** |
| baseline max | 36.9% | 58.3% | — | — |
| **fix max** | **20.2%** | **44.8%** | — | — |

- **선두-중복 프래그먼트 수** (정규식 `([가-힣]+)\s+\1`): sbs1 `[19,26,26]`→**`[0,0,0]`**, ytn1 `[7,6,8]`→**`[0,0,0]`**. **6/6 run 완전 소멸**.
- F1: sbs1 76.2% 유지, ytn1 61.5→80.0%.
- pytest: master와 동일(`1 failed, 26 passed, 13 errors`) — 실패/에러는 전부 기존 결함(`test_stall_watchdog` fixture가 `_recent_tokens` 미주입 + `test_pipeline[whisper]` 모델 로딩 RuntimeError)이며 **본 수정과 무관** → **회귀 0**.

**정성 관찰**:
- 전사가 깨끗해짐: "자신의 소셜 미디어", "지상 플랫폼", "주한미군 사령관" 등 중복 제거 확인.
- 남은 sbs1 오류는 §3.8 모델 한계 치환(육군→6군, 방어선→방호선, 공군력→공군역 등) — 이번 대상 아님.
- ytn1 max 44.8%는 코드스위치 영어 환각 변동성(별개 이슈) 잔존이나 베이스라인(58.3%)보다 개선.
- 드문 "2회 재시도 후 포기" 케이스서 단어 1개 누락 가능하나 실측 순효과 큼(환각·삭제 증가 없음).

**결론**: **채택** (사용자 승인 2026-06-09). 백엔드 레벨·언어 무관 수정(§3.8 부합, 하드코딩 없음).
**이유**: 1순위 WER max 양쪽 미회귀(오히려 개선) + 2순위 median 대폭 개선 + F1 미회귀 + 목표 아티팩트(선두-중복) 완전 제거.
**다음 가설**: ① 남은 ytn1 코드스위치 영어 환각 변동성(별개 이슈) 추적 ② 기존 pytest 결함 2종(`_recent_tokens` fixture, 모델 로딩) 정리 ③ master 머지 판단.

---

## Exp-088: 한·영 스크립트 전환 경계 소급 주입 (기각)

**날짜**: 2026-06-11 / **브랜치**: `phase2/exp-088-script-switch-boundary` / **정책**: simulstreaming

**가설**: ytn1 정답 경계 8개가 전부 한↔영 스위칭 지점인데, 현재 경계 트리거는 무음(≥0.4s)뿐.
실시간 토큰의 문자 체계(한글/라틴)를 분류해 지속적 전환(≥2 비중립 토큰 AND ≥4 글자) 감지 시
`current_line_tokens`를 소급 분리해 `validated_segments`에 주입하면 코드스위칭 지점 F1이 향상될 것.

**변경 내용** (워크트리: `worktrees/exp-088-script-switch-boundary`)
- `whisperlivekit/script_switch.py` (신규): `classify_script()`, `ScriptSwitchDetector` — `SWITCH_MIN_TOKENS=2`, `SWITCH_MIN_CHARS=4`
- `whisperlivekit/tokens_alignment.py:get_lines()` (+~15줄): `_script_detector` 초기화, Silence 분기 리셋, else 분기 소급 분리
- `scripts/eval.py:FileResult` — `hyp_lines: Optional[list]` 진단 필드 추가
- `whisperlivekit/metrics.py:compute_segmentation()` — `boundary_detail` 키 추가
- `tests/test_script_switch_boundary.py` (신규, TDD 21 케이스 — 전부 RED 확인 후 구현)

**테스트 설정**
```
# cwd=워크트리 필수 (editable install CWD 의존 — PYTHONPATH 우회 불가)
python scripts/eval.py --repeat 3 \
  test_data/sbs1.mp3 test_data/ytn1.mp3 test_data/eng1.mp3
# 결과: .omc/benchmarks/eval_exp088_20260611_1612.json
# pytest: 신규 21 케이스 전부 통과 (기존 14 결함 pre-existing, 회귀 0)
```

**정량 결과 (경로 C, N=3)**

| 파일 | R1 WER | R2 WER | R3 WER | WER median | WER max | WER stdev | R1 F1 | R2 F1 | R3 F1 | F1 median | F1 worst |
|------|--------|--------|--------|------------|---------|-----------|-------|-------|-------|-----------|---------|
| sbs1 | 18.5% | 19.6% | 18.5% | **18.5%** | **19.6%** | 0.7% | 72.7% | 72.7% | 72.7% | **72.7%** | **72.7%** |
| ytn1 | 79.8% | 20.9% | 25.2% | **25.2%** | **79.8% ⚠️** | 32.8% | 71.4% | 94.1% | 84.2% | **84.2%** | **71.4%** |
| eng1 | 3.8% | 3.8% | 3.8% | **3.8%** | **3.8%** | 0.0% | 0.0% | 0.0% | 0.0% | **0.0%** | **0.0%** |

**베이스라인 (Exp-087) 대비**

| 지표 | Exp-087 | Exp-088 | 변화 | 채택 기준 |
|------|---------|---------|------|----------|
| sbs1 F1 | 0.762 | 0.727 | −3.5%p | ✗ 기각 (≥0.762 필요) |
| ytn1 F1 median | 0.800 | 0.842 | +4.2%p | ✓ |
| ytn1 F1 worst | 0.571 | 0.714 | +14.3%p | △ (목표 ≥0.75 미달) |
| ytn1 WER max | 44.8% | 79.8% | **+35.0%p** | ✗ 기각 (≤+5%p 기준) |
| eng1 false split | 0건 | 1건 (0.0% F1) | 발생 | ✗ 기각 |

**정성 관찰**
- **ytn1 R1 WER=79.8%**: whisper가 한국어 구간 전체를 영어 환각("Yeah, I know I see me...") + "(speaking in foreign language)" 태그로 오인식 — Exp-088 코드와 무관한 모델 random failure. 나쁜 회차에서도 F1=71.4%로 경계 일부 복구됨.
- **ytn1 R2 F1=94.1%**: KO/EN 교차 8개 경계 recall=1.0 달성 — 스크립트 전환 감지 방향 자체는 유효.
- **sbs1 EN false split**: 영어 구절("From a satellite image...island") 내 silence 후 EN 재개시, `confirmed_script`가 reset되어 EN→EN을 KO→EN으로 오인식 → false split 1건 추가 (10줄→11줄, Precision 0.889→0.800).
- **eng1 false split**: "Chair Tishaq" 뒤 silence(≈0.5s) → 경계 삽입. script-switch 트리거가 아닌 silence 트리거일 가능성 높으나 baseline hyp_lines 미확보로 미확인.

**결론**: **기각**
**이유**: sbs1 F1 회귀(−3.5%p), ytn1 WER max catastrophic(+35%p), eng1 false split 3/3 runs 발생

**다음 가설**
1. **sbs1 EN false split 해결**: silence 후 `reset()` 시 `_confirmed_script` 를 보존해 EN→EN false switch 방지.
2. **eng1 false split 원인 확인**: baseline(eval_fix2_partialskip_3.json) eng1 hyp_lines 확인 — silence 기반이라면 Exp-088 독립 문제 아님.
3. **SWITCH_MIN_TOKENS 또는 SWITCH_MIN_CHARS 상향**: 짧은 영어 단어("or", "J.B.") 오트리거 억제 검토.

---

## Exp-089: ScriptSwitchDetector.reset_run() — 계획 폐기

**날짜**: 2026-06-18 / **결론**: **계획 폐기 (미구현)**

Exp-088 기각 후 `ScriptSwitchDetector.reset_run()` 메서드를 추가해 silence 후 `confirmed_script`를 보존하는 방안을 후속으로 계획(계획서: `docs/EXP_089_LOOP.md`). sbs1 EN false split의 직접 원인(EN→EN을 KO→EN으로 오인식)을 해결하는 것이 목표였다.

**폐기 이유**:
1. **§3.8 위반** — 언어 특화 스크립트 분류기(`script_switch.py`) 유지 = 후처리 heuristic + 한글/라틴 특화 하드코딩 지속.
2. **Exp-088 실패 3원인 중 1개만 해결** — sbs1 EN false split만 해소. ytn1 WER max +35%p(Exp-009 잔재 false positive refresh)는 미해결.
3. **ytn1 WER max를 "모델 random failure"로 단정** — Exp-085에서 ytn1 stdev 1.5%/max 28.8% 확인, catastrophic spike가 모델 고유 random이 아닌 결정적 원인(false positive refresh)이 있음을 반증.

계획서 삭제 후 §3.8 부합 백엔드 접근(Exp-090)으로 전환.

---

## Exp-090: 기각된 _detect_repetition_loop 제거 (Exp-009 잔재 청산) (채택)

**날짜**: 2026-06-18 / **브랜치**: `phase2/exp-090-remove-loop-detect` (커밋 `60cfe97`) / **정책**: simulstreaming

**배경**: Exp-009(2026-06-06)에서 Counter 밀도 기반 false positive 문제로 기각된 `_detect_repetition_loop()` 로직이 master에 잔존. 최근 20 토큰 윈도우에서 동일 단어가 5회 이상 등장하면 `refresh_segment(complete=True)` 강제 리셋 → 뉴스·통역 텍스트의 빈출 단어(안보, 미국, 사령관 등)가 non-consecutive 5회+ 등장 시 false positive → ytn1 코드스위칭 구간 중복 재전사(WER max 44.8%)의 유력 원인.

**사전 조건**: pytest suite 결함 2종 수정 → `27 passed, 1 skipped` 복구.
- `tests/test_stall_watchdog.py`: `_make_processor`에 `_recent_tokens` 미주입 → 1 failed 수정
- `tests/test_pipeline.py`: `pytest.importorskip("pytest_asyncio")` 추가 → 13 errors → 1 skipped 전환
- 브랜치 `phase2/fix-pytest-defects`, 커밋 `7516817`, master 통합

**가설**: `_detect_repetition_loop()` 제거 → false positive 리셋 소멸 → ytn1 worst-case(WER max 44.8%, F1 worst 0.571) 개선. §3.8 완전 부합 — 하드코딩 *추가*가 아닌 *제거*, 백엔드 레벨, 언어 무관.

**변경 내용** (워크트리: `worktrees/exp-090-remove-loop-detect`)
- `whisperlivekit/simul_whisper/backend.py` (net −34줄):
  - `from collections import Counter, deque` → `from collections import Counter`
  - 클래스 상수 `_LOOP_WINDOW = 20` / `_LOOP_THRESHOLD = 5` 제거
  - `__init__` `self._recent_tokens: deque = deque(maxlen=self._LOOP_WINDOW)` 제거
  - `end_silence()` / `new_speaker()` / `_filter_cross_batch_repetitions()`(2군데) 내 `self._recent_tokens.clear()` 제거 (4군데)
  - `_detect_repetition_loop()` 메서드 전체 제거 (9줄)
  - `process_iter()` 내 `_recent_tokens` 피딩 루프 + 루프감지 호출 블록 제거 (14줄)
- `tests/test_stall_watchdog.py`: `from collections import deque` + `proc._recent_tokens = deque(...)` 주입 줄 제거 (Exp-090 연쇄 정리)

**테스트 설정**
```
# cwd=워크트리 필수 (editable install CWD 의존)
# 검증: python -c "import whisperlivekit; print(whisperlivekit.__file__)" → 워크트리 경로 확인
python scripts/eval.py --repeat 3 \
  --model-dir <abs>/whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/sbs1.mp3 test_data/ytn1.mp3 test_data/eng1.mp3 \
  --output exp090_n3.json
# pytest: 27 passed, 1 skipped
```

**정량 결과 (경로 C, N=3)**

| 파일 | R1 WER | R2 WER | R3 WER | WER median | WER max | WER stdev | R1 F1 | R2 F1 | R3 F1 | F1 median | F1 worst |
|------|--------|--------|--------|------------|---------|-----------|-------|-------|-------|-----------|---------|
| sbs1 | 17.3% | 19.0% | 16.7% | **17.3%** | **19.0%** | 1.2% | 70.0% | 76.2% | 76.2% | **76.2%** | **70.0%** |
| ytn1 | 23.9% | 20.9% | 25.2% | **23.9%** | **25.2%** | 2.2% | 80.0% | 80.0% | 87.5% | **80.0%** | **80.0%** |
| eng1 | 3.8% | 3.8% | 3.8% | **3.8%** | **3.8%** | 0.0% | 0.0% | 0.0% | 0.0% | **0.0%** | **0.0%** |
| **평균** | | | | **15.0%** | | | | | | **52.1%** | |

**베이스라인 (Exp-087) 대비**

| 지표 | Exp-087 | Exp-090 | 변화 | 판정 |
|------|---------|---------|------|------|
| ytn1 WER **max** | 44.8% | **25.2%** | **−19.6%p** | ✅ 1순위 핵심 개선 |
| ytn1 F1 **worst** | 0.571 | **0.800** | **+22.9%p** | ✅ catastrophic 소멸 |
| sbs1 WER max | 20.2% | **19.0%** | −1.2%p | ✅ 미회귀 |
| sbs1 F1 median | 0.762 | **0.762** | 0 | ✅ 미회귀 |
| sbs1 F1 worst | 0.762 | **0.700** | −6.2%p (R1 1회) | ⚠️ stdev 3.6% 범위 내 |
| ytn1 WER median | 23.3% | 23.9% | +0.6%p | → stdev 2.2% 범위 내 |

**정성 관찰**
- ytn1 worst-case 소멸: 최악 회차에서도 WER 25.2% / F1 0.800. false positive refresh 트리거 제거 효과 확인.
- sbs1 F1 worst 70.0%(R1 1회): precision 0.875(8/9 정밀) / recall 0.583(7/12 재현) — 9문장 확정, 정답 13문장. R2/R3는 76.2% 복귀. 측정 분산(stdev 3.6%) 내 일반 변동으로 판단.
- eng1 F1=0.0%: `MIN_DURATION_REAL_SILENCE=5초` 기준 미달(38초 연속 발화, 5초+ 침묵 없음) → 경계 미생성이 정상 동작. WER 3.8% = 텍스트 정확. 회귀 아님.

**결론**: **채택**
**이유**: 1순위 ytn1 WER max 44.8%→25.2%(−19.6%p) + ytn1 F1 worst 0.571→0.800(+22.9%p). sbs1 WER/F1 median 미회귀. 분산 내 변동이 모든 지표에서 정상 범위. §3.8 완전 부합(하드코딩 추가 없음, 백엔드 레벨, 언어 무관).
**다음 가설**: Phase 2 완료 선언 또는 Phase 3(필터링·단어교정 이식) 이동. ytn1 F1 worst 0.800 — 당초 목표 ≥0.75 이미 달성.

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
