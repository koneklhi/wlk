# 프론트엔드 연동 요약 — React UI ↔ whisperlivekit 백엔드

> **대상 독자**: React UI를 백엔드에 연결할 프론트엔드 개발자.
> 이 문서 하나로 연동을 시작할 수 있도록 핵심만 정리한 **정본**이다(구 상세본 `FRONTEND_HANDOFF.md`는
> `docs/archive/`로 이동, 더 이상 갱신하지 않음 — 내용은 이 문서로 대체됨).
> **기존 whisperlive UI 코드를 개조**해 만든다면 스키마 상세(§3~)에 들어가기 전에 **§2를 먼저** 읽을 것.

---

## 1. 한눈에 보는 변경 (TL;DR)

| 축 | 기존 whisperlive | 신규 whisperlivekit |
|---|---|---|
| 전송 프로토콜 | SSE (`GET`, `text/event-stream`) + REST start/stop | **WebSocket** `ws://host:port/asr` |
| 전송 모델 | 이벤트 단위(세그먼트 1개 델타) | **기본 = full**(매 ~50ms `lines[]` 전량 스냅샷) — 누적 불필요, 무수정 동작. **`?mode=delta` opt-in** 시 `snapshot` 1회 + 이후 `diff`(바뀐 꼬리만)로 전환되며 **클라이언트 누적 필수**(§4.2) |
| 녹음 시작/종료 | `POST /api/recordings/start`·`/stop` | WS 연결=시작, **빈 프레임 `ArrayBuffer(0)`**=종료 |
| 번역 | 별도 `POST /api/translate` SSE | `lines[].translation` **인라인**(동작) + `buffer_translation`(진행중 번역, 동작·§7) |
| 화자분할 | 없음 | **신규** `lines[].speaker`(int) + `buffer_diarization` |
| 시간 필드 | `start`/`end` float(초) | `start`/`end` **문자열** `"HH:MM:SS"` — **PC 실제 벽시계 시각**(녹음 시작 0초 기준 경과시간 아님) |
| 확정 표시 | `status: "process"/"complete"` | `finalized: bool`(별칭 `completed`) |

React가 반드시 새로 구현할 것: ① WS 연결·종료 시퀀스 ② config 메시지 처리 후 오디오 송신
③ **델타 수신 누적 + `id` key 증분 렌더**(§4.2) ④ 화자(speaker) 배지/색 ⑤ 오디오 캡처(**기본 WebM MediaRecorder**,
또는 `--pcm-input` 시 PCM AudioWorklet).

---

## 2. 기존 whisperlive UI 코드 개조 가이드

이 프로젝트의 React UI는 기존 whisperlive(wl) UI 코드를 개조해 만든다. wl과 wlk는 전송 계층·렌더
모델·오디오 입력·확정표시·번역 경로가 **근본적으로 다르므로**, 계약 상세(§3~)에 들어가기 전에 아래
매핑을 먼저 이해해야 "무엇을 뜯어고쳐야 하는지"가 보인다.

> **큰 그림 — UI의 역할 자체가 바뀐다**
> - **wl UI = 제어 + 표시**: 브라우저는 **오디오를 보내지 않았다.** 서버가 로컬 마이크를 직접
>   캡처했고, UI는 start/stop 버튼과 SSE 결과 표시만 담당했다.
> - **wlk UI = 캡처 + 제어 + 표시**: 브라우저가 마이크를 캡처해 WebSocket으로 오디오를
>   스트리밍한다. → **오디오 캡처는 "개조"가 아니라 "신규 개발"이다.**

### 2.1 항목별 wl → wlk 매핑

| 관심사 | 기존 wl | 신규 wlk | UI 코드 변경 |
|---|---|---|---|
| 전송 계층 | SSE(전사 `/api/recordings`) + 별도 SSE(번역 `/api/translate`) + REST(start/stop/status) | 단일 WebSocket `/asr`(수신·제어·오디오 통합) | `EventSource` 2개·`fetch(start/stop)` 제거 → **`WebSocket` 하나로 통합** |
| 오디오 캡처 | **서버가 PyAudio로 로컬 마이크 캡처**(브라우저 미전송) | 브라우저 `getUserMedia`로 캡처해 WS로 전송 | **신규 개발.** 주 경로 = **WebM(`MediaRecorder`)**, 이게 기본·배포. PCM(AudioWorklet+16kHz 리샘플)은 `--pcm-input` 옵트인 시만(§6) |
| 메시지 모델 | 커서 기반 **문장 1개 델타** | **`snapshot` 1회 + 이후 `diff`**(바뀐 꼬리만, 기본) | 이벤트 append → **서버-권위 `lines[]` 미러를 누적 재구성**(prune → 꼬리 교체 → `n_lines` 검증) 후 `id` key로 증분 렌더(§4.2) |
| 필드명 | `content` / `language` / `status:"process"·"complete"` | `text` / `detected_language`(별칭 `lang`) / `finalized`(bool) | 파싱 필드명·타입 교체(§9.4 매핑표) |
| 확정/미확정 표시 | 문장 단위 `status` 회색↔진하게 | 의미가 다름 → **§2.2 참조** | `lines[]`=진하게 / `buffer_*`=연하게 **2단계**. `finalized`는 색 아닌 리렌더 최적화(안정 key)용(§2.2) |
| 번역 | 문장마다 **별도 `POST /api/translate` SSE**(토큰 스트리밍) | `lines[].translation` **인라인**(확정 후 통째로) + `buffer_translation`(진행중 번역) | `/api/translate` 호출·SSE 제거 → `lines[].translation` 읽기. **스트리밍 타이핑 UX는 사라짐.** `buffer_translation`도 동작(§7) |
| 화자분할 | 없음 | `lines[].speaker`(int), `-2`=침묵/`0`=진행중 | **신규 UI**(배지·색 직접 구현, §5) |
| 타임스탬프 | SSE에 없음(내부만 float 초) | `start`/`end` = 벽시계 `"HH:MM:SS"` 문자열(표시 전용) | 표시에만 사용. **누적/식별 키는 `id`**(안정 세그먼트 식별자) — `start\|end\|speaker` 복합키 금지(§4.4) |
| 녹음 제어 | start/stop/status — **stop=캡처만 정지, WS 연결 유지(재개 가능)**, stop 시 화면도 클리어 | 연결=시작 / 빈 프레임=**종료(되돌릴 수 없음)**, status·재개 없음 | start=WS 열기+캡처 시작 / stop=빈 프레임+`close()`. **pause/resume 버튼이 있었다면 wlk는 resume 불가 → 제거·비활성**(재시작=`close()` 후 새 WS 연결=서버 세션 초기화). wl stop은 화면을 지웠으나 wlk는 프론트 누적분이 남음 |
| 단어교정 | `/api/corrections`(GET/POST/DELETE) | **거의 동일** | 사전 관리 화면 **거의 1:1 재사용**(§9.1) |
| glossary | `/api/prompts`(glossary/sentence 블록) | **구현됨**(GET 조회·POST add-item·POST delete-item) | 단어교정(§9.1)과 유사하게 연결 가능 — 상세는 §9.1 참조 |

### 2.2 확정/미확정 표시 (진하게 vs 연하게) — 채택 방식

렌더는 **2단계 농도**로 단순하게 간다. **`lines[]`의 `text`는 전부 진하게, `buffer_*` 텍스트만
연하게.** 텍스트 색을 정할 때 `finalized`를 볼 필요가 없다(내장 UI가 실제로 이렇게 한다 —
`lines[].text`엔 색을 안 주고 `buffer`만 회색).

```
lines[]의 text   → 진하게 (finalized true/false 무관, opacity 1)
buffer_* 꼬리     → 연하게 (opacity ~0.4)
```

`buffer_*`는 별도 줄이 아니라 **맨 아래(현재 진행) 줄의 꼬리**에 이어붙인다: 전사 꼬리 =
`buffer_diarization` → `buffer_transcription` 순, 번역 꼬리 = `buffer_translation`(번역 활성 시 진행중 번역, 비활성 시 `""`).

```jsx
const rows = [...finalizedHistory, ...lines.filter(l => !l.finalized)];
rows.map((line, i) => (
  <p>                                    {/* lines[] 텍스트 = 진하게 */}
    <SpeakerBadge n={line.speaker} />
    <span>{line.text}</span>
    {i === rows.length - 1 &&            /* 맨 아래 줄에만 buffer 꼬리를 연하게 */
      <span className="buffer">{buffer_diarization}{buffer_transcription}</span>}
    {line.translation && <div className="translation">{line.translation}</div>}
  </p>
));
```
```css
.buffer { opacity: 0.4; }   /* 또는 회색 */
```

- **`finalized`는 여전히 필요하다 — 색이 아니라 "어떤 줄을 다시 안 그릴지" 판단에.** `finalized === true`인
  줄은 리렌더 최적화(안정 key)에 활용할 수 있고, `false`인 줄만 매 메시지 새로 그리면 된다. 스타일링에서만
  안 쓸 뿐이다.
- **트레이드오프**: wl처럼 "문장 전체가 회색이었다가 확정 시 진해지는" 단계는 없다. 단어는 검증돼
  `lines[]`에 들어오는 즉시 진하게 굳는다(드물게 언어전환 경계에서 이미 진한 단어가 철회될 수
  있으나 실사용에선 거의 없음). 이 방식이 가장 단순하고 내장 UI와 동일하다.
- **종료 시 buffer 정착(fold-in)**: 마지막 `ready_to_stop` 렌더에서 내장 UI는 남은 `buffer_*`
  꼬리를 연한 span이 아니라 **마지막 줄 본문에 일반 텍스트로 접합**한다. 이 처리를 빼면 종료
  순간 마지막 미확정 발화가 화면에서 증발한다(§3.2 종료 시퀀스와 연동).

### 2.3 가장 큰 함정 3가지

> 1. **오디오 캡처는 신규 개발.** 기존 wl UI엔 오디오 전송 코드가 없다(서버가 마이크를 잡았음).
>    wlk의 기본 경로인 `MediaRecorder`(WebM) 캡처를 새로 구현해야 한다(§6).
> 2. **`buffer_*`는 `lines[]`에 아직 없는 "선행 텍스트"다.** 연하게 꼬리로 붙이면 되지만(§2.2),
>    특히 **diar 기본 ON에선 `buffer_diarization`을 빼면 최근 발화가 몇 초간 화면에서 사라진다**
>    (화자배정 지연 구간).
> 3. **wl에 있던 것들의 상실.** 번역 스트리밍 UX(확정 후 통째로 나타남·토큰 스트리밍 아님)와
>    **pause/resume**(wlk는 종료가 되돌릴 수 없어 재개 불가 → pause 버튼 제거·비활성, §2.1).
>    glossary 관리 API(`/api/prompts`)는 **구현됨**(§9.1) — 더 이상 상실 항목 아님.

---

## 3. 연결 라이프사이클

### 3.1 엔드포인트
- WebSocket: `ws://<host>:<port>/asr` (기본 `ws://localhost:8900/asr`), TLS면 `wss://`.
  > ⚠️ **절대 URL 권장**: `new WebSocket('/asr')` 같은 **상대 URL은 구형·에어갭 브라우저가 거부**한다(`URL is invalid`).
  > 프론트는 `` `${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/asr` `` 로 **절대 URL을 조립**할 것.
  > 임시 우회로 현재 백엔드가 index.html 서빙 시 상대 WS URL→절대 URL 정규화 shim을 `<head>`에 주입한다
  > (`basic_server.py` `_WS_SHIM`). 프론트가 절대 URL로 고치면 shim은 무해하게 통과한다. 상세 = [FRONTEND_LANGUAGE_SELECT_PATCH.md §0](FRONTEND_LANGUAGE_SELECT_PATCH.md).
- `GET /`는 기본적으로 내장 데모 UI를 서빙하지만, **`frontend/static/`에 React 빌드 산출물(dist)을 배치하면
  (`index.html` 존재 기준) 자동으로 그 dist를 대신 서빙한다** — 배포 방법 A([API_SPEC.md §1.1](API_SPEC.md)) 구현 완료.
  서빙 루트는 `--frontend-dir`(기본값 `frontend/static`)로 지정한다. **dist가 Vite `base`(예 `/wlkies`)로 빌드됐으면**
  백엔드가 `index.html`에서 base를 자동 추출해 그 하위(`/wlkies/assets`, `/wlkies/{spa}`)로 서빙하고 `GET /`는 base로
  리다이렉트한다(`--frontend-base`, 기본값 `auto`; 루트 빌드도 하위호환). `/asr`는 어느 경우든 동일하게 쓰면 된다.
- `GET /health`는 헬스체크용(§9.2) — React가 연결 전 서버 기동 확인에 활용 가능.
- 쿼리 파라미터(선택):
  - `?language=<code>` — **세션별 소스 언어 지정**. 허용값 `{auto, ko, en}`. **생략** = 서버 전역 `--lan`(기본 `auto`)을
    따름(세션 오버라이드 없음), **`?language=auto`** = 그 세션만 강제 auto(코드스위칭), **`?language=ko`/`en`** = 그 언어로
    고정. 허용 밖 값은 서버가 경고 로그 후 무시(서버 기본값 폴백).
    > ⚠️ **정정(2026-07-17~ 실효)**: 이 파라미터는 과거 기본 백엔드(SimulStreaming)에서 **무효**였다(세션 언어 주입이
    > `transcribe()`만 가로채는데 기본 백엔드는 `infer()`를 호출해 조용히 무시됨). 이제 실제로 동작한다 —
    > 언어를 고정하면 그 세션의 한↔영 재감지·`language_switch` 경계 로직이 비활성화된다. 세션에 실제 적용된 언어는
    > **연결 직후 `config` 메시지의 `language` 필드**로 확인할 수 있다(§4.1).
    > 참고: 내장 테스트 UI(설정 패널)에 소스 언어 드롭다운(auto/ko/en)이 추가돼 있어 `ko`/`en` 선택 시 WS URL에
    > `?language=`를 붙이고 auto면 생략한다(`buildWebSocketUrl()`). **배포 React의 언어 선택 UI는 프론트 담당 별도 소관** —
    > 필요 시 이 방식(드롭다운→쿼리파라미터)을 참고만 하면 된다.
  - `?mode=delta|full` — 출력 프로토콜(§4.2). **생략 시 서버 기본값 `full`**(= 매 메시지 전량 스냅샷, 누적 불필요).
    누적 재구성을 구현했다면 `?mode=delta`로 opt-in해 증분 전송을 받는다
    (마이그레이션용 임시 경로 — 세션이 길어질수록 페이로드·재렌더 비용이 선형 증가). `?mode=diff`는 `delta`의
    하위호환 별칭. 서버 기본값 자체는 CLI `--ws-protocol {delta,full}`로 바꾼다.

### 3.2 시퀀스 (React 구현 순서)
```
1) new WebSocket(".../asr")                       // 연결 = 녹음 시작
2) onmessage: {"type":"config", useAudioWorklet}  // 1회 수신 → 오디오 송신 방식 결정 후 녹음 시작
3) 오디오 청크를 바이너리(ArrayBuffer)로 계속 send
4) onmessage: {"type":"snapshot"} 1회 → {"type":"diff"} 반복  // 누적 재구성 후 증분 렌더(§4.2)
5) websocket.send(new ArrayBuffer(0))             // 사용자가 멈춤 = 녹음 종료
6) onmessage: {"type":"ready_to_stop"}            // 서버 처리 완료 → 최종 렌더 후 websocket.close()
```

- **연결 직후 서버가 config 메시지를 1회 전송**:
  ```json
  {"type": "config", "useAudioWorklet": true, "protocol": "delta", "mode": "delta", "language": "auto"}
  ```
  클라이언트는 이 config를 받은 **뒤에** 녹음을 시작해야 한다(송신 방식이 여기서 정해짐). `language`는 그 세션에
  실제 적용된 소스 언어(§4.1).
- **종료**: 빈 프레임 `new ArrayBuffer(0)` 송신 → 서버가 잔여 오디오를 flush하고 처리 마무리.
- **완료 신호**: 서버가 처리를 끝내면 `{"type":"ready_to_stop"}`을 보낸다. 받으면 마지막 상태
  렌더 후 `close()`.
- **종료 처리 중 잠금**: 빈 프레임 전송 후 `ready_to_stop`이 올 때까지 **새 녹음을 시작하면 안
  된다**(내장 UI는 record 버튼을 비활성화). 이 flush 구간에 새 WS를 열면 이전 세션과 상태가 꼬인다.

### 3.3 비정상 종료·재연결
내장 클라이언트엔 **자동 재연결이 없다.** `onclose`는 close code/reason을 읽지 않고 안내 문구만
띄운 뒤 녹음을 멈춘다. 서버 재시작·네트워크 끊김 시 세션이 그대로 끝나므로, **재연결이 필요하면
React가 직접 구현**해야 한다(`onclose`/`onerror`에서 code 확인 후 재연결·상태 복구 결정). 정상
종료(빈 프레임→`ready_to_stop`→`close`)와 비정상 종료를 구분할 것.

---

## 4. 메시지 스키마 (서버 → 클라이언트)

서버가 보내는 JSON은 **`type` 필드**로 종류를 구분한다.

### 4.1 제어 메시지
| type | 시점 | 페이로드 | 의미 |
|---|---|---|---|
| `config` | 연결 직후 1회 | `{"type":"config","useAudioWorklet":bool,"protocol":"delta"\|"full","mode":(protocol과 동일·구 별칭),"language":"auto"\|"ko"\|"en"}` | 오디오 송신 방식 + **적용 프로토콜** + **세션 적용 언어** 통지 |
| `ready_to_stop` | 처리 완료 | `{"type":"ready_to_stop"}` | 종료 신호 |
| `snapshot`/`diff` | `?mode=delta`일 때만 | §4.2 | 상태 메시지(델타) |
| (`type` 없음) | full 모드(기본) | §4.2 | 상태 스냅샷(전량 전송) |

> **`config.protocol`(신설)**: 이 세션에 실제 적용된 출력 프로토콜. `mode`는 같은 값을 싣는 구 클라이언트 호환
> 별칭이다(과거엔 항상 `"full"`이었다). 클라이언트는 `protocol ?? mode ?? "full"`로 읽는다.
>
> **`config.language`(2026-07-17 신설, additive·하위호환)**: 그 세션에 실제 적용된 소스 언어. `?language=`로 지정했으면
> 그 값, 미지정이면 서버 전역 `--lan`(기본 `auto`). 세션 언어가 의도대로 걸렸는지 확인용(필드 없는 구버전 서버 대비
> 방어적으로 읽을 것). 내장 UI는 이 값을 콘솔 로그로만 확인한다.

### 4.2 상태 메시지 — full(기본) / 델타(`?mode=delta` opt-in)
매 사이클(~50ms) 중 **직전과 다를 때만** 전송된다.

#### 기본은 기존 그대로 — 델타는 선택이다

> **아무것도 안 하면 full 모드**로 동작한다: 매 메시지가 전체 상태 스냅샷이라 통째 교체 렌더만 하면 된다
> (기존 인계본 내용 그대로). 단 세션이 길어질수록 페이로드와 전체 재렌더 비용이 누적 줄 수에 비례해 커진다
> (실측: 109초 시점 이미 메시지당 ~5.5KB).
> **`?mode=delta`로 opt-in하면** 매 메시지가 1~2줄로 평평해져 이 증가가 사라진다(총 전송량 4.7배 절감).
> 대신 **React가 상태를 누적**해야 한다 — 아래 재구성 알고리즘이 전부다.

- 첫 메시지 `{"type":"snapshot","seq":1, ...아래 전체 상태...}`
- 이후 `{"type":"diff","seq":N,"n_lines":M,"status":…,"buffer_*":…,"remaining_time_*":…,`
  `(선택)"lines_pruned":K,(선택)"new_lines":[Segment,…],(선택)"error":…}`

| diff 전용 필드 | 타입 | 항상? | 의미 |
|---|---|---|---|
| `seq` | number | O | 1부터 증가하는 메시지 순번(연결 단위) |
| `n_lines` | number | O | 이 메시지 적용 **후** 가져야 할 총 줄 수 — 검증 기준 |
| `lines_pruned` | number | ✕ | 앞에서 잘려나간 줄 수. 있으면 **먼저** 앞에서 그만큼 제거 |
| `new_lines` | Segment[] | ✕ | **공통 prefix 이후의 꼬리 전체**(append 대상 아님 — 아래 ⚠️) |

**⚠️ `new_lines`는 append가 아니라 꼬리 교체다.** 백엔드는 최근 줄을 **소급 수정**한다(경계 재조정·침묵 게이트
재개방, 대략 8초 이내 — §4.4의 ①②가 이 현상이다). 그러면 이미 보낸 줄이 갱신된 내용으로 `new_lines`에 다시
실린다. append 하면 같은 줄의 옛 판과 새 판이 함께 쌓여 **중복 표시**된다.

```js
// 서버-권위 lines[] 미러 재구성 (참조 구현: live_transcription.js `reconstructLines`)
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

- **렌더도 증분으로**: `common` 이전 줄은 건드리지 않고 꼬리만 교체한다. React는 `key={line.id}`로 리스트를
  렌더하면 앞부분이 자동 재사용된다(내장 UI는 `reconcileTranscriptDom`이 같은 일을 한다 — HTML이 같은 줄의
  DOM 노드는 아예 손대지 않는다).
- **재동기 수단은 재연결뿐**(새 연결 = 새 `snapshot`). 서버에 재전송 요청 채널은 없다.
- **full 모드(기본)**: `type` 필드 없이 매 메시지가 아래 전체 상태를 담고 `lines[]`를 전량 재전송한다 —
  받은 그대로 전체 교체 렌더만 하면 된다(누적 불필요).

#### 전체 상태 페이로드 (델타의 `snapshot`, full의 매 메시지)

```jsonc
{
  "status": "active_transcription",   // 또는 "no_audio_detected" | "error"
  "lines": [ /* Segment[] (§4.3) */ ],
  "buffer_transcription": "진행중 미확정 전사 텍스트",
  "buffer_diarization": "",           // 화자 배정 대기중 텍스트(diar 모드)
  "buffer_translation": "In progress...", // LLM 번역기가 채우는 진행중(미확정) 번역 — 번역 비활성 시 ""
  "remaining_time_transcription": 1.2,
  "remaining_time_diarization": 0.0,
  "error": "..."                      // status=="error"일 때만 존재
}
```

| 최상위 필드 | 타입 | 항상? | 의미 |
|---|---|---|---|
| `status` | str | O | `active_transcription`/`no_audio_detected`/`error` |
| `lines` | Segment[] | O(빈 배열 가능) | 확정/진행중 세그먼트 |
| `buffer_transcription` | str | O | 아직 확정 안 된 진행중 전사(디코딩 꼬리). **마지막 줄에 이어붙여 표시**(§2.2) |
| `buffer_diarization` | str | O | diar 지연으로 아직 화자배정 안 된 최근 발화. **마지막 줄 꼬리에 연하게 표시**(diar ON이면 빼지 말 것, §2.2) |
| `buffer_translation` | str | O | LLM 번역기(`TranslationManager.apply_interim_translation()`)가 채우는 진행중(미확정) 번역. 확정 문장이 없어 `lines[].translation`이 아직 없을 때 표시용. 번역 비활성(`--llm-translation` OFF)이면 항상 `""`, §7 참고 |
| `remaining_time_transcription` | float(초) | O | 전사 처리 지연(랙) |
| `remaining_time_diarization` | float(초) | O | 화자분할 처리 지연(diar off면 0) |
| `error` | str | status=="error"만 | 오류 메시지(FFmpeg 등) |

> ⚠️ **서버는 세션 전체 확정 히스토리를 무제한 유지하지만, 그 전체를 매번 보내지는 않는다(델타).** React는
> 위 재구성 알고리즘으로 서버-권위 `lines[]` 미러를 **반드시 누적 유지**해야 한다. 장시간 세션에서 리스트가
> 계속 길어지므로 렌더 성능이 걱정되면 가상 스크롤을 추가로 고려할 수 있다(델타 전송 + `id` key 증분 렌더만으로도
> 앞부분 재렌더 비용은 사라진다).
> ⚠️ **누적/식별 키는 `id`(안정 세그먼트 식별자, number) 단독을 쓸 것.** `start`/`end`는 1초 해상도
> 벽시계 문자열이라 같은 초에 여러 세그먼트가 시작될 수 있어(빠른 화자전환·코드스위칭) 키로 부적합하다.
> **`start`+`end`+`speaker` 복합키는 금지** — 백엔드가 같은 문장의 `end`를 사후에 늘려 재전송(문법게이트 재조립)하므로
> `end`가 낀 키는 매 성장마다 새 항목이 돼 같은 문장의 절단판이 누적된다(**growing-prefix 중복 표시**, 상세 §4.4).
> 델타 재구성은 위치 기반(꼬리 교체)이라 그 자체로는 중복이 없지만, 그 위에 얹는 React key·Map은 반드시 `id` 단독.
> ⚠️ **status별 렌더**: `no_audio_detected`를 받으면 내장 UI는 **화면 자막만 가리고 누적 state는
> 유지**한다(다음 `active_transcription`에서 복원). React가 이 status에서 자기 누적까지 비우면
> 침묵 구간마다 자막이 영구 소실된다. `error` status엔 내장 UI가 별도 배너가 없으니 필요하면
> React가 직접 만든다.

### 4.3 `lines[]` 세그먼트 필드
| 필드 | 타입 | 항상? | 값/예시 | 의미 |
|---|---|---|---|---|
| `speaker` | int | O | `1`,`2`,… / `-2` | 화자 번호. **diar off면 항상 `1`**. **`-2`=침묵 세그먼트**. (§5) |
| `text` | str·null | O | `"안녕하세요"` | 전사 텍스트(침묵이면 `null`/`""`) |
| `id` | number | O | `12.34` | **안정 세그먼트 식별자**(세션상대 시작초). 누적/React key는 **반드시 이 값**(§4.2 경고·§4.4). `end`가 자라거나 재개방돼도 불변 |
| `start` | str | O | `"13:15:30"` | **PC 실제 벽시계 시각**(`HH:MM:SS`, 24시간제, 센티초 없음) — 녹음 시작 시점이 아니라 그 세그먼트가 실제로 발화된 시각. **표시 전용, 식별 key로 쓰지 말 것** |
| `end` | str | O | `"13:15:32"` | 동상 |
| `finalized` | bool | O | `true`/`false` | 문장 확정 여부. **diar on/off 관계없이 정상 갱신됨** |
| `completed` | bool | O | `finalized`와 동일 | React 호환 별칭 |
| `finalize_trigger` | str·null | O | `silence`/`punctuation`/`language_switch`/`speaker_change`/`null` | 문장이 어떤 로직으로 확정·분리됐는지. `null`=미확정. 확정 트리거 배지 표시에 활용 가능(필수 아님) |
| `translation` | str | 번역 있을 때만 | `"Hello"` | 인라인 번역(§7). 확정+번역활성 세그먼트만 |
| `detected_language` | str | 감지됐을 때만 | `"ko"`,`"en"` | 언어 코드 |
| `lang` | str | detected_language 있을 때만 | 동일 값 | React 호환 별칭 |

> ⚠️ `text`가 없고 `speaker != -2`인 줄은 응답에서 아예 빠진다(침묵 세그먼트만 `text` 없이도 방출).

### 4.4 중복 표시 방지 — 렌더 규칙 (⚠️ 미준수 시 같은 문장 중복)

백엔드는 문장 확정을 뒤 맥락에 따라 사후 조정하므로, 같은 세그먼트가 ① `end`가 자란 채 다시 오거나 ②
`finalized`가 `true`→`false`로 재개방될 수 있다(같은 `id` 유지).

- **델타에서는 이 재조정이 `new_lines` 꼬리 재전송으로 온다**(§4.2): 꼬리 교체를 그대로 수행하면 ①②가 자동 해소된다
  (재조정된 줄이 같은 `id`로 갱신 내용을 실어 다시 오기 때문). full 모드(기본)면 매 스냅샷 통째 교체 렌더로 동일 효과.
- **누적/키는 `id` 단독** (§4.2 경고): `start|end|speaker` 복합키는 `end` 성장분이 새 항목으로 쌓여 **growing-prefix 중복**을 만든다.
  `id`로 upsert + 진행중(`finalized:false`) 줄을 같은 `id`의 확정판보다 우선 렌더.
- **`buffer_*`는 마지막 진행중 줄에만** 이어붙인다 — 확정된 줄에 붙이면 진행중 텍스트가 확정 블록과 중복돼 보인다
  (위 §2.2 코드의 `i === rows.length - 1`은 진행중 줄이 있을 때 그게 마지막이라는 전제; 진행중 줄이 없으면 buffer도 비어야 정상).

> 정본 = [API_SPEC.md §2.4.4](API_SPEC.md), 참조 구현 = 내장 UI `live_transcription.js`. 이 규칙 미준수가 실측에서 kor
> 낭독체 WER을 3배 부풀린 사례가 있었다(측정이 UI DOM 스크래핑 → 렌더 중복이 지표까지 오염).

---

## 5. 화자분할(speaker) 표시

기존 `whisperlive`에 **없던 신규 기능**이다. **`--diarization`은 기본값이 `True`(ON)** —
서버 쪽 별도 설정 없이 연결해도 화자 배정이 붙는다. config 메시지엔 화자분할 여부 플래그가
따로 없으므로 **프론트는 `speaker` 값으로 다화자 여부를 추론**한다.

| `speaker` | 의미 |
|---|---|
| `1,2,3,…` | 화자 번호(diar on이면 1-base) |
| `1` | diar off일 때 **모든** 세그먼트 |
| `-2` | **침묵 세그먼트** — 침묵 아이콘으로 렌더 |
| `0` | (UI 한정) "화자분할 진행중" 로딩 표식 |

⚠️ **내장 UI엔 화자별 색상 매핑이 없다**(단일 배지 클래스). 다화자 구분색이 필요하면
**React가 `speaker` 번호→색 매핑을 직접 구현**해야 한다. 침묵(`-2`)은 silence 아이콘, diar
진행중(`0`)은 스피너로 렌더하는 것을 권장한다.

**diar + 번역 동시 사용 가능**: 과거엔 diar 모드에서 `finalized`가 항상 false라 번역이 붙지
않는 제약이 있었으나 해소됐다. `finalized`/`completed`를 diar on/off 관계없이 그대로 신뢰해서
렌더링하면 된다.

---

## 6. 오디오 송신 (클라이언트 → 서버)

`config` 메시지의 `useAudioWorklet`(= 서버 `--pcm-input` 여부)로 분기한다.

> ⚠️ 이 값은 **서버 CLI 플래그(`--pcm-input`)로만 결정되는 순수 서버→클라이언트 값**이다.
> 프론트가 요청·설정할 수 있는 경로(쿼리 파라미터·WS 메시지 등)가 없다 — **받아서 분기만 하면
> 된다.** 배포 기본값(`--pcm-input` 미지정)에서는 항상 `false`가 오므로, WebM 경로만 구현할
> 계획이면 이 값 자체를 신경 쓸 필요가 없다.

### 6.1 WebM 모드 (`useAudioWorklet === false`) — **기본·배포 경로**
`MediaRecorder(stream, {mimeType:"audio/webm"})`로 만들고 **`recorder.start(100)`처럼 timeslice(ms)를
반드시 지정**해 100ms마다 나오는 Blob을 `websocket.send`. 서버가 FFmpeg로 디코딩한다.
⚠️ **`start()`를 인자 없이 호출하면 `stop()` 시점까지 청크가 안 나와 실시간 전사가 아예 안 된다**
(가장 흔한 실수 — 내장 UI 기본 timeslice=100ms). **`--pcm-input` 기본값이 꺼져 있어 이게 기본
경로이며, 폐쇄망 배포도 이 설정으로 기동한다.**

### 6.2 PCM 모드 (`useAudioWorklet === true`, 서버 `--pcm-input`)
1. AudioWorklet으로 마이크 mono Float32를 캡처.
2. 네이티브 샘플레이트 → **16kHz 리샘플**, **s16le(Int16 little-endian) PCM** 변환.
3. 0.5초 단위 ArrayBuffer로 `websocket.send`.

### 6.3 React 주의
- **먼저 구현할 주 경로는 WebM(`MediaRecorder`)** 이다 — 기본값이자 배포 설정. 대부분의 경우
  이것만 구현하면 된다.
- **`mimeType` fallback**: `audio/webm` 미지원 브라우저(일부 Safari)에선 `MediaRecorder` 생성자가
  throw하므로 `try{new MediaRecorder(stream,{mimeType:"audio/webm"})}catch{new MediaRecorder(stream)}`로
  감싼다. 단 폴백이 mp4 등 다른 컨테이너를 내면 서버 FFmpeg 디코딩과 어긋날 수 있으니 배포 대상
  브라우저(폐쇄망 Chrome/Edge)를 확인할 것.
- **PCM(AudioWorklet)은 서버를 `--pcm-input`으로 전환할 때만** 필요하다. 이 경우 React도
  AudioWorklet+Worker(16kHz/s16le 변환)를 미러링해야 하며(AudioWorklet 미지원 브라우저에선
  throw), 기본 배포에선 불필요하다.
- 마이크는 `autoGainControl/noiseSuppression/echoCancellation` 전부 `false`로 `getUserMedia`.
- 종료 프레임 `new ArrayBuffer(0)`은 두 모드 공통.

### 6.4 내장 UI 코드 재사용 가이드
"오디오 캡처는 신규 개발"(§2.3)이지만 **백지 작성은 아니다** — 내장 데모(`whisperlivekit/web/live_transcription.js`)의 캡처 로직은 DOM 조작과 분리돼 있어 상당 부분 그대로 옮길 수 있다.

**그대로/거의 그대로 재사용 가능**
| 대상 | 위치 | 비고 |
|---|---|---|
| WebM 캡처 핵심 블록 | `:645-659` | `mimeType` try/catch + `ondataavailable`+`start(chunkDuration)`. DOM 의존 없음 |
| 마이크 constraints | `:600-603` | `autoGainControl/noiseSuppression/echoCancellation:false` |
| 녹음 종료 정리(cleanup) | `:696-745` | recorder/audioContext/microphone 해제 순서 |
| config 대기 패턴 | `:34-35`,`:772,776` | `configReady` Promise — config 수신 전 캡처 시작 금지 |
| PCM 전환 시 파일째 재사용 | `pcm_worklet.js`,`recorder_worker.js` | 순수 Web API(프레임워크 비종속), 지금 당장은 불필요 |

**참고만 하고 새로 작성**
- DOM 직접 조작(`statusText`·`linesTranscriptDiv` 등) → React state/JSX로 재작성.
- `enumerateMicrophones()`(`:126-140`)의 getUserMedia+enumerateDevices 로직은 재사용 가능하나, `populateMicrophoneSelect()` 드롭다운 렌더는 새로 작성.
- Chrome extension 전용 분기(`isExtension`·`tabCapture`)는 React 웹앱에 불필요, 제거.
- 파형·타이머·Wake Lock은 선택 UX — 필요하면 로직만 참고.

---

## 7. 번역(translation) 표시

- **활성화**: 서버 플래그 `--llm-translation`(**기본 ON**, 2026-07-16~ — 배포 PC llama.cpp `gpt-oss-20b`
  대상). 끄면(`--no-llm-translation`) `lines[].translation`·`buffer_translation` 모두 항상 비어 있다.
  dev PC는 `--translation-serve ollama` 등으로 Ollama `qwen2.5:7b`를 가리키도록 재정의한다(서버 플래그만
  바뀌고 프론트 변경 불필요, 상세: [DEPLOYMENT_OFFLINE.md §5](DEPLOYMENT_OFFLINE.md)).
- **세그먼트별 확정 번역** `lines[].translation`(str): 번역 활성 + 해당 세그먼트
  `finalized=true`일 때 채워진다. 캐시 미스면 비차단으로 번역 요청 후 **다음 스냅샷부터**
  채워진다(확정 후 문장 통째로 등장 — wl처럼 토큰 단위로 흐르지 않음). **이 경로는 정상 동작한다.**
- ✅ **(2026-07-16 구현 완료) 진행중(미확정) 번역 `buffer_translation`도 이제 동작한다.** `TranslationManager`에
  `apply_interim_translation(text, src_lang)`이 추가돼, 확정 세그먼트 번역과 **동일한 `--llm-translation`
  경로/번역기 백엔드**로 `lines[]`의 마지막 `finalized:false` 세그먼트(아직 확정 안 된 자라나는 문장) 텍스트를
  번역해 채운다(레거시 NLLB 경로와는 무관 — 그쪽은 여전히 미완성 스텁으로 남아 있다). 스로틀은 "이전 요청
  완료 전엔 새 요청 안 보냄" 하나뿐이라 값은 다소 지연(stale)될 수 있고, 문장이 확정되는 순간 그 진행중
  세그먼트가 사라지므로 `buffer_translation`도 함께 리셋된다. **React는 별도 변경 없이 그대로 렌더하면 된다**
  (이미 넣어둔 렌더 코드가 있다면 이제 실제로 값이 채워짐).

---

## 8. 전사 저장 API (`/api/save-transcript`)

WS `/asr`와 별개로, 사용자가 UI의 **저장 버튼을 눌렀을 때**만 누적 전사를 서버 로컬 파일로
저장하는 REST 엔드포인트다(브라우저 다운로드가 아니라 서버 프로세스가 디스크에 씀).
**녹음 종료(`ready_to_stop`) 시 자동 호출하지 않는다** — 버튼을 누르지 않으면 저장되지 않는다.

| 메서드/경로 | 요청 body | 응답 | 비고 |
|---|---|---|---|
| `POST /api/save-transcript` | `{"lines":[{"speaker":int,"text":str,"translation":str\|undefined}, ...]}` | `{"status":"success","path":str,"line_count":int}` | 저장 경로는 서버 `--transcript-save-dir`(기본 `./transcripts`); 파일명 `transcript_YYYYMMDD_HHMMSS.txt` |

- txt 형식은 화자+텍스트(+번역)만 담는다(타임스탬프 없음): `[화자 N] 텍스트` 다음 줄에
  `    ↳ 번역`(있을 때만).
- 저장 버튼은 녹음 중에도 클릭 가능하며, 클릭 시점까지의 전체 누적 내용을 매번 새 타임스탬프
  파일로 저장한다(직전 저장 이후 증분만 골라내지 않음 — 의도된 동작).
- **React 권장 흐름**: 저장 버튼(또는 동등 UI)을 두고, 클릭 시 §4의 누적 history(`finalized`
  줄 전체) + 마지막 미확정 줄을 합쳐 `lines` payload로 구성해 호출한다.
- 응답 `line_count`는 요청 `lines` 개수(**빈 텍스트 줄 포함**)라 실제 파일 기록 줄 수와 다를 수
  있다(빈 텍스트 줄은 파일에서 스킵).

---

## 9. 부록 (선택 기능)

### 9.1 단어교정/번역 Glossary 관리 REST — `/api/corrections`, `/api/prompts`
운용 중 단어 교정 사전 + 번역 glossary(예 `공군`→`ROKAF`)를 동적으로 추가/삭제하는 API. wl의
사전 관리 API와 형식이 **거의 동일**하므로 기존 UI 화면을 그대로 재사용할 수 있다(필수 아님).

**단어교정 — `/api/corrections`**

| 메서드/경로 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `GET /api/corrections` | — | `{"틀린단어": "교정단어", ...}` | **사용자 추가분(SQLite)만** 반환 — 내장 기본 사전(base JSON)은 안 들어옴. 교정 UI가 GET 결과만 표시하면 기본 사전이 안 보임 |
| `POST /api/corrections` | `{"wrong_word": "6군", "correct_word": "육군"}` | `{"status": "success"}` | 추가, **즉시 반영**(다음 전사부터) |
| `DELETE /api/corrections/{wrong_word}` | — (path param) | `{"status": "success"}` | 삭제, **즉시 반영** |

**번역 Glossary — `/api/prompts`** (구현 완료 — 이전 버전 이 문서는 미구현으로 표기했으나 정정됨)

| 메서드/경로 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `GET /api/prompts` | — | `{"glossary_block": {"공군":"ROKAF", ...}, "sentence_block": {...}}` | `glossary_block`은 **사용자 추가분만** 반환(내장 기본 용어집 숨김), `sentence_block`은 기본+사용자 **전체** 반환 |
| `POST /api/prompts/add-item` | `{"block_key": "glossary_block", "origin": "공군", "translation": "ROKAF"}` | `{"status": "success"}` | `block_key`는 `"glossary_block"` 또는 `"sentence_block"`, `translation` 필수(누락 시 400). 추가, **즉시 반영**(다음 번역부터) |
| `POST /api/prompts/delete-item` | `{"block_key": "glossary_block", "origin": "공군"}` | `{"status": "success"}` 또는 `{"status": "warning", "message": "..."}` | 대상 없거나 내장 기본 항목이라 삭제 불가면 warning(에러 아님, HTTP 200) |

### 9.2 헬스체크 — `GET /health`
`{"status":"ok","backend":"whisper","ready":true}`. (`backend`는 서버 `--backend`에 따른 동적값, 기본 `whisper`.) React가 WS 연결 전 서버 기동 여부를
폴링하는 용도로 쓸 수 있음(선택).

### 9.3 증분 전송 opt-in `?mode=delta`
전량 전송(full)이 **기본**이므로 기존 연동은 손대지 않아도 그대로 동작한다. 장시간 세션의 페이로드·재렌더
증가를 없애려면 `/asr?mode=delta`로 연결하고 §4.2의 누적 재구성을 구현한다(내장 UI가 참조 구현이며 실제로
`?mode=delta`로 접속한다). 전환·롤백이 URL 파라미터 하나이므로 언제든 되돌릴 수 있다.
서버 기본값 자체는 CLI `--ws-protocol {delta,full}`로 바꾼다 — 모든 클라이언트가 델타를 지원하면 `delta`로 올린다.

### 9.4 기존 ↔ 신규 필드 매핑 (마이그레이션 참고용)
| 기존(whisperlive SSE) | 신규(whisperlivekit WS) | 비고 |
|---|---|---|
| `content` | `lines[].text` | |
| `language` | `lines[].detected_language`(별칭 `lang`) | |
| `status:"process"/"complete"` | `lines[].finalized`(별칭 `completed`) | bool로 변경 |
| `start`(float) | `lines[].start`(str) | **타입 변경** — PC 실제 벽시계 시각(`"HH:MM:SS"`) |
| `end`(float) | `lines[].end`(str) | **타입 변경** — 위와 동일 |
| (이벤트 단위 1개) | `snapshot.lines[]` + `diff.new_lines[]` | 델타 — 누적 미러에 **꼬리 교체**로 적용(§4.2) |
| — | `lines[].speaker` | **신규(화자분할)** |
| 별도 `POST /api/translate` | `lines[].translation` + `buffer_translation` | 인라인화(둘 다 동작, §7) |
| — | `buffer_transcription` | 진행중 미확정 텍스트 |

---

## 10. React 측 구현 체크리스트

- [ ] `EventSource`/`POST start|stop` 제거 → `new WebSocket(".../asr")`.
- [ ] 첫 `{"type":"config"}` 처리 → `useAudioWorklet` 분기 후 녹음 시작.
- [ ] **델타 수신 구현(필수, §4.2)**: `snapshot`이면 전체 교체, `diff`면 ① `lines_pruned` 앞 제거 →
      ② `common = n_lines - new_lines.length` → ③ `lines.slice(0, common).concat(new_lines)` **꼬리 교체
      (append 금지)** → ④ `buffer_*`/`remaining_time_*`/`status` 교체 → ⑤ `lines.length === n_lines` 검증
      (불일치 시 재연결). 누적 구현 전이면 `?mode=full`로 pin(§9.3).
- [ ] **증분 렌더**: `key={line.id}`로 리스트를 렌더해 공통 prefix가 재사용되게 한다(전체 교체 렌더 금지 —
      세션이 길어지면 매 메시지 전체 재렌더가 메인스레드를 잡아먹는다). `lines[]` +
      `buffer_transcription`(마지막 줄 미확정) 합성은 그대로.
- [ ] 저장 버튼 클릭 시 `POST /api/save-transcript` 호출(§8) — 자동 저장 아님.
- [ ] 오디오 캡처 구현: **WebM(MediaRecorder) 기본**, 또는 PCM(AudioWorklet+Worker, 서버
      `--pcm-input` 시). 재사용 가능한 내장 코드는 §6.4 참고.
- [ ] 필드 타입 변경: `start`/`end`는 `"HH:MM:SS"` 문자열(PC 실제 벽시계 시각, 센티초 없음),
      `finalized`(=completed) bool, 언어는 `detected_language`(=lang). **history Map 키(누적 시)는
      `id` 단독**(§4.2·§4.4) — `start` 단독·`start`+`end`+`speaker` 복합키 **금지**(growing-prefix 중복).
- [ ] 첫 `config`의 `protocol`(=`mode`) 값으로 서버가 델타인지 full인지 확인(`protocol ?? mode ?? "full"`).
- [ ] 확정/미확정 스타일(2단계): `lines[]` 텍스트는 전부 진하게, `buffer_*`만 연하게.
      `finalized`는 색이 아니라 **히스토리 누적에만** 사용(§2.2 참조).
- [ ] 화자 UI: `speaker` 배지/색 직접 구현, `-2`=침묵, `0`=diar 진행중, `buffer_diarization` 표시.
- [ ] 종료: `send(new ArrayBuffer(0))` → `ready_to_stop` 수신 → `close()`. 종료 flush 중엔 새 녹음 시작 금지(§3.2).
- [ ] 녹음 상태 표시는 wl의 `GET /api/recordings/status` 폴링 대신 **WS `readyState`/`onopen`·`onclose`**로 대체(대응 엔드포인트 없음). 비정상 종료 시 자동 재연결은 없으니 필요하면 직접 구현(§3.3).
- [ ] 번역 표시: 인라인 `lines[].translation`(정상 동작) + `buffer_translation`(진행중 번역, 2026-07-16
      구현 완료 — 별도 React 작업 불필요, §7).
- [ ] (선택) 단어교정 사전 관리 UI가 필요하면 `/api/corrections` REST 호출(§9.1).
