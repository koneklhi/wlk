# 프로젝트 개요

**wlkies-frontend** — 대한민국 공군 AI 실시간 음성 인식·통역(STT) 시스템 프론트엔드

- 백엔드: whisperlivekit + Spring Boot
- 빌드 산출물: `../backend/src/main/resources/static/` (Spring Boot 정적 파일)
- 배포 기본 경로: `/wlkies`

---

## 기술 스택

| 분야 | 기술 |
|------|------|
| 런타임 | React 19 + TypeScript 5.9 |
| 빌드 | Vite 7 |
| 스타일 | Tailwind CSS 4 + `tw-animate-css` |
| 라우팅 | TanStack Router 1 (파일 기반 코드 생성) |
| 상태 관리 | Zustand 5 (persist 미들웨어) |
| UI | Radix UI (Select, Slot, Tooltip) + CVA |
| 애니메이션 | Framer Motion |
| 아이콘 | Lucide React |
| 오디오 | MediaRecorder API + Web Audio API (AnalyserNode) |
| 통신 | WebSocket (wlk 프로토콜) + Fetch API |

---

## 코드 컨벤션

### 파일명
- 컴포넌트: `PascalCase.tsx`
- 유틸/훅/API: `camelCase.ts`
- 폴더 기반 구조 (src/api, src/components, src/hooks, src/stores 등)

### TypeScript
- `strict: true` (tsconfig.app.json)
- JSDoc `@fileoverview`로 파일 헤더 작성 (필수는 아니나 선호)
- 타입 정의는 `src/types/`에 수집 (`stt.ts` 등)
- `as const`를 상수 객체에 적용

### 스타일링
- Tailwind CSS 유틸리티 클래스 사용
- 동적 클래스 병합은 `cn()` (`src/utils/index.ts`, clsx + tailwind-merge)
- CSS 변수 (`var(--*)`)를 전역 테마에 사용 (`src/styles.css`)
- 폰트: Pretendard Variable (직접 호스팅, `@font-face`)

### 상태 관리
- 전역 상태: Zustand (`src/stores/`)
- persist 미들웨어로 설정 저장 (key: `stt-theme`, `stt-theme-v2`)
- 로컬 상태: `useState` / `useRef`

### API 통신
- REST: `fetchJson<T>()` (`src/utils/fetchJson.ts`) — GET/POST/DELETE, 5초 타임아웃
- WebSocket: 직접 `WebSocket` API + `stt.store.ts` 핸들러
- 백엔드 연결 상수는 `src/constants/index.ts`

### 임포트
- Path alias `@/` → `src/` (tsconfig + vite config)
- 상대 경로 대신 `@/` 사용

### 라우팅
- TanStack Router 파일 기반 코드 생성
- `src/routes/` 폴더에 라우트 파일 배치 (`__root.tsx`, `index.tsx` 등)
- `src/routeTree.gen.ts`는 자동 생성 — 직접 수정 금지
- `pnpm dev` 실행 시 `rms doctor` (TanStack Router Doctor) 자동 실행

---

## 개발 명령어

```bash
pnpm install          # 의존성 설치
pnpm dev              # 개발 서버 (http://localhost:5173/wlkies)
pnpm build            # 프로덕션 빌드 → ../backend/src/main/resources/static/
pnpm preview          # 빌드 결과 미리보기
pnpm lint             # ESLint
pnpm typecheck        # tsc --noEmit
```

### Vite Proxy (개발)
- `/asr` → `ws://VITE_SERVER_HOST:VITE_SERVER_PORT` (WebSocket)
- `/api` → `http://VITE_SERVER_HOST:VITE_SERVER_PORT` (HTTP)
- `/health` → `http://VITE_SERVER_HOST:VITE_SERVER_PORT` (HTTP)

서버 주소는 `.env`의 `VITE_SERVER_HOST`, `VITE_SERVER_PORT`로 설정.

---

## 프로젝트 구조

```
src/
├── api/                    # REST API 클라이언트 (corrections, health)
├── assets/                 # 폰트(Pretendard), 이미지(공군 로고)
├── components/
│   ├── SttMain.tsx         # 메인 STT 화면 (헤더/트랜스크립트/툴바)
│   ├── SttSettingDrawer.tsx # 오른쪽 설정 슬라이드 드로어
│   ├── ConfirmDialog.tsx   # 종료 확인 팝업
│   ├── SpeakerBadge.tsx    # 화자 분할 뱃지
│   ├── BackendErrorOverlay.tsx # 서버 오류 오버레이
│   └── ui/                 # shadcn 스타일 UI 프리미티브 (button, input, select)
├── constants/index.ts      # 서버 URL 상수
├── hooks/
│   ├── useAudioRecorder.ts # MediaRecorder 기반 오디오 녹음 훅
│   └── useWaveform.ts      # Canvas 기반 웨이브폼 훅
├── routes/                 # TanStack Router 파일 기반 라우트
├── router.tsx              # TanStack Router 인스턴스 (/wlkies 기반 경로 처리)
├── stores/
│   ├── stt.store.ts        # STT WebSocket 상태 (Zustand)
│   └── theme.store.ts      # 테마 설정 persist store
├── styles.css              # 전역 스타일 (Pretendard, Tailwind, CSS vars)
├── types/stt.ts            # whisperlivekit/wlk 프로토콜 타입
└── utils/
    ├── fetchJson.ts        # JSON API 요청 헬퍼 (5초 타임아웃)
    └── index.ts            # cn() 유틸 (clsx + twMerge)
```

---

## 핵심 아키텍처

### STT 데이터 흐름

1. `SttMain` → `useAudioRecorder` 훅으로 마이크 오디오 캡처 (WebM, 100ms interval)
2. 오디오 Blob → `useSTTStore.sendAudioChunk()` → WebSocket 전송
3. 백엔드(whisperlivekit) → WebSocket 스냅샷 푸시 (전사·화자분할·번역)
4. `useSTTStore.handleMessage()` 파싱 → Zustand 상태 갱신
5. 리렌더링 → 실시간 트랜스크립트 표시

### wlk 프로토콜 메시지 타입

| 메시지 | 방향 | 설명 |
|--------|------|------|
| `config` | 서버→클라이언트 | 오디오 설정 (useAudioWorklet) |
| `ready_to_stop` | 서버→클라이언트 | 녹음 종료 준비 |
| `WsStateSnapshot` | 서버→클라이언트 | 전사 상태 스냅샷 (lines, buffer, status) |
| 오디오 Blob | 클라이언트→서버 | MediaRecorder WebM 청크 |

### 상태 관리 패턴

- `stt.store.ts`: WebSocket 연결/재연결, 메시지 파싱, 녹음 흐름(`RecordFlow`)
- `theme.store.ts`: 테마 설정 (색상, 로고 크기, 폰트 크기/색상), localStorage persist
- 재연결: 최대 5회, 1초 간격 (비정상 close 시에만)

---

## 환경 변수

| 변수 | 설명 |
|------|------|
| `VITE_BASE_URL` | 라우팅 접두사 (기본: `/wlkies`) |
| `VITE_SERVER_HOST` | 개발 서버 호스트 |
| `VITE_SERVER_PORT` | 개발 서버 포트 (기본: `8900`) |
| `VITE_WS_URL` | WebSocket 절대 URL (설정 시 로컬 경로 대신 사용) |
| `VITE_CORRECTIONS_URL` | 단어교정 사전 API 엔드포인트 |
| `VITE_APP_VERSION` | 앱 버전 |

---

## 참고 문서

- `README.md` — 프로젝트 상세 설명, 컴포넌트 가이드
- `docs/implementation-plan.md` — 현재 구현 계획
- `docs/overengineering-audit.md` — 코드 단순화 감사 리포트
- `../../docs/API_SPEC.md` — 서버 REST/WebSocket 계약 정본
- `../../docs/DELTA_PROTOCOL_SPEC.md` — 델타 프로토콜 재구성 알고리즘 정본
- `../../docs/SCHEMA_CHANGES.md` — WebSocket 메시지 스키마 변경 이력
