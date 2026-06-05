# `/log-session` 커맨드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/log-session` 슬래시 커맨드를 만들어 세션 종료 시 대화 내용을 3층 레이어드 마크다운으로 `.omc/session-logs/`에 저장한다.

**Architecture:** Claude Code 슬래시 커맨드는 `.claude/commands/<name>.md` 파일 하나로 구현된다. 파일 안에 Claude가 따를 지침을 한국어로 작성하고, Claude가 실행 시 현재 대화 컨텍스트를 읽어 마크다운을 생성·저장한다. 별도 Python 코드나 라이브러리는 불필요하다.

**Tech Stack:** Markdown (Claude Code slash command), `.gitignore`

---

## 파일 목록

| 작업 | 경로 | 역할 |
|------|------|------|
| 수정 | `.gitignore` | `.omc/session-logs/` 제외 항목 추가 |
| 생성 | `.claude/commands/log-session.md` | 슬래시 커맨드 지침 파일 |

---

## Task 1: `.gitignore`에 세션 로그 디렉토리 추가

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: `.gitignore` 하단 OMC 섹션에 한 줄 추가**

  현재 `.gitignore` 하단 OMC 블록:
  ```
  # OMC 런타임 상태 — 세션·체크포인트·메모리 등 매 실행마다 변하는 파일들
  .omc/state/
  .omc/sessions/
  .omc/project-memory.json
  .omc/benchmarks/*.log
  ```

  아래와 같이 `.omc/session-logs/` 줄을 추가한다:
  ```
  # OMC 런타임 상태 — 세션·체크포인트·메모리 등 매 실행마다 변하는 파일들
  .omc/state/
  .omc/sessions/
  .omc/project-memory.json
  .omc/benchmarks/*.log
  .omc/session-logs/
  ```

- [ ] **Step 2: 변경 확인**

  ```powershell
  git diff .gitignore
  ```

  예상 출력:
  ```diff
  +.omc/session-logs/
  ```

- [ ] **Step 3: 커밋**

  ```powershell
  git add .gitignore
  git commit -m "chore: .omc/session-logs/ gitignore 추가"
  ```

---

## Task 2: 슬래시 커맨드 파일 작성

**Files:**
- Create: `.claude/commands/log-session.md`

- [ ] **Step 1: 커맨드 파일 생성**

  `.claude/commands/log-session.md`를 아래 내용으로 생성한다:

  ````markdown
  ---
  description: 현재 세션의 대화 내용을 3층 레이어드 마크다운으로 .omc/session-logs/에 저장한다
  ---

  이번 세션의 대화 전체를 검토해 구조화된 세션 기록을 작성해줘.

  ## 실행 순서

  1. **세션 유형 자동 감지** — 아래 기준으로 판단한다:
     - `dev` (개발): 파일 수정/생성, 코드 변경, 디버깅, 테스트 실행이 포함된 경우
     - `qa` (Q&A): 코드 변경 없이 질문·답변 중심, 개념/도구 설명 위주
     - `exp` (탐색·설계): 브레인스토밍, 아키텍처 토론, 계획 수립, 문서 설계
     - `mix` (혼합): 위 유형 2개 이상이 실질적으로 섞인 경우

  2. **파일명 결정** — `YYYY-MM-DD_HHmm_<유형약자>_<주제-슬러그>.md`
     - 날짜·시각: 오늘 날짜와 현재 시각
     - 주제 슬러그: 세션 내용을 보고 3~4 단어로 한국어 생성 (예: `문장-확정-로직`, `폐쇄망-패키징`)

  3. **`.omc/session-logs/` 디렉토리가 없으면 생성**

  4. **아래 3층 구조로 마크다운 작성** — 의미 없는 섹션은 생략하되, `한눈에 보기`와 `다음 세션을 위해`는 항상 포함한다

  ---

  ## 출력 구조

  ### 공통 상단 (모든 유형)

  ```markdown
  # 세션 기록: YYYY-MM-DD HH:MM

  ## 한눈에 보기

  **세션 유형**: (dev | qa | exp | mix 중 하나, 한국어 명칭 포함)
  **핵심 결정/답변**: (한 줄 요약)
  **변경 파일 목록**: (코드 변경이 없으면 이 항목 생략)
  - `경로/파일.py` — 수정: 한 줄 설명
  - `경로/파일2.py` — 신규
  ```

  ---

  ### 상세 내용 — 개발 세션 (dev)

  ```markdown
  ## 상세 내용

  ### 1. 문제 정의
  (어떤 버그/요구사항/이슈였는가)

  ### 2. 분석 과정
  (Claude의 사고 방식, 검토한 여러 옵션, 기각 이유)

  ### 3. 결정 근거
  (왜 이 방안을 선택했는가, 트레이드오프)

  ### 4. 구현 내용

  **변경 파일: `경로/파일.py`**
  ```diff
  - 이전 코드
  + 새 코드
  ```
  (diff가 너무 길면 핵심 변경 부분만 발췌하고 "이하 생략" 표시)

  ### 5. 결과 & 검증
  (수행 결과, 테스트/eval 결과, 잔여 이슈)
  ```

  ---

  ### 상세 내용 — Q&A 세션 (qa)

  ```markdown
  ## 상세 내용

  ### 질문 배경
  (왜 이 질문이 필요했는가)

  ### 핵심 질문과 답변
  **Q**: (질문)
  **A**: (Claude의 답변 요약)

  ### 후속 구체화
  (이어진 질문/답변으로 어떻게 이해가 깊어졌는가)

  ### 최종 이해 / 결론
  (이 세션 후 도달한 최종 이해 또는 결정)
  ```

  ---

  ### 상세 내용 — 탐색·설계 세션 (exp)

  ```markdown
  ## 상세 내용

  ### 탐색 주제
  (무엇을 탐색/설계하려 했는가)

  ### 발견사항
  (코드베이스 분석, 문서 검토, 제약 발견 등)

  ### 토론 요약
  (제안된 접근법들, 트레이드오프 비교)

  ### 결론 / 결정 사항
  (최종으로 합의된 방향, 채택/기각 사유)

  ### 보류 사항
  (결정 못 한 것, 추가 정보가 필요한 것 — 없으면 생략)
  ```

  ---

  ### 상세 내용 — 혼합 세션 (mix)

  ```markdown
  ## 상세 내용

  (시간 순서로 파트를 구분해 각 파트에 해당 유형의 섹션 구조를 적용한다)

  ### 파트 1: [개발 | Q&A | 탐색·설계]
  (해당 유형의 섹션 구조 그대로 적용)

  ### 파트 2: [개발 | Q&A | 탐색·설계]
  ...
  ```

  ---

  ### 공통 하단 (모든 유형)

  ```markdown
  ## 다음 세션을 위해

  **미결 사항**: (없으면 생략)
  - [ ] ...

  **이어서 할 것**: (없으면 생략)
  - ...

  **열린 질문**: (없으면 생략)
  - ...
  ```

  ---

  ## 저장 및 확인

  5. 위 구조로 작성한 내용을 `.omc/session-logs/<파일명>.md`에 저장한다.
  6. 저장된 파일 경로를 출력한다.
  7. 수정하거나 추가할 내용이 있는지 사용자에게 확인을 구한다.
  ````

- [ ] **Step 2: 파일 생성 확인**

  ```powershell
  Get-Content .claude\commands\log-session.md | Select-Object -First 5
  ```

  예상 출력:
  ```
  ---
  description: 현재 세션의 대화 내용을 3층 레이어드 마크다운으로 .omc/session-logs/에 저장한다
  ---

  이번 세션의 대화 전체를 검토해 구조화된 세션 기록을 작성해줘.
  ```

- [ ] **Step 3: 커밋**

  ```powershell
  git add .claude\commands\log-session.md
  git commit -m "feat: /log-session 세션 기록 슬래시 커맨드 추가"
  ```

---

## Task 3: 동작 검증

**Files:** 없음 (수동 실행 검증)

- [ ] **Step 1: 커맨드 실행**

  현재 세션(이 `/log-session` 구현 세션 자체)에서 커맨드를 실행한다:

  `/log-session`

- [ ] **Step 2: 출력 확인**

  다음 사항을 확인한다:
  - 세션 유형이 올바르게 감지됐는가 (`exp` 또는 `mix` 예상)
  - `한눈에 보기` 섹션에 핵심 결정이 한 줄로 요약됐는가
  - `다음 세션을 위해` 섹션이 포함됐는가
  - 파일이 `.omc/session-logs/` 아래에 생성됐는가

  ```powershell
  Get-ChildItem .omc\session-logs\
  ```

  예상: 날짜_시각_exp_log-session-커맨드-구현.md (또는 유사한 이름) 파일 1개 생성

- [ ] **Step 3: 파일 내용 열기**

  IDE 또는 에디터에서 생성된 파일을 열어 구조가 설계 문서와 일치하는지 육안 확인한다.
