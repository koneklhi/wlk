# 번역 Glossary 이식 설계 (Stage 1: glossary_block + sentence_block)

- 작성일: 2026-07-16
- 관련 ROADMAP 항목: Phase 5-2 (번역 Glossary 동적 추가/삭제 기능 이식)
- 관련 레퍼런스: `whisperlive_code/prompt_manager.py`, `whisperlive_code/translator.py`, `whisperlive_code/app.py`

## 1. 배경 및 목표

Phase 3에서 STT 단어 교정(`WordCorrectionManager`)은 이미 이식·연결 완료됐다(`whisperlivekit/filtering/`).
Phase 5는 그 **번역판**이다 — 운용 중 번역 용어집(예: `공군:ROKAF`)을 동적으로 추가/삭제하면
**다음 번역부터 즉시** 반영되도록 한다.

wl(whisperlive)에서는 이 기능이 `TranslationPromptManager`로 구현돼 있었고, glossary(용어집) +
sentence_block(few-shot 예시) + Qdrant 벡터 RAG(유사 예시 검색) 3계층으로 구성돼 있었다.
이 스펙은 **Stage 1(glossary_block + sentence_block)만** 다룬다. Stage 2(Qdrant RAG)는
§8에 확장 지점만 남기고 별도 스펙으로 분리한다(사유는 §2 참조).

**중요 전제**: glossary DB(`user_translation_glossary.db`), 실제 용어집 JSON, Qdrant 로컬 DB,
bge-m3 임베딩 모델 — 이 실제 자산 파일들은 전부 **폐쇄망 배포 PC에만 존재**하며 이 dev 저장소
안에는 없다. 이번 작업은 새 데이터를 만드는 게 아니라, **배포 PC의 기존 파일을 그대로 가져와
꽂을 수 있는 코드 연결부**를 만드는 것이다. dev 환경에서는 빈 placeholder로 검증하고, 배포 시
사용자가 실제 파일로 교체한다.

## 2. 범위 및 단계 분리

| | Stage 1 (이 스펙) | Stage 2 (별도 스펙) |
|---|---|---|
| 기능 | glossary_block, sentence_block | Qdrant 벡터 RAG(유사 예시 검색) |
| 신규 의존성 | 없음 | `qdrant-client`, `sentence-transformers` |
| 라이브러리 스택 | — | langchain 래퍼 대신 **직접 `qdrant-client` + `sentence-transformers`** (bge-m3는 sentence-transformers로 직접 로드, Qdrant는 `QdrantClient(path=...)` 로컬 임베디드 모드로 langchain vectorstore 래퍼 없이 직접 `search()` 호출) |
| pyproject.toml | 변경 없음 | 신규 extra 추가 필요 |
| 배포 데이터 | JSON(dict) + SQLite 1개 | + Qdrant 로컬 DB 디렉터리 + bge-m3 모델 디렉터리 |

분리 사유: Stage 1은 신규 의존성이 없어 지금 바로 구현·테스트·머지 가능한 반면, Stage 2는 새
의존성 추가로 폐쇄망 wheelhouse 패키징 영향이 있어(§6 문서 갱신 대상) 별도로 검토·리뷰하는 게
안전하다(외과적 변경 원칙).

## 3. 데이터 레이아웃

`whisperlivekit/filtering/`과 동일한 콜로케이션 패턴을 따른다 — 코드와 데이터를 같은 모듈 디렉터리에 둔다.

```
whisperlivekit/llm_translation/
├── __init__.py                        (신규 — get_prompt_manager() 싱글턴 팩토리)
├── prompt_manager.py                  (신규 — TranslationPromptManager)
├── translator.py                      (기존 — build_system_blocks() 추가)
├── manager.py                         (기존 — TranslationManager, 변경 없음)
├── admin_translation_glossary.json    (신규, git-tracked — 개발자 기본 용어집. dev 기본값 = `{}`)
└── user_translation_glossary.db       (신규, gitignore 대상 — SQLite, _init_db()가 빈 스키마 자동 생성)
```

- `admin_translation_glossary.json`은 **dict 포맷** `{origin: translation}` (주의: `filtering/admin_replacement.json`은
  `[{origin, replaced}, ...]` 리스트 포맷이라 다름 — 서로 다른 매니저의 서로 다른 스키마이므로 혼동 금지).
- `user_translation_glossary.db`의 `prompt_settings` 테이블은 `glossary_block`/`sentence_block` 두 키를
  JSON 문자열로 저장하는 **단일 DB**다(용어집·예시문이 별도 DB가 아님).
- git 추적 정책은 `filtering/`과 동일하게: JSON 시드 파일은 커밋(`git ls-files` 확인됨), `*.db`는
  `.gitignore`에 `whisperlivekit/llm_translation/*.db` 한 줄 추가(기존 167번 줄 `filtering/*.db` 패턴과 동일).
- 배포 시 사용자가 배포 PC의 실제 두 파일을 이 경로에 덮어쓰면 코드 변경 없이 바로 활성화된다.

## 4. TranslationPromptManager 이식

wl `prompt_manager.py`(`TranslationPromptManager`)를 이식하되, 버그 1건을 수정한다:

```python
# wl 원본 버그: 인자 없이 정의됐는데 인자를 받아 호출됨 (NameError 유발)
def _load_default_glossary_from_file(self) -> dict:
    ...
    if os.path.exists(file_path):   # file_path 미정의

# 수정: 파라미터 추가
def _load_default_glossary_from_file(self, file_path) -> dict:
    ...
```

나머지 메서드는 wl 그대로 이식:

- `add_item(block_key, origin, translation)` / `remove_item(block_key, origin)` — `glossary_block`·
  `sentence_block` 공용 처리, DB 즉시 반영.
- `get_user_view_settings()` — 사용자 조회용. glossary는 **사용자 추가분만** 노출(admin 기본값 숨김),
  sentence는 전체(기본+사용자) 노출.
- `get_relevant_glossary(input_text)` — 입력 문장에 **실제 등장하는 용어만** 골라 반환(한↔영 양방향
  substring 매칭). 매칭 없으면 빈 문자열(빈 헤더 방지).
- `get_sentence_block()` — few-shot 예시 전체 반환(내용 있으면 항상 포함).

`whisperlivekit/llm_translation/__init__.py`에 `get_prompt_manager()` 싱글턴 팩토리 추가
(`filtering/__init__.py`의 `get_word_manager()`와 동일 패턴 — 모듈 전역 `_prompt_manager` +
lazy init).

## 5. translator.py 통합 (프롬프트 조립)

`TranslatorBase`에 공용 조립 메서드를 추가해 `LlamaTranslator`/`OllamaTranslator`가 공유한다:

```python
# TranslatorBase에 추가
def build_system_blocks(self, from_lang, to_lang, content) -> list[str]:
    blocks = [self.get_static_system_text(from_lang, to_lang)]

    prompt_manager = get_prompt_manager()
    glossary_part = prompt_manager.get_relevant_glossary(content)
    if glossary_part:
        blocks.append(GLOSSARY_RULES_TEXT)   # 9/10번으로 재번호 (기존 1-8번과 충돌 방지)
        blocks.append(glossary_part)

    sentence_part = prompt_manager.get_sentence_block()
    if sentence_part:
        blocks.append(sentence_part)

    return blocks
```

- `GLOSSARY_RULES_TEXT`는 wl 원본이 "5. GLOSSARY PRIORITY... 6. Contextual Translation..."으로
  번호가 매겨져 있었으나, wlk의 정적 프롬프트(`get_static_system_text`)가 이미 1~8번을 쓰고 있어
  **9/10번으로 재번호**한다(순수 가독성 문제, LLM 동작에는 영향 없음).
- **LlamaTranslator**: `system_blocks = self.build_system_blocks(...)` → 기존 `build_prompt(content, system_blocks)`
  그대로 사용.
- **OllamaTranslator**: 동일하게 `build_system_blocks(...)` 호출 후 `"\n\n".join(system_blocks)`로
  합쳐 기존 `_call_chat(system_text, content)`에 전달(Ollama API는 system 메시지가 문자열 하나라
  join만 다름, 로직 동일).
- glossary 블록은 **매칭될 때만** 추가(wl 로직 그대로), sentence 블록은 **내용이 있으면 항상** 추가.
- `manager.py`(`TranslationManager`)는 **변경 없음** — `translate_sentence(text, src_lang)` 호출부는
  그대로이며, 조립은 전부 translator.py 내부에서 처리된다.
- Stage 2(RAG)는 이 메서드 안에 블록 하나를 추가로 append하는 형태로 확장될 예정(§8).

## 6. REST API (`/api/prompts`)

`basic_server.py`의 기존 `/api/corrections` 블록 바로 아래에 추가한다(완전히 별개 매니저·별개
엔드포인트, 단어교정 API는 손대지 않음):

```python
class PromptItemRequest(BaseModel):
    block_key: str            # "glossary_block" 또는 "sentence_block"
    origin: str
    translation: Optional[str] = None

@app.get("/api/prompts")
async def get_prompts():
    """사용자 뷰: glossary는 사용자 추가분만, sentence는 전체(기본+사용자) 반환."""
    return get_prompt_manager().get_user_view_settings()

@app.post("/api/prompts/add-item")
async def add_prompt_item(request: PromptItemRequest):
    if request.block_key not in ("glossary_block", "sentence_block"):
        raise HTTPException(status_code=400, detail="Invalid block key")
    get_prompt_manager().add_item(request.block_key, request.origin, request.translation)
    return {"status": "success"}

@app.post("/api/prompts/delete-item")
async def delete_prompt_item(request: PromptItemRequest):
    if request.block_key not in ("glossary_block", "sentence_block"):
        raise HTTPException(status_code=400, detail="Invalid block key")
    success = get_prompt_manager().remove_item(request.block_key, request.origin)
    if success:
        return {"status": "success"}
    return {"status": "warning", "message": "Item not found or cannot delete default glossary item"}
```

- 잘못된 `block_key`는 wl처럼 200+error body 대신 **`HTTPException(400)`**으로 통일(같은 파일의
  `_convert_to_pcm`이 이미 이 스타일을 사용 — 일관성).
- "삭제 대상 없음"은 실패가 아니라 정상 케이스이므로 wl 그대로 **200 + `warning`** 유지.
- **갱신 즉시 반영**: `add_item`/`remove_item`이 싱글턴 `self.user_settings`를 즉시 갱신 + DB 저장하므로,
  별도 리로드 없이 다음 `translate_sentence()` 호출부터 바로 반영된다(단어교정과 동일 원리).

## 7. 테스트 전략

### 7.1 검증 대상과 픽스처 (기존 관례 그대로)

배포 PC 실물 파일 없이, **합성 tmp_path 픽스처로 로직만 검증**하고 테스트 종료 후 폐기한다.

- **`tests/test_prompt_manager.py`** (신규) — `tests/test_filtering.py`의 `make_manager()` 헬퍼
  패턴을 그대로 따라 `make_prompt_manager(tmp_path, glossary_dict, sentence_rows=None)` 작성.
  합성 용어(예: `"공군":"ROKAF"`)로 `add_item`/`remove_item`/`get_relevant_glossary`(매칭 시만
  반환·양방향 매칭 검증)/`get_sentence_block`/`get_user_view_settings`(admin 기본값 숨김 검증) 검증.
  `_load_default_glossary_from_file` 버그 수정 회귀 테스트 포함.
- **`tests/test_prompts_api.py`** (신규) — `tests/test_corrections_api.py`의 `isolated_word_manager`
  픽스처 패턴 그대로 `create_test_app()` 스타일 최소 목업 앱(실제 `basic_server.py`의 `lifespan`/
  `TranscriptionEngine` 미사용)으로 `/api/prompts`·`/api/prompts/add-item`·`/api/prompts/delete-item`
  3종 라우트 검증. 전역 싱글턴을 tmp_path 버전으로 스왑 후 테스트 종료 시 원복.
- **`tests/test_llm_translator.py`**(기존 파일에 케이스 추가) — `get_prompt_manager`를 patch해
  glossary 매칭 시 프롬프트에 블록이 실리는지 / 매칭 없으면 안 실리는지 / sentence_block은 존재
  시 항상 실리는지 검증(기존 파일의 `patch.object(translator.client, "post", ...)` mock 패턴과
  동일선상).

### 7.2 경로C(VBCable 실측) 측정과의 충돌 방지

다른 세션 창에서 경로C 측정이 진행 중일 수 있으므로, 이번 검증은 그것과 **절대 리소스 충돌이
없도록** 아래를 지킨다:

- **GPU 모델 로드·실서버 기동·VBCable 접근 전혀 없음** — 위 세 테스트 파일 모두 목업 앱 +
  tmp_path + HTTP mock으로 끝나며, `basic_server.py`의 실제 `lifespan`(`TranscriptionEngine` 로드)을
  건드리지 않는다.
- **실행은 `.venv\Scripts\python.exe -m pytest`로 직접 호출** — `uv run pytest` 금지(공유 Junction
  `.venv` 자동 동기화가 진행 중인 측정을 전멸시킬 위험, CLAUDE.md §4 가드레일).
- **실서버 수동 스모크테스트(서버 기동 + curl)는 보류** — 필요 시 다른 세션의 경로C 측정이
  끝난 뒤 별도로 진행한다.
- **임시 데이터 폐기**: `tmp_path`는 pytest가 테스트마다 자동 격리·정리하므로 레포에 흔적이 남지
  않는다. 수동 확인용 스크래치 파일을 만들 경우 스크래치패드 디렉터리에만 두고 검증 후 삭제한다.
- **테스트 전부 통과 확인 후, 위 tmp_path 산출물 외에 남은 임시 파일이 없는지 확인하고 정리한다.**

## 8. Stage 2 (Qdrant RAG) 확장 지점 — 별도 스펙 예정

이번 스펙엔 포함하지 않되, §5의 `build_system_blocks()`가 이미 확장 지점을 마련해둔다 — Stage 2에서는
이 메서드 안에 블록 하나를 추가로 append하면 된다:

```python
# Stage 2에서 build_system_blocks() 안에 추가될 형태 (지금은 구현하지 않음)
rag_examples = await rag_manager.search_similar(content, k=3)
if rag_examples:
    blocks.append(rag_examples)
```

Stage 2는 `qdrant-client`(로컬 임베디드 모드, `QdrantClient(path=...)`)와 `sentence-transformers`
(bge-m3 로컬 모델 직접 로드)를 신규 의존성으로 추가하며, 별도 스펙에서 pyproject extra·
`docs/DEPLOYMENT_OFFLINE.md` §2 갱신까지 함께 다룬다.

→ 2026-07-21 구현 완료, 코드는 `whisperlivekit/llm_translation/rag_manager.py`(`TranslationRagManager`) 참조.
배포 PC 미검증(Qdrant payload 스키마 가정·`client.search()` API 버전 이슈 — `docs/DEPLOYMENT_OFFLINE.md` §6.3 참조).

**구현 시 확정된 설계 변경 — RAG는 확정 문장에만 적용한다.** 위 의사코드는 `build_system_blocks()`에
무조건 append하는 형태였으나, 실제로는 번역 경로가 둘(확정 문장 → `lines[].translation`, 진행 중 버퍼 →
`buffer_translation`)이고 둘 다 같은 `translate_sentence()`를 타므로 그대로 두면 **미확정 버퍼 번역에도
RAG가 걸린다**. 버퍼는 발화 중 초당 수 회 갱신되므로 임베딩 인코딩 + 벡터 검색이 그 빈도로 반복돼
실시간성이 무너진다. 따라서 `build_system_blocks(..., use_rag: bool = False)` 플래그를 두고
`TranslationManager._translate_and_cache()`(확정)만 `use_rag=True`로 호출한다. 기본값 `False`는
새 호출자가 플래그를 빠뜨려도 미확정 경로로 새지 않게 하는 fail-safe다.

## 9. 관련 문서 갱신 체크리스트 (구현 단계에서 처리)

- `ROADMAP.md` Phase 5 5-2 — 현재 "whisperlive_code/manager.py 기반"으로 잘못 적혀 있음(실제로는
  `prompt_manager.py`) → 정정.
- CLAUDE.md 연동 갱신 문서 표의 "번역 파이프라인 변경" 행에 따른 프론트엔드 인계 문서 갱신 —
  단, 다른 세션에서 문서 구조 정리가 진행 중이므로(`FRONTEND_HANDOFF.md` 아카이브 여부 등) **구현
  시점에 현재 정본 파일명을 재확인**하고 반영한다(이 스펙에 고정 파일명을 박아두지 않음).
- `.gitignore`에 `whisperlivekit/llm_translation/*.db` 추가.
- `pyproject.toml` 변경 없음(Stage 1 한정).
