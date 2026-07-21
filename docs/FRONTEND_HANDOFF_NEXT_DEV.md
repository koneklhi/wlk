# 배포 UI 프론트엔드 인계

배포 PC(폐쇄망, http://localhost:8900)에서 도는 실시간 음성인식·번역 웹 UI다. 백엔드(FastAPI, whisperlivekit)가
React 빌드 결과물(dist)을 직접 서빙한다. 이전 개발자가 만든 dist를 백엔드에 붙이면서 나온 문제 중 백엔드에서
처리할 수 있는 건 처리했고, 프론트에서 고쳐야 하는 것만 아래에 남긴다.

## 백엔드 동작 (알고 있어야 할 것)

- dist를 `frontend/static/`에 두면 백엔드가 base(`/wlkies`)를 자동으로 잡아 서빙한다. 접속은 `localhost:8900`.
- **`localhost:8900/dev` = 백엔드 내장 데모 UI**(dist 유무와 무관하게 항상 뜬다). 배포 UI에서 뭔가 안 될 때
  같은 서버·같은 `/asr`를 내장 UI로 눌러보면 백엔드 문제인지 프론트 문제인지 바로 갈린다. 포트는 같고
  경로만 다르므로 서버를 따로 띄울 필요가 없다.
- 전사 WebSocket은 `/asr`. **연결 하나가 세션 하나다.** 빈 프레임(0바이트)을 보내면 그 세션은 끝나고
  `ready_to_stop`이 오며, 같은 연결로는 다시 전사할 수 없다. 다시 녹음하려면 새로 연결해야 한다.
- `/asr?language=ko|en|auto`로 세션 언어를 고정할 수 있다.
- **델타 전송이 추가됐다(선택 기능).** 기본값은 예전과 같은 전량 전송(full)이라 **지금 코드를 안 고쳐도 그대로
  동작한다**. 다만 세션이 길어지면 매 메시지가 전사 전체를 싣느라 점점 느려지는데, `/asr?mode=delta`로 연결하면
  첫 메시지만 `{"type":"snapshot"}` 전체이고 이후는 `{"type":"diff"}`로 **바뀐 뒷부분만** 와서 이 문제가 사라진다
  (실측 전송량 4.7배 절감). 대신 프론트가 누적해야 한다 — `diff`를 받으면 ① `lines_pruned`만큼 앞에서 지우고
  ② `common = n_lines - new_lines.length`를 구해 ③ `lines.slice(0, common).concat(new_lines)`로 **뒷부분을
  갈아끼운다**(뒤에 붙이면 안 된다 — 백엔드가 최근 줄을 나중에 고쳐 다시 보내기 때문에 중복된다)
  ④ `buffer_*`·`status`는 매번 그대로 교체 ⑤ 줄 수가 `n_lines`와 다르면 재연결.
  **전용 명세서 = `docs/DELTA_PROTOCOL_SPEC.md`**(복사해 쓸 참조 구현 포함), 계약 상세는 `docs/API_SPEC.md` §2.4.2.
  서버가 연결 직후 보내는 `config` 메시지의 `protocol` 필드로 현재 모드를 확인할 수 있다.
- REST: `/health`, 단어대치 `/api/corrections`(GET·POST, 삭제는 `DELETE /api/corrections/{단어}`),
  번역사전 `/api/prompts` · `/api/prompts/add-item` · `/api/prompts/delete-item`.
- 오디오는 MediaRecorder WebM Blob을 그대로 WS로 보낸다.

## 고쳐야 할 것

### [제가 직접 쓴 것]

5090 pc 안에 있는 dist 빌드파일에는 음성 시작,일시정지,종료 버튼이 보이는 것을 보면 구현이 되어 있는데 gitlab에 커밋된 코드 파일 내용에서는 해당 부분을 찾지 못했어요.

제 생각에는 현재 gitlab에 커밋된 코드 내용은 5090 pc에 있는 내용에 비해 구버전인것처럼 보입니다. 유주형상병님이 로컬에 개발한 뒤 dist 파일만 보내고 gitlab에 push를 안한거일 수도 있을 것 같아요.

우선 UI에서 시작 버튼을 눌러서 음성 받는건 되는데 이후에 "일시정지"나 "종료" 버튼이 안됩니다.  
 관리자 페이지 이동 버튼을 눌렀을때 에러가 납니다. 링크가 깨지는 것 같아요. 주소창에 직접 localhost:8900/wlkies/admin 을 치면 관리자 페이지 접속이 됩니다.

번역을 켰을때 UI 수정이 필요합니다. 번역 켰을때 전사 시간 숫자가 날라가고 , 문장이 확정되기 전 실시간 번역 내용의 위치가 원본 문장 아래에 있어야하는데 옆에 있는 것 처럼 보입니다.

UI상에서 언어 선택 기능이 어떻게 백엔드랑 연결이 되어 되어 있는지 확인해주세요. 잘 안되어서 우선 백엔드 단에서 서버를 킬때 --lan [ko,en,auto] 옵션을 주는 방식으로 키고 테스트 하고 있습니다.

### [클로드가 쓴 것]

1. **중지 후 재시작이 안 됨.** 시작은 되는데 중지/종료하고 다시 시작하면 전사가 안 온다(콘솔 에러 없음).
   위의 "1연결=1세션" 때문이다. 중지하면 그 연결의 세션이 끝나는데 프론트가 같은 연결을 재사용하려 한다.
   재시작할 때 WS를 새로 연결하도록 고치고, 중지/재개/초기화 버튼이 상태에 맞게 켜지고 꺼지게 정리해야 한다
   (지금은 중지하면 버튼이 먹통).

2. **중지할 때 콘솔 예외.** `Cannot read properties of null (reading 'current')`가 requestAnimationFrame
   콜백에서 뜬다. rAF 루프가 정리된 뒤에도 돌면서 null이 된 ref를 읽는 것이다. 루프를 cancelAnimationFrame으로
   확실히 멈추고 콜백 안에 null 가드를 넣으면 된다. 정확한 위치는 현행 소스에서 확인.

3. **관리자 페이지 이동 버튼이 404.** 버튼을 누르면 URL이
   `/wlkiesundefinedfunction search() { [native code] }undefined`처럼 깨져서 만들어진다. base를 포함한
   정상 경로(`/wlkies/admin`)로 이동하게 고쳐야 한다. 라우터 Link/navigate를 쓰면 basepath가 자동으로 붙는다.
   지금은 주소창에 `localhost:8900/wlkies/admin`을 직접 쳐서 우회 중.

4. **WebSocket 절대 URL.** 프론트가 `new WebSocket('/asr')`처럼 상대경로로 여는데, 배포 PC 브라우저(구버전)가
   상대 WS URL을 거부한다. 지금은 백엔드가 index.html에 보정 스크립트를 끼워 넣어 넘기고 있다. 프론트에서
   절대 URL로 만들면 그 보정을 걷어낼 수 있다.

   ```
   const base = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host;
   new WebSocket(base + '/asr');
   ```

5. **언어 선택이 실제로 전달되는지 확인.** 배포 UI에 언어(자동/한국어/영어) 선택이 이미 있다. 그 값이 WS 연결
   시 `?language=`로 붙는지만 확인하면 된다(DevTools Network에서 WS 요청 URL). 안 붙으면 연결 URL에
   `?language=선택값`을 추가.

## 참고

- 지금 백엔드가 임시로 받아주는 게 둘 있다. 하나는 4번의 WS URL 보정 스크립트, 다른 하나는 관리자 번역사전
  경로다. 프론트가 번역사전을 `/api/corrections/prompts...`로 부르는데 정본은 `/api/prompts...`라 백엔드가
  둘 다 받게 해뒀다. 프론트를 정본 경로로 맞추면 이 우회도 뺄 수 있다(급하진 않음).
- 백엔드가 진단할 때 넘겨받은 프론트 소스는 배포 dist보다 구버전이었다(언어 선택·관리자 버튼·재개 버튼이
  없었고 파형은 있었다). 위 내용은 배포 PC 실제 동작 기준이니 세부 구현은 현행 소스로 맞추면 된다.
- 새 dist는 `frontend/static/`에 index.html·assets를 덮어쓰고 Ctrl+F5 하면 반영된다. 백엔드 재기동 필요 없음.
- WS 메시지 형식이나 엔드포인트 동작 확인이 필요하면 백엔드팀에 요청.
