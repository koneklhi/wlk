---
name: code-guide
description: WLK 프로젝트 코드 설명 에이전트 - 아키텍처/기능/파일/이식 대상을 실행 흐름 중심으로 설명하고, 자연어 질문으로 특정 기능의 코드 위치를 찾아 설명한다. 호출: /code-guide [arch|feature|file|port|where] [대상]
---

# WLK 코드 가이드 에이전트

이 스킬은 WhisperLiveKit 기반 STT 시스템의 코드 흐름을 모드별로 설명한다.

## 사용법

```
/code-guide arch                              # 전체 아키텍처 E2E 흐름
/code-guide feature <이름>                    # 특정 기능의 코드 흐름
/code-guide file <경로>                       # 특정 파일 설명
/code-guide port <모듈명>                     # whisperlive_code 이식 대상 분석
/code-guide where <자연어 설명>               # 특정 기능이 구현된 코드 위치 + 설명
```

---

## 실행 지침

스킬이 호출되면 다음 순서로 진행한다.

### STEP 1: 모드 파싱

사용자 입력(args)에서 첫 번째 단어를 모드로, 나머지를 대상(target)으로 파싱한다.

- `arch` → 전체 아키텍처 흐름 모드
- `feature <이름>` → 기능 흐름 모드
- `file <경로>` → 파일 설명 모드
- `port <모듈명>` → 이식 대상 분석 모드
- `where <자연어>` → 코드 위치 탐색 + 설명 모드
- 모드 없이 호출 시 → 사용법 출력

---

### STEP 2: 모드별 사전 로드 파일

#### `arch` 모드
아래 파일을 순서대로 읽은 뒤 전체 E2E 흐름을 설명한다:

1. `0.Metafile/WLK_INTERNALS.md` — 내부 구조 메모
2. `whisperlivekit/basic_server.py` — FastAPI WebSocket 진입점
3. `whisperlivekit/audio_processor.py` — 오디오 처리 파이프라인
4. `whisperlivekit/core.py` — TranscriptionEngine, 모델 초기화

설명 범위: 클라이언트 WebSocket 연결 → 오디오 청크 수신 → VAD 처리 → Whisper 추론 → 결과 JSON 송출

---

#### `feature <이름>` 모드

아래 매핑에 따라 탐색할 파일을 결정한다. 매핑에 없는 이름은 코드베이스 전체에서 검색한다.

| feature 이름 | 탐색 파일 |
|---|---|
| `translation` | `whisperlive_code/translator.py`, `whisperlive_code/prompt_manager.py` |
| `vad` | `whisperlivekit/silero_vad_iterator.py` |
| `sentence-confirm` | `whisperlivekit/local_agreement/` (디렉터리 전체) |
| `filtering` | `whisperlive_code/filtering____init__.py` |
| `glossary` | `whisperlive_code/manager.py` |
| `websocket` | `whisperlivekit/basic_server.py` |
| `audio-pipeline` | `whisperlivekit/audio_processor.py` |
| 그 외 | 키워드로 코드베이스 전체 grep 후 관련 파일 탐색 |

---

#### `file <경로>` 모드

1. 지정된 파일을 읽는다
2. 해당 파일을 import하거나 호출하는 파일을 추가로 탐색한다
3. 파일의 클래스, 함수, 핵심 로직 흐름을 설명한다

---

#### `port <모듈명>` 모드

1. `whisperlive_code/<모듈명>` 읽기
2. `whisperlivekit/` 코드베이스에서 연결 지점 탐색
3. 이식 시 어느 파일 어느 위치에 어떻게 통합되어야 하는지 매핑하여 출력

---

#### `where <자연어 설명>` 모드

자연어로 기능을 설명하면 해당 기능이 구현된 코드 위치를 찾아 스니펫과 설명을 제공한다.

1. 자연어 설명에서 핵심 키워드를 추출한다 (예: "문장 확정" → `finalize`, `commit`, `confirmed`, `local_agreement`)
2. Explore 에이전트를 사용해 키워드로 코드베이스를 검색한다
3. 관련 코드 섹션을 `파일:라인`으로 특정한다
4. 각 위치에서 5~15줄의 핵심 스니펫을 인용하고 한국어로 설명한다
5. 관련 위치가 여러 곳이면 모두 나열한다 (최대 3곳)
6. 이 코드에 도달하는 호출 경로를 간략히 추가한다

**키워드 추출 예시:**

| 자연어 질문 | 검색 키워드 |
|---|---|
| 문장이 확정되는 시점 | `finalize`, `confirmed`, `is_final`, `commit`, `local_agreement` |
| VAD가 음성을 감지하는 곳 | `vad`, `detect`, `speech`, `silero`, `voice_activity` |
| 번역 요청이 LLM에 전달되는 코드 | `translate`, `llm`, `prompt`, `llama`, `generate` |
| 환각 문장이 제거되는 위치 | `filter`, `hallucination`, `remove`, `filtering` |
| WebSocket으로 결과가 송출되는 곳 | `send`, `emit`, `websocket`, `json`, `result` |

---

### STEP 3: Explore 에이전트 디스패치

파일 탐색이 필요하면 `feature-dev:code-explorer` 또는 `oh-my-claudecode:explore` 에이전트를 활용한다.
에이전트에 전달할 컨텍스트에는 아래 프로젝트 배경을 포함한다:

```
프로젝트: WhisperLiveKit 기반 실시간 STT 시스템 (한국어/영어)
핵심 구조:
- whisperlivekit/ : FastAPI + WebSocket + Whisper ASR 파이프라인
- whisperlive_code/ : 이식 예정 기존 코드 (번역, 필터링, glossary)
목표: 코드 실행 흐름을 단계별로 파악하여 새 기능 구현 위치 결정
```

---

### STEP 4: 출력 형식

**모든 모드에서 아래 형식으로 출력한다.**

```
## [모드]: [대상]

### 진입점
- 파일: path/to/file.py:LINE
- 함수: function_name()

### 실행 흐름
1. 단계 설명 → [file.py:function()](path/to/file.py#LLINE)
2. 단계 설명 → [file.py:function()](path/to/file.py#LINE)
3. ...

### 핵심 데이터 구조
- ClassName / dict key: 역할 설명

### 외부 연결점
- 연결 모듈/기능: 연결 방식 설명
```

**규칙 (arch / feature / file / port 모드):**
- 파일 경로는 `[file.py:LINE](상대경로#LINE)` 마크다운 링크로 작성 (VSCode 클릭 이동 가능)
- 실행 흐름은 최소 5단계 이상 구체적으로 작성
- 코드 스니펫은 핵심 시그니처만 인용 (블록 전체 인용 금지)
- 한국어로 출력

---

**`where` 모드 전용 출력 형식 (아래 구조로 출력):**

    ## where: <질문>

    ### 구현 위치 #1
    - 파일: [path/to/file.py:LINE](path/to/file.py#LINE)
    - 함수/클래스: function_name()

    ```python
    # 핵심 코드 스니펫 (5~15줄, 실제 파일에서 인용)
    ```

    설명: 이 코드가 하는 일 2~4줄 설명

    ---

    ### 구현 위치 #2 (관련 코드가 여러 곳인 경우, 최대 3곳)
    ...

    ---

    ### 이 코드에 도달하는 경로
    - 호출자A() → 호출자B() → 여기

**`where` 모드 규칙:**
- 코드 스니펫은 반드시 실제 파일에서 읽어서 인용 (추측 금지)
- 설명은 "이 코드가 **왜** 여기 있는지", "**무엇을** 하는지" 중심으로 작성
- 관련 위치가 없을 경우 "해당 기능을 구현한 코드를 찾지 못했습니다. 다음 키워드로 직접 검색해보세요: [키워드 목록]" 출력

---

## 프로젝트 주요 파일 참조

| 파일 | 역할 |
|---|---|
| `whisperlivekit/basic_server.py` | FastAPI 앱, WebSocket `/asr` 엔드포인트 |
| `whisperlivekit/audio_processor.py` | 오디오 청크 처리, VAD, Whisper 호출 |
| `whisperlivekit/core.py` | `TranscriptionEngine` 싱글톤, 모델 초기화 |
| `whisperlivekit/silero_vad_iterator.py` | 음성 활동 감지(VAD) |
| `whisperlivekit/local_agreement/` | 토큰 확정(Local Agreement) 로직 |
| `whisperlivekit/parse_args.py` | CLI 인자 파서 |
| `whisperlive_code/translator.py` | LLM 기반 번역 파이프라인 |
| `whisperlive_code/prompt_manager.py` | 번역 프롬프트 관리 |
| `whisperlive_code/manager.py` | Glossary 동적 관리 |
| `whisperlive_code/filtering____init__.py` | 환각 제거 + 단어 대치 필터 |
| `0.Metafile/WLK_INTERNALS.md` | 내부 구조 메모 |
