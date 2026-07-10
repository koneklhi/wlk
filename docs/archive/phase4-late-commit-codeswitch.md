# Phase 4 근본 개선 — 늦은 확정(late-commit) + 수정 가능한 꼬리로 코드스위칭 강건성 회복

> **작성 2026-06-26.** 지금까지의 개선(Exp-131~136: PLC·beam·CRT·lang-set 마스킹)은 전부
> **즉시-확정 구조를 그대로 둔 채 파라미터만** 건드려 worst-case 회귀로 기각됐다.
> 이 문서는 **확정(commit) 구조 자체**를 바꾸는 근본 방향을 정의한다.
> 전제: **실시간 지연이 늦어도 된다 — 정확도를 매우 높게 올리는 것이 목표**(사용자 명시, 2026-06-26).

---

## 1. 진짜 이유 — WL vs WLK 차이는 파라미터가 아니라 확정 구조

`whisperlive`(WL)가 코드스위칭에 강했던 이유를 코드 단위로 분석([LOCALAGREEMENT_ANALYSIS_tmp.txt](../../../LOCALAGREEMENT_ANALYSIS_tmp.txt))한 결과,
차이는 **"언제 확정하는가"**다.

| 축 | WL (느리지만 강건) | WLK 현재 (빠르지만 취약) |
|---|---|---|
| **확정 시점** | 같은 출력 **10회 반복** 후 확정 | AlignAtt: 매 infer 마지막 단어만 빼고 **즉시 확정**, fire 시 전부 |
| **미확정 꼬리** | ~50초까지 **수정 가능** | 사실상 **즉시 잠김** |
| **재디코딩 컨텍스트** | 매 스텝 확정지점~끝 **전체(45초) 재디코딩** | segment 누적(`audio_max_len=30`) **forward-only**, 재디코딩 없음 |
| **언어 감지** | **매 스텝 재감지** (토크나이저 중간 전환) | 2.0초 후 **고정** (PLC 옵션, 기본 비활성) |
| **환각 폭주** | 10회 불일치 시 꼬리 **드롭 → 자동 차단** | 확정 후 고정 → **bong1 웃음 환각이 그대로 박힘** |

WLK는 SimulStreaming(AlignAtt)을 **저지연** 때문에 채택(Exp-001)했고, 그 대가로 WL의 세 가지 강건성
장치(늦은 확정 / 수정 가능한 긴 꼬리 / 매 스텝 언어 재감지)를 전부 잃었다.

### 코드 위치

- 확정 정책: `whisperlivekit/simul_whisper/align_att_base.py` `_split_tokens` (fire/is_last 시 전부, 평시 마지막 단어만 hold)
- 온라인 프로세서: `whisperlivekit/simul_whisper/backend.py` `SimulStreamingOnlineProcessor`
- 늦은 확정 노브: `whisperlivekit/parse_args.py` `frame_threshold`(기본 25), `audio_max_len`(기본 30.0)
- 언어 재감지: `align_att_base.py` `_detect_language_if_needed`(2.0초 후 고정), `_maybe_periodic_lang_check`(PLC, 기본 None)
- WL 스타일 full-buffer 재디코딩 경로(현재 비활성): `whisperlivekit/local_agreement/online_asr.py` `OnlineASRProcessor`

---

## 2. 왜 지금까지의 수정이 전부 마이너했나 — 핵심 통찰

Exp-131~136은 즉시-확정 구조를 건드리지 않고 파라미터만 조정 → 전부 worst-case 회귀로 기각.

**결정적 통찰**: PLC(언어 재감지)를 **단독**으로 켜면(Exp-131/133) **이미 확정된 텍스트를 되돌릴 수 없어**
bong1이 회귀한다. 언어 재감지는 **"늦은 확정 + 수정 가능한 꼬리"와 반드시 짝지어야** 효과가 난다.
이 결합은 **한 번도 시도된 적 없다**(실험 이력 확인: 컨텍스트 확대·확정 지연 방향 = 미시도.
Exp-135 provisional buffer는 1-step뿐이라 너무 얕았고, Exp-126 컨텍스트 완전 제거는 전사 붕괴 → 컨텍스트 필수 확인).

**worst-case 우선 원칙(CLAUDE.md §4)과의 정합**: WL의 "10회 불일치 시 드롭"이 바로 환각 폭주 차단 장치다.
최근 기각들의 주범인 **bong1 웃음-환각 catastrophic run을 구조적으로 막는다** → 이 방향은 median이 아니라
**worst-case를 직접 겨냥**한다.

---

## 3. 목표 수치 (경로 C, 채택 확정 N≥3, 최악 케이스 미회귀 1순위)

현재 베이스라인(Exp-130 기준, N=5, diar-ON, CRT=3.0, beams=2):

| 파일 | WER median | WER max | F1 median | 비고 |
|---|---|---|---|---|
| bong1 | 44.1% | **55.0%** | 48.5% | 다화자·웃음 환각 = 최악 케이스 원천 |
| ytn2 | 44.3% | **61.6%** | 55.6% | 짧은 텀 코드스위칭 = 1순위 |
| sbs1 | 24.4% | 32.7% | 36.4% | 단일화자 회귀 감시 |
| ytn1 (held-out) | 29.4% | 49.1% | 70.6% | ytn2 쌍둥이, 코드스위칭 일반화 |
| eng1 (held-out) | 3.8% | 5.7% | — | 영어 회귀 감시 |

**이번 플랜의 1차 성공 기준**:
- **bong1 max < 50%** (웃음 환각 catastrophic run 제거 — worst-case 1순위)
- **ytn2 median < 35%** (코드스위칭 전환 누락 감소)
- sbs1 / eng1 미회귀 (median·max 모두 ≤ +5%p)

---

## 4. 핵심 제약 (반드시 준수)

1. **폐쇄망 오프라인**: 런타임 네트워크 호출 금지 (CLAUDE.md §3.1).
2. **외과적 변경**: `whisperlivekit/` 본체 수정 최소화, 가능하면 새 모듈로 분리 (CLAUDE.md §1).
3. **데이터 특화 하드코딩 금지**: 개선은 일반화돼야 함. 특정 단어·구절 암기 금지 (CLAUDE.md §3.8).
4. **측정 기준**: 경로 C(VBCable)만. 화자분할 ON(Sortformer). **① 스크리닝 = `--repeat 1`** (평소), **② 채택 확정 = `--repeat 3`** (머지 직전, CLAUDE.md §4).
5. **채택 우선순위**: 1순위 = 최악 케이스(max) 미회귀, 2순위 = median 개선.
6. **main 코드 편집 금지**: 구현은 feature 브랜치 + 워크트리(subagent)에서. main 세션은 검토·디스패치.

---

## 5. 단계별 플랜 — 싼 검증 → 구조적 재설계

세 레버를 전부 켜는 것이 목표(늦은 확정 / 수정 가능한 꼬리 / 매 스텝 언어 재감지).
각 단계는 독립적으로 측정·채택/기각하며, 앞 단계 결과로 뒤 단계 방향을 조정한다.

### Stage 1 — `frame_threshold` 상향 (SimulStreaming 네이티브 "늦은 확정", 미시도)

- **가설**: AlignAtt가 각 토큰을 확정하기 전 기다리는 미래 프레임 수(`frame_threshold`)를 키우면,
  코드스위칭 전환 구간에서 잘못된 조기 확정이 줄어든다. 지연↑·정확도↑의 가장 직접적 교환.
- **변경**: `frame_threshold` 25 → 50 → 100 스윕 (CLI 플래그, **코드 변경 없음**).
  최적값을 찾은 뒤 **PLC(`periodic_lang_check` 2.0/4.0)와 결합** — 언어 재감지가 늦은 확정과
  짝지어졌을 때 비로소 효과를 내는지 검증(§2 통찰의 1차 확인).
- **측정**: 테스트 3파일 N≥3 + held-out.
- **채택 게이트**: ytn2 median 개선 AND bong1/sbs1 max 미회귀(≤ +5%p).
- **분기**: 개선 확인 → Stage 2로 구조화. 효과 없음 → "즉시 확정이 근본 원인" 가설 재검토,
  Stage 2/3 우선순위 재조정.
- **비용**: 가장 쌈. 코드 거의 안 건드리고 핵심 가설을 1~2 실험으로 판정.

### Stage 2 — 다단계 수정 버퍼 (WL 10회 stabilization을 라이브 경로에 이식)

- **가설**: WL의 "10회 stabilization 후 확정 / 불일치 시 드롭"이 ① 코드스위칭 꼬리 수정 ② 환각 폭주
  차단을 동시에 달성한다. Exp-135의 1-step provisional은 너무 얕아 효과가 없었다 → **N-step + 경계 확정**으로 확장.
- **변경** (외과적, 새 모듈 우선): `align_att_base.py` `_split_tokens` 커밋 경로 +
  `backend.py` `SimulStreamingOnlineProcessor`에 **provisional 큐** 추가.
  최근 K단어를 확정하지 않고 보류 → 후속 infer가 다시 쓸 수 있게 하고,
  **N회 생존 OR VAD silence / 세그먼트 / 언어 전환 경계**에서만 최종 확정.
  신규 플래그 `--commit-stable-iters N`, `--provisional-window K`.
- **측정**: 동일.
- **채택 게이트**: **bong1 max 개선(웃음 환각 catastrophic 제거)이 1순위 신호.**
  ytn2 median 개선 동반, sbs1/eng1 미회귀.
- **리스크**: 확정 지연 증가(허용). 지연 체감은 경로 B 정성으로 별도 확인 가능.

### Stage 3 — 2-pass 아키텍처 (가장 근본, "지연 OK"를 정면 활용)

- **가설**: WL의 full formula(full-buffer 재디코딩 + `language=auto` 매 스텝 + 긴 버퍼)를
  명시적 2-pass로 재현하면 최고 정확도. 라이브 디스플레이는 빠르고, 확정 텍스트는 느리지만 정확.
- **변경** (대규모): `audio_processor.py` 이벤트 루프에 **second pass** 추가.
  - 라이브 디스플레이(미확정) = 현재 SimulStreaming 유지(즉각 피드백).
  - **확정/번역 트리거용 텍스트 = 별도의 느린 full-context 재디코딩**
    (`local_agreement/online_asr.py` `OnlineASRProcessor`, `language=auto`,
    `buffer_trimming_sec` 30~45 상향). WER·번역은 이 느린 패스에서만 산출.
  - §3.4 번역 트리거(문장 확정 시점)와 자연 연결.
- **측정/게이트**: 동일.
- **차별점**: Exp-001에서 LocalAgreement가 "영어 코드스위칭 통째 누락"으로 기각됐으나,
  분석상 그건 **eager 1-gram 확정 + 고정 언어**로 돌렸기 때문일 가능성이 크다.
  WL의 **full formula(N회 stabilization + 매 스텝 언어 재감지 + 긴 버퍼)는 미시도** — Stage 3가 그 풀셋을 정면 재검증한다.

---

## 6. 측정 프로토콜 (CLAUDE.md §4 — 2계층)

```powershell
# ① 스크리닝(기본) — bong1 + ytn2 + sbs1, 화자분할 ON, 방향 탐색용
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"
# ↑ --repeat 생략 = 1회, 방향 신호로만 해석

# ② 채택 확정(머지 직전에만) — N≥3회, median+분산 판단
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3 `
  --output ".omc/benchmarks/eval_$ts.json"

# held-out(채택 후보에 한해, 단회) — ytn1 + eng1
# (② 명령과 동일 + --files test_data/ytn1.mp3 test_data/eng1.mp3, --repeat 제거)
```

- **채택 확정 시 fail-fast 금지**: 첫 회차가 나빠도 N회 전부 측정(분산이 곧 데이터, ② 단계 한정). 단 VBCable 미설정·무음 캡처 등
  *하니스 버그*는 즉시 중단·수정.
- 각 실험은 `--output` JSON 저장 → `/log-experiment`에서 `files[].transcription`/`reference`로
  **`### 분석`(전사 내용 정성 대조)** 섹션까지 작성.

---

## 7. 채택/기각 규칙

**채택 조건** (모두 충족):
1. 최악 케이스(max) 미회귀 — median이 좋아도 catastrophic run이 늘면 기각 (1순위).
2. ytn2 또는 bong1 median 개선 (코드스위칭·다화자 = 공동 최우선).
3. sbs1 / eng1(영어 회귀) median·max 모두 ≤ +5%p.
4. held-out(ytn1·eng1) 미회귀 — 일반화 검증.
5. `pytest tests/` 전부 통과.

**즉시 기각**:
- 어느 한 언어(한/영) 커버리지가 의미 있게 하락.
- bong1 웃음 환각 catastrophic run이 오히려 증가.

**목표 필수 기능 예외 (자율 기각 금지 → 사용자 질의)**: 위 채택 조건 1~5 정량 게이트 미달이라도, §3.1 폐쇄망·§3.2 한/영 두 언어 고정 달성에 필요한 기반 기능이면 자율 기각하지 않는다. ⓐ목표·제약 근거 ⓑ회귀 위치 ⓒ대안 구현 여지를 함께 보고하고 **사용자에게 채택 여부를 묻는다**. 특히 한/영 출력 고정(§3.2) 관련 기능이 bong1 worst-case에서 회귀하더라도(ytn2↔bong1 구조적 트레이드오프) 목표 필수 여부를 먼저 판단한다 (계기: Exp-136 자율 기각 → Exp-138 일·중 환각 재발).

---

## 8. 실험 기록 규칙

1. 각 단계 측정 완료 후 `EXPERIMENTS.md`에 Exp-N 추가(Exp-137부터), `/log-experiment`로 작성.
2. **`### 분석` 섹션 필수** — eval JSON 전사 텍스트 직접 대조(비언어 토큰·환각 폭주·코드스위칭 실패·화자 혼동).
3. 채택 실험은 커밋 후 다음 단계 베이스라인. 기각도 기록(같은 실수 반복 방지).
4. **major 방향 전환**(Stage 변경, 루프 종료)은 사용자 보고 후 진행(CLAUDE.md §4).

---

## 9. 주요 파일 색인

| 역할 | 경로 |
|---|---|
| AlignAtt 확정 정책 | `whisperlivekit/simul_whisper/align_att_base.py` (`_split_tokens`, `_detect_language_if_needed`) |
| SimulStreaming 온라인 프로세서 | `whisperlivekit/simul_whisper/backend.py` |
| 늦은 확정·버퍼 노브 | `whisperlivekit/parse_args.py` (`frame_threshold`, `audio_max_len`, `periodic_lang_check`) |
| WL 스타일 full-buffer 재디코딩(Stage 3) | `whisperlivekit/local_agreement/online_asr.py` (`OnlineASRProcessor`) |
| 이벤트 루프(Stage 3 2-pass) | `whisperlivekit/audio_processor.py` |
| 평가 스크립트 | `scripts/eval.py` |
| WL 메커니즘 분석 | `LOCALAGREEMENT_ANALYSIS_tmp.txt` |
| 실험 로그 | `EXPERIMENTS.md` (활성; Exp-001~130 `PHASE2_EXPERIMENTS.md`) |
| 설계 제약 | `CLAUDE.md` |

---

## 10. 루프 진행 방식

```
Stage 1 (frame_threshold) → 측정 → 가설 확인?
  ├─ 예 → Stage 2 (수정 버퍼) → 측정 → bong1 max 개선?
  │         ├─ 예 → 채택, Stage 3로 정확도 추가 확보 여부 판단
  │         └─ 아니오 → 원인 분석 후 Stage 3 직행
  └─ 아니오 → "즉시 확정이 근본 원인" 가설 재검토 → 사용자 보고
```

**다음 행동**: 사용자 합의 시 Stage 1부터 feature 브랜치 + 워크트리에서 착수.
