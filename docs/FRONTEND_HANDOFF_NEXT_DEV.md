# 배포 UI ↔ 백엔드 연동 핸드오프 (신규 프론트엔드 개발자용)

- 작성: 백엔드팀
- 날짜: 2026-07-19
- 대상: **배포 PC(폐쇄망) React UI를 이어받는 신규 프론트엔드 개발자** (이전 dist를 만든 개발자와 다른 사람)

---

## 0. 요약 (TL;DR)

이전 개발자가 만든 React 빌드 산출물(dist)을 폐쇄망 배포 PC에서 백엔드(`whisperlivekit`, FastAPI)와 연결하는
과정에서 이슈가 여러 건 있었다. **백엔드에서 처리 가능한 것(렌더링·WebSocket 주소·API 경로)은 백엔드에서
해결**했고 일부는 임시 우회(서버측 shim/alias) 중이다. **프론트 재빌드가 필요한 이슈 5건**이 남아 있으며 이
문서 §4에 증상·원인·요구사항을 담았다. 현재 실사용 핵심 기능(전사·번역·단어대치·번역사전)은 우회책으로
동작하는 상태다.

**당신이 해야 할 일 = §4 (프론트 수정 5건).** §2(백엔드 계약)·§3(해결된 것)은 배경으로 먼저 읽어라.

---

## 1. 시스템 개요

- **무엇**: 실시간 STT(음성→텍스트) + 번역 시스템. 한국어/영어 두 언어 대상.
- **백엔드**: Python FastAPI(`whisperlivekit`), 단일 프로세스. 배포 PC에서 `python -m whisperlivekit.basic_server --lan auto`로 기동, 포트 **8900**.
- **배포 환경**: **폐쇄망(인터넷 차단) Windows PC 1대**. 사용자는 그 PC의 브라우저에서 `http://localhost:8900` 접속(단일 PC 로컬).
- **프론트**: React(Vite) dist. **백엔드가 dist를 same-origin으로 직접 서빙**한다(별도 웹서버·Nginx 없음). dist는 배포 PC의 `C:\whist\wlk\frontend\static\`(`index.html` + `assets/`)에 위치.
- ⚠️ **폐쇄망 배포 PC의 브라우저는 구버전일 수 있다** — 최신 브라우저에만 있는 기능(상대 WebSocket URL 등)에 의존하면 깨진다(§4-4).

---

## 2. 백엔드 계약 (Contract) — 프론트가 지켜야 할 것

### 2-1. 정적 서빙 / base 경로
- 백엔드가 `index.html`의 자산 참조에서 **빌드 base(`/wlkies`)를 자동 감지**해 그 하위로 서빙한다.
  `GET /` → `/wlkies/` 리다이렉트. `/wlkies/*`의 실제 파일 없는 경로는 **SPA fallback**으로 `index.html` 반환.
- 즉 **현재 Vite `base: '/wlkies'` 빌드가 그대로 동작**한다. base를 바꿔도(예: `/`) 백엔드가 자동 재감지하므로
  프론트는 base를 자유롭게 정해도 된다(단, `/`로 바꾸면 §4-3 관리자 URL 문제도 자연히 단순해질 수 있음).

### 2-2. WebSocket (전사) — **중요: 연결당 1회성 세션**
- 엔드포인트: **`ws://<origin>/asr`** (same-origin. 배포에선 `ws://localhost:8900/asr`).
- 쿼리 파라미터: `?language=auto|ko|en`(세션 언어, §4-5), `?mode=full|diff`.
- **연결당 전사 세션 1회**: 클라이언트가 **빈 프레임(0바이트)**을 보내면 서버가 그 세션을 **영구 종료**하고
  `{ "type": "ready_to_stop" }`를 보낸다. **같은 WS 연결에서는 다시 전사할 수 없다.** → 재시작하려면
  **새 WS 연결을 열어야 한다**(§4-1 핵심).
- 서버→클라 메시지:
  - `{ "type": "config", "useAudioWorklet", "mode", "language" }` — 연결 직후 1회.
  - 상태 스냅샷 — `lines[]`(확정/미확정 세그먼트), `buffer_transcription/diarization/translation`, `status` 등.
  - `{ "type": "ready_to_stop" }` — 세션 종료 확인.
- 오디오 전송: MediaRecorder **WebM** Blob을 그대로 `ws.send()`(서버 기본 `--pcm-input` 미지정 → WebM 경로).

### 2-3. REST
- `GET /health` → `{ "status", "backend", "ready" }`.
- **단어 대치 사전**: `GET /api/corrections`, `POST /api/corrections`(body `{wrong_word, correct_word}`),
  `DELETE /api/corrections/{wrong_word}`.
- **번역 사전(glossary/sentence)**: **정본** = `GET /api/prompts`, `POST /api/prompts/add-item`,
  `POST /api/prompts/delete-item`. (현재 dist는 `/api/corrections/prompts*`로 호출하는데, 백엔드가 이를
  **alias로도 수용** 중 — §3-C.)

> 스키마·엔드포인트 상세 정본: [API_SPEC.md](API_SPEC.md), [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md),
> [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md), [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md).

---

## 3. 이미 해결한 이슈 (백엔드 조치 완료) — 프론트 필수 조치 없음

| # | 증상 | 원인 | 백엔드 조치 | 프론트 권장(선택) |
|---|---|---|---|---|
| A | UI 백지, 콘솔 `Failed to load module script ... MIME type "text/html"` | dist가 `/wlkies/assets/*`를 절대참조하는데 백엔드가 루트 `/`에서만 서빙 → 자산 요청이 SPA fallback에 걸려 HTML 반환 | base(`/wlkies`) 자동감지 서빙 + `/`→`/wlkies/` 리다이렉트 | 없음(완료) |
| B | 전사 안 됨, 콘솔 `Failed to construct 'WebSocket': The URL '/asr' is invalid` | 프론트가 상대 URL `new WebSocket('/asr')` 사용 → 구형 브라우저가 거부 | `index.html`에 WS URL 정규화 shim 주입(상대 `/asr` → 절대 `ws://host/asr`) | **§4-4: 절대 URL로 조립하면 shim 불필요** |
| C | 관리자 번역사전 저장 시 콘솔 405/404 (`/api/corrections/prompts`, `/api/corrections/prompts/add-item`) | 프론트가 `CORRECTIONS_URL` 기반으로 `/api/corrections/prompts*` 조립(정본은 `/api/prompts*`) | `/api/corrections/prompts*` alias 라우트 추가 | 선택: 정본 `/api/prompts*` 사용 |

---

## 4. 프론트에서 고쳐야 할 것 (당신의 작업) — 우선순위순

> ⚠️ **소스 버전 주의**: 백엔드팀이 진단에 참고한 프론트 소스(store·hooks·일부 컴포넌트를 텍스트로 전달받음)는
> **실제 배포 dist보다 옛 버전**으로 확인됐다 — 배포본엔 있는 **언어 선택 UI(자동/한국어/영어)**·관리자 이동
> 버튼·재개/종료 버튼이 그 소스엔 없고, 반대로 그 소스에 있던 파형 시각화는 배포본엔 없다. 따라서 아래 각
> 항목의 **증상·요구사항은 배포 PC 실제 동작 관측 기준으로 신뢰**하되, "프론트 내부 구현이 이렇다"는 서술은
> **당신이 가진 현행 소스로 재확인**하라(§7).

### 4-1. [최우선] 녹음 컨트롤 상태머신 + 재시작 시 WS 재연결
- **증상**: "시작" → 전사는 잘 됨. 그러나 "중지/종료" 후 버튼이 먹통(예: "재개"가 비활성)이고, 다시 "시작"해도
  전사가 안 됨(콘솔 에러는 없음).
- **원인**: 백엔드 WS는 **연결당 1회성 세션**(§2-2). 프론트가 중지 후에도 **같은 WS를 유지**한 채 재개하려
  하는데, 서버는 이미 종료된 세션에 더는 응답하지 않는다.
- **요구사항**:
  1. "시작" = WS를 **(재)연결**한 뒤 전사 시작. 종료된 연결을 재사용하지 말 것.
  2. "중지/종료" = 빈 프레임 전송 → `ready_to_stop` 수신 시 상태를 **명확히 idle**로 전이(필요하면 WS도 close).
  3. "재시작/재개" = **반드시 새 WS 연결**로 새 세션 시작.
  4. 녹음 상태(idle / connecting / recording / stopping)를 명확히 관리하고, 각 버튼의 enable/disable을 상태에
     정확히 연동(재개가 영구 비활성으로 갇히지 않게).
- (참고: 만약 "같은 연결에서 일시정지/재개" UX를 강하게 원하면 백엔드팀과 협의 가능하나, **재연결 방식이 더
  단순하고 안전**하다.)

### 4-2. [높음] requestAnimationFrame 콜백의 null 참조
- **증상**: 중지 클릭 시 콘솔 `Uncaught TypeError: Cannot read properties of null (reading 'current')`
  (requestAnimationFrame 콜백에서 발생, 비동기 스택).
- **원인**: `requestAnimationFrame`으로 도는 루프가 정리(cleanup)된 뒤에도 실행되어 **이미 `null`이 된 ref를
  읽는다**. **정확한 발생 위치는 배포 dist 소스로 확인 필요**하다(§7 참조 — 백엔드팀이 받은 소스는 실제 배포
  dist와 달라 rAF 사용처를 특정하지 못했다). 참고: **현재 배포 UI에는 주파수/파형 시각화가 없다**(있다면 그
  그리기 루프를 의심하겠지만, 배포본엔 없으므로 rAF를 쓰는 다른 UI 로직을 소스에서 확인해야 한다).
- **요구사항**: 해당 rAF 루프를 중지/언마운트 시 `cancelAnimationFrame`으로 **확실히 종료**하고, 콜백 안에서
  읽는 ref가 null이면 즉시 중단하는 가드를 추가한다. 녹음이 끝나면(상태 전이 시) 새 프레임을 예약하지 않게 한다.

### 4-3. [높음] 관리자 페이지 이동 버튼 URL 조립 버그
- **증상**: 관리자 메뉴 이동 클릭 시 URL이
  `http://localhost:8900/wlkiesundefinedfunction search() { [native code] }undefined` 로 조립돼 404.
- **원인**: 이동 URL을 잘못된 값(`undefined` + 네이티브 함수의 문자열)으로 문자열 연결.
- **요구사항**: base(`/wlkies`)를 포함한 올바른 라우트로 이동. **TanStack Router `<Link to="/admin">` 또는
  `navigate({ to: '/admin' })`** 사용(라우터 basepath가 자동으로 `/wlkies` 접두를 붙임). 굳이 `window.open`/
  `location`을 써야 하면 반드시 `/wlkies/admin` **절대경로**로. (현재 우회: 주소창에 직접 `localhost:8900/wlkies/admin` 입력.)

### 4-4. [중간] WebSocket 절대 URL 사용 (백엔드 shim 제거 목표)
- **현황**: 백엔드가 `index.html`에 shim을 주입해 상대 WS URL을 절대 URL로 보정 중(§3-B). 동작하지만 임시.
- **요구사항**: 프론트에서 WS URL을 **절대 URL로 조립**:
  ```ts
  const wsBase = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
  new WebSocket(`${wsBase}/asr`); // 필요 시 `?language=${lang}` 추가 (§4-5)
  ```
  이러면 백엔드 shim 없이도 모든 브라우저에서 동작한다(shim은 이미 절대 URL이면 그대로 통과하므로 병행 무해).

### 4-5. [확인 필요] 언어 선택값이 `?language=`로 실제 전송되는지
- **현황**: **배포 dist에는 언어(자동/한국어/영어) 선택 UI가 이미 있다**(백엔드팀이 받은 옛 소스엔 없어 초기
  진단에서 "UI 없음"으로 잘못 적었던 부분 — §4 상단 주의 참조). 백엔드는 WS 쿼리 `?language=auto|ko|en`를 수용한다.
- **확인 필요**: 그 선택값이 WS 접속 URL에 `?language=<선택>`으로 **실제 전송되는지**. DevTools → Network →
  WS 요청의 URL을 확인한다(예: 한국어 선택 후 연결 시 URL에 `?language=ko`가 붙는가).
- **요구사항**: 전송되지 **않으면** 그 배선만 추가한다 — 연결 시 `` new WebSocket(`${wsBase}/asr?language=${선택값}`) ``
  (wsBase는 §4-4). 세션 도중 언어 변경은 재연결을 의미하므로 **연결 전에만 변경 가능**하게 권장. 이미 정상
  전송된다면 이 항목은 완료. 참고: [FRONTEND_LANGUAGE_SELECT_PATCH.md](FRONTEND_LANGUAGE_SELECT_PATCH.md)
  (그 문서의 "셀렉터 추가"는 이미 구현돼 있을 수 있으니 `?language=` 전송 여부만 확인하면 됨).

---

## 5. 현재 운영 중인 임시 우회책 (프론트 수정 전까지)

- **관리자 페이지**: 주소창에 `http://localhost:8900/wlkies/admin` 직접 입력(§4-3 고치면 불필요).
- **녹음 재시작**: F5 새로고침 후 "시작"(§4-1 고치면 불필요).

---

## 6. 참고 자료

- 백엔드 서빙/shim/alias 구현: `whisperlivekit/basic_server.py`.
- 백엔드 계약·스키마: [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md), [API_SPEC.md](API_SPEC.md),
  [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md), [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md).
- 언어선택 패치 스펙: [FRONTEND_LANGUAGE_SELECT_PATCH.md](FRONTEND_LANGUAGE_SELECT_PATCH.md).

---

## 7. 백엔드팀 → 신규 개발자에게 요청/확인 사항

- **현재 배포 dist의 소스 전체(현행 버전) 접근이 필요합니다.** 백엔드팀이 진단에 참고한 소스는 **실제 배포
  dist보다 옛 버전으로 확인**됐습니다 — 배포본엔 있는 **언어 선택 UI**·관리자 이동 버튼·재개/종료 버튼이 그
  소스엔 없었고(반대로 그 소스의 파형 시각화는 배포본에 없음). 또한 **관리자 이동 버튼·녹음 컨트롤(재개/종료)
  컴포넌트·라우터(`router.tsx`/`routeTree.gen.ts`)·관리자 페이지 컴포넌트**는 아예 전달받지 못했습니다. §4를
  정확히 수정하려면 **현행 dist를 만든 소스**가 필요합니다.
- 프론트 **빌드/배포 파이프라인 인수인계**: 빌드 명령, Vite `base` 설정, dist를 배포 PC(`C:\whist\wlk\frontend\static\`)에
  반영하는 절차.
- §4-1·§4-3을 고친 새 dist를 배포 PC의 `frontend/static/`에 덮어쓰면(index.html+assets) 백엔드 재기동 없이도
  **강력 새로고침(Ctrl+F5)**으로 반영됩니다.
- WS 메시지 실제 예시나 각 엔드포인트 동작 확인이 필요하면 백엔드팀에 요청하세요(테스트 지원 가능).
