# /eval — 경로 C 성능 평가 (실제 파이프라인 기준)

기능 수정 후 경로 C(VBCable 루프백)로 실제 오디오 파이프라인 전체를 통과한 성능을 측정한다.
**WER(전사 정확도) + 문장 분리 F1(문장 확정 정확도)**를 출력한다.
서버 기동/종료와 VBCable 장치 설정/복원은 스크립트가 자동으로 처리한다.
**테스트(채택/기각) 세트 = `bong1.wav` + `ytn2.mp3` + `sbs1.mp3`** (화자분할 ON; ytn2·bong1 공동 최우선). 측정은 **2계층**: ① 평소 스크리닝 = `--repeat 1`(방향 신호), ② master 채택 직전 확정 = `--repeat 3`(median+분산 판단). **held-out 일반화 검증 = `ytn1.mp3` + `eng1.mp3`** (채택 후보에 한해 **단회** diar-ON). `eval.py`의 기본 `--files`는 코드 상 여전히 sbs1/ytn1/eng1이므로 **루틴은 `--files` 명시 필수**.

**성능 판정 기준은 경로 C만** 사용한다. 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회하므로 폐기.

**채택 판단 우선순위(② 채택 확정 단계)**: **1순위 = 최악 케이스(max) 미회귀**, 2순위 = median 개선.
최악 케이스가 발생하면 median 개선보다 원인 파악과 해결이 먼저다.
스크리닝(1회) 수치는 방향 신호로만 해석 — 미세 채택/기각 결론의 근거로 쓰지 않는다.
채택 확정(머지 직전)에만 `--repeat 3`으로 돌려 median + 분산(min/max/stdev)으로 판단. **채택 확정 시 fail-fast 금지.**
단 VBCable 미설정·무음 캡처 등 *하니스 버그*는 즉시 중단·수정.
**목표 필수 기능 예외**: §3.1·§3.2 불변 제약 달성에 필요한 기반 기능이 게이트 탈락 시 자율 기각 금지 — 결과·대안 보고 후 사용자 질의.

## 기본 사용법

```powershell
# ① 스크리닝(기본) — bong1 + ytn2 + sbs1, 화자분할 ON, 방향 탐색·catastrophic 회귀 감지용
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"
# ↑ --repeat 생략 = 기본값 1회. 수치는 '방향 신호'로만 해석한다.

# ② 채택 확정용 (master 머지 직전에만 — N≥3회 반복, median+분산 판단)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3 `
  --output ".omc/benchmarks/eval_$ts.json"

# held-out 일반화 검증 — 채택 후보에 한해 ytn1 + eng1 (단회, diar-ON)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/ytn1.mp3 test_data/eng1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"
# ↑ held-out은 단회 검증(채택 확정이라도 --repeat 3 불필요)
```

## 실행 절차 (Claude가 따를 순서)

1. `$env:PYTHONIOENCODING = "utf-8"` 설정 후 eval.py 실행 (`--output`으로 JSON 자동 저장됨)
2. VBCable 자동 설정 여부 로그 확인 (성공/실패/건너뜀)
3. 저장된 JSON에서 파일별 `wer_median/min/max/stdev`, `seg_f1_median`, `avg_wer_c_median`/`avg_seg_f1_c_median` 추출.
   **median + 최악 케이스(max)를 함께** 본다 (경로 C = 성능 기준 지표).
4. `.omc/transcripts/`에 저장된 전사 파일을 읽어 **정성 평가**를 수행한다 (아래 §정성 평가 절차 참조).
   정량(WER/F1)과 정성(목표 달성 여부·신규 이슈)을 **함께** 고려해 채택/기각/사용자 확인을 판정한다.
5. `.omc/benchmarks/`의 가장 최근 JSON과 비교:
   ```powershell
   Get-ChildItem .omc/benchmarks/eval_*.json | Sort-Object Name | Select-Object -Last 1
   ```
6. 개선 여부를 "이전 WER → 현재 WER (변화량%p)" 및 정성 판정 결과와 함께 표시
7. 결과를 `/log-experiment`로 기록할지 사용자에게 확인

## 정성 평가 절차

eval.py 완료 후 `.omc/transcripts/`에 저장된 `{파일명}_{경로}_R{회차}.txt`를 읽어
**정량 지표가 포착 못하는 목표 달성 여부**를 판정한다.

각 전사 파일의 `[전사]` vs `[정답]` 텍스트를 비교해 다음 세 항목을 분석한다:

1. **목표 달성**: 이번 실험의 가설(예: "언어 전환 시 truncation 감소")이 실제로 개선됐는가?
   - 가설이 겨냥한 구간(예: 코드스위칭 전환부, 다화자 발화 경계)의 오류 패턴 변화 확인
2. **신규 문제**: 이전에 없던 오류 유형(환각 폭주·언어 혼용·단어 누락 폭증)이 생겼는가?
3. **오류 분포 변화**: WER 개선/악화가 어느 구간에서 발생했는가? (특정 구간 집중인지 전반적인지)

### 정량 + 정성 통합 채택 판정

| 정량(WER) | 정성 | 판정 |
|-----------|------|------|
| 개선 | 목표 달성, 신규 이슈 없음 | **채택** |
| 개선 | 목표 달성, 신규 이슈 있음 | **사용자 확인** — 이슈 규모·성격 함께 보고 |
| 변화 없음 | 목표 달성 | **사용자 확인** — 달성 근거와 수치 변화 없음 이유 함께 보고 |
| 회귀 | 목표 달성, 다른 구간 악화 | **사용자 확인** — 목표 달성 구간과 회귀 구간을 모두 보고 |
| 회귀 | 목표 미달성 | **기각** |

> §3.1·§3.2 불변 제약 관련 기능이 정량 게이트 탈락 시 자율 기각 금지 — 결과·대안 보고 후 사용자 질의.

## 결과 해석 기준

WER과 문장 분리 F1 모두 주요 지표다. 두 지표를 함께 보아야 전체 품질을 판단할 수 있다.

### WER (전사 정확도)

환각 단어 생성(삽입)·단어 누락(삭제)을 포함한 전반적인 전사 정확도를 측정한다.

| WER 변화 | 판정 |
|----------|------|
| -5%p 이상 감소 | 유의미한 개선 |
| ±5%p 이내 | 유의미한 변화 없음 |
| +5%p 이상 증가 | 성능 저하 — 원인 조사 필요 |

**WER 원인 구분:** WER이 높거나 개선되지 않을 때, 전사 출력(JSON)을 확인해 원인을 구분한다.
- **치환 오류** ("육군"→"6군", "공군력"→"공군역"): 모델 자체 한계 — Phase 2에서 직접 추적하지 않음
- **환각 삽입·단어 누락**: 스트리밍 단계 문제 — Phase 2 개선 대상

### 문장 분리 F1 (문장 확정 정확도)

정답의 빈 줄 경계(화자전환 1순위 + 온점분리 2순위)와 STT 확정 문장(`lines[]`)의 경계 위치를 단어 정렬로 비교한다.

| F1 | 판정 |
|----|------|
| 0.8 이상 | 문장 경계 매우 정확 |
| 0.5 ~ 0.8 | 보통 — 일부 과분할/미분할 |
| 0.5 미만 | 문장 구분 부정확 — Precision↓=과분할, Recall↓=미분할로 진단 |

> 참고: Phase 2 문장 확정 로직 구현 전에는 STT가 전체 전사를 1개 라인으로 묶어 출력하므로
> F1≈0이 정상 베이스라인이다. 문장 확정 로직이 도입될수록 F1이 상승해야 한다.

## VBCable 자동 설정

스크립트가 자동으로 처리한다:
- CABLE이 이미 기본 장치면 그대로 진행
- 아니면 `audio_device.py`로 임시 설정 → 테스트 완료 후 원래 장치로 복원
- 자동 설정 실패 시 경고 출력 후 경로 C 건너뜀

수동 설정이 필요한 경우 (자동 설정 실패 시):
- Windows 소리 → 재생 장치: `CABLE Input` 기본값으로 변경
- Windows 소리 → 녹음 장치: `CABLE Output` 기본값으로 변경

## 주의사항

- 서버 포트 8901 사용 (수동 서버 기본값 8900과 충돌 방지)
- 서버 ready까지 최대 120초 대기 (모델 로딩 시간)
- 경로 C `--repeat 3` 실행 시 (오디오 길이 + `--wait`) × 3 소요 (테스트 3파일 bong1+ytn2+sbs1 기준: 약 18분 이상; 화자분할 서버 로딩 최초 1회 +약 30초 추가). 백그라운드 실행 권장
- 결과 JSON은 `.omc/benchmarks/` 디렉토리에 저장 권장 (`.gitignore` 적용됨)
- **서버 로그**(Exp-153~): eval.py가 매 회차 서버 stdout/stderr를 `.omc/server_logs/server_<stem>_<path>_R<rep>_<ts>.log`로 **항상** 저장한다. `[QualityGate]`(avg_logprob 억제)·`[BatchRepeatFilter]` 등 필터 계측은 기본 기록되고, `[LangSwitch]` 전환 트레이스는 `--trace-tokens` 시 기록. Q1(필터 기여도) 분석에 사용
