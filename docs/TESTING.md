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
  - 서버 기동: `whisperlivekit-server --pcm-input` (나머지는 모두 parse_args.py 기본값)
  - 파일 송신: `python -m whisperlivekit.test_client test_data/sbs1.mp3 --live`
  - Windows PowerShell에서 한국어 출력 깨짐 방지: `$env:PYTHONIOENCODING = "utf-8"` 선행 실행 필요
- 옵션: `--speed 1.0`(실시간) / `--speed 0`(가능한 한 빠르게), `--language ko`/`--language en` 강제,
  `--live`로 비확정/확정 진행 출력, `--json`으로 원본 응답 로깅.
- **자동 평가**: `scripts/eval.py`는 기본적으로 경로 C(1차 정량)를 실행한다. 경로 A는 `--paths A`로
  빠른 개발 스모크(코드 회귀 확인)용으로 돌린다. 두 경로 모두 **WER + 문장 분리 F1**을 산출한다.
  문장 분리 F1은 정답의 빈 줄 경계(= 화자전환 1순위 + 온점분리 2순위)와 STT 확정 문장(`lines[]`)의 경계 위치를 비교한다.

### 경로 B — 마이크 직접 녹음 (정성적)

- 서버를 `--pcm-input` 플래그 없이 기동 → 브라우저가 `MediaRecorder` 방식으로 마이크 음성을 실시간 캡처
- 브라우저에서 `http://localhost:8900/` 접속 → 내장 웹 UI
  ([whisperlivekit/web/live_transcription.html](../whisperlivekit/web/live_transcription.html))에서 마이크 직접 녹음
- 마이크에 직접 말하면서 전사 결과를 실시간 확인 (정성적 평가)
- 서버 기동: `whisperlivekit-server` (모든 인자가 parse_args.py 기본값 — `--lan auto` + simulstreaming. `--periodic-lang-check` 기본 None(비활성); 탐색 시 명시적 값 지정. 상세는 [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) 참조)
- 목적: 실제 마이크 입력에 대한 정성적 평가 (경로 C 정량 평가와 병행)

### 경로 C — 오디오 루프백 (1차 정량 성능 기준, Phase 2 도입)

- VBCable로 테스트 파일을 PC에서 재생해 가상 마이크 경유 전사
- 마이크 입력 경로(경로 B)를 유지하면서 동일 음성으로 반복 측정 가능 → 재현성 있는 정량 평가.
  실제 오디오 파이프라인을 거치므로 Phase 2 채택/기각의 **1차 정량 신호**다.
- 헬퍼: [scripts/vbcable_test.py](../scripts/vbcable_test.py)
- `scripts/eval.py`는 기본으로 경로 C를 실행해 **WER + 문장 분리 F1**을 산출한다(F1 기준: 빈 줄 = 화자전환 경계(1순위 필수) + 온점분리 경계(2순위 선택)).
  브라우저 `#linesTranscript`의 `.textcontent`(확정 문장)만 추출하므로 타임스탬프 행이 섞이지 않는다.

**수동 서버 기동 명령:**
```
whisperlivekit-server
```
모든 인자가 `parse_args.py` 기본값(포트 8900, `--lan auto`, 화자분할 ON, `--compression-ratio-threshold 3.0`, `--logprob-threshold -2.0` 등)이라
인자 없이 기동해도 eval.py/closed_test.py 자동 기동 설정과 동일하다.
단, eval/closed_test는 서버를 **8901**로 자동 기동한다(수동 서버 8900과 포트 충돌 없이 병행 가능).

> ⚠️ **반복 측정 — 2계층**: 실시간 STT는 동일 조건에서도 매 실행마다 성능 편차가 발생한다.
> **① 평소 스크리닝 = 1회** (`--repeat` 생략) — 방향 탐색·catastrophic 회귀 감지용. 1회 수치는 방향 신호로만 해석한다.
> **② master 채택 확정(머지 직전)만 최소 3회** (`--repeat 3`) — median+분산(min/max/stdev)으로 판단. 상세 규칙은 CLAUDE.md §4.

- 상세 배경은 [ROADMAP.md](../ROADMAP.md) Phase 2 참조.

### test_data 디렉토리 구조

- `test_data/` 디렉토리: 음성 파일(mp3/wav) + 선택적 정답 스크립트(txt)
- 파일명 규칙: 음성파일과 정답 스크립트 파일명 동일, 확장자만 다름 (예: `sbs1.mp3` ↔ `sbs1.txt`)
- 정답 스크립트가 없는 음성파일도 존재 가능
- **정답 스크립트 형식**: 빈 줄(`\n\n`)로 구분된 블록이 문장 분리 F1 경계가 된다. 경계 기준:
  1. **화자가 바뀌는 순간 = 빈 줄(1순위, 필수)** — 화자전환 경계는 반드시 빈 줄로 표기.
  2. **한 화자의 긴 발화 = 온점 기준 분리(2순위, 선택)** — 한 블록 ≤2문장 허용, 3문장+ 이상이면 분리.
  - 잠정: metric 구현 전까지 기존 동일가중 F1을 사용. 현재 .txt가 거의 화자턴 단위이므로 **동일가중 F1 ≈ 화자전환 F1**. 온점분리 블록이 늘어날 때부터 primary/secondary 분리 metric이 필요.
- **파일 목록** (측정 기본 설정: 화자분할 ON — 이 옵션 전체가 이제 `parse_args.py` 기본값이라 추가 인자 없이 `whisperlivekit-server`만 기동해도 동일 설정임):
  - `bong1.mp3` / `bong1.txt` — 봉준호 기생충 인터뷰. **영어 2명 + 한국어 2명**, 화자 교대·긴 발화 혼재. 다화자·온점분리 역량의 핵심 테스트 대상.
    **테스트(채택/기각) + 개선 최우선 대상**(다화자·긴 발화). 채택 확정 시 `--repeat 3` 루틴.
  - `ytn2.mp3` / `ytn2.txt` — SCM 회의 통역. 영어 발화자 발화 → 한국인 통역, **한 문장씩 화자 교대**(순차통역). EN↔KO 짧은 텀 교차.
    **테스트(채택/기각) + 개선 최우선 대상**(짧은 텀 코드스위칭). 채택 확정 시 `--repeat 3` 루틴.
  - `sbs1.mp3` / `sbs1.txt` — 뉴스 리포트. **대부분 한국어 → 중간 영어 인용 → 다시 한국어 종료**(사실상 단일 앵커, 언어 전환 경계). **테스트(채택/기각)**.
  - `ytn1.mp3` / `ytn1.txt` — SCM 회의 통역, ytn2 동일 이벤트 다른 구간. 영어 발화자+한국어 통역, 한 문장씩 화자 교대.
    **held-out**(ytn2 동일 이벤트 쌍둥이 — ytn2 개선이 미학습 데이터에 일반화되는지 코드스위칭 검증용).
  - `eng1.mp3` / `eng1.txt` — **단일 영어 발화자**만 말하는 상황. script-switch false split 감시용.
    **held-out**(영어 전용 회귀 감시).
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
