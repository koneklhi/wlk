# /eval — 경로 A + C 통합 성능 평가

기능 수정 후 경로 A(파일 기반 WebSocket)와 경로 C(VBCable 루프백) 테스트를 자동으로 실행하고
WER 결과를 출력한다. 서버 기동/종료와 VBCable 장치 설정/복원은 스크립트가 자동으로 처리한다.

## 기본 사용법

```powershell
# 경로 A + C 모두 실행 (기본)
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo

# 경로 A만 실행 (빠름, VBCable 불필요)
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --paths A

# 결과를 파일로 저장 (베이스라인 또는 비교용)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --output ".omc/benchmarks/eval_$ts.json"
```

## 실행 절차 (Claude가 따를 순서)

1. `$env:PYTHONIOENCODING = "utf-8"` 설정 후 eval.py 실행
2. VBCable 자동 설정 여부 로그 확인 (성공/실패/건너뜀)
3. 결과 JSON에서 `avg_wer_a`, `avg_wer_c` 추출
4. `.omc/benchmarks/`의 가장 최근 JSON과 비교:
   ```powershell
   Get-ChildItem .omc/benchmarks/eval_*.json | Sort-Object Name | Select-Object -Last 1
   ```
5. 개선 여부를 "이전 WER → 현재 WER (변화량%p)" 형식으로 표시
6. 결과를 `/log-experiment`로 기록할지 사용자에게 확인

## 결과 해석 기준

| WER 변화 | 판정 |
|----------|------|
| -5%p 이상 감소 | 유의미한 개선 |
| ±5%p 이내 | 유의미한 변화 없음 |
| +5%p 이상 증가 | 성능 저하 — 원인 조사 필요 |

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
- 경로 A는 `--speed 0`으로 가능한 빠르게 실행
- 경로 C는 오디오 길이 + `--wait` 시간만큼 소요 (기본 sbs1.mp3: 약 2분)
- 결과 JSON은 `.omc/benchmarks/` 디렉토리에 저장 권장 (`.gitignore` 적용됨)
