# wlkies-frontend

대한민국 공군 AI 실시간 음성 인식·통역(STT) 시스템 — 배포 UI(React)

- 저장소 내 위치: `frontend/app/` (본 README 의 루트)
- 백엔드: `whisperlivekit`(FastAPI, Python) — Spring Boot 아님
- 빌드 산출물: `frontend/static/`(`vite.config.ts` `build.outDir: '../static'`) — 백엔드 `--frontend-dir`(기본값 `frontend/static`)가 이 경로를 서빙
- 배포 기본 경로(base): `/wlkies` (`vite.config.ts` `base`) — 백엔드 `--frontend-base`(기본값 `auto`)가 빌드된 `index.html` 의 자산 참조에서 자동 추출

## Tech Stack

| 분야 | 기술 |
|------|------|
| 런타임 | React 19.2.4 + TypeScript 5.9.3 |
| 빌드 | Vite 7.3.1 |
| 스타일 | Tailwind CSS 4.1.16 + `tw-animate-css` |
| 라우팅 | TanStack Router 1.166.7 (파일 기반 코드 생성, `router-plugin`/`router-devtools`) |
| 상태 관리 | Zustand 5.0.11 (persist 미들웨어) |
| UI | Radix UI(`react-alert-dialog`, `react-select`, `react-slot`) + `class-variance-authority` (shadcn 스타일 프리미티브) |
| 애니메이션 | Framer Motion (설정 드로어 슬라이드 트랜지션) |
| 아이콘 | Lucide React (`react-icons` 도 의존성에 있으나 `src/` 내 실사용 없음) |
| 알림 | react-toastify (오류·관리자 CRUD 결과 토스트) |
| 오디오 | MediaRecorder API(WebM) + Web Audio API(AnalyserNode) |
| 통신 | WebSocket(wlk delta/full 프로토콜) + Fetch API |
| 테스트 | Vitest (`*.test.ts`, `pnpm test`) |
| 패키지 매니저 | pnpm (`pnpm-lock.yaml`, `.npmrc`) |

Path alias: `@` → `src/`(`tsconfig.app.json` `paths`, `vite.config.ts` `resolve.alias`).

## Project Structure

```
frontend/app/
├── index.html                 # 진입점 HTML
├── package.json
├── vite.config.ts             # base=/wlkies, outDir=../static, dev proxy
├── .env.example                # 환경변수 예시 (커밋 대상)
├── AGENTS.md                  # 코드 컨벤션 + 계약 문서 링크
├── docs/
│   ├── implementation-plan.md      # 과거 구현 계획 메모
│   └── overengineering-audit.md    # 과거 단순화 감사 메모
├── public/                    # 정적 자산 (공군 로고)
└── src/
    ├── main.tsx                # React root 마운트 + ToastContainer
    ├── router.tsx               # TanStack Router 인스턴스 (basepath=BASE_PATH)
    ├── routeTree.gen.ts         # 파일 기반 라우터 자동 생성 (직접 수정 금지)
    ├── styles.css                # 전역 스타일 (Pretendard, Tailwind, CSS 변수)
    │
    ├── routes/                  # TanStack Router 파일 기반 라우트
    │   ├── __root.tsx           # 루트 라우트 (Outlet 만)
    │   ├── index.tsx            # "/" — <SttMain/> 렌더
    │   └── admin.tsx            # "/admin" — 블록 관리 + 단어교정 + 번역용어 + 번역예시
    │
    ├── api/                     # REST API 클라이언트
    │   ├── corrections.ts       # 단어교정 사전 + 번역 사전(glossary/예시) CRUD
    │   ├── retranslate.ts       # 블록 재번역 (POST /api/retranslate, timeout 60초)
    │   └── health.ts            # 백엔드 헬스체크 (GET /health)
    │
    ├── assets/
    │   ├── fonts/Pretendard/    # Pretendard Variable 폰트 (직접 호스팅)
    │   └── images/              # 공군 로고
    │
    ├── components/
    │   ├── SttMain.tsx              # 메인 화면 (헤더/전사영역/설정드로어), 세션 렌더만 담당
    │   ├── BlockControlPanel.tsx    # 관리자 페이지 — 블록 삭제/재번역 (BroadcastChannel 명령)
    │   ├── SttSettingDrawer.tsx     # 오른쪽 슬라이드 설정 드로어
    │   ├── SttTextViewer.tsx        # 전사 행 1개 렌더 (원문+번역+선택적 시각)
    │   ├── SttTranslateLoader.tsx   # 번역 대기 로더
    │   ├── SttThemeProvider.tsx     # 테마 CSS 변수 주입 + useSttTextStyle 훅
    │   ├── SttSliderField.tsx       # 설정 드로어용 수치 행 (슬라이더 + 숫자 입력 겸용)
    │   ├── WaveformVisualizer.tsx   # canvas 기반 실시간 파형 (useWaveform 사용)
    │   ├── BackendErrorOverlay.tsx  # 헬스체크 실패 시 오버레이
    │   └── ui/                      # shadcn 스타일 UI 프리미티브
    │       ├── alert-dialog.tsx     # 종료 확인 다이얼로그
    │       ├── button.tsx
    │       ├── input.tsx
    │       └── select.tsx
    │
    ├── constants/
    │   └── index.ts              # Api.{HEALTH,CORRECTIONS,PROMPTS,PROMPTS_ADD,PROMPTS_DELETE,RETRANSLATE}, BASE_PATH, APP_VERSION
    │
    ├── hooks/
    │   ├── useSttSession.ts      # 세션 오케스트레이션 — 소켓·마이크 라이프사이클이 만나는 유일한 곳
    │   ├── useAudioRecorder.ts(+.test.ts) # 마이크 캡처 + WebM 인코딩 (MediaRecorder)
    │   ├── useTranscriptRows.ts  # store 슬라이스 → 화면 행 배열 파생 (useMemo) + toRowInput
    │   ├── useBlockCommandBridge.ts # 관리자 창 명령 수신부 (실시간 화면에서 1회 마운트)
    │   └── useWaveform.ts        # AnalyserNode → requestAnimationFrame → canvas 직접 그리기
    │
    ├── stores/
    │   ├── stt.store.ts          # STT 세션/전사 상태 (Zustand) — WS 연결·재연결·메시지 파싱의 유일한 소유자
    │   ├── theme.store.ts        # 테마·폰트·로고 설정 persist store (key: stt-theme-v2)
    │   └── stt-sidebar-store.ts  # 설정 드로어 열림/닫힘 상태
    │
    ├── types/
    │   └── stt.ts                # wlk WebSocket 계약 타입 (정본 = docs/API_SPEC.md §2.4)
    │
    └── utils/
        ├── deltaProtocol.ts(+.test.ts)     # 델타 프로토콜 메시지 판별 + lines 재구성 (순수 함수)
        ├── blockNumbers.ts(+.test.ts)      # 블록 번호 발급·승계 (순수 함수)
        ├── blockCommands.ts(+.test.ts)     # 관리자 창 ↔ 화면 창 명령 브리지 + 판정 (순수 함수)
        ├── transcriptRows.ts(+.test.ts)    # 서버 상태 → 화면 행 목록 파생 (순수 함수)
        ├── wsUrl.ts               # WebSocket URL 조립 (origin 기반 절대 URL)
        ├── fetchJson.ts           # JSON API 요청 헬퍼 (기본 5초 timeout, 인자로 조정)
        └── index.ts               # cn() 유틸 (clsx + tailwind-merge)
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        React Components                          │
│  SttMain ── SttSettingDrawer ── SttTextViewer ── SttTranslateLoader│
│  WaveformVisualizer  │  BackendErrorOverlay  │  routes/admin.tsx  │
├──────────────────────────────────────────────────────────────────┤
│                       Hooks (오케스트레이션)                        │
│  useSttSession  │  useAudioRecorder  │  useTranscriptRows  │ useWaveform│
├──────────────────────────────────────────────────────────────────┤
│                        Zustand Stores                            │
│  stt.store.ts (WS 세션)  │  theme.store.ts  │  stt-sidebar-store  │
├──────────────────────────────────────────────────────────────────┤
│                       Utils / API Clients                        │
│  deltaProtocol.ts │ transcriptRows.ts │ wsUrl.ts │ fetchJson.ts  │
│  corrections.ts (단어교정 + 번역 glossary/예시) │ health.ts       │
├──────────────────────────────────────────────────────────────────┤
│              External Services (백엔드 = whisperlivekit)          │
│  WebSocket /asr  │  REST /api/corrections, /api/prompts*, /health│
└──────────────────────────────────────────────────────────────────┘
```

### State Flow

세션의 소켓 라이프사이클과 마이크 라이프사이클은 `useSttSession` 훅 한 곳에서만 순서가 정해진다.
저장소(`stt.store.ts`)는 소켓만, `useAudioRecorder` 는 마이크만 안다.

1. **시작**: `useSttSession.startOrResume()` → ① `useAudioRecorder.prepare()` 로 마이크 권한 획득(거부되면 서버 세션을 열지 않는다) → ② `useSttStore.beginSession()` 으로 WebSocket 연결, `config` 메시지 수신까지 대기 → ③ 새 `MediaRecorder` 로 인코더 시작(`startEncoder`) → `markRecording()`
2. `useAudioRecorder` 가 100ms 간격으로 WebM Blob 을 만들어 `onChunk`(= `useSttStore.sendAudioChunk`) 콜백으로 전달 → WebSocket 으로 전송
3. 백엔드(whisperlivekit)가 delta(`snapshot`/`diff`) 또는 full(무-`type`) 상태 메시지를 push → `useSttStore.handleMessage()` 가 `deltaProtocol.classify()` 로 메시지 종류를 가르고, delta 모드면 `reconstructLines()` 로 `lines` 배열을 재구성, 확정 세그먼트를 `finalizedHistory` 에 누적
4. `useTranscriptRows()` 훅이 `committedLines`/`finalizedHistory`/`serverLines`/`volatile` 슬라이스를 구독해 `transcriptRows.buildRows()` 로 화면 행 배열을 파생(`useMemo`)
5. `SttMain` 이 그 행을 `SttTextViewer` 로 렌더(원문 + 번역 + 선택적 시각), 예상치 못한 끊김/desync 는 `useSttSession` 의 자동 복구(backoff 재개)가 처리

### wlk 프로토콜

프로토콜 상세 알고리즘(델타 재구성 규칙 등)은 여기서 중복 서술하지 않는다 — 정본은
[docs/API_SPEC.md](../../docs/API_SPEC.md) §2.4.2, [docs/DELTA_PROTOCOL_SPEC.md](../../docs/DELTA_PROTOCOL_SPEC.md),
메시지 스키마는 [docs/SCHEMA_CHANGES.md](../../docs/SCHEMA_CHANGES.md). 프론트측 타입 정의 = `src/types/stt.ts`, 재구성 구현 = `src/utils/deltaProtocol.ts`.

| 메시지/타입 | 방향 | 설명 |
|-------------|------|------|
| `ConfigMessage`(`type:'config'`) | 서버→클라이언트 | 연결 직후 1회. `useAudioWorklet`(true면 PCM, false면 WebM), 실제 적용 `protocol`/`language` |
| `SnapshotMessage`(`type:'snapshot'`) | 서버→클라이언트 | delta 모드 첫 상태 메시지(연결당 1회). `lines` 전체 |
| `DiffMessage`(`type:'diff'`) | 서버→클라이언트 | delta 모드 이후 상태 메시지. `lines` 대신 `new_lines`(공통 prefix 이후 꼬리 전체) + `n_lines` |
| `FullState`(`type` 필드 없음) | 서버→클라이언트 | full 모드 상태 메시지. 매번 `lines` 전체 교체 |
| `ReadyToStopMessage`(`type:'ready_to_stop'`) | 서버→클라이언트 | EOS 이후 flush 완료 신호 |
| 오디오 Blob | 클라이언트→서버 | MediaRecorder WebM 청크(100ms), 빈 바이너리 프레임 = EOS |

세션 상태(`SttPhase`): `idle → connecting → recording → stopping → paused`(또는 `error`). 언어(`SourceLanguage`): `auto`/`ko`/`en`
(`LANGUAGE_OPTIONS`). 전송 프로토콜(`WsMode`): 기본 `delta`(대역폭 절감), `full` 로 탈출 가능. 확정 계기(`FinalizeTrigger`):
`silence`/`punctuation`/`language_switch`/`speaker_change`.

## Quick Start

### 설치

```bash
cd frontend/app
pnpm install
```

### 개발 서버

```bash
pnpm dev
```

- 로컬: `http://localhost:5173/wlkies`
- `vite.config.ts` 의 dev proxy 가 로컬에서 띄운 wlk 백엔드(uvicorn)로 요청을 전달한다. **`/wlkies` 자체는 프록시하지 않는다** — dev 서버가 이 base 로 앱을 직접 서빙하므로 프록시하면 앱이 뜨지 않는다. 프론트는 백엔드 API 를 base 없는 절대 경로(`/health`, `/api/...`)로 호출한다.

| 경로 패턴 | 대상 | 프로토콜 |
|-----------|------|----------|
| `/asr` | `ws://{VITE_SERVER_HOST}:{VITE_SERVER_PORT}` | WebSocket |
| `/api` | `http://{VITE_SERVER_HOST}:{VITE_SERVER_PORT}` | HTTP |
| `/health` | `http://{VITE_SERVER_HOST}:{VITE_SERVER_PORT}` | HTTP |

`VITE_SERVER_HOST` 기본값 `127.0.0.1`, `VITE_SERVER_PORT` 기본값 `8900`(백엔드 `--port` 기본값과 동일).

### 빌드

```bash
pnpm build
```

빌드 출력: `frontend/static/`(`vite.config.ts` `build.outDir: '../static'`, `frontend/app` 기준 한 단계 위). 백엔드
`whisperlivekit/basic_server.py` 가 `--frontend-dir`(기본값 `frontend/static`, 저장소 루트 기준)로 이 디렉터리를 서빙하고,
`--frontend-base`(기본값 `auto`)가 빌드된 `index.html` 의 자산 참조에서 base(`/wlkies`)를 자동 추출한다. Spring Boot 는 이 저장소에 없다.

## Environment Variables

정본 = `.env.example`(커밋 대상, 배포 빌드는 이 파일 없이도 동작한다). 배포 PC 는 백엔드가 dist 를 직접 서빙하므로(`localhost:8900`)
아무 설정도 필요 없다 — WS/REST URL 은 런타임에 `window.location` 기준으로 조립된다(`src/utils/wsUrl.ts`).

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `VITE_BASE_URL` | `/wlkies` | 라우팅 prefix. **`vite.config.ts` 의 `base` 와 반드시 일치해야 한다** |
| `VITE_APP_VERSION` | (없음) | 앱 버전 — 설정 드로어 footer 에 표시 |
| `VITE_SERVER_HOST` | `127.0.0.1` | dev 전용. Vite 프록시가 바라볼 백엔드 호스트 |
| `VITE_SERVER_PORT` | `8900` | dev 전용. Vite 프록시가 바라볼 백엔드 포트 |
| `VITE_WS_URL` | (없음, 미설정 시 `window.location` 기준 자동조립) | dev 전용. 프론트를 백엔드와 다른 호스트에서 띄울 때만 설정 — 특정 PC IP 를 박아 배포 빌드를 만들면 그 PC 밖에서 동작하지 않으므로 **배포 빌드에는 설정하지 않는다** |

`VITE_CORRECTIONS_URL` 같은 변수는 존재하지 않는다 — 단어교정/번역 API 경로는 `src/constants/index.ts` 의 `Api` 상수(하드코딩 경로)로 관리된다.

## 백엔드 API 상수 (`src/constants/index.ts`)

| 상수 | 값 | 용도 |
|------|-----|------|
| `Api.HEALTH` | `/health` | 헬스체크 |
| `Api.CORRECTIONS` | `/api/corrections` | 단어교정 사전 (GET/POST, DELETE `${CORRECTIONS}/{wrong_word}`) |
| `Api.PROMPTS` | `/api/prompts` | 번역 사전(glossary_block/sentence_block) 조회 |
| `Api.PROMPTS_ADD` | `/api/prompts/add-item` | 번역 사전 항목 추가 |
| `Api.PROMPTS_DELETE` | `/api/prompts/delete-item` | 번역 사전 항목 삭제 |
| `BASE_PATH` | `import.meta.env.VITE_BASE_URL ?? '/wlkies'` | 라우터 basepath |
| `APP_VERSION` | `import.meta.env.VITE_APP_VERSION ?? ''` | 표시용 앱 버전 |

전부 **base(`/wlkies`) 없는 절대 경로**다 — base 를 붙이면 백엔드의 SPA fallback 이 JSON 대신 `index.html` 을 돌려줘 조용히 실패한다.

## 주요 기능

### 음성 인식(STT) 세션
- 마이크 오디오 캡처(MediaRecorder, WebM, 100ms 청크) → WebSocket 스트리밍
- 델타(delta) 프로토콜 기본 적용 — 대역폭 절감, `full` 모드로 탈출 가능
- 세션 언어 선택(`auto`/`ko`/`en`, 시작 전에만 변경 가능)
- 예상치 못한 끊김·desync 자동 재개(backoff, 최대 3회) — 사용자의 '재개'와 동일 동작
- 실시간 파형 시각화(`WaveformVisualizer`/`useWaveform`)

### 전사·번역 표시
- 문장 확정 시 번역 결과 표시, 미확정 구간엔 `SttTranslateLoader`
- 시각(HH:MM:SS) 표시 토글(**기본 on**)
- 확정 원인(`finalize_trigger`) 배지 표시 토글(**기본 on**) — 확정된 줄마다 색상 pill로
  침묵/종결/언어전환/화자전환을 표시한다. 라벨·색은 내장 UI(`live_transcription.js` `TRIGGER_LABELS`)와 동일
- 화자분리 UI 는 배포 UI 에 **탑재돼 있지 않다** — 서버가 화자 번호(`speaker`)를 보내도 화면에 별도 뱃지/색상으로 표시하지 않는다(`transcriptRows.ts` 설계 주석 참조)
- **블록 번호(`#N`) 표시 토글(기본 on)** — 메타 줄 맨 앞에 작게 붙는다. 관리자 페이지가 이 번호로
  블록을 지목한다(아래 "블록 관리" 절)

### 블록 관리 — 삭제 / 재번역 (`BlockControlPanel`, `blockNumbers.ts`, `blockCommands.ts`)

환각만 담긴 블록이 통째로 확정되거나 번역이 비는 일이 있어, 운용 중에 그 블록만 골라 지우거나
다시 번역한다. 관리자 창(`/admin`)에서 **실시간 화면에 보이는 `#번호`를 입력** → 대상 미리보기 확인
→ 삭제 / 다시 번역. 삭제는 **최근 1건 실행취소**가 가능하다.

**왜 서버가 아니라 다른 창에 명령을 보내는가.** 단어교정 사전은 서버가 가진 전역 데이터라 서버 한 곳만
고치면 모든 화면에 퍼진다(매 tick 전 구간 재적용). 반면 "지금 화면의 7번 블록"은 **화면 상태**다 —
서버에는 진행 중 세션을 찾아갈 경로가 없고(세션 레지스트리 부재), 일시중단→재개하면 새 세션이라
서버의 줄 번호와 화면의 번호가 어긋난다. 그래서 번호 해석은 화면 창이 하고, 관리자 창은 명령만 보낸다.

- **전제: 같은 브라우저의 다른 창**(다른 모니터). BroadcastChannel 은 창·모니터가 달라도 같은 origin 이면
  통하지만, **다른 PC·다른 브라우저에서는 통하지 않는다**. 미지원 브라우저면 패널이 비활성으로 뜬다
- **번호는 고정·결번**(`blockNumbers.ts`) — 발급 순서를 유지하고 삭제해도 뒤 블록을 당기지 않는다.
  한 번 읽은 번호가 계속 유효해야 연속 삭제가 안전하고, 결번 자체가 "여기 지웠다"는 표시가 된다.
  번호는 세그먼트를 따라다니므로 일시중단→재개를 넘어서도 유지된다(`id`→번호 영구 Map 은 금지 —
  새 세션은 `id` 가 0부터 다시 매겨져 즉시 오배정된다)
- **삭제는 컬렉션에서 지우지 않고 렌더 단계에서만 거른다**(`buildRows` 마지막의 `suppressedBlockNos` 필터).
  그래서 실행취소가 `Set` 원소 하나를 빼는 것으로 끝나고 **원래 자리로 정확히 복귀**한다.
  필터를 앞으로 옮기거나 정렬을 넣으면 ① buffer 꼬리가 엉뚱한 블록에 붙고 ② 아무것도 안 지웠을 때의
  출력이 달라져 경로 C 측정(`stt-row` DOM 순서 스크래핑)이 조용히 흔들린다
- **화면 창이 2개면 조작을 막는다** — 창마다 독립 WebSocket 세션이라 **번호 체계가 서로 다르다**.
  조회(비파괴)를 먼저 보내 수집 창(700ms) 동안 응답한 `clientId` 를 세고, 0개·2개 이상이면 안내 후 중단한다.
  파괴적 명령은 그렇게 확인된 `clientId` 앞으로만 보낸다
- **미확정 블록은 삭제할 수 없다** — 확정되며 두 세그먼트로 갈라지면 뒤 조각이 새 번호를 받아 부활한다
- **재번역 REST(`POST /api/retranslate`)는 관리자 창이 직접 호출한다**(조회 때 원문을 이미 받았다).
  브리지에 LLM 왕복만큼의 긴 대기가 생기지 않고, 화면 창이 중간에 닫혀도 부작용이 없다.
  결과는 화면 창의 `translationOverrides` 에 들어가 서버 번역을 이긴다 — 단어교정으로 원문이 바뀌면
  자동 폐기된다. 번역 백엔드가 `temperature: 0` 이라 **용어집을 바꾸지 않으면 결과가 같을 수 있고**,
  그 경우 토스트로 명시한다(정본 = `docs/API_SPEC.md` §3.6)

### 관리자 페이지 (`/admin`, `routes/admin.tsx`)
- **탭 없는 1페이지 좌우 2분할** — 좌: 블록 관리(위) + 단어교정 사전(전사 후처리 오인식→정답 매핑, 아래),
  우: 번역 용어(glossary, 위) + 번역 예시(sentence, 아래)
- 페이지 전체 스크롤이 아니라 **패널별 내부 스크롤**이다(각 목록이 자기 영역 안에서만 스크롤)
- **정적 JSON 기본값은 화면에 보이지 않는다** — 목록에 뜨는 건 사용자가 이 화면에서 직접 넣은
  DB 항목뿐이다. 배포 전 관리자가 미리 채우는 base JSON(`admin_replacement.json`,
  `admin_translation_glossary.json`)은 서버가 GET 응답에서 제외한다(정본 = `docs/API_SPEC.md`
  §3.3·§3.4). **숨긴 항목도 전사·번역에는 그대로 적용되며**, 그 사실을 알리는 안내 문구나
  건수 표시는 화면에 두지 않는다(운용자에게 보일 필요가 없다는 판단)
  - 예외: 번역 예시(`sentence_block`)는 개발자 기본값도 계속 표시된다(서버가 기본값+사용자
    사본을 합쳐 주는 Copy-on-Write 구조라 애초에 편집·삭제 가능한 항목이다)
- 기본 내장 항목은 삭제 불가 — 서버가 HTTP 200 + `status:'warning'` 로 알려주며 토스트로 안내.
  base 항목이 목록에 안 뜨므로 UI 로는 도달할 수 없고, API 직접 호출 방어용으로 남아 있다
- **등록 창은 연속 입력용이다**(세 패널 공용 `AddDialog`) — 항목을 여러 개 넣는 게 기본 상황이라
  추가 버튼을 누른 뒤 **마우스를 다시 쓰지 않도록** 만들었다
  - 열면 첫 칸(오인식 단어 / 원본 단어 / 원본 문장)에 **커서가 자동으로 잡힌다**
  - **Enter = 등록**(두 칸 중 어디서든). 한글 조합 중(IME 미확정)의 Enter 는 조합 확정용이라 무시한다 —
    이 가드가 없으면 마지막 글자가 빠진 채 등록된다
  - **등록해도 창이 닫히지 않는다** — 두 칸만 비워지고 커서가 첫 칸으로 돌아간다. 결과는 토스트와
    뒤쪽 목록 갱신으로 확인한다. 등록에 **실패하면 입력값을 지우지 않는다**(고쳐서 바로 재시도)
  - 닫기는 **ESC · 취소 · X · 바깥 클릭** 네 경로이며 모두 입력값을 비우고 닫는다(다음에 열면 빈 칸)

### 백엔드 헬스체크
- 15초 간격 자동 폴링(`GET /health`)
- 실패 시 `BackendErrorOverlay` 표시, 수동 재연결(재확인) 지원

### 테마/설정 (`SttSettingDrawer`, `theme.store.ts`)
- 배경 색상 / 로고(타이틀) 배경 색상 / 로고 폰트 색상
- 원본·번역·시스템 폰트 크기 및 색상 개별 설정
- 로고 전체 크기 프리셋(`sm`=50% / `md`=100% / `lg`=150% / `xl`=200%, 타이틀·서브타이틀 폰트 크기·로고 이미지 크기 동시 변경)
- 시각 표시 / 확정 원인 배지 표시 / 블록 번호 표시 토글(전부 기본 on)
- **화면 레이아웃 5종**(전부 `SttSliderField` — 슬라이더와 숫자 입력이 같은 값을 본다).
  배포 현장마다 화면 크기·시청 거리가 달라 운용자가 현장에서 가독성을 맞추기 위한 것이다:

  | 설정 | store 필드 | CSS 변수 | 기본값 | 범위(step) | 적용 지점 |
  |---|---|---|---|---|---|
  | 화면 좌우 여백 | `screenPaddingXPercent` | `--stt-padding-x` | `5`% | 0–30 (0.5) | `SttMain` 스크롤 컨테이너 좌우 padding |
  | 문단 간격 | `blockGapPx` | `--stt-block-gap` | `56`px | 0–200 (2) | `SttMain` 블록(행)↔블록 gap |
  | 문장 간격 | `lineSpacingRatio` | `--stt-line-height` · `--stt-sentence-gap` | `1.75`배 | 1.0–3.0 (0.05) | 줄간격(`useSttTextStyle`) **과** 블록 내부 gap(`SttTextViewer`) |
  | 번역 중 투명도 | `processingOpacity` | `--stt-processing-opacity` | `0.4` | 0.1–1.0 (0.05) | 미확정 원문 div + `SttTranslateLoader` |
  | 하단 여백 | `bottomPaddingPercent` | `--stt-bottom-pad` | `20`% | 0–60 (1) | `SttMain` sentinel **위**의 spacer 높이(`vh`) |

  - 문장 간격은 **배율 하나**로 줄간격과 원문↔번역 간격을 함께 움직인다. 후자는
    `(배율−1) × 원본폰트크기 × 0.5`로 파생한다(기본값 검산 `(1.75−1)×24×0.5 = 9px` ≈ 종전 `gap-2`).
  - 하단 여백은 `vh` 다 — CSS 백분율 padding 은 높이가 아니라 **너비** 기준이라 "화면 높이 %"를
    담지 못한다. 또 컨테이너 `padding-bottom` 이 아니라 **spacer div** 여야 한다(`SttMain` 참조).
- localStorage persist(key: `stt-theme-v2`, `version: 1`), "설정 초기화" 버튼으로 기본값 복원.
  **기본값을 바꿀 땐 키를 올리지 말고 `migrate` 를 쓴다** — 키를 올리면 저장된 색상·폰트 설정이
  통째로 날아간다(v1→v2 때 실제로 그랬다). `version: 1` 마이그레이션이 구 저장분의 `showTimestamp` 를
  새 기본값(on)으로 1회 끌어올린다

### 알림
- react-toastify 기반 토스트 — 세션 오류, 관리자 페이지 CRUD 성공/실패/경고

## 컴포넌트 가이드

### `SttMain`
메인 화면. 헤더(로고+타이틀), 전사 영역, 설정 드로어로 구성. 세션 제어 로직은 갖지 않고 `useSttSession()`/`useTranscriptRows()` 를
구독해 렌더만 한다. 자동 스크롤(바닥 근접 시에만 따라감), 헬스 폴링(15초), 세션 오류 토스트를 담당.

전사 목록 아래에는 **하단 여백 spacer → sentinel(`endRef`)** 순서로 두 div 가 있고, 둘 다
`data-testid="stt-transcript"` **바깥**이다. 순서·위치 둘 다 의미가 있다:
- 자동 스크롤이 sentinel 바닥을 뷰포트 바닥에 맞추므로, 하단 여백을 컨테이너 `padding-bottom` 으로
  주면 그 여백은 sentinel 아래(화면 밖)에 남아 최신 전사가 여전히 화면 맨 아래에 붙는다.
  spacer 를 sentinel **위**에 둬야 스크롤이 여백을 화면 안으로 끌어올려 최신 전사를 위로 민다.
- `stt-transcript` **안**에 넣으면 블록 간격(`--stt-block-gap`)이 spacer 앞에 한 번 더 붙는다.

### `SttSettingDrawer`
오른쪽에서 슬라이드되는 설정 패널(Framer Motion). 버튼 활성/비활성은 세션 `phase` 에서 파생한다.
- 세션 제어(시작/일시중단/재개, 종료는 `AlertDialog` 확인 후)
- 언어 선택(`select`, 세션 시작 전에만 활성)
- 웨이브폼(`WaveformVisualizer`, 녹음/일시중단 중에만 표시)
- 테마·폰트·로고 설정, 화면 레이아웃 5종(`SttSliderField`), 시각 표시·확정 원인 표시 토글, 기록/설정 초기화
- 관리자 페이지(`/admin`) 링크

### `SttTextViewer`
전사 행 1개 렌더 — (선택적 메타 줄: 시각 + 확정 원인 배지) + 원문(진하게/연하게는 확정 여부에 따라)
+ 번역(대기 중이면 `SttTranslateLoader`). 미확정 buffer 꼬리는 같은 문단 안에 이어 붙인다.
메타 줄은 **세 토글(블록 번호·시각·확정 원인)이 모두 꺼지면** 렌더 자체를 생략한다(빈 div 를 남기면
flex gap 만 먹어 행 간격이 벌어진다). 블록 번호는 나머지 둘과 독립적으로 켜진다 — 시각·배지를 다 꺼도
관리자 페이지에서 블록을 지목할 수 있어야 하기 때문이다.
**메타 줄은 반드시 `data-testid="stt-text"` 바깥**이다 — 안에 넣으면 경로 C 전사에 섞인다.

### `SttThemeProvider` / `useSttTextStyle`
`theme.store.ts` 값을 CSS 변수(`--stt-*`)로 주입하는 Provider 와, 원문/번역/시스템 텍스트 스타일을 반환하는 훅.
색상·폰트뿐 아니라 **레이아웃 값도 여기서 CSS 변수로 나간다**(위 테마/설정 표) — 소비하는 쪽
(`SttMain`·`SttTextViewer`·`SttTranslateLoader`)은 store 를 직접 구독하지 않고 변수만 읽는다.

### `SttSliderField`
설정 드로어의 수치 입력 행. `[라벨] [range] [number] [단위]` 한 줄이며 range/number 가 같은 store
값을 본다. range 는 네이티브 `<input type="range">` 다 — **폐쇄망 패키징에 새 npm 의존성(radix
slider)을 얹지 않기 위해서**이고, 겉모습은 `styles.css` 의 `.stt-range` 가 맞춘다. 숫자 칸은
타이핑 중간 상태를 위해 문자열 draft 를 두고, 파싱되는 값만 `min`~`max` 로 clamp 해 커밋한다
(blur 시 store 값으로 재동기화).

### `WaveformVisualizer` + `useWaveform`
`AnalyserNode` 를 `requestAnimationFrame` 으로 canvas 에 직접 그린다. `ResizeObserver` 로 컨테이너 크기 변화를 canvas 물리 크기(DPR 포함)에 동기화.

### `BackendErrorOverlay`
헬스체크 실패 시 표시되는 전체 화면 오버레이. 연결 시도 중/서버 오류(500)/네트워크 불가 상태를 구분해 안내.

### `BlockControlPanel` (관리자 페이지 좌측 상단)
실시간 전사 블록을 **번호로 지목해** 삭제하거나 다시 번역한다. 서버가 아니라 **다른 창**에 명령을
보내는 유일한 컴포넌트다 — 자세한 배경은 아래 "블록 관리" 절 참조.

### `routes/admin.tsx` (AdminPage)
좌측 상단에 `BlockControlPanel`, 그 아래 단어교정. 우측은 번역용어 + 번역예시 — 탭이 없다.
데이터 소스 3종(`words`/`translate_words`/`translate_sentence`)은 아래 `Section` 이 맡는다.
`Section` 컴포넌트 하나가 소스 하나를 맡아 `useItems()`(조회/추가/삭제) + 검색어 + 추가 다이얼로그
상태를 자기 안에 들고, 배치(폭·높이)는 `className` 으로 부모(`AdminPage`)가 정한다.

레이아웃은 `flex-1 min-h-0` 를 부모→패널로 내려 **패널별 내부 스크롤**을 만든다(`SectionUI` 의 목록
div 가 `flex-1 min-h-0 overflow-y-auto`). 바깥에 `overflow-y-auto` 를 주면 페이지가 통째로 스크롤돼
세 패널이 한 화면에 유지되지 않는다.

`AddDialog` 는 세 패널이 공유하며 **연속 입력**을 전제로 한다(위 기능 절 참조). 구현상 주의점 셋:
- 첫 칸 포커스는 `srcRef` + `useEffect(..., [open])` 로 잡는다. `autoFocus` 만으로는 등록 직후
  재포커스(창이 안 닫혀 DOM 이 그대로 살아 있다)를 못 한다
- Enter 핸들러는 `e.nativeEvent.isComposing` 로 한글 조합 중을 걸러야 한다
- `useItems.addItem` 은 실패를 **재던진다** — 창이 유지되므로 호출측이 성공/실패를 구분해야
  실패 시 입력값을 보존할 수 있다. 삼키면 실패해도 칸이 비워진다

## 자동화 계약 (경로 C 측정이 의존한다 — 지우지 말 것)

STT 성능 정량 측정(경로 C, `scripts/vbcable_test.py`)이 **이 앱을 Playwright로 직접 몰아서** WER·화자분리
F1·문장분리 F1을 산출한다. 즉 배포되는 화면이 곧 측정 대상이다. 아래 `data-*` 속성이 그 접점이며,
**화면 외관·동작에는 아무 영향이 없다**(그래서 리팩터링 중 무심코 지우기 쉽다 — 지우면 측정이
조용히 깨진다. 함께 갱신할 문서는 루트 `CLAUDE.md` 연동 갱신 표 참조).

| 속성 | 위치 | 하니스가 쓰는 방식 |
|---|---|---|
| `data-testid="stt-settings-toggle"` | `SttSettingDrawer.tsx` 우측 토글 | 컨트롤이 드로어 안에 있으므로 **가장 먼저 눌러 드로어를 연다** |
| `data-testid="stt-start"` / `"stt-pause"` / `"stt-stop"` | `SttSettingDrawer.tsx` 버튼 | 시작 → (재생) → **일시 중단**. `stt-stop`은 절대 누르지 않는다 — `endSession('stop')`이 화면 전사를 즉시 비운다 |
| `data-testid="stt-status"` + `data-phase` | `SttSettingDrawer.tsx` 상태 값 | `data-phase`는 지역화 문구가 아니라 raw enum(`recording`/`paused` …). 문구를 바꿔도 자동화가 안 깨지도록 일부러 enum을 노출한다 |
| `data-testid="stt-language"` | 언어 `<select>` | 동일 class 의 select 가 3개라 이 속성으로만 특정된다 |
| `data-testid="stt-transcript"` | `SttMain.tsx` 전사 컨테이너 | 스크래핑 루트 |
| `data-testid="stt-row"` + `data-trigger` | `SttTextViewer.tsx` 행 컨테이너 | 행 하나 = 확정 문장 하나(F1 의 경계 단위). `data-trigger`는 전사 txt의 `[문장별 확정 트리거]` 섹션 입력 |
| `data-block-no` | `SttTextViewer.tsx` 행 컨테이너 | 하니스는 쓰지 않는다(디버깅용). 화면의 `#N` 배지와 같은 값 — 관리자 페이지가 이 번호로 블록을 지목한다 |
| `data-testid="stt-text"` | `SttTextViewer.tsx` 원문 div | **원문만** 읽는다 — 행 전체 innerText 를 쓰면 시각 표시·번역문이 전사에 섞인다 |
| `data-testid="stt-idle"` / `"stt-backend-error"` | `SttMain.tsx` / `BackendErrorOverlay.tsx` | "전사 0줄"이 하니스 고장인지 백엔드 문제인지 가르는 신호 |

`TranscriptRow.trigger`(`utils/transcriptRows.ts`)는 `Segment.finalize_trigger`를 행까지 전달하는 필드다.
쓰임이 둘이다 — 화면의 확정 원인 배지(설정으로 on/off)와 이 계약의 `data-trigger` 속성. **배지를 꺼도
`data-trigger`는 그대로 붙으므로 측정은 설정과 무관하게 동작한다.** 배지는 `stt-text` div 바깥에 있어
`stt-text`의 innerText 를 오염시키지 않는다 — 배지를 옮길 일이 생기면 이 조건을 반드시 지킬 것.

## 스크립트

```bash
pnpm dev          # 개발 서버 (http://localhost:5173/wlkies)
pnpm build        # 프로덕션 빌드 → frontend/static/
pnpm preview      # 빌드 결과 미리보기
pnpm lint         # ESLint
pnpm typecheck    # tsc -b --noEmit
pnpm test         # vitest run
```

## 참고 문서

- `AGENTS.md` — 코드 컨벤션(파일명·TypeScript·스타일링·상태관리·라우팅) + 개발 명령어
- `docs/implementation-plan.md` — 과거 구현 계획 메모(저작권/보안고지, 녹음제어, 종료확인팝업)
- `docs/overengineering-audit.md` — 과거 단순화 감사 메모
- [../../docs/API_SPEC.md](../../docs/API_SPEC.md) — 서버 REST/WebSocket 계약 정본
- [../../docs/DELTA_PROTOCOL_SPEC.md](../../docs/DELTA_PROTOCOL_SPEC.md) — 델타 프로토콜 재구성 알고리즘 정본
- [../../docs/SCHEMA_CHANGES.md](../../docs/SCHEMA_CHANGES.md) — WebSocket 메시지 스키마 변경 이력
