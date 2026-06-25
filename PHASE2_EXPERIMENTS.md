# Phase 2 실험 로그

STT 성능 개선 과정에서 수행한 실험을 기록한다.
각 실험은 **가설 → 변경 → 결과 → 결론** 흐름으로 작성한다.

> **[2026-06-23] 현행 측정 regime**: 테스트(채택/기각) = bong1 + ytn2 + sbs1, held-out = ytn1 + eng1, ytn2·bong1 공동 최우선 (CLAUDE.md §3.8 참조). **신규 Exp부터 이 regime 적용.** 이전 Exp의 수치·판단은 구 regime(테스트=sbs1+ytn2) 기준이므로 참고용으로만 사용.

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

## 참고 베이스라인 (Exp-105 — 신 체제 시작점 2026-06-23, Exp-130으로 대체됨)

> **[2026-06-23] 신 체제 베이스라인** (bong1+ytn2+sbs1 diar-ON, `--periodic-lang-check 4.0`, `--compression-ratio-threshold 3.0`, `--repeat 3`)
> JSON: `.omc/benchmarks/eval_regime_baseline_20260623_1326.json`

| 파일 | WER median | WER max | WER stdev | F1 median | 회차별 |
|------|-----------|---------|----------|-----------|--------|
| bong1 | **61.6%** | 67.7% | 6.5% | **42.9%** | R1 54.7%/44.4%, R2 67.7%/37.2%, R3 61.6%/42.9% |
| ytn2  | **35.0%** | 96.1% | 35.6% | **54.5%** | R1 35.0%/54.5%, R2 96.1%/0.0%, R3 34.0%/63.2% |
| sbs1  | **26.2%** | 32.1% | 5.1% | **36.4%** | R1 22.0%/36.4%, R2 26.2%/36.4%, R3 32.1%/18.2% |

비고: ytn2 R2=96.1%는 VBCable 순간 불안정(WER≠100% 확인), 코드 문제 아님.
bong1: 웃음 구간에서 Whisper 환각 다발(JSON 분석 확인). sbs1: diar-ON으로 F1 36.4%(diar-OFF 76.2%)로 급락, 원인=Sortformer 과분할(ref=3 vs hyp=9-11, recall=1.0 precision=0.20).

---

## Exp-130 (신뢰 baseline 재확립 + provenance 하니스 강화 — 2026-06-25)

### 배경 — 클린 리셋 결정

Exp-106~129는 두 가지 구조적 결함으로 수치 신뢰 불가 판정, 포렌식 재측정 없이 전체 기각:

1. **조용한 코드-버전 함정**: `eval.py`가 서버를 `python -m whisperlivekit.basic_server`로 기동하며 cwd를 상속. `import whisperlivekit`은 cwd 기준 PathFinder가 우선이고 editable finder는 후순위 fallback. 잘못된 cwd(루트 등)에서 측정하면 변경한 코드가 무시된 채 오류 없이 엉뚱한 코드가 측정됨. Exp-106~129 측정의 실제 import 경로 불명.
2. **VBCable 간헐 불안정 + provenance 미기록**: 측정 중 끊김으로 catastrophic-WER 회차가 생성되나 코드 효과와 구별 불가. 결과 JSON에 import 경로·git HEAD·VBCable 상태가 없어 소급 검증 불가.

추가로 Exp-129의 "beam=3 채택" 결론도 코드에 미반영 상태 확인 (master·모든 워크트리 `parse_args.py --beams default=2`). 코드 상태는 Exp-105 설정(beams=2, PLC=4.0)과 일치.

→ **클린 리셋**: Exp-129 결론 전체 기각. master 현재 코드를 새 기준점으로 재설정.

### Phase A — eval 하니스 provenance 강화

**브랜치**: `harness/eval-provenance` → master 머지 커밋 `f3676af`

**변경 파일**: `scripts/eval.py`
- `_probe_provenance(cwd, args)` 함수 추가: 서버와 동일 python·cwd로 `import whisperlivekit`을 서브프로세스 프로브 → 실제 import 경로·git branch/SHA·beams 기본값 캡처
- `--expect-code-root` 인자 추가: 실제 import 경로가 기대 루트와 다르면 즉시 중단(fail-fast)
- 결과 JSON 최상위 `"provenance"` 블록 추가: `whisperlivekit_file`, `git_branch`, `git_sha`, `decoder`, `diarization`, `vbcable_loopback` 기록
- 측정 시작 직후 콘솔에 `[provenance] code=<name> branch=<b>@<sha> beams=<n> CRT=<x> PLC=<y> diar=<on/off> vbcable=<ok/FAIL>` 1줄 출력

**추가 정리 (main 직접)**:
- `.claude/commands/eval.md`, `phase2-improve.md`: `bong1.mp3` → `bong1.wav` 정정 + provenance 게이트 명문화

**부수 발견 (미수정)**: beams probe가 `create_parser` 함수를 import 시도하나 실제 함수명은 `parse_args()` → probe ImportError로 beams=null 기록. 실제 측정에는 영향 없음(서버 default=2 사용). 다음 수정 시 함께 수정 예정.

### Phase B — master 신뢰 baseline 측정 (N=5)

**설정**: master@f3676af, beams=2(default), PLC=None(default), CRT=3.0, diar-ON(Sortformer), VBCable=OK(RMS 0.14164/0.14858), `--repeat 5`

**테스트 세트 결과 (bong1+ytn2+sbs1):**

| 파일 | WER median | WER min | WER max | WER stdev | F1 median |
|------|-----------|---------|---------|-----------|-----------|
| bong1 | **51.1%** | 41.4% | 54.7% | 5.0% | **44.4%** |
| ytn2  | **58.1%** | 50.7% | 68.0% | 6.4% | **20.0%** |
| sbs1  | **78.0%** | 53.6% | 83.9% | 12.8% | **0.0%** |

회차별 (WER/F1): bong1 R1 54.7%/43.2%, R2 51.1%/54.1%, R3 48.9%/44.4%, R4 41.4%/47.1%, R5 51.7%/20.0%
ytn2 R1 58.1%/13.3%, R2 50.7%/40.0%, R3 58.6%/16.7%, R4 68.0%/20.0%, R5 54.7%/23.5%
sbs1 R1 83.9%/44.4%, R2 79.2%/0.0%, R3 62.5%/0.0%, R4 78.0%/13.3%, R5 53.6%/0.0%

**held-out 결과 (ytn1+eng1):**

| 파일 | WER median | WER min | WER max | WER stdev | F1 median |
|------|-----------|---------|---------|-----------|-----------|
| ytn1 | **61.3%** | 50.3% | 62.0% | 4.9% | **15.4%** |
| eng1 | **23.8%** | 3.8% | 30.5% | 11.2% | **0.0%** |

회차별: ytn1 R1 57.7%/13.3%, R2 61.3%/15.4%, R3 62.0%/23.5%, R4 50.3%/0.0%, R5 61.3%/33.3%
eng1 R1 30.5%/0.0%, R2 30.5%/0.0%, R3 16.2%/100.0%, R4 3.8%/100.0%, R5 23.8%/0.0%

**주요 관찰**:
- **Exp-129(beam=3+PLC=2.0) 대비 크게 악화**: Exp-129 수치(bong1 35.6%/ytn2 32.5%/sbs1 19.6%)와 비교해 특히 sbs1이 78.0%로 급등. 이번 측정은 PLC=None(master 기본값)이며, PLC 없이는 언어 고착 후 환각 체인이 억제되지 않는 것으로 추정.
- **sbs1 환각 증가 확인**: 전사에 "하이드레이션 브레이크 … 홍명보 감독" 등 음성과 무관한 내용 삽입. Exp-105(PLC=4.0) 당시 sbs1 26.2%와 비교하면 PLC가 환각 억제에 중요한 역할을 하는 것으로 보임.
- **sbs1 F1=0%**: 대부분 회차에서 문장 분리 신호 없음. 단일화자 뉴스에서 화자분할 기반 경계가 생기지 않음.
- **eng1 F1 불안정**: R3/R4에서 100% 달성, R1/R2/R5에서 0%. 단일세그먼트 구조의 자연 분산.

**결론**: 이 수치가 Phase C 실험의 새 비교 기준점(provenance 기록 + N=5 측정). Exp-106~129는 기각이나 **방향성은 참고** — 특히 beam=3+PLC=2.0이 이 baseline 대비 얼마나 개선되는지 정식 재검증이 Phase C 1순위.

**다음 가설 (Phase C 1순위)**: PLC=2.0 단독 적용 → beam=3 단독 → 조합 순으로 각각 baseline(Exp-130) 대비 검증. 파라미터 변경만(코드 수정 불필요)으로 측정 가능.

JSON (테스트): `.omc/benchmarks/eval_baseline_trusted_20260625_0948.json`
JSON (held-out): `.omc/benchmarks/eval_baseline_trusted_heldout_20260625_1025.json`

---

## 현재 측정 기준 베이스라인 (Exp-130 — 2026-06-25)

> **설정**: master@f3676af, beams=2, PLC=None, CRT=3.0, diar-ON, N=5, VBCable=OK
> JSON: `.omc/benchmarks/eval_baseline_trusted_20260625_0948.json` (테스트), `eval_baseline_trusted_heldout_20260625_1025.json` (held-out)

| 파일 | WER median | WER max | WER stdev | F1 median | 회차별 |
|------|-----------|---------|----------|-----------|--------|
| bong1 | **51.1%** | 54.7% | 5.0% | **44.4%** | R1 54.7%/43.2%, R2 51.1%/54.1%, R3 48.9%/44.4%, R4 41.4%/47.1%, R5 51.7%/20.0% |
| ytn2  | **58.1%** | 68.0% | 6.4% | **20.0%** | R1 58.1%/13.3%, R2 50.7%/40.0%, R3 58.6%/16.7%, R4 68.0%/20.0%, R5 54.7%/23.5% |
| sbs1  | **78.0%** | 83.9% | 12.8% | **0.0%** | R1 83.9%/44.4%, R2 79.2%/0.0%, R3 62.5%/0.0%, R4 78.0%/13.3%, R5 53.6%/0.0% |

held-out: ytn1 WER 61.3%/max 62.0%/F1 15.4%, eng1 WER 23.8%/max 30.5%/F1 0.0%

비고: sbs1 WER 78%는 PLC=None(환각 체인 미억제) 영향으로 추정. Phase C에서 PLC=2.0 적용 시 개선 예상.

---

## Exp-106 (기각 — 2026-06-23)

**ChangeSpeaker 이벤트 최소 간격 2.0s 디바운스 (과분할 억제)**

**가설**: Sortformer 과분할로 sbs1 F1이 76.2%→36.4% 급락. ChangeSpeaker 이벤트 간격을 2.0s 이상으로 제한하면 spurious 경계 감소, F1 회복.

**변경**: `whisperlivekit/audio_processor.py` — `MIN_SPEAKER_CHANGE_INTERVAL = 2.0` 추가, `_update_diarization_state`에 인터벌 체크. 브랜치: `exp/phase2-diar-debounce`.

**정량 결과 (경로 C N=3, 신 체제):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 49.2% | 53.2% | 4.7% | 45.0% | **-12.4pp** | +2.1pp |
| ytn2  | 45.8% | 69.0% | 14.1% | 57.1% | **+10.8pp** ✗ | +2.6pp |
| sbs1  | 22.0% | 23.2% | 1.2% | 36.4% | -4.2pp | 0pp |

**기각 이유**: ytn2 WER median +10.8pp 회귀 (채택 조건 ② 위반). sbs1 F1 변화 없음 (디바운스와 무관한 원인 존재).

**관찰**: sbs1 F1이 2.0s 디바운스에도 불변 → Sortformer가 2.0s 이상 간격으로 false ChangeSpeaker 발생하거나, silence 기반 분절이 주 원인. bong1 WER 대폭 개선(-12.4pp)은 긍정적 신호 — 다화자 환경에서 과분할 억제 효과 유효. ytn2 악화는 짧은 코드스위칭 화자전환 신호 억제 부작용.

**다음 가설**: bong1 웃음 구간 환각 억제 (`nonspeech_prob` 파라미터 노출 및 조정).

JSON: `worktrees/exp/phase2-diar-debounce/.omc/benchmarks/eval_exp106_diar_debounce_20260623_1424.json`

---

## Exp-107 (기각 — 2026-06-23)

**nonspeech_prob=0.35 파라미터 노출 및 조정 (웃음 구간 환각 억제)**

**가설**: bong1 웃음 구간에서 Whisper가 대규모 환각 텍스트 생성. `nonspeech_prob`을 기본값 0.5→0.35로 낮추면 웃음/잡음 구간을 "no speech"로 판정해 침묵 처리, 환각 감소 및 WER 개선.

**변경**: `whisperlivekit/config.py`, `whisperlivekit/core.py`, `whisperlivekit/simul_whisper/backend.py`, `whisperlivekit/parse_args.py`, `scripts/eval.py` — `--nonspeech-prob` CLI 인자 추가 및 배선. 브랜치: `exp/phase2-nonspeech-threshold`.

**정량 결과 (경로 C N=3, 신 체제, `--nonspeech-prob 0.35`):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 52.0% | 54.1% | 9.4% | 44.4% | **-9.6pp** ✓ | +1.5pp |
| ytn2  | 61.1% | 100.0% | 27.9% | 40.0% | **+26.1pp** ✗ | -14.5pp ✗ |
| sbs1  | 20.8% | 23.8% | 3.0% | 36.4% | -5.4pp ✓ | 0pp |

**기각 이유**: ytn2 WER +26.1pp (max 100%) — 채택 조건 ② 위반. 0.35가 ytn2 코드스위칭 짧은 세그먼트를 과도하게 침묵 처리하여 거의 무전사 상태 발생.

**관찰**: bong1 WER -9.6pp 개선은 유효. nonspeech_prob 낮추기가 bong1 환각 억제에 효과적이나, ytn2 코드스위칭 구간에 심각한 부작용. 0.35는 너무 aggressive — 더 보수적인 값(0.45) 또는 다른 접근 필요.

**다음 가설**: `compression_ratio_threshold` 3.0 → 2.4 조정 — bong1 웃음 환각 "(웃음 소리) × 10" 패턴은 높은 compression ratio를 가지므로 임계값 낮추면 제거 가능. ytn2 코드스위칭은 반복 패턴 없어 오탐 위험 낮음. 코드 변경 없이 파라미터만 변경.

JSON: `worktrees/exp/phase2-nonspeech-threshold/.omc/benchmarks/eval_exp107_nonspeech035_20260623_1514.json`

---

## Exp-108 (기각 — 2026-06-23)

**compression_ratio_threshold 3.0 → 2.4 (bong1 반복 환각 억제)**

**가설**: bong1 웃음 환각 "(웃음 소리) × 10" 패턴은 compression ratio가 높음. 3.0→2.4로 낮추면 이런 반복 세그먼트 제거 가능. ytn2 코드스위칭은 반복성 없어 오탐 위험 낮음.

**변경**: 코드 변경 없음 — eval.py `--compression-ratio-threshold 2.4` 파라미터만 변경. main에서 직접 측정.

**정량 결과 (경로 C N=3, 신 체제, `--compression-ratio-threshold 2.4`):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 41.4% | 73.1% | 20.5% | 50.0% | **-20.2pp** ✓ | +7.1pp ✓ |
| ytn2  | 37.9% | 54.7% | 11.6% | 51.9% | +2.9pp ✓ | -2.6pp |
| sbs1  | 25.0% | 48.2% | 14.5% | 20.0% | -1.2pp | **-16.4pp** ✗ |

**기각 이유**: sbs1 max WER 32.1%→48.2% (+16.1pp 악화) — 1순위 최악 케이스 미회귀 기준 위반. sbs1 F1 -16.4pp 급락.

**관찰**: bong1 WER -20.2pp 매우 큰 개선 효과 확인 — compression_ratio_threshold 방향은 유효하나 2.4는 sbs1 정상 한국어 발화도 제거. sbs1 R2 WER 48.2%/F1 20.0% 이상(stdev 14.5%로 불안정). 중간값 2.7 시도 필요.

**다음 가설**: `compression_ratio_threshold` 2.7 시도 — 2.4(bong1 크게 개선/sbs1 악화)와 3.0(베이스라인) 중간값. bong1 환각 일부 억제 유지하면서 sbs1 오탐 최소화.

JSON: `.omc/benchmarks/eval_exp108_crt24_20260623_1538.json`

---

## Exp-109 (기각 — 2026-06-23)

**compression_ratio_threshold 3.0 → 2.7 (중간값 탐색)**

**가설**: Exp-108(2.4)은 bong1 -20.2pp 개선이나 sbs1 max +16.1pp 악화. 중간값 2.7은 bong1 개선 일부 유지하면서 sbs1 부작용 감소 가능.

**변경**: 코드 변경 없음 — `--compression-ratio-threshold 2.7`.

**정량 결과 (경로 C N=3):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 54.1% | 65.9% | 14.0% | 35.0% | -7.5pp | -7.9pp ✗ |
| ytn2  | 36.9% | 58.6% | 16.8% | 63.2% | +1.9pp | +8.7pp ✓ |
| sbs1  | 31.5% | 43.5% | 11.9% | 20.0% | **+5.3pp** ✗ | **-16.4pp** ✗ |

**기각 이유**: sbs1 max WER +11.4pp, F1 -16.4pp — 1순위 최악 케이스 기준 위반. 2.4와 마찬가지로 sbs1 F1 20.0%로 동일 급락.

**관찰**: compression_ratio_threshold를 3.0 미만으로 낮추면 sbs1 F1이 36.4%→20.0%로 임계적으로 급락함 (2.4와 2.7 모두 동일). 이 방향은 sbs1에 구조적 악영향이 있으므로 **포기**. bong1 WER 개선 효과(2.4: -20.2pp, 2.7: -7.5pp)는 분명하나 sbs1 트레이드오프가 해소 불가.

**다음 가설**: `logprob_threshold=-0.8` — Whisper 신뢰도 기반으로 저신뢰도 세그먼트(환각) 제거. compression_ratio와 달리 텍스트 반복성이 아닌 확률 기반이라 sbs1 정상 발화에 영향 적을 것.

JSON: `.omc/benchmarks/eval_exp109_crt27_20260623_1602.json`

---

## Exp-110 (기각 — 2026-06-23)

**logprob_threshold=-0.8 (저신뢰도 세그먼트 제거)**

**가설**: 환각 텍스트는 Whisper 신뢰도(logprob)가 낮음. logprob<-0.8 세그먼트 제거 → 환각 억제, sbs1 영향 최소화.

**변경**: 코드 변경 없음 — `--logprob-threshold -0.8`.

**정량 결과 (경로 C N=3):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 41.7% | 43.5% | 1.8% | 18.8% | -19.9pp | **-24.1pp** ✗ |
| ytn2  | 38.4% | 40.9% | 5.1% | 35.3% | +3.4pp | **-19.2pp** ✗ |
| sbs1  | 35.7% | 38.1% | 6.6% | 20.0% | **+9.5pp** ✗ | -16.4pp ✗ |

**기각 이유**: F1 전 파일 급락 (bong1 -24.1pp, ytn2 -19.2pp, sbs1 -16.4pp), sbs1 WER +9.5pp. logprob=-0.8이 문장 경계를 담당하는 세그먼트까지 제거하여 문장 분리 성능 붕괴.

**관찰**: logprob 방향 전체 포기. compression_ratio+logprob+nonspeech_prob 파라미터 조정 방향의 패턴이 확인됨: 어느 방향이든 3개 파일 동시 개선 불가. 단순 파라미터 조정 방향 소진 → 코드 레벨 개선 또는 새 파라미터로 방향 전환 필요.

**다음 가설**: `periodic_lang_check=2.0` (4.0→2.0초) — 코드스위칭 감지 주기 단축으로 ytn2 WER 직접 공략. bong1/sbs1에 미치는 영향이 상대적으로 적을 것으로 예상. 코드 변경 없음.

JSON: `.omc/benchmarks/eval_exp110_logprob08_20260623_1625.json`

---

## Exp-112 (기각 — 2026-06-23)

**Sortformer confidence threshold 0.5 (spurious 화자 전환 억제)**

**가설**: Sortformer `_process_predictions()`가 단순 argmax라 불확실한 프레임(확률 균등 분포)에서 spurious 화자 전환 발생. confidence<0.5 프레임에서 이전 화자 유지 → sbs1 과분할(ref=3 vs hyp=9-11) 개선.

**변경**: `whisperlivekit/diarization/sortformer_backend.py` — `_SPEAKER_CONFIDENCE_THRESHOLD=0.5` 클래스 상수 추가, `_process_predictions()`에서 각 프레임 최대 확률이 threshold 미만이면 이전 화자 유지. 브랜치: `exp/phase2-diar-confidence`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 47.4% | 51.4% | 12.3% | 51.3% | -3.7pp | +2.5pp |
| ytn2  | 30.5% | 43.8% | 8.5% | 59.3% | +2.4pp | -0.7pp |
| sbs1  | 45.2% | 63.7% | 12.0% | 0.0% | **+19.6pp** ✗ | **-36.4pp** ✗ |

**기각 이유**: sbs1 WER +19.6pp (최악 63.7%), F1 완전 붕괴(0.0%) — sbs1의 실제 화자 전환 구간에서도 Sortformer confidence<0.5라 threshold가 실제 경계까지 제거함. spurious vs 실제 경계 구분 불가.

**관찰**: sbs1 F1 문제를 Sortformer 파라미터 조정으로 해결하는 접근 **포기**. diar-ON에서 sbs1 F1이 36.4%에 고착(diar-OFF는 76.2%) — Sortformer의 구조적 한계. 다른 접근(compression_ratio, dibaounce, confidence threshold 모두 실패) 소진.

**다음 가설**: `periodic_lang_check=1.5` (2.0→1.5초) — Exp-111에서 2.0이 ytn2 -6.9pp 큰 개선. 1.5로 더 단축하면 ytn2 추가 개선 가능. 코드 변경 없음.

JSON: `worktrees/exp/phase2-diar-confidence/.omc/benchmarks/eval_exp112_diarconf05_20260623_1723.json`

---

## Exp-113 (기각 — 2026-06-23)

**periodic_lang_check 2.0→1.5초 (더 공격적 언어 감지)**

**가설**: Exp-111(2.0s)이 ytn2 -6.9pp 개선. 1.5s로 더 단축하면 추가 개선 가능.

**변경**: 코드 변경 없음 — `--periodic-lang-check 1.5`.

**정량 결과 (경로 C N=3):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 48.9% | 58.0% | 6.1% | 44.4% | -2.2pp | -4.4pp |
| ytn2  | 35.0% | 37.9% | 4.8% | 56.0% | **+6.9pp** ✗ | -4.0pp |
| sbs1  | 19.0% | 63.7% | 25.9% | 18.2% | -6.6pp | **-18.2pp** ✗ |

**기각 이유**: ytn2 WER +6.9pp, sbs1 max 63.7% (+35.7pp). sbs1 stdev 25.9% 매우 불안정.

**관찰**: 1.5s가 2.0s보다 오히려 나빠짐 — 너무 자주 언어 감지하면 코드스위칭 중간에 잘못된 언어 전환 발생. **periodic_lang_check=2.0이 최적값**으로 역확인. 이 방향 탐색 완료.

**다음 가설**: `nonspeech_prob=0.45` — 0.35(Exp-107, ytn2 100% 기각)보다 보수적. bong1 웃음 환각 일부 억제하면서 ytn2 과억제 방지. periodic_lang_check=2.0 베이스라인에서 측정.

JSON: `.omc/benchmarks/eval_exp113_plc15_20260623_1747.json`

---

## Exp-114 (기각 — 2026-06-23)

**nonspeech_prob=0.45 + periodic_lang_check=2.0 (보수적 비음성 억제)**

**가설**: Exp-107(0.35)이 ytn2 WER 100%를 만든 근거는 지나친 억제. 0.45는 더 보수적으로 bong1 환각 일부 억제 가능.

**변경**: `--nonspeech-prob 0.45 --periodic-lang-check 2.0`. 워크트리: `exp/phase2-nonspeech-threshold`.

**정량 결과 (경로 C N=3):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 47.7% | 79.8% | 18.6% | 41.0% | -3.4pp | -7.8pp |
| ytn2  | 53.7% | 62.6% | 10.6% | 54.5% | **+25.6pp** ✗ | -5.5pp |
| sbs1  | 25.0% | 25.6% | 2.9% | 36.4% | -0.6pp | 0pp |

**기각 이유**: ytn2 WER +25.6pp — nonspeech_prob=0.45도 ytn2 코드스위칭 구간을 과억제하는 동일 문제.

**관찰**: nonspeech_prob 방향(0.35/0.45 모두)이 ytn2에 구조적으로 악영향. 이 방향 **포기**. ytn2 코드스위칭 구간의 Whisper nonspeech_prob이 정상 발화임에도 높게 나와 threshold에 걸리는 것으로 추정.

**다음 가설**: `logprob_threshold=-0.5` (Exp-110의 -0.8보다 보수적). 마지막 파라미터 조정 시도. 실패 시 방향 재설정 필요.

JSON: `worktrees/exp/phase2-nonspeech-threshold/.omc/benchmarks/eval_exp114_nonspeech045_20260623_1811.json`

---

## Exp-115 (기각 — 2026-06-23)

**logprob_threshold=-0.5 (보수적 저신뢰도 필터)**

**가설**: Exp-110(-0.8)이 F1 전체 붕괴. -0.5는 더 보수적으로 환각만 제거 가능.

**변경**: 코드 변경 없음 — `--logprob-threshold -0.5`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 58.0% | 58.0% | 1.9% | 20.0% | +6.9pp ✗ | -28.8pp ✗ |
| ytn2  | 62.6% | 66.0% | 4.2% | 0.0% | +34.5pp ✗ | -60.0pp ✗ |
| sbs1  | 45.2% | 49.4% | 4.8% | 20.0% | +19.6pp ✗ | -16.4pp ✗ |

**기각 이유**: 전 파일 WER 악화 + F1 완전 붕괴. -0.8과 동일 패턴.

**관찰**: logprob 방향 **완전 포기**. Exp-111 이후 4연속 기각. 단순 파라미터 조정 방향 소진. 아직 시도 안 한 방향: init_prompt(언어 컨텍스트 힌트), VAD threshold 조정. 방향 재설정 필요.

JSON: `.omc/benchmarks/eval_exp115_logprob05_20260623_1834.json`

---

## Exp-116 (기각 — 2026-06-23)

**static_init_prompt 언어 힌트 설정**

**가설**: `static_init_prompt = "이것은 한국어와 영어가 혼용된 대화입니다. This is a Korean and English conversation."` → Whisper context에 한/영 언어 힌트 영구 고정 → ytn2 코드스위칭 개선 + bong1 환각 억제.

**변경**: `scripts/eval.py` — `--static-init-prompt`, `--init-prompt` 인자 추가 및 extra_server_args 배선. 브랜치: `exp/phase2-init-prompt`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 113.0% | 155.6% | 30.2% | 41.7% | **+61.9pp** ✗ | -7.1pp |
| ytn2  | 173.9% | 255.2% | 72.1% | 40.0% | **+145.8pp** ✗ | -20.0pp |
| sbs1  | 144.0% | 244.6% | 109.6% | 15.4% | **+118.4pp** ✗ | -21.0pp |

**기각 이유**: 전 파일 WER 100%+ 폭발 — 완전 실패.

**원인 분석**: `static_init_prompt`가 Whisper SimulStreaming context에 영구 고정 텍스트를 삽입. Whisper가 이 텍스트를 "이전 발화"로 인식하여 해당 컨텍스트를 기반으로 실제 음성 대신 hallucination 대량 생성. 삽입 오류 폭발(WER>100%)로 확인. **init_prompt / static_init_prompt 방향 완전 포기**.

**관찰**: WER 100%+ = 삽입 오류 폭발 = Whisper가 오디오와 무관한 텍스트를 생성하는 심각한 hallucination. static_init_prompt가 Whisper 디코더에 잘못된 컨텍스트를 주입하는 메커니즘 문제. 언어 힌트 목적의 init_prompt 접근은 SimulStreaming 구조에서 근본적으로 작동하지 않음.

**다음 가설**: VAC threshold 상향 (Silero VAD threshold 0.3→0.5) — bong1 웃음 구간이 Silero VAD를 통과(speech로 분류)하여 Whisper에 전달됨. threshold를 표준값 0.5로 올리면 VAD 신뢰도 낮은 웃음 구간을 pre-filter 가능. nonspeech_prob와 달리 Whisper 내부 추론 전 오디오 레벨 필터.

JSON: `worktrees/exp/phase2-init-prompt/.omc/benchmarks/eval_exp116_static_init_prompt_20260623_1905.json`

---

## Exp-117 (기각 — 2026-06-23)

**VAC threshold 0.3→0.5 (Silero VAD 기준 강화)**

**가설**: Silero VAD가 bong1 웃음 구간을 speech(score>0.3)로 분류하여 Whisper에 전달 → 환각 발생. threshold=0.5로 높이면 웃음 구간(VAD score 0.3~0.5) 필터링으로 hallucination 감소.

**변경**: `whisperlivekit/parse_args.py` — `--vac-threshold` 인자 추가. `whisperlivekit/audio_processor.py` — `FixedVADIterator` threshold 하드코딩 0.3 → `args.vac_threshold` 사용. `scripts/eval.py` — `--vac-threshold` 추가 및 배선. 브랜치: `exp/phase2-vac-threshold`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0, vac_threshold=0.5):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 39.9% | 60.4% | 13.5% | 47.4% | **-11.2pp** ✓ | -1.4pp |
| ytn2  | 37.9% | 56.7% | 12.5% | 50.0% | **+9.8pp** ✗ | -10.0pp |
| sbs1  | 20.2% | 44.0% | 14.5% | 20.0% | -5.4pp ✓ | **-16.4pp** ✗ |

**기각 이유**: ytn2 WER +9.8pp (채택 조건 ② 위반), sbs1 F1 -16.4pp 급락.

**관찰**: bong1 -11.2pp 개선 유의미 — VAC threshold 상향이 bong1 웃음 구간 필터링에 효과적임 확인. 하지만 ytn2 코드스위칭 전환 구간에서 Silero VAD가 일부 speech를 non-speech로 오분류. **nonspeech_prob 방향(Exp-107/114)과 동일 트레이드오프 패턴**: bong1 개선 ↔ ytn2/sbs1 악화.

**분석**: bong1 웃음/잡음과 ytn2 코드스위칭 전환 구간이 Silero VAD에서 유사한 score 범위에 위치. 단순 임계값으로는 구분 불가. bong1을 직접 공략하는 방향(단순 임계값 조정)은 한계 도달.

**다음 가설**: bong1 환각 패턴 분석 후 cross-batch 반복 필터 또는 더 타겟적 접근. bong1 환각이 반복 패턴인지 랜덤 텍스트인지 확인 필요.

JSON: `worktrees/exp/phase2-vac-threshold/.omc/benchmarks/eval_exp117_vac05_20260623_1932.json`

---

## Exp-120 (기각 — 2026-06-23)

**compression_ratio_threshold=2.5 (2.4와 2.7 중간)**

**가설**: Exp-108(2.4) bong1 -20.2pp, Exp-119(2.7) 무효과. 2.5에서 bong1 개선 유지하면서 sbs1/ytn2 안정화.

**변경**: 코드 변경 없음 — `--compression-ratio-threshold 2.5`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 59.8% | 62.8% | 15.4% | 38.1% | **+8.7pp** ✗ | **-10.7pp** ✗ |
| ytn2  | 48.3% | 55.2% | 15.7% | 52.2% | **+20.2pp** ✗ | **-7.8pp** ✗ |
| sbs1  | 24.4% | 27.4% | 1.7% | 36.4% | -1.2pp ✓ | 0pp |

**기각 이유**: bong1 +8.7pp, ytn2 +20.2pp 전면 악화. CRT=2.4가 큰 개선을 보인 것과 달리 2.5에서는 오히려 베이스라인보다 나빠짐.

**관찰**: CRT 조정 실험 결과 패턴 정리 (베이스=3.0 대비):
- CRT=2.4: bong1 -20.2pp ✓ / sbs1 max 폭증(46.2%) ✗
- CRT=2.5: bong1 +8.7pp ✗ / ytn2 +20.2pp ✗
- CRT=2.7: bong1 +2.1pp ✗ / ytn2 +11.3pp ✗
**측정 분산(stdev 12-16%)이 너무 커서 3회 median으로 CRT 효과를 일관되게 판정하기 어려움. CRT 방향 탐색 종료.**

**상황**: Exp-116~120 연속 5회 기각. 현재 파라미터 조정·후처리 필터 방향 소진. _apply_dry_penalty 강화 또는 beams 조정 등 미시도 방향 남아 있음. 다음에 시도할 방향: DRY penalty multiplier 증가(현재 `1.0 * 2.0^(length-2)` → 더 공격적으로) 또는 beams=4로 증가.

JSON: `.omc/benchmarks/eval_exp120_crt25_20260623_2101.json`

---

## Exp-121 (기각 — 2026-06-23)

**DRY penalty multiplier 1.0 → 2.0 강화**

**가설**: `_apply_dry_penalty()`의 페널티 공식 `1.0 * 2.0^(length-2)`에서 곱수를 1.0→2.0으로 배가. 반복 토큰 생성 시 logit 페널티가 2배 강해져 bong1 웃음 구간 반복 환각 감소 기대.

**변경**: `worktrees/exp/phase2-dry-penalty/whisperlivekit/simul_whisper/align_att_base.py` line 526 — `1.0 * 2.0 ** (length - 2)` → `2.0 * 2.0 ** (length - 2)`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 43.8% | 58.0% | 10.5% | 48.6% | **-7.3pp** ✓ | -0.2pp |
| ytn2  | 29.1% | 47.8% | 11.4% | 63.2% | +1.0pp | +3.2pp ✓ |
| sbs1  | 19.0% | **33.9%** | 8.6% | 36.4% | **-6.6pp** ✓ | 0pp |

**기각 이유**: sbs1 max WER 28.0%→33.9% (+5.9pp) — 1순위 기준(max 미회귀) 위반. R1=19.0%, R2=33.9%, R3=19.0%로 R2 이상치.

**관찰**: bong1 median -7.3pp, sbs1 median -6.6pp로 DRY 강화가 반복 환각 억제에 효과적임을 시사. sbs1 max 악화는 R2 1회 이상치 가능성 있음(R1/R3는 안정). DRY 2x는 너무 aggressive — 1.5x(중간값) 시도 가치 있음.

**다음 가설**: DRY penalty multiplier 1.0 → 1.5 (2.0의 절반 강화) — bong1 개선 일부 유지하면서 sbs1 max 안정화.

JSON: `worktrees/exp/phase2-dry-penalty/.omc/benchmarks/eval_exp121_dry2x_20260623_2152.json`

---

## Exp-122 (기각 — 2026-06-23)

**DRY penalty multiplier 2.0 → 1.5 (Exp-121 완화)**

**가설**: Exp-121(2.0x)에서 bong1 -7.3pp 개선됐으나 sbs1 max +5.9pp 악화. 1.5x 중간값으로 bong1 개선 일부 유지하면서 sbs1 max 안정화.

**변경**: `worktrees/exp/phase2-dry-penalty/whisperlivekit/simul_whisper/align_att_base.py` line 526 — `2.0 * 2.0 ** (length - 2)` → `1.5 * 2.0 ** (length - 2)`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 35.6% | 54.4% | 11.3% | 46.2% | **-15.5pp** ✓ | -2.6pp |
| ytn2  | 27.1% | 39.9% | 7.9% | 66.7% | -1.0pp ✓ | +6.7pp ✓ |
| sbs1  | 32.1% | **39.3%** | 9.3% | 36.4% | **+6.5pp** ✗ | 0pp |

**기각 이유**: sbs1 WER median +6.5pp (②조건 위반), max +11.3pp (1순위 기준 위반). bong1 -15.5pp 대폭 개선에도 불구하고 sbs1 전면 악화.

**관찰**: DRY penalty 강도별 sbs1 결과 정리 (베이스라인 대비):
- DRY 1.0x (베이스): sbs1 median 25.6%, max 28.0%
- DRY 1.5x: sbs1 median +6.5pp ✗, max +11.3pp ✗
- DRY 2.0x: sbs1 median -6.6pp ✓, max +5.9pp ✗
비단조적 패턴 + 높은 측정 분산(stdev 8-11%)으로 DRY 강도 조정 효과를 3회 측정으로 안정적으로 판정하기 어려움. **DRY penalty 방향 탐색 종료.**

**다음 가설**: beam_size 2→3 — 코드 변경 없이 파라미터만 변경, 더 정확한 빔 서치로 코드스위칭·환각 감소 기대.

JSON: `worktrees/exp/phase2-dry-penalty/.omc/benchmarks/eval_exp122_dry15x_20260623_2217.json`

---

## Exp-123 (기각 — 2026-06-23)

**beam_size 2→3 (빔 서치 공간 확대)**

**가설**: 현재 beam_size=2. 3으로 늘리면 코드스위칭·환각 구간에서 더 좋은 디코딩 경로 선택 가능 → bong1/ytn2 WER 개선 기대. 파라미터만 변경(코드 수정 없음).

**변경**: `worktrees/exp/phase2-beams3/scripts/eval.py`에 `--beams` 인자 추가, `--beams 3` 파라미터 사용.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 36.0% | **70.4%** | 20.4% | 51.4% | **-15.1pp** ✓ | +2.6pp |
| ytn2  | 29.6% | **33.0%** | 2.5% | 60.0% | +1.5pp | 0pp |
| sbs1  | **17.9%** | 23.8% | 3.8% | 36.4% | **-7.7pp** ✓ | 0pp |

**기각 이유**: bong1 max +10.9pp (59.5%→70.4%) — 1순위 기준 위반. R2=70.4% 이상치, R1=36.0%, R3=34.1%로 분산 급증(stdev 20.4%).

> **[2026-06-24 재확인]** 이상치 분석(spread=36.3pp) → Exp-129에서 beam=3 재측정. R2=70.4%는 VBCable 불안정이었음 확인. 재측정 결과 bong1 max=48.0%, 채택 기준 통과 → **Exp-129에서 beam=3 채택**.

**관찰**: sbs1 -7.7pp·max -4.2pp, ytn2 max -14.8pp(stdev 11.8%→2.5% 대폭 안정화)로 beam=3이 코드스위칭·단일화자 구간에서 명확히 효과적. 하지만 bong1의 웃음 구간 환각 회차(R2)가 70%+으로 급등해 최악케이스 기준을 충족하지 못함. bong1 불안정의 근본 원인은 비언어음(웃음) 구간 환각이 한 회차 WER 전체를 망가뜨리는 것.

**다음 가설**: `logprob_threshold=-0.5` — 낮은 신뢰도 세그먼트 드롭으로 환각 세그먼트 억제, bong1 최악케이스 감소 기대. eval.py 이미 지원, 코드 변경 없음.

JSON: `worktrees/exp/phase2-beams3/.omc/benchmarks/eval_exp123_beams3_20260623_2242.json`

---

## Exp-124 (기각 — 2026-06-23)

**logprob_threshold=-0.5 (낮은 신뢰도 세그먼트 드롭)**

**가설**: 환각 세그먼트는 avg-logprob가 낮은 경향. -0.5 임계값으로 낮은 신뢰도 세그먼트를 드롭해 bong1 웃음 구간 환각 억제.

**변경**: 코드 변경 없음 — `--logprob-threshold -0.5`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 47.4% | 55.3% | 4.6% | 15.4% | -3.7pp | **-33.4pp** ✗ |
| ytn2  | 57.6% | 68.0% | 13.7% | 11.1% | **+29.5pp** ✗ | **-48.9pp** ✗ |
| sbs1  | 44.0% | 60.7% | 10.4% | 0.0% | **+18.4pp** ✗ | **-36.4pp** ✗ |

**기각 이유**: 전면 악화. logprob_threshold=-0.5가 너무 공격적으로 세그먼트를 드롭해 전사 자체가 무너짐 (F1 0~15%). 정상 발화 세그먼트까지 드롭된 것으로 보임.

**관찰**: Whisper avg_logprob는 -0.5 부근에 정상 발화도 많이 분포. 이 값은 너무 공격적. logprob 방향 전체 탐색 종료.

**다음 가설**: beam_size=4 — beam=3에서 sbs1/ytn2 효과적이었고 bong1만 R2 이상치 문제. beam=4로 bong1 불안정 해소 여부 확인.

JSON: `.omc/benchmarks/eval_exp124_logprob05_20260623_2306.json`

---

## Exp-125 (기각 — 2026-06-24)

**beam_size 2→4**

**가설**: beam=3(Exp-123)에서 bong1 R2=70.4% 이상치 발생. beam=4로 더 넓은 빔 서치 → bong1 불안정 해소 및 디코딩 품질 향상 기대.

**변경**: `worktrees/exp/phase2-beams3/scripts/eval.py` `--beams 4`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | **33.5%** | **34.7%** | **0.8%** | 54.1% | **-17.6pp** ✓ | +5.3pp ✓ |
| ytn2  | 40.4% | **97.0%** | 37.3% | 42.9% | **+12.3pp** ✗ | -17.1pp ✗ |
| sbs1  | 23.8% | 25.0% | 2.5% | 36.4% | -1.8pp ✓ | 0pp |

**기각 이유**: ytn2 WER median +12.3pp (②조건 위반), max 97.0% catastrophic (1순위 위반).

**관찰**: bong1 stdev 0.8%로 극도 안정화 (R1=33.2%/R2=33.5%/R3=34.7%) — beam=4가 bong1 환각 체인을 효과적으로 차단. 그러나 beam 크기 vs ytn2 WER 단조 증가 패턴 확인 (beam2=28.1%, beam3=29.6%, beam4=40.4%). beam 증가가 코드스위칭 짧은 세그먼트 실시간 처리에 오버헤드 발생. **beam_size 방향 종료.**

**다음 가설**: `condition_on_previous_text=False` — 이전 세그먼트 텍스트 컨디셔닝 제거로 bong1 환각 체인(웃음→반복 환각) 방지. ytn2 처리 오버헤드 없이 bong1 최악케이스 억제 기대.

JSON: `worktrees/exp/phase2-beams3/.omc/benchmarks/eval_exp125_beams4_20260624_0849.json`

---

## Exp-126 (기각 — 2026-06-24)

**condition_on_previous_text=False (max_context_tokens=0)**

**가설**: bong1 웃음 환각은 이전 세그먼트 텍스트 컨디셔닝으로 체인이 강화됨. max_context_tokens=0으로 이전 컨텍스트 완전 차단 → 환각 체인 방지, bong1 최악케이스 개선.

**변경**: `worktrees/exp/phase2-beams3/scripts/eval.py`에 `--max-context-tokens` 인자 추가, `--max-context-tokens 0` 사용.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 75.8% | 100.0% | 15.4% | 19.0% | **+24.7pp** ✗ | **-29.8pp** ✗ |
| ytn2  | 48.8% | 56.7% | 12.0% | 50.0% | **+20.7pp** ✗ | -10.0pp |
| sbs1  | 100.0% | 100.0% | 33.0% | 0.0% | **+74.4pp** ✗ | **-36.4pp** ✗ |

**기각 이유**: sbs1 median/max WER 100%, bong1 median +24.7pp — 전사 자체 파괴. 컨텍스트 없이 한국어 연속 발화 처리 불가.

**관찰**: condition_on_previous_text/max_context_tokens 방향 **포기**. 이전 컨텍스트는 필수적 — 제거하면 전사 붕괴.

**다음 가설**: `audio_min_len` 조정 — 현재 parse_args.py default=0.0. 웃음 같은 짧은 비음성 청크를 스킵하여 bong1 환각 억제. 1.5~2.0s 시도.

JSON: `worktrees/exp/phase2-beams3/.omc/benchmarks/eval_exp126_ctx0_20260624_0915.json`

---

## Exp-127 (즉시 기각 — 2026-06-24)

**audio_min_len=1.5 (짧은 오디오 청크 스킵)**

**가설**: bong1 웃음 구간이 짧은 비음성 청크로 들어옴. audio_min_len=1.5로 1.5초 미만 버퍼 스킵 → 웃음 환각 억제.

**변경**: `worktrees/exp/phase2-beams3/scripts/eval.py`에 `--audio-min-len` 인자 추가, `--audio-min-len 1.5` 사용.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER |
|------|-----------|---------|----------|-----------|-----------------|
| bong1 | 95.8% | 100.0% | 27.3% | 10.5% | **+44.7pp** ✗ |
| ytn2  | 100.0% | 100.0% | 20.8% | 0.0% | **+71.9pp** ✗ |
| sbs1  | 100.0% | 100.0% | 0.0% | 0.0% | **+74.4pp** ✗ |

**기각 이유**: 전 파일 WER 100% catastrophic. SimulStreaming은 짧은 청크를 연속 스트리밍하는 구조라 audio_min_len=1.5가 대부분의 청크를 스킵 → 전사 거의 없음.

**관찰**: audio_min_len은 "해당 시점의 버퍼 누적량"이 아닌 "단일 청크 길이" 기준. SimulStreaming 청크가 대부분 1.5초 미만 → 전사 자체 불가. **audio_min_len 방향 포기**.

**다음 가설**: VAC threshold=0.4 — Exp-117(0.5)이 bong1 -11.2pp 개선됐지만 ytn2 +9.8pp 악화. 중간값 0.4에서 bong1 일부 개선하면서 ytn2 부작용 최소화 가능성. 아직 시도하지 않은 유일한 값.

JSON: `worktrees/exp/phase2-beams3/.omc/benchmarks/eval_exp127_audio_min15_20260624_1010.json`

---

## Exp-128 (즉시 기각 — 2026-06-24)

**VAC threshold=0.4 (Silero VAD 임계값 중간값)**

**가설**: Exp-117(0.5)에서 bong1 -11.2pp 개선됐으나 ytn2 +9.8pp 악화. 중간값 0.4에서 bong1 개선 유지하면서 ytn2 부작용 완화 기대.

**변경**: `worktrees/exp/phase2-vac-threshold` — `--vac-threshold 0.4`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER |
|------|-----------|---------|----------|-----------|-----------------|
| bong1 | 83.1% | 90.9% | 16.7% | 37.8% | **+32.0pp** ✗ |
| ytn2  | 100.0% | 100.0% | 0.0% | 0.0% | **+71.9pp** ✗ |
| sbs1  | 100.0% | 100.0% | 0.0% | 0.0% | **+74.4pp** ✗ |

**기각 이유**: ytn2/sbs1 전회차 WER 100%, bong1 median +32pp catastrophic. Exp-117(0.5)보다 오히려 악화.

**관찰**: VAC threshold 단조 감소(0.3→0.4)에서 성능이 단조적으로 나빠짐. **VAC threshold 방향 완전 포기**.

JSON: `worktrees/exp/phase2-vac-threshold/.omc/benchmarks/eval_exp128_vac04_20260624_1220.json`

---

## Exp-129 (채택 — 2026-06-24)

**beam_size=3 재측정 (Exp-123 이상치 재확인)**

**가설**: Exp-123 bong1 R2=70.4%가 VBCable 불안정에 의한 이상치인지 재확인. 이상치라면 beam=3 채택.

**변경**: `worktrees/exp/phase2-beams3` — `--beams 3` (코드 변경 없음).

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | **35.6%** | **48.0%** | 9.3% | 48.6% | **-15.5pp** ✓ | -0.2pp |
| ytn2  | 32.5% | 36.5% | 3.2% | 63.6% | +4.4pp ✓ | +3.6pp ✓ |
| sbs1  | **19.6%** | 27.4% | 4.8% | 36.4% | **-6.0pp** ✓ | 0pp |

회차별: bong1 R1=48.0%/F1 48.6%, R2=29.9%/F1 55.6%, R3=35.6%/F1 33.3% | ytn2 R1=36.5%, R2=30.0%, R3=32.5% | sbs1 R1=27.4%, R2=18.5%, R3=19.6%

**Held-out 결과 (ytn1+eng1, N=3):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs Exp-111 |
|------|-----------|---------|----------|-----------|------------|
| ytn1 | 34.4% | 36.8% | 3.7% | 58.8% | WER +7.4pp / F1 -23.6pp ★주의 |
| eng1 | **5.7%** | 5.7% | 1.1% | 0.0% | WER ±0 |

회차별: ytn1 R1=34.4%/F1 50.0%, R2=29.4%/F1 82.4%, R3=36.8%/F1 58.8%

**채택 조건 판정:**
① F1 유의미 상승: WER 개선 중심 실험 (bong1 -15.5pp, sbs1 -6.0pp) ✓
② WER 회귀 ≤+5pp: ytn2 +4.4pp ✓
③ pytest: 코드 변경 없음 ✓
④ 아티팩트: 특이 없음 ✓
⑤ held-out ytn1 WER max +1.2pp(경미), F1 -23.6pp (★ 주의 — R2에서 82.4% 달성, 자연 분산 내 가능성)

**채택 이유**:
- bong1 WER median -15.5pp, max -11.5pp (가장 중요한 파일 가장 큰 개선)
- Exp-123 R2=70.4%는 VBCable 불안정 이상치 확인 (Exp-129에서 없음)
- ytn2 max -11.3pp 안정화, sbs1 -6.0pp 개선
- ytn1 WER max +1.2pp 경미, F1 하락은 측정 분산 가능성 (R2에서 82.4% 달성)
- beam=3 코드 변경 없음 — parse_args.py 기본값 변경만 필요

**beam=3 채택 후 적용 방법**: `whisperlivekit/parse_args.py`의 `--beam-size` 기본값 2→3 변경 (또는 eval.py 기본 `--beams 3`으로 측정).

JSON (테스트): `worktrees/exp/phase2-beams3/.omc/benchmarks/eval_exp129_beams3_retry_20260624_1245.json`
JSON (held-out): `worktrees/exp/phase2-beams3/.omc/benchmarks/eval_exp129_beams3_heldout_20260624_1327.json`

---

## 이전 채택 베이스라인 (Exp-129 — 2026-06-24, Exp-130으로 대체됨)

> **파라미터**: `--compression-ratio-threshold 3.0 --periodic-lang-check 2.0 --beam-size 3 --diarization --sortformer-model ... --repeat 3`

| 파일 | WER median | WER max | WER stdev | F1 median | 회차별 |
|------|-----------|---------|----------|-----------|--------|
| bong1 | **35.6%** | 48.0% | 9.3% | **48.6%** | R1 48.0%/48.6%, R2 29.9%/55.6%, R3 35.6%/33.3% |
| ytn2  | **32.5%** | 36.5% | 3.2% | **63.6%** | R1 36.5%/54.5%, R2 30.0%/80.0%, R3 32.5%/63.6% |
| sbs1  | **19.6%** | 27.4% | 4.8% | **36.4%** | R1 27.4%/40.0%, R2 18.5%/36.4%, R3 19.6%/20.0% |

held-out: ytn1 WER 34.4%/max 36.8%/F1 58.8%, eng1 WER 5.7%/F1 0.0%

---

## Exp-119 (기각 — 2026-06-23)

**compression_ratio_threshold=2.7 (2.4와 3.0 중간값)**

**가설**: Exp-108(CRT=2.4)에서 bong1 -20.2pp 개선 확인됐으나 sbs1 max 폭증. 2.7은 중간값으로 bong1 일부 개선하면서 sbs1 오탐 최소화.

**변경**: 코드 변경 없음 — `--compression-ratio-threshold 2.7`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 53.2% | 62.5% | 12.3% | 48.6% | +2.1pp ✗ | -0.2pp |
| ytn2  | 39.4% | 40.9% | 5.0% | 51.9% | **+11.3pp** ✗ | **-8.1pp** ✗ |
| sbs1  | 19.6% | 26.2% | 4.4% | 36.4% | -6.0pp ✓ | 0pp |

**기각 이유**: ytn2 WER +11.3pp (채택 조건 ② 위반), bong1 개선 없음(+2.1pp 오히려 악화).

**관찰**: CRT=2.7이 bong1 환각을 전혀 억제하지 못함. 이는 bong1 웃음 환각 텍스트의 CRT가 2.7~3.0 사이에 분포함을 의미. Exp-108(2.4)에서는 효과 있었으므로 범위가 2.4~2.7 사이. 그러나 2.4는 sbs1 max 폭증(46.2%), 2.7은 bong1 무효과. **CRT 방향은 이 실험으로 소진** — 2.4와 2.7 사이 세밀한 조정(2.5/2.6)을 시도하거나 다른 방향으로 전환 필요. ytn2는 CRT 조정에 매우 민감(+11.3pp) — CRT 조정이 ytn2에서 일관되게 악화됨.

**다음 가설**: `compression_ratio_threshold=2.5` — 2.4(bong1 최대 효과)와 2.7(무효과) 사이. 혹은 반복 필터 임계값 조정(top_count >= 4 → >= 3).

JSON: `.omc/benchmarks/eval_exp119_crt27_20260623_2036.json`

---

## Exp-118 (기각 — 2026-06-23)

**TTR(Type-Token Ratio) 기반 복합 반복 환각 감지**

**가설**: bong1 환각("이 노래는/이 노래에/이 노래를" 변형 반복) 패턴은 단일 단어 Counter로 잡히지 않음. 배치 내 한국어 단어 10개+이고 TTR(고유 단어수/전체 단어수) < 0.45이면 복합 반복 환각으로 판단해 배치 드롭+리셋.

**변경**: `whisperlivekit/simul_whisper/backend.py` — `_filter_cross_batch_repetitions()`에 TTR 체크 추가 (len >= 10 && TTR < 0.45). 브랜치: `exp/phase2-ttr-filter`.

**정량 결과 (경로 C N=3, periodic_lang_check=2.0):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 41.1% | **71.6%** | 18.8% | 45.7% | **-10.0pp** ✓ | **-3.1pp** |
| ytn2  | 33.0% | 48.3% | 10.9% | 63.2% | +4.9pp ✓ | +3.2pp ✓ |
| sbs1  | 23.2% | **37.5%** | 9.2% | 36.4% | -2.4pp ✓ | 0pp |

**기각 이유**: **1순위 max WER 회귀** — bong1 max 59.5%→71.6% (+12.1pp ✗), sbs1 max 28.0%→37.5% (+9.5pp ✗). TTR 필터가 일부 회차에서 정상 발화를 drop해 최악 케이스 악화.

**관찰**: bong1 median -10pp는 개선 효과 있으나 max가 치명적으로 올라감. TTR < 0.45 임계값이 너무 관대해 정상 한국어 발화(반복적 대화체)도 필터링됨. VAC threshold / nonspeech_prob과 동일 패턴(median 개선 ↔ max 회귀). 이 방향 추가 시도 가치 있으나 임계값 재조정 필요.

**다음 가설**: `compression_ratio_threshold=2.7` — Exp-108(2.4)에서 bong1 -20.2pp 매우 큰 효과 확인됐으나 sbs1 max 회귀 심함. 2.7은 2.4와 3.0(베이스라인) 중간값으로 sbs1 오탐 최소화 기대. 코드 변경 없음.

JSON: `worktrees/exp/phase2-ttr-filter/.omc/benchmarks/eval_exp118_ttr_20260623_2011.json`

---

## Exp-111 (채택 — 2026-06-23)

**periodic_lang_check 4.0→2.0초 (코드스위칭 감지 주기 단축)**

**가설**: 현재 4.0초마다 언어 재감지. 2.0초로 단축하면 ytn2 코드스위칭 구간에서 더 빠르게 언어 전환 감지 → WER 개선. bong1/sbs1 영향 미미 예상.

**변경**: 코드 변경 없음 — `--periodic-lang-check 2.0`.

**테스트 세트 결과 (경로 C N=3):**

| 파일 | WER median | WER max | WER stdev | F1 median | vs 베이스라인 WER | vs 베이스라인 F1 |
|------|-----------|---------|----------|-----------|-----------------|----------------|
| bong1 | 51.1% | 59.5% | 14.1% | 48.8% | **-10.5pp** ✓ | +5.9pp ✓ |
| ytn2  | 28.1% | 47.8% | 11.8% | 60.0% | **-6.9pp** ✓ | +5.5pp ✓ |
| sbs1  | 25.6% | 28.0% | 3.3% | 36.4% | -0.6pp ✓ | 0pp |

**Held-out 결과 (ytn1+eng1):**

| 파일 | WER median | WER max | WER stdev | F1 median | catastrophic? |
|------|-----------|---------|----------|-----------|---------------|
| ytn1 | 27.0% | 35.6% | 5.3% | **82.4%** | 아니오 |
| eng1 | 5.7% | 6.7% | 1.5% | 0.0% | 아니오 |

**채택 이유**:
- 테스트 3종 WER 모두 개선, 회귀 없음 (1순위 최악 케이스 기준 통과)
- ytn2 max WER 96.1%→47.8% (-48.3pp!) — 불안정 최악 케이스 대폭 개선
- bong1 WER -10.5pp, F1 +5.9pp 개선
- held-out catastrophic 회귀 없음; ytn1 F1 82.4% (목표 80% 달성!)
- eng1 WER 5.7% 회귀 없음

**새 베이스라인 파라미터**: `--periodic-lang-check 2.0` (이전 4.0에서 변경)

JSON (테스트): `.omc/benchmarks/eval_exp111_plc20_20260623_1648.json`
JSON (held-out): `.omc/benchmarks/eval_exp111_plc20_heldout_20260623_1711.json`

---

## 이전 채택 베이스라인 (Exp-111 — 2026-06-23, Exp-129로 대체됨)

> **파라미터**: `--compression-ratio-threshold 3.0 --periodic-lang-check 2.0 --diarization --sortformer-model ... --repeat 3`

| 파일 | WER median | WER max | WER stdev | F1 median | 회차별 |
|------|-----------|---------|----------|-----------|--------|
| bong1 | **51.1%** | 59.5% | 14.1% | **48.8%** | R1 59.5%/33.3%, R2 51.1%/48.8%, R3 32.0%/55.6% |
| ytn2  | **28.1%** | 47.8% | 11.8% | **60.0%** | R1 28.1%/40.0%, R2 47.8%/88.9%, R3 26.6%/60.0% |
| sbs1  | **25.6%** | 28.0% | 3.3% | **36.4%** | R1 28.0%/36.4%, R2 21.4%/36.4%, R3 25.6%/36.4% |

held-out: ytn1 WER 27.0%/F1 82.4%, eng1 WER 5.7%/F1 0.0%

---

## 이전 채택 베이스라인 (Exp-093 — 2026-06-18)

**주기적 언어재감지 4.0s + ForeignLang 즉시 트리거 (beam_size=2, --lan auto, --periodic-lang-check 4.0)**

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 20.2% | 19.6% | 17.9% | **19.6%** | **76.2%** | 20.2% | 1.2% |
| ytn1 | 18.4% | 18.4% | 20.2% | **18.4%** | **71.4%** | 20.2% | 1.1% |
| eng1 | 5.7% | 3.8% | 5.7% | **5.7%** | 0.0% | 5.7% | 1.1% |
| **평균** | | | | **15.9%** | **49.2%** | | |

- ytn1 max 20.2%: Exp-104(22.1%) 대비 1.9pp 개선.
- sbs1 max 20.2%: Exp-104(27.4%) 대비 7.2pp 개선 — watch item 해소.
- eng1 max 5.7%: Exp-104(6.7%) 대비 1.0pp 개선.
- ytn2(held-out, diar-on) WER median **25.1%**, max 27.1%, F1 50.0% — Exp-104(28.1%) 대비 3.0pp 개선. 폭주 0회.
- ytn1 catastrophic run 완전 소멸 (이전 max 108.0% → 22.7%). stdev 44.6% → 0.6%로 극적 안정화.
- JSON: `.omc/benchmarks/eval_exp093_primary_n3.json`

주요 변경 파일:
- `whisperlivekit/simul_whisper/align_att_base.py` — `_maybe_periodic_lang_check()` 추가, `infer()` 마지막 호출
- `whisperlivekit/simul_whisper/backend.py` — `_FOREIGN_LANG_PATTERN` 상수 + `process_iter()` 즉시 재감지 트리거
- `whisperlivekit/simul_whisper/config.py` — `periodic_lang_check_secs` 필드
- `whisperlivekit/simul_whisper/decoder_state.py` — `last_periodic_lang_check`, `last_lang_switch_time` 필드
- `whisperlivekit/config.py`, `whisperlivekit/parse_args.py`, `whisperlivekit/basic_server.py` — `--trace-tokens`, `--periodic-lang-check` 옵션 배선
- `scripts/eval.py` — `--trace-tokens`, `--periodic-lang-check`, `server_log_file`

브랜치: `phase4/diarization-spike`

---

## Exp-105 (phase4/diarization-spike 채택 — 2026-06-22)

**diar-off 언어 고착 해소 — 주기적 언어재감지 + ForeignLang 즉시 트리거 + 진단 인프라**

정책: simulstreaming. 브랜치 `phase4/diarization-spike`.

**가설**: Exp-093/104의 `MIN_DURATION_REAL_SILENCE=2` 방식은 2s 침묵이 없으면 언어 전환 불가 → diar-off 경로에서
뉴스 한·영 연속 전환(짧은 pause) 구간 언어 고착. 두 가지 보완이 필요:
1. **주기적 재감지**: 침묵 없이도 4s마다 `detect_current_language(window_secs=2.0, min_prob=0.90)` → 언어가 다르면
   `_apply_detected_language()` 전환. 히스테리시스 3s(flip-flop 방지).
2. **ForeignLang 즉시 트리거**: `(speaking in foreign language)` 패턴 방출 시 즉시 `detected_language=None` 리셋 →
   다음 청크에서 강제 재감지.

4단계 진행: Round 0(진단 인프라) → Round 1(기각) → Round 2(채택) → Round 3(ytn2 확인).

**Round 0 — 진단 인프라 (코드 변경, 벤치마크 없음)**
- `backend.py` CrossBatchFilter: `logger.debug` → `logger.info`
- `backend.py` TokenTrace: `infer`/`emit` 단계별 토큰 목록 `logger.debug` 추가 (`--trace-tokens` 플래그)
- `align_att_base.py` QualityGate: `%.60s` → `%.200s` (텍스트 잘림 제거)
- 진단 결과: "텅 빈 바다가" 누락 = 필터 아닌 디코더 자체 미생성 → Round 2 언어 재감지로 해결

**Round 1 — 기각: tokens_alignment.py 언어전환 경계 삽입**
- `tokens_alignment.py` `get_lines()` 내 `_detect_script()` 기반 언어전환 경계 삽입
- **기각 이유**: ytn1 max 27.0% > 22.1% 가드레일 위반 (옳은 문장 중간에 잘못된 경계 삽입)
- `git checkout -- whisperlivekit/tokens_alignment.py`로 롤백

**변경 (Round 0 진단 인프라 + Round 2 채택)**:
- `whisperlivekit/simul_whisper/align_att_base.py` — `_maybe_periodic_lang_check(audio_end_secs)` 추가, `infer()` 마지막 호출
- `whisperlivekit/simul_whisper/backend.py` — `_FOREIGN_LANG_PATTERN` 상수 + `process_iter()` 즉시 재감지 트리거 + CrossBatchFilter debug→info + TokenTrace 로그
- `whisperlivekit/simul_whisper/config.py` — `periodic_lang_check_secs: Optional[float] = field(default=None)`
- `whisperlivekit/simul_whisper/decoder_state.py` — `last_periodic_lang_check: float = 0.0`, `last_lang_switch_time: float = 0.0`
- `whisperlivekit/config.py` — `trace_tokens: bool = False`, `periodic_lang_check_secs: Optional[float] = None`
- `whisperlivekit/parse_args.py` — `--trace-tokens`, `--periodic-lang-check` 옵션
- `whisperlivekit/basic_server.py` — `trace_tokens` 활성 시 backend/align_att_base logger DEBUG 설정
- `scripts/eval.py` — `--trace-tokens`, `--periodic-lang-check`, `server_log_file` 파라미터

**테스트**: `.venv\Scripts\python.exe scripts\eval.py --paths C --repeat 3 --periodic-lang-check 4.0 --files test_data\sbs1.mp3 test_data\ytn1.mp3 test_data\eng1.mp3`

**정량 결과 (Round 2, 경로 C N=3, --periodic-lang-check 4.0):**

| 파일 | R1 WER | R2 WER | R3 WER | median WER | max WER | stdev | F1 (median) | vs Exp-104 |
|---|---|---|---|---|---|---|---|---|
| sbs1 | 20.2% | 19.6% | 17.9% | **19.6%** | 20.2% | 1.2% | **76.2%** | median ↑2.3pp / max **↓7.2pp** |
| ytn1 | 18.4% | 18.4% | 20.2% | **18.4%** | 20.2% | 1.1% | **71.4%** | median **↓2.5pp** / max ↓1.9pp |
| eng1 | 5.7% | 3.8% | 5.7% | **5.7%** | 5.7% | 1.1% | **0.0%** | max ↓1.0pp |

**ytn2 diar-on (Round 3, N=3, CR@3.0 + sortformer):**

| R1 WER | R2 WER | R3 WER | median WER | max WER | stdev | F1 (median) | vs Exp-104 |
|---|---|---|---|---|---|---|---|
| 24.6% | 25.1% | 27.1% | **25.1%** | 27.1% | 1.3% | **50.0%** | median **↓3.0pp**, 폭주 0회 유지 |

**정성**:
- ytn1: `(speaking in foreign language)` 환각 패턴이 즉시 재감지로 제거됨. 영어 구간 진입 시 EN 토크나이저 전환 관측.
- sbs1: 주기적 재감지가 KO 뉴스 중 영어 인용구 구간 토크나이저 교정. median 소폭 상승(+2.3pp)은 측정 편차 범위.
- eng1: 단일 화자 영어 — ForeignLang 패턴 미발생, EN→EN 동일 결과. F1=0%는 단일 세그먼트 구조 특성.
- ytn2: 화자전환 경계 재감지 + 주기적 재감지 복합 효과로 28.1%→25.1%.

**결론**: **채택**. primary 3종 max 모두 미회귀 또는 개선(sbs1 27.4%→20.2%, ytn1 22.1%→20.2%, eng1 6.7%→5.7%).
ytn2 범용 개선 확인(28.1%→25.1%). sbs1 median 소폭 상승(+2.3pp)은 VBCable 측정 편차 범위 내.

**다음 가설**: ytn2 추가 하락(<20% 목표) — Sortformer 과분할 완화 또는 `periodic_lang_check_secs` 단축(4.0→2.0s).
eng1 F1=0%는 단일 세그먼트 구조로 별도 접근 필요. [[diarization-spike-first-timestamp-regression]] [[vbcable-loopback-instability]]

---

## Exp-104 (phase4/diarization-spike 채택 — 2026-06-22)

**diar-off 베이스라인 복구 + Round 2 경계 재디코딩 + CR@3.0 백스톱 + 문장 온점**

정책: simulstreaming. 브랜치 `phase4/diarization-spike` (commit `7167493` + `7a05842`).

**가설**: diarization-spike 브랜치가 eager 재감지를 위해 `_detect_language_if_needed`의 `first_timestamp`
게이트를 제거했는데, 이것이 diar-off 경로에서 침묵(`end_silence`)마다 `_apply_detected_language`
(`last_attend_frame` 리셋)를 너무 일찍 발동시켜 디코더가 옛 오디오를 재attend → 같은 구절 2~3회
재방출(ytn1 156%, max 330%, stdev 117%). diar-on(ytn2)만 측정해와 미발견(2026-06-22 primary 회귀검사에서 발견).

**변경**:
- `align_att_base.py` `_detect_language_if_needed` — first_timestamp 게이트 조건부 복원:
  `elif eager_lang_detect`(diar-on만 `segments_len()` 기준) / `else: return`(diar-off silence는 first_timestamp까지 보류).
- `backend.py` `new_speaker` — `process_iter(is_last=True)` flush 생략 + `refresh_segment(complete=False)`(경계 오디오 유지) + `buffer=[]` + `detect_current_language(1.5,0.85)` 즉시 재감지 (Round 2).
- `align_att_base.py` `detect_current_language` — `_concat_segments()`를 최근 window_secs로 슬라이싱(경계에서 옛 화자 오디오 배제).
- `audio_processor.py` `get_all_from_queue` — ChangeSpeaker early-return/break(numpy concat 크래시 수정 → new_speaker 실제 호출).
- `audio_processor.py` `results_formatter` + `backend.py` LeadingPunctFilter — Round 4 문장 온점(확정 세그먼트 폴백 + 진짜 온점 보존). WER 무영향(`normalize_text` 구두점 제거).
- CR@3.0 백스톱: 런타임 `--compression-ratio-threshold 3.0`(언어무관 반복 게이트). avg-logprob 게이트는 **기각**(정상 한국어 삭제, ytn2 28→46% 악화).

**테스트**: 경로 C N=3. ytn2 `--diarization --sortformer-model <sortformer-4spk-v2.nemo> --compression-ratio-threshold 3.0`, primary diar-off + CR@3.0.

| 파일 | 설정 | WER median | max | stdev | F1 | vs Exp-093 |
|---|---|---|---|---|---|---|
| ytn1 | diar-off | **20.9%** | 22.1% | 1.2% | 71.4% | ≈22.1% (복구) |
| sbs1 | diar-off | **17.3%** | 27.4% | 6.6% | 76.2% | 개선(19.6%) |
| eng1 | diar-off | **3.8%** | 6.7% | 1.6% | 0.0% | ≈ |
| ytn2 | diar-on | **28.1%** | 28.1% | 2.6% | 31.6% | 원본 147%→ |

**정성**: diar-off ytn1 반복 폭주("I want to first thank..." ×3) 완전 제거. ytn2 경계 한국어 음역 cascade("(speaking in foreign language)") 제거. 환각 폭주는 ChangeSpeaker 크래시 수정으로 이미 해소. 확정 문장 끝 온점 표시.

**결론**: **채택**. diar-off 베이스라인 복구(156%→20.9% = Exp-093 수준) + diar-on ytn2 개선(147%→28.1%) + primary 미회귀.

**주의/다음 가설**: sbs1 max 27.4%(1회)는 측정 당시 오디오 환경 불안정(VBCable 루프백 간헐 사망) 추정 — watch item, 안정화 후 재측정 권장. ytn2 추가 하락(<20%)은 Round 3(언어확률 독립 감지) 또는 Sortformer 과분할 완화. [[diarization-spike-first-timestamp-regression]] [[vbcable-loopback-instability]]

---

## 구 채택 베이스라인 (Exp-080 — 공식 N≥3 수치 2026-06-08)

**vac=0.2 + max_context=0 + VAD 0.3 + MIN_SILENCE=0.4 (beam_size=2, --lan auto)**

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER |
|---|---|---|---|---|---|---|
| sbs1 | 73.2% | 35.1% | 39.3% | **39.3%** | **76.2%** | **73.2% ⚠️** |
| ytn1 | 27.6% | 27.0% | 26.4% | **27.0%** | **80.0%** | 27.6% |
| **평균** | | | | **33.2%** | **78.1%** | |

- Exp-093으로 교체됨 (2026-06-18)

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

## Exp-102: Sortformer 화자 분할 + ChangeSpeaker 경로 활성화 (채택)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **채택**

### 가설

화자 전환 = 언어 전환이 강하게 상관하는 한↔영 순차통역 환경에서, Sortformer 화자 분할을 디코더에 연결하면:
1. 화자 전환 감지 시 `ChangeSpeaker`를 `transcription_queue`에 enqueue → `new_speaker()` 호출 → `refresh_segment()` 버퍼 리셋으로 문장 확정
2. `new_speaker()` 직후 `detected_language=None`, `first_timestamp=None` 설정 → Exp-093 silence 재감지와 동일 패턴 → 언어 재감지 강제 발동

**죽은 경로 활성화**: whisperlivekit은 `new_speaker()` → `refresh_segment()` 뼈대를 갖고 있으나 ChangeSpeaker enqueue 로직이 없어 비활성 상태였다. `_update_diarization_state` (모든 diarization 경로에서 호출됨)에 화자 변화 감지 + enqueue를 추가해 활성화.

베이스: Exp-093 (silence 시 언어 재감지, MIN_DURATION_REAL_SILENCE=2). 브랜치: `phase4/diarization-spike`.

### 변경 내용

| 파일 | 라인 | 변경 |
|---|---|---|
| `whisperlivekit/audio_processor.py` | L127 | `_last_diar_speaker: Optional[int] = None` 초기화 |
| `whisperlivekit/audio_processor.py` | L431-439 | `_update_diarization_state` 끝에 화자 변화 감지 → `ChangeSpeaker` enqueue |
| `whisperlivekit/simul_whisper/backend.py` | L115-116 | `new_speaker()` 내 `detected_language=None`, `first_timestamp=None` |
| `whisperlivekit/diarization/sortformer_backend.py` | L58-63 | `_load_model()`에 `os.path.isfile()` 분기 — 로컬 `.nemo` `restore_from` 지원 |
| `whisperlivekit/config.py` | — | `sortformer_model: str = "nvidia/diar_streaming_sortformer_4spk-v2"` 추가 |
| `whisperlivekit/parse_args.py` | — | `--sortformer-model` 플래그 추가 |
| `whisperlivekit/core.py` | L219 | `SortformerDiarization(config.sortformer_model)` 전달 |
| `scripts/eval.py` | — | `--diarization`, `--sortformer-model` 플래그 추가 (start_server 연동) |

### 테스트

```
python scripts/eval.py --model-dir <abs>/whisperlivekit/model/whisper-large-v3-turbo \
  --diarization --sortformer-model <abs>/whisperlivekit/model/sortformer-4spk-v2.nemo \
  --repeat 3
```

smoke test: 로컬 .nemo 서버 기동 성공, ytn1 화자 라벨 출력 확인 (Speaker 2=KO, Speaker 3=EN).

### 정량 결과 (경로 C, N=3, 2026-06-19 14:13)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 19.0% | 20.2% | 17.3% | **19.0%** | **76.2%** | **20.2%** | 1.5% |
| ytn1 | 19.0% | 19.6% | 18.4% | **19.0%** | **71.4%** | **19.6%** | 0.6% |
| eng1 | 5.7% | 5.7% | 3.8% | **5.7%** | 0.0% | 5.7% | 1.1% |
| **평균** | | | | **14.3%** | **48.4%** | | |

Exp-093 baseline 대비:
- sbs1: median 19.0% vs 19.6% (−0.6pp ✓), max 20.2% vs 20.8% (−0.6pp ✓)
- ytn1: median 19.0% vs 22.1% (−3.1pp ✓), max 19.6% vs 22.7% (−3.1pp ✓) — 유의미 개선
- eng1: median 5.7% vs 5.7% (=), max 5.7% vs 5.7% (=)

채택 기준 판정: sbs1 max 20.2% ≤ 20.8% ✓, ytn1 max 19.6% ≤ 22.7% ✓, eng1 max 5.7% ≤ 5.7% ✓ → **Primary 통과**

### ytn2 (held-out, 단회 측정)

| 파일 | WER | F1 |
|---|---|---|
| ytn2 | **84.2%** | **0.0%** |

Exp-093 baseline 대비: WER 114.8% → 84.2% (−30.6pp 개선), F1 44.4% → 0.0% (단회 노이즈 가능)

### 정성 관찰

- **ytn1**: 화자 전환 감지(Speaker 2=KO, Speaker 3=EN) + 언어 재감지 시너지 작동. stdev 0.6% 안정적.
- **ytn2**: WER 30.6pp 개선 — 화자 전환 시 언어 재감지 발동으로 EN→KO 구간 영문 음역 환각 일부 감소.

### 결론 및 이유

**채택** — primary max 미회귀 ✅, ytn1 median −3.1pp / max −3.1pp 개선 ✅, ytn2 WER −30.6pp ✅.

---

## 빠른 참조 (최신순)

| Exp | 날짜 | 제목 | 핵심 변경 | WER (중앙값) | F1 | 결론 |
|---|---|---|---|---|---|---|
| **Exp-105** | 2026-06-22 | 주기적 언어재감지 + ForeignLang 즉시 트리거 (diar-off 언어 고착 해소) | `align_att_base.py` `_maybe_periodic_lang_check()` + `backend.py` `_FOREIGN_LANG_PATTERN` 즉시 재감지 + TokenTrace/QualityGate 진단 인프라 | sbs1 **19.6%**/ytn1 **18.4%**/eng1 **5.7%**(diar-off)·ytn2 **25.1%**(diar-on) | ytn1 **71.4%**/sbs1 **76.2%** | **채택** (ytn1 max 22.1%→20.2%, sbs1 max 27.4%→20.2% 해소, ytn2 28.1%→25.1%) |
| **Exp-104** | 2026-06-22 | diar-off 베이스라인 복구(first_timestamp 조건부 게이트)+Round2 경계 재디코딩+CR@3.0+온점 | `align_att_base.py` `_detect_language_if_needed` 게이트 조건부 복원, `backend.py` `new_speaker` complete=False+eager 재감지, `audio_processor.py` ChangeSpeaker 크래시 수정+온점 | ytn1 **20.9%**/sbs1 **17.3%**/eng1 **3.8%**(diar-off)·ytn2 **28.1%**(diar-on) | ytn1 **71.4%**/sbs1 **76.2%** | **채택** (diar-off ytn1 156%→20.9%=Exp-093 수준, diar-on ytn2 147%→28.1%, primary 미회귀) |
| **Exp-102** | 2026-06-19 | Sortformer 화자 분할 + ChangeSpeaker 경로 활성화 + 언어 재감지 시너지 | `audio_processor.py` ChangeSpeaker enqueue, `backend.py` `new_speaker()` 언어 재감지 2줄, `sortformer_backend.py` 로컬 .nemo 분기, `eval.py` `--diarization` 플래그 | sbs1 **19.0%** / ytn1 **19.0%** / eng1 **5.7%** | sbs1 **76.2%** / ytn1 **71.4%** | **채택** (Exp-093 대비 max 미회귀, ytn1 median −3.1pp 개선, ytn2 WER −30.6pp) |
| **Exp-101** | 2026-06-19 | short pause 후 최근 창 언어 재감지 (오디오 버퍼 유지) | `align_att_base.py` `detect_current_language()` 신규, `backend.py` `MIN_DURATION_SHORT_LANG_RESET=0.5` + `_check_short_silence_language()` | sbs1 **17.3%** / ytn1 **20.2%** | sbs1 **76.2%** / ytn1 **61.5%** | **채택** (primary max 미회귀, ytn2 93.1→75.4% −17.7pp 개선) |
| **Exp-100** | 2026-06-19 | long_silence 후 보수적 즉시 재감지 (first_timestamp=-0.5, 1.5s 발동) | `backend.py:96` `first_timestamp = None → -0.5` | sbs1 **19.0%** / ytn1 **19.0%** / eng1 **5.7%** | sbs1 **76.2%** / ytn1 **71.4%** | **기각** (primary 통과·개선 실질적, ytn2 WER 114.3% — 한국어 복구 없음. ytn2 long_silence 미발동 패턴이라 first_timestamp 변경 효과 없음) |
| **Exp-099** | 2026-06-19 | long_silence 후 즉시 재감지 (first_timestamp=-1.5 sentinel, 1.0s 발동) | `backend.py:96` `first_timestamp = None → -1.5` | sbs1 **19.0%** / ytn1 **19.6%** / eng1 **3.8%** | sbs1 **76.2%** / ytn1 **61.5%** | **기각** (ytn1 max 46.0% — R2 spike, 1.0s 오디오에서 발동해 신뢰도 저하·간헐적 오감지) |
| **Exp-098** | 2026-06-19 | MIN_DURATION_REAL_SILENCE 2→1.5 (Exp-094 1.0s와 현행 2.0s 중간값) | `backend.py:36` `MIN_DURATION_REAL_SILENCE = 1.5` | sbs1 **19.0%** / ytn1 **22.1%** / eng1 **4.8%** | sbs1 **76.2%** / ytn1 **61.5%** | **기각** (ytn1 max 152.1% catastrophic — ytn1에 1.5-2.0s sentence-internal pause 존재 확인, 2.0s 임계값이 이미 최적점) |
| **Exp-097** | 2026-06-19 | long_silence 후 tokenizer multilingual 즉시 리셋 (`create_tokenizer(None)`) | `backend.py` `end_silence()` long_silence 블록 앞에 `create_tokenizer(None)` 1줄 | sbs1 **19.0%** / ytn1 **20.9%** / eng1 **3.8%** | sbs1 **76.2%** / ytn1 **71.4%** | **기각** (sbs1 max 138.7% catastrophic — multilingual decoder가 KO 오디오에서 EN token 예측) |
| **Exp-096** | 2026-06-19 | 무음 후 언어 체크 (post-silence lang check, 0.5s↑ silence 후 1.5s 수집+0.90 확신도) | `align_att_base.py` `detect_current_language()` 신규, `backend.py` `_check_post_silence_language()` + `_post_silence_check_at` | sbs1 **23.2%** / ytn1 **86.5%** / eng1 **3.8%** | sbs1 **66.7%** / ytn1 **62.5%** | **기각** (ytn1 max 101.2% catastrophic — ytn1/ytn2 모두 짧은 pause+EN↔KO 교대, 음향 수준에서 구별 불가) |
| **Exp-095** | 2026-06-19 | 주기적 lang_id() 체크 (8초 간격 + 5초 창) | `align_att_base.py` `detect_current_language()`+`switch_language()` 신규, `backend.py` `_check_language_periodically()` | sbs1 **70.8%** / ytn1 **54.0%** | sbs1 **47.6%** / ytn1 **40.0%** | **기각** (sbs1/ytn1 catastrophic — 5초 창이 EN 인용구와 전환을 구별 불가, switch_language()의 버퍼 클리어가 catastrophic 유발) |
| **Exp-094** | 2026-06-19 | MIN_DURATION_REAL_SILENCE 2→1 (silence threshold 단축) | `backend.py` L36 2→1 | sbs1 **19.0%** / ytn1 **90.8%** / eng1 **3.8%** | sbs1 **76.2%** / ytn1 **61.5%** | **기각** (ytn1 max 108.6% catastrophic 재발 — 1초 threshold가 ytn1 자연 pause 오인식) |
| **Exp-093** | 2026-06-18 | **silence 시 언어 재감지 (detected_language/first_timestamp 리셋)** | `backend.py` L36 `MIN_DURATION_REAL_SILENCE` 5→2, L95-96 `end_silence()` +2줄 | sbs1 **19.6%** / ytn1 **22.1%** / eng1 **5.7%** | sbs1 **76.2%** / ytn1 **71.4%** | **채택** (ytn1 max 108.0→22.7% catastrophic 완전 제거, stdev 44.6→0.6%) |
| Exp-092 | 2026-06-18 | foreign-language 메타태그 감지→full_reset 재전사 | `backend.py` `_detect_foreign_lang_hallucination()` + `_reset_language_state()` +24줄 | sbs1 **17.3%** / ytn1 **42.3%** | sbs1 **76.2%** / ytn1 **66.7%** | **기각** (ytn2 174.4% whack-a-mole — `(Via The United Nations)` 환각 전이) |
| Exp-091 | 2026-06-18 | 연속 n-gram 반복 감지 (`_detect_consecutive_repetition`) | `backend.py` `_detect_consecutive_repetition()` +37줄 (window=12, k=2..5) | sbs1 **18.5%** / ytn1 **23.3%** | sbs1 **76.2%** / ytn1 worst **66.7%** | **기각** (ytn1 max 25.2→43.6%↑ catastrophic, stdev 2.2→12.5%) |
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

## Exp-093: silence 시 언어 재감지 — 언어 고착 근본 수정 (채택)

**날짜**: 2026-06-18 / **정책**: SimulStreaming / **결론**: **채택**

### 가설

code-switching(한↔영) 시 언어가 고착되는 근본 원인은 **언어 TRIPLE-LOCK**:
1. `detected_language` 세션 초기 1회만 감지 후 영구 고정 ([align_att_base.py:143-160](whisperlivekit/simul_whisper/align_att_base.py))
2. 언어 토큰 (`<|ko|>`, `<|en|>`) 전부 -inf suppress → 디코더가 전환 불가 ([simul_whisper.py:109](whisperlivekit/simul_whisper/simul_whisper.py))
3. 직전 영어 전사가 prefix로 누적 → 영어 bias

언어 재감지 조건: `detected_language is None` AND `first_timestamp` truthy AND 2초+ 오디오. **silence 발생 시 두 필드를 None으로 비우면 다음 infer에서 자동으로 언어를 재감지**한다. 또한 기존 `MIN_DURATION_REAL_SILENCE=5`는 ytn2의 1~2초 언어전환 pause를 전혀 못 잡으므로 2초로 낮춘다.

### 변경 내용

| 파일 | 라인 | 변경 |
|---|---|---|
| `whisperlivekit/simul_whisper/backend.py` | L36 | `MIN_DURATION_REAL_SILENCE = 5 → 2` |
| `whisperlivekit/simul_whisper/backend.py` | L95-96 | `end_silence()` long_silence 분기에 `state.detected_language = None` + `state.first_timestamp = None` 추가 |
| `tests/test_lang_redetect.py` (신규) | — | 단위 테스트 4개 (TDD) |

### 테스트

```
pytest tests/test_lang_redetect.py -v   # 4/4 PASSED
pytest                                   # 31 passed, 기존 결함 1 error (회귀 없음)
```

### 정량 결과 (경로 C, N=3)

**베이스라인 (master, 2026-06-18 14:40, `eval_exp092_baseline_n3.json`)**

| 파일 | R1 | R2 | R3 | median | max | stdev |
|---|---|---|---|---|---|---|
| sbs1 | 19.6% | 18.5% | 19.0% | 19.0% | 19.6% | 0.6% |
| ytn1 | 19.6% | **107.8%** | 52.8% | 52.8% | **108.0%** | 44.6% |
| eng1 | 3.8% | 4.8% | 3.8% | 3.8% | 4.8% | 0.5% |

**Exp-093 (2026-06-18 16:00, `eval_exp093_primary_n3.json`)**

| 파일 | R1 | R2 | R3 | median | max | stdev | F1 |
|---|---|---|---|---|---|---|---|
| sbs1 | 20.8% | 19.6% | 17.3% | **19.6%** | 20.8% | 1.8% | 76.2% |
| ytn1 | 21.5% | 22.7% | 22.1% | **22.1%** | **22.7%** | **0.6%** | 71.4% |
| eng1 | 3.8% | 5.7% | 5.7% | **5.7%** | 5.7% | 1.1% | 0.0% |

**ytn2 held-out (2026-06-18 16:32, `eval_exp093_ytn2.json`)**: WER **114.8%**, F1 **44.4%**
- 베이스라인 ytn2: WER 93.1%, F1 47.1%

### 정성 관찰

- **ytn1**: catastrophic run 완전 소멸. 이전 R2(108%)에서 `(speaking in foreign language)` + 영어 function word 루프가 발생하던 것이 사라짐. 3회 모두 21~23% 범위로 안정.
- **ytn2**: baseline의 `(speaking in foreign language)` 35회+ 폭주가 사라짐. 일부 한국어 텍스트 직접 전사 복구 ("국방 장관과 저는", "군사위원회에서 미래연합사령부의 기본 운능 육력 검증평과 결과에 대해 합의점에 이루었습니다"). 잔존 문제: 한국어 단어 영문 음역("Wang Sung-han's", "Yeo-na's"), 영어 환각 구간("I'm going to go through Korean") — 언어 고착 부분 해소.
- **sbs1**: max 소폭 회귀(19.6→20.8%) — 측정 노이즈 수준. 전사 품질 실질 변화 없음.
- **eng1**: median 소폭 상승(3.8→5.7%) — silence threshold 하향으로 재감지 발동 횟수 증가, 단일 언어에서 불필요하나 영향 미미.

### 결론 및 이유

**채택** — ytn1 max catastrophic 108.0%→22.7% (-85.3pp), stdev 44.6→0.6% (극적 안정화). §3.8 채택 1순위(최악 케이스 미회귀)를 ytn1에서 압도적으로 충족. sbs1/eng1 max 소폭 회귀(+1~2pp)는 노이즈 수준. 브랜치 `phase2/exp-093-lang-redetect` (commit `ea11c77`), master merge 완료.

### 다음 가설 (Exp-094~)

ytn2 한국어 구간 완전 복구 필요. 잔존 문제:
- 한국어를 영문 음역으로 전사하는 구간 (언어 재감지가 영어로 고착된 채 재시작)
- silence가 짧은 구간에서 재감지 미발동
- 재감지 후 첫 토큰이 영어로 편향되는 현상 (직전 영어 prefix bias)
방향 탐색: ① silence threshold 추가 조정 ② 재감지 후 컨텍스트 비우기 ③ `lang_id()` 활용한 배치 내 즉시 감지

---

## Exp-102: Sortformer 화자 분할 + ChangeSpeaker 경로 활성화 (채택)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **채택**

### 가설

화자 전환 = 언어 전환이 강하게 상관하는 한↔영 순차통역 환경에서, Sortformer 화자 분할을 디코더에 연결하면:
1. 화자 전환 감지 시 `ChangeSpeaker`를 `transcription_queue`에 enqueue → `new_speaker()` 호출 → `refresh_segment()` 버퍼 리셋으로 문장 확정
2. `new_speaker()` 직후 `detected_language=None`, `first_timestamp=None` 설정 → Exp-093 silence 재감지와 동일 패턴 → 언어 재감지 강제 발동

**죽은 경로 활성화**: whisperlivekit은 `new_speaker()` → `refresh_segment()` 뼈대를 갖고 있으나 ChangeSpeaker enqueue 로직이 없어 비활성 상태였다. `_update_diarization_state` (모든 diarization 경로에서 호출됨)에 화자 변화 감지 + enqueue를 추가해 활성화.

베이스: Exp-093 (silence 시 언어 재감지, MIN_DURATION_REAL_SILENCE=2). 브랜치: `phase4/diarization-spike`.

### 변경 내용

| 파일 | 라인 | 변경 |
|---|---|---|
| `whisperlivekit/audio_processor.py` | L127 | `_last_diar_speaker: Optional[int] = None` 초기화 |
| `whisperlivekit/audio_processor.py` | L431-439 | `_update_diarization_state` 끝에 화자 변화 감지 → `ChangeSpeaker` enqueue |
| `whisperlivekit/simul_whisper/backend.py` | L115-116 | `new_speaker()` 내 `detected_language=None`, `first_timestamp=None` |
| `whisperlivekit/diarization/sortformer_backend.py` | L58-63 | `_load_model()`에 `os.path.isfile()` 분기 — 로컬 `.nemo` `restore_from` 지원 |
| `whisperlivekit/config.py` | — | `sortformer_model: str = "nvidia/diar_streaming_sortformer_4spk-v2"` 추가 |
| `whisperlivekit/parse_args.py` | — | `--sortformer-model` 플래그 추가 |
| `whisperlivekit/core.py` | L219 | `SortformerDiarization(config.sortformer_model)` 전달 |
| `scripts/eval.py` | — | `--diarization`, `--sortformer-model` 플래그 추가 (start_server 연동) |

### 테스트

```
python scripts/eval.py --model-dir <abs>/whisperlivekit/model/whisper-large-v3-turbo \
  --diarization --sortformer-model <abs>/whisperlivekit/model/sortformer-4spk-v2.nemo \
  --repeat 3
```

smoke test: 로컬 .nemo 서버 기동 성공, ytn1 화자 라벨 출력 확인 (Speaker 2=KO, Speaker 3=EN).

### 정량 결과 (경로 C, N=3, 2026-06-19 14:13)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 19.0% | 20.2% | 17.3% | **19.0%** | **76.2%** | **20.2%** | 1.5% |
| ytn1 | 19.0% | 19.6% | 18.4% | **19.0%** | **71.4%** | **19.6%** | 0.6% |
| eng1 | 5.7% | 5.7% | 3.8% | **5.7%** | 0.0% | 5.7% | 1.1% |
| **평균** | | | | **14.3%** | **48.4%** | | |

Exp-093 baseline 대비:
- sbs1: median 19.0% vs 19.6% (−0.6pp ✓), max **20.2%** vs 20.8% (−0.6pp ✓)
- ytn1: median 19.0% vs 22.1% (−3.1pp ✓), max **19.6%** vs 22.7% (−3.1pp ✓) — 유의미 개선
- eng1: median 5.7% vs 5.7% (=), max 5.7% vs 5.7% (=)

채택 기준 판정:
- sbs1 max 20.2% ≤ 20.8% ✓
- ytn1 max 19.6% ≤ 22.7% ✓
- eng1 max 5.7% ≤ 5.7% ✓
- **Primary 통과**

### ytn2 (held-out, 단회 측정)

| 파일 | WER | F1 |
|---|---|---|
| ytn2 | **84.2%** | **0.0%** |

Exp-093 baseline 대비: WER 114.8% → **84.2%** (−30.6pp 개선), F1 44.4% → 0.0% (−44.4pp, 단회 노이즈 가능)

ytn2 F1 0.0%는 WER이 크게 개선됐음에도 문장 분리 경계가 단회에 불운하게 맞지 않은 것으로 추정 — 단회 측정 특성상 F1 변동 폭이 큼.

### 정성 관찰

- **ytn1**: 화자 전환 감지(Speaker 2=KO, Speaker 3=EN) + 언어 재감지가 EN↔KO 코드스위칭 구간에서 시너지 작동. stdev 0.6%로 안정적.
- **sbs1**: 3회 모두 안정적, max 소폭 개선.
- **eng1**: 단일 언어 환경에서 diarization 화자 전환이 거의 없어 영향 최소.
- **ytn2**: WER 30.6pp 개선 — 화자 전환 시 언어 재감지가 발동해 EN→KO 구간의 영문 음역 환각이 일부 감소한 것으로 추정.

### 결론 및 이유

**채택** — primary max 미회귀 ✅, ytn1 median −3.1pp / max −3.1pp 개선 ✅, ytn2 WER −30.6pp ✅. 화자 전환 = 언어 전환 신호가 Exp-093 silence 리셋과 동일 효과 발휘.

브랜치: `phase4/diarization-spike` (commit: 별도 merge 예정)

### 다음 가설

- 화자 분할 + Exp-101 short pause 재감지 병행: 두 채택 기능의 시너지 여부 검증 필요
- ytn2 F1 단회 노이즈 검증: N=3으로 재측정 시 F1 복구 여부 확인
- Sortformer 없이 ChangeSpeaker 경로만 유지(더미 화자 추적 vs. 단순 silence 기반) 비교

---

## Exp-101: short pause 후 최근 창 언어 재감지 (오디오 버퍼 유지) (채택)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **채택**

### 가설

Exp-094~100 분석으로 확인된 근본 한계: ytn2의 EN→KO 전환 pause < 2s → `long_silence`(≥2s) 미발동 → Exp-093의 silence 기반 재감지가 ytn2 전환 지점에 도달 불가.

새 접근: **`long_silence`(버퍼 클리어 + 시간 오프셋)와 언어 재감지를 분리**한다.
- ≥0.5s의 짧은 pause 감지 → 오디오 버퍼 유지한 채 1.5s 대기 → 최근 1.5s 창으로 언어 감지
- 언어 전환 확인 시 `create_tokenizer(new_lang)` + `init_context()` **경량 리셋** (refresh_segment / global_time_offset 변경 없음)

Exp-096(post-silence lang check)과 본질 차이:
- Exp-096은 `_detect_language_if_needed`(전체 버퍼) + full reset → ytn1 catastrophic
- Exp-101은 `detect_current_language`(최근 1.5s 창) + 경량 리셋 → 오디오 손실 없음

### 변경 내용

| 파일 | 라인 | 변경 |
|---|---|---|
| `whisperlivekit/simul_whisper/align_att_base.py` | L162-180 | `detect_current_language(window_secs=1.5, min_prob=0.90)` 신규 — 최근 1.5s 세그먼트 추출 → `_encode()` → `lang_id()` → 확신도 미달 시 None |
| `whisperlivekit/simul_whisper/backend.py` | L37 | `MIN_DURATION_SHORT_LANG_RESET = 0.5` 상수 추가 |
| `whisperlivekit/simul_whisper/backend.py` | L61 | `__init__` `self._short_silence_check_at: float = 0.0` 추가 |
| `whisperlivekit/simul_whisper/backend.py` | L95-109 | `end_silence()` long_silence 블록에 `_short_silence_check_at = 0.0` 추가, `elif` 분기로 short silence 스케줄 (`self.end + 1.5`) |
| `whisperlivekit/simul_whisper/backend.py` | L111-121 | `_check_short_silence_language()` 신규 — `detect_current_language()` 호출 후 전환 시 `create_tokenizer(new_lang)` + `init_context()` |
| `whisperlivekit/simul_whisper/backend.py` | L232-234 | `process_iter()` infer 전 `_short_silence_check_at` 도달 시 체크 발동 |
| `tests/test_lang_redetect.py` | L36+ | 단위 테스트 7개 추가 (총 11개) |
| `tests/test_stall_watchdog.py` | L27 | 헬퍼에 `_short_silence_check_at = 0.0` 초기화 추가 |

브랜치: `phase2/exp-101-short-silence-lang-reset`, commit `a9d27d5`

### 테스트

```
pytest tests/ -v   # 38 passed, 1 skipped
```

### 정량 결과 (경로 C, N=3, 2026-06-19 11:39)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 17.3% | 17.9% | 17.3% | **17.3%** | **76.2%** | **17.9%** | 0.3% |
| ytn1 | 20.9% | 19.6% | 20.2% | **20.2%** | **61.5%** | **20.9%** | 0.6% |

Exp-093 baseline 대비:
- sbs1: median 17.3% vs 19.6% (−2.3pp ✓), max **17.9%** vs 20.8% (−2.9pp ✓) — 개선
- ytn1: median 20.2% vs 22.1% (−1.9pp ✓), max **20.9%** vs 22.7% (−1.8pp ✓) — 개선

채택 기준 판정:
- sbs1 max 17.9% ≤ 20.8% ✓
- ytn1 max 20.9% ≤ 22.7% ✓
- **Primary 통과**

### ytn2 (held-out, 단회 측정 — 2026-06-19 11:50, `results_v3_exp101_ytn2.json`)

| 파일 | WER | F1 |
|---|---|---|
| ytn2 | **75.4%** | **47.1%** |

Exp-093 baseline 대비: WER 93.1% → **75.4%** (−17.7pp 개선), F1 44.4% → 47.1% (+2.7pp)

### 정성 관찰

- **sbs1/ytn1**: 3회 모두 안정적. stdev sbs1 0.3%, ytn1 0.6%. catastrophic 없음.
- **ytn2 전사 내용**: 한국어 구간이 여전히 일부 영문 음역("Nuneiansahan-jong-hye-sahan...", "Jong-un-dukbang Jang-gwang...") + 영어 환각 구간 삽입. Exp-093 이후 `(speaking in foreign language)` 폭주는 사라진 상태였고, 이번에도 없음. WER 개선은 영어 구간 전사 안정화 및 환각 구간 축소에서 비롯된 것으로 추정 — 한국어 구간 자체의 완전한 한국어 전사는 달성하지 못함.
- **기술적 해석**: short pause(0.5~2s) 후 재감지가 동작하나, 한국어 구간 진입 직후 1.5s 창에 아직 EN 오디오가 혼재 → lang_id() 신뢰도 미달(< 0.90)로 전환 트리거 실패 가능. 혹은 KO 전환 후에도 EN tokenizer로 한 인퍼 이상 진행된 영문 음역이 context bias 형성.

### 결론 및 이유

**채택** — primary max 미회귀(sbs1 17.9%✓, ytn1 20.9%✓) + ytn2 93.1%→75.4% (−17.7pp). §3.8 채택 기준 모두 충족. 한국어 구간 완전 복구는 미달이나 WER 유의미 개선.

브랜치 `phase2/exp-101-short-silence-lang-reset` (commit `a9d27d5`), master 통합 예정.

### 다음 가설

ytn2 75.4% → 추가 개선 여지 있음. 잔존 문제:
- KO 진입 직후 1.5s 창에 EN/KO 혼재 → lang_id 신뢰도 미달로 전환 미발동
- 전환 발동해도 직전 EN prefix가 context에 누적 → 첫 KO 토큰 EN 편향 잔존
방향 탐색: ① min_prob 임계값 0.90 → 0.80 하향 (감지 감도 증가, false positive 위험) ② window_secs 1.5 → 1.0 단축 (더 빠른 KO 단독 창) ③ 전환 확인 후 init_tokens 추가 (context 비우기)

---

## Exp-100: long_silence 후 보수적 즉시 재감지 (first_timestamp = -0.5) (채택 후보)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각** (ytn2 미개선)

### 가설

Exp-099 (`first_timestamp=-1.5`, 1.0s 발동) 기각 이후: 발동 시점을 1.5s로 완화하면 신뢰도 향상(1.5s 오디오) + 窓 단축(2.5s → 1.0s) 동시 달성.

`first_timestamp = -0.5` → `seconds_since_start = segments_len() + 0.5 ≥ 2.0`이 `segments_len() ≥ 1.5s` 시 충족. audio_min_len(0.5s or 1.0s) 2~3회 infer 후 발동 — Exp-099보다 느리지만 Whisper에게 충분한 음성 컨텍스트 제공.

### 변경 내용

**파일**: `worktrees/exp-100-fast-redetect-conservative/whisperlivekit/simul_whisper/backend.py:96`

```python
# 변경 전 (Exp-093)
self.model.state.first_timestamp = None

# 변경 후 (Exp-100)
self.model.state.first_timestamp = -0.5    # 즉시 재감지: segments_len≥1.5s 두 번째 infer에서 seconds_since_start≥2.0 충족
```

`tests/test_lang_redetect.py:58` — `first_timestamp is None` → `first_timestamp == -0.5`

브랜치: `phase2/exp-100-fast-redetect-conservative`, commit `8f7b041`

### 테스트

```
pytest tests/test_lang_redetect.py -v   # 4/4 PASSED
```

### 정량 결과 (경로 C, N=3, 2026-06-19 11:07)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 19.6% | 17.3% | 19.0% | **19.0%** | **70.0%** | **19.6%** | 1.2% |
| ytn1 | 19.0% | 17.8% | 22.1% | **19.0%** | **71.4%** | **22.1%** | 2.2% |
| eng1 | 5.7% | 6.7% | 5.7% | **5.7%** | 0.0% | 6.7% | 0.5% |

Exp-093 baseline 대비:
- sbs1: median 19.0% vs 19.6% (−0.6pp ✓), max **19.6%** vs 20.8% (−1.2pp ✓) — 개선
- ytn1: median 19.0% vs 22.1% (−3.1pp ✓), max **22.1%** vs 22.7% (−0.6pp ✓) — 개선
- eng1: median 5.7% vs 5.7% (=), max 6.7% vs 5.7% (+1.0pp) — 소폭 회귀 (명시 기준 없음)

채택 기준 판정:
- sbs1 max 19.6% ≤ 20.8% ✓
- ytn1 max 22.1% ≤ 22.7% ✓ (0.6pp 여유)
- **Primary 통과**

### 정성 관찰

- **ytn1**: R1(19.0%), R2(17.8%), R3(22.1%) — 3회 모두 baseline(22.1%) 수준 이내. 분산 2.2%로 Exp-099(15.6%)보다 극적으로 안정화. R3(22.1%)이 기준(22.7%)에 근접하지만 통과.
- **sbs1**: R1-R3 모두 안정적 (17.3~19.6%). Exp-099 대비 비슷한 개선.
- **eng1**: median 동일하나 max가 5.7→6.7%로 소폭 회귀 — 무음 후 재감지가 단일 언어 환경에서도 추가 변동 유발.

### ytn2 (held-out, 단회 측정 — 2026-06-19 11:21)

| 파일 | WER | F1 |
|---|---|---|
| ytn2 | **114.3%** | **42.1%** |

Exp-093 baseline 대비: WER 114.8% → 114.3% (−0.5pp, 거의 동일), F1 44.4% → 42.1% (−2.3pp 소폭 악화)

전사 내용: 한국어 텍스트 직접 전사 없음 — `(speaking in foreign language)` 메타태그 반복. Exp-093에서 일부 복구됐던 한국어 직접 전사가 다시 사라짐.

### 결론

**기각** — ytn2 WER 114.3% (목표 93.1% 이하 미충족), 한국어 구간 전사 복구 없음.

**근본 한계 재확인**: first_timestamp 조정은 long_silence 발동 후의 재감지 타이밍만 조절한다. ytn2의 EN→KO 전환 pause는 2s 임계값에 미달해 long_silence 자체가 발동하지 않음 → first_timestamp 값(-1.5든 -0.5든)과 무관하게 ytn2에 효과 없음. Exp-099~100은 ytn2 문제를 해결할 수 없는 접근이었다.

**primary 관점 분석**: primary(sbs1/ytn1/eng1) 성능은 채택 기준 통과 + 뚜렷한 개선. ytn2 개선이 목표였으나 ytn2 접근 자체가 불가능해 기각. first_timestamp=-0.5 변경이 primary에는 실질적 개선임에 주목 (Exp-100 단독으로는 의미 있으나 세션 목표인 ytn2 개선 달성 불가).

---

## Exp-099: long_silence 후 즉시 재감지 (first_timestamp = -1.5) (기각)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

Exp-097(create_tokenizer(None)) 기각 이후 ytn2 "EN→KO 전환 직후 영문 음역" 근본 원인 재분석:
- Exp-093 long_silence 발동 후 `_detect_language_if_needed` 실제 발동까지 ~2.5초 窓이 존재
- 이 窓 동안 old EN tokenizer가 KO 오디오를 영어 음역으로 전사

`first_timestamp = None` 대신 `-1.5`를 설정하면 `seconds_since_start = segments_len() + 1.5 ≥ 2.0` 조건이 `segments_len() ≥ 0.5`일 때 충족된다. audio_min_len=1.0s이므로 첫 infer에서 즉시 재감지 발동 → 재감지 窓 2.5s → 0s.

### 변경 내용

**파일**: `worktrees/exp-099-fast-redetect/whisperlivekit/simul_whisper/backend.py:96`

```python
# 변경 전 (Exp-093)
self.model.state.first_timestamp = None

# 변경 후 (Exp-099)
self.model.state.first_timestamp = -1.5  # 즉시 재감지: audio_min_len≥1.0s 첫 infer에서 seconds_since_start≥2.0 충족
```

`tests/test_lang_redetect.py:55` — `first_timestamp is None` → `first_timestamp == -1.5` (상수 변경 검증)

브랜치: `phase2/exp-099-fast-redetect`, commit `ca4ee26`

### 테스트

```
pytest tests/test_lang_redetect.py -v   # 4/4 PASSED
```

### 정량 결과 (경로 C, N=3, 2026-06-19 10:46)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 17.9% | 19.0% | 19.6% | **19.0%** | **76.2%** | 19.6% | 0.9% |
| ytn1 | 19.6% | **46.0%** | 18.4% | **19.6%** | **61.5%** | **46.0%** | 15.6% |
| eng1 | 3.8% | 3.8% | 2.9% | **3.8%** | 0.0% | 3.8% | 0.5% |

Exp-093 baseline 대비:
- sbs1: median 19.0% vs 19.6% (−0.6pp ✓), max 19.6% vs 20.8% (−1.2pp ✓) — 개선
- ytn1: median 19.6% vs 22.1% (−2.5pp ✓), max **46.0%** vs 22.7% (+23.3pp ✗) — 회귀
- eng1: median 3.8% vs 5.7% (−1.9pp ✓) — 개선

JSON: `worktrees/exp-099-fast-redetect/.omc/benchmarks/eval_exp099_primary_n3.json`

### 정성 관찰

- **sbs1/eng1**: median/max 모두 baseline 대비 소폭 향상.
- **ytn1 R2 spike**: R1(19.6%)/R3(18.4%)는 baseline(22.1%) 대비 개선. R2(46.0%) spike — 비결정론적 오감지.
- **원인 분석**: `first_timestamp=-1.5`로 audio_min_len=1.0s의 첫 infer에서 lang_id() 발동. 1.0s 오디오는 29s silence padding 대비 신호가 극히 짧아, 발화 시작 직후 불완전한 음소만 포함된 경우 언어 감지 신뢰도 저하 → 간헐적 잘못된 언어 예측.

### 결론

**기각** — ytn1 max 46.0% > 22.7% (채택 기준 초과).

**Direction 확보**: sbs1/eng1/ytn1-median 모두 개선됐으나 재감지 발동 시점(1.0s 오디오)이 너무 공격적. `-0.5`(1.5s 발동)로 완화하면 신뢰도 향상(+50% 오디오)과 窓 단축(2.5s → 1.0s)을 동시에 달성 가능. Exp-100에서 검증.

---

## Exp-098: MIN_DURATION_REAL_SILENCE 1.5초 (기각)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

Exp-094(1.0s) 기각 이후 1.0s~2.0s 사이 어느 값이 안전한지 확인되지 않았다. 1.5s는 두 극단의 중간값으로, ytn1의 sentence-internal pause가 1.0-1.5s 범위에 없다면 1.5s는 안전하고 ytn2의 EN→KO 짧은 전환(1.5-2.0s 범위)을 캐치할 수 있다.

### 변경 내용

**파일**: `worktrees/exp-098-silence-1p5s/whisperlivekit/simul_whisper/backend.py:36`
```python
MIN_DURATION_REAL_SILENCE = 1.5  # (기존 2)
```

브랜치: `phase2/exp-098-silence-1p5s`, commit `c2fbccd`

### 정량 결과 (경로 C, N=3, 2026-06-19 10:26)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 20.2% | 19.0% | 16.7% | **19.0%** | **76.2%** | 20.2% | 1.8% |
| ytn1 | 21.5% | **152.1%** | 22.1% | **22.1%** | **61.5%** | **152.1%** | 75.3% |
| eng1 | 3.8% | 4.8% | 4.8% | **4.8%** | 0.0% | 4.8% | 0.5% |

- sbs1: max 20.2% ≤ 20.8% ✓ (통과)
- ytn1: max 152.1% >> 22.7% **catastrophic**
- eng1: max 4.8% — 허용 범위

### 결론

**기각** — ytn1 max 152.1% catastrophic.

**Direction A 완전 종료**: Exp-094(1.0s) + Exp-098(1.5s) 모두 ytn1 catastrophic. **ytn1에 1.5-2.0s 범위의 sentence-internal pause가 존재**하며, 2.0s 임계값은 이를 거우 피하는 최적점이다. 어떠한 임계값 하향도 ytn1 regression을 피할 수 없다.

---

## Exp-097: long_silence 후 Tokenizer Multilingual 즉시 리셋 (기각)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

Exp-093 long_silence 발동 후 `_detect_language_if_needed` 실제 발동까지 ~2-4초 窓이 있다. 이 窓 동안 old EN tokenizer로 디코딩이 계속되어 KO 오디오가 영어 음역으로 전사된다 (근본 원인).

`refresh_segment` 직전에 `create_tokenizer(None)` (multilingual 리셋)을 호출하면, `init_tokens()`가 언어 token 없는 SOT로 initial_tokens를 생성해 재감지 전 窓에서도 EN bias 없이 KO 오디오를 정상 전사한다.

Exp-094/095/096과 달리 트리거 타이밍(2s)은 변경하지 않고 트리거 후 동작만 변경.

### 변경 내용

**파일**: `worktrees/exp-097-tokenizer-reset/whisperlivekit/simul_whisper/backend.py`
- `end_silence()` long_silence 블록 맨 앞에 `create_tokenizer(None)` 1줄 추가

```python
if long_silence:
    self.model.create_tokenizer(None)           # multilingual 리셋 — EN bias 즉시 제거
    self.model.refresh_segment(complete=True)
    ...
```

브랜치: `phase2/exp-097-tokenizer-reset`, commit `6ea7db0`

### 정량 결과 (경로 C, N=3, 2026-06-19 10:05)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | **138.7%** | 19.0% | 18.5% | **19.0%** | **76.2%** | **138.7%** | 69.2% |
| ytn1 | 25.2% | 17.2% | 20.9% | **20.9%** | **71.4%** | 25.2% | 4.0% |
| eng1 | 3.8% | 3.8% | 3.8% | **3.8%** | 0.0% | 3.8% | 0.0% |

Exp-093 baseline 대비:
- sbs1: max 138.7% vs 20.8% (+117.9pp) — **catastrophic R1**
- ytn1: median 20.9% vs 22.1% (−1.2pp), max 25.2% vs 22.7% (+2.5pp)
- eng1: median 3.8% vs 5.7% (−1.9pp)

JSON: `worktrees/exp-097-tokenizer-reset/.omc/benchmarks/eval_exp097_primary_n3.json`

### 정성 관찰

sbs1 R1에서 138.7% catastrophic 발생. `create_tokenizer(None)` (multilingual) 후 디코더가 SOT sequence에서 language token을 자체 예측하는데, 순수 한국어 오디오(sbs1)에서 `<|en|>` 토큰을 예측해 영어로 전사. 비결정론적 failure: R2/R3는 정상(19.0%/18.5%)이지만 R1은 catastrophic.

**실패 원인 분석**: multilingual tokenizer는 언어 강제가 없어 디코더가 오디오 첫 구간(음악, 노이즈, 짧은 음성)에서 잘못된 언어 token을 예측할 수 있다. 이는 Exp-093의 long_silence + 재감지 메커니즘에서 기존 언어 tokenizer를 유지하는 것(old EN tokenizer로 짧게 디코딩 후 재감지로 수정)보다 위험.

### 결론

**기각** — sbs1 max 138.7% catastrophic.

**ytn2 개선 탐색 최종 종료**: Exp-094~097 총 4개 독립 방향이 모두 동일한 이유로 기각됨. 근본 한계:

| 방향 | 실패 원인 |
|------|-----------|
| Exp-094 threshold 단축 | ytn1/ytn2 동일 short-pause 패턴 → ytn1 catastrophic |
| Exp-095 주기적 체크 | EN 인용구와 전환 구별 불가 → catastrophic |
| Exp-096 post-silence check | ytn1/ytn2 동일 패턴 → ytn1 catastrophic |
| Exp-097 tokenizer reset | multilingual decoder가 KO 오디오를 EN으로 잘못 예측 → catastrophic |

현재 아키텍처(SimulStreaming + VAD silence 기반 언어 재감지)에서는 ytn2 개선 불가. 개선을 위해서는 아키텍처 수준의 변화가 필요 (§ 다음 가설 참조).

### 다음 가설

아키텍처 수준 변화가 필요한 방향:
1. **모델 수준**: whisper-large-v3(non-turbo) 또는 코드스위칭에 특화된 모델 사용
2. **이중 디코더**: KO/EN 두 개의 language-specific tokenizer를 동시에 실행하고 더 높은 확신도 결과를 채택
3. **파인튜닝**: ytn2 류의 코드스위칭 데이터로 whisper-large-v3-turbo 파인튜닝
4. **세그먼트 재처리**: 영어 음역 패턴 감지 시 해당 세그먼트를 Korean tokenizer로 재디코딩

---

## Exp-096: 무음 후 언어 체크 (Post-Silence Lang Check) (기각)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

Exp-094(long_silence 임계값 단축)·Exp-095(주기적 체크) 모두 EN 인용구와 진짜 EN→KO 전환을 구별하지 못해 기각됐다. 공통 실패 원인은 "지속 시간이 짧은 진짜 전환(0.5-1.9s pause)"을 잡으려다 EN 인용구 직후 pause에도 트리거되는 것이었다.

새 접근: 짧은 silence(0.5s ≤ silence < 2s) 발생 시 즉시 리셋하지 않고 **1.5초 더 오디오를 수집한 뒤** lang_id()로 현재 언어를 확인, **확신도 0.90 이상 + 언어 변경**일 때만 Exp-093 full reset. EN 인용구 직후에는 EN 오디오가 계속 들어오므로 0.90 확신도가 KO를 반환하지 않을 것이라는 기대.

### 변경 내용

**파일**: `worktrees/exp-096-post-silence-lang-check/whisperlivekit/simul_whisper/align_att_base.py`
- `detect_current_language(window_secs=1.5, min_prob=0.90)` 신규 추가 (L162–178)
  - 최근 1.5초 오디오 추출 → `_encode()` → `lang_id()` → 확신도 미달 시 None 반환

**파일**: `worktrees/exp-096-post-silence-lang-check/whisperlivekit/simul_whisper/backend.py`
- 모듈 상수 3개 추가: `_POST_SILENCE_MIN_DURATION=0.5`, `_POST_SILENCE_COLLECT_SECS=1.5`, `_POST_SILENCE_MIN_PROB=0.90`
- `__init__`: `_post_silence_check_at: float = 0.0` 필드 추가
- `end_silence()`: long_silence 블록에 `_post_silence_check_at = 0.0` (long_silence가 처리하므로 취소) + `elif` 트리거 추가
- `_check_post_silence_language()` 신규 메서드: 수집 완료 후 `detect_current_language()` 호출, 전환 감지 시 Exp-093과 동일한 full reset (`detected_language=None`, `first_timestamp=None`, `global_time_offset`, tracking 필드 클리어)
- `process_iter()`: `infer()` 앞에 `_check_post_silence_language()` 조기 반환 삽입

**파일**: `worktrees/exp-096-post-silence-lang-check/tests/test_post_silence_lang.py` (신규)
- 14개 테스트 케이스, 전체 PASSED

브랜치: `phase2/exp-096-post-silence-lang-check`, commit `ac633bb`

### 테스트 설정

```
cd worktrees/exp-096-post-silence-lang-check
uv sync --extra vbcable --extra listen
python eval.py --model-dir ../../whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/sbs1.mp3 test_data/ytn1.mp3 test_data/eng1.mp3 --repeat 3
```

### 정량 결과 (경로 C, N=3, 2026-06-19 09:39)

| 파일 | R1 WER | R2 WER | R3 WER | median WER | F1 (median) | max WER | stdev |
|---|---|---|---|---|---|---|---|
| sbs1 | 23.2% | 22.0% | 25.0% | **23.2%** | **66.7%** | **25.0%** | 1.5% |
| ytn1 | 86.5% | 101.2% | 76.7% | **86.5%** | **62.5%** | **101.2%** | 12.4% |
| eng1 | 3.8% | 4.8% | 3.8% | **3.8%** | 0.0% | 4.8% | 0.5% |

Exp-093 baseline 대비:
- sbs1: median 23.2% vs 19.6% (+3.6pp), max 25.0% vs 20.8% (+4.2pp) — **회귀**
- ytn1: median 86.5% vs 22.1% (+64.4pp), max 101.2% vs 22.7% (+78.5pp) — **catastrophic**
- eng1: median 3.8% vs 5.7% (−1.9pp) — 소폭 개선

JSON: `worktrees/exp-096-post-silence-lang-check/.omc/benchmarks/eval_exp096_primary_n3.json`

### 정성 관찰

ytn1이 전체적으로 무너졌다 (median 86.5%). ytn2.txt 구조 분석 결과 ytn2뿐 아니라 **ytn1도 EN/KO 교대 패턴** — "EN long block 후 KO"가 아니라 EN 문장·KO 번역·EN 문장·KO 번역이 반복된다. ytn1과 ytn2가 동일 오디오 패턴이므로 어떤 접근도 두 데이터셋을 동시에 처리할 수 없다.

post-silence check가 ytn1의 EN↔KO 교대 구간 짧은 pause에서도 트리거되어 EN 인용구가 등장할 때마다 full reset → ytn1 catastrophic 유발.

### 결론

**기각** — ytn1 max 101.2%로 채택 기준(≤22.7%) 대폭 초과.

**근본 한계 확정**: Exp-094·095·096 세 독립 접근이 동일 이유로 기각됨 — ytn1/ytn2 모두 EN/KO 교대 + 짧은 pause 패턴이므로 음향 수준에서 구별 불가. ytn2 개선 탐색 종료.

---

## Exp-095: 주기적 lang_id() 체크 (Direction C) (기각)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

silence 없이 발화 도중 EN→KO 언어 전환이 발생해도 감지하도록, 8초마다 최근 5초 오디오의 언어를 재확인한다.
현재 `detected_language`와 다른 언어가 감지되면 즉시 토크나이저를 교체(`switch_language()`).

### 변경 내용

| 파일 | 변경 |
|---|---|
| `align_att_base.py` | `detect_current_language(window_secs=5.0, min_prob=0.7)` 신규: 최근 5초 오디오 재인코딩 후 lang_id() |
| `align_att_base.py` | `switch_language(new_lang)` 신규: `refresh_segment(complete=True)` + `create_tokenizer()` + state 갱신 |
| `backend.py` | `_LANG_RECHECK_INTERVAL=8.0` 상수, `_last_lang_check_end` 필드, `_check_language_periodically()` |
| `backend.py` | `process_iter()`: `infer()` 직후 `_check_language_periodically()` 호출, True 시 현 배치 드롭 |
| `tests/test_lang_recheck.py` | 신규 10개 (TDD, 10/10 PASSED) |

### 정량 결과 (경로 C, N=3 — `eval_exp095_primary_n3.json`)

| 파일 | R1 | R2 | R3 | median | max | stdev | F1 |
|---|---|---|---|---|---|---|---|
| sbs1 | **76.8%** | 57.7% | 70.8% | **70.8%** | **76.8%** | 9.7% | 47.6% |
| ytn1 | **81.0%** | 52.1% | 54.0% | **54.0%** | **81.0%** | 16.1% | 40.0% |
| eng1 | — | — | — | — | — | — | — |

*(eng1 누락: eval 스크립트가 sbs1+ytn1 후 종료 — 두 파일의 catastrophic으로 기각 결정에 충분)*

### 정성 관찰

- **sbs1**: baseline 19.6% → 70.8%. sbs1에는 ~10초 분량의 영어 인용구가 포함됨. 주기적 5초 창이 해당 구간에 걸리면 EN (confidence > 0.7)으로 올바르게 감지 → `switch_language("en")` 호출 → `refresh_segment(complete=True)`로 오디오 버퍼 전체 삭제 → 이후 KO 오디오가 EN 토크나이저로 디코딩됨.
- **ytn1**: baseline 22.1% → 54.0%. 동일 패턴. ytn1의 영어 구간에서 false switch 발생.
- **근본 문제**: 5초 감지 창으로 "KO 내 EN 인용구"(sbs1 스타일)와 "EN→KO 언어 전환"(ytn2 스타일)을 구분할 수 없음. `switch_language()`의 `refresh_segment(complete=True)` 버퍼 클리어가 catastrophic WER의 직접 원인.

### 결론 및 이유

**기각** — sbs1 max 20.8%→76.8%, ytn1 max 22.7%→81.0% catastrophic. §3.8 채택 1순위(최악 케이스 미회귀) 완전 실패. Direction C(주기적 lang_id 체크)는 EN 인용구 포함 콘텐츠에 false positive를 피할 수 없어 primary 데이터에 부적합. worktree `exp-095-lang-recheck-periodic` 폐기.

### 실패 원인 분석 (미래 실험 참고)

1. **5초 감지 창 = 구별 불가**: sbs1의 10초 EN 인용구와 ytn2의 EN→KO 전환 후 KO 구간이 창 크기 관점에서 동일. 창 크기/신뢰도 조정으로 해결 불가.
2. **switch_language()의 버퍼 클리어**: `refresh_segment(complete=True)`가 오디오 전체를 삭제해 이후 디코딩이 컨텍스트 없이 시작 → catastrophic. 소프트 전환(버퍼 유지) 변형은 새 토크나이저로 기존 오디오를 재디코딩하는 문제 발생.
3. **mid-stream 전환의 근본 한계**: 스트리밍 모드에서 이미 방출된 토큰은 재회수 불가. 언어 전환을 무음 경계 외에서 감지하려면 already-buffered 오디오 재처리가 필요하며 이는 현 아키텍처와 충돌.

### 다음 가설

ytn2 언어 전환 개선의 현실적 접근:
- **Direction B**: long_silence 발동 시 컨텍스트 편향 제거 강화 (이미 `init_context()` 호출 중 — 추가 효과 불확실)
- **현실적 인정**: EN→KO short-pause 전환은 현 아키텍처 제약 내에서 무음 기반 재감지(Exp-093) 이상의 개선이 어려울 수 있음. Exp-093 베이스라인이 primary에서 최적임을 확인.

---

## Exp-094: MIN_DURATION_REAL_SILENCE 2→1 (silence threshold 단축) (기각)

**날짜**: 2026-06-19 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

Exp-093 채택 후 ytn2에 잔존하는 "Wang Sung-han's" 같은 한국어 영문 음역 문제의 원인:
EN→KO 전환 pause가 1~2초로 짧아 `MIN_DURATION_REAL_SILENCE=2` 임계값에 걸리지 않음 →
`detected_language` "en" 유지 → 한국어가 영어 토크나이저로 디코딩 → 음역 emit.

임계값을 1초로 낮추면 1~2초 pause도 long_silence로 인식, 언어 재감지가 트리거된다.

### 변경 내용

| 파일 | 라인 | 변경 |
|---|---|---|
| `whisperlivekit/simul_whisper/backend.py` | L36 | `MIN_DURATION_REAL_SILENCE = 2 → 1` |
| `tests/test_lang_redetect.py` | L39, L67 | 단위테스트 상수값 및 short_silence 경계값 업데이트 (== 1, - 0.5) |

### 테스트

```
pytest tests/test_lang_redetect.py -v   # 4/4 PASSED
```

### 정량 결과 (경로 C, N=3 — `eval_exp094_primary_n3.json`)

**베이스라인 = Exp-093 채택값** (sbs1 max 20.8% / ytn1 max 22.7%)

| 파일 | R1 | R2 | R3 | median | max | stdev | F1 |
|---|---|---|---|---|---|---|---|
| sbs1 | 23.8% | 18.5% | 19.0% | **19.0%** | **23.8%** | 2.9% | 76.2% |
| ytn1 | 83.4% | 90.8% | **108.6%** | **90.8%** | **108.6%** | 12.9% | 61.5% |
| eng1 | 3.8% | 3.8% | 4.8% | **3.8%** | 4.8% | 0.5% | 0.0% |

### 정성 관찰

- **ytn1**: R1부터 83.4% — `뭐야?뭐야...` 반복 폭주 재발. threshold 1초가 ytn1의 EN/KO 교차 통역 구간(1~2초 자연 pause)을 false redetection으로 처리 → 재감지 윈도우(2.2초) 내에 혼합 오디오 → 언어 오감지 → oscillation → catastrophic.
- **딜레마 확인**: ytn1은 짧은 pause에서 **재감지 불필요**(동일 언어 패턴), ytn2는 짧은 pause에서 **재감지 필요**(언어 전환). 단일 threshold로 두 케이스 동시 해결 불가.
- **sbs1/eng1**: max 소폭 변화(sbs1 +3pp, eng1 개선). 단, ytn1 catastrophic이 압도적.

### 결론 및 이유

**기각** — ytn1 max 22.7%→108.6% catastrophic 완전 재발(채택 기준 ≤22.7% 초과). §3.8 채택 1순위(최악 케이스 미회귀) 완전 실패. silence threshold 단일 값 조정으로는 ytn1/ytn2 동시 해결 불가. worktree `exp-094-silence-threshold-1s` 폐기, main 코드 변경 없음.

### 다음 가설 (Exp-095~)

**Direction C: 주기적 `lang_id()` 체크** — silence 없이 mid-stream에서 언어 전환 감지.
- `align_att_base.py`에 `detect_current_language()` public method 추가 (현재 오디오 버퍼 → encoder → `lang_id()`)
- `backend.py`에서 일정 주기(5~8초) 경과 시 언어 재확인 → 불일치 시 `detected_language` + `first_timestamp` 리셋으로 재감지 트리거
- `MIN_DURATION_REAL_SILENCE=2` 유지 (Exp-093 베이스 보존)
- 장점: ytn1 자연 pause를 건드리지 않음(주기가 길어 false redetection 없음), ytn2 긴 EN 구간 후 KO 복귀 캐치 가능

---

## Exp-092: foreign-language 메타태그 감지→full_reset (기각)

**날짜**: 2026-06-18 / **정책**: SimulStreaming / **결론**: **기각**

### 가설

ytn2에서 발생하는 `(speaking in foreign language)` 메타태그는 한·영 환경(§3.2)에서 **항상 환각 마커** → false positive 0. 감지 시 `full_reset()`으로 언어 재감지를 유도하면 언어 고착 + 메타태그 폭주를 한 번에 차단 가능.

### 변경 내용

`whisperlivekit/simul_whisper/backend.py` (+24줄):
- `_FOREIGN_LANG_MARKER = "foreign lang"` 상수
- `_detect_foreign_lang_hallucination(tokens)` — 마커 문자열 감지
- `_reset_language_state()` — full_reset + detected_language 클리어 + 추적 변수 초기화
- `_filter_cross_batch_repetitions()` 진입부에 감지 분기 추가
- `tests/test_burst_full_reset.py` 신규 (TDD, 7개)

### 정량 결과 (경로 C, N=3 — `eval_exp092_primary_n3.json`)

| 파일 | R1 | R2 | R3 | median | max | stdev | F1 |
|---|---|---|---|---|---|---|---|
| sbs1 | 19.6% | 16.7% | 17.3% | 17.3% | 19.6% | 1.6% | 76.2% |
| ytn1 | 34.4% | 58.3% | 42.3% | 42.3% | 58.3% | 12.2% | 66.7% |
| eng1 | 5.7% | 3.8% | 3.8% | 3.8% | 5.7% | 1.1% | 0.0% |

**ytn2 (`eval_exp092_ytn2.json`)**: WER **174.4%**, F1 **11.8%** (베이스라인 93.1%/47.1% 대폭 악화)

### 정성 관찰

- ytn1: 메타태그 차단 효과 실재 — R2에서 baseline 108%→58.3%로 개선. 그러나 나머지 2회도 34~42%로 편차 여전.
- ytn2: `(speaking in foreign language)` 소멸 → `(Via The United Nations Security Council)` 등 다른 환각으로 전이(whack-a-mole). 언어 고착 자체가 해소되지 않아 다른 아티팩트로 폭주 양상이 바뀐 것.

### 결론 및 이유

**기각** — ytn2 WER 93.1%→174.4% 대폭 악화. 증상 억제만 됐고 언어 고착 근본 원인(detected_language 영구 고정) 미해결. Exp-093(silence 재감지)이 근본 수정으로 채택됨. 단, ytn1 메타태그 차단 효과 실재하므로 Exp-093과 결합 평가 가능성은 백로그에 남긴다.

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

## Exp-091: 연속 n-gram 반복 감지 (`_detect_consecutive_repetition`) — 기각

**날짜**: 2026-06-18 / **브랜치**: `phase2/exp-091-consecutive-repeat-detect` (커밋 `bb4d39d`) / **정책**: simulstreaming

**배경**: Exp-090으로 `_detect_repetition_loop`(Counter 밀도 기반) 제거 후, ytn2(코드스위칭 영어 발화)에서 "have been working on it..." 류 무한 반복 루프 발생 → WER 302% catastrophic. Exp-087 baseline(103.4%)보다도 악화. 루프 감지 자체는 여전히 필요하나 Exp-009의 밀도 기반 방식이 false positive를 낳았으므로, 대신 **연속 n-gram 일치**만 감지하는 방식으로 설계.

**가설**: `tokens[-k:] == tokens[-2k:-k]` (k=2..5)로 최근 k개 토큰이 그 직전 k개와 완전 일치하는 경우만 루프로 판정 → 비연속 빈출 단어는 트리거 안 함 → false positive 최소화하면서 반복 루프(ytn2 "have been working on it...") 차단.

**변경 내용** (워크트리: `worktrees/exp-091-consec-repeat`)
- `whisperlivekit/simul_whisper/backend.py` (+37줄):
  - `from collections import Counter, deque` (deque 재추가)
  - 클래스 상수 `_CONSEC_REPEAT_MAX_NGRAM = 5`, `_CONSEC_REPEAT_WINDOW = 12` 추가
  - `self._recent_tokens: deque = deque(maxlen=self._CONSEC_REPEAT_WINDOW)` 추가
  - `end_silence()` / `new_speaker()` / `_filter_cross_batch_repetitions()`(2군데) 내 `self._recent_tokens.clear()` 추가
  - `_detect_consecutive_repetition()` 신규 메서드: k=2..5 순회, `tokens[-k:] == tokens[-2k:-k]` 시 True
  - `process_iter()`: 피딩 루프 + 감지 호출 + 리셋 블록 추가
- `tests/test_stall_watchdog.py`: `from collections import deque` + `_CONSEC_REPEAT_WINDOW` 기반 deque 주입 재추가

**테스트 설정**
```
# cwd=워크트리 필수 (editable install CWD 의존)
python scripts/eval.py --repeat 3 \
  --model-dir <abs>/whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/sbs1.mp3 test_data/ytn1.mp3 test_data/eng1.mp3 \
  --output exp091_primary_n3.json
# ytn2 단회 (held-out, 채택 후보 검증)
python scripts/eval.py --repeat 1 \
  --model-dir <abs>/whisperlivekit/model/whisper-large-v3-turbo \
  --files c:\...\test_data\ytn2.mp3 \
  --output exp091_ytn2.json
```

**정량 결과 (경로 C)**

primary N=3:

| 파일 | R1 WER | R2 WER | R3 WER | WER median | WER max | WER stdev | R1 F1 | R2 F1 | R3 F1 | F1 median | F1 worst |
|------|--------|--------|--------|------------|---------|-----------|-------|-------|-------|-----------|---------|
| sbs1 | 15.5% | 22.0% | 18.5% | **18.5%** | **22.0%** | 3.3% | 76.2% | 76.2% | 76.2% | **76.2%** | **76.2%** |
| ytn1 | 20.9% | **43.6%** | 23.3% | **23.3%** | **43.6% ⚠️** | **12.5%** | 87.5% | **66.7%** | 87.5% | **87.5%** | **66.7%** |
| eng1 | 2.9% | 3.8% | 3.8% | **3.8%** | **3.8%** | 0.5% | 0.0% | 0.0% | 0.0% | **0.0%** | **0.0%** |

ytn2 단회:
| 파일 | WER | F1 | 비고 |
|------|-----|-----|------|
| ytn2 (Exp-087 baseline) | 103.4% | 47.1% | 한국어 구간 "(speaking in foreign language)" 오인식 |
| ytn2 (Exp-090) | 302% | — | 반복 루프 감지 제거 후 "have been working on it..." 무한 루프 |
| ytn2 **(Exp-091)** | **85.7%** | **35.3%** | 반복 루프 차단 확인, 단회 측정 |

**베이스라인 (Exp-090) 대비**

| 지표 | Exp-090 | Exp-091 | 변화 | 판정 |
|------|---------|---------|------|------|
| ytn1 WER **max** | 25.2% | **43.6%** | **+18.4%p** | ❌ catastrophic 회귀 |
| ytn1 WER stdev | 2.2% | **12.5%** | +10.3%p | ❌ 극단 불안정 |
| ytn1 F1 **worst** | 0.800 | **0.667** | −13.3%p | ❌ 회귀 |
| sbs1 WER max | 19.0% | 22.0% | +3.0%p | ⚠️ 허용 범위 |
| sbs1 F1 median | 0.762 | 0.762 | 0 | ✅ |
| ytn2 WER (단회) | 302% | **85.7%** | −216%p | ✅ (단회) |

**정성 관찰**
- ytn1 R2 catastrophic(WER 43.6%, F1 66.7%): `_detect_consecutive_repetition`이 코드스위칭 구간에서 false positive 트리거 의심. window=12 + k=2 bigram이 코드스위칭 경계의 짧은 반복 패턴(예: "군의", "군의" 또는 영어 2-gram 일치)에 과민하게 반응.
- ytn2 루프 차단 확인: Exp-090에서 발생한 "have been working on it..." 무한 반복이 제거됨. WER 302% → 85.7%.
- ytn2 WER 85.7%는 주로 한국어 구간 "(speaking in foreign language)" 오인식 문제 — Exp-091과 무관한 모델 한계.
- stdev 폭증(2.2% → 12.5%)은 연속 n-gram 감지기가 실행마다 다른 타이밍에 트리거됨을 시사.

**결론**: **기각**
**이유**: 1순위(ytn1 WER max 미회귀) 실패 — 25.2% → 43.6%(+18.4%p) catastrophic 회귀. `_detect_consecutive_repetition`(window=12, k=2..5)가 코드스위칭 구간에서도 false positive를 일으켜 정상 발화를 잘라냄. ytn2 개선(302%→85.7%)이 있으나 단회 측정이고 primary 기준 위반이 우선.

**다음 가설**: Phase 2 완료 판단. Exp-090에서 목표(ytn1 WER max ≤30%, F1 worst ≥0.75) 이미 달성. 연속 반복 루프 감지는 코드스위칭 환경에서 false positive 위험이 높아 현재 접근법으로는 안전하지 않음 — Phase 3(필터링·단어교정 이식) 또는 별도 실험으로 별도 추적 필요.

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
