# 작업 시 우선 참조 파일 색인

본 문서는 [CLAUDE.md](../CLAUDE.md)에서 분리한 **파일 경로 색인**이다. 작업 대상을 빠르게 찾을 때 참조한다.

## whisperlivekit 본체

- [pyproject.toml](../pyproject.toml) — 의존성, 스크립트 엔트리, 린트 설정
- [whisperlivekit/basic_server.py](../whisperlivekit/basic_server.py) — FastAPI 서버 진입점, WebSocket `/asr` 엔드포인트
- [whisperlivekit/audio_processor.py](../whisperlivekit/audio_processor.py) — 오디오 처리 파이프라인 핵심
- [whisperlivekit/core.py](../whisperlivekit/core.py) — `TranscriptionEngine` 등 핵심 객체
- [whisperlivekit/parse_args.py](../whisperlivekit/parse_args.py) — CLI 인자 정의
- [whisperlivekit/model/whisper-large-v3-turbo/](../whisperlivekit/model/whisper-large-v3-turbo/) — STT 로컬 모델 디렉터리

## 상위 라이브러리 메모

- [0.Metafile/WLK_README.md](../0.Metafile/WLK_README.md) — 상위 라이브러리(WhisperLiveKit) README
- [0.Metafile/WLK_INTERNALS.md](../0.Metafile/WLK_INTERNALS.md) — 내부 구조 메모

## 기존 whisperlive 코드 (참조 + 일부 그대로 이식)

[whisperlive_code/](../whisperlive_code/) — 기존 `whisperlive` 시스템에서 우리 요구사항용으로 수정했던 주요 코드.
**요구사항 이해용**이며, §3.4 / §3.5 / §3.6 / React UI 연결부는 **그대로 이식**한다 ([CLAUDE.md](../CLAUDE.md) §3 참조).

- [whisperlive_code/server.py](../whisperlive_code/server.py), [whisperlive_code/app.py](../whisperlive_code/app.py),
  [whisperlive_code/main.py](../whisperlive_code/main.py) — 서버/엔트리 구조 참고
- [whisperlive_code/transcriber.py](../whisperlive_code/transcriber.py), [whisperlive_code/client.py](../whisperlive_code/client.py)
  — 전사·클라이언트 흐름 참고 (임시방편 로직은 이식하지 않음)
- [whisperlive_code/filtering____init__.py](../whisperlive_code/filtering____init__.py),
  [whisperlive_code/manager.py](../whisperlive_code/manager.py) — 필터링·Glossary 그대로 이식
- [whisperlive_code/translator.py](../whisperlive_code/translator.py),
  [whisperlive_code/prompt_manager.py](../whisperlive_code/prompt_manager.py) — 번역 파이프라인 그대로 이식

## Phase 2 — 문장 확정 / 스트리밍 디코더 (STT 품질 개선 작업 영역)

- [whisperlivekit/tokens_alignment.py](../whisperlivekit/tokens_alignment.py) — 문장 확정 + 토큰 정렬 (`get_lines`, `get_lines_diarization`)
- [whisperlivekit/simul_whisper/simul_whisper.py](../whisperlivekit/simul_whisper/simul_whisper.py) — SimulStreaming 핵심 디코더 (`_filter_repetitions` 등)
- [whisperlivekit/simul_whisper/backend.py](../whisperlivekit/simul_whisper/backend.py) — SimulStreaming 온라인 프로세서 (`new_speaker` 등)
- [whisperlivekit/silero_vad_iterator.py](../whisperlivekit/silero_vad_iterator.py) — VAD silence 감지
- [whisperlivekit/timed_objects.py](../whisperlivekit/timed_objects.py) — `ASRToken` / `Silence` / `Segment`(`to_dict` 직렬화)

## Phase 3 — 필터링 / 단어 교정 (그대로 이식, [CLAUDE.md](../CLAUDE.md) §3.5/§3.6)

- [whisperlivekit/filtering/__init__.py](../whisperlivekit/filtering/__init__.py) — 환각 문장·단어 제거 로직
- [whisperlivekit/filtering/manager.py](../whisperlivekit/filtering/manager.py) — `WordCorrectionManager` (단어 교정 사전, SQLite 동적 갱신)
- [whisperlivekit/filtering/hallucination.json](../whisperlivekit/filtering/hallucination.json),
  [whisperlivekit/filtering/admin_replacement.json](../whisperlivekit/filtering/admin_replacement.json) — 기본 사전

## Phase 4 — 번역 파이프라인 (그대로 이식, [CLAUDE.md](../CLAUDE.md) §3.4)

- [whisperlivekit/llm_translation/translator.py](../whisperlivekit/llm_translation/translator.py) — `LlamaTranslator` / `OllamaTranslator` (서빙 도구 분기)
- [whisperlivekit/llm_translation/manager.py](../whisperlivekit/llm_translation/manager.py) — `TranslationManager` (확정 세그먼트 비차단 번역 캐시)

## eval 하니스 (경로 C 정량 측정)

- [scripts/eval.py](../scripts/eval.py) — 경로 C/A 측정, WER + 문장 분리 F1 산출 (`--repeat`, `--paths`)
- [scripts/vbcable_test.py](../scripts/vbcable_test.py) — VBCable 브라우저 자동화
- [scripts/audio_device.py](../scripts/audio_device.py) — VBCable 장치 자동 설정/복원
