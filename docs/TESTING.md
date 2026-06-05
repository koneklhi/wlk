# 테스트 / 환경 가이드

본 문서는 [CLAUDE.md](../CLAUDE.md)에서 분리한 **환경 상세 + 테스트 실행 절차**를 담는다.
불변 설계 제약·운영 규칙은 CLAUDE.md를, 본 문서는 "어떻게 실행하고 검증하는가"를 다룬다.

---

## 1. 개발 / 테스트 환경 (현재 작업 환경)

- Windows PC, **RTX 3080**, 인터넷 연결 가능
- VS Code IDE에서 Claude Code를 통해 개발/테스트
- 테스트 입력 경로 — 세 가지 방식 병렬 운영 (경로 C는 Phase 2에서 도입)

### 경로 A — 파일 기반 (빠른 개발 스모크/회귀 확인)

- WhisperLiveKit 내장 헤드리스 클라이언트 [whisperlivekit/test_client.py](../whisperlivekit/test_client.py)로
  **`test_data/` 내 로컬 mp3/wav 파일을 WebSocket `/asr`에 직접 송신**한다.
- **가상 오디오 케이블(VB-Cable, VoiceMeeter 등)에 의존하지 않는다.** 사운드 카드/드라이버 설치도 불필요.
- 의존성: 시스템 `ffmpeg` 설치 필수 (파일을 PCM s16le 16kHz mono로 변환).
- 서버는 `--pcm-input` 플래그로 기동 → 클라이언트가 PCM 청크를 직접 송신.
- 실행 예:
  - 서버 기동:
    `whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --lan auto --pcm-input --warmup-file test_data/sbs1_10s.mp3`
  - 파일 송신: `python -m whisperlivekit.test_client test_data/sbs1.mp3 --live`
  - Windows PowerShell에서 한국어 출력 깨짐 방지: `$env:PYTHONIOENCODING = "utf-8"` 선행 실행 필요
- 옵션: `--speed 1.0`(실시간) / `--speed 0`(가능한 한 빠르게), `--language ko`/`--language en` 강제,
  `--live`로 비확정/확정 진행 출력, `--json`으로 원본 응답 로깅.
- **자동 평가**: `scripts/eval.py`는 기본적으로 경로 C(1차 정량)를 실행한다. 경로 A는 `--paths A`로
  빠른 개발 스모크(코드 회귀 확인)용으로 돌린다. 두 경로 모두 **WER + 문장 분리 F1**을 산출한다.
  문장 분리 F1은 정답의 빈 줄 블록(= 문장 1개)과 STT 확정 문장(`lines[]`)의 경계 위치를 비교한다.

### 경로 B — 마이크 직접 녹음 (정성적)

- 서버를 `--pcm-input` 플래그 없이 기동 → 브라우저가 `MediaRecorder` 방식으로 마이크 음성을 실시간 캡처
- 브라우저에서 `http://localhost:8000/` 접속 → 내장 웹 UI
  ([whisperlivekit/web/live_transcription.html](../whisperlivekit/web/live_transcription.html))에서 마이크 직접 녹음
- 마이크에 직접 말하면서 전사 결과를 실시간 확인 (정성적 평가)
- 서버 기동 예:
  `whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --lan ko --warmup-file test_data/sbs1_10s.mp3`
  - Phase 1 단계에서는 `--lan ko`로 한국어 강제 — `--lan auto`는 LocalAgreement 백엔드가 청크마다 언어를
    재추정해 한·일 진동/hallucination을 유발. 한·영 Code-Switching 대응은 [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) 참조.
- 목적: 실제 마이크 입력에 대한 정성적 평가 (경로 C 정량 평가와 병행)

### 경로 C — 오디오 루프백 (1차 정량 성능 기준, Phase 2 도입)

- VBCable로 테스트 파일을 PC에서 재생해 가상 마이크 경유 전사
- 마이크 입력 경로(경로 B)를 유지하면서 동일 음성으로 반복 측정 가능 → 재현성 있는 정량 평가.
  실제 오디오 파이프라인을 거치므로 Phase 2 채택/기각의 **1차 정량 신호**다.
- 헬퍼: [scripts/vbcable_test.py](../scripts/vbcable_test.py)
- `scripts/eval.py`는 기본으로 경로 C를 실행해 **WER + 문장 분리 F1**을 산출한다.
  브라우저 `#linesTranscript`의 `.textcontent`(확정 문장)만 추출하므로 타임스탬프 행이 섞이지 않는다.

**수동 서버 기동 명령 (eval.py 자동 기동 옵션과 동일하게 맞출 것):**
```
python -m whisperlivekit.basic_server \
  --model_dir whisperlivekit/model/whisper-large-v3-turbo \
  --backend whisper \
  --lan auto \
  --host localhost --port 8001 \
  --warmup-file test_data/sbs1_10s.mp3
```
`--pcm-input` 없음(브라우저 마이크 모드), VAC 기본 켜짐(`--no-vac` 없음), `--lan auto` 기본.
`eval.py --lan` 기본값과 반드시 일치시킬 것 — 옵션이 다르면 수동/자동 결과를 비교할 수 없다.

> ⚠️ **반복 측정 필수**: 실시간 STT는 동일 조건에서도 매 실행마다 성능 편차가 발생한다.
> 채택/기각 판단에 사용하는 경로 C 수치는 **동일 파일·설정으로 최소 3회 실행** 후
> 중앙값(또는 평균)을 기준으로 한다. 1회 결과만으로 결론 내리지 말 것.

- 상세 배경은 [ROADMAP.md](../ROADMAP.md) Phase 2 참조.

### test_data 디렉토리 구조

- `test_data/` 디렉토리: 음성 파일(mp3/wav) + 선택적 정답 스크립트(txt)
- 파일명 규칙: 음성파일과 정답 스크립트 파일명 동일, 확장자만 다름 (예: `sbs1.mp3` ↔ `sbs1.txt`)
- 정답 스크립트가 없는 음성파일도 존재 가능
- **정답 스크립트 형식**: 빈 줄(`\n\n`)로 구분된 블록 = 문장 1개. 문장 분리 F1 평가의 기준이 된다.
  (마침표 기준 분리는 하지 않음 — `U.S.` 등 약어 오분할 회피)
- 현재: `sbs1.mp3`/`sbs1.txt` (뉴스 리포트, 한·영 인용구), `ytn1.mp3`/`ytn1.txt` (SCM 회의 통역, 한·영 코드 스위칭 풍부)
- 용도: STT 전사 정확도(WER) + 문장 확정 정확도(F1) 정량 분석

### STT 동작 확인용 UI 선택지

- **터미널**: `test_client.py --live` 또는 `--json` 출력으로 `lines[]`(확정) + `buffer_transcription`(비확정)
  흐름까지 확인 가능. 백엔드 로그/print 병행. (경로 A 파일 기반 테스트용)
- **WhisperLiveKit 내장 웹 UI**
  ([whisperlivekit/web/live_transcription.html](../whisperlivekit/web/live_transcription.html) + `live_transcription.js`,
  `live_transcription.css`, 서버 실행 시 `GET /`에서 자동 서빙됨): 서버 기동 후 브라우저에서 접속하면 마이크 캡처 및
  실시간 전사 결과를 UI상에서 시각적으로 확인 가능. (경로 B 마이크 직접 녹음 테스트용)
- **기존 React 웹 UI**: 번역(llama) 파이프라인까지 묶어 최종 검증할 때 연결.

### 권장 검증 순서

1. `test_client.py`로 mp3/wav 송신 (경로 A) → 터미널에서 번역 제외, 실시간 STT 전사 동작 확인 (개발 스모크)
2. 서버 기동 후 브라우저 + 마이크 직접 녹음 (경로 B) → 내장 웹 UI에서 실시간 전사 결과 시각 확인 (정성 평가)
3. `test_client.py --live` 터미널 출력으로 확정/비확정 플래그 + 언어 전환 동작 확인
4. 기존 React 웹 UI 연결 후 번역 + 최종 UI 표출까지 확인

---

## 2. 배포 환경

- **폐쇄망** Windows PC, **RTX 5090**, 외부 인터넷 차단
- 실제 마이크 입력 사용
- 모든 모델·라이브러리는 **오프라인 / 로컬 경로 기반**으로 동작해야 한다. 런타임에 HuggingFace Hub, PyPI,
  GitHub 등에 접속하면 안 된다. (불변 제약 — [CLAUDE.md](../CLAUDE.md) §3 참조)

---

## 3. 모델

- **STT**: `whisper-large-v3-turbo` — 로컬 경로:
  [whisperlivekit/model/whisper-large-v3-turbo/](../whisperlivekit/model/whisper-large-v3-turbo/)
  (`config.json` / `model.safetensors` / `tokenizer.json` 등)
- **번역**: 기존 `whisperlive`에서 쓰던 **OSS 20B LLM** 그대로 사용.
