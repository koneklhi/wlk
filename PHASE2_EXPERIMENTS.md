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
- **경로 A `speed=0`(오디오 일괄 덤프) 전사가 후반부 절단되는 정황**: 측정 신뢰성부터 검증할 것
  (재시작 후 Phase 0a). 채택/기각의 1차 지표는 경로 C로 통일한다.

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
- 측정 환경: 경로 C(VBCable), `--lan ko`, 기본 설정(VAC 켜짐), sbs1+ytn1 파일별 서버 재시작

---

## 빠른 참조 (최신순)

| Exp | 날짜 | 제목 | 핵심 변경 | WER (중앙값) | Latency | 결론 |
|---|---|---|---|---|---|---|
| [Exp-032](#exp-032-_loop_threshold-53-과공격-기각) | 2026-06-06 | LOOP_THRESHOLD=3 | `backend.py` `_LOOP_THRESHOLD=3` (5→3) | R1 55.3%/R2 66.3% WER, F1 12-29% | — | **기각** |
| [Exp-031](#exp-031-master-char-run-단일음절-필터) | 2026-06-06 | master+char-run 필터 | `backend.py` char-run 억제 + context 리셋, threshold=5 | 중앙값 avg WER 67.2%, F1 37.7% (R1 43.5%, R2 67.2%, R3 98.0%) | — | **기각** |
| [Exp-030](#exp-030-슬라이딩-윈도우-한국어-전용-빈도-필터) | 2026-06-06 | 슬라이딩 윈도우 한국어 전용 빈도 필터 | `backend.py` `_KO_CHAR` + `threshold=5, window=25` | avg WER 87.3% (베이스라인 대비 +12.8%p) | — | **기각** |
| [Exp-029](#exp-029-슬라이딩-윈도우-단어-빈도-필터) | 2026-06-06 | 슬라이딩 윈도우 단어 빈도 필터 | `backend.py` `_WORD_WINDOW_SIZE=20`, `_WORD_FREQ_THRESHOLD=4`, `_recent_words` 빈도 체크 | avg WER 79.5% (ytn1 99.4% catastrophic) | — | **기각** |
| [Exp-028](#exp-028-단일음절-연속-반복-억제--context-리셋) | 2026-06-06 | 단일음절 연속 반복 억제 + context 리셋 | `backend.py` `_max_char_run` + `_CHAR_RUN_THRESHOLD=4` + 억제 카운터≥5 시 context 리셋 | avg WER **61.8%**, F1 **45.1%** | — | **채택** |
| [Exp-027](#exp-027-하이픈-프리픽스-단어-반복-억제) | 2026-06-06 | 하이픈 프리픽스 단어 반복 억제 | `backend.py` `_consecutive_short_hyphen` 카운터 + `_HALLUCINATION_HYPHEN_THRESHOLD=4` | avg WER 72.1% | — | **기각** |
| [Exp-009](#exp-009-반복-루프-감지--refresh_segment-리셋) | 2026-06-06 | 반복 루프 감지 + 디코더 리셋 | `backend.py` `_detect_repetition_loop()` + `refresh_segment()` | — | — | **진행 중** |
| [Exp-008](#exp-008-vad-end_threshold-비대칭-설정-노이즈-차단) | 2026-06-06 | VAD end_threshold=0.35 비대칭 설정 | `silero_vad_iterator.py` end_threshold 파라미터, `audio_processor.py` end_threshold=0.35 | sbs1: 113.7%→149.4% | — | **기각** (발화 중 가짜 silence 과다 → WER 폭발) |
| [Exp-007](#exp-007-eval-파이프-블로킹-수정--vad-threshold-03-재측정) | 2026-06-06 | eval.py 서버 stdout 파이프 블로킹 수정 | `scripts/eval.py` `stdout=PIPE` → `DEVNULL` | sbs1: 79.2% / ytn1: 25.8% / avg: 52.5% | — | **채택** (목표 미달, 다음 실험 진행) |
| [Exp-006](#exp-006-vad-threshold-03--min_duration_real_silence-05) | 2026-06-06 | VAD threshold 낮춤 + Silence 문장확정 임계 낮춤 | `audio_processor.py` threshold 0.5→0.3, MIN_SILENCE 5→0.5 | sbs1: 97.0% / ytn1: 99.4% / avg: 98.5% | — | **기각** (측정 무효 — eval 파이프 블로킹) |
| [Exp-005](#exp-005-워치독-is_lasttrue-flush) | 2026-06-06 | 워치독 is_last=True flush | `backend.py` process_iter() 워치독에 infer(is_last=True) 추가 | sbs1: 97.6% / ytn1: 99.4% / avg: 98.5% | — | **기각** |
| [Exp-004](#exp-004-디코더-멈춤-복구-워치독--경로-c-vbcable-하니스-결함-수정) | 2026-06-06 | 디코더 멈춤 워치독 + 경로 C 하니스 수정 | `backend.py` stall 워치독 + `audio_device.py`/`vbcable_test.py` 하니스 | 단일 run 60~68% (3회 미완) | — | 하니스 **채택** / 워치독 **보류** |
| [Exp-003](#exp-003-한국어-종결어미-기반-문장-확정--nfc-정규화) | 2026-06-05 | 한국어 종결어미 문장 확정 | `tokens_alignment.py` 종결어미 감지 + NFC 정규화 | sbs1: 95.8% / ytn1: 99.4% / avg: 97.6% | — | **기각** |
| [Exp-002](#exp-002-cross-batch-stateful-반복-필터) | 2026-06-05 | Cross-batch 반복 필터 | `process_iter()` 반환 토큰에서 연속 반복 제거 | sbs1: 87.5% / ytn1: 38.7% / avg: 63.1% | — | **채택** |
| [Exp-001](#exp-001-vbcable-마이크-정성-평가--정책-최종-확정) | 2026-05-21 | VBCable 마이크 정성 평가 | 브라우저 마이크 입력으로 실사용 품질 비교 | — | — | **SimulStreaming 채택** |
| [Exp-000](#exp-000-정책-선택-기준-벤치마크-베이스라인) | 2026-05-20 | 정책 선택 기준 벤치마크 | SimulStreaming vs LocalAgreement 비교 | SS: 0.321 / LA: 0.434 | SS: 114ms / LA: 2511ms | → Exp-001에서 확정 |

---

## Exp-000: 정책 선택 기준 벤치마크 (베이스라인)

**날짜**: 2026-05-20
**정책**: simulstreaming vs localagreement (비교)
**가설**: Phase 2 알고리즘을 어느 정책 위에서 설계할지 결정하기 위해 동일 음성에서 두 정책을 실측 비교한다.

**설정**
- 샘플: `test_data/sbs1.mp3` (108.5s) — 한국어 + 영어 인용구 포함
- 모델: `whisper-large-v3-turbo` (로컬)
- 언어: `--lan auto` (코드 스위칭 평가)
- 속도: `speed=1.0` (실시간, latency 측정 의미 보장)
- 명령어: `uv run python scripts/bench_phase2_policies.py --sample test_data/sbs1.mp3`
- 결과 파일: [.omc/benchmarks/phase2_policies_20260520T003636Z.md](.omc/benchmarks/phase2_policies_20260520T003636Z.md)

**정량 결과**

| 항목 | SimulStreaming | LocalAgreement |
|---|---|---|
| WER | **0.321** | 0.434 |
| WER 세부 (subs/ins/del) | 28 / 24 / 2 | 7 / 0 / 66 |
| avg latency | **114ms** | 2511ms |
| p95 latency | 221ms | 9665ms |
| RTF | 1.541 | 1.572 |
| 영문 매치 (hits/ref) | **96%** (25/26) | 0% (0/26) |
| n_transcription_calls | 184 | 31 |
| n_tokens_produced | 242 | 27 |

**정성 관찰**
- SimulStreaming: 반복·버벅임 패턴 있음 ("브런스는", "바 바뀌면" 등). 영어 인용구는 거의 완벽하게 포착.
- LocalAgreement: 더 자연스러운 문장 생성. 영어 인용구 전체 누락 (del 66개). 지연이 매우 큼 (p95 약 10초).
- (마이크 정성 평가 후 상세 인상 추가 예정)

**결론**: → Exp-001(VBCable 정성 평가)에서 SimulStreaming으로 최종 확정
**이유**: 정량 지표 SimulStreaming 우세, 마이크 실사용 결과로 재확인
**다음 실험**: Phase 2 문장 확정 알고리즘 첫 구현 → Exp-002

---

## Exp-001: VBCable 마이크 정성 평가 — 정책 최종 확정

**날짜**: 2026-05-21
**정책**: simulstreaming vs localagreement (최종 비교)
**가설**: 정량 벤치마크(Exp-000)에서 SimulStreaming이 우세했으나, 마이크 실입력 환경에서도 동일한 우열이 유지되는지 확인하고 Phase 2 개발 정책을 확정한다.

**테스트 설정**
- 도구: VBCable — `sbs1.mp3`를 PC 재생 → 가상 오디오 케이블로 마이크 입력에 라우팅
- 입력 방식: 브라우저 마이크 캡처 (`--pcm-input` 없이 서버 기동)
- 서버 명령어:
  ```powershell
  # SimulStreaming
  uv run whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --backend-policy simulstreaming --lan auto --warmup-file test_data/sbs1_10s.mp3
  # LocalAgreement
  uv run whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --backend-policy localagreement --lan auto --warmup-file test_data/sbs1_10s.mp3
  ```
- 결과 파일: `Desktop/simul_sbs_output.txt`, `Desktop/local_sbs_output.txt`

**정성 결과**

| 항목 | SimulStreaming | LocalAgreement |
|---|---|---|
| 전체 커버리지 | 완주 (SBS 김수영까지) | **절반 이후 누락** |
| 한국어 반복 아티팩트 | `미 미 미`, `한 한 한도도도`, `-그 -그 -그` 다수 | 없음 (깔끔) |
| 영어 코드 스위칭 | **완벽 포착** ("From a satellite image..." 등) | **전체 누락** |
| 단어 왜곡 | `국건한`, `공군역과`, `간순한` 등 | `성빈 바다`(→텅 빈), `사령관관관계획` |
| 체감 지연 | 낮음 | 높음 |

**SimulStreaming 전사 샘플 (주요 구간)**
- 반복 예시: `"미 미 미어어어트"`, `"한 한 한도도도 동쪽이를를를"`, `"지 지 지를를 올 올렸습니다"`
- 영어 포착: `"From a satellite image, the Republic of Korea, looks like an island."` ✓
- 영어 포착: `"Like a fixed aircraft carrier floating in the water between Japan, and mainland China."` ✓

**LocalAgreement 전사 샘플**
- 깔끔한 한국어: `"지도를 돌려보면 태평양은 성빈 바다가 아니라 동맹국들이 연결된 거대한 방어선"` (문장 자연스러움)
- 영어 구간 이후 출력 없음 — 약 60초 이후 내용 전체 누락

**결론**: **SimulStreaming 채택** (Phase 2 개발 기반 정책 확정)
**이유**: LocalAgreement의 영어 누락과 커버리지 손실은 LCS 합의 알고리즘의 구조적 문제로 Phase 2에서 패치 불가. SimulStreaming의 반복 아티팩트는 문장 확정 로직(직전 commit과 중복 비교)으로 보완 가능.
**다음 가설**: SimulStreaming의 반복 토큰 (`바 바 바`, `지 지 지`) 및 노이즈 접두어 (`-그`) 를 문장 확정 단계에서 후처리로 제거 → Phase 2 알고리즘 설계 시작 → Exp-002

---

## Exp-002: Cross-batch Stateful 반복 필터

**날짜**: 2026-06-05
**정책**: simulstreaming
**가설**: SimulStreaming은 배치 경계에서 직전 단어를 반복 생성하는 아티팩트("바 바 바", "-그 -그 -그", "도도도도")가 있다.
기존 `_apply_dry_penalty()`는 로짓 공간 패널티로 배치 내부 반복을 억제하지만, 배치 경계를 넘는 연속 반복은 잡지 못한다.
`process_iter()` 반환 직후 직전 방출 단어를 기억하고 연속 동일 단어를 제거하는 stateful 필터를 추가하면
삽입 오류(insertion)가 크게 줄어 WER이 개선될 것이다. sbs1의 WER 100% 초과 원인이 이 삽입 아티팩트이므로
큰 개선 효과가 예상된다.

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py:46` — `__init__`에 `self._last_emitted_word: str = None` 추가
- `whisperlivekit/simul_whisper/backend.py:83` — `end_silence()` long_silence 시 `_last_emitted_word = None` 리셋
- `whisperlivekit/simul_whisper/backend.py:100` — `new_speaker()` 시 `_last_emitted_word = None` 리셋
- `whisperlivekit/simul_whisper/backend.py:106-125` — `_filter_cross_batch_repetitions()` 메서드 추가
- `whisperlivekit/simul_whisper/backend.py:144` — `process_iter()` 내 필터 호출 추가
- `tests/test_cross_batch_filter.py` — 유닛 테스트 10개 신규 추가

**알고리즘 요약**
- `prev = _last_emitted_word` (이전 배치 마지막 단어, 또는 None)
- 각 토큰 text.strip()이 `prev`와 같으면 제거 (연속 반복만 제거, 비연속 중복은 보존)
- 배치 내 연속 반복도 동일하게 제거
- long silence(≥5s) 및 화자 교체 시 상태 리셋

**테스트**
- 유닛 테스트: `uv run pytest tests/test_cross_batch_filter.py tests/test_metrics_segmentation.py -v` → 16/16 통과
- 결과 파일:
  - `.omc/benchmarks/eval_20260605_1_exp002.json`
  - `.omc/benchmarks/eval_20260605_2_exp002.json`
  - `.omc/benchmarks/eval_20260605_3_exp002.json`

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER |
|------|----------|----------|----------|
| 1회차 | 87.5% | 93.9% | 90.7% |
| 2회차 | 57.1% | 35.6% | 46.4% |
| 3회차 | 87.5% | 38.7% | 63.1% |
| **중앙값** | **87.5%** | **38.7%** | **63.1%** |

| 항목 | 베이스라인 (master) | Exp-002 (중앙값) | 변화 |
|------|-------------------|-----------------|------|
| sbs1 WER | 108.3% | 87.5% | **-20.8%p** |
| ytn1 WER | 47.9% | 38.7% | **-9.2%p** |
| 평균 WER | 78.1% | 63.1% | **-15.0%p** |
| 문장분리 F1 | 0.0% | 0.0% | 변화 없음 |

**정성 관찰**
- sbs1: 반복 아티팩트가 상당히 줄었으나 완전히 제거되지 않음. "미 미 미어어어" → 필터가 "미"를 한 번 남기고 "미어어어"는 다른 단어라 통과. 서브워드 수준의 반복("어어어")은 여전히 남음.
- ytn1: 한·영 코드스위칭 구간이 잘 보존됨. "-그 -그 -그" 패턴 대부분 제거됨.
- 2회차에서 sbs1 57.1%로 대폭 개선됐으나 1·3회차에서 87.5%로 회귀. 실행마다 반복 아티팩트 발생량이 크게 다름(모델 비결정성).
- 목표 수치(sbs1 < 60%, 평균 < 50%)에 도달하지 못함 — 연속 단어 반복 외에도 서브워드 반복이 주요 원인.

**결론**: **채택**
**이유**: 모든 채택 조건 충족(중앙값 WER 감소, WER 회귀 없음, pytest 통과, 두 파일 모두 개선). 단, 1차 목표에는 미달이므로 추가 개선 필요.
**다음 가설**: 서브워드/음절 수준 반복("어어어", "를를를")도 제거하는 방향으로 필터 확장, 또는 A-2(Silence 기반 조기 확정)으로 반복이 쌓이기 전에 세그먼트를 확정

---

## Exp-003: 한국어 종결어미 기반 문장 확정 + NFC 정규화

**날짜**: 2026-06-05
**정책**: simulstreaming
**가설**: Exp-002 이후 F1=0% 문제가 남았다. 원인은 두 가지:
① `tokens_alignment.py get_lines()`가 Silence 토큰(≥5초)에만 문장을 확정하므로, 일반 방송 음성의 0.5~1초 문장 간 침묵으로는 확정이 전혀 발생하지 않음.
② cross-batch 반복 필터(`_filter_cross_batch_repetitions`)의 문자열 비교가 Whisper NFD(분해형 자모) 출력과 NFC 패턴 사이 불일치로 일부 반복을 놓침.
→ 한국어 종결어미 패턴 감지를 `get_lines()` `else` 분기에 추가하면 Silence 없이도 문장이 확정되어 F1이 개선될 것이다. 동시에 NFC 정규화를 필터에 적용하면 반복 아티팩트도 더 정확히 제거된다.

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py` — `_normalize()` 메서드 추가 (NFC 변환), `_filter_cross_batch_repetitions()` 내 비교를 NFC로 통일 (유지됨)
- `whisperlivekit/tokens_alignment.py` — `unicodedata`, `re` import 추가 + `_KO_SENTENCE_END` 패턴 정의 + `get_lines()` `else` 분기에 종결어미/구두점 감지 확정 로직 추가 (기각으로 **롤백됨**)
- `whisperlivekit/audio_processor.py` — `MIN_SILENCE_SENTENCE_BOUNDARY_S=0.2` 시도 후 부작용으로 **원복됨**

**진단 과정 (주요 발견)**
- 포트 충돌: eval 초반에 이전 서버(base model)가 포트 8001 점유 → 올바른 서버가 시작되지 않고 기존 서버로 측정됨. 포트 정리 후 재측정.
- Whisper 토크나이저는 한국어를 NFD(분해형 자모)로 출력 → NFC 기반 regex 매칭이 항상 실패 → `unicodedata.normalize("NFC", ...)` 필요.
- 경로 A로 직접 테스트하면 F1 53% 달성 (한국어 종결어미 감지 정상 동작).
- 경로 C에서는 VBCable 브라우저 경로에서 "서버 처리 완료 신호 미수신" 경고가 반복 → 30초 타임아웃 초과 → F1 측정 불가.

**테스트**
- 유닛 테스트: `uv run pytest tests/` → 16/16 통과
- 결과 파일:
  - `.omc/benchmarks/eval_20260605_1_exp003_fixed.json`
  - `.omc/benchmarks/eval_20260605_2_exp003_fixed.json`
  - `.omc/benchmarks/eval_20260605_3_exp003_fixed.json`

**정량 결과 (경로 C, 3회 반복 — 포트 정리 후)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 95.8% | 99.4% | 97.6% | 0.0% |
| 2회차 | 96.4% | 99.4% | 97.9% | 0.0% |
| 3회차 | 95.8% | 99.4% | 97.6% | 0.0% |
| **중앙값** | **95.8%** | **99.4%** | **97.6%** | **0.0%** |

| 항목 | Exp-002 (중앙값) | Exp-003 (중앙값) | 변화 |
|------|----------------|-----------------|------|
| sbs1 WER | 87.5% | 95.8% | +8.3%p ↑ (회귀) |
| ytn1 WER | 38.7% | 99.4% | +60.7%p ↑ (회귀) |
| 평균 WER | 63.1% | 97.6% | +34.5%p ↑ (회귀) |
| F1 | 0.0% | 0.0% | 변화 없음 |

**경로 A 참고 (기준 아님, 코드 동작 확인용)**
- sbs1: F1 63.2% (목표 ≥60% 달성), WER 50.0%
- ytn1: F1 42.9%, WER 74.8%
- 평균 F1 53.0% — 경로 A에서는 한국어 종결어미 감지가 정상 동작함

**정성 관찰**
- 경로 C "서버 처리 완료 신호 미수신"이 매 측정마다 발생. tokens_alignment.py 변경 전에는 없던 경고.
- 경로 A에서는 세그먼트 분리가 정상 동작했으나, "." 단독 토큰이 별도 세그먼트로 만들어지는 부작용 확인.
- ytn1 WER 99.4% 는 반복 아티팩트가 폭발했음을 의미. 원인 확정 못함.

**결론**: **기각**
**이유**: 경로 C WER이 Exp-002 중앙값(63.1%) 대비 97.6%로 대폭 회귀. WER 회귀 ≤+5%p 기준을 크게 초과. 경로 C F1도 0%로 개선 없음.
**롤백**: `tokens_alignment.py` 종결어미 코드 전량 제거, `audio_processor.py` 침묵 임계값 원복. `backend.py` NFC 정규화는 WER에 영향 없으므로 유지.
**다음 가설**:
1. 경로 C 타임아웃 문제 근본 원인 파악 (서버가 30초 내 완료 신호를 못 보내는 이유)
2. 경로 C F1 측정 개선 (타임아웃 연장 또는 다른 측정 방법)
3. WER을 더 개선하기 위해 A-2(Silence 기반 조기 확정) 재검토

---

## Exp-004: 디코더 멈춤 복구 워치독 + 경로 C VBCable 하니스 결함 수정

**날짜**: 2026-06-06
**정책**: simulstreaming
**가설**: Exp-003이 남긴 두 미해결 문제 — ① 경로 C "서버 처리 완료 신호 미수신" 타임아웃, ② 후반부 "반복 아티팩트 폭발(원인 미확정)" 및 사용자 관찰 "첫 몇 단어만/전혀 전사 안 됨" — 은 서로 다른 두 결함에서 비롯된다고 보고 근본 원인을 규명한다.

**진단 (근본 원인)**
- GPU 정상: torch 2.8.0+cu128, `cuda.is_available()=True`, RTX 3080. 모델 기본 cuda 로드. "GPU 미사용"은 전사 멈춤의 *결과*였음(원인 아님).
- **디코더 멈춤(stall)**: 경로 C bad-run을 계측 로그로 포착(crun_1.log). 연속 발화가 ~30초 롤링 윈도우를 채우면 SimulStreaming 디코더가 영구히 0토큰 상태(`break=loop_end`, `most_attended=None`, `tok=0`)에 빠짐. `refresh_segment`는 ≥5초 침묵(`MIN_DURATION_REAL_SILENCE`)에서만 발동해 연속 발화에선 복구 불가 → 끝부분 유실. context는 정상 트림(~445)이라 오버플로 아님. 간헐적(경로 A 13/13 정상, 경로 C에서 발생).
- **"전혀 안됨" = 테스트 하니스 VBCable 결함**: `scripts/audio_device.py vbcable_audio_context`가 `is_vbcable_default()`(재생 장치만 검사)에 의존 → 재생이 이미 CABLE Input이면 녹음(CABLE Output) 설정을 건너뜀 → 브라우저 getUserMedia가 실제 마이크(무음) 캡처 → 전사 0. `run_browser_test`의 0.5초 레이스로 앞부분도 유실. (Exp-003의 "완료 신호 미수신" 타임아웃 정황도 이 무음/멈춤에서 비롯.)

**변경 내용** (브랜치 `phase2/fix-transcription-stall`)
- `whisperlivekit/simul_whisper/backend.py` — 디코더 멈춤 복구 워치독: 모듈 상수 `STALL_RECOVER_SEC=10.0`, `__init__`에 `_last_emit_end`, `process_iter()` 빈 결과 분기에 "오디오 전진 > 임계 & 0토큰 → `refresh_segment(complete=True)` 강제 복구", 토큰 방출/`end_silence`(long)/`new_speaker`에 baseline 갱신. (커밋 `79265dc`)
- `tests/test_stall_watchdog.py` — 워치독 단위 테스트 3개 신규.
- `scripts/audio_device.py:vbcable_audio_context` — 재생·녹음 각각 독립 검사·설정 + 둘 다 CABLE인지 재검증해 yield. (커밋 `476c026`)
- `scripts/vbcable_test.py:run_browser_test` — 0.5초 sleep → WebSocket OPEN 대기 루프로 레이스 제거. (커밋 `476c026`)

**검증**
- 워치독 단위테스트 3/3, `pytest tests/` 비-네트워크 전부 통과.
- 워치독 경로 A 스모크: 2회 발동·복구, 전사 끝까지(회귀 없음).
- 하니스 결정적 검증(브라우저 없이): 녹음을 비-CABLE(Jabra)로 강제해도 컨텍스트가 CABLE Output으로 교정 → "전혀 안됨" 수정 증명.
- 하니스 경로 C end-to-end 1회: 앞부분 유실 없음, 끝까지 도달(708자) → 무음 캡처 해소 확인.

**정량 결과 (단일 run 참고 — 경로 C 3회 중앙값 미완료)**

| run | 조건 | WER | 비고 |
|---|---|---|---|
| 워치독 경로 A 스모크 | fix | 55.95% | 워치독 2회 발동·복구 |
| fix 경로 C (하니스 전) | fix | 60.1% | 끝까지 전사 |
| fix 경로 C (하니스 후) | fix | 68.5% | 끝까지, 뒷부분 반복 환각 잔존 |

(주의: 채택 1차 기준인 경로 C 3회 중앙값 + baseline A/B는 fail-fast 중단으로 미완료.)

**정성 관찰**
- "전혀 안됨/첫 몇 단어"는 하니스 결함이었고 수정 후 재현 안 됨.
- 워치독: 경로 A에서 복구 목격, 경로 C에선 이번 run에 stall 미발생으로 복구 직접 목격은 다음 과제.
- **반복 환각("공급한 공급...")이 후반부 잔존 → WER 60~68%**. 남은 핵심 WER 동인.

**결론**: 하니스 수정 **채택**(결함·수정 증명, 양 PC 경로 C 측정 신뢰성 회복). 워치독 **조건부 보류**(경로 A 복구·무회귀 확인했으나 경로 C 3회 중앙값 미측정).
**이유**: 하니스 결함은 측정 신뢰성의 전제인 명백한 버그. 워치독은 무해한 안전망이나 정식 채택엔 경로 C 중앙값 필요.
**다음 가설**:
1. 경로 C 3회(fail-fast)로 하니스+워치독 상태의 진짜 baseline WER/F1 확보 → 워치독 정식 채택 판정.
2. 후반부 반복 환각(WER 주범) 근본 원인 → A-3(확정 후 중복 억제) 또는 디코더 반복 억제 강화.
3. master에 남은 wip-exp-004 종결어미 코드(`tokens_alignment.py`의 `unicodedata`/`_KO_SENTENCE_END` 미정의 → NameError로 no-op) 제거.


## Exp-005: 워치독 is_last=True flush

**날짜**: 2026-06-06
**정책**: simulstreaming
**가설**: `process_iter()` 워치독이 `refresh_segment(complete=True)`만 하고 디코더가 hold-back한 토큰을 버린다. `infer(is_last=True)`를 워치독 내에서 먼저 호출하면 held-back 토큰이 flush되어 WER이 개선될 것이다.

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py` — `process_iter()` 워치독 분기에 `flushed = self.model.infer(is_last=True)` 호출 후 토큰 반환 로직 추가
- `tests/test_stall_watchdog.py` — `side_effect` 기반 mock으로 변경 + `test_stall_flush_returns_pending_tokens` 테스트 추가 (4개 → 4개)

**진단 (사후 — 왜 실패했나)**
- AlignAtt `align_att_base.py`에서 "attention reaches end" 기준: `content_mel_len - most_attended_frame <= (4 if is_last else frame_threshold)`. 그런데 `frame_threshold = 4`이므로 is_last=True/False 모두 임계가 4로 동일.
- 결과: `infer(is_last=True)` 재호출이 `infer(is_last=False)`와 동일하게 동작 → held-back 토큰 없음 → 가설 오류.
- 진짜 경로 C WER 97% 원인: **Silero VAD가 VBCable 루프백 오디오를 침묵으로 분류** → 첫 2~3초 이후 오디오가 transcription_queue에 진입 안 됨.

**테스트**
- 유닛 테스트: `uv run pytest tests/test_stall_watchdog.py -v` → 4/4 통과
- 결과 파일:
  - `.omc/benchmarks/eval_exp005_r1.json`
  - `.omc/benchmarks/eval_exp005_r2.json`
  - `.omc/benchmarks/eval_exp005_r3.json`

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER |
|------|----------|----------|----------|
| 1회차 | 97.6% | 99.4% | 98.5% |
| 2회차 | 97.0% | 99.4% | 98.2% |
| 3회차 | 98.2% | 99.4% | 98.8% |
| **중앙값** | **97.6%** | **99.4%** | **98.5%** |

| 항목 | Exp-004 유효 베이스라인 | Exp-005 | 변화 |
|------|----------------------|---------|------|
| sbs1 WER | ~97% | 97.6% | 변화 없음 |
| ytn1 WER | ~99% | 99.4% | 변화 없음 |
| F1 | 0.0% | 0.0% | 변화 없음 |

**결론**: **기각**
**이유**: 가설이 잘못됨. is_last 차이가 없어 flush 효과 없음. WER 99%→97% 수준 그대로.
**다음 가설**: VBCable 오디오가 Silero VAD threshold(0.5)를 통과 못 함 → threshold 낮춤(→ Exp-006)

---

## Exp-006: VAD threshold 0.3 + MIN_DURATION_REAL_SILENCE 0.5

**날짜**: 2026-06-06
**정책**: simulstreaming
**가설**: 경로 C WER 97% + F1 0% 원인 두 가지:
① **Silero VAD threshold=0.5**: VBCable 루프백 오디오는 speech_prob ≈ 0.4 → 첫 문장 일시정지 후 triggered=False 상태에서 0.4 < 0.5로 "start" 신호 없음 → current_silence 영구 유지 → 오디오 큐 진입 불가 → WER 97%.
② **MIN_DURATION_REAL_SILENCE=5**: 뉴스 문장간 0.5~1초 휴지는 Silence 토큰 생성 기준(5초) 미달 → 문장 확정 없음 → F1 0%.

threshold=0.3으로 낮추면 VBCable speech_prob=0.4 오디오가 통과. MIN_DURATION_REAL_SILENCE=0.5로 낮추면 0.5초+ 휴지에서 Silence 토큰 생성 → 문장 확정.

**변경 내용**
- `whisperlivekit/audio_processor.py:26` — `MIN_DURATION_REAL_SILENCE = 5` → `0.5` (주석도 정정)
- `whisperlivekit/audio_processor.py:99,101` — `FixedVADIterator(...)` 두 곳 모두 `threshold=0.3` 추가

**테스트**
- 결과 파일: (측정 후 기입)

**테스트**
- 결과 파일: 3회 모두 "처리 완료 신호 미수신" — 아래 참조

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 | 비고 |
|------|----------|----------|----------|----|------|
| 1회차 | ~97.0% | ~99.4% | ~98.5% | 0.0% | 신호 미수신, 6~8단어만 전사 |
| 2회차 | ~97.0% | ~99.4% | ~98.5% | 0.0% | 동일 |
| 3회차 | ~97.0% | ~99.4% | ~98.5% | 0.0% | 동일 |
| **중앙값** | **97.0%** | **99.4%** | **98.5%** | **0.0%** | **측정 무효** |

**⚠️ 측정 무효 판정**: 모든 3회 실행이 "처리 완료 신호 미수신(30초 타임아웃)" 패턴으로 실패. VAD threshold 변경과 무관하게 `eval.py`의 구조적 결함이 원인으로 확인됨.

**근본 원인 분석** (Exp-007에서 수정):
- `eval.py` `start_server()`가 `stdout=subprocess.PIPE, stderr=subprocess.STDOUT`으로 서버를 기동
- eval.py는 `proc.stdout` 파이프를 절대 읽지 않음
- 108초 분량 오디오 처리 중 서버 로그가 64KB 파이프 버퍼를 채움
- 버퍼 가득 → 서버의 `logging.info()` 호출이 블로킹 → asyncio 이벤트 루프 동결
- 이벤트 루프 동결 → WebSocket 수신 불가 → "ready_to_stop" 전송 불가 → 타임아웃

Exp-004 수동 테스트(서버 직접 실행, stdout 터미널 표시)에서 WER 60~68%로 동작했던 것과 자동 eval에서 항상 실패하는 것이 이 원인으로 설명됨.

**결론**: **기각** (측정 무효 — eval 파이프 블로킹으로 인한 서버 동결)
**이유**: VAD threshold 변경 자체의 효과를 측정할 수 없었음. 수정이 유효한지 불명확.
**다음 가설**: eval.py `start_server()` `stdout=subprocess.PIPE` → `subprocess.DEVNULL`로 변경하면 서버가 동결되지 않아 정상 측정 가능 → Exp-007에서 검증. Exp-007은 이 실험(threshold=0.3, MIN_SILENCE=0.5)을 그대로 유지하며 eval 하니스만 수정.

---

## Exp-007: eval 파이프 블로킹 수정 + VAD threshold 0.3 재측정

**날짜**: 2026-06-06
**정책**: simulstreaming
**가설**: Exp-005/006에서 "처리 완료 신호 미수신" 패턴이 반복된 원인은 VAD threshold 문제가 아니라
`eval.py` `start_server()`의 `stdout=subprocess.PIPE`다. eval.py는 `proc.stdout`을 읽지 않아
파이프 버퍼가 꽉 차면 서버의 asyncio 이벤트 루프가 동결됨.
`subprocess.DEVNULL`로 변경하면 서버가 정상 동작하고, Exp-006의 VAD threshold=0.3 변경 효과를
처음으로 올바르게 측정할 수 있을 것.

**변경 내용**
- `scripts/eval.py:99` — `stdout=subprocess.PIPE, stderr=subprocess.STDOUT` → `stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL`
- (Exp-006 변경 그대로 유지: `audio_processor.py` threshold=0.3, MIN_DURATION_REAL_SILENCE=0.5)

**테스트**
- 결과 파일: (측정 후 기입)

**테스트**
- 결과 파일:
  - `.omc/benchmarks/eval_exp007_r1.json`
  - `.omc/benchmarks/eval_exp007_r2.json`
  - `.omc/benchmarks/eval_exp007_r3.json`

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 64.3% | 25.8% | 45.0% | 51.0% |
| 2회차 | 95.2% | 27.6% | 61.4% | 39.6% |
| 3회차 | 79.2% | 25.8% | 52.5% | 44.9% |
| **중앙값** | **79.2%** | **25.8%** | **52.5%** | **44.9%** |

| 항목 | Exp-002 채택 베이스라인 | Exp-007 (중앙값) | 변화 |
|------|----------------------|-----------------|------|
| sbs1 WER | 87.5% | 79.2% | **-8.3%p** |
| ytn1 WER | 38.7% | 25.8% | **-12.9%p** |
| 평균 WER | 63.1% | 52.5% | **-10.6%p** |
| 문장분리 F1 | 0.0% | 44.9% | **+44.9%p** |

**정성 관찰**
- sbs1 편차 큼: 1회차 64.3%에서 2회차 95.2%로 급등. 서버 동결은 아님(완료 신호 정상 수신) — 반복 아티팩트 비결정성 때문.
- ytn1은 안정적: 3회 모두 25.8~27.6% WER. VAD threshold=0.3으로 이전(38.7%)보다 일관 개선.
- F1이 처음으로 44.9%로 진입. MIN_SILENCE=0.5가 뉴스 문장 간 0.5~1초 휴지를 확정 신호로 포착한 결과.
- 목표(avg WER < 50%, F1 ≥ 60%) 미달. WER은 0.5%p 차이로 아쉽게 초과. F1은 15.1%p 추가 개선 필요.

**결론**: **채택** (목표 미달이나 Exp-002 대비 전 항목 개선, 합당한 진전)
**이유**: eval.py 파이프 수정으로 측정 하니스가 안정화됐고 VAD/Silence 임계치 변경으로 WER 10.6%p, F1 +44.9%p 개선. 목표는 미달이나 지금까지 가장 큰 단일 개선. 하니스 수정은 모든 후속 실험에 필수이므로 단독으로도 채택.
**다음 가설**: ① sbs1 반복 아티팩트 분산이 크다 → 2회차 95.2%의 원인 진단(반복 토큰 급등?) → Exp-008에서 반복 필터 강화 or ② F1 44.9%→60%+ 개선 — MIN_SILENCE=0.5가 문장 시작 직후(짧은 절 경계)에 오발동하는지 확인 후 최소 토큰 수 조건 추가 고려

---

## Exp-008: VAD end_threshold 비대칭 설정 — 노이즈 차단 (기각)

**날짜**: 2026-06-06 / **결론**: **기각**

Exp-007 sbs1 `-그러니까` 환각 원인을 VBCable 노이즈(speech_prob≈0.2)가 end_threshold=0.15를 넘어 디코더에 유입되는 것으로 가정. end_threshold=0.35 설정 시 실발화 speech_prob≈0.4와 너무 가까워 발화 중 단어 경계에서 가짜 silence 이벤트 과다 발생 → 디코더 반복 리셋 → WER 폭발(113.7%, 149.4%). Exp-009에서 VAD 파라미터가 아닌 반복 루프 감지로 접근.

---

## Exp-009: 반복 루프 감지 + refresh_segment() 리셋

**날짜**: 2026-06-06
**정책**: simulstreaming
**가설**: Exp-007 sbs1의 `-그러니까` 환각은 VAD 문제가 아닌 **모델 반복 루프** 문제다.
영어 코드스위칭 구간에서 모델이 한국어 환각을 생성하다 같은 단어를 반복 생성하는 루프에 빠진다.
최근 방출된 20개 토큰 중 동일 단어가 5회 이상 등장하면 반복 루프로 판정,
`refresh_segment()`로 디코더를 리셋해 루프를 차단하면 sbs1 WER이 개선되고
F1도 함께 개선될 것이다 (환각에 의한 가짜 문장 경계 감소).

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py`
  - `__init__`: `_LOOP_WINDOW=20`, `_LOOP_THRESHOLD=5`, `_recent_tokens: deque(maxlen=20)` 추가
  - `end_silence()` long_silence 시 `_recent_tokens.clear()` 추가
  - `new_speaker()` 시 `_recent_tokens.clear()` 추가
  - `_detect_repetition_loop()` 메서드 추가 (Counter 기반 밀도 감지)
  - `process_iter()`: 토큰을 `_recent_tokens`에 추가 후 루프 감지; True면 `refresh_segment()` + 빈 결과 반환

**테스트**
- 결과 파일: `.omc/benchmarks/eval_exp009_r1.json`

**정량 결과 (경로 C)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 65.5% | 95.7% | 80.6% | 27.1% |

**결론**: **기각** (fail-fast 적용). ytn1 WER 95.7% — 기준선(25.8%) 대비 극심한 퇴행.
밀도 기반 감지(20-window 중 5회 = 25%)가 정상 뉴스 발화에서 false positive 다수 발생.
뉴스에서 "시간" 같은 단어가 non-consecutive하게 5회 이상 등장 → 정상 발화를 루프로 오판.
Exp-010에서 연속(consecutive) 감지 방식으로 전환: 마지막 K개 토큰이 연속으로 동일한 단어면 루프 판정.

---

## Exp-027: 하이픈 프리픽스 단어 반복 억제

**날짜**: 2026-06-06
**정책**: SimulStreaming
**상태**: 기각

**가설**: 하이픈-프리픽스 단어(`-그러`, `-그러로` 등) 반복 루프가 WER의 원인. 짧은 하이픈 접두 단어 ≥4회 연속 시 억제.

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py` — `_filter_cross_batch_repetitions`에 `_consecutive_short_hyphen` 카운터 + 억제 로직 추가; `_HALLUCINATION_HYPHEN_THRESHOLD = 4`

**정량 결과 (경로 C)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 78.6% | 65.6% | 72.1% | 35.4% |
| **중앙값** | **78.6%** | **65.6%** | **72.1%** | **35.4%** |

(fail-fast 적용 — 1회차 결과로 기각 판정)

| 항목 | 채택 베이스라인 | Exp-027 | 변화 |
|------|----------------|---------|------|
| 평균 WER | 74.5% | 72.1% | -2.4%p (자연 분산 내) |
| F1 | 39.8% | 35.4% | -4.4%p |

**정성 관찰**: 실제 실행에서 타깃 패턴("-그러 -그러로")이 아닌 "스스스스스...", "브브브브브..." 단일음절 반복이 발생 → 하이픈 필터 무력화

**결론**: **기각**
**이유**: 설계 당시 가정한 환각 패턴(-그러)이 실제 실행에서 나타나지 않고 다른 단일음절 반복 패턴이 발생. 필터 작동 안 함.
**다음 가설**: 단일음절 반복 토큰 자체를 `_max_char_run` 기반으로 억제

---

## Exp-028: 단일음절 연속 반복 억제 + context 리셋

**날짜**: 2026-06-06
**정책**: SimulStreaming
**상태**: 채택

**가설**: 단일음절 연속 반복 토큰("스스스스스", "브브브브브", "감사스스스스스스스스스스스스스스")을 `_max_char_run >= 4` 기준으로 억제하고, 억제 카운터 ≥5이면 context 리셋으로 환각 피드백 루프를 끊는다.

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py`
  - 클래스 상수: `_CHAR_RUN_THRESHOLD = 4`, `_HALLUCINATION_RESET_THRESHOLD = 5`
  - `__init__`: `self._consecutive_char_repeat: int = 0`
  - `end_silence`/`new_speaker`/stall recovery: `_consecutive_char_repeat` 리셋
  - `_max_char_run` 정적 메서드 추가
  - `_filter_cross_batch_repetitions` 교체: char-run 감지 + context 리셋 로직 포함

**테스트**
- 유닛 테스트: `uv run pytest` → 27/27 통과

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 54.8% | 29.4% | 42.1% | 50.0% |
| 2회차 | 66.7% | 84.7% | 75.7% | 26.7% |
| 3회차 | 93.5% | 30.1% | 61.8% | 45.1% |
| **중앙값** | **66.7%** | **30.1%** | **61.8%** | **45.1%** |

| 항목 | 채택 베이스라인 | Exp-028 (중앙값) | 변화 |
|------|----------------|-----------------|------|
| 평균 WER | 74.5% | 61.8% | **-12.7%p** |
| F1 | 39.8% | 45.1% | **+5.3%p** |

**정성 관찰**
- 단일음절 반복 제거 효과 확인 (일부 run에서 ytn1 WER 30% 근처 달성)
- 잔존 문제: "시원한 시원한 시원한", "사이의 사이의 사이의", "통해 통해 통해" 등 구절 수준 반복 미제거
- sbs1 분산 큼 (R1 54.8% → R3 93.5%): 구절 반복이 sbs1에서 더 심하게 발생

**결론**: **채택**
**이유**: 베이스라인 대비 WER -12.7%p 개선. 단일음절 필터 효과 확인. 구절 반복은 별도 실험으로 해결.
**다음 가설**: 슬라이딩 윈도우 단어 빈도 필터로 구절 수준 반복 억제

---

## Exp-029: 슬라이딩 윈도우 단어 빈도 필터

**날짜**: 2026-06-06
**정책**: SimulStreaming
**상태**: 기각

**가설**: Exp-028의 단일음절 필터에 슬라이딩 윈도우 단어 빈도 필터를 추가해 구절 수준 반복("시원한 시원한 시원한", "사이의 사이의 사이의")을 억제한다. 파라미터: `_WORD_WINDOW_SIZE=20`, `_WORD_FREQ_THRESHOLD=4`, 최소 단어 길이 2자.

**변경 내용**
- `whisperlivekit/simul_whisper/backend.py`
  - 클래스 상수 `_WORD_WINDOW_SIZE = 20`, `_WORD_FREQ_THRESHOLD = 4` 추가
  - `self._recent_words: list = []` 추가
  - `end_silence`/`new_speaker`/stall recovery/context 리셋 시 `_recent_words.clear()` 추가
  - `_filter_cross_batch_repetitions`에 단어 빈도 체크 추가

**테스트**
- 결과 파일: `.omc/benchmarks/eval_exp029_r1.json`

**정량 결과 (경로 C)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 59.5% | 99.4% | 79.5% | 35.8% |

(fail-fast 중단 — ytn1 99.4% catastrophic)

| 항목 | 채택 베이스라인 (Exp-028) | Exp-029 | 변화 |
|------|--------------------------|---------|------|
| 평균 WER | 61.8% | 79.5% | +17.7%p ↑ (회귀) |
| F1 | 45.1% | 35.8% | -9.3%p |

**정성 관찰**
- ytn1 R1 전사가 완전히 영어로 전사됨 (언어 감지 실패 + 필터가 영어 단어도 억제)
- "in", "foreign", "language" 등 영어 전치사가 `len(stripped) >= 2` 조건에 포함되어 반복 억제됨
- 파라미터 threshold=4, window=20이 지나치게 공격적

**결론**: **기각**
**이유**: 단어 빈도 필터가 영어 단어도 억제 + 파라미터 과공격적 → ytn1 99.4% catastrophic
**다음 가설**: 한국어 단어에만 빈도 필터 적용 (U+AC00-U+D7A3 범위 감지) + 완화된 파라미터(threshold=5, window=25)

---

## Exp-030: 슬라이딩 윈도우 한국어 전용 빈도 필터

**날짜**: 2026-06-06
**정책**: SimulStreaming
**상태**: 기각

**가설**: Exp-029(단어 빈도 필터 과공격적)의 수정 버전. 한국어 단어에만 빈도 필터 적용(`_KO_CHAR = re.compile(r'[가-힣]')`). 파라미터 완화: `threshold=5, window=25`.

**변경 파일**: `whisperlivekit/simul_whisper/backend.py`
- `import re` 추가
- `_WORD_WINDOW_SIZE=25`, `_WORD_FREQ_THRESHOLD=5`, `_KO_CHAR=re.compile(r'[가-힣]')` 추가
- 빈도 필터 조건: `_KO_CHAR.search(stripped) and count >= 5`

**정량 결과**:
- eval을 올바른 방법(exp-030 cwd + main venv Python)으로 실행 → R1: sbs1 89.3%, ytn1 85.3%, avg WER **87.3%**, F1 35.4%
- 베이스라인(74.5%)보다 12.8%p 악화 → catastrophic

**근본 원인 분석**:
- exp-028/030은 phase2/exp-016을 베이스로 함
- phase2/exp-016의 backend.py에는 master에 있는 Exp-009 반복 루프 감지 코드(`_LOOP_WINDOW`, `_LOOP_THRESHOLD`, `deque`)가 없음
- 따라서 exp-030 베이스 자체가 master(Exp-009 포함)보다 성능이 낮음
- 이전 eval이 main cwd(master 코드)로 실행되어 베이스라인 수치가 실제 exp-016 코드와 다름

**결론**: **기각**
**이유**: eval 코드 실행 환경 오류로 인해 exp-028/029/030 모두 master 코드(exp-009 포함) 대비 열등한 코드 베이스. 올바른 접근은 master 브랜치 위에 char-run 필터 추가
**다음 가설**: master 베이스에서 Exp-031 — char-run 단일음절 필터만 추가 (KO 빈도 필터 제외, exp-009 반복 루프 감지와 시너지)

---

## Exp-031: master char-run 단일음절 필터

**날짜**: 2026-06-06
**정책**: SimulStreaming
**상태**: 기각

**가설**: master 베이스(exp-009 반복 루프 감지 포함) 위에 단일음절 char-run 환각 억제 필터를 추가하면 exp-009의 word-level 반복 감지와 시너지로 WER 개선.

**변경 파일**: `whisperlivekit/simul_whisper/backend.py`
- `_CHAR_RUN_THRESHOLD=4`, `_HALLUCINATION_RESET_THRESHOLD=5` 클래스 변수 추가
- `self._consecutive_char_repeat: int = 0` 상태 변수 추가
- `_max_char_run(text)` 정적 메서드 추가
- `_filter_cross_batch_repetitions()`: char-run 토큰 억제 + 5회 연속 시 context 리셋

**베이스**: master 브랜치 (exp-009 반복 루프 감지 코드 포함)

**정량 결과 (경로 C, 3회 반복)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 61.3% | 25.8% | 43.5% | 52.1% |
| 2회차 | 58.9% | 75.5% | 67.2% | 29.2% |
| 3회차 | 50.6% | 145.4% | 98.0% | 37.7% |
| **중앙값** | **58.9%** | **75.5%** | **67.2%** | **37.7%** |

**실패 분석 (R3 ytn1 145.4%)**:
- "I am a member of a member... I'm a member who is... I am a member who is an international member..." 패턴의 점진적 반복 환각
- char-run 필터는 단일문자 반복(스스스스)에만 반응
- `_LOOP_THRESHOLD=5` (20토큰 창에서 동일 단어 5회)는 "member"가 3-4회 등장하는 점진적 반복은 못 잡음
- ytn1의 한영 혼용 콘텐츠에서 language confusion → hallucination cascade

**결론**: **기각**
**이유**: 중앙값 WER 67.2%, F1 37.7%. 목표(WER < 30%, F1 ≥ 60%) 미달. char-run 필터 효과는 있으나(R1: 43.5%) 점진적 phrase-level 반복에 취약.
**다음 가설**: Exp-032 — `_LOOP_THRESHOLD` 5→3으로 낮춰 점진적 반복 루프를 더 빨리 감지

---

## Exp-032: _LOOP_THRESHOLD 5→3 (과공격 기각)

**날짜**: 2026-06-06
**정책**: SimulStreaming
**상태**: 기각

**가설**: exp-031(char-run 필터 + LOOP_THRESHOLD=5)에서 점진적 반복("member" 패턴)이 threshold=5를 채우기 전에 다수 방출됨. threshold=3으로 낮춰 조기 감지.

**변경 파일**: `whisperlivekit/simul_whisper/backend.py`
- `_LOOP_THRESHOLD=3` (exp-031의 5에서 변경)

**정량 결과 (경로 C)**

| 측정 | sbs1 WER | ytn1 WER | 평균 WER | F1 |
|------|----------|----------|----------|----|
| 1회차 | 53.0% | 57.7% | 55.3% | 29.2% |
| 2회차 | 57.1% | 75.5% | 66.3% | 12.5% |
| 3회차 | 미실행 | 미실행 | 미실행 | 미실행 |

(R1+R2 패턴에서 기각 결론 — R3 미실행)

**실패 분석**:
- threshold=3은 과공격적: 일반 영어 텍스트에서 "a", "the", "of", "I" 등이 3회 나오는 경우도 리셋 트리거
- F1 급락(12.5%): 빈번한 context 리셋으로 문장이 중단되어 완성된 라인 수 감소
- exp-031 R1 최고 성능(43.5%, F1 52.1%)보다 나빠짐: threshold=3이 good case를 방해

**결론**: **기각**
**이유**: F1 12-29%(exp-031 중앙값 37.7% 대비 악화). threshold=3은 과공격적
**다음 가설**: Exp-033 — threshold=4 (중간값 탐색)

---

## 실험 템플릿 (신규 항목 작성 시 복사)

```markdown
## Exp-N: [제목]

**날짜**: YYYY-MM-DD
**정책**: simulstreaming / localagreement
**가설**: 왜 이 변경이 필요한가 — 어떤 문제를 해결하려 했는가

**변경 내용**
- `파일경로:라인번호` — 무엇을 어떻게 바꿨는가
- (추가 변경 항목)

**테스트**
- 샘플: test_data/XXX.mp3 (Xs)
- 명령어: `uv run python scripts/bench_phase2_policies.py --sample test_data/XXX.mp3`
- 결과 파일: .omc/benchmarks/phase2_XXX.md

**정량 결과**

| 항목 | 이전 (Exp-N-1) | 이번 (Exp-N) |
|---|---|---|
| WER | | |
| avg latency | | |
| p95 latency | | |
| 영문 매치 | | |

**정성 관찰**: 환각, 단어 유실, 코드 스위칭, 체감 지연 등 주관적 인상

**결론**: 채택 / 기각 / 수정 예정
**이유**: 한 줄 요약
**다음 가설**: 이 결과를 보고 다음에 뭘 시험할지
```
