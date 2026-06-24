# /eval — 경로 C 성능 평가 (실제 파이프라인 기준)

기능 수정 후 경로 C(VBCable 루프백)로 실제 오디오 파이프라인 전체를 통과한 성능을 측정한다.
**WER(전사 정확도) + 문장 분리 F1(문장 확정 정확도)**를 출력한다.
서버 기동/종료와 VBCable 장치 설정/복원은 스크립트가 자동으로 처리한다.
**테스트(채택/기각) 세트 = `bong1.wav` + `ytn2.mp3` + `sbs1.mp3`** (화자분할 ON, `--repeat 3` 루틴; ytn2·bong1 공동 최우선). **held-out 일반화 검증 = `ytn1.mp3` + `eng1.mp3`** (채택 후보에 한해 동일 diar-ON 설정으로 측정). `eval.py`의 기본 `--files`는 코드 상 여전히 sbs1/ytn1/eng1이므로 **루틴은 `--files` 명시 필수**.

**성능 판정 기준은 경로 C만** 사용한다. 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회하므로 폐기.

**채택 판단 우선순위**: **1순위 = 최악 케이스(max) 미회귀**, 2순위 = median 개선.
최악 케이스가 발생하면 median 개선보다 원인 파악과 해결이 먼저다.
채택/기각 측정 시 `--repeat 3`으로 돌려 median + 분산(min/max/stdev)으로 판단. **fail-fast 금지.**
단 VBCable 미설정·무음 캡처 등 *하니스 버그*는 즉시 중단·수정.

## 기본 사용법

```powershell
# 테스트(채택/기각) — bong1 + ytn2 + sbs1, 화자분할 ON, 빠른 현황 확인
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0

# 채택/기각 결정용 (N≥3회 반복 — Claude가 실험 비교 시 사용)
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3

# held-out 일반화 검증 — 채택 후보에 한해 ytn1 + eng1 (동일 diar-ON 설정)
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/ytn1.mp3 test_data/eng1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3

# 결과를 파일로 저장 (베이스라인 또는 비교용)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3 `
  --output ".omc/benchmarks/eval_$ts.json"
```

## 실행 절차 (Claude가 따를 순서)

1. `$env:PYTHONIOENCODING = "utf-8"` 설정 후 eval.py 실행
2. VBCable 자동 설정 여부 로그 확인 (성공/실패/건너뜀)
3. 결과 JSON에서 파일별 `summary`(wer_median/min/max/stdev, f1_*)와 `avg_wer_c_median`/`avg_seg_f1_c_median` 추출.
   **median + 최악 케이스(max)를 함께** 본다 (경로 C = 성능 기준 지표)
4. `.omc/benchmarks/`의 가장 최근 JSON과 비교:
   ```powershell
   Get-ChildItem .omc/benchmarks/eval_*.json | Sort-Object Name | Select-Object -Last 1
   ```
5. 개선 여부를 "이전 F1 → 현재 F1" 및 "이전 WER → 현재 WER (변화량%p)" 형식으로 표시
6. 결과를 `/log-experiment`로 기록할지 사용자에게 확인

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

- 서버 포트 8001 사용 (개발 서버 8000과 충돌 방지)
- 서버 ready까지 최대 120초 대기 (모델 로딩 시간)
- 경로 C `--repeat 3` 실행 시 (오디오 길이 + `--wait`) × 3 소요 (테스트 3파일 bong1+ytn2+sbs1 기준: 약 18분 이상; 화자분할 서버 로딩 최초 1회 +약 30초 추가). 백그라운드 실행 권장
- 결과 JSON은 `.omc/benchmarks/` 디렉토리에 저장 권장 (`.gitignore` 적용됨)
