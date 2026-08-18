# WhisperLiveKit API 명세서 — React 프론트엔드 연동용

> **범위**: 배포 React UI가 실제로 사용하는 백엔드 계약만 정식 명세로 정리한다 —
> 실시간 전사 WebSocket `/asr` 1개 + 애플리케이션 REST 엔드포인트(`/health`,
> `/api/save-transcript`, `/api/corrections`, `/api/prompts`). OpenAI/Deepgram 호환 계층
> (`/v1/audio/transcriptions`, `/v1/listen` 등)은 이 프론트와 무관하며 상세는
> [0.Metafile/docs/API.md](../0.Metafile/docs/API.md) 참조.
>
> 문서 기준: 전사 라인 리텐션 = **무제한**, 번역 glossary 관리 API·진행중 번역 구현 완료. 값·기본값은 §6 참조.

---

## 1. 개요

| 항목                   | 값                                                        |
| ---------------------- | --------------------------------------------------------- |
| 백엔드 주소(개발)      | `ws://<개발 서버 IP>:8900` · `http://<개발 서버 IP>:8900` |
| 백엔드 주소(배포)      | **same-origin**(방법 A, §1.1)                             |
| WebSocket 스킴         | `ws://` (TLS 시 `wss://`)                                 |
| REST 스킴              | `http://` (TLS 시 `https://`)                             |
| 인증                   | 없음(폐쇄망 내부망 전제)                                  |
| 요청 콘텐츠 타입(REST) | `application/json`                                        |
| 문자 인코딩            | UTF-8                                                     |

**구성**: 전사·화자분할·번역 실시간 스트림은 전부 **단일 WebSocket `/asr`** 로 흐른다
(제어·오디오 송신·결과 수신 통합). REST는 부가 기능(헬스체크·단어교정 사전·번역 glossary 등)만 담당한다.

### 1.1 연결 대상 · 배포 방식 (방법 A)

- **개발 중**: 백엔드·프론트 모두 같은 개발 PC에서 구동한다(단일 호스트). 백엔드는 `localhost:8900`, Vite dev
  서버는 `localhost:5173`이며 `/asr`·`/api`·`/health`를 Vite 프록시로 8900에 전달한다(`vite.config.ts`).
  마이크(`getUserMedia`)는 보안 컨텍스트(`https` 또는 `localhost`)에서만 동작하는데, 둘 다 localhost라 문제 없다.
- **배포 = 방법 A(단일 프로그램)**: 단일 PC 로컬 전용. wlk 백엔드가 React **빌드 산출물(`dist/`)을 `/`에서 서빙**하도록 통합한다(정적 마운트 + SPA fallback — 기존 wl이 쓰던 방식과 동일). 사용자는 그 PC에서 `localhost:8900`으로 접속 → localhost라 마이크도 http로 정상, **HTTPS 불필요**. **구현 완료** — `whisperlivekit/basic_server.py` + `--frontend-dir` 플래그(기본값 `frontend/static`, 저장소 루트 기준 상대경로). `frontend/static/index.html`이 있으면 그 dist를 서빙하고 `assets`를 마운트, 그 외 경로는 SPA fallback으로 `index.html`을 반환한다. `index.html`이 없으면(개발 PC 등) 기존 내장 데모 UI로 자동 폴백한다. **dist가 Vite `base`(예 `/wlkies`)로 빌드된 경우**, 백엔드가 `index.html`의 자산 참조에서 base를 자동 추출해 그 하위(`/wlkies/assets`, `/wlkies/{spa}`)로 서빙하고 `GET /`는 base로 리다이렉트한다. base는 `--frontend-base`(기본값 `auto` = 자동추출; `''`/`'/'`=루트, `/wlkies` 등으로 명시 오버라이드 가능)로 조정한다. 루트(base `/`) 빌드도 동일 코드로 하위호환된다.
  - **`GET /dev` = 내장 데모 UI 고정 경로**: `GET /`는 dist 유무에 따라 배포 UI와 내장 UI 중 **하나만** 내주므로, dist를 넣는 순간 내장 UI에 접근할 수 없어진다. `/dev`는 `--frontend-dir` 유무와 무관하게 **항상 내장 UI**를 서빙해 두 UI가 같은 서버(포트 8900)에서 경로로만 갈리도록 한다. 프론트 이슈 분리(백엔드 계약이 맞는지 내장 UI로 교차 확인)용이며, SPA fallback은 base(`/wlkies`) 하위에만 걸려 있어 이 경로를 가로채지 않는다.
- **백엔드 URL 구성(권장 패턴)**: 프론트는 백엔드 주소를 **same-origin 자동 유도(`window.location` 기반)를 기본값**으로 두고, **개발용 env 변수(예 `VITE_WLK_URL`)로만 오버라이드**한다. → 배포(방법 A = same-origin)에선 설정 없이 동작하고, 개발 중엔 env로 개발 서버 IP를 지정한다.
  - 빌드 **base path**는 `/`(루트)든 `/wlkies` 같은 하위 경로든 무방하다 — 백엔드가 `index.html`에서 base를 자동 추출(`--frontend-base auto`)해 그 하위로 자산·SPA를 서빙하고 `GET /`는 base로 리다이렉트하므로 자산 절대경로 URL이 맞춰진다. react-router 등 클라이언트 라우팅을 쓰면 백엔드 SPA fallback이 필요하다(백엔드에 반영).

### 1.2 배포 UI 현재 표시 범위 (백엔드 계약과 별개)

> 백엔드는 아래 값을 **모두 계속 제공**한다. 이 표는 **배포 UI가 실제로 무엇을 표시하는지**이며, 백엔드 계약(스키마)은 바뀌지 않는다.

| 항목                                  | 현재 상태                 | 비고                                                      |
| ------------------------------------- | ------------------------- | --------------------------------------------------------- |
| 번역 `lines[].translation`            | **표시함**                | 서버 `--llm-translation` **기본 ON**(2026-07-16~)               |
| 화자분할 `speaker`                    | **수신만, UI 표시 안 함** | 서버 diar ON(값은 옴). 화자 배지·색은 배포 UI에 넣지 않기로 결정됨(§2.6) |
| 전사 저장 `POST /api/save-transcript` | **UI에서 제거됨**(2026-07-22) | API 계약은 유지, 배포 UI가 호출하지 않음. §3.2는 참고용   |
| `finalize_trigger`                    | **UI에 배지로 표시**(기본 ON) | 확정 줄마다 색상 pill(침묵/종결/언어전환/화자전환). 설정 드로어 "확정 원인 표시"로 끌 수 있고, 별도로 `data-trigger` DOM 속성이 경로 C 계측에 쓰인다(§2.7) |

---

## 2. WebSocket API — `/asr`

실시간 전사의 유일한 채널. **연결 = 녹음 시작**, **빈 프레임 전송 = 녹음 종료**.

### 2.1 연결

```
ws://<host>:<port>/asr[?language=<code>][&mode=delta|full]
```

**쿼리 파라미터**(선택)

| 파라미터   | 타입   | 기본               | 설명                                                            |
| ---------- | ------ | ------------------ | --------------------------------------------------------------- |
| `language` | string | 서버 `--lan`(기본 `auto`) | 세션 소스 언어 지정. 허용값 `{auto, ko, en}`. 생략 시 서버 전역 `--lan` 따름(세션 오버라이드 없음) |
| `mode`     | string | 서버 `--ws-protocol`(기본 `full`) | 출력 프로토콜(§2.4.2). `full`=매 메시지 전체 스냅샷(**기본**, 구 동작), `delta`=snapshot 1회+이후 diff(**opt-in**). `diff`는 `delta`의 하위호환 별칭. 허용값 외는 경고 로그 후 서버 기본값 폴백 |

> **`mode=delta` opt-in**: 기본값이 `full`이므로 **델타 미대응 클라이언트는 코드를 고치지 않아도 기존 그대로
> 동작한다**. 델타 재구성(§2.4.2)을 구현한 클라이언트가 `?mode=delta`로 명시적으로 전환한다 — 세션이 길어져도
> 페이로드·재렌더 비용이 늘지 않는다. 모든 클라이언트가 델타를 지원하게 되면 서버 기본값을
> `--ws-protocol delta`로 올릴 수 있다. 실제 적용된 프로토콜은 `config` 메시지의 `protocol` 필드로 통지된다(§2.4.1).

> **⚠️ 실효 시점(2026-07-17~): 이제 기본 백엔드(SimulStreaming)에서 실제로 동작한다.** 과거엔 이 파라미터가
> 문서에만 명세돼 있었을 뿐, 세션 언어 주입이 `transcribe()`만 가로채는 프록시로 구현돼 있었는데 기본 백엔드는
> `infer()`를 호출하므로 **조용히 무시**됐다(무효였음). 현재는 `SimulStreamingOnlineProcessor`가 세션 언어로
> 디코더 설정(`AlignAttConfig`)의 얕은 사본을 만들어 세션 단위로 실효화한다.

**허용값·검증·의미**

| 값               | 세션 동작                                                                                                  |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| (생략)           | 서버 전역 `--lan`을 그대로 따름 — **세션 오버라이드 없음**                                                  |
| `?language=auto` | **세션을 강제 auto**(코드스위칭 재감지 로직 전부 활성) — 서버가 `--lan ko`로 떠 있어도 그 세션만 auto      |
| `?language=ko`   | 세션 소스 언어를 한국어로 **고정**                                                                          |
| `?language=en`   | 세션 소스 언어를 영어로 **고정**                                                                            |
| 그 외 값         | **경고 로그 후 무시** → 서버 전역 `--lan`으로 폴백(허용 집합 = `{auto, ko, en}`)                            |

- **언어 고정(`ko`/`en`)의 효과**: 한↔영 코드스위칭 전용 로직(매청크/주기/짧은침묵/화자전환 eager/스크립트-앵커
  언어 재감지, `language_switch` 문장경계 트리거, ForeignLang/ScriptMismatch 언어상태 리셋, 긴침묵 언어리셋)이
  세션 단위로 비활성화된다. 드롭·경계 재디코딩 등 언어 무관 로직은 그대로 유지된다.
- **실제 적용 언어 확인**: 연결 직후 `config` 메시지의 `language` 필드가 그 세션에 실제 적용된 언어를 알려준다(§2.4.1).
- **개념 구분**: 이 세션 파라미터는 "그 세션의 오디오 입력이 어떤 언어인가"(소스 언어 모드)이며, 서버가 항상
  한국어/영어 두 언어로만 출력하도록 제한하는 출력 언어 제약(일본어·중국어 환각 차단)과는 별개다.

> 이 `language`를 제외하면, 클라이언트가 서버 동작(화자분할 on/off, 오디오 입력 형식 등)을 쿼리로 바꿀 수는 없다.
> 그런 설정은 서버 CLI 플래그로만 결정되며, 관련 값은 연결 직후 `config` 메시지로 통지된다(§2.4.1).

### 2.2 라이프사이클

```
Client                                   Server
  │───── WebSocket 연결 ─────────────────▶│   (연결 = 녹음 시작)
  │◀──── {"type":"config", ...} ──────────│   1회, 오디오 송신 방식 통지
  │                                        │
  │───── 오디오 바이너리 프레임 ─────────▶│   (config 수신 후 시작, 반복)
  │◀──── {"type":"snapshot", ...} ────────│   1회, 전체 상태(델타 모드)
  │◀──── {"type":"diff", ...} ────────────│   (~50ms, 직전과 다를 때만, 반복)
  │           …                           │
  │───── ArrayBuffer(0) (빈 프레임) ──────▶│   (녹음 종료 신호)
  │◀──── 잔여 diff ───────────────────────│   (flush 결과)
  │◀──── {"type":"ready_to_stop"} ────────│   (처리 완료)
  │───── close() ────────────────────────▶│
```

**규칙**

- 클라이언트는 **`config` 수신 후에** 오디오 송신을 시작한다(송신 형식이 config로 정해짐).
- 종료는 빈 프레임 `ArrayBuffer(0)` 1회 → 서버가 잔여 오디오 flush → `ready_to_stop` → 클라이언트 `close()`.
- **종료 처리 중(빈 프레임 전송 ~ `ready_to_stop` 수신) 새 세션을 열지 않는다** — flush 구간에 새 연결 시 상태 충돌.
- **자동 재연결 없음**: 서버는 재연결/세션 복구를 하지 않는다. 비정상 `onclose`/`onerror` 시 재연결·상태 복구는 클라이언트 책임.
- **일시중지(pause) 없음**: 종료는 되돌릴 수 없다. "재시작"은 `close()` 후 새 연결(= 서버 세션 초기화).

### 2.3 Client → Server 메시지 (바이너리)

전부 **바이너리 프레임**(텍스트 프레임 없음). 배포 기본값에서는 항상 WebM 경로 하나만 쓴다.

| 상황          | 프레임 내용                                                                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 오디오(WebM)  | `MediaRecorder(stream,{mimeType:"audio/webm"})`의 Blob 청크. **`recorder.start(100)`** 처럼 timeslice(ms) 필수 지정(100ms 권장). 서버가 FFmpeg로 디코딩 |
| **종료 신호** | 빈 프레임 `new ArrayBuffer(0)`                                                                                                                          |

> `recorder.start()`를 **인자 없이** 호출하면 `stop()` 전까지 청크가 방출되지 않아 실시간 전사가 되지 않는다.

### 2.4 Server → Client 메시지 (JSON 텍스트)

수신 JSON은 **`type` 필드**로 종류를 구분한다.

- `type: "config" | "ready_to_stop"` → **제어 메시지**(§2.4.1)
- `type: "snapshot" | "diff"` → **상태 메시지(델타 모드 = `?mode=delta` opt-in)**(§2.4.2)
- `type` 없음 → **상태 스냅샷(full 모드 = 기본)**(§2.4.2)

#### 2.4.1 제어 메시지

| `type`          | 시점           | 페이로드                                                  | 의미                                                                            |
| --------------- | -------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `config`        | 연결 직후 1회  | `{"type":"config","useAudioWorklet":false,"protocol":"full","mode":"full","language":"auto"}` | 오디오 송신 형식 + **적용 프로토콜** + **세션 적용 언어** 통지. `useAudioWorklet`은 배포 기본값에선 고정(구현 불필요) |
| `ready_to_stop` | 종료 처리 완료 | `{"type":"ready_to_stop"}`                                | 최종 렌더 후 `close()` 하라는 신호                                              |

> **`config.protocol`(신설)**: 그 세션에 실제 적용된 출력 프로토콜(`"delta"`|`"full"`). `mode`는 같은 값을 싣는 구
> 클라이언트 호환 별칭이다(과거 `mode`는 항상 `"full"`이었다). 클라이언트는 `protocol ?? mode ?? "full"`로 읽는다.
>
> **`config.language`(2026-07-17 신설, 하위호환·필드 추가만)**: 그 세션에 실제 적용된 소스 언어. `?language=`로
> 세션 언어를 지정했으면 그 값(`auto`/`ko`/`en`), 지정하지 않았으면 서버 전역 `config.lan`(기본 `auto`)이 담긴다.
> 클라이언트는 이 값으로 세션 언어가 의도대로 걸렸는지 확인할 수 있다(필드가 없는 구버전 서버 대비 방어적으로 읽을 것).

#### 2.4.2 상태 메시지 — full(기본) / 델타(opt-in)

매 처리 사이클(~50ms) 중 **직전 상태와 내용이 다를 때만** 전송된다. `lines[]`는 **세션 전체 확정 히스토리를
무제한 유지**한다(§6 리텐션) — 다만 **그 전체를 매번 보내지는 않는다.**

##### 델타 프로토콜 (opt-in, `?mode=delta`)

> **왜 있나**: full 모드는 매 메시지가 전체 상태 스냅샷이라, 세션이 길어질수록 WebSocket 페이로드와 전체 재렌더
> 비용이 누적 줄 수에 비례해 커진다(실측: 109초 시점 이미 메시지당 ~5.5KB, 총 전송량 4.7배). 델타는 매 메시지
> 1~2줄만 실어 이 증가를 없앤다.
> **델타를 쓰려면 클라이언트가 상태를 누적해야 한다.** 미구현 클라이언트는 아무것도 하지 않으면 된다 —
> 서버 기본값이 `full`이라 기존 동작이 유지된다(§2.1).

- 첫 메시지 `{"type":"snapshot","seq":1, ...아래 전체 필드...}` — 전체 상태.
- 이후 `{"type":"diff","seq":N,"n_lines":M,"status":…,"buffer_*":…,"remaining_time_*":…,`
  `(선택)"lines_pruned":K,(선택)"new_lines":[Segment,…],(선택)"error":…}`

| 필드           | 타입      | 항상 존재 | 의미                                                                 |
| -------------- | --------- | :-------: | -------------------------------------------------------------------- |
| `seq`          | number    |     O     | 1부터 증가하는 메시지 순번(연결 단위). 누락 감지용 참고값            |
| `n_lines`      | number    |  O(diff)  | 이 메시지 적용 **후** 클라이언트가 가져야 할 총 줄 수 — 검증 기준     |
| `lines_pruned` | number    |     ✕     | 앞에서 잘려나간 줄 수. 있으면 **먼저** 앞에서 그만큼 제거            |
| `new_lines`    | Segment[] |     ✕     | **공통 prefix 이후의 꼬리 전체**(append 대상 아님 — 아래 ⚠️)          |

**⚠️ `new_lines`는 append가 아니라 꼬리 교체다.** 백엔드는 최근 줄을 **소급 수정**한다(경계 재조정·침묵 게이트
재개방, 대략 8초 이내 — §2.4.4의 ①②가 바로 이 현상이다). 그러면 이미 보낸 줄이 갱신된 내용으로 `new_lines`에 다시
실린다. append 하면 같은 줄의 옛 판과 새 판이 함께 쌓여 **중복 표시**된다.

```js
// 재구성 알고리즘 (참조 구현: whisperlivekit/web/live_transcription.js `reconstructLines`)
function applyMessage(lines, msg) {
  if (msg.type === "snapshot") return msg.lines.slice();            // 전체 교체
  if (msg.lines_pruned) lines.splice(0, msg.lines_pruned);          // ① 앞부분 prune
  const newLines = msg.new_lines || [];
  const common = msg.n_lines - newLines.length;                     // ② 공통 prefix 길이
  lines = lines.slice(0, common).concat(newLines);                  // ③ 꼬리 교체(append 아님)
  if (lines.length !== msg.n_lines) reconnect();                    // ⑤ 검증 실패 → 재동기
  return lines;
}
// ④ status·buffer_transcription·buffer_diarization·buffer_translation·
//    remaining_time_transcription·remaining_time_diarization·error 는 매 메시지 값으로 그대로 교체.
```

- **렌더도 증분으로**: `common` 이전 줄은 DOM/컴포넌트를 건드리지 않고 꼬리만 교체한다. React라면 `key={line.id}`
  로 리스트를 렌더하면 앞부분이 자동으로 재사용된다(내장 UI는 `reconcileTranscriptDom`이 같은 일을 한다).
- **재동기 수단은 재연결뿐**이다(새 연결 = 새 `snapshot`). 서버는 재전송 요청을 받지 않는다.
- 줄 dedup·key는 여전히 **`id` 단독**(§2.4.4). 복합키 금지.

##### full 모드 (기본)

`type` 필드 **없음**. 매 메시지가 아래 전체 상태를 담으며, `lines[]`는 세션 전체 히스토리를 그대로 재전송한다 —
클라이언트는 받은 `lines[]`를 전체 교체 렌더만 해도 히스토리가 유지된다(별도 누적 불필요). 페이로드·재렌더 비용이
세션 길이에 비례해 커지므로, 장시간 세션을 다루는 클라이언트는 `?mode=delta`로 전환하는 것이 좋다.

##### 전체 상태 페이로드 (델타의 `snapshot`, full의 매 메시지)

```jsonc
{
  "status": "active_transcription",
  "lines": [
    /* Segment 객체 배열, §2.4.3 */
  ],
  "buffer_transcription": "진행 중 미확정 전사 텍스트",
  "buffer_diarization": "",
  "buffer_translation": "",
  "remaining_time_transcription": 1.2,
  "remaining_time_diarization": 0.0,
  "error": "...",
}
```

| 필드                           | 타입       |    항상 존재    | 의미                                                                              |
| ------------------------------ | ---------- | :-------------: | --------------------------------------------------------------------------------- |
| `status`                       | string     |        O        | 세션 상태(§2.5)                                                                   |
| `lines`                        | Segment[]  | O(빈 배열 가능) | 확정·진행 중 세그먼트 목록(§2.4.3)                                                |
| `buffer_transcription`         | string     |        O        | 아직 확정 안 된 진행 중 전사(디코딩 꼬리). 맨 아래 줄 꼬리에 이어붙여 표시        |
| `buffer_diarization`           | string     |        O        | 화자배정 지연으로 `lines[]`에 아직 없는 최근 발화(diar 모드). 표시에서 빼지 말 것 |
| `buffer_translation`           | string     |        O        | 진행 중(미확정) 번역. 번역 활성 시 `lines[]`의 마지막 `finalized:false` 세그먼트를 번역해 채움(§4) |
| `remaining_time_transcription` | number(초) |        O        | 전사 처리 지연(랙). 표시용 참고값                                                 |
| `remaining_time_diarization`   | number(초) |        O        | 화자분할 처리 지연. diar off면 `0`                                                |
| `error`                        | string     |        ✕        | `status=="error"`일 때만 존재. 오류 메시지(FFmpeg 등)                             |

> **항목 식별 key는 `id`(안정 세그먼트 식별자)를 쓸 것 — §2.4.4.** `start`/`end`는 1초 해상도 벽시계
> 문자열이라 같은 초에 여러 세그먼트가 시작될 수 있어 식별 key로 부적합하다(과거 이 문서가 권장하던
> `start|end|speaker` 복합키는 growing-prefix 중복 버그의 원인이라 폐기 — §2.4.4).

#### 2.4.3 `lines[]` — Segment 객체

| 필드                | 타입           | 항상 존재 | 값/예시                    | 의미                                                     |
| ------------------- | -------------- | :-------: | -------------------------- | -------------------------------------------------------- |
| `speaker`           | int            |     O     | `1`,`2`,… / `-2`           | 화자 번호(§2.6). diar off면 항상 `1`, `-2`=침묵          |
| `text`              | string \| null |     O     | `"안녕하세요"`             | 전사 텍스트. 침묵 세그먼트면 `null`/`""`                 |
| `id`                | number         |     O     | `12.34`                    | **안정 세그먼트 식별자**(세션상대 시작초). 라인 dedup·React key는 **반드시 이 값**을 쓸 것(§2.4.4). `end`가 자라거나 재개방돼도 불변 |
| `start`             | string         |     O     | `"13:15:30"`               | 발화 시각(PC 벽시계, `HH:MM:SS`, 24h, 센티초 없음). **표시 전용 — 식별 key로 쓰지 말 것**(§2.4.4) |
| `end`               | string         |     O     | `"13:15:32"`               | 발화 종료 시각(동일 형식)                                |
| `finalized`         | bool           |     O     | `true`/`false`             | 문장 확정 여부. diar on/off 무관하게 갱신                |
| `completed`         | bool           |     O     | `finalized`와 동일         | 호환 별칭                                                |
| `finalize_trigger`  | string \| null |     O     | §2.7                       | 확정·분리 원인. `null`=미확정                            |
| `translation`       | string         |     ✕     | `"Hello"`                  | 인라인 번역(§4). 번역 활성 + `finalized=true` 세그먼트만 |
| `detected_language` | string         |     ✕     | `"ko"`,`"en"`              | 감지 언어 코드(감지됐을 때만)                            |
| `lang`              | string         |     ✕     | `detected_language`와 동일 | 호환 별칭                                                |

Segment 예시:

```json
{
  "speaker": 2,
  "text": "회의를 시작하겠습니다",
  "id": 12.34,
  "start": "13:15:30",
  "end": "13:15:32",
  "finalized": true,
  "completed": true,
  "finalize_trigger": "punctuation",
  "translation": "Let's begin the meeting",
  "detected_language": "ko",
  "lang": "ko"
}
```

> `text`가 없고 `speaker != -2`인 세그먼트는 응답에서 아예 빠진다(침묵 세그먼트만 `text` 없이 방출).

#### 2.4.4 라인 dedup·렌더 규칙 (⚠️ 미준수 시 중복 표시 버그)

백엔드는 **문장 확정 판정을 뒤에 오는 발화 맥락에 따라 사후에 조정**한다(문법-조건부 문장 확정). 그래서 같은
세그먼트가 스냅샷마다 다음처럼 변할 수 있다:

1. **`end`가 자란다** — 같은 문장이 더 길어진 채 다시 온다(같은 `id`, 커진 `end`·`text`).
2. **확정 세그먼트가 다시 진행중으로 재개방된다** — `finalized`가 `true`→`false`로 돌아오고 같은 `id`로 계속 자란다
   (예: 스퓨리어스 온점으로 조기 확정 → 온점 철회 후 문장 계속).

**델타 프로토콜(`?mode=delta`)에서 이 재조정은 `new_lines` 꼬리 재전송으로 나타난다.** §2.4.2의 꼬리 교체를 그대로
수행하면 위 ①②가 자동으로 맞춰진다 — 재조정된 줄이 **같은 `id`로 갱신 내용을 실어 다시 오기 때문**이다.
full 모드(기본)에서는 매 스냅샷 `lines[]`를 통째로 다시 그리면 동일한 결과가 된다.

**별도 누적 Map을 둔다면 — 반드시 `id`로:** React key나 컴포넌트 상태 유지, 또는 세션 초기의 빈
`no_audio_detected` 상태 대비로 라인을 Map에 누적한다면, **키는 `id` 단독**을 쓴다.
- ❌ `start|end|speaker` 복합키 금지 — `end`가 자랄 때마다 새 항목으로 쌓여 같은 문장의 절단판이 누적된다(**growing-prefix 중복**).
- ❌ `start` 단독도 부적합 — 1초 해상도라 같은 초에 시작한 다른 세그먼트(특히 다화자)가 충돌한다.
- ✅ `id`로 upsert(같은 `id`면 덮어쓰기) + **진행중 줄 우선**(같은 `id`의 이전 확정판보다 `finalized:false` 줄을 우선 렌더 →
  재개방 시 stale 확정판 가림). `no_audio_detected`(빈 `lines[]`)에서 누적을 비우지 말 것(§2.5).

**`buffer_transcription` 표시:** 마지막 **진행중(`finalized:false`) 줄** 꼬리에만 이어붙인다. **확정된 줄에는 붙이지 말 것** —
확정 줄에 붙이면 진행중 텍스트가 확정 블록과 중복돼 보인다.

**`lines[]`가 비고 `buffer_*`만 있을 때(세션 초기):** 확정 줄이 아직 하나도 없는데 `buffer_transcription`/`buffer_diarization`만
채워진 스냅샷에서는, 버퍼를 독립된 진행중 줄로 보이게 하기 위해 **임시 줄(예 `{speaker:1, text:""}`)을 하나 만들어 그 꼬리에
버퍼를 붙인다**. 이 케이스를 처리하지 않으면 첫 발화가 확정되기 전까지 화면이 빈 채로 남는다. 참조 = `live_transcription.js:475-477`.

**⚠️ 세션 종료 시 `buffer_*` 정착(fold-in) — 누락 시 마지막 발화 증발:** `ready_to_stop` 수신 후의 **마지막 렌더**에서는
남은 `buffer_diarization`·`buffer_transcription`(및 `buffer_translation`)을 **연한 진행중 span으로 남기지 말고 마지막 줄 본문에
일반 텍스트로 접합**한다(각 조각을 `trim`하고, 앞줄 본문과 버퍼가 모두 비어있지 않을 때만 단일 공백으로 join). 이 처리를 빼면
**종료 순간 마지막 미확정 발화가 화면에서 그대로 사라진다** — 버퍼는 별도 줄이 아니라 확정 줄에 못 실린 진행중 꼬리이기 때문.
참조 = `live_transcription.js:521-537`·`:539-547`(`isFinalizing` 분기).

> 참조 구현 = 내장 테스트 UI `whisperlivekit/web/live_transcription.js`(누적 Map을 `id`로 키잉 + 진행중 줄과 같은 `id`
> 확정판 억제). 배경: 이 규칙 미준수(`start|end|speaker` 누적)가 실측에서 kor 낭독체 WER을 3배 이상 부풀린 사례가 있었다
> (성능 측정이 UI DOM을 스크래핑하므로 렌더 중복이 지표까지 오염 — 프론트 버그가 백엔드 지표로 오인됨).
> **누적의 최소 단위는 델타 재구성이다**(§2.4.2): 서버는 `lines[]`를 세션 전체 **무제한 유지**하지만 매번
> 전량 전송하지는 않으므로, 클라이언트는 `snapshot`+`diff`로 서버-권위 `lines[]` 미러를 반드시 들고 있어야 한다.
> 그 미러 위에서 `id`를 key로 리스트를 렌더하면 위 ①②(`end` 성장·재개방)가 자동 해소된다.
> 내장 UI의 `finalizedHistory` Map(확정 줄 별도 누적)은 과거 서버가 확정 줄을 5분 슬라이딩 윈도우로 잘라내던
> 시절의 레거시로, 지금은 중복 안전장치일 뿐이다 — React가 그대로 옮길 필요는 없다.

### 2.5 `status` 값

| 값                     | 의미                                  | 클라이언트 렌더 권장                                                                                             |
| ---------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `active_transcription` | 정상 처리 중                          | 재구성된 상태대로 렌더                                                                                           |
| `no_audio_detected`    | `lines`·버퍼 모두 비어 "그릴 게 없음" | 화면 자막만 가리되 **누적 state는 유지**(다음 active에서 복원). 이 status에서 클라이언트 히스토리를 비우지 말 것 |
| `error`                | 처리 오류                             | `error` 필드 표시. 내장 UI엔 배너 없음 → 필요 시 클라이언트가 직접 구현                                          |

### 2.6 `speaker` 값

| 값        | 의미                                                        |
| --------- | ----------------------------------------------------------- |
| `1,2,3,…` | 화자 번호(diar on: 1-base)                                  |
| `1`       | diar off일 때 **모든** 세그먼트                             |
| `-2`      | 침묵 세그먼트(침묵 아이콘 렌더 권장)                        |
| `0`       | (표시 전용) "화자분할 진행 중" 로딩 표식 — 스피너 렌더 권장 |

> `--diarization` 기본값 = **ON**. config에 화자분할 여부 플래그가 따로 없으므로 클라이언트는
> `speaker` 값으로 다화자 여부를 추론한다. 화자별 구분색 매핑은 클라이언트가 직접 구현.
>
> **이번 연동 범위**: `speaker`는 **수신만 하고 화면에는 표시하지 않는다**(배지·색 미구현, §1.2).
> 위 표시 권장은 추후 화자분할을 UI에 넣을 때 참고용.

### 2.7 `finalize_trigger` 값

문장이 어떤 로직으로 확정·분리됐는지. 배지 표시 등에 활용 가능(선택).

| 값                | 의미                        |
| ----------------- | --------------------------- |
| `silence`         | 침묵 경계로 확정            |
| `punctuation`     | 문장부호(온점 등)로 확정    |
| `language_switch` | 한↔영 언어 전환 경계로 확정 |
| `speaker_change`  | 화자 전환 경계로 확정       |
| `null`            | 미확정(`finalized=false`)   |

### 2.8 오류 처리

- 처리 오류는 스냅샷 `status:"error"` + `error` 필드로 전달(예: FFmpeg 디코딩 실패).
- 연결 수준 오류(서버 다운·네트워크 끊김)는 WebSocket `onclose`/`onerror`로만 나타난다 —
  서버는 close code/reason에 별도 의미를 싣지 않으며 자동 재연결도 하지 않는다(§2.2).

---

## 3. REST API

### 3.1 `GET /health`

서버 기동·준비 상태 확인. WS 연결 전 폴링에 사용 가능(선택).

**응답 200**

```json
{ "status": "ok", "backend": "whisper", "ready": true }
```

| 필드      | 타입   | 의미                                             |
| --------- | ------ | ------------------------------------------------ |
| `status`  | string | `"ok"`                                           |
| `backend` | string | 서버 `--backend`에 따른 동적값(기본 `"whisper"`) |
| `ready`   | bool   | 모델 로딩 완료 여부                              |

### 3.2 `POST /api/save-transcript`

> ⚠️ **이번 연동 범위 제외**(§1.2) — 저장 버튼 미구현. 아래는 참고/추후용.

누적 전사를 **서버 로컬 디스크**에 저장(브라우저 다운로드 아님). **사용자가 저장 버튼을 눌렀을 때만**
호출한다 — 녹음 종료(`ready_to_stop`) 시 자동 저장되지 않는다.

**요청 본문**

```json
{
  "lines": [
    { "speaker": 1, "text": "안녕하세요", "translation": "Hello" },
    { "speaker": 2, "text": "회의를 시작합니다" }
  ]
}
```

| 필드                  | 타입   | 필수 | 의미             |
| --------------------- | ------ | :--: | ---------------- |
| `lines`               | array  |  O   | 저장할 라인 배열 |
| `lines[].speaker`     | int    |  O   | 화자 번호        |
| `lines[].text`        | string |  O   | 전사 텍스트      |
| `lines[].translation` | string |  ✕   | 번역(있을 때만)  |

**응답 200**

```json
{
  "status": "success",
  "path": "transcripts/transcript_20260714_131530.txt",
  "line_count": 2
}
```

| 필드         | 타입   | 의미                                                                                                    |
| ------------ | ------ | ------------------------------------------------------------------------------------------------------- |
| `status`     | string | `"success"`                                                                                             |
| `path`       | string | 저장된 파일 경로(서버 `--transcript-save-dir`, 기본 `./transcripts`)                                    |
| `line_count` | int    | 요청 `lines` 개수. **빈 텍스트 줄 포함**이라 실제 파일 기록 줄 수와 다를 수 있음(빈 줄은 파일에서 스킵) |

- 저장 파일명: `transcript_YYYYMMDD_HHMMSS.txt`.
- 파일 형식: `[화자 N] 텍스트`, 번역이 있으면 다음 줄에 `    ↳ 번역`(타임스탬프 없음).
- 저장 버튼은 녹음 중에도 클릭 가능하며, 매 클릭마다 클릭 시점까지의 **전체 누적**을 새 타임스탬프 파일로 저장(증분 아님).
- 권장 흐름: `finalized` 줄 전체 + 마지막 미확정 줄을 합쳐 `lines`로 구성해 호출.
- **payload 구성 시 클라이언트 전처리(권장)**: 화면 표시와 별개로, 저장 payload는 클라이언트가 다듬어 보내는 것이 좋다 —
  ① **침묵 세그먼트(`speaker === -2`)와 `text`·`translation`이 모두 빈 줄은 제외**, ② `text`/`translation`은 `trim`,
  ③ 값 없는 `translation`은 필드 자체를 생략. 이 전처리를 하지 않아도 서버가 빈 줄은 파일에서 스킵하지만, `line_count`
  왜곡과 침묵 줄 저장을 피하려면 클라이언트에서 걸러 보낸다. 참조 = 내장 UI `buildTranscriptPayload()` `live_transcription.js:247-251`.

### 3.3 단어교정 사전 — `/api/corrections`

전사 직후 적용되는 단어 교정 사전을 운용 중 동적으로 조회·추가·삭제. 변경은 **즉시 반영**되며,
**진행 중인 세션의 이미 확정된 문장에도 소급 적용**된다(§3.5).

#### `GET /api/corrections`

**응답 200**

```json
{ "6군": "육군", "공군참모총장": "공참총장" }
```

> **사용자가 추가한 항목(SQLite)만** 반환한다(`word_manager.user_replacements`). 서버 내장
> 기본 사전(base JSON = `admin_replacement.json`)은 **응답에서 제외**한다 — base는 배포 전
> 관리자가 미리 채워 넣는 값이고, 관리 UI는 배포 후 현장 사용자가 직접 넣는 항목을 위한
> 화면이기 때문이다(§3.4 `glossary_block`과 동일한 정책).
>
> **숨긴다는 건 표시만이다** — base 항목은 실제 전사 후처리 치환에 그대로 적용된다. 치환 경로는
> 여전히 base+사용자 병합본(`word_manager.combined_replacements`)을 쓰며, 동일 `wrong_word`가
> 양쪽에 있으면 사용자 DB 값이 우선한다.

#### `POST /api/corrections`

**요청**

```json
{ "wrong_word": "6군", "correct_word": "육군" }
```

**응답 200**

```json
{ "status": "success" }
```

#### `DELETE /api/corrections/{wrong_word}`

경로 파라미터 `wrong_word`로 항목 삭제. **base JSON 전용 항목**(사용자 DB엔 없고 base JSON에만 있는 단어)은
삭제할 수 없다 — 삭제 대신 경고를 반환한다(`/api/prompts/delete-item`의 기본 glossary 항목 보호와 동일 패턴).
base 항목은 위 GET에 애초에 안 잡히므로 **관리 UI에서는 이 경로에 도달할 수 없다** — API를 직접 호출하는
경우를 막는 방어 로직이다. 사용자가 base와 같은 `wrong_word`를 POST로 추가(override)한 뒤 삭제하면
DB 행만 지워져 `success`가 되고, 그 항목은 GET 결과에서 사라지되 치환은 base 값으로 되돌아간다.

**응답 200 (일반 삭제 성공 · 존재하지 않는 단어 삭제 포함)**

```json
{ "status": "success" }
```

**응답 200 (base 전용 항목 삭제 시도 — 삭제되지 않음)**

```json
{ "status": "warning", "message": "기본 사전 항목은 삭제할 수 없습니다." }
```

### 3.4 번역 glossary — `/api/prompts`

번역 프롬프트에 주입되는 용어집(`glossary_block`)·예시 문장(`sentence_block`)을 운용 중 동적으로
조회·추가·삭제. 변경은 **즉시 반영**되며(다음 번역 요청부터), 진행 중인 세션의 **최근 확정 문장은
소급 재번역**된다(§3.5) — 입력 문장에 실제 등장하는 용어만 번역 프롬프트에 골라 주입되는 방식이라
§3.3 단어교정 사전과 별개로 동작한다.

> **정본 경로 = `/api/prompts*`.** 배포 React admin은 이 세 엔드포인트를 `CORRECTIONS_URL` 기반으로
> `/api/corrections/` 접두를 붙여 호출하므로(`GET /api/corrections/prompts`,
> `POST /api/corrections/prompts/add-item`, `POST /api/corrections/prompts/delete-item`), 백엔드가
> 이를 정본 경로의 **alias**로 함께 수용한다(basic_server의 FastAPI stacked decorator). alias는 배포
> 프론트 호환용이며 기능·페이로드·응답은 정본과 동일하다. 신규 클라이언트는 정본 `/api/prompts*`를 쓴다.

#### `GET /api/prompts`

**응답 200**

```json
{
  "glossary_block": { "해군": "ROKN" },
  "sentence_block": { "보고를 드리기 전 안내 말씀드리겠습니다.": "Before we begin, a brief notice." }
}
```

| 필드 | 타입 | 의미 |
|---|---|---|
| `glossary_block` | object | **사용자가 추가한 항목만** 반환(서버 내장 기본 용어집은 숨김 — §3.3 corrections와 동일한 정책) |
| `sentence_block` | object | 개발자 기본값 + 사용자 추가분을 **합쳐서** 반환 |

#### `POST /api/prompts/add-item`

**요청**

```json
{ "block_key": "glossary_block", "origin": "해군", "translation": "ROKN" }
```

| 필드 | 타입 | 필수 | 의미 |
|---|---|:--:|---|
| `block_key` | string | O | `"glossary_block"` 또는 `"sentence_block"`. 그 외 값은 400 |
| `origin` | string | O | 원어 용어(glossary) 또는 원문(sentence) |
| `translation` | string | O | 대역어(glossary) 또는 번역문(sentence). 누락 시 400 |

**응답 200**
```json
{ "status": "success" }
```

#### `POST /api/prompts/delete-item`

**요청**
```json
{ "block_key": "glossary_block", "origin": "해군" }
```

**응답 200**
```json
{ "status": "success" }
```
또는(대상이 없거나 삭제 불가한 항목일 때 — **에러 아님, HTTP 200**)
```json
{ "status": "warning", "message": "Item not found or cannot delete default glossary item" }
```

> `glossary_block`은 사용자가 추가한 항목만 삭제 대상이다(서버 내장 기본 용어집은 애초에 GET에도
> 안 잡히므로 삭제 요청도 warning으로 끝난다). `sentence_block`은 기본 예시 문장도 삭제 가능(최초
> 수정 시 기본값을 사용자 버전으로 복제 후 편집).

### 3.5 녹음 중 사전 변경의 소급 적용 범위

관리자 페이지는 별도 탭에서 열리므로 **녹음(전사 세션)이 돌아가는 중에도** §3.3·§3.4를 호출할 수 있다.
이때 반영 범위는 다음과 같다. **신규 WebSocket 메시지 타입은 없다** — 소급 결과는 기존 `lines[]` 갱신
(delta 모드에서는 §2.4.4의 꼬리 교체)으로만 전달되므로 클라이언트는 무수정으로 동작한다.

| 대상 | 앞으로의 전사/번역 | 진행 중 세션의 과거 문장 |
|---|---|---|
| **전사 텍스트 대치**(§3.3) | 즉시 | **세션 전 구간 소급** — 서버가 매 tick(~50ms) 세션 전체 `lines[]`에 사전을 다시 적용한다. 항목을 **삭제하면 원문으로 원복**된다 |
| 미확정 버퍼(`buffer_transcription`·`buffer_diarization`) | 즉시 | 해당 없음(매 tick 새로 계산) |
| **번역**(§3.4, 그리고 §3.3으로 텍스트가 바뀐 문장) | 즉시 | **최근 N개 확정 문장만** 재번역(`--retro-retranslate-lines`, 기본 20; `0`이면 소급 재번역 비활성) |

- **재번역만 제한하는 이유**: 텍스트 대치는 이미 매 tick 전 구간에 도는 정규식이라 소급 비용이 사실상
  0이지만, 재번역은 LLM 호출이다. 흔한 단어를 등록하면 과거 수백 줄이 한꺼번에 재번역 대상이 되는데
  배포 LLM은 단일 서버라 전량을 던지면 진행 중인 실시간 번역이 밀린다. 동시 실행에도 상한이 걸린다.
- **최초 번역은 이 창과 무관하게 항상 수행**된다 — 창은 *재*번역만 제한한다.
- 새 번역이 도착하기 전까지 그 줄은 **직전 번역을 그대로 표시**한다(빈칸 깜빡임 방지).
- 창 밖의 오래된 문장은 "교정된 텍스트 + 이전 번역"으로 남는다 — 의도된 트레이드오프다.
- **한계**: 일시중단(⏸) 후 재개하면 WebSocket 세션이 새로 시작되고 이전 구간은 클라이언트에만 남으므로
  (내장/배포 UI 모두) 소급 대상이 아니다. 서버를 uvicorn 멀티워커로 띄우는 것도 지원하지 않는다 —
  사전이 프로세스 전역 싱글턴이라 다른 워커의 메모리에는 반영되지 않는다.

---

## 4. 번역(translation) 동작

- **활성화**: 서버 `--llm-translation` 플래그(**기본 ON**, 배포 PC llama.cpp `gpt-oss-20b` 대상 —
  2026-07-16~; 끄려면 `--no-llm-translation`). 꺼져 있으면 `lines[].translation`·`buffer_translation`
  모두 항상 비어 있다. (dev는 `--translation-serve ollama` 등으로 Ollama `qwen2.5:7b`를 가리키도록
  재정의 — 서버 플래그만 다르고 프론트 계약은 동일. 상세: [DEPLOYMENT_OFFLINE.md §5](DEPLOYMENT_OFFLINE.md))
- **확정 문장 번역** `lines[].translation`: 번역 활성 + 해당 세그먼트 `finalized=true`일 때 채워진다.
  캐시 미스면 비차단으로 요청 후 **다음 스냅샷부터** 채워진다(문장 통째로 등장, 토큰 스트리밍 아님).
  결과가 원문과 **같은 언어**(에코 — `detected_language` 캐리오버로 방향 반전)면 서버가 방향 강제
  지시문으로 1회 재시도하고, 재시도까지 실패하면 **빈 문자열 `""`로 정착**될 수 있다 — 확정 세그먼트의
  `translation: ""`는 "번역 실패로 정착" 상태일 수 있으니 프론트는 빈 값 표시 생략 규칙을 그대로 적용하면 된다.
- **진행 중 번역** `buffer_translation`: 번역 활성 시 `lines[]`의 마지막 `finalized:false` 세그먼트를
  같은 번역기로 번역해 채운다. 이전 요청이 끝나기 전엔 새 요청을 보내지 않는 단순 스로틀이라 값이
  다소 지연(stale)될 수 있고, 문장이 확정되는 순간 그 세그먼트가 사라지므로 함께 `""`로 리셋된다.
  확정 번역(`lines[].translation`)과는 독립된 캐시/상태를 쓴다.
- **번역 glossary**(§3.4): 입력 문장에 실제 등장하는 용어만 골라 매 번역 요청 프롬프트에 동적으로
  주입된다(`glossary_block`) — 예시 문장(`sentence_block`)도 함께 주입. `/api/prompts`로 추가한
  항목은 **다음 번역 요청부터 즉시 반영**되고, 진행 중인 세션의 **최근 확정 문장은 소급 재번역**된다(§3.5).
- **Qdrant RAG 유사 예시 (Stage 2) — 확정 문장에만 적용**: `whisperlivekit/llm_translation/` 아래
  `local_stt_shot/`와 `Embedding_model/` 디렉터리가 **둘 다 존재하면**(CLI 플래그 없음 — 경로는 코드 고정)
  번역 프롬프트에 기존 공식 번역 유사 예시 블록(`### SIMILAR EXAMPLES (RAG)`)이 추가로 주입된다.
  **주입 대상은 `lines[].translation`(확정 문장) 뿐이며 `buffer_translation`(진행 중 번역)은 받지
  않는다** — 버퍼는 발화 중 계속 갱신돼 매번 임베딩 인코딩 + 벡터 검색이 돌면 실시간성이 무너지기
  때문이다. 디렉터리가 없거나 `qdrant-client`/`sentence-transformers`가 설치돼 있지 않으면 조용히
  비활성화되고 기존 동작 그대로다(기동 실패하지 않음). **프론트 계약은 무변경** — 번역 품질만 달라진다.
  **개발 PC는 이 자산 디렉터리를 배치하지 않아 항상 OFF**(배포 PC 전용 기능) — 개발 PC 번역 테스트에서는
  Qdrant 없이 glossary(Stage 1)만 적용된다.

---

## 5. 데이터 타입 규약 요약

| 항목                      | 규약                                                                  |
| ------------------------- | --------------------------------------------------------------------- |
| 시간(`start`/`end`)       | 문자열 `"HH:MM:SS"`(PC 벽시계, 24시간제, 센티초 없음) — 경과시간 아님 |
| 확정 플래그               | `finalized`(bool), 별칭 `completed`                                   |
| 언어 코드                 | `detected_language`(예 `"ko"`,`"en"`), 별칭 `lang`                    |
| 미확정/버퍼 텍스트        | `buffer_*`(string), 항상 존재하되 내용이 없으면 `""`                  |
| 지연값                    | `remaining_time_*`(number, 초)                                        |
| 항목 식별 key(클라이언트) | **`id`(number, 안정 세그먼트 식별자) 단독** — `start`/`end` 복합키 금지(§2.4.4) |

---

## 6. 상수·기본값

| 항목                 | 값                          | 근거/비고                                                                     |
| -------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| 기본 WS/REST 포트    | `8900`                      | 서버 `--port`(개발 기본)                                                      |
| WS 경로              | `/asr`                      | —                                                                             |
| **WS 출력 프로토콜** | **`full`(기본)**            | 서버 `--ws-protocol {delta,full}`; 세션별 `?mode=delta\|full` 오버라이드(§2.1·§2.4.2). 기본 full = 매 메시지 전체 스냅샷(누적 불필요). `?mode=delta` opt-in 시 `snapshot` 1회+이후 `diff` — **클라이언트 누적 필수** |
| 오디오 입력          | WebM(MediaRecorder) 고정    | `useAudioWorklet=false`                                                       |
| WebM 청크 timeslice  | 100ms                       | `recorder.start(100)`                                                         |
| 화자분할             | 기본 ON                     | 서버 `--diarization`(기본 True)                                               |
| 번역                 | **기본 ON**(2026-07-16~) | 서버 `--llm-translation`(끄려면 `--no-llm-translation`)                       |
| **전사 라인 리텐션** | **무제한**                  | 서버가 `lines[]`를 세션 전체 유지(과거 5분 슬라이딩 → 무제한, master `606ecac`). 단 **전송은 델타** — 전량 재전송 아님 |
| 전사 저장 디렉터리   | `./transcripts`             | 서버 `--transcript-save-dir`                                                  |

---

## 7. 관련 문서

- 메시지 스키마 변경 이력: [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md)
- OpenAI/Deepgram 호환 계층: [0.Metafile/docs/API.md](../0.Metafile/docs/API.md)
  (⚠️ 이 upstream 문서는 diff 프로토콜을 "`?mode=diff` 옵트인"으로 기술한다 — 본 저장소도 **opt-in**이지만
  권장 파라미터는 `?mode=delta`이며 `diff`는 하위호환 별칭이다. 델타 계약의 정본은 위 §2.4.2다.)
- 서버측 델타 구현: `whisperlivekit/diff_protocol.py`(모듈 docstring에 재구성 알고리즘 명세)
