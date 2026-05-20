# CLAUDE.md

이 파일은 본 저장소(WhisperLiveKit 기반 실시간 STT 통역 시스템)에서 Claude Code가 작업할 때 참조할 프로젝트 가이드이다. 모든 응답과 산출물은 **한국어**로 작성한다.

---

## 1. 프로젝트 정체성

- **목적**: 기존 `whisperlive` 라이브러리 기반 실시간 STT 통역 시스템을, `whisperlivekit` 라이브러리 기반으로 새로 개발한다.
- **현 단계**: ROADMAP Phase 1 완료 (기본 STT 전사 동작 확인). Phase 2(문장 단위 확정 로직) 진입 직전.
- **상위 라이브러리**: `whisperlivekit` 패키지 본체가 이 저장소에 포함되어 있다. 우리 시스템은 이 위에 얹혀 동작한다.
- **기존 `whisperlive` 코드 참조 디렉터리**: [whisperlive_code/](whisperlive_code/)
  - 공식 `whisperlive` GitHub 코드를 기반으로 우리 요구사항에 맞게 수정했던 **주요 파일들**이 들어 있다.
  - **기본 용도**: 요구사항을 이해하기 위한 참고 자료. 임시방편 로직(같은 문장 N회 반복 시 확정, 타임스탬프 변화량 임계치 등)은 **그대로 이식하지 않는다**.
  - **예외 — 그대로 이식하는 영역**: §3.4 번역 파이프라인, §3.5 필터링/단어 교정, §3.6 Glossary 동적 관리, 그리고 ROADMAP Phase 4(React UI 연결 + 번역 통합) 부분은 `whisperlive_code/`의 코드·로직을 **그대로 사용**한다.

## 2. 환경

### 2.1 개발 / 테스트 환경 (현재 작업 환경)
- Windows PC, **RTX 3080**, 인터넷 연결 가능
- VS Code IDE에서 클로드 코드를 통해 개발/테스트
- **테스트 입력 경로 — 두 가지 방식 병렬 운영**

**경로 A — 파일 기반 (정량적, 기존 방식)**
  - WhisperLiveKit 내장 헤드리스 클라이언트 [whisperlivekit/test_client.py](whisperlivekit/test_client.py)로 **`test_data/` 내 로컬 mp3/wav 파일을 WebSocket `/asr`에 직접 송신**한다.
  - **가상 오디오 케이블(VB-Cable, VoiceMeeter 등)에 의존하지 않는다.** 사운드 카드/드라이버 설치도 불필요.
  - 의존성: 시스템 `ffmpeg` 설치 필수 (파일을 PCM s16le 16kHz mono로 변환).
  - 서버는 `--pcm-input` 플래그로 기동 → 클라이언트가 PCM 청크를 직접 송신.
  - 실행 예:
    - 서버 기동: `whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --lan auto --pcm-input --warmup-file test_data/sbs1_10s.mp3`
      (스트리밍 정책 `--backend-policy`는 Phase 2 설계 세션에서 결정. 선택지: `simulstreaming`(WLK 기본값) / `localagreement`)
    - 파일 송신: `python -m whisperlivekit.test_client test_data/sbs1.mp3 --live`
    - Windows PowerShell에서 한국어 출력 깨짐 방지: `$env:PYTHONIOENCODING = "utf-8"` 선행 실행 필요
  - 옵션: `--speed 1.0`(실시간) / `--speed 0`(가능한 한 빠르게), `--language ko`/`--language en` 강제, `--live`로 비확정/확정 진행 출력, `--json`으로 원본 응답 로깅.

**경로 B — 마이크 직접 녹음 (정성적, 신규)**
  - 서버를 `--pcm-input` 플래그 없이 기동 → 브라우저가 `MediaRecorder` 방식으로 마이크 음성을 실시간 캡처
  - 브라우저에서 `http://localhost:8000/` 접속 → 내장 웹 UI ([whisperlivekit/web/live_transcription.html](whisperlivekit/web/live_transcription.html))에서 마이크 직접 녹음
  - 마이크에 직접 말하면서 전사 결과를 실시간 확인 (정성적 평가)
  - 서버 기동 예: `whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --lan auto --warmup-file test_data/sbs1_10s.mp3`
    (스트리밍 정책 플래그는 Phase 2 설계 세션 이후 확정)
  - 목적: 파일 기반 정량 평가와 함께, 실제 마이크 입력에 대한 정성적 평가 병행

**test_data 디렉토리 구조**
  - `test_data/` 디렉토리: 음성 파일(mp3/wav) + 선택적 정답 스크립트(txt)
  - 파일명 규칙: 음성파일과 정답 스크립트 파일명 동일, 확장자만 다름 (예: `sbs1.mp3` ↔ `sbs1.txt`)
  - 정답 스크립트가 없는 음성파일도 존재 가능
  - 현재: `sbs1.mp3` (음성), `sbs1.txt` (정답 스크립트)
  - 용도: 향후 음성파일 기반 STT 성능 분석 시 활용
- **STT 동작 확인용 UI 선택지** (필요에 따라 선택):
  - **터미널**: `test_client.py --live` 또는 `--json` 출력으로 `lines[]`(확정) + `buffer_transcription`(비확정) 흐름까지 확인 가능. 백엔드 로그/print 병행. (경로 A 파일 기반 테스트용)
  - **WhisperLiveKit 내장 웹 UI** ([whisperlivekit/web/live_transcription.html](whisperlivekit/web/live_transcription.html) + `live_transcription.js`, `live_transcription.css`, 서버 실행 시 `GET /`에서 자동 서빙됨): 서버 기동 후 브라우저에서 접속하면 마이크 캡처 및 실시간 전사 결과를 UI상에서 시각적으로 확인 가능. (경로 B 마이크 직접 녹음 테스트용)
  - **기존 React 웹 UI**: 번역(llama) 파이프라인까지 묶어 최종 검증할 때 연결.
- **검증 순서 (권장)**:
  1. `test_client.py`로 mp3/wav 송신 (경로 A) → 터미널에서 번역 제외, 실시간 STT 전사 동작 확인 (정량 평가)
  2. 서버 기동 후 브라우저 + 마이크 직접 녹음 (경로 B) → 내장 웹 UI에서 실시간 전사 결과 시각 확인 (정성 평가)
  3. `test_client.py --live` 터미널 출력으로 확정/비확정 플래그 + 언어 전환 동작 확인
  4. 기존 React 웹 UI 연결 후 번역 + 최종 UI 표출까지 확인

### 2.2 배포 환경
- **폐쇄망** Windows PC, **RTX 5090**, 외부 인터넷 차단
- 실제 마이크 입력 사용
- 모든 모델·라이브러리는 **오프라인 / 로컬 경로 기반**으로 동작해야 한다. 런타임에 HuggingFace Hub, PyPI, GitHub 등에 접속하면 안 된다.

### 2.3 모델
- **STT**: `whisper-large-v3-turbo` — 로컬 경로: [whisperlivekit/model/whisper-large-v3-turbo/](whisperlivekit/model/whisper-large-v3-turbo/)
- **번역**: 기존 `whisperlive`에서 쓰던 **OSS 20B LLM** 그대로 사용.

## 3. 핵심 설계 제약

### 3.1 마이크 캡처 위치
- 배포 환경(폐쇄망)에서는 `whisperlivekit` 기본 구현(브라우저 `getUserMedia` → WebSocket `/asr`)을 그대로 사용한다.
- 개발/테스트 환경에서는 마이크 캡처를 우회하고 `test_client.py`로 파일을 직접 송신한다 (§2.1 참조). 백엔드 코드는 두 경로에서 동일하게 동작해야 한다.

### 3.2 언어 강제
- **한국어 / 영어 두 언어만** 강제로 들어오는 환경. 두 언어 인식률 극대화가 목표.
- **Code-Switching**(한 발화 안에 한·영 혼용) 상황에서 단어 유실 / 환각 / 문장 조기 확정이 발생하지 않도록 주의해 설계한다.

### 3.3 문장 단위 출력 — 백엔드 책임 범위

#### 3.3.1 책임 분리
- **백엔드(우리 작업)가 하는 일**:
  1. 한 문장이 끝났는지 판단 — 확정/비확정 상태 결정
  2. 위 결과를 React UI에 메시지로 전달
- **React 측에 이미 구현·완성된 부분** (백엔드가 손대지 않음):
  - 확정/비확정에 따른 색상 변경 (옅은 회색 ↔ 일반 색상)
  - 문장 종료 시 새 단락 줄바꿈
  - 화면 레이아웃·렌더링 일반

#### 3.3.2 React에 보내는 메시지 스키마 — 본격 통합 시점에 결정
- **현 단계에서는 스키마 형태를 못박지 않는다.**
- 의미상 가져갈 가능성이 높은 필드 (기존 `whisperlive` 기준): `text`(원본 메시지), `start` / `end`(타임스탬프), `completed`(확정/비확정 플래그), `lang`(언어 정보) 등.
- `whisperlivekit` 기본 출력은 `lines[]` + `buffer_transcription` / `buffer_diarization` / `buffer_translation` 형태로 다르다. 이에 맞춰 **새 스키마로 최적화하고 React 구조도 함께 변경할 수 있다**.
- 따라서 메시지 스키마의 최종 형태와 React 측 변경 범위는 **ROADMAP Phase 4(React UI 연결 + 번역 통합) 진입 직전에 사용자와 의논해 결정**한다. 자세한 미정 사항은 §7 참조.

#### 3.3.3 문장 확정 판단 알고리즘 (구체는 §7에서 결정)
- 기존 `whisperlive`의 임시방편(같은 문장 N회 반복 시 확정, 타임스탬프 변화량 임계치 등)은 **그대로 이식하지 않는다**.
- 활용 가능 신호 및 정책 예시 (아래는 참고 예시이며, 이 목록에 한정하지 않는다):
  - 스트리밍 정책: SimulStreaming(AlignAtt + CIF 기반 단어 끝 감지, WLK 기본값), LocalAgreement(가설 비교 기반 토큰 안정화)
  - 확정 신호: Whisper segment 경계, `no_speech_prob`, VAD 무음 구간, 구두점, 언어 전환 경계 등
  - 정책과 신호의 조합 방식은 설계 세션에서 비교 후 결정한다.
- 후보 비교 후 본격 개발 시점에 사용자와 합의해 확정 — §7 1번 항목 참조.

### 3.4 번역 트리거
- 문장이 **확정된 시점**에 번역 수행 → UI 출력.
- 번역 파이프라인(LLM, 프롬프트, 번역기 모듈)은 **기존 `whisperlive` 구조를 그대로 사용**한다.
- 참조 파일: [whisperlive_code/translator.py](whisperlive_code/translator.py), [whisperlive_code/prompt_manager.py](whisperlive_code/prompt_manager.py) — **코드/로직 그대로 이식**, 임의 개선 금지.

### 3.5 필터링 / 단어 교정
- 환각 문장·단어 제거 + 사전 기반 단어 대치를 전사 직후 수행.
- 이 로직은 기존 `whisperlive`의 [whisperlive_code/filtering____init__.py](whisperlive_code/filtering____init__.py), [whisperlive_code/manager.py](whisperlive_code/manager.py) 내용을 **그대로 새 시스템에 적용**한다. **코드/로직 그대로 이식**, 임의 개선 금지.

### 3.6 Glossary / 사전 동적 관리
- 운용 중 단어 교정 사전 + 번역 glossary를 **동적으로 추가/삭제** 가능해야 함.
- 인터페이스·구현은 기존 `whisperlive` 구조 그대로 — [whisperlive_code/manager.py](whisperlive_code/manager.py) 기준 코드/로직 그대로 이식.
- 사전 갱신은 **즉시 반영** — 다음 전사/번역부터 새 사전 적용.

### 3.7 React UI 재사용 정책
- **React UI는 기본적으로 그대로 재사용을 우선한다.** 추가 기능은 가능한 한 **백엔드 측에서 구현**하되, 메시지 스키마 최적화 등을 위해 React 측 변경이 필요한 경우는 §7에서 의논해 결정한다.

## 4. 구현 우선순위

세부 Phase 정의·태스크·완료 기준은 [ROADMAP.md](ROADMAP.md) 참조.
본 문서는 변하지 않는 설계 제약·운영 규칙만 다룬다.

## 5. 코드 스타일 / 운영 규칙

### 5.1 언어
- 코드 식별자·주석을 제외한 모든 사용자 응답·문서·커밋 메시지는 **한국어**.
- 기존 `whisperlivekit` 코드의 영어 식별자/주석은 보존.

### 5.2 Python
- `pyproject.toml` 기준: Python `>=3.11, <3.14`, FastAPI 기반.
- 린트: `ruff check` (line-length 120, target `py311`).
- 테스트: `pytest` (`tests/` 디렉터리).
- 패키지 매니저: `uv` 사용 (`uv.lock` 존재).

### 5.3 변경 범위
- 요구사항에 명시되지 않은 리팩터링·추상화·"미래 확장 대비" 코드는 추가하지 않는다.
- `whisperlivekit/` 본체 코드는 **필요한 최소 범위만** 수정. 가능하면 새 모듈로 분리해 얹는 방식을 우선한다.
- [whisperlive_code/](whisperlive_code/)에서 그대로 가져오는 모듈(`filtering____init__.py`, `manager.py`, `translator.py`, `prompt_manager.py`, React UI 연결부 등)은 **이식 시 임의 개선 금지** — 동작 동일성을 우선.

### 5.4 폐쇄망 호환성
- 새로 추가하는 코드는 **런타임 네트워크 호출 금지** (HF Hub auto-download, requests to github.com 등).
- 모델 경로는 로컬 파일/디렉터리를 명시적으로 받도록 설계 (예: `--model-path` 패턴).

### 5.5 계획 이탈 방지
- 구현 중 승인된 계획과 다른 방향이 필요해지면 **즉시 멈추고** 사용자에게 상황을 보고한 뒤 재승인을 받는다.
- 임의 판단으로 계획을 벗어난 구현을 진행하지 않는다.

## 6. 작업 시 우선 참조 파일

- [pyproject.toml](pyproject.toml) — 의존성, 스크립트 엔트리, 린트 설정
- [whisperlivekit/basic_server.py](whisperlivekit/basic_server.py) — FastAPI 서버 진입점, WebSocket `/asr` 엔드포인트
- [whisperlivekit/audio_processor.py](whisperlivekit/audio_processor.py) — 오디오 처리 파이프라인 핵심
- [whisperlivekit/core.py](whisperlivekit/core.py) — `TranscriptionEngine` 등 핵심 객체
- [whisperlivekit/parse_args.py](whisperlivekit/parse_args.py) — CLI 인자 정의
- [whisperlivekit/model/whisper-large-v3-turbo/](whisperlivekit/model/whisper-large-v3-turbo/) — STT 로컬 모델 디렉터리 (`config.json` / `model.safetensors` / `tokenizer.json` 등)
- [0.Metafile/WLK_README.md](0.Metafile/WLK_README.md) — 상위 라이브러리(WhisperLiveKit) README
- [0.Metafile/WLK_INTERNALS.md](0.Metafile/WLK_INTERNALS.md) — 내부 구조 메모
- [whisperlive_code/](whisperlive_code/) — 기존 `whisperlive` 시스템에서 우리 요구사항용으로 수정했던 주요 코드. **요구사항 이해용** + §3.4 / §3.5 / §3.6 / React UI 연결부는 **그대로 이식**.
  - [whisperlive_code/server.py](whisperlive_code/server.py), [whisperlive_code/app.py](whisperlive_code/app.py), [whisperlive_code/main.py](whisperlive_code/main.py) — 서버/엔트리 구조 참고
  - [whisperlive_code/transcriber.py](whisperlive_code/transcriber.py), [whisperlive_code/client.py](whisperlive_code/client.py) — 전사·클라이언트 흐름 참고 (임시방편 로직은 이식하지 않음)
  - [whisperlive_code/filtering____init__.py](whisperlive_code/filtering____init__.py), [whisperlive_code/manager.py](whisperlive_code/manager.py) — 필터링·Glossary 그대로 이식
  - [whisperlive_code/translator.py](whisperlive_code/translator.py), [whisperlive_code/prompt_manager.py](whisperlive_code/prompt_manager.py) — 번역 파이프라인 그대로 이식

## 7. 미정 사항 — 구현 직전에 사용자와 합의

- 문장 단위 확정 알고리즘의 구체 설계 (후보 비교 후 결정)
- 한·영 Code-Switching 검출 방식과 문장 분할 트리거
- **React에 보내는 메시지 스키마의 최종 형태 + React UI 변경 범위**
  - 후보 A: 기존 `whisperlive`의 세그먼트 스키마(`{text, start, end, completed, lang, …}`)를 가져가고 백엔드에서 `whisperlivekit` 출력을 그에 맞춰 변환
  - 후보 B: `whisperlivekit` 출력에 맞춰 새 스키마를 정의하고 React UI를 그에 맞게 변경
  - STT 핵심 기능(ROADMAP Phase 1~3) 구현 완료 후, React UI 연결 단계(ROADMAP Phase 4) 진입 직전에 의논해 결정
- 폐쇄망용 모델 디렉터리 레이아웃과 배포 패키징 형태
