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

## 기존 whisperlive 코드 (비교 참고 전용)

[whisperlive_code/](../whisperlive_code/) — 기존 `whisperlive` 시스템에서 우리 요구사항용으로 수정했던 주요 코드.
**성능·기법 비교용 참고 자료**일 뿐, 이식은 완료됐고 신규 이식 대상이 아니다([CLAUDE.md](../CLAUDE.md) §1 참조).

- **[docs/LEGACY_WHISPERLIVE_READING_GUIDE.md](LEGACY_WHISPERLIVE_READING_GUIDE.md) — 읽는 순서·초점 가이드
  (인수인계용). 3프로세스 구조 → 슬라이딩 재디코딩 → 확정 4갈래 → 번역까지 데이터 흐름 + 현행 대조표. 코드 분석 전에 먼저 읽는다**
- [whisperlive_code/server.py](../whisperlive_code/server.py), [whisperlive_code/app.py](../whisperlive_code/app.py),
  [whisperlive_code/main.py](../whisperlive_code/main.py) — 서버/엔트리 구조 참고
- [whisperlive_code/transcriber.py](../whisperlive_code/transcriber.py), [whisperlive_code/client.py](../whisperlive_code/client.py)
  — 전사·클라이언트 흐름 참고 (임시방편 로직은 이식하지 않았음)
- [whisperlive_code/filtering____init__.py](../whisperlive_code/filtering____init__.py),
  [whisperlive_code/manager.py](../whisperlive_code/manager.py) — 필터링·Glossary 참고(현재 구현 = `whisperlivekit/filtering/`)
- [whisperlive_code/translator.py](../whisperlive_code/translator.py),
  [whisperlive_code/prompt_manager.py](../whisperlive_code/prompt_manager.py) — 번역 파이프라인 참고(현재 구현 = `whisperlivekit/llm_translation/`)

## Phase 2 — 문장 확정 / 스트리밍 디코더 (STT 품질 개선 작업 영역)

- [whisperlivekit/tokens_alignment.py](../whisperlivekit/tokens_alignment.py) — 문장 확정 + 토큰 정렬 (`get_lines`, `get_lines_diarization`)
- [whisperlivekit/simul_whisper/simul_whisper.py](../whisperlivekit/simul_whisper/simul_whisper.py) — SimulStreaming 핵심 디코더 (`_filter_repetitions` 등)
- [whisperlivekit/simul_whisper/backend.py](../whisperlivekit/simul_whisper/backend.py) — SimulStreaming 온라인 프로세서 (`new_speaker` 등)
- [whisperlivekit/silero_vad_iterator.py](../whisperlivekit/silero_vad_iterator.py) — VAD silence 감지
- [whisperlivekit/timed_objects.py](../whisperlivekit/timed_objects.py) — `ASRToken` / `Silence` / `Segment`(`to_dict` 직렬화)

## Phase 3 — 필터링 / 단어 교정 (완료, [CLAUDE.md](../CLAUDE.md) §3.5/§3.6)

- [whisperlivekit/filtering/__init__.py](../whisperlivekit/filtering/__init__.py) — 환각 문장·단어 제거 로직
- [whisperlivekit/filtering/manager.py](../whisperlivekit/filtering/manager.py) — `WordCorrectionManager` (단어 교정 사전, SQLite 동적 갱신)
- [whisperlivekit/filtering/hallucination.json](../whisperlivekit/filtering/hallucination.json),
  [whisperlivekit/filtering/admin_replacement.json](../whisperlivekit/filtering/admin_replacement.json) — 기본 사전

## Phase 4 — 번역 파이프라인 (완료, [CLAUDE.md](../CLAUDE.md) §3.4)

- [whisperlivekit/llm_translation/translator.py](../whisperlivekit/llm_translation/translator.py) — `LlamaTranslator` / `OllamaTranslator` (서빙 도구 분기)
- [whisperlivekit/llm_translation/manager.py](../whisperlivekit/llm_translation/manager.py) — `TranslationManager` (확정 세그먼트 비차단 번역 캐시)

## 문서 색인

- [docs/MASTER_CHANGES.md](MASTER_CHANGES.md) — master 최종본 upstream 대비 전체 변경 요약 + 향후 개선 (채택 실험 증류본)
- [docs/SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) — React 메시지 스키마 변경 이력
- [docs/API_SPEC.md](API_SPEC.md) — React가 실제 사용하는 WebSocket `/asr` + REST 엔드포인트 정식 명세 (최신 정본)
- [docs/DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md) — 폐쇄망 오프라인 반입·서버 기동(venv 없이 `C:\Python312` 직접 설치, DLP 회피)·경로 C 자동/경로 B 테스트 + 단어집·번역(기본 ON) 배포 설정 §5
- [docs/OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) — 설계 결정 이력 (대부분 해소 — 정본 문서 링크)
- [docs/TESTING.md](TESTING.md) — 실행 명령어·검증 순서·test_data 구조
- [docs/TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md) — 전사 요구사항·2지표(화자분리/문장분리 F1) 측정 정본
- [docs/SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) — 문장 확정 알고리즘·경계 신호 상세
- [docs/OPERATOR_TUNING_GUIDE.md](OPERATOR_TUNING_GUIDE.md) — 배포 상황별(`--scenario`) 파라미터 튜닝 가이드
- [frontend/app/README.md](../frontend/app/README.md) — 배포 UI(React) 구조·기능 지침

**유형별 하위 디렉토리** (필수 참조 문서가 아닌 일회성 산출물 — 신규 문서도 이 규칙을 따른다):
- [docs/research/](research/) — 리서치·설계 조사 결과물(예: [DIARIZATION_SPIKE.md](research/DIARIZATION_SPIKE.md), [CODESWITCH_REALTIME_DESIGN.md](research/CODESWITCH_REALTIME_DESIGN.md), [PHASE3_TRANSLATION_RESEARCH.md](research/PHASE3_TRANSLATION_RESEARCH.md), [PHASE3_WORD_REPLACEMENT_RESEARCH.md](research/PHASE3_WORD_REPLACEMENT_RESEARCH.md))
- [docs/goal_prompt/](goal_prompt/) — 자율 루프 goal 프롬프트(완료된 것은 [docs/archive/](archive/)로 이동)
- [docs/backlog/](backlog/) — 개선 백로그(예: [BACKLOG_CODESWITCH_FOLLOWUP.md](backlog/BACKLOG_CODESWITCH_FOLLOWUP.md))

## eval 하니스 (경로 C 정량 측정)

- [scripts/eval.py](../scripts/eval.py) — 경로 C/A 측정, WER + 화자분리 F1 + 문장분리 F1 2지표 산출 (`--repeat`, `--paths`, `--browser-ui`)
- [scripts/vbcable_test.py](../scripts/vbcable_test.py) — VBCable 브라우저 자동화. 기본은 **배포 UI**(`/wlkies/`,
  `data-testid` 계약), `--ui inline`으로 내장 UI(`/dev`) 대조군. 하니스 고장은 `HarnessError`로 즉시 중단
- [scripts/audio_device.py](../scripts/audio_device.py) — VBCable 장치 자동 설정/복원

## 폐쇄망 배포 진단 (배포 PC에서 실행, 읽기 전용)

- [scripts/verify_deploy_tree.py](../scripts/verify_deploy_tree.py) — 배포 PC의 실행 중인 소스 트리를
  `deploy/deploy_source.zip`과 대조해 `STALE`/`MISSING` 파일을 찾는다. 증분 반입 배치를 한 번 놓치면 그
  파일이 영구히 구세대로 남는 사고([DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md) §8)를 잡는 유일한 수단
- [scripts/diagnose_translation.py](../scripts/diagnose_translation.py) — 번역 결과가 빈 문자열이 되는
  단계를 찾는다. 프로덕션과 동일한 요청을 보내고 **후처리 이전의 원본 LLM 응답**을 찍은 뒤 `<` 절단 ·
  `_sanitize_result`를 단계별로 적용해 어디서 비는지 보여준다
