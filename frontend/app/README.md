# wlkies-frontend

대한민국 공군 AI 실시간 음성 인식·번역 시스템 (STT) 프론트엔드

## Tech Stack

| 분야 | 기술 |
|------|------|
| 런타임 | React 19 + TypeScript 5.9 |
| 빌드 | Vite 7 |
| 스타일 | Tailwind CSS 4 + `tw-animate-css` |
| 라우팅 | TanStack Router 1 (파일 기반 코드 생성) |
| 상태 관리 | Zustand 5 (persist 미들웨어) |
| UI | Radix UI (Select, Slot, Tooltip) + `class-variance-authority` |
| 애니메이션 | Framer Motion |
| 아이콘 | Lucide React |
| 오디오 | MediaRecorder API + Web Audio API (AnalyserNode) |
| 통신 | WebSocket (whisperlivekit/wlk 프로토콜) + Fetch API |

## Project Structure

```
app/frontend/
├── index.html                 # 진입점 HTML (base: /wlkies)
├── package.json
├── vite.config.ts             # Tailwind plugin, 라우터 플러그인, Vite proxy
├── public/                    # 정적 자산 (배포용 로고)
└── src/
    ├── main.tsx               # React root 마운트
    ├── styles.css             # 전역 스타일 (Pretendard, Tailwind, CSS vars, keyframes)
    ├── router.tsx             # TanStack Router 인스턴스 (기반 경로 /wlkies 처리)
    ├── routeTree.gen.ts       # 파일 기반 라우터 자동 생성 (변경 금지)
    │
    ├── api/                   # REST API 클라이언트
    │   ├── corrections.ts     # 단어교정 사전 CRUD (GET/POST/DELETE)
    │   └── health.ts          # 백엔드 헬스체크
    │
    ├── assets/                # 정적 자원
    │   ├── fonts/             # Pretendard Variable 폰트
    │   └── images/            # 공군 로고 등
    │
    ├── components/            # UI 컴포넌트
    │   ├── SttMain.tsx        # 메인 STT 화면 (헤더/트랜스크립트/툴바)
    │   ├── SttSettingDrawer.tsx # 오른쪽 설정 슬라이드 드rawer
    │   ├── CorrectionsPanel.tsx # 단어교정 사전 UI
    │   ├── SpeakerBadge.tsx   # 화자 분할 뱃지 ( speaker별 색상)
    │   ├── BackendErrorOverlay.tsx # 서버 오류 오버레이
    │   └── ui/                # shadcn 스타일 UI 프리미티브
    │       ├── button.tsx     # Button (CVA 기반 바이어ント)
    │       └── input.tsx      # Input
    │
    ├── constants/
    │   └── index.ts           # Path 상수, Server URL 상수
    │
    ├── hooks/
    │   └── useAudioRecorder.ts # MediaRecorder 기반 오디오 녹음 훅
    │
    ├── stores/
    │   ├── stt.store.ts       # STT Zustand store (WebSocket 연동)
    │   └── theme.store.ts     # 테마 설정 persist store
    │
    ├── types/
    │   └── stt.ts             # whisperlivekit/wlk 프로토콜 타입 정의
    │
    └── utils/
        ├── fetchJson.ts       # JSON API 요청 헬퍼 (GET/POST/DELETE)
        └── index.ts           # cn() 유틸 (clsx + twMerge)
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   React Components               │
│  SttMain  │  SttSettingDrawer  │  Corrections    │
│            │                    │  Panel          │
├─────────────────────────────────────────────────┤
│              Zustand Stores                     │
│  stt.store.ts  │  theme.store.ts               │
├─────────────────────────────────────────────────┤
│              Hooks / Utils                      │
│  useAudioRecorder  │  fetchJson  │  cn()        │
├─────────────────────────────────────────────────┤
│              API Clients                        │
│  corrections.ts  │  health.ts                   │
├─────────────────────────────────────────────────┤
│         External Services (Backend)             │
│  WebSocket (/asr)  │  REST (/api/*, /health)    │
└─────────────────────────────────────────────────┘
```

### State Flow

1. **SttMain** 컴포넌트가 `useAudioRecorder` 훅으로 마이크 오디오 캡처
2. 오디오 청크(Blob)를 `useSTTStore.sendAudioChunk()`를 통해 WebSocket으로 전송
3. 백엔드(whisperlivekit)가 전사·화자분할·번역 결과를 WebSocket 스냅샷으로 푸시
4. `useSTTStore.handleMessage()`가 메시지를 파싱하여 Zustand 상태 갱신
5. Zustand 리렌더링으로 컴포넌트에 실시간 트랜스크립트 표시

### wlk 프로토콜 요약

| 메시지 타입 | 방향 | 설명 |
|-------------|------|------|
| `config` | 서버 → 클라이언트 | 오디오 설정 (useAudioWorklet 여부) |
| `ready_to_stop` | 서버 → 클라이언트 | 녹음 종료 준비 |
| `WsStateSnapshot` | 서버 → 클라이언트 | 전사 상태 스냅샷 (lines, buffer, status) |
| 오디오 Blob | 클라이언트 → 서버 | MediaRecorder WebM 청크 (100ms) |

## Quick Start

### 설치

```bash
cd app/frontend
pnpm install
```

### 개발 서버

```bash
pnpm dev
```

- 로컬: `http://localhost:5173/wlkies`
- Vite proxy가 백엔드 서버(`48.2.40.84:8900`)로 요청 전달

| 경로 패턴 | 대상 | 프로토콜 |
|-----------|------|----------|
| `/wlkies/asr`, `/asr` | `ws://48.2.40.84:8900` | WebSocket |
| `/wlkies/api` | `http://48.2.40.84:8900` | HTTP |
| `/wlkies/health`, `/health` | `http://48.2.40.84:8900` | HTTP |

### 빌드

```bash
pnpm build
```

빌드 출력: `app/backend/src/main/resources/static/` (Spring Boot 정적 파일)

## Environment Variables

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `VITE_WS_URL` | `/asr` | WebSocket 서버 URL (절대경로) |
| `VITE_CORRECTIONS_URL` | `/api/corrections` | 단어교정 사전 API 엔드포인트 |

## 주요 기능

### 음성 인식 (STT)
- 마이크 오디오 캡처 (MediaRecorder / WebM)
- 실시간 WebSocket 스트리밍 (whisperlivekit wlk 프로토콜)
- 화자 분할 (Diarization) — 최대 8명 색상 구분
- 실시간 전사·번역 결과 표시
- 자동 재연결 (최대 5회, 1초 간격)

### 단어교정 사전
- REST API 연동 (GET/POST/DELETE)
-잘못된 단어 → 올바른 단어 매핑
- 실시간 목록 조회 및 추가/삭제

### 백엔드 헬스체크
- 15초 간격 자동 모니터링
- 서버 오류(500) 시 오버레이 표시
- 수동 재연결 지원

### 테마/설정
- 배경·헤더 색상 커스터마이징
- 로고 크기 조정 (50%/100%/150%/200%)
- localStorage에 설정 자동 persist

## 컴포넌트 가이드

### `SttMain`
메인 화면. 헤더, 상태 바, 웨이브폼, 트랜스크립트, 툴바 영역으로 구성.
- `useAudioRecorder` 훅으로 오디오 캡처
- `useSTTStore`로 WebSocket 상태 구독
- Canvas 기반 실시간 waveform 렌더링

### `SttSettingDrawer`
오른쪽에서 슬라이드되는 설정 패널. 섹션별 콜라apsible 구조.
- 연결 설정 (WS connect/disconnect)
- 녹음 제어 (시작/중지/초기화)
- 디스플레이 설정 (색상/로고 크기)

### `SpeakerBadge`
화자 ID를 색상 뱃지로 표시. speaker 값별 특수 처리:
- `-2`: 침묵 세그먼트 (음량 아이콘)
- `0`: 화자분할 처리 중 (로딩 아이콘)
- `1~`: 일반 화자 (8색 순환)

## 스크립트

```bash
pnpm dev          # 개발 서버
pnpm build        # 프로덕션 빌드
pnpm preview      # 빌드 결과 미리보기
pnpm lint         # ESLint
```
