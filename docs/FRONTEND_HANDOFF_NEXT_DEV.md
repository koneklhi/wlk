# 배포 UI 프론트엔드 인계 — 처리 결과

> **상태 (2026-07-21 갱신)**: 배포 PC에서 개발 중이던 React 소스가 개발 PC 저장소로 반입됐다
> (`frontend/app/`, 브랜치 `feat/deploy-ui`). 아래 이슈는 **전부 개발 PC에서 처리 완료**했고
> 통합 검증까지 마쳤다. 남은 일은 새 dist를 배포 PC로 반입해 실환경에서 재확인하는 것이다.
>
> 이 문서는 이제 **인계 지시서가 아니라 처리 이력**이다. 프론트 계약 정본은
> [API_SPEC.md](API_SPEC.md) · [DELTA_PROTOCOL_SPEC.md](DELTA_PROTOCOL_SPEC.md) ·
> [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md)다.

배포 PC(폐쇄망, http://localhost:8900)에서 도는 실시간 음성인식·번역 웹 UI다. 백엔드(FastAPI, whisperlivekit)가
React 빌드 결과물(dist)을 직접 서빙한다.

## 백엔드 동작 (알고 있어야 할 것)

- dist를 `frontend/static/`에 두면 백엔드가 base(`/wlkies`)를 자동으로 잡아 서빙한다. 접속은 `localhost:8900`.
  개발 PC에서는 `frontend/app`에서 `pnpm build`하면 `frontend/static/`으로 바로 떨어진다.
- **`localhost:8900/dev` = 백엔드 내장 데모 UI**(dist 유무와 무관하게 항상 뜬다). 배포 UI에서 뭔가 안 될 때
  같은 서버·같은 `/asr`를 내장 UI로 눌러보면 백엔드 문제인지 프론트 문제인지 바로 갈린다. 포트는 같고
  경로만 다르므로 서버를 따로 띄울 필요가 없다.
- 전사 WebSocket은 `/asr`. **연결 하나가 세션 하나다.** 빈 프레임(0바이트)을 보내면 그 세션은 끝나고
  `ready_to_stop`이 오며, 같은 연결로는 다시 전사할 수 없다. 다시 녹음하려면 새로 연결해야 한다.
- `/asr?language=ko|en|auto`로 세션 언어를 고정할 수 있다. **3글자 코드(`kor`/`eng`)는 허용값이 아니다** —
  보내면 경고 로그만 남기고 무시된다.
- **델타 전송**은 `?mode=delta`로 opt-in한다(서버 기본값은 `full`). 전용 명세 = `docs/DELTA_PROTOCOL_SPEC.md`.
- REST: `/health`, 단어대치 `/api/corrections`(GET·POST, 삭제는 `DELETE /api/corrections/{단어}`),
  번역사전 `/api/prompts` · `/api/prompts/add-item` · `/api/prompts/delete-item`,
  전사 저장 `POST /api/save-transcript`.
- 오디오는 MediaRecorder WebM Blob을 그대로 WS로 보낸다.

## 처리 결과

### 사용자가 지적한 것

| 지적 | 결과 |
|---|---|
| 커밋된 코드가 5090 PC dist보다 구버전으로 보임 | **확인됨.** 이후 배포 PC의 현행 소스(`wlkies-feat-1`)를 받아 저장소에 반입 — 시작/일시정지/종료 버튼·언어 선택·관리자 링크가 모두 들어 있는 신버전이었다 |
| 시작은 되는데 일시정지/종료가 안 됨 | **수정.** 아래 클로드 항목 1번과 같은 원인 |
| 관리자 페이지 이동 버튼 에러 | **수정.** 아래 3번 |
| 번역 켰을 때 전사 시간 숫자가 날아감 | 현행 소스는 타임스탬프를 아예 렌더하지 않았다 → **선택 기능으로 신규 구현**(설정 드로어 '시각 표시', 기본 숨김) |
| 실시간 번역이 원본 아래가 아니라 옆에 표시 | 현행 소스에서는 이미 `flex-col`로 아래 배치 — **구버전 dist 이슈, 해소됨** |
| 언어 선택이 백엔드와 연결됐는지 확인 필요 | **원인 규명 + 수정.** 아래 5번. 이제 `--lan` 없이 UI에서 선택하면 된다 |

### 클로드가 지적한 것

1. **중지 후 재시작이 안 됨** → **수정.** `connect()`가 "이미 연결돼 있으면 즉시 return"하는 구조라
   종료 후 새 연결을 열지 않았다. 소켓 생성을 `beginSession()` 한 곳으로 모으고, 재시작·재개·자동재연결·
   desync 재동기를 전부 같은 경로로 통일했다. 버튼 활성/비활성도 세션 상태에서 파생하도록 바꿨다.
   - ⚠️ **함께 발견된 더 위험한 문제**: 소켓만 새로 열고 `MediaRecorder`를 재사용하면 안 된다.
     WebM 헤더는 **첫 blob에만** 실리므로, 새 세션의 FFmpeg가 헤더 없는 클러스터를 받아
     **에러도 close도 없이 영구 무출력**이 된다(소켓은 열려 있고 화면만 멈춘 것처럼 보인다).
     세션마다 인코더를 새로 만들도록 했고, 브라우저 통합 검증으로 재개 후 자막이 실제로 이어지는 것까지 확인했다.
2. **중지할 때 rAF null ref 예외** → 현행 소스에는 이미 `cancelAnimationFrame` 정리와 null 가드가 있었다.
   **해소 상태로 확인.**
3. **관리자 페이지 이동 버튼 404** → **수정.** 커스텀 `createBrowserHistory`의 `parseLocation`/`createHref`가
   라이브러리 타입과 맞지 않아(location 객체가 아니라 string을 받는다) URL이 깨졌다.
   TanStack Router 기본 `basepath`로 교체.
4. **WebSocket 절대 URL** → **수정.** `window.location` 기준으로 절대 URL을 조립한다.
   특정 PC IP(`ws://48.2.40.30:8900`)를 `.env`에 박아 빌드하던 것도 제거 — 이제 배포 PC에서 무설정 동작한다.
5. **언어 선택이 실제로 전달되는지** → **원인 규명.** 두 가지가 겹쳐 있었다.
   ① UI가 `?language=kor|eng`를 보냈는데 서버 허용값은 `ko|en`이라 무시됐다.
   ② `connect()` early return 탓에 드롭다운을 바꿔도 재연결 자체가 일어나지 않았다(항상 no-op).
   둘 다 수정. `AUTO`도 생략이 아니라 명시 전송한다 — 생략하면 서버 전역 `--lan`을 따라가서,
   `--lan ko`로 띄운 서버에선 AUTO를 골라도 한국어로 고정되기 때문이다.

### 추가로 발견해 고친 것 (지적 목록에 없던 것)

- **델타 메시지를 통째로 버리고 있었다.** 디스패처가 "`type` 필드가 있으면 제어 메시지"로 갈라서
  `snapshot`/`diff`가 마지막 bare return으로 폐기됐다. 서버를 `--ws-protocol delta`로 올리는 순간
  화면이 백지가 되는 상태였다. 판별 기준을 "type 값이 무엇인가"로 바꾸고 재구성 로직을 이식했다.
- **세그먼트 dedup 키가 복합키였다.** 인계 문서(구버전)가 `start|end|speaker`를 명시적으로 지시했는데,
  저장소 정본은 `id` 단독을 요구한다(문장이 자라도 불변). `end`가 자라면 키가 갈라져
  같은 문장의 절단판이 새 항목으로 계속 쌓이고 순서까지 뒤집혔다.
- **헬스체크가 항상 실패하고 있었다.** `/wlkies/health`를 호출했는데 백엔드 라우트는 `/health`고
  `/wlkies/*`는 SPA fallback이라 HTML이 돌아왔다. 그 탓에 오류 오버레이는 영영 뜨지 않는 죽은 코드였다.
- **`buffer_diarization`을 렌더하지 않았다.** 화자분할 ON일 때 최근 발화가 몇 초간 화면에서 증발한다.
- **미확정 줄을 1개만 렌더했다.** 나머지는 화면에서 사라졌다.
- **`pnpm typecheck`가 0개 파일을 검사하고 있었다.** 루트 `tsconfig.json`이 solution 파일인데
  `tsc --noEmit`은 `-b` 없이 references를 따라가지 않는다. 고치자 기존 타입에러 15건이 드러났고
  (그중 관리자 페이지 8건은 탭 분기가 죽은 코드였다) 전부 해소했다. `pnpm lint`도 eslint가
  devDependencies에 없어 실행 불가 상태였다.
- **마운트 시 WS 자동 연결**을 제거했다. 연결 = 서버 세션 생성(FFmpeg + 파이프라인 기동)이라
  아무도 녹음하지 않는 페이지 로드마다 고아 세션이 생겼다.

### 실장치 검증에서 추가로 드러난 것 (2026-07-21)

개발 PC에서 서버를 띄우고 시작을 눌렀는데 전사가 한 줄도 나오지 않는다는 보고가 있었다.
**전사 파이프라인은 정상이었다** — 실제 브라우저 + 실장치 마이크(VBCable CABLE Output)로
`ytn2`(109초 한↔영 코드스위칭)를 넣으니 12줄이 정상 전사됐고 콘솔 에러도 없었다
(WS `?language=auto&mode=delta` 1개 연결, delta 631프레임 수신).

원인은 **실패가 침묵으로 끝나는 구조**였다. 두 가지를 고쳤다.

1. **오류가 화면에 안 보였다.** `failSession()` 이 저장하는 `lastError` 를 렌더하는 코드가
   어디에도 없어, 마이크 권한 거부·연결 실패가 드로어 상태점 색만 바꾸고 끝났다. 사용자에게는
   "시작을 눌러도 아무 일도 안 일어남" 으로 보인다. 이제 toast 로 내보내고, `getUserMedia` 의
   DOMException 을 원인별 한국어 안내로 바꾼다(권한 거부 → 주소창 자물쇠, 장치 없음 →
   Windows 소리 설정, 점유 → 다른 프로그램 확인).
2. **소리가 안 들어오는 것도 안 보였다.** 녹음 중인데 8초가 지나도록 표시할 전사가 한 줄도
   없으면 상태 라벨을 '입력 음성 없음' 으로 바꾼다.
   ⚠️ 서버의 `status: "no_audio_detected"` 는 이 판정에 **쓸 수 없다** — 무음이 이어지면 서버가
   침묵 세그먼트(`speaker:-2, text:""`)를 만들어 `lines` 가 비지 않으므로, 그 status 는 세션 첫
   스냅샷(seq=1)에만 잠깐 나오고 이후로는 계속 `active_transcription` 이다(실측 확인).

**검증 방식의 교훈**: 기존 E2E 는 Chromium 가짜 마이크(`--use-file-for-fake-audio-capture`)로만
돌아 실장치 `getUserMedia` 경로(권한 프롬프트·사이트별로 저장된 마이크 선택·앱별 출력 장치)를
한 번도 밟지 않았다. 그래서 사용자 환경에서만 나는 실패를 못 잡았다. 또한 headless Chromium 은
실장치가 없어 권한 허용/거부와 무관하게 항상 `NotSupportedError` 를 내므로 `NotAllowedError`
분기는 브라우저로 재현할 수 없다 — 단위 테스트(`useAudioRecorder.test.ts`)로 덮었다.

## 아직 남은 것

- **백엔드 임시 우회 2개는 아직 제거하지 않았다.** 배포 PC가 여전히 구 dist로 돌고 있어,
  지금 걷어내면 그쪽이 깨진다. **새 dist 반입 → 실환경 확인 후** 제거한다.
  - `basic_server.py`의 `_WS_SHIM`(index.html에 주입하는 WS URL 보정 스크립트)
  - `/api/corrections/prompts*` alias (정본은 `/api/prompts*`)
- 화자 분리 UI(화자 배지·색상)는 **배포 UI에 넣지 않기로** 결정됨.

## 검증 방법

```powershell
cd frontend\app
pnpm install
pnpm typecheck   # 0 errors
pnpm test        # 단위 30건 (델타 재구성·행 병합·마이크 오류 매핑)
pnpm build       # -> frontend\static\
```

> `pnpm lint` 는 이 저장소로 반입되기 전부터 있던 5건(`react-refresh/only-export-components` 4건 +
> `admin.tsx` 의 `set-state-in-effect` 1건)이 남아 있어 exit 1 로 끝난다. 신규 변경분은 0건이다.

서버를 띄우고 `http://localhost:8900/` 접속(자동으로 `/wlkies/`로 리다이렉트).
확인 항목: WS URL에 `mode=delta&language=`가 붙는지 / 시작→일시중단→**재개 시 자막이 이어지는지** /
장시간 전사에서 중복 줄이 없는지 / 침묵 구간에서 자막이 사라지지 않는지 / 저장 버튼이
`--transcript-save-dir`에 파일을 남기는지 / 종료 후 재시작이 되는지.
