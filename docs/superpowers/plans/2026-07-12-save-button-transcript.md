# 저장 버튼 방식 전사 저장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 녹음 중지 시 자동으로 전사를 저장하던 동작을 없애고, UI의 저장 버튼을 사용자가 클릭했을 때만
누적 전사를 서버 로컬 `.txt`로 저장하도록 바꾼다.

**Architecture:** 서버 쪽 `POST /api/save-transcript` 엔드포인트는 이미 범용(요청 body의 `lines`를 그대로
저장)이라 변경하지 않는다. 프론트엔드(`live_transcription.{html,css,js}`)에 새 저장 버튼을 추가하고,
기존에 `ready_to_stop` 핸들러 안에 있던 payload 생성 로직을 재사용 가능한 함수로 분리해 버튼 클릭
핸들러에 연결한다. 자동 호출 코드는 제거한다.

**Tech Stack:** 바닐라 JS(프레임워크 없음), FastAPI 서버(`whisperlivekit/basic_server.py`, 변경 없음),
Material Symbols 스타일 인라인 SVG 아이콘.

## Global Constraints

- 모든 응답·커밋 메시지는 한국어(코드 식별자·주석 제외) — 저장소 루트 CLAUDE.md.
- **main 브랜치에서 코드 편집 금지** — 이 플랜의 모든 코드 작업은 `worktrees/save-button-transcript`
  워크트리(브랜치 `feat/save-button-transcript`)에서 수행한다. `docs/superpowers/plans/`·`specs/`
  자체는 main에서 이미 커밋됨(화이트리스트 대상)이므로 이 플랜 문서 갱신 외 추가 main 편집 없음.
- 새 워크트리는 `.venv`를 새로 만들지 않는다 — 메인 저장소 `.venv`를 Windows Directory Junction으로
  연결(`mklink /J .venv ..\..\.venv`). 이 작업은 JS/HTML/CSS/문서만 건드리므로 Python 의존성 변경이
  전혀 없다 — `uv sync`/`uv add`/`uv run` 실행 금지(공유 venv 오염 방지, CLAUDE.md §4).
- 이 변경은 STT 정확도와 무관한 순수 UX 기능 — `/eval` 측정 대상 아님, `EXPERIMENTS.md`/`EXPERIMENTS_LOG.md`
  기록 불필요.
- 자동화된 JS 테스트 하네스가 이 프로젝트엔 없다(`tests/`는 pytest뿐, `package.json` 없음) — 프론트
  변경의 검증은 실제 서버 기동 후 브라우저 수동 시나리오로 한다(Task 4).
- 코드 변경과 동일 작업 단위로 관련 문서를 갱신한다(FRONTEND_HANDOFF.md·ROADMAP.md·
  DEPLOYMENT_OFFLINE.md·TESTING.md — Task 3에서 처리, CLAUDE.md "코드 변경 시 연동 갱신 문서" 표 원칙).

---

### Task 1: 저장 버튼 UI 마크업 + 스타일 + 아이콘

**Files:**
- Modify: `whisperlivekit/web/live_transcription.html:14-29`
- Modify: `whisperlivekit/web/live_transcription.css:239-244`
- Create: `whisperlivekit/web/src/save.svg`

**Interfaces:**
- Consumes: 없음(신규 마크업/스타일).
- Produces: DOM 요소 `#saveTranscriptButton`(class `settings-toggle`, 초기 `disabled` 속성 있음) —
  Task 2의 JS가 `document.getElementById("saveTranscriptButton")`로 참조.

- [ ] **Step 1: 저장 아이콘 SVG 파일 생성**

`whisperlivekit/web/src/save.svg` 신규 생성(기존 `settings.svg`와 동일한 Material Symbols 스타일):

```svg
<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px" fill="#5f6368"><path d="M840-680v480q0 33-23.5 56.5T760-120H200q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h480l160 160Zm-80 34L646-760H200v560h560v-446ZM480-240q50 0 85-35t35-85q0-50-35-85t-85-35q-50 0-85 35t-35 85q0 50 35 85t85 35ZM240-560h360v-160H240v160Zm-40-34v446-560 114Z"/></svg>
```

- [ ] **Step 2: HTML에 저장 버튼 마크업 추가**

`whisperlivekit/web/live_transcription.html`에서 다음 블록을 찾는다:

```html
                <button id="recordButton">
                    <div class="shape-container">
                        <div class="shape"></div>
                    </div>
                    <div class="recording-info">
                        <div class="wave-container">
                            <canvas id="waveCanvas"></canvas>
                        </div>
                        <div class="timer">00:00</div>
                    </div>
                </button>

                <button id="settingsToggle" class="settings-toggle" title="Show/hide settings">
                    <img src="web/src/settings.svg" alt="Settings" />
                </button>
```

다음으로 교체(recordButton과 settingsToggle 사이에 저장 버튼 삽입):

```html
                <button id="recordButton">
                    <div class="shape-container">
                        <div class="shape"></div>
                    </div>
                    <div class="recording-info">
                        <div class="wave-container">
                            <canvas id="waveCanvas"></canvas>
                        </div>
                        <div class="timer">00:00</div>
                    </div>
                </button>

                <button id="saveTranscriptButton" class="settings-toggle" title="전사 저장" disabled>
                    <img src="web/src/save.svg" alt="Save" />
                </button>

                <button id="settingsToggle" class="settings-toggle" title="Show/hide settings">
                    <img src="web/src/settings.svg" alt="Settings" />
                </button>
```

- [ ] **Step 3: CSS에 disabled 상태 스타일 추가**

`whisperlivekit/web/live_transcription.css`에서 다음 블록을 찾는다:

```css
.settings-toggle img {
  width: 20px;
  height: 20px;
}

@media (max-width: 10000px) {
```

다음으로 교체:

```css
.settings-toggle img {
  width: 20px;
  height: 20px;
}

.settings-toggle:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.settings-toggle:disabled:hover {
  background-color: var(--button-bg);
}

@media (max-width: 10000px) {
```

- [ ] **Step 4: 브라우저에서 마크업/스타일 수동 확인**

서버 기동(`whisperlivekit-server`) 후 `http://localhost:8000/` 접속(포트는 `parse_args.py` 기본값
확인 — 다르면 실제 기본 포트 사용). 브라우저 개발자도구로 확인:
- 녹음 버튼과 설정 버튼 사이에 새 원형 저장 버튼이 보인다.
- 저장 버튼이 흐리게(`opacity: 0.4`) 표시되고 `disabled` 속성이 있다(아직 JS 로직 없어 항상 disabled).
- 마우스 커서를 올리면 `not-allowed` 커서가 표시된다.

- [ ] **Step 5: Commit**

```bash
git add whisperlivekit/web/live_transcription.html whisperlivekit/web/live_transcription.css whisperlivekit/web/src/save.svg
git commit -m "feat(frontend): 전사 저장 버튼 마크업/스타일 추가"
```

---

### Task 2: JS 로직 — payload 빌더 분리, 자동저장 제거, 클릭 핸들러, 활성화 상태 관리

**Files:**
- Modify: `whisperlivekit/web/live_transcription.js:44` (element 참조 추가)
- Modify: `whisperlivekit/web/live_transcription.js:219-221` (헬퍼 함수 추가)
- Modify: `whisperlivekit/web/live_transcription.js:307-320` (자동 저장 제거)
- Modify: `whisperlivekit/web/live_transcription.js:377` (렌더 시 상태 갱신 호출)
- Modify: `whisperlivekit/web/live_transcription.js:554-556` (녹음 시작 시 상태 초기화)
- Modify: `whisperlivekit/web/live_transcription.js:831-834` (클릭 핸들러 등록)

**Interfaces:**
- Consumes: Task 1이 만든 `#saveTranscriptButton` DOM 요소, 기존 모듈 전역 `finalizedHistory`(Map),
  `lastReceivedData`(마지막 websocket 스냅샷), 기존 `statusText` 요소.
- Produces: `buildTranscriptPayload(): Array<{speaker:number, text:string, translation:string|undefined}>`,
  `updateSaveButtonState(): void` — 둘 다 이후 다른 코드가 재사용할 수 있는 모듈 전역 함수.

- [ ] **Step 1: 저장 버튼 element 참조 추가**

`whisperlivekit/web/live_transcription.js`에서 다음 줄을 찾는다:

```js
const statusText = document.getElementById("status");
const recordButton = document.getElementById("recordButton");
```

다음으로 교체:

```js
const statusText = document.getElementById("status");
const recordButton = document.getElementById("recordButton");
const saveTranscriptButton = document.getElementById("saveTranscriptButton");
```

- [ ] **Step 2: payload 빌더 + 상태 갱신 헬퍼 함수 추가**

다음 블록을 찾는다:

```js
websocketInput.addEventListener("change", () => {
  const urlValue = websocketInput.value.trim();
  if (!urlValue.startsWith("ws://") && !urlValue.startsWith("wss://")) {
    statusText.textContent = "Invalid WebSocket URL (must start with ws:// or wss://)";
    return;
  }
  websocketUrl = urlValue;
  statusText.textContent = "WebSocket URL updated. Ready to connect.";
});

function setupWebSocket() {
```

다음으로 교체(두 함수를 `setupWebSocket` 앞에 삽입):

```js
websocketInput.addEventListener("change", () => {
  const urlValue = websocketInput.value.trim();
  if (!urlValue.startsWith("ws://") && !urlValue.startsWith("wss://")) {
    statusText.textContent = "Invalid WebSocket URL (must start with ws:// or wss://)";
    return;
  }
  websocketUrl = urlValue;
  statusText.textContent = "WebSocket URL updated. Ready to connect.";
});

// 클릭 시점까지 확정된 누적 전사 + 최신 미확정 줄을 저장 payload로 변환.
// 저장 버튼 클릭 핸들러와 활성/비활성 상태 판정(updateSaveButtonState) 양쪽에서 재사용한다.
function buildTranscriptPayload() {
  return [...finalizedHistory.values(), ...((lastReceivedData && lastReceivedData.lines) || []).filter((l) => !l.finalized)]
    .filter((l) => l.speaker !== -2 && (l.text || l.translation))
    .map((l) => ({ speaker: l.speaker, text: (l.text || "").trim(), translation: (l.translation || "").trim() || undefined }));
}

function updateSaveButtonState() {
  saveTranscriptButton.disabled = buildTranscriptPayload().length === 0;
}

function setupWebSocket() {
```

- [ ] **Step 3: `ready_to_stop` 핸들러에서 자동 저장 제거**

다음 블록을 찾는다:

```js
        // 종료 시 누적 전사를 서버 로컬 폴더에 자동 저장 (fire-and-forget, 실패해도 종료 흐름 유지)
        const payload = [...finalizedHistory.values(), ...((lastReceivedData && lastReceivedData.lines) || []).filter((l) => !l.finalized)]
          .filter((l) => l.speaker !== -2 && (l.text || l.translation))
          .map((l) => ({ speaker: l.speaker, text: (l.text || "").trim(), translation: (l.translation || "").trim() || undefined }));
        if (payload.length) {
          fetch("/api/save-transcript", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ lines: payload }),
          })
            .then((r) => r.json())
            .then((d) => { statusText.textContent = `전사 기록 저장됨: ${d.path}`; })
            .catch((e) => { console.error("전사 저장 실패:", e); });
        }
```

다음으로 교체:

```js
        // 자동 저장은 하지 않는다 — 저장은 사용자가 저장 버튼을 눌렀을 때만 수행한다(buildTranscriptPayload 참조).
        updateSaveButtonState();
```

- [ ] **Step 4: 렌더 시마다 저장 버튼 상태 갱신**

다음 줄을 찾는다:

```js
  const mergedLines = [...finalizedHistory.values(), ...(lines || []).filter((l) => !l.finalized)];
```

다음으로 교체:

```js
  const mergedLines = [...finalizedHistory.values(), ...(lines || []).filter((l) => !l.finalized)];
  updateSaveButtonState();
```

- [ ] **Step 5: 녹음 시작 시 저장 버튼 비활성화**

다음 블록을 찾는다:

```js
async function startRecording() {
  finalizedHistory.clear();
  lastSignature = "";
```

다음으로 교체:

```js
async function startRecording() {
  finalizedHistory.clear();
  lastSignature = "";
  updateSaveButtonState();
```

- [ ] **Step 6: 저장 버튼 클릭 핸들러 등록**

다음 블록을 찾는다:

```js
settingsToggle.addEventListener("click", () => {
settingsDiv.classList.toggle("visible");
settingsToggle.classList.toggle("active");
});
```

다음으로 교체(클릭 핸들러를 뒤에 추가):

```js
settingsToggle.addEventListener("click", () => {
settingsDiv.classList.toggle("visible");
settingsToggle.classList.toggle("active");
});

saveTranscriptButton.addEventListener("click", async () => {
  const payload = buildTranscriptPayload();
  if (!payload.length) return;
  saveTranscriptButton.disabled = true;
  try {
    const res = await fetch("/api/save-transcript", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lines: payload }),
    });
    const data = await res.json();
    statusText.textContent = `전사 기록 저장됨: ${data.path}`;
  } catch (e) {
    console.error("전사 저장 실패:", e);
    statusText.textContent = "전사 저장 실패. 콘솔을 확인하세요.";
  } finally {
    updateSaveButtonState();
  }
});
```

- [ ] **Step 7: 브라우저에서 저장 흐름 수동 확인**

서버 기동 후 브라우저에서:
1. 녹음 시작 → 아직 확정 줄이 없으면 저장 버튼이 비활성 상태 유지되는지 확인.
2. 발화 후 확정 줄이 생기면 저장 버튼이 활성화(흐림 해제)되는지 확인.
3. 녹음 중 저장 버튼 클릭 → 상태 텍스트에 `전사 기록 저장됨: <경로>` 표시 확인, 서버
   `--transcript-save-dir`(기본 `./transcripts`) 폴더에 새 `.txt` 파일 생성 확인, 파일 내용이
   `[화자 N] 텍스트` 형식인지 확인.
4. 녹음 중지(정지 버튼) → 자동으로 새 `.txt`가 생기지 않는지 확인(파일 개수 그대로).
5. 새 녹음 시작 → 저장 버튼이 다시 비활성화되는지 확인.

- [ ] **Step 8: Commit**

```bash
git add whisperlivekit/web/live_transcription.js
git commit -m "feat(frontend): 전사 저장을 자동 저장에서 버튼 클릭 저장으로 변경"
```

---

### Task 3: 문서 갱신

**Files:**
- Modify: `docs/FRONTEND_HANDOFF.md:251`
- Modify: `docs/FRONTEND_HANDOFF.md:299-314`
- Modify: `ROADMAP.md:199`
- Modify: `docs/DEPLOYMENT_OFFLINE.md:380`
- Modify: `docs/TESTING.md:39`

**Interfaces:**
- Consumes: 없음(문서 전용, Task 1/2의 코드 결과를 서술).
- Produces: 없음(다른 태스크가 이 문서를 소비하지 않음).

- [ ] **Step 1: FRONTEND_HANDOFF.md §7 체크리스트 항목 정정**

다음 줄을 찾는다:

```markdown
- [ ] 녹음 종료 시 `POST /api/save-transcript` 호출(§10) — 내장 UI와 동일하게 자동 저장하면 저장 로직이 통일된다.
```

다음으로 교체:

```markdown
- [ ] 저장 버튼 클릭 시 `POST /api/save-transcript` 호출(§10) — 내장 UI와 동일하게 버튼 클릭으로만 저장하면 저장 로직이 통일된다(자동 저장 아님).
```

- [ ] **Step 2: FRONTEND_HANDOFF.md §10 섹션 전체 정정**

다음 블록을 찾는다:

```markdown
## 10. REST API — 전사 저장 (`/api/save-transcript`)

WS `/asr`와 별개로, 녹음 종료 시 누적 전사를 **서버 로컬 파일**로 저장하는 REST 엔드포인트다
(브라우저 다운로드가 아니라 서버 프로세스가 디스크에 씀). 단어 교정 API(`/api/corrections`,
[SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) §4)와 동일한 REST 계열이며, 내장 UI는 `ready_to_stop` 수신 직후
자동 호출한다([live_transcription.js:307-320](../whisperlivekit/web/live_transcription.js#L307-L320)).

| 메서드/경로 | 요청 body | 응답 | 비고 |
|---|---|---|---|
| `POST /api/save-transcript` | `{"lines":[{"speaker":int,"text":str,"translation":str\|undefined}, ...]}` | `{"status":"success","path":str,"line_count":int}` | 저장 경로는 서버 `--transcript-save-dir`(기본 `./transcripts`); 파일명 `transcript_YYYYMMDD_HHMMSS.txt` |

- 서버 구현: [basic_server.py](../whisperlivekit/basic_server.py) `save_transcript()`.
- txt 형식은 화자+텍스트(+번역)만 담는다(타임스탬프 없음): `[화자 N] 텍스트` 다음 줄에 `    ↳ 번역`(있을 때만).
- **React 권장 흐름**: `ready_to_stop` 처리 시 §2의 누적 history(`finalized` 줄 전체) + 마지막 미확정 줄을 합쳐
  `lines` payload로 구성해 fire-and-forget으로 호출(await/블로킹 금지 — 실패해도 녹음 종료 흐름을 막지 않아야 함).
  이렇게 하면 내장 UI와 React의 저장 로직이 통일된다.
```

다음으로 교체:

```markdown
## 10. REST API — 전사 저장 (`/api/save-transcript`)

WS `/asr`와 별개로, 사용자가 UI의 저장 버튼을 눌렀을 때 누적 전사를 **서버 로컬 파일**로 저장하는
REST 엔드포인트다(브라우저 다운로드가 아니라 서버 프로세스가 디스크에 씀). 단어 교정 API
(`/api/corrections`, [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) §4)와 동일한 REST 계열이며, 내장 UI는
저장 버튼(`#saveTranscriptButton`) 클릭 시에만 호출한다(`live_transcription.js`의
`buildTranscriptPayload()` + 클릭 핸들러). **녹음 종료(`ready_to_stop`) 시 자동 호출하지 않는다** —
버튼을 누르지 않으면 저장되지 않는다.

| 메서드/경로 | 요청 body | 응답 | 비고 |
|---|---|---|---|
| `POST /api/save-transcript` | `{"lines":[{"speaker":int,"text":str,"translation":str\|undefined}, ...]}` | `{"status":"success","path":str,"line_count":int}` | 저장 경로는 서버 `--transcript-save-dir`(기본 `./transcripts`); 파일명 `transcript_YYYYMMDD_HHMMSS.txt` |

- 서버 구현: [basic_server.py](../whisperlivekit/basic_server.py) `save_transcript()`.
- txt 형식은 화자+텍스트(+번역)만 담는다(타임스탬프 없음): `[화자 N] 텍스트` 다음 줄에 `    ↳ 번역`(있을 때만).
- 저장 버튼은 녹음 중에도 클릭 가능하며, 클릭 시점까지의 전체 누적 내용을 매번 새 타임스탬프 파일로
  저장한다(직전 저장 이후 증분만 골라내지 않음 — 같은 문장이 여러 파일에 중복 저장될 수 있음, 의도된
  동작).
- **React 권장 흐름**: 저장 버튼(또는 동등 UI)을 두고, 클릭 시 §2의 누적 history(`finalized` 줄 전체) +
  마지막 미확정 줄을 합쳐 `lines` payload로 구성해 호출한다. `ready_to_stop`에 자동 연결하지 않는다 —
  이렇게 하면 내장 UI와 React의 저장 로직(버튼 트리거)이 통일된다.
```

- [ ] **Step 3: ROADMAP.md 정정**

다음 줄을 찾는다:

```markdown
→ /api/save-transcript POST 연결 완료 (녹음 종료 시 전사 .txt 자동 저장, `--transcript-save-dir`)
```

다음으로 교체:

```markdown
→ /api/save-transcript POST 연결 완료 (UI 저장 버튼 클릭 시 전사 .txt 저장, `--transcript-save-dir`)
```

- [ ] **Step 4: DEPLOYMENT_OFFLINE.md 정정**

다음 줄을 찾는다:

```markdown
- 녹음을 멈추면 내장 UI가 누적 전사를 서버 로컬 폴더(`--transcript-save-dir`, 기본값 `./transcripts`)에 `.txt`로 자동 저장한다.
```

다음으로 교체:

```markdown
- 저장 버튼을 누르면 내장 UI가 그 시점까지의 누적 전사를 서버 로컬 폴더(`--transcript-save-dir`, 기본값 `./transcripts`)에 `.txt`로 저장한다(녹음 종료 시 자동 저장되지 않음).
```

- [ ] **Step 5: TESTING.md 정정**

다음 줄을 찾는다:

```markdown
- 녹음 종료 시 내장 UI가 누적 전사를 `--transcript-save-dir`(기본값 `./transcripts`) 폴더에 `.txt`로 자동 저장한다 (`POST /api/save-transcript`).
```

다음으로 교체:

```markdown
- 저장 버튼 클릭 시 내장 UI가 그 시점까지의 누적 전사를 `--transcript-save-dir`(기본값 `./transcripts`) 폴더에 `.txt`로 저장한다 (`POST /api/save-transcript`, 녹음 중에도 클릭 가능, 녹음 종료 시 자동 저장 아님).
```

- [ ] **Step 6: grep으로 잔여 stale 참조 확인**

```bash
grep -rn "자동 저장\|녹음 종료 시.*save-transcript" docs/ ROADMAP.md
```

기대 결과: 위 5곳 외에 "자동 저장"이라는 표현이 `/api/save-transcript`와 연결된 곳이 더 없어야
한다(다른 무관한 문맥의 "자동"은 무시).

- [ ] **Step 7: Commit**

```bash
git add docs/FRONTEND_HANDOFF.md ROADMAP.md docs/DEPLOYMENT_OFFLINE.md docs/TESTING.md
git commit -m "docs: 전사 저장이 자동 저장 아닌 버튼 클릭 저장임을 반영"
```

---

### Task 4: 최종 회귀 확인 + 브랜치 마무리

**Files:**
- 없음(검증 전용, 코드/문서 변경 없음).

**Interfaces:**
- Consumes: Task 1~3의 전체 결과물.
- Produces: 없음(검증 결과만 보고).

- [ ] **Step 1: ruff lint 확인**

```bash
.venv\Scripts\ruff.exe check .
```

Expected: 기존과 동일한 결과(이 플랜은 Python 코드를 건드리지 않으므로 새 위반 없어야 함).

- [ ] **Step 2: pytest 회귀 확인**

```bash
.venv\Scripts\python.exe -m pytest tests/ -q
```

Expected: 기존 통과/스킵 수와 동일(서버 코드 변경 없음 — 새 실패 없어야 함).

- [ ] **Step 3: 서버 기동 후 전체 시나리오 재확인**

```bash
.venv\Scripts\whisperlivekit-server.exe
```

브라우저로 접속해 Task 1 Step 4 + Task 2 Step 7의 시나리오를 처음부터 끝까지 한 번 더 통째로
수행(녹음 시작 → 저장 버튼 비활성 확인 → 발화 → 활성화 확인 → 저장 클릭 → 파일 생성 확인 → 녹음
중지 → 자동 저장 없음 확인 → 재녹음 시작 → 버튼 다시 비활성화 확인).

- [ ] **Step 4: 최종 상태 확인**

```bash
git status
git log --oneline -5
```

Expected: `feat/save-button-transcript` 브랜치에 Task 1~3의 커밋 3개가 순서대로 있고, working tree
clean.
