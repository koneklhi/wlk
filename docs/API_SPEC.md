# WhisperLiveKit API 명세서 — React 프론트엔드 연동용

> **범위**: 배포 React UI가 실제로 사용하는 백엔드 계약만 정식 명세로 정리한다 —
> 실시간 전사 WebSocket `/asr` 1개 + 애플리케이션 REST 엔드포인트(`/health`,
> `/api/save-transcript`, `/api/corrections`, `/api/prompts`). OpenAI/Deepgram 호환 계층
> (`/v1/audio/transcriptions`, `/v1/listen` 등)은 이 프론트와 무관하며 상세는
> [0.Metafile/docs/API.md](../0.Metafile/docs/API.md) 참조.
> **연동 개요·마이그레이션 가이드·코드 근거 상세**는 [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md)
> 참조(구 상세본 FRONTEND_HANDOFF.md는 `docs/archive/`로 이동, 내용은 SUMMARY로 대체).
>
> 문서 기준: master `534bad1` 시점(전사 라인 리텐션 = **무제한**, 번역 glossary 관리 API·진행중 번역 구현 완료). 값·기본값은 §6 참조.

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

- **개발 중**: 백엔드는 팀 개발 PC에서 구동된다. 프론트는 **`ws://<개발 서버 IP>:8900/asr`**(REST도 동일 호스트)로 붙는다 — 개발자 자신의 `localhost`가 아님에 주의.
  - **마이크(`getUserMedia`)는 보안 컨텍스트(`https` 또는 `localhost`)에서만 동작**하므로, React 개발 서버는 **개발자 자기 `localhost`에서 실행**한다(예: `http://localhost:5173`). WebSocket/REST 대상만 위 개발 서버 IP를 가리키면 된다.
- **배포 = 방법 A(단일 프로그램)**: 단일 PC 로컬 전용. wlk 백엔드가 React **빌드 산출물(`dist/`)을 `/`에서 서빙**하도록 통합한다(정적 마운트 + SPA fallback — 기존 wl이 쓰던 방식과 동일). 사용자는 그 PC에서 `localhost:8900`으로 접속 → localhost라 마이크도 http로 정상, **HTTPS 불필요**. (백엔드 정적 서빙 배선은 빌드 `dist/`가 나오면 백엔드팀이 추가한다.)
- **백엔드 URL 구성(권장 패턴)**: 프론트는 백엔드 주소를 **same-origin 자동 유도(`window.location` 기반)를 기본값**으로 두고, **개발용 env 변수(예 `VITE_WLK_URL`)로만 오버라이드**한다. → 배포(방법 A = same-origin)에선 설정 없이 동작하고, 개발 중엔 env로 개발 서버 IP를 지정한다.
  - 빌드 **base path는 `/`** 기준(방법 A에서 `dist/`가 루트에서 서빙됨). react-router 등 클라이언트 라우팅을 쓰면 백엔드 SPA fallback이 필요하다(백엔드에 반영).

### 1.2 이번 연동 구현 범위 (UI 지침 — 백엔드 계약과 별개)

> 백엔드는 아래 값을 **모두 계속 제공**한다. 이 표는 **이번에 UI에서 무엇을 구현/표시할지**의 범위이며, 백엔드 계약(스키마)은 바뀌지 않는다.

| 항목                                  | 이번 범위                 | 비고                                                      |
| ------------------------------------- | ------------------------- | --------------------------------------------------------- |
| 번역 `lines[].translation`            | **표시함**                | 서버 `--llm-translation` **ON** 상태로 구동               |
| 화자분할 `speaker`                    | **수신만, UI 표시 안 함** | 서버 diar ON(값은 옴). 화자 배지·색은 이번엔 미구현(§2.6) |
| 전사 저장 `POST /api/save-transcript` | **범위 제외**             | 저장 버튼 미구현. §3.2는 참고용                           |
| `finalize_trigger`                    | **UI에 표시(테스트용)**   | 성능 분석 목적. **최종 배포 시 UI에서 제거 예정**(§2.7)   |

---

## 2. WebSocket API — `/asr`

실시간 전사의 유일한 채널. **연결 = 녹음 시작**, **빈 프레임 전송 = 녹음 종료**.

### 2.1 연결

```
ws://<host>:<port>/asr[?language=<code>]
```

**쿼리 파라미터**(선택)

| 파라미터   | 타입   | 기본               | 설명                                                            |
| ---------- | ------ | ------------------ | --------------------------------------------------------------- |
| `language` | string | 서버 `--lan`(auto) | 세션 소스 언어 강제(예: `ko`, `en`). 생략 시 서버 설정/자동감지 |

> 클라이언트가 서버 동작(화자분할 on/off, 오디오 입력 형식 등)을 쿼리로 바꿀 수는 없다.
> 그런 설정은 서버 CLI 플래그로만 결정되며, 관련 값은 연결 직후 `config` 메시지로 통지된다(§2.4.1).

### 2.2 라이프사이클

```
Client                                   Server
  │───── WebSocket 연결 ─────────────────▶│   (연결 = 녹음 시작)
  │◀──── {"type":"config", ...} ──────────│   1회, 오디오 송신 방식 통지
  │                                        │
  │───── 오디오 바이너리 프레임 ─────────▶│   (config 수신 후 시작, 반복)
  │◀──── 상태 스냅샷(JSON) ───────────────│   (~50ms, 직전과 다를 때만, 반복)
  │           …                           │
  │───── ArrayBuffer(0) (빈 프레임) ──────▶│   (녹음 종료 신호)
  │◀──── 잔여 스냅샷 ─────────────────────│   (flush 결과)
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

수신 JSON은 **`type` 필드 유무**로 종류를 구분한다.

- `type` 있음 → **제어 메시지**(§2.4.1: `config`, `ready_to_stop`)
- `type` 없음 → **상태 스냅샷**(§2.4.2)

#### 2.4.1 제어 메시지

| `type`          | 시점           | 페이로드                                                  | 의미                                                                            |
| --------------- | -------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `config`        | 연결 직후 1회  | `{"type":"config","useAudioWorklet":false,"mode":"full"}` | 오디오 송신 형식 통지. 배포 기본값에선 항상 이 값으로 고정(구현 불필요, 참고용) |
| `ready_to_stop` | 종료 처리 완료 | `{"type":"ready_to_stop"}`                                | 최종 렌더 후 `close()` 하라는 신호                                              |

#### 2.4.2 상태 스냅샷

`type` 필드 없음. 매 처리 사이클(~50ms) 중 **직전 스냅샷과 내용이 다를 때만** 전송된다.
`lines[]`는 **세션 전체 확정 히스토리를 무제한 유지**하며 매 스냅샷 그대로 재전송된다 — 클라이언트는
받은 `lines[]`를 **전체 교체 렌더**만 해도 히스토리가 유지된다(별도 누적 불필요, §6 리텐션 참조).

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

> `start`/`end`는 초 단위 벽시계 문자열(`HH:MM:SS`)이라 같은 초에 여러 세그먼트가 시작될 수 있다.
> 클라이언트가 항목 식별 key가 필요하면 `start` 단독이 아니라 **`start|end|speaker` 복합키**를 쓸 것.

#### 2.4.3 `lines[]` — Segment 객체

| 필드                | 타입           | 항상 존재 | 값/예시                    | 의미                                                     |
| ------------------- | -------------- | :-------: | -------------------------- | -------------------------------------------------------- |
| `speaker`           | int            |     O     | `1`,`2`,… / `-2`           | 화자 번호(§2.6). diar off면 항상 `1`, `-2`=침묵          |
| `text`              | string \| null |     O     | `"안녕하세요"`             | 전사 텍스트. 침묵 세그먼트면 `null`/`""`                 |
| `start`             | string         |     O     | `"13:15:30"`               | 발화 시각(PC 벽시계, `HH:MM:SS`, 24h, 센티초 없음)       |
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

### 2.5 `status` 값

| 값                     | 의미                                  | 클라이언트 렌더 권장                                                                                             |
| ---------------------- | ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `active_transcription` | 정상 처리 중                          | 스냅샷대로 렌더                                                                                                  |
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

### 3.3 단어교정 사전 — `/api/corrections`

전사 직후 적용되는 단어 교정 사전을 운용 중 동적으로 조회·추가·삭제. 변경은 **즉시 반영**(다음 전사부터).

#### `GET /api/corrections`

**응답 200**

```json
{ "6군": "육군", "공군참모총장": "공참총장" }
```

> **사용자가 추가한 항목(SQLite)만** 반환한다. 서버 내장 기본 사전(base JSON)은 이 응답에 포함되지 않으므로,
> 관리 UI가 GET 결과만 표시하면 기본 사전 항목은 보이지 않는다.

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

경로 파라미터 `wrong_word`로 항목 삭제.
**응답 200**

```json
{ "status": "success" }
```

### 3.4 번역 glossary — `/api/prompts`

번역 프롬프트에 주입되는 용어집(`glossary_block`)·예시 문장(`sentence_block`)을 운용 중 동적으로
조회·추가·삭제. 변경은 **즉시 반영**(다음 번역 요청부터) — 입력 문장에 실제 등장하는 용어만
번역 프롬프트에 골라 주입되는 방식이라 §3.3 단어교정 사전과 별개로 동작한다.

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

---

## 4. 번역(translation) 동작

- **활성화**: 서버 `--llm-translation` 플래그(기본 **OFF**). 꺼져 있으면 `lines[].translation`·
  `buffer_translation` 모두 항상 비어 있다. (개발 기본 Ollama `qwen2.5:7b`, 배포 llama.cpp `gpt-oss-20b` —
  서버 플래그만 다르고 프론트 계약은 동일.)
- **확정 문장 번역** `lines[].translation`: 번역 활성 + 해당 세그먼트 `finalized=true`일 때 채워진다.
  캐시 미스면 비차단으로 요청 후 **다음 스냅샷부터** 채워진다(문장 통째로 등장, 토큰 스트리밍 아님).
- **진행 중 번역** `buffer_translation`: 번역 활성 시 `lines[]`의 마지막 `finalized:false` 세그먼트를
  같은 번역기로 번역해 채운다. 이전 요청이 끝나기 전엔 새 요청을 보내지 않는 단순 스로틀이라 값이
  다소 지연(stale)될 수 있고, 문장이 확정되는 순간 그 세그먼트가 사라지므로 함께 `""`로 리셋된다.
  확정 번역(`lines[].translation`)과는 독립된 캐시/상태를 쓴다.
- **번역 glossary**(§3.4): 입력 문장에 실제 등장하는 용어만 골라 매 번역 요청 프롬프트에 동적으로
  주입된다(`glossary_block`) — 예시 문장(`sentence_block`)도 함께 주입. `/api/prompts`로 추가한
  항목은 **다음 번역 요청부터 즉시 반영**된다.

---

## 5. 데이터 타입 규약 요약

| 항목                      | 규약                                                                  |
| ------------------------- | --------------------------------------------------------------------- |
| 시간(`start`/`end`)       | 문자열 `"HH:MM:SS"`(PC 벽시계, 24시간제, 센티초 없음) — 경과시간 아님 |
| 확정 플래그               | `finalized`(bool), 별칭 `completed`                                   |
| 언어 코드                 | `detected_language`(예 `"ko"`,`"en"`), 별칭 `lang`                    |
| 미확정/버퍼 텍스트        | `buffer_*`(string), 항상 존재하되 내용이 없으면 `""`                  |
| 지연값                    | `remaining_time_*`(number, 초)                                        |
| 항목 식별 key(클라이언트) | `start`+`end`+`speaker` 복합키 권장                                   |

---

## 6. 상수·기본값

| 항목                 | 값                          | 근거/비고                                                                     |
| -------------------- | --------------------------- | ----------------------------------------------------------------------------- |
| 기본 WS/REST 포트    | `8900`                      | 서버 `--port`(개발 기본)                                                      |
| WS 경로              | `/asr`                      | —                                                                             |
| 오디오 입력          | WebM(MediaRecorder) 고정    | `useAudioWorklet=false`                                                       |
| WebM 청크 timeslice  | 100ms                       | `recorder.start(100)`                                                         |
| 화자분할             | 기본 ON                     | 서버 `--diarization`(기본 True)                                               |
| 번역                 | 기본 OFF (**현재 구동 ON**) | 서버 `--llm-translation`                                                      |
| **전사 라인 리텐션** | **무제한**                  | `lines[]` 세션 전체 유지·재전송(과거 5분 슬라이딩 → 무제한, master `606ecac`) |
| 전사 저장 디렉터리   | `./transcripts`             | 서버 `--transcript-save-dir`                                                  |

---

## 7. 관련 문서

- 연동 개요·wl→wlk 마이그레이션 가이드·코드 근거 상세: [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md)
- 메시지 스키마 변경 이력: [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md)
- OpenAI/Deepgram 호환 계층·diff 프로토콜 상세: [0.Metafile/docs/API.md](../0.Metafile/docs/API.md)
