# Goal Prompt — WER 15% 미만 자율 달성 루프

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> Claude는 이 지시를 받으면 WER 15% 달성까지 자율 루프를 실행한다.
> 사용자 추가 입력 없이 진행하되, **목표 달성·방향 소진·major 방향 전환** 시에만 보고한다.

---

## 목표

**테스트 3파일(bong1 + ytn2 + sbs1) 경로 C 측정 평균 WER < 15%** 달성.

> ⚠️ **base 기질·무효 (2026-07-05)**: 아래 baseline은 `model_dir` 배선 버그로 base(74M) 위에서 측정된 것(Exp-158 확인) — **수치 전부 무효**. turbo 기질(E5) 1차 baseline은 [EXPERIMENTS.md](../EXPERIMENTS.md)의 "현재 베이스라인" 참조(bong1 28.1%/ytn2 41.9%/sbs1 16.1%, held-out 미측정, 평균 28.7%). 게이트 max 임계값(§채택/기각 기준)도 재산정 필요.

현재 master baseline (E2, Exp-142 채택 후 — 2026-07-01, **base 기질·무효**):
| 파일 | WER median | WER max | 특성 |
|------|-----------|---------|------|
| bong1 | **37.5%** | 48.0% | 영어2+한국어2 다화자, 웃음/박수 비음성 구간 |
| ytn2  | **31.5%** | 36.0% | 한↔영 짧은 텀 코드스위칭 (순차통역) |
| sbs1  | **19.6%** | 22.6% | 한국어 중심, 중간 영어 인용 |
| **평균** | **29.5%** | — | **목표까지 -14.5pp 필요** |

---

## 루프 정의

```
LOOP (avg_wer > 15%가 유지되는 한):

  ① ANALYZE  — 현재 eval JSON에서 어떤 파일이 높은가?
               전사 텍스트를 직접 읽어 구체적 실패 패턴 확인.

  ② DIAGNOSE — 실패 패턴 → 근본 원인 가설 수립.
               "이 오류를 다른 방식으로 접근하면 어떻게 되는가?" 먼저 브레인스토밍.

  ③ DESIGN   — 가설 구현 방법 설계 (접근법 다양성 우선).
               기존에 시도한 방법이면 왜 실패했는지 재분석 후 다른 각도로.

  ④ IMPLEMENT & SCREEN — 워크트리에서 구현 → N=1 스크리닝.
               catastrophic → 즉시 기각. 개선 신호 → N=3 확정.

  ⑤ DECIDE   — 채택/기각 결정 → /log-experiment 기록 → baseline 업데이트.

  ⑥ CHECK    — avg_wer < 15%? → DONE. else → LOOP.
```

---

## 세션 시작 즉시

### 1. 상태 파악

```powershell
# EXPERIMENTS.md(STATE) 읽기 — 항상 먼저
# 현재 baseline, epoch, 채택 이력 확인
git worktree list   # 미완료 워크트리 확인
```

**미완료 작업**: 없음(PLC wiring은 Exp-143에서 이미 해결). **현재 1순위는 turbo baseline held-out(ytn1/eng1) 측정 + ytn2 회귀 재조사** — [EXPERIMENTS.md](../EXPERIMENTS.md) Exp-158·"다음 가설" 참조.

### 2. 전사 텍스트 분석

```powershell
# 가장 최근 eval JSON 경로 확인
Get-ChildItem "$root\.omc\benchmarks\eval_*.json" | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Select-Object FullName
# files[].transcription / files[].reference 필드를 직접 읽어 패턴 파악
```

---

## 실패 모드 진단 가이드

eval JSON의 `transcription`과 `reference`를 대조해 어떤 종류의 오류인지 먼저 파악한다.
**수치보다 오류 유형이 먼저다 — 오류 유형이 달라지면 접근법도 달라진다.**

| 관찰된 패턴 | 의심 원인 | → 해결 방향 힌트 |
|-----------|---------|----------------|
| 웃음·박수·기침 구간에서 엉뚱한 텍스트 | 비음성 구간을 발화로 오감지 | 비음성 구간 감지 강화 |
| 같은 단어·구가 반복 출력 | 컨텍스트 고착, 환각 체인 | 컨텍스트 리셋, 반복 억제 |
| 영어→한국어(또는 역) 전환 시 단어 유실 | 언어 전환 시점 인식 지연 | 언어 전환 탐지 개선 |
| 언어가 잘못 고착 (영어 구간을 한국어로 전사) | 초기 언어 감지 실패 후 유지 | 언어 재감지 주기·임계치 조정 |
| 짧은 발화 후 엉뚱한 삽입 | 세그먼트 경계 오인식 | 세그먼트 확정 타이밍 개선 |
| 문장이 중간에 잘리거나 너무 일찍 확정 | 조기 확정 | 확정 신호 임계치 조정 |
| 특정 단어가 일관되게 오인식 | 모델 어휘 한계 | 컨텍스트 프롬프트 / hotwords |
| 정상 구간인데도 WER 높음 | 발음·억양 차이, 모델 한계 | 디코딩 파라미터 탐색 |

---

## 탐색 공간 — 문제별 다양한 접근법

이 목록은 **제약 없는 아이디어 공간**이다. 한 가지 접근에 막히면 다른 각도로 시도한다.
기존에 기각된 방법도 **다른 구현 방식**이라면 재시도 가능하다 (원인 분석 후).

---

### 🔴 문제 1: 비음성 구간 환각 (bong1 worst-case 근본 원인)

웃음·박수 구간에서 Whisper가 무의미한 텍스트를 생성. E2에서 CJK를 막아도 라틴/한글 쓰레기로 형태만 바뀜.

**접근법 A — 비음성 구간 자체를 배제**
- A1. `no_speech_prob` + `avg_logprob` 복합 조건으로 세그먼트 드롭 (후처리)
  - 구현 위치: `whisperlivekit/filtering/__init__.py`
  - 조건 예: `no_speech_prob > 0.7 AND avg_logprob < -1.5`
- A2. Silero VAD 파라미터 강화 (`min_silence_duration_ms` 단축, `threshold` 상향)
  - 비음성 구간을 VAD 단에서 배제 → Whisper에 아예 전달 안 됨
  - 구현 위치: `backend.py` VAD 설정
- A3. `hallucination_silence_threshold` 파라미터 (faster-whisper 내장)
  - 일정 시간 이상 무음 감지 시 해당 구간 드롭
  - `align_att_base.py`의 디코딩 옵션에 추가 가능 여부 확인

**접근법 B — 비음성 구간의 출력을 인식 후 필터**
- B1. 전사 후 텍스트 패턴으로 환각 감지 (반복 단어, 이상 문자 비율, 길이 대비 정보량)
- B2. CRT(compression_ratio_threshold) 낮춰서 반복성 높은 세그먼트 차단
  - 현재 3.0 → 2.5~2.8 탐색
- B3. 세그먼트 확률 분포 분석: 토큰 확률 표준편차가 낮으면(= 모델이 확신하지만 틀릴 때) 경고 신호

**접근법 C — 비음성 구간을 다르게 처리**
- C1. 비음성 구간 탐지 후 언어 context 리셋 → 이후 정상 발화 언어 재감지
- C2. 비음성 구간을 짧은 세그먼트로 분리해 별도 처리 (정상 발화와 독립)

---

### 🟡 문제 2: 코드스위칭 경계 (ytn2 — 한↔영 짧은 텀 교차)

한 문장씩 교대하는 환경에서 언어 전환 시 단어 유실 또는 전환 지연.

**접근법 A — 언어 전환 탐지 개선**
- A1. 매 배치에서 언어 ID 토큰 확인 → 전환 즉시 감지
  - `periodic_lang_check` 주기 단축 (현재 4.0s → 2.0s → 1.0s 탐색)
  - 탐지 방법: 디코딩 중 언어 토큰 확률 모니터링
- A2. 언어 전환 시점을 명시적 신호로 추출
  - 연속 배치에서 언어가 바뀌면 → 이전 세그먼트 강제 확정 + 새 언어로 context 시작
  - 구현: `align_att_base.py`의 language change 감지 로직
- A3. 언어 전환 직전 토큰들의 확률 분포 분석 → 전환 예측

**접근법 B — 언어 전환 = 문장 경계 신호로 활용**
- B1. 언어 바뀌는 순간 → 자동 문장 확정 트리거
  - 현재 확정 신호(VAD silence, 세그먼트 경계)에 "언어 전환"을 추가
  - 구현: `simul_whisper.py`의 확정 로직에 language change hook
- B2. 언어 전환 + 짧은 무음 조합 시 확정 (단독 신호보다 정확도 높음)

**접근법 C — 디코딩 전략 변경**
- C1. 전환 구간에서 beam_size 증가 (언어 불확실성 높을 때만 탐색 확대)
- C2. 전환 감지 시 context 클린업 → 이전 언어 context가 새 언어 인식을 방해 방지
- C3. multilingual 모드로 배치마다 언어 자동 감지 후 해당 언어로 재디코딩

**접근법 D — 문장 구조 기반 경계 감지**
- D1. 의미 완결 신호 감지: 마지막 토큰 확률 패턴에서 EOS 신호 추출
  - Whisper 출력에 구두점은 없지만, 문장 끝 토큰 분포가 다름
- D2. 언어 전환 직전 발화의 길이·속도 분석 → 짧은 발화 = 단문 완결 신호
- D3. 통역 패턴 활용: EN 발화 → KO 통역은 거의 항상 교대 → 언어 전환 자체가 문장 경계

---

### 🟢 문제 3: 문장 경계 인식 (F1 — 전반적)

확정 문장 경계가 정답과 일치하지 않음. F1이 낮으면 WER도 간접 영향.

**접근법 A — 의미 완결 신호 기반**
- A1. 무음(silence) 길이 + 언어 전환 조합으로 문장 경계 판단
- A2. 토큰 확률 급변 시점 감지 (새 발화 시작 신호)
- A3. 발화 속도 변화 감지 (문장 끝 = 속도 느려짐)

**접근법 B — 하드웨어/타임스탬프 기반**
- B1. 타임스탬프 기반 긴 무음 (현재 VAD silence보다 세밀한 기준)
- B2. 화자 전환 탐지 결과를 문장 경계 1차 신호로만 사용 (확정 로직에서 분리)

**접근법 C — 출력 후처리**
- C1. 확정된 텍스트의 의미 완결성 판단 (짧은 규칙 기반: 동사 있으면 완결 등)
- C2. 온점/쉼표가 없어도 구조적 경계(주어+동사+목적어 완결) 추정

---

### 🔵 공통: 디코더 파라미터 재검증

E2(lang_restrict_koen + logprob=-2.0) 환경에서 E1 기각 실험들 재검증.
**단일 변수 → 확인 후 콤보** 순서.

| 파라미터 | 탐색 범위 | 기대 효과 | 비고 |
|---------|---------|---------|------|
| `--periodic-lang-check` | 2.0 / 1.0 / 0.5 | 코드스위칭 전환 빠른 감지 | E1에서 bong1 max 회귀(버그로 실제 미동작) |
| `--beam-size` | 3 / 4 | median 개선 가능성 | E1 sbs1 max 회귀 (E2 재검증) |
| `--compression-ratio-threshold` | 2.5 / 2.8 | garbage 세그먼트 추가 차단 | 미탐색(E2) |
| `no_speech_threshold` | 0.5 / 0.6 / 0.7 | 비음성 구간 배제 | parse_args 추가 필요 |
| `repetition_penalty` | 1.1 / 1.2 | 반복 환각 억제 | 미탐색 |
| `condition_on_previous_text` | False | context 고착 방지 | 미탐색 |
| `temperature` | fallback 조정 | 낮은 품질 세그먼트 재시도 | 미탐색 |

---

### 🟣 공통: 컨텍스트·프롬프트 전략

**접근법 A — 초기 프롬프트 최적화**
- A1. `--init-prompt`에 코드스위칭 힌트 포함 ("한국어와 영어가 번갈아 나옵니다.")
- A2. `--init-prompt`에 도메인 특화 용어 포함 (SCM, ROK, OPCON 등 ytn2 맥락)
- A3. `static_init_prompt` vs `dynamic_init_prompt` 전략 비교

**접근법 B — Hotwords**
- B1. faster-whisper `hotwords` 파라미터로 자주 오인식 단어 힌트
- B2. 언어별 hotwords 분리 등록

**접근법 C — Context 리셋 전략**
- C1. 언어 전환 감지 시 이전 context 제거 (오염 방지)
- C2. 비음성 구간 이후 context 리셋 (환각 연쇄 방지)
- C3. 세그먼트 단위 context 슬라이딩 윈도우 (오래된 context 영향 감소)

---

### ⚫ 복합 접근: 앙상블·멀티패스

- **투 패스 디코딩**: 1차 패스로 언어 감지만 수행 → 2차 패스를 감지된 언어로 재디코딩
- **세그먼트 앙상블**: 같은 구간을 다른 파라미터로 2회 디코딩 → 더 높은 신뢰도 결과 선택
- **동적 파라미터**: 언어 불확실성 높은 구간에서 beam 자동 증가
- **후처리 재조합**: 세그먼트 경계를 후처리에서 재계산 (확정 후 재구성)

---

## 이터레이션 의사결정 절차

```
매 이터레이션 시작:

  1. 현재 결과의 실패 분포 확인
     - 어떤 파일이 목표(avg 15%)에서 가장 멀리 있는가?
     - 그 파일의 전사 텍스트에서 지배적 실패 패턴은?

  2. 아직 시도 안 한 접근법 목록 작성
     - EXPERIMENTS.md(STATE)에서 기각된 실험들의 기각 이유 확인
     - 기각 이유가 현재도 유효한가? (E1→E2 변화로 전제가 달라졌을 수 있음)
     - 같은 목표를 다른 레이어(디코더/후처리/프롬프트/VAD)에서 해결 가능한가?

  3. 가설 선택 기준
     - 잠재 개선량 높음 + 구현 간단 → 먼저
     - 단일 변수 → 콤보 순서
     - 이미 기각된 방향의 변형이면 기각 원인 해결 여부 명확히

  4. 구현 전 자문
     - "이 접근법이 실패한다면 어떤 이유에서인가?"
     - "그 이유를 피할 다른 구현 방법이 있는가?"
```

---

## 새 워크트리 생성 표준 절차

```powershell
$root = "c:\Users\A040-000-0001\Desktop\260605wlk\wlk"
$name = "exp-<가설명칭>"  # 예: exp-nospeech-drop, exp-beam3-e2, exp-lang-switch-boundary

git worktree add -b "exp/$name" "$root\worktrees\$name" master
Set-Location "$root\worktrees\$name"
cmd /c mklink /J .venv ..\..\..\.venv   # 공유 venv (패키지 변경 없으면)

# import 확인
.venv\Scripts\python.exe -c "import whisperlivekit; print('OK')"
```

---

## 측정 명령 레퍼런스

```powershell
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$root = "c:\Users\A040-000-0001\Desktop\260605wlk\wlk"

# ① 스크리닝 (N=1, 방향 신호) — 워크트리 cwd에서
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir "$root\whisperlivekit\model\whisper-large-v3-turbo" `
  --files "$root\test_data\bong1.wav" "$root\test_data\ytn2.mp3" "$root\test_data\sbs1.mp3" `
  --diarization --sortformer-model "$root\whisperlivekit\model\sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --output "$root\.omc\benchmarks\eval_${ts}_<name>.json"

# ② 확정 (N=3, 채택 직전) — 위와 동일 + --repeat 3

# ③ held-out (채택 후보에 한해 단회)
.venv\Scripts\python.exe scripts/eval.py `
  --files "$root\test_data\ytn1.mp3" "$root\test_data\eng1.mp3" `
  --diarization --sortformer-model "$root\whisperlivekit\model\sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --output "$root\.omc\benchmarks\eval_${ts}_heldout.json"
```

---

## 채택/기각 기준 (CLAUDE.md §4)

```
스크리닝(N=1):
  catastrophic (baseline max 대비 +20pp 이상): 즉시 기각
  개선 신호 (-3pp 이상, 주요 파일): N=3 확정 진행
  미미 (±3pp): 다른 가설 먼저 또는 콤보로

확정(N=3):
  ① 1순위: max WER 미회귀 (⚠️ 아래 수치는 base 기질 게이트 — turbo 기질(E5) 게이트로 재산정 필요,
           1차 turbo 참고치: bong1 ≤ 34.7%, ytn2 ≤ 47.3%, sbs1 ≤ 31.0% — EXPERIMENTS.md 참조)
  ② 2순위: median WER 개선
  WER > F1 우선 (F1 하락 있어도 WER 명확히 개선이면 채택 가능)
  F1 catastrophic 폭주 시 원인 파악 우선
```

---

## 불변 제약 (변경 불가)

- **폐쇄망**: 런타임 네트워크 호출 금지. 모델은 로컬만.
- **한/영 두 언어 고정**: `lang_restrict_koen=True`(E2 기본값). WER 미개선이어도 자율 기각 금지 — 사용자 질의.
- **데이터 특화 하드코딩 금지**: 일반화된 개선만 (특정 파일 텍스트 암기 아님).
- **경로 C(VBCable)만 채택 기준**: RMS < 0.01이면 VBCable 사망 → 재부팅/Audiosrv 재시작 후 재측정.

---

## 루프 보고 시점

아래 경우에만 사용자 보고 + 입력 대기:
1. **목표 달성**: 평균 WER < 15% → 최종 결과·채택 이력·핵심 기여 실험 보고
2. **방향 소진**: 탐색 공간 전부 시도 후 미달성 → 현황·격차·추가로 시도할 방향(새 아이디어) 보고
3. **major 방향 전환**: 구조적 변경(VAD 파이프라인 교체, 디코더 아키텍처 변경 등) 시작 전
4. **§3.2 불변 제약 탈락**: lang_restrict 관련 기능이 게이트 탈락 시
5. **VBCable 사망**: 재부팅 후에도 RMS < 0.01 지속 시

---

## 참조 파일

| 파일 | 용도 |
|------|------|
| `EXPERIMENTS.md` | **항상 먼저** — 현행 baseline·epoch·채택 이력 |
| `CLAUDE.md §3~4` | 설계 제약·측정 규칙·자율 루프 원칙 |
| `whisperlivekit/simul_whisper/align_att_base.py` | 품질 게이트·언어 감지·확정 로직 |
| `whisperlivekit/simul_whisper/backend.py` | 디코더 파라미터 전달, VAD 설정 |
| `whisperlivekit/filtering/__init__.py` | 현재 필터링 파이프라인 |
| `whisperlivekit/simul_whisper/config.py` | AlignAttConfig 필드 목록 |
| `whisperlivekit/parse_args.py` | CLI 파라미터 기본값 |
| `whisperlive_code/` | 참고용 구현 예시 (복사 금지, 아이디어만) |
| `EXPERIMENTS_LOG.md` | 필요한 Exp만 `grep "Exp-NNN"` |
| `docs/FILE_INDEX.md` | 코드 파일 위치 전체 색인 |
