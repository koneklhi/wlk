# 번역 파이프라인 연결 — 중간(interim) 번역 추가 설계

작성일: 2026-07-12

## 배경

배포 PC에 번역 기능을 연결하는 작업. 사용자 요청은 다음 두 가지:
1. 문장이 확정된 시점에 그 문장을 번역해 원본 전사 아래 출력
2. 문장이 확정되기 전에도 중간중간 번역 결과를 보여줘 실시간으로 전사+번역이 진행 중임을 체감시킴

개발 PC는 배포용 LLM(gpt-oss-20b, llama.cpp)에 접근할 수 없으므로, 임시로 가벼운 로컬 LLM(Ollama)으로
UI 동작을 검증하고, 배포 시점엔 모델 설정만 바꿔 끼우는 방식을 원함.

## 조사 결과 — 기존 구현 현황

`whisperlivekit`에 whisperlive 이식 번역 파이프라인이 이미 상당 부분 구현되어 master에 머지되어 있다.

**이미 구현된 것 (변경 불필요):**
- `whisperlivekit/llm_translation/translator.py` — `TranslatorBase`/`OllamaTranslator`(dev, `/v1/chat/completions`)
  /`LlamaTranslator`(prod, `/v1/completions` + harmony 프롬프트, whisperlive_code와 동일 프로토콜)
  /`create_translator(serve, model_name, endpoint)` 팩토리. 번역 방향은 `get_to_lang()`이 자동 결정
  (`ko→en`, 그 외→`ko`).
- `whisperlivekit/llm_translation/manager.py` — `TranslationManager.apply_translations()`: 확정된
  세그먼트(`seg.finalized`)에 한해 캐시 히트 시 즉시 적용, 캐시 미스 시 `asyncio.ensure_future`로
  비차단 번역 태스크 생성(다음 스냅샷부터 반영).
- `whisperlivekit/audio_processor.py` L164-171(생성), L579-580(매 사이클 `apply_translations(lines)` 호출),
  L708-709(종료 시 `close()`) — 확정 문장 번역 파이프라인이 이미 배선됨.
- `config.py` L85-89 / `parse_args.py` L408-437 — `--llm-translation`, `--translation-serve`,
  `--translation-endpoint`, `--translation-model` 플래그. **dev 기본값이 이미 `ollama`/`http://localhost:11434`
  /`qwen2.5:7b`** — 이 PC에 Ollama 0.31.2 설치 및 `qwen2.5:7b`(4.7GB) pull 완료 확인됨.
- 배포 전환은 `docs/DEPLOYMENT_OFFLINE.md` §5에 이미 검증 완료로 문서화: `--translation-serve llama
  --translation-endpoint http://localhost:2010 --translation-model gpt-oss-20b`로 플래그만 교체.
  관련 차단 버그 2건(§5.2 config 필드 누락, §5.4 diarization 동시 사용 시 미확정 이슈)은 master에 수정 완료.
- `whisperlivekit/web/live_transcription.js` L470-488 — `lines[].translation`(확정 문장 번역)을
  원본 텍스트 아래 `label_translation` 블록으로 렌더링하는 코드 이미 존재.

**빠진 것 (이번 설계 대상):**
- 스키마상 최상위 `buffer_translation` 필드(진행중 미확정 번역)와 프론트 렌더링(L474-478,
  `.buffer_translation` 스타일)은 이미 존재하지만, 현재 이 필드는 whisperlivekit 상위 라이브러리 자체의
  **미완성 NLLB 번역 스텁**에만 연결되어 있다 (`--target-language` 플래그 help 문구에 "Not functional
  yet"로 명시, `core.py` `online_translation_factory`가 외부 `nllw` 패키지 필요, 기본 비활성).
  우리가 이식한 LLM 번역기(`TranslationManager`)는 확정 문장만 다루고 미확정 버퍼는 건드리지 않는다.
- whisperlive_code 원본에도 "중간중간 번역" 개념이 없었다(프론트가 완료 판단한 문장만 명시적으로
  `POST /api/translate` 요청). 따라서 interim 번역은 신규 설계.

## 아키텍처

### 데이터 흐름

**확정 문장 번역 (기존, 변경 없음)**
```
문장 확정 (tokens_alignment.py) → results_formatter()
  → llm_translation_manager.apply_translations(lines)
  → 캐시 히트: seg.translation 채움 / 캐시 미스: 비차단 태스크 생성
  → lines[].translation → 프론트 렌더링
```

**중간 번역 (신규)**
```
results_formatter() 매 사이클(~50ms)
  → buffer_transcription_text = 현재 미확정 버퍼 텍스트
  → llm_translation_manager.apply_interim_translation(buffer_transcription_text, src_lang)
  → buffer_translation 필드에 담아 FrontData로 전송
  → 프론트가 이미 렌더링 (live_transcription.js L474-478, 코드 변경 불필요)
```

### 컴포넌트 변경

**`whisperlivekit/llm_translation/manager.py` — `TranslationManager`에 메서드 추가**

```
apply_interim_translation(text: str, src_lang: str) -> str
```
- 내부 상태(인스턴스 변수): `_interim_source`(마지막 번역 요청한 버퍼 텍스트),
  `_interim_result`(마지막 완료된 번역 결과), `_interim_in_flight`(bool)
- `text`가 빈 문자열이면 즉시 `""` 반환 + 내부 상태 리셋 (문장이 막 확정되어 버퍼가 비워진 경우)
- `_interim_in_flight`가 `False`이고 `text != _interim_source`이면: 논블로킹 태스크로 번역 요청
  시작(`asyncio.ensure_future`), `_interim_in_flight = True`, `_interim_source = text`
- 항상 `_interim_result`(가장 최근에 완료된 번역 — 다소 오래된 버퍼 기준일 수 있음)를 그 자리에서 반환
- **스로틀 방식**: 고정 시간 간격이 아니라 "이전 요청이 끝날 때까지 다음 요청을 보내지 않는" self-throttle.
  LLM 응답 속도에 자연스럽게 맞춰짐(dev 환경 빠르면 자주 갱신, 배포 환경 느리면 드물게 갱신) — 임의의
  매직 넘버(예: "N초마다") 없이 in-flight 가드 하나로 구현.
- 확정 캐시(`apply_translations`의 `_cache`/`_in_flight`)와는 독립된 상태 — 서로 간섭하지 않음.
- 에러 처리는 기존 `_translate_and_cache`와 동일하게 예외를 로그만 남기고 삼킴(번역 실패가 전사 흐름을
  막지 않아야 함).

**`whisperlivekit/audio_processor.py` — `results_formatter()` (L558-609 부근) 훅 추가**

- 현재 `self.llm_translation_manager.apply_translations(lines)` 호출(L579-580) 다음에
  `state = await self.get_current_state()`(L581)로 `buffer_transcription_text`를 얻는 순서인데,
  interim 번역에도 이 값이 필요하므로 `get_current_state()` 호출을 `apply_translations` 호출보다
  앞으로 당긴다(로직 변경 없이 순서만 조정).
- `llm_translation_manager is not None`일 때: `src_lang = (state.buffer_transcription.detected_language
  if state.buffer_transcription else None) or "ko"`로 언어 결정 후 `apply_interim_translation()` 호출,
  결과를 `buffer_translation_text`에 대입해 기존 NLLB 경로(`get_lines()` 반환값)를 덮어씀.
- `llm_translation_manager is None`(번역 비활성)일 때는 기존 NLLB 경로 값을 그대로 사용 — 동작 변화 없음.

### 번역 방향

이미 구현되어 있음(`TranslatorBase.get_to_lang`): `ko → en`, 그 외(`en` 등) `→ ko`. `src_lang`은
세그먼트/버퍼의 `detected_language`를 그대로 사용 — 별도 작업 불필요.

### CLI 플래그

별도 on/off 플래그를 추가하지 않는다. `--llm-translation` 활성 시 확정 번역과 중간 번역이 함께 동작한다
(YAGNI — 운영상 분리 필요성이 실제로 확인되면 그때 `--llm-translation-interim` 플래그를 추가).

## 에러 처리

- Ollama/llama.cpp 서버가 응답하지 않거나 타임아웃/예외가 발생해도 `_translate_and_cache`와 동일한
  패턴으로 예외를 로그만 남기고 무시 — 전사 파이프라인 자체는 영향받지 않는다.
- 번역 결과가 빈 문자열이면 캐시/interim 상태에 반영하지 않는다(기존 `apply_translations`와 동일 정책).

## 검증 계획

- 실행: `whisperlivekit-server --llm-translation` (나머지 dev 기본값 그대로 = Ollama + qwen2.5:7b)
- **경로 B(마이크, 내장 웹 UI)**로 정성 확인. 번역에는 WER/F1 같은 정량 지표가 없으므로 경로 C(VBCable)
  측정은 불필요 — "화면에 번역이 뜨는지"를 눈으로 보는 스모크 테스트.
- 확인 항목:
  1. 문장 확정 시 그 아래에 번역이 표시되는가
  2. 확정 전에도 중간 번역이 몇 초 간격으로 갱신되며 표시되는가
  3. 화자분할(`--diarization`) 동시 ON 시에도 정상 동작하는가(§5.4 기존 한계 — 화자전환 시점에만
     확정되는 특성은 유지됨, 이번 변경으로 악화되지 않아야 함)
  4. 한→영, 영→한 양방향 모두 자연스럽게 동작하는가

## 문서 갱신 (코드 변경과 동일 작업 단위)

- `docs/SCHEMA_CHANGES.md` (L50 부근) — `buffer_translation` 출처를 "NLLB 스텁(비활성)"에서
  "LLM 번역기가 채우는 진행중 번역(확정 문장 없을 때)"으로 정정
- `docs/FRONTEND_HANDOFF.md` (L101, L234) — 위와 동일하게 출처 설명 정정
- `docs/DEPLOYMENT_OFFLINE.md` §5 — interim 번역도 동일 `TranslationManager`로 동작함을 1줄 추가

## 범위 밖 (이번 작업에서 다루지 않음)

- NLLB 기반 번역 경로(`--target-language`, `nllw` 패키지) — 상위 라이브러리 미완성 스텁, 이번 작업과
  무관하게 그대로 둔다.
- 번역 Glossary 동적 관리(`/api/prompts/*`) — `docs/SCHEMA_CHANGES.md`에 Phase 5로 연기 명시됨.
- 배포 PC에서의 실제 gpt-oss-20b 대상 재검증 — 이번 설계는 dev PC 코드 변경 + dev 검증까지이며,
  배포 PC 재검증은 별도로 진행.
