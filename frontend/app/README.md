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
    │   └── admin.tsx            # "/admin" — 단어교정 + 번역용어 + 번역예시 관리
    │
    ├── api/                     # REST API 클라이언트
    │   ├── corrections.ts       # 단어교정 사전 + 번역 사전(glossary/예시) CRUD
    │   └── health.ts            # 백엔드 헬스체크 (GET /health)
    │
    ├── assets/
    │   ├── fonts/Pretendard/    # Pretendard Variable 폰트 (직접 호스팅)
    │   └── images/              # 공군 로고
    │
    ├── components/
    │   ├── SttMain.tsx              # 메인 화면 (헤더/전사영역/설정드로어), 세션 렌더만 담당
    │   ├── SttSettingDrawer.tsx     # 오른쪽 슬라이드 설정 드로어
    │   ├── SttTextViewer.tsx        # 전사 행 1개 렌더 (원문+번역+선택적 시각)
    │   ├── SttTranslateLoader.tsx   # 번역 대기 로더
    │   ├── SttThemeProvider.tsx     # 테마 CSS 변수 주입 + useSttTextStyle 훅
    │   ├── WaveformVisualizer.tsx   # canvas 기반 실시간 파형 (useWaveform 사용)
    │   ├── BackendErrorOverlay.tsx  # 헬스체크 실패 시 오버레이
    │   └── ui/                      # shadcn 스타일 UI 프리미티브
    │       ├── alert-dialog.tsx     # 종료 확인 다이얼로그
    │       ├── button.tsx
    │       ├── input.tsx
    │       └── select.tsx
    │
    ├── constants/
    │   └── index.ts              # Api.{HEALTH,CORRECTIONS,PROMPTS,PROMPTS_ADD,PROMPTS_DELETE}, BASE_PATH, APP_VERSION
    │
    ├── hooks/
    │   ├── useSttSession.ts      # 세션 오케스트레이션 — 소켓·마이크 라이프사이클이 만나는 유일한 곳
    │   ├── useAudioRecorder.ts(+.test.ts) # 마이크 캡처 + WebM 인코딩 (MediaRecorder)
    │   ├── useTranscriptRows.ts  # store 슬라이스 → 화면 행 배열 파생 (useMemo)
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
        ├── transcriptRows.ts(+.test.ts)    # 서버 상태 → 화면 행 목록 파생 (순수 함수)
        ├── wsUrl.ts               # WebSocket URL 조립 (origin 기반 절대 URL)
        ├── fetchJson.ts           # JSON API 요청 헬퍼 (5초 timeout)
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
- 시각(HH:MM:SS) 표시 토글(기본 off — 투사 화면 방해 방지)
- 화자분리 UI 는 배포 UI 에 **탑재돼 있지 않다** — 서버가 화자 번호(`speaker`)를 보내도 화면에 별도 뱃지/색상으로 표시하지 않는다(`transcriptRows.ts` 설계 주석 참조)

### 관리자 페이지 (`/admin`, `routes/admin.tsx`)
- 단어교정 사전 CRUD (전사 후처리 오인식→정답 매핑)
- 번역 용어(glossary) + 번역 예시(sentence) CRUD (2분할 화면)
- 기본 내장 항목은 삭제 불가 — 서버가 HTTP 200 + `status:'warning'` 로 알려주며 토스트로 안내

### 백엔드 헬스체크
- 15초 간격 자동 폴링(`GET /health`)
- 실패 시 `BackendErrorOverlay` 표시, 수동 재연결(재확인) 지원

### 테마/설정 (`SttSettingDrawer`, `theme.store.ts`)
- 배경 색상 / 로고(타이틀) 배경 색상 / 로고 폰트 색상
- 원본·번역·시스템 폰트 크기 및 색상 개별 설정
- 로고 전체 크기 프리셋(`sm`=50% / `md`=100% / `lg`=150% / `xl`=200%, 타이틀·서브타이틀 폰트 크기·로고 이미지 크기 동시 변경)
- localStorage persist(key: `stt-theme-v2`), "설정 초기화" 버튼으로 기본값 복원

### 알림
- react-toastify 기반 토스트 — 세션 오류, 관리자 페이지 CRUD 성공/실패/경고

## 컴포넌트 가이드

### `SttMain`
메인 화면. 헤더(로고+타이틀), 전사 영역, 설정 드로어로 구성. 세션 제어 로직은 갖지 않고 `useSttSession()`/`useTranscriptRows()` 를
구독해 렌더만 한다. 자동 스크롤(바닥 근접 시에만 따라감), 헬스 폴링(15초), 세션 오류 토스트를 담당.

### `SttSettingDrawer`
오른쪽에서 슬라이드되는 설정 패널(Framer Motion). 버튼 활성/비활성은 세션 `phase` 에서 파생한다.
- 세션 제어(시작/일시중단/재개, 종료는 `AlertDialog` 확인 후)
- 언어 선택(`select`, 세션 시작 전에만 활성)
- 웨이브폼(`WaveformVisualizer`, 녹음/일시중단 중에만 표시)
- 테마·폰트·로고 설정, 시각 표시 토글, 기록/설정 초기화
- 관리자 페이지(`/admin`) 링크

### `SttTextViewer`
전사 행 1개 렌더 — 원문(진하게/연하게는 확정 여부에 따라) + 번역(대기 중이면 `SttTranslateLoader`) + 선택적 시각.
미확정 buffer 꼬리는 같은 문단 안에 이어 붙인다.

### `SttThemeProvider` / `useSttTextStyle`
`theme.store.ts` 값을 CSS 변수(`--stt-*`)로 주입하는 Provider 와, 원문/번역/시스템 텍스트 스타일을 반환하는 훅.

### `WaveformVisualizer` + `useWaveform`
`AnalyserNode` 를 `requestAnimationFrame` 으로 canvas 에 직접 그린다. `ResizeObserver` 로 컨테이너 크기 변화를 canvas 물리 크기(DPR 포함)에 동기화.

### `BackendErrorOverlay`
헬스체크 실패 시 표시되는 전체 화면 오버레이. 연결 시도 중/서버 오류(500)/네트워크 불가 상태를 구분해 안내.

### `routes/admin.tsx` (AdminPage)
단어교정(`words`) 탭과 번역교정(`translate_split`, 번역용어+번역예시 2분할) 탭으로 구성. `useItems()` 내부 훅이 각 데이터 소스(`words`/`translate_words`/`translate_sentence`)에 대해 조회/추가/삭제를 처리한다.

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
