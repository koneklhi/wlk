# 프론트엔드 배선 이슈 패치 스펙 — WS URL + 언어선택 (핸드오프)

> 대상: 배포 React UI(`wlkies-frontend`) 개발자.
> 배경: 배포 PC UI 백지 원인(Vite `base:/wlkies` ↔ 백엔드 루트 서빙 불일치)은 **백엔드에서 해결됨**
> (master `fix/frontend-base-serving`, base 자동추출 하위 서빙). 이 문서는 그와 별개로, 조사 중 발견된
> **프론트 배선 2건**(① WebSocket 상대 URL 거부, ② 언어선택 미배선)을 프론트에서 마무리하기 위한 스펙이다.

## 0. WebSocket 절대 URL 사용 (필수)

**증상**: 배포 PC 브라우저에서 전사가 시작되지 않고, 콘솔에 `The URL '/asr' is invalid` 류 오류.

**원인**: 프론트가 `new WebSocket('/asr')`처럼 **슬래시로 시작하는 상대 URL**을 넘긴다. 최신 브라우저는
이를 현재 origin 기준으로 해석하지만, **구형·에어갭(폐쇄망) 브라우저는 상대 WebSocket URL을 거부**한다
(WebSocket 생성자는 원래 절대 URL을 요구한다).

**정식 해결(프론트)**: WS URL을 항상 **절대 URL로 조립**한다. `/asr`(그리고 §2의 `?language=`)를 붙이기 전에:

```ts
const wsBase = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
connect(`${wsBase}/asr`); // 필요하면 `?language=${lang}` 추가 (§2)
```

**임시 우회(백엔드, 현재 적용 중)**: 백엔드가 index.html을 서빙할 때 `<head>`에 shim `<script>`를 1회 주입해,
슬래시로 시작하는 상대 WS URL을 런타임에 `ws[s]://<host>/asr` 절대 URL로 정규화한다
(`whisperlivekit/basic_server.py`의 `_WS_SHIM`/`_index_html_response`). 이 덕에 **dist 재빌드 없이도**
현재 프론트가 배포 PC에서 동작한다. 프론트가 위 절대 URL 조립으로 고치면 shim은 **무해하게 통과**(이미
절대 URL이면 그대로 반환)하며, 정식 수정 후에는 백엔드 shim을 제거해도 된다.

## 1. 무엇이 문제인가 (언어선택)

세션 언어모드(한국어/영어/자동)는 **세션 시작 시 사용자가 선택**하는 배포 요구사항이다(백엔드 CLAUDE.md §3.2).
백엔드는 이를 위해 **WebSocket 접속 시 쿼리 파라미터 `?language=`를 이미 수용**한다:

- 엔드포인트: `ws://<origin>/asr?language=<code>`
- 허용값: `auto` | `ko` | `en` (그 외 값은 무시하고 서버 전역 기본값 사용)
- 근거: `whisperlivekit/basic_server.py`의 `/asr` 핸들러 — `websocket.query_params.get("language")`를
  읽어 `AudioProcessor(language=...)`에 전달. `docs/FRONTEND_HANDOFF_SUMMARY.md` §쿼리 파라미터 참조.

그러나 현재 프론트는 언어를 **전혀 전송하지 않는다**:

- `src/stores/stt.store.ts`의 `connect(url)`는 받은 url로 그대로 `new WebSocket(url)`.
- 호출부는 두 곳 모두 **하드코딩 `/asr`**(쿼리 없음):
  - `src/components/SttSettingDrawer.tsx` — "연결" 버튼 `onClick={() => connect('/asr')}`
  - `src/components/SttMain.tsx` — BackendErrorOverlay `onClose={() => ...connect('/asr')}`
- 드로어에 **언어 선택 UI 자체가 없다**(연결/녹음/디스플레이 3섹션뿐).

→ 결과: 항상 서버 전역 기본값(`--lan`, 기본 `auto`)으로만 동작. 사용자가 세션 언어를 고를 수 없다.

## 2. 프론트에서 할 일 (최소 변경)

### 2-1. 언어 상태 추가
`stt.store.ts`(또는 별도 settings store)에 세션 언어 상태 추가:

```ts
// STTStore 타입에 추가
sessionLanguage: 'auto' | 'ko' | 'en';
setSessionLanguage: (lang: 'auto' | 'ko' | 'en') => void;

// 초기값 / 액션
sessionLanguage: 'auto',
setSessionLanguage: (lang) => set({ sessionLanguage: lang }),
```

(선택 유지가 필요하면 zustand `persist` 사용 — theme.store 패턴 참고.)

### 2-2. 접속 URL에 쿼리 부착
`connect()` 호출 시 현재 선택 언어를 쿼리로 붙인다. 두 방법 중 하나:

- **간단(호출부에서 조립)**: `connect('/asr')` → 아래로 교체
  ```ts
  const lang = useSTTStore.getState().sessionLanguage;
  connect(`/asr?language=${lang}`);
  ```
  - `SttSettingDrawer.tsx` "연결" 버튼과 `SttMain.tsx` 에러재시도 onClose **둘 다** 교체.
- **권장(store가 조립)**: `connect`를 인자 없이 부르게 하고 store 내부에서
  `const url = \`/asr?language=${get().sessionLanguage}\`` 로 조립 → 호출부 중복 제거.

> 주의: `auto`도 명시 전송해도 무방(백엔드가 허용값). 굳이 생략 최적화할 필요 없음.

### 2-3. 언어 선택 UI 추가
`SttSettingDrawer.tsx`의 "연결"(또는 새 "언어") 섹션에 select 추가. **연결 전에만** 바꿀 수 있게
(`disabled={isConnected}`) 하는 것을 권장 — 세션 도중 언어 변경은 재접속을 의미하기 때문:

```tsx
<select
  value={sessionLanguage}
  disabled={isConnected}
  onChange={(e) => setSessionLanguage(e.target.value as 'auto' | 'ko' | 'en')}
>
  <option value="auto">자동(코드스위칭)</option>
  <option value="ko">한국어</option>
  <option value="en">English</option>
</select>
```

## 3. 검증
1. 언어를 `ko`로 선택 후 연결 → DevTools Network의 WS 요청 URL이 `/asr?language=ko`인지 확인.
2. 백엔드 서버 로그에 `WebSocket connection opened. language=ko` 가 찍히는지 확인
   (`basic_server.py`가 세션 언어 수신 시 로깅).
3. `auto`/`en`도 동일 확인.

## 4. 범위 밖(참고)
- **완전한 ko/en 세션 고정 거동**(코드스위칭 재감지·주기 재확인·화자전환 eager 재감지 비활성화 등)은
  백엔드 `feat/session-lang-lock` 브랜치가 master에 머지돼야 완결된다. 현재 master의 `?language=`는
  **초기 언어를 고정**하는 수준까지 동작한다(그 이상은 후속).
- 드로어 메인 정지 버튼이 `endRecording()`만 호출하고 WS 종료 프레임(`stopRecording()` = 빈 `ArrayBuffer`)은
  "초기화" 버튼에서만 보내는 점도 관찰됨 — 정지 시 마지막 문장 확정을 원하면 정지 버튼에서도
  `stopRecording()`을 함께 부르는 것을 검토(백엔드 API 불일치는 아님, UX 개선 사항).
