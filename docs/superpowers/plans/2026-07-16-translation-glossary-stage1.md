# 번역 Glossary 이식 (Stage 1: glossary_block + sentence_block) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** wl(whisperlive)의 `TranslationPromptManager`(용어집 glossary_block + few-shot 예시 sentence_block)를 `whisperlivekit/llm_translation/`에 이식하고, 번역 프롬프트 조립 + `/api/prompts` REST API로 배포 PC의 실제 glossary 데이터를 그대로 꽂을 수 있는 연결부를 완성한다.

**Architecture:** `whisperlivekit/filtering/`(WordCorrectionManager)과 동일한 콜로케이션 패턴 — 코드와 JSON/SQLite 데이터를 같은 모듈 디렉터리에 둔다. `TranslatorBase`에 공용 `build_system_blocks()` 메서드를 추가해 `LlamaTranslator`/`OllamaTranslator`가 공유하고, `basic_server.py`에 기존 `/api/corrections`와 나란히 `/api/prompts` 3종 엔드포인트를 추가한다. Qdrant RAG(Stage 2)는 이 스펙에 포함하지 않으며, `build_system_blocks()`에 확장 지점만 남긴다.

**Tech Stack:** Python 3.11+, FastAPI, SQLite(표준 라이브러리 `sqlite3`), pytest(`anyio` 마커, 기존 컨벤션). 신규 외부 의존성 없음.

**참조 스펙:** `docs/superpowers/specs/2026-07-16-translation-glossary-design.md`
**참조 레퍼런스:** `whisperlive_code/prompt_manager.py`, `whisperlive_code/translator.py`, `whisperlive_code/app.py`

## Global Constraints

- 모든 커밋 메시지·문서·주석 아닌 응답은 한국어(코드 식별자·주석은 기존 관례대로 영어 유지).
- **`uv run`/`uv sync`/`uv add` 절대 금지** — 공유 Junction `.venv` 자동 동기화가 다른 세션의 경로C(VBCable) 실측을 전멸시킬 위험. 테스트는 반드시 `.venv\Scripts\python.exe -m pytest`로 직접 호출.
- **GPU 모델 로드·실서버(`basic_server.py`) 기동·VBCable 접근 전혀 없이 검증** — 모든 테스트는 `tmp_path` 격리 + 목업 FastAPI 앱 + HTTP mock으로 끝낸다(기존 `tests/test_corrections_api.py`, `tests/test_filtering.py` 패턴 그대로).
- ruff: line-length 120, target `py311`. lint는 `.venv\Scripts\ruff.exe` 직접 호출(uv 경유 금지).
- glossary JSON은 `{origin: translation}` **dict** 포맷(단어교정 `admin_replacement.json`의 리스트 포맷과 다름 — 혼동 금지).
- `admin_translation_glossary.json`은 git-tracked(placeholder `{}`), `user_translation_glossary.db`는 `.gitignore` 대상(`filtering/*.db`와 동일 관례).
- 코드 작업은 반드시 별도 브랜치+워크트리에서(CLAUDE.md 워크트리 규약) — main 브랜치/메인 워크트리에서 코드 편집 금지.

---

### Task 1: 워크트리 준비

**Files:** 없음(git worktree 생성만)

**Interfaces:**
- Produces: `worktrees/translation-glossary-stage1/`(브랜치 `feat/translation-glossary-stage1`) — 이후 모든 Task는 이 워크트리 절대경로에서 실행한다.

- [ ] **Step 1: 워크트리 + 브랜치 생성**

Run (저장소 루트에서):
```powershell
git worktree add worktrees/translation-glossary-stage1 -b feat/translation-glossary-stage1
```
Expected: `Preparing worktree (new branch 'feat/translation-glossary-stage1')` 출력, `worktrees/translation-glossary-stage1/` 디렉터리 생성됨.

- [ ] **Step 2: `.venv` Junction 연결 (메인 `.venv` 공유, CLAUDE.md 관례)**

Run:
```powershell
cd worktrees\translation-glossary-stage1
cmd /c mklink /J .venv ..\..\.venv
cd ..\..
```
Expected: `Junction created for .venv <<===>> ..\..\.venv` 출력.

- [ ] **Step 3: 워크트리에서 pytest가 정상 동작하는지 확인**

Run (워크트리 디렉터리에서):
```powershell
cd worktrees\translation-glossary-stage1
.venv\Scripts\python.exe -m pytest tests/test_filtering.py -v
cd ..\..
```
Expected: 기존 `test_filtering.py` 테스트 전부 PASS (워크트리 환경이 정상 동작함을 확인 — 신규 코드 관련 실패 아님).

---

### Task 2: TranslationPromptManager 이식 (glossary_block + sentence_block)

**Files:**
- Create: `worktrees/translation-glossary-stage1/whisperlivekit/llm_translation/prompt_manager.py`
- Create: `worktrees/translation-glossary-stage1/whisperlivekit/llm_translation/admin_translation_glossary.json`
- Modify: `worktrees/translation-glossary-stage1/whisperlivekit/llm_translation/__init__.py` (현재 0바이트)
- Modify: `worktrees/translation-glossary-stage1/.gitignore`
- Test: `worktrees/translation-glossary-stage1/tests/test_prompt_manager.py`

**Interfaces:**
- Produces: `TranslationPromptManager(base_json_path, db_path)` 클래스 — 메서드 `add_item(block_key, origin, translation) -> bool`, `remove_item(block_key, origin) -> bool`, `get_user_view_settings() -> dict`, `get_relevant_glossary(input_text) -> str`, `get_sentence_block() -> str`, 속성 `defaults: dict`, `user_settings: dict`.
- Produces: `get_prompt_manager() -> TranslationPromptManager` 싱글턴 팩토리 (`whisperlivekit.llm_translation` 패키지 루트에서 import 가능).
- Consumes: 없음(신규 모듈).

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_prompt_manager.py`:
```python
# -*- coding: utf-8 -*-
"""Phase 5 번역 Glossary(TranslationPromptManager) 독립 모듈 검증 테스트.

whisperlivekit/llm_translation/prompt_manager.py가 audio_processor 등 코어 없이도
독립적으로 동작하는지 확인한다. 각 테스트는 tmp_path 기반 임시 fixture를 사용해
전역 싱글턴 오염 없이 격리 실행된다.
"""

import json
from pathlib import Path

from whisperlivekit.llm_translation.prompt_manager import TranslationPromptManager


def make_prompt_manager(tmp_path: Path, glossary: dict) -> TranslationPromptManager:
    """임시 JSON + DB로 TranslationPromptManager를 생성한다."""
    json_path = tmp_path / "admin_translation_glossary.json"
    db_path = tmp_path / "user_translation_glossary.db"
    json_path.write_text(json.dumps(glossary, ensure_ascii=False), encoding="utf-8")
    return TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))


def test_load_default_glossary_from_file(tmp_path):
    """admin JSON의 기본 용어집이 정상 로드되는지 확인 (버그 수정 회귀 테스트)."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    assert mgr.defaults["glossary_block"] == {"공군": "ROKAF"}


def test_load_default_glossary_missing_file(tmp_path):
    """admin JSON 파일이 없으면 빈 딕셔너리를 반환한다."""
    db_path = tmp_path / "user_translation_glossary.db"
    mgr = TranslationPromptManager(
        base_json_path=str(tmp_path / "nonexistent.json"), db_path=str(db_path)
    )
    assert mgr.defaults["glossary_block"] == {}


def test_get_relevant_glossary_matches_origin(tmp_path):
    """입력 문장에 원문 용어가 등장하면 glossary 블록에 포함된다."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    result = mgr.get_relevant_glossary("우리 공군은 임무를 수행했다")
    assert "공군 : ROKAF" in result
    assert result.startswith("GLOSSARY(Term:Translation)")


def test_get_relevant_glossary_matches_translation_bidirectional(tmp_path):
    """번역어가 입력 문장에 등장해도(영→한 방향) glossary 블록에 포함된다."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    result = mgr.get_relevant_glossary("The ROKAF conducted a mission")
    assert "공군 : ROKAF" in result


def test_get_relevant_glossary_no_match_returns_empty(tmp_path):
    """매칭되는 용어가 없으면 빈 문자열을 반환한다 (빈 헤더 방지)."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    result = mgr.get_relevant_glossary("오늘 날씨가 좋다")
    assert result == ""


def test_add_glossary_item_persists_and_merges(tmp_path):
    """add_item으로 추가한 용어가 사용자 사전에 저장되고 get_relevant_glossary에 반영된다."""
    mgr = make_prompt_manager(tmp_path, {})
    mgr.add_item("glossary_block", "해군", "ROKN")
    assert mgr.user_settings["glossary_block"] == {"해군": "ROKN"}
    result = mgr.get_relevant_glossary("해군 함정이 이동했다")
    assert "해군 : ROKN" in result


def test_remove_glossary_item(tmp_path):
    """remove_item으로 사용자 추가 용어를 삭제할 수 있다."""
    mgr = make_prompt_manager(tmp_path, {})
    mgr.add_item("glossary_block", "해군", "ROKN")
    assert mgr.remove_item("glossary_block", "해군") is True
    assert "해군" not in mgr.user_settings["glossary_block"]


def test_remove_glossary_item_not_found(tmp_path):
    """존재하지 않는 용어 삭제는 False를 반환한다."""
    mgr = make_prompt_manager(tmp_path, {})
    assert mgr.remove_item("glossary_block", "없는용어") is False


def test_get_user_view_settings_hides_admin_glossary(tmp_path):
    """get_user_view_settings는 admin 기본 glossary는 숨기고 사용자 추가분만 노출한다."""
    mgr = make_prompt_manager(tmp_path, {"공군": "ROKAF"})
    mgr.add_item("glossary_block", "해군", "ROKN")
    view = mgr.get_user_view_settings()
    assert view["glossary_block"] == {"해군": "ROKN"}
    assert "공군" not in view["glossary_block"]


def test_get_sentence_block_default(tmp_path):
    """sentence_block 수정 전에는 기본 예시 문장이 반환된다."""
    mgr = make_prompt_manager(tmp_path, {})
    result = mgr.get_sentence_block()
    assert result.startswith("### EXAMPLES")
    assert "The ROK Air Force conducted joint air operations" in result


def test_add_sentence_item_overrides_defaults_copy_on_write(tmp_path):
    """sentence_block에 add_item을 한 번이라도 호출하면 기본값을 복사해 사용자 버전으로 전환된다."""
    mgr = make_prompt_manager(tmp_path, {})
    mgr.add_item("sentence_block", "테스트 입력", "테스트 출력")
    assert mgr.user_settings["sentence_block"] is not None
    result = mgr.get_sentence_block()
    assert "테스트 입력" in result
    assert "The ROK Air Force conducted joint air operations" in result


def test_get_user_view_settings_sentence_shows_full(tmp_path):
    """sentence_block은 기본+사용자 전체가 노출된다 (glossary와 달리 숨기지 않음)."""
    mgr = make_prompt_manager(tmp_path, {})
    view = mgr.get_user_view_settings()
    assert "The ROK Air Force conducted joint air operations" in view["sentence_block"]


def test_settings_persist_across_manager_instances(tmp_path):
    """DB에 저장된 사용자 설정은 매니저를 새로 생성해도 로드된다."""
    json_path = tmp_path / "admin_translation_glossary.json"
    db_path = tmp_path / "user_translation_glossary.db"
    json_path.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")

    mgr1 = TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))
    mgr1.add_item("glossary_block", "공군", "ROKAF")

    mgr2 = TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))
    assert mgr2.user_settings["glossary_block"] == {"공군": "ROKAF"}
```

- [ ] **Step 2: 테스트가 실패하는지 확인 (모듈이 아직 없음)**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt_manager.py -v
```
Expected: `ModuleNotFoundError: No module named 'whisperlivekit.llm_translation.prompt_manager'`로 전부 FAIL.

- [ ] **Step 3: `prompt_manager.py` 구현**

Create `whisperlivekit/llm_translation/prompt_manager.py`:
```python
# -*- coding: utf-8 -*-
"""번역 프롬프트에 주입할 용어집(glossary_block)과 예시문(sentence_block) 관리.

whisperlive_code/prompt_manager.py를 이식. 원본의 _load_default_glossary_from_file이
인자 없이 정의됐으나 인자를 받아 호출되던 버그(NameError 유발)를 수정했다.
"""

import json
import os
import sqlite3


class TranslationPromptManager:
    """glossary_block: {origin: translation} 용어 매핑. 개발자 기본값(JSON) + 사용자
    추가분(DB)을 병합해 사용하며, 입력 문장에 실제 등장하는 용어만 골라 반환한다.

    sentence_block: few-shot 예시 문장쌍. 사용자가 수정하기 전까지는 개발자 기본값을
    그대로 쓰고(Copy-on-Write), 한 번이라도 add_item/remove_item이 호출되면 전체를
    사용자 버전으로 교체한다.
    """

    def __init__(self, base_json_path: str, db_path: str):
        self.db_path = db_path

        self.headers = {
            "glossary_block": "GLOSSARY(Term:Translation)",
            "sentence_block": "### EXAMPLES",
        }

        self.defaults = {
            "glossary_block": self._load_default_glossary_from_file(base_json_path),
            "sentence_block": {
                "The ROK Air Force conducted joint air operations": "대한민국 공군은 연합 공중작전을 수행했다.",
                "보고를 드리기 전 안내 말씀드리겠습니다.": "Before we begin, a brief notice.",
                "우리는 한미 연합 공중훈련의 일환으로 대한민국(ROK) 공군 부대와 협조했다": "We coordinated with ROK Air Force unit as part of ROK-US combined air exercise.",
            },
        }

        self.user_settings = {
            "glossary_block": {},
            "sentence_block": None,
        }

        self._init_db()
        self.load_settings()

    # ------------------------------------------------------------------
    # [초기화 및 DB 관리]
    # ------------------------------------------------------------------
    def _load_default_glossary_from_file(self, file_path: str) -> dict:
        """JSON 파일에서 개발자 기본 용어집 로드 (실패 시 빈 딕셔너리 반환)."""
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"Warning: Failed to load default glossary: {e}")
            return {}

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            conn.commit()

    def load_settings(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM prompt_settings")
            rows = cursor.fetchall()

            for key, val_str in rows:
                if key in self.user_settings:
                    try:
                        self.user_settings[key] = json.loads(val_str)
                    except json.JSONDecodeError:
                        self.user_settings[key] = {} if key == "glossary_block" else None

    def _save_to_db(self, key: str):
        val = self.user_settings[key]
        if val is None:
            return

        json_val = json.dumps(val, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO prompt_settings (key, value) VALUES (?, ?)",
                (key, json_val),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # [데이터 추가/삭제/조회 API 연동용]
    # ------------------------------------------------------------------
    def add_item(self, block_key: str, origin: str, translation: str) -> bool:
        if block_key == "glossary_block":
            self.user_settings["glossary_block"][origin.strip()] = translation.strip()
            self._save_to_db("glossary_block")
        elif block_key == "sentence_block":
            if self.user_settings["sentence_block"] is None:
                self.user_settings["sentence_block"] = self.defaults["sentence_block"].copy()
            self.user_settings["sentence_block"][origin.strip()] = translation.strip()
            self._save_to_db("sentence_block")
        return True

    def remove_item(self, block_key: str, origin: str) -> bool:
        target_key = origin.strip()
        if block_key == "glossary_block":
            if target_key in self.user_settings["glossary_block"]:
                del self.user_settings["glossary_block"][target_key]
                self._save_to_db("glossary_block")
                return True
            return False
        elif block_key == "sentence_block":
            if self.user_settings["sentence_block"] is None:
                self.user_settings["sentence_block"] = self.defaults["sentence_block"].copy()
            if target_key in self.user_settings["sentence_block"]:
                del self.user_settings["sentence_block"][target_key]
                self._save_to_db("sentence_block")
                return True
        return False

    def get_user_view_settings(self) -> dict:
        """프론트엔드 표출용 데이터 반환 (개발자 glossary 기본값은 숨김)."""
        current_sentence = self.user_settings["sentence_block"]
        if current_sentence is None:
            current_sentence = self.defaults["sentence_block"]
        return {
            "glossary_block": self.user_settings["glossary_block"],
            "sentence_block": current_sentence,
        }

    # ------------------------------------------------------------------
    # [프롬프트 동적 주입용]
    # ------------------------------------------------------------------
    def get_relevant_glossary(self, input_text: str) -> str:
        """입력 문장에 실제 등장하는 용어만 골라 glossary 블록 문자열로 반환.

        단순 in 매칭(조사 문제 회피), 한→영·영→한 양방향 검색. 매칭 없으면 빈 문자열
        (빈 헤더 방지).
        """
        combined_glossary = self.defaults["glossary_block"].copy()
        combined_glossary.update(self.user_settings["glossary_block"])

        if not combined_glossary:
            return ""

        relevant_items = []
        input_lower = input_text.lower()

        for origin, trans in combined_glossary.items():
            match_origin = origin.lower() in input_lower
            match_trans = trans.lower() in input_lower
            if match_origin or match_trans:
                relevant_items.append(f"{origin} : {trans}")

        if not relevant_items:
            return ""

        return f"{self.headers['glossary_block']}\n" + "\n".join(relevant_items)

    def get_sentence_block(self) -> str:
        """예시 문장 전체 반환 (없으면 빈 문자열)."""
        current_dict = self.user_settings["sentence_block"]
        if current_dict is None:
            current_dict = self.defaults["sentence_block"]

        if not current_dict:
            return ""

        items = []
        for inp, out in current_dict.items():
            items.append(f"- INPUT : {inp}\n- OUTPUT : {out}")

        return f"{self.headers['sentence_block']}\n" + "\n\n".join(items)
```

Create `whisperlivekit/llm_translation/admin_translation_glossary.json`:
```json
{}
```

- [ ] **Step 4: 테스트 재실행 → 여전히 실패 확인 (팩토리 미구현)**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt_manager.py -v
```
Expected: 전부 PASS (Step 3에서 `TranslationPromptManager` 자체는 이미 완성됐으므로 이 시점에 통과해야 함). PASS 되지 않으면 Step 3 코드를 점검한다.

- [ ] **Step 5: `get_prompt_manager()` 싱글턴 팩토리 작성 (`__init__.py`)**

Modify `whisperlivekit/llm_translation/__init__.py` (현재 0바이트, 전체 내용 아래로 교체):
```python
from pathlib import Path

from .prompt_manager import TranslationPromptManager

_LLM_TRANSLATION_DIR = Path(__file__).resolve().parent

_prompt_manager = None


def get_prompt_manager() -> TranslationPromptManager:
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = TranslationPromptManager(
            base_json_path=str(_LLM_TRANSLATION_DIR / "admin_translation_glossary.json"),
            db_path=str(_LLM_TRANSLATION_DIR / "user_translation_glossary.db"),
        )
    return _prompt_manager
```

- [ ] **Step 6: `.gitignore`에 glossary DB 추가**

Modify `.gitignore` — `whisperlivekit/filtering/*.db` 줄 바로 아래에 추가:
```
whisperlivekit/filtering/*.db
whisperlivekit/llm_translation/*.db
```

- [ ] **Step 7: 전체 테스트 재실행 (최종 확인)**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt_manager.py -v
```
Expected: 13개 테스트 전부 PASS.

- [ ] **Step 8: Commit**

```bash
git add whisperlivekit/llm_translation/prompt_manager.py whisperlivekit/llm_translation/__init__.py whisperlivekit/llm_translation/admin_translation_glossary.json .gitignore tests/test_prompt_manager.py
git commit -m "feat(translation): TranslationPromptManager 이식 (glossary_block + sentence_block)

wl(whisperlive) prompt_manager.py를 whisperlivekit/llm_translation/에 이식.
_load_default_glossary_from_file의 NameError 버그(인자 미정의) 수정.
get_prompt_manager() 싱글턴 팩토리를 filtering/의 get_word_manager()와 동일 패턴으로 추가."
```

---

### Task 3: translator.py 통합 (프롬프트 조립)

**Files:**
- Modify: `whisperlivekit/llm_translation/translator.py`
- Modify: `tests/test_llm_translator.py` (기존 파일에 케이스 추가)

**Interfaces:**
- Consumes: `get_prompt_manager()` (Task 2에서 생성), `TranslationPromptManager.get_relevant_glossary(text) -> str`, `.get_sentence_block() -> str`.
- Produces: `TranslatorBase.build_system_blocks(from_lang, to_lang, content) -> list[str]` — Stage 2(RAG)가 나중에 이 메서드에 블록을 추가로 append할 확장 지점.

- [ ] **Step 1: 실패하는 테스트 작성 (기존 `tests/test_llm_translator.py` 끝에 추가)**

Append to `tests/test_llm_translator.py`:
```python
def _make_prompt_manager_mock(glossary_result: str = "", sentence_result: str = ""):
    mock_pm = MagicMock()
    mock_pm.get_relevant_glossary.return_value = glossary_result
    mock_pm.get_sentence_block.return_value = sentence_result
    return mock_pm


@pytest.mark.anyio
async def test_llama_includes_glossary_block_when_matched():
    """glossary가 매칭되면 프롬프트에 GLOSSARY 블록이 포함된다."""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("번역결과")
    mock_pm = _make_prompt_manager_mock(glossary_result="GLOSSARY(Term:Translation)\n공군 : ROKAF")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("우리 공군은", "ko")

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "GLOSSARY(Term:Translation)" in sent_prompt
    assert "공군 : ROKAF" in sent_prompt
    assert "GLOSSARY PRIORITY" in sent_prompt


@pytest.mark.anyio
async def test_llama_omits_glossary_block_when_no_match():
    """glossary 매칭이 없으면 GLOSSARY 블록이 프롬프트에 포함되지 않는다."""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("번역결과")
    mock_pm = _make_prompt_manager_mock(glossary_result="")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("오늘 날씨가 좋다", "ko")

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "GLOSSARY" not in sent_prompt


@pytest.mark.anyio
async def test_llama_always_includes_sentence_block_when_present():
    """sentence_block이 존재하면 항상 프롬프트에 포함된다."""
    translator = LlamaTranslator("gpt-oss-20b", "http://localhost:2010")
    mock_resp = _make_completions_response("번역결과")
    mock_pm = _make_prompt_manager_mock(sentence_result="### EXAMPLES\n- INPUT : x\n- OUTPUT : y")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("아무 문장", "ko")

    sent_prompt = mock_post.call_args.kwargs["json"]["prompt"]
    assert "### EXAMPLES" in sent_prompt


@pytest.mark.anyio
async def test_ollama_includes_glossary_in_joined_system_text():
    """OllamaTranslator: glossary 매칭 시 system 메시지에 GLOSSARY 블록이 합쳐져 포함된다."""
    translator = OllamaTranslator("qwen2.5:7b", "http://localhost:11434")
    mock_resp = _make_chat_response("번역결과")
    mock_pm = _make_prompt_manager_mock(glossary_result="GLOSSARY(Term:Translation)\n공군 : ROKAF")

    with patch("whisperlivekit.llm_translation.translator.get_prompt_manager", return_value=mock_pm), \
         patch.object(translator.client, "post", new=AsyncMock(return_value=mock_resp)) as mock_post:
        await translator.translate_sentence("우리 공군은", "ko")

    sent_messages = mock_post.call_args.kwargs["json"]["messages"]
    system_message = next(m["content"] for m in sent_messages if m["role"] == "system")
    assert "공군 : ROKAF" in system_message
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_llm_translator.py -v -k "glossary or sentence_block_when_present or joined_system_text"
```
Expected: 신규 4개 테스트 FAIL — `patch("whisperlivekit.llm_translation.translator.get_prompt_manager", ...)`가 `AttributeError: <module> does not have the attribute 'get_prompt_manager'`(아직 translator.py에 import 안 됨).

- [ ] **Step 3: `translator.py` 수정 — import 추가 + `build_system_blocks` 메서드 + 호출부 교체**

Modify `whisperlivekit/llm_translation/translator.py` — 파일 최상단 import 블록:

old_string:
```python
import httpx


class TranslatorBase:
```
new_string:
```python
import httpx

from whisperlivekit.llm_translation import get_prompt_manager


class TranslatorBase:
```

Modify — `get_static_system_text` 메서드 바로 아래에 `get_glossary_rules_text`와 `build_system_blocks` 추가:

old_string:
```python
    def build_prompt(self, content: str, system_blocks: list) -> str:
```
new_string:
```python
    @staticmethod
    def get_glossary_rules_text(to_lang: str) -> str:
        return (
            "9. GLOSSARY PRIORITY: Strictly follow the provided GLOSSARY for technical military terms to ensure consistency.\n"
            f"10. Contextual Translation: While following the glossary, ensure the overall sentence structure is grammatically correct in {to_lang}."
        )

    def build_system_blocks(self, from_lang: str, to_lang: str, content: str) -> list:
        """정적 프롬프트 + (매칭 시) glossary 블록 + (존재 시) sentence 예시 블록 조립."""
        blocks = [self.get_static_system_text(from_lang, to_lang)]

        prompt_manager = get_prompt_manager()
        glossary_part = prompt_manager.get_relevant_glossary(content)
        if glossary_part:
            blocks.append(self.get_glossary_rules_text(to_lang))
            blocks.append(glossary_part)

        sentence_part = prompt_manager.get_sentence_block()
        if sentence_part:
            blocks.append(sentence_part)

        return blocks

    def build_prompt(self, content: str, system_blocks: list) -> str:
```

Modify — `LlamaTranslator.translate_sentence`:

old_string:
```python
    async def translate_sentence(self, content: str, src_lang: str) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = [self.get_static_system_text(from_lang, to_lang)]
        prompt = self.build_prompt(content, system_blocks)
        return await self._call_completions(prompt)
```
new_string:
```python
    async def translate_sentence(self, content: str, src_lang: str) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = self.build_system_blocks(from_lang, to_lang, content)
        prompt = self.build_prompt(content, system_blocks)
        return await self._call_completions(prompt)
```

Modify — `OllamaTranslator.translate_sentence`:

old_string:
```python
    async def translate_sentence(self, content: str, src_lang: str) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_text = self.get_static_system_text(from_lang, to_lang)
        return await self._call_chat(system_text, content)
```
new_string:
```python
    async def translate_sentence(self, content: str, src_lang: str) -> str:
        from_lang = self.convert_lang_formal(src_lang)
        to_lang = self.convert_lang_formal(self.get_to_lang(src_lang))
        system_blocks = self.build_system_blocks(from_lang, to_lang, content)
        system_text = "\n\n".join(system_blocks)
        return await self._call_chat(system_text, content)
```

- [ ] **Step 4: 신규 테스트 통과 확인**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_llm_translator.py -v
```
Expected: 기존 케이스 포함 전부 PASS(신규 4개 + 기존 8개 = 12개).

- [ ] **Step 5: Task 2 테스트도 회귀 없는지 재확인**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt_manager.py tests/test_llm_translator.py -v
```
Expected: 전부 PASS.

- [ ] **Step 6: Commit**

```bash
git add whisperlivekit/llm_translation/translator.py tests/test_llm_translator.py
git commit -m "feat(translation): translator.py에 glossary/sentence 프롬프트 조립 연결

TranslatorBase.build_system_blocks() 추가 — LlamaTranslator/OllamaTranslator가
공유. glossary 매칭 시에만 GLOSSARY 규칙(9/10번, 기존 1-8번과 번호 충돌 회피)+
용어 블록 추가, sentence_block은 존재 시 항상 포함. manager.py(TranslationManager)는
변경 없음."
```

---

### Task 4: REST API (`/api/prompts`)

**Files:**
- Modify: `whisperlivekit/basic_server.py`
- Test: `tests/test_prompts_api.py` (신규)

**Interfaces:**
- Consumes: `get_prompt_manager()`(Task 2), `TranslationPromptManager.add_item/remove_item/get_user_view_settings`.
- Produces: `GET /api/prompts`, `POST /api/prompts/add-item`, `POST /api/prompts/delete-item` 엔드포인트.

- [ ] **Step 1: 실패하는 테스트 작성**

Create `tests/test_prompts_api.py`:
```python
# -*- coding: utf-8 -*-
"""Phase 5 /api/prompts REST 엔드포인트 테스트.

basic_server.py의 번역 Glossary 관리 API를 검증한다:
- GET /api/prompts -> 사용자 뷰 설정 반환 (glossary는 사용자분만, sentence는 전체)
- POST /api/prompts/add-item -> 항목 추가 (즉시 반영)
- POST /api/prompts/delete-item -> 항목 삭제 (즉시 반영)
"""

import json
from typing import Optional

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from whisperlivekit.llm_translation.prompt_manager import TranslationPromptManager


def create_test_app():
    """테스트용 FastAPI 앱 생성 (parse_args 우회)."""
    from whisperlivekit.llm_translation import get_prompt_manager

    app = FastAPI()

    class PromptItemRequest(BaseModel):
        block_key: str
        origin: str
        translation: Optional[str] = None

    @app.get("/api/prompts")
    async def get_prompts():
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

    return app


app = create_test_app()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def isolated_prompt_manager(tmp_path):
    """각 테스트마다 새로운 격리된 TranslationPromptManager를 생성한다.

    전역 싱글톤 _prompt_manager를 재설정하고 테스트 단위로 독립적인 DB를 사용한다.
    """
    json_path = tmp_path / "admin_translation_glossary.json"
    db_path = tmp_path / "user_translation_glossary.db"
    json_path.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
    manager = TranslationPromptManager(base_json_path=str(json_path), db_path=str(db_path))

    import whisperlivekit.llm_translation as llm_translation_module
    original_manager = llm_translation_module._prompt_manager
    llm_translation_module._prompt_manager = manager

    yield manager

    llm_translation_module._prompt_manager = original_manager


def test_get_prompts_empty(client, isolated_prompt_manager):
    """GET /api/prompts - 빈 사용자 glossary + 기본 sentence_block 반환."""
    response = client.get("/api/prompts")
    assert response.status_code == 200
    data = response.json()
    assert data["glossary_block"] == {}
    assert "The ROK Air Force conducted joint air operations" in data["sentence_block"]


def test_post_add_glossary_item(client, isolated_prompt_manager):
    """POST /api/prompts/add-item - glossary_block 항목 추가."""
    response = client.post(
        "/api/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "해군", "translation": "ROKN"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_get_prompts_after_add_glossary(client, isolated_prompt_manager):
    """GET /api/prompts - 추가된 glossary 항목이 포함되어 반환되는지 확인."""
    client.post(
        "/api/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "해군", "translation": "ROKN"},
    )
    response = client.get("/api/prompts")
    data = response.json()
    assert data["glossary_block"] == {"해군": "ROKN"}


def test_post_add_sentence_item(client, isolated_prompt_manager):
    """POST /api/prompts/add-item - sentence_block 항목 추가."""
    response = client.post(
        "/api/prompts/add-item",
        json={"block_key": "sentence_block", "origin": "테스트 입력", "translation": "테스트 출력"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_add_item_invalid_block_key(client, isolated_prompt_manager):
    """POST /api/prompts/add-item - 잘못된 block_key는 400을 반환한다."""
    response = client.post(
        "/api/prompts/add-item",
        json={"block_key": "invalid_block", "origin": "x", "translation": "y"},
    )
    assert response.status_code == 400


def test_delete_glossary_item(client, isolated_prompt_manager):
    """POST /api/prompts/delete-item - glossary_block 항목 삭제."""
    client.post(
        "/api/prompts/add-item",
        json={"block_key": "glossary_block", "origin": "해군", "translation": "ROKN"},
    )
    response = client.post(
        "/api/prompts/delete-item",
        json={"block_key": "glossary_block", "origin": "해군"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_delete_nonexistent_item_returns_warning(client, isolated_prompt_manager):
    """POST /api/prompts/delete-item - 존재하지 않는 항목 삭제는 warning을 반환한다."""
    response = client.post(
        "/api/prompts/delete-item",
        json={"block_key": "glossary_block", "origin": "없는용어"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "warning"


def test_delete_item_invalid_block_key(client, isolated_prompt_manager):
    """POST /api/prompts/delete-item - 잘못된 block_key는 400을 반환한다."""
    response = client.post(
        "/api/prompts/delete-item",
        json={"block_key": "invalid_block", "origin": "x"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompts_api.py -v
```
Expected: import 자체는 성공(Task 2에서 이미 `get_prompt_manager` 존재)하므로, 이 목업 앱은 `basic_server.py`를 건드리지 않고 자체 완결적이라 **이미 PASS할 수 있음**. PASS되면 Step 3은 "basic_server.py에도 동일 라우트가 실제로 등록되는지"를 검증하는 게 목적이므로 계속 진행한다.

- [ ] **Step 3: `basic_server.py`에 실제 엔드포인트 추가**

Modify `whisperlivekit/basic_server.py` — import 블록:

old_string:
```python
from whisperlivekit import AudioProcessor, TranscriptionEngine, get_inline_ui_html, parse_args
from whisperlivekit.filtering import get_word_manager
```
new_string:
```python
from whisperlivekit import AudioProcessor, TranscriptionEngine, get_inline_ui_html, parse_args
from whisperlivekit.filtering import get_word_manager
from whisperlivekit.llm_translation import get_prompt_manager
```

Modify — `CorrectionUpdate` 모델 근처에 `PromptItemRequest` 추가:

old_string:
```python
class CorrectionUpdate(BaseModel):
    wrong_word: str
    correct_word: str
```
new_string:
```python
class CorrectionUpdate(BaseModel):
    wrong_word: str
    correct_word: str


class PromptItemRequest(BaseModel):
    block_key: str            # "glossary_block" 또는 "sentence_block"
    origin: str
    translation: Optional[str] = None
```

Modify — `delete_correction` 엔드포인트 바로 아래에 3개 엔드포인트 추가:

old_string:
```python
@app.delete("/api/corrections/{wrong_word}")
async def delete_correction(wrong_word: str):
    """단어 교정 삭제. 즉시 반영."""
    word_manager = get_word_manager()
    word_manager.delete_user_word(wrong_word)
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Transcript Save API  (/api/save-transcript) — 저장 버튼 클릭 시 프론트가 호출
# ---------------------------------------------------------------------------
```
new_string:
```python
@app.delete("/api/corrections/{wrong_word}")
async def delete_correction(wrong_word: str):
    """단어 교정 삭제. 즉시 반영."""
    word_manager = get_word_manager()
    word_manager.delete_user_word(wrong_word)
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Translation Glossary Management REST API  (/api/prompts)
# ---------------------------------------------------------------------------

@app.get("/api/prompts")
async def get_prompts():
    """사용자 뷰: glossary는 사용자 추가분만, sentence는 전체(기본+사용자) 반환."""
    return get_prompt_manager().get_user_view_settings()


@app.post("/api/prompts/add-item")
async def add_prompt_item(request: PromptItemRequest):
    """glossary_block 또는 sentence_block에 항목 추가. 즉시 반영."""
    if request.block_key not in ("glossary_block", "sentence_block"):
        raise HTTPException(status_code=400, detail="Invalid block key")
    get_prompt_manager().add_item(request.block_key, request.origin, request.translation)
    return {"status": "success"}


@app.post("/api/prompts/delete-item")
async def delete_prompt_item(request: PromptItemRequest):
    """glossary_block 또는 sentence_block에서 항목 삭제. 즉시 반영."""
    if request.block_key not in ("glossary_block", "sentence_block"):
        raise HTTPException(status_code=400, detail="Invalid block key")
    success = get_prompt_manager().remove_item(request.block_key, request.origin)
    if success:
        return {"status": "success"}
    return {"status": "warning", "message": "Item not found or cannot delete default glossary item"}


# ---------------------------------------------------------------------------
# Transcript Save API  (/api/save-transcript) — 저장 버튼 클릭 시 프론트가 호출
# ---------------------------------------------------------------------------
```

Modify — `HTTPException`이 최상단에 import돼 있는지 확인. 현재 `basic_server.py`는 `_convert_to_pcm` 내부에서 `from fastapi import HTTPException`을 지역 import하고 있으므로, 최상단 fastapi import에 추가해 정리한다:

old_string:
```python
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
```
new_string:
```python
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
```

`HTTPException`이 최상단에서 import되므로 `_convert_to_pcm` 안의 지역 import는 이제 중복이다 — 함께 제거한다:

old_string:
```python
    stdout, stderr = await proc.communicate(input=audio_bytes)
    if proc.returncode != 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {stderr.decode().strip()}")
    return stdout
```
new_string:
```python
    stdout, stderr = await proc.communicate(input=audio_bytes)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Audio conversion failed: {stderr.decode().strip()}")
    return stdout
```

- [ ] **Step 4: 테스트 재실행**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompts_api.py -v
```
Expected: 9개 테스트 전부 PASS.

- [ ] **Step 5: `basic_server.py` 임포트 정합성 확인 (서버 기동 없이)**

Run:
```powershell
.venv\Scripts\python.exe -c "import ast; ast.parse(open('whisperlivekit/basic_server.py', encoding='utf-8').read())"
```
Expected: 예외 없이 종료(문법 오류 없음 확인). **주의: 실제로 `basic_server.py`를 import/실행하면 `parse_args()`가 즉시 호출돼 CLI 인자 파싱 및 이후 서버 기동 경로를 탄다 — 이번 검증은 반드시 `ast.parse`(문법 검사만)로 제한하고, 모듈을 실제로 import하지 않는다.**

- [ ] **Step 6: 전체 회귀 테스트**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/test_prompt_manager.py tests/test_llm_translator.py tests/test_prompts_api.py tests/test_corrections_api.py -v
```
Expected: 전부 PASS(기존 단어교정 API 회귀 없음 확인).

- [ ] **Step 7: Commit**

```bash
git add whisperlivekit/basic_server.py tests/test_prompts_api.py
git commit -m "feat(translation): /api/prompts REST 엔드포인트 추가

GET /api/prompts, POST /api/prompts/add-item, POST /api/prompts/delete-item.
잘못된 block_key는 HTTPException(400)(기존 _convert_to_pcm과 동일 스타일),
삭제 대상 없음은 200+warning(wl 원본 유지). /api/corrections는 변경 없음."
```

---

### Task 5: 문서 정리 (ROADMAP.md 정정)

**Files:**
- Modify: `ROADMAP.md`

**Interfaces:** 없음(문서 전용)

- [ ] **Step 1: Phase 5 5-2 항목의 잘못된 참조 파일명 정정**

Modify `ROADMAP.md`:

old_string:
```
 5-1. 단어 교정 사전 동적 추가/삭제 기능 이식 [이식]
→ whisperlive_code/manager.py 기반 그대로
 5-2. 번역 Glossary 동적 추가/삭제 기능 이식 [이식]
→ whisperlive_code/manager.py 기반 그대로
```
new_string:
```
 5-1. 단어 교정 사전 동적 추가/삭제 기능 이식 [이식]
→ whisperlive_code/manager.py 기반 그대로
 ✅ 5-2. 번역 Glossary 동적 추가/삭제 기능 이식 [이식] (Stage 1 완료 — glossary_block+sentence_block)
→ whisperlive_code/prompt_manager.py 기반(TranslationPromptManager), whisperlivekit/llm_translation/에
  filtering/ 콜로케이션 패턴으로 이식. Qdrant RAG(유사 예시 검색)는 Stage 2로 별도 진행 예정
  (docs/superpowers/specs/2026-07-16-translation-glossary-design.md §8).
```

- [ ] **Step 2: Commit**

```bash
git add ROADMAP.md
git commit -m "docs: ROADMAP Phase 5-2 참조 파일 정정 + Stage 1 완료 표기

whisperlive_code/manager.py(단어교정용)를 잘못 참조하던 것을 실제 구현 근거인
prompt_manager.py로 정정. Stage 2(Qdrant RAG)는 별도 스펙으로 이어짐을 명시."
```

---

### Task 6: 최종 검증 및 정리

**Files:** 없음(검증 전용)

**Interfaces:** 없음

- [ ] **Step 1: 전체 테스트 스위트 실행 (경로C 안전 방식)**

Run:
```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```
Expected: 전체 테스트 PASS, FAIL 없음. (이 명령은 `basic_server.py`를 import/기동하지 않으므로 GPU 로드·VBCable 접근이 없다 — 다른 세션의 경로C 측정과 리소스 충돌 없음.)

- [ ] **Step 2: ruff lint 확인 (직접 호출, uv 경유 금지)**

Run:
```powershell
.venv\Scripts\ruff.exe check whisperlivekit/llm_translation/ whisperlivekit/basic_server.py tests/test_prompt_manager.py tests/test_prompts_api.py tests/test_llm_translator.py
```
Expected: `All checks passed!` 또는 스타일 경고만(에러 없음). 경고가 있으면 수정 후 재실행.

- [ ] **Step 3: 임시 산출물 정리 확인**

Run:
```powershell
git status --short
```
Expected: Task 1~5에서 의도한 파일들(코드·테스트·문서)만 변경 목록에 보임. `tmp_path` 기반 pytest 임시 데이터는 pytest가 테스트 세션 종료 시 자동 격리·정리하므로 워크트리에 흔적이 남지 않아야 한다 — 만약 의도치 않은 파일(수동 스크래치 파일 등)이 보이면 삭제한다.

- [ ] **Step 4: 최종 커밋 로그 확인**

Run:
```powershell
git log --oneline master..HEAD
```
Expected: Task 2~5의 커밋 4개(+워크트리 생성은 커밋 없음)가 순서대로 보임.

- [ ] **Step 5: 사용자에게 보고**

배포 PC 배치 안내를 포함해 보고한다: `whisperlivekit/llm_translation/admin_translation_glossary.json`과 `user_translation_glossary.db`를 배포 PC의 실제 파일로 교체하면 코드 변경 없이 즉시 활성화됨. `superpowers:finishing-a-development-branch` 스킬로 머지/PR 여부를 사용자와 결정한다(이 Task 자체는 병합을 수행하지 않음).

**문서 후속 확인 안내(자동 편집하지 않음)**: 스펙 §9에 따르면 `/api/prompts` 신규 엔드포인트를 프론트엔드 인계 문서에도 반영해야 하지만(CLAUDE.md 연동 갱신 문서 표 "번역 파이프라인 변경" 행), 이 작업 시점에 다른 세션이 `docs/FRONTEND_HANDOFF_SUMMARY.md`·`docs/DEPLOYMENT_OFFLINE.md`·`docs/SCHEMA_CHANGES.md`를 `worktrees/interim-translation`에서 실시간으로 편집 중이었다. 충돌을 피하기 위해 이 Task에서는 해당 문서를 건드리지 않았으므로, 그 작업이 머지된 뒤 `/api/prompts` 엔드포인트 반영 여부를 사용자에게 확인받아야 한다고 보고한다.
