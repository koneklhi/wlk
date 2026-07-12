# 프론트엔드 인계 문서 — React UI ↔ whisperlivekit 백엔드 연결

> **대상 독자**: React UI를 백엔드에 연결할 프론트엔드 개발자.
> **목적**: 기존 `whisperlive`(SSE) 대비 달라진 **WebSocket 메시지 계약 + 연결 절차 + 신규 화자분할(speaker)**을
> 코드 근거와 함께 한 문서로 인계한다.
> 이 문서는 [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md)의 상위 확장본이다(코드 대조로 보강·정정 포함).
> 모든 인용은 `파일:라인`으로 근거를 명시했다.

> **⚠️ 갱신 이력(코드 재대조 결과 — 2026-07-10)**: 최초 작성 이후 상당한 백엔드 리팩터링(CASE1/2/3 문장경계
> 수정, Exp-1xx대)이 있었다. 이번 대조로 발견한 실질 변경 3가지:
> 1. **§3.4·§5 정정**: "화자분할(diar) 모드에서 인라인 번역 미동작" 제약은 **해소됐다**([tokens_alignment.py:425-427](../whisperlivekit/tokens_alignment.py#L425-L427), 커밋 `2af2765`). 이제 diar ON에서도 번역이 붙는다.
> 2. **§3.1 정정**: `--diarization` 플래그의 **기본값이 `True`(ON)로 바뀌었다** — 아무 설정 없이 연결해도 화자 배정이 붙는다.
> 3. **§9(신규) 추가**: 문서 작성 이후 `/api/corrections`(단어교정 사전 관리) REST API가 신설됐다. `/health`, `/v1/listen`(Deepgram 호환), `/v1/audio/transcriptions`·`/v1/models`(OpenAI 호환)도 함께 추가됐으나 React 메인 연동에는 필수 아님.
> 그 외 파일 내 `파일:라인` 인용은 대규모 라인 이동이 있어 이번 대조로 갱신했다 — 내용(스키마·필드 의미) 자체는 대부분 그대로다.

---

## 0. 한눈에 보는 변경 (TL;DR)

| 축 | 기존 whisperlive | 신규 whisperlivekit |
|---|---|---|
| 전송 프로토콜 | SSE (`GET`, `text/event-stream`) + REST start/stop | **WebSocket** `ws://host:port/asr` |
| 전송 모델 | 이벤트 단위(세그먼트 1개 델타) | **전체 상태 스냅샷**(매 ~50ms `lines[]` 전체) — 매 메시지를 transcript 통째 교체로 처리 |
| 녹음 시작/종료 | `POST /api/recordings/start`·`/stop` | WS 연결=시작, **빈 프레임 `ArrayBuffer(0)`**=종료 |
| 번역 | 별도 `POST /api/translate` SSE | `lines[].translation` **인라인** + `buffer_translation` |
| 화자분할 | 없음 | **신규** `lines[].speaker`(int) + `buffer_diarization` |
| 시간 필드 | `start`/`end` float(초) | `start`/`end` **문자열** `"HH:MM:SS"` — **PC 실제 벽시계 시각**(녹음 시작 0초 기준 경과시간 아님) |
| 확정 표시 | `status: "process"/"complete"` | `finalized: bool`(별칭 `completed`) |

React가 반드시 새로 구현할 것: ① WS 연결·종료 시퀀스 ② config 메시지 처리 후 오디오 송신 ③ 매 메시지 전체교체 렌더 ④ 화자(speaker) 배지/색 ⑤ 오디오 캡처(PCM AudioWorklet 또는 WebM MediaRecorder).

---

## 1. 연결 라이프사이클

### 1.1 엔드포인트
- WebSocket: `ws://<host>:<port>/asr` (기본 `ws://localhost:8900/asr`), TLS면 `wss://`.
  - 핸들러: [basic_server.py:91-92](../whisperlivekit/basic_server.py#L91-L92) `@app.websocket("/asr")`.
  - 내장 UI의 URL 구성 예: [live_transcription.js:178-192](../whisperlivekit/web/live_transcription.js#L178-L192).
- `GET /`는 내장 데모 UI(HTML 1파일)를 서빙한다([basic_server.py:57-59](../whisperlivekit/basic_server.py#L57-L59)). **React 배포 시엔 사용하지 않는다** — `/asr`만 쓰면 된다.
- `GET /health`는 헬스체크용(§9) — React가 연결 전 서버 기동 확인에 활용 가능.
- 쿼리 파라미터(선택):
  - `?language=ko` — 세션별 소스 언어 강제([basic_server.py:96](../whisperlivekit/basic_server.py#L96)). 생략 시 서버 `--lan` 기본값/auto.
  - `?mode=diff` — 증분(diff) 프로토콜 옵트인(§6). 생략 시 `mode=full`(기본·권장).

### 1.2 시퀀스 (React 구현 순서)
```
1) new WebSocket(".../asr")                       // 연결 = 녹음 시작
2) onmessage: {"type":"config", useAudioWorklet}  // 1회 수신 → 오디오 송신 방식 결정 후 녹음 시작
3) 오디오 청크를 바이너리(ArrayBuffer)로 계속 send
4) onmessage: 상태 스냅샷(status/lines/buffer...) // 수신할 때마다 transcript 전체 교체 렌더
5) websocket.send(new ArrayBuffer(0))             // 사용자가 멈춤 = 녹음 종료
6) onmessage: {"type":"ready_to_stop"}            // 서버 처리 완료 → 최종 렌더 후 websocket.close()
```

- **연결 직후 서버가 config 메시지를 1회 전송**:
  ```python
  # basic_server.py:115
  await websocket.send_json({"type": "config", "useAudioWorklet": bool(config.pcm_input), "mode": mode})
  ```
  클라이언트는 이 config를 받은 **뒤에** 녹음을 시작해야 한다(송신 방식이 여기서 정해짐). 내장 UI는 `configReady` Promise로 대기([live_transcription.js:267-276, 739-743](../whisperlivekit/web/live_transcription.js#L267-L276)).
- **오디오 수신 루프**(서버): [basic_server.py:122-125](../whisperlivekit/basic_server.py#L122-L125) — `receive_bytes()`로 바이너리만 받는다.
- **종료**: 빈 프레임 `new ArrayBuffer(0)` 송신([live_transcription.js:659](../whisperlivekit/web/live_transcription.js#L659)) → 서버가 `is_stopping` 처리·잔여 flush([audio_processor.py:734-744](../whisperlivekit/audio_processor.py#L734-L744)).
- **완료 신호**: 서버가 처리 끝나면 `{"type":"ready_to_stop"}` 전송([basic_server.py:83-84](../whisperlivekit/basic_server.py#L83-L84)). 받으면 마지막 상태 렌더 후 `close()`.

---

## 2. 메시지 스키마 (서버 → 클라이언트)

서버가 보내는 JSON은 **`type` 필드 유무**로 종류를 구분한다.

### 2.1 제어 메시지 (`type` 있음)
| type | 시점 | 페이로드 | 의미 |
|---|---|---|---|
| `config` | 연결 직후 1회 | `{"type":"config","useAudioWorklet":bool,"mode":"full"\|"diff"}` | 오디오 송신 방식 결정 |
| `ready_to_stop` | 처리 완료 | `{"type":"ready_to_stop"}` | 종료 신호 |
| `snapshot`/`diff` | `?mode=diff`일 때만 | §6 | 증분 프로토콜(full 모드엔 안 옴) |

### 2.2 상태 스냅샷 메시지 (`type` 없음 — full 모드 기본)
`FrontData.to_dict()`가 생성([timed_objects.py:220-244](../whisperlivekit/timed_objects.py#L220-L244)). 매 사이클(~50ms) 중 **직전과 다를 때만** 전송([audio_processor.py:587-599](../whisperlivekit/audio_processor.py#L587-L599)).

```jsonc
{
  "status": "active_transcription",   // 또는 "no_audio_detected" | "error"
  "lines": [ /* Segment[] (§2.3) */ ],
  "buffer_transcription": "진행중 미확정 전사 텍스트",
  "buffer_diarization": "",           // 화자 배정 대기중 텍스트(diar 모드)
  "buffer_translation": "",           // 진행중(미확정) 번역
  "remaining_time_transcription": 1.2,
  "remaining_time_diarization": 0.0,
  "error": "..."                      // status=="error"일 때만 존재
}
```

| 최상위 필드 | 타입 | 항상? | 의미 | 근거 |
|---|---|---|---|---|
| `status` | str | O | `active_transcription`/`no_audio_detected`/`error` | [audio_processor.py:583-585](../whisperlivekit/audio_processor.py#L583-L585)(`error`는 L563) |
| `lines` | Segment[] | O(빈 배열 가능) | 확정/진행중 세그먼트 | §2.3 |
| `buffer_transcription` | str | O | 아직 확정 안 된 진행중 전사. **마지막 줄에 "진행중" 스타일로 표시** | |
| `buffer_diarization` | str | O | diar 지연으로 아직 화자배정 안 된 텍스트(diar 모드만 의미) | [tokens_alignment.py:379-429](../whisperlivekit/tokens_alignment.py#L379-L429) `get_lines_diarization()` |
| `buffer_translation` | str | O | 진행중(미확정) 번역 | [tokens_alignment.py:562](../whisperlivekit/tokens_alignment.py#L562) |
| `remaining_time_transcription` | float(초) | O | 전사 처리 지연(랙) | [audio_processor.py:244-259](../whisperlivekit/audio_processor.py#L244-L259) `get_current_state()` |
| `remaining_time_diarization` | float(초) | O | 화자분할 처리 지연(diar off면 0) | [audio_processor.py:594](../whisperlivekit/audio_processor.py#L594) |
| `error` | str | status=="error"만 | 오류 메시지(FFmpeg 등) | [timed_objects.py:242-243](../whisperlivekit/timed_objects.py#L242-L243) |

> ⚠️ **서버는 5분 슬라이딩 윈도우만 유지한다** — `lines[]`는 무제한 누적이 아니라 최근 구간만 담겨 온다.
> React도 내장 UI([live_transcription.js:27-30, 370-376](../whisperlivekit/web/live_transcription.js#L27-L30))처럼
> **`finalized`(=`completed`) `true`인 줄을 별도 상태(예: Map, key=`${start}|${end}|${speaker}` 복합키)에 직접 누적**하고 화면엔
> "누적 history + 아직 미확정인 최신 줄"만 합쳐 렌더해야 한다. 매 스냅샷을 그대로 전체교체(§0 TL;DR)만 하면
> 5분이 지난 확정 자막이 화면에서 사라진다.
> ⚠️ `start`가 초 단위 벽시계 시각(`HH:MM:SS`)으로 바뀌면서 같은 초에 여러 세그먼트가 시작될 수 있다(빠른 화자전환·코드스위칭) —
> `start` 단독을 키로 쓰면 충돌로 항목이 덮어써진다. 반드시 `start`+`end`+`speaker` 복합키를 쓸 것
> ([live_transcription.js:370-376](../whisperlivekit/web/live_transcription.js#L370-L376) 참고).

### 2.3 `lines[]` 세그먼트 필드 (`Segment.to_dict(session_start)`)
```python
# timed_objects.py — Segment.to_dict(self, session_start: Optional[float] = None)
# session_start(에폭초, WS 라이브 세션에선 AudioProcessor.beg_loop)가 주어지면
# 세션 상대 경과초(self.start/self.end)를 실제 벽시계 시각으로 변환해 내보낸다.
if session_start is not None:
    start_str = format_walltime(session_start, self.start)  # "HH:MM:SS" — PC 실제 시각
    end_str = format_walltime(session_start, self.end)
else:
    start_str = format_time(self.start)   # 폴백: "H:MM:SS.cc" (세션 상대 경과시간, 업로드 배치용)
    end_str = format_time(self.end)
_dict = {
  'speaker': int(self.speaker) if self.speaker != -1 else 1,
  'text':    self.text,
  'start':   start_str,
  'end':     end_str,
  'finalized': self.finalized,
  'completed': self.finalized,          # React 호환 별칭
}
_dict['finalize_trigger'] = self.finalize_trigger  # None이어도 항상 방출(silence/punctuation/language_switch/speaker_change|null)
if self.translation:        _dict['translation'] = self.translation
if self.detected_language:  _dict['detected_language'] = ...; _dict['lang'] = ...
```
> 라이브 WS(`/asr`) 응답은 `basic_server.py`의 `handle_websocket_results()`가 `session_start = audio_processor.beg_loop`(첫 유효 오디오 청크 수신 시점의 `time.time()` epoch)를 읽어 매번 전달하므로, `lines[].start`/`end`는 **항상 PC의 실제 벽시계 시각**이다. 반면 업로드 배치 엔드포인트(`/v1/audio/transcriptions`, `/v1/listen`)는 `session_start`를 넘기지 않아 기존 경과시간 포맷을 그대로 유지한다.

| 필드 | 타입 | 항상? | 값/예시 | 의미 |
|---|---|---|---|---|
| `speaker` | int | O | `1`,`2`,… / `-2` | 화자 번호. **diar off면 항상 `1`**. **`-2`=침묵 세그먼트**. (§3) |
| `text` | str·null | O | `"안녕하세요"` | 전사 텍스트(침묵이면 `null`/`""`) |
| `start` | str | O | `"13:15:30"` | **PC 실제 벽시계 시각**(`HH:MM:SS`, 24시간제, 센티초 없음) — 녹음 시작 시점이 아니라 그 세그먼트가 실제로 발화된 현재 시각. float 아님 ([format_walltime](../whisperlivekit/timed_objects.py#L18-L20)) |
| `end` | str | O | `"13:15:32"` | 동상 |
| `finalized` | bool | O | `true`/`false` | 문장 확정 여부. **(정정) diar 모드에서도 이제 정상 갱신됨** — 화자전환 등으로 줄이 닫히면 `true`(§3.4) |
| `completed` | bool | O | `finalized`와 동일 | React 호환 별칭 |
| `finalize_trigger` | str·null | O | `silence`/`punctuation`/`language_switch`/`speaker_change`/`null` | 문장이 어떤 로직으로 확정·분리됐는지. `null`=미확정. 항상 방출되는 필드 — 프론트에서 확정 트리거 배지 표시에 활용 가능(필수 아님) |
| `translation` | str | 번역 있을 때만 | `"Hello"` | 인라인 번역(§5). 확정+번역활성 세그먼트만(diar ON에서도 이제 동작, §3.4) |
| `detected_language` | str | 감지됐을 때만 | `"ko"`,`"en"` | 언어 코드 |
| `lang` | str | detected_language 있을 때만 | 동일 값 | React 호환 별칭 |

> ⚠️ `text`가 없고 `speaker != -2`인 줄은 직렬화에서 빠진다([timed_objects.py:235](../whisperlivekit/timed_objects.py#L235) `line.text or line.speaker==-2`).

### 2.4 기존 ↔ 신규 필드 매핑
| 기존(whisperlive SSE) | 신규(whisperlivekit WS) | 비고 |
|---|---|---|
| `content` | `lines[].text` | |
| `language` | `lines[].detected_language`(별칭 `lang`) | |
| `status:"process"/"complete"` | `lines[].finalized`(별칭 `completed`) | bool로 변경 |
| `start`(float) | `lines[].start`(str) | **타입 변경** — PC 실제 벽시계 시각(`"HH:MM:SS"`) |
| `end`(float) | `lines[].end`(str) | **타입 변경** — 위와 동일 |
| (이벤트 단위 1개) | `lines[]`(전체 배열) | 매 메시지 전체교체 |
| — | `lines[].speaker` | **신규(화자분할)** |
| 별도 `POST /api/translate` | `lines[].translation` + `buffer_translation` | 인라인화 |
| — | `buffer_transcription` | 진행중 미확정 텍스트 |

---

## 3. 화자분할(speaker / diarization) — 신규 기능

기존 `whisperlive`에 **없던 기능**이다. 서버를 `--diarization`으로 켜면 각 세그먼트에 화자 번호가 붙는다.

### 3.1 활성화
서버 플래그 `--diarization`([parse_args.py:41-46](../whisperlivekit/parse_args.py#L41-L46)), 기본 백엔드 sortformer. **⚠️(정정) `--diarization`은 이제 기본값이 `True`(ON)다** — 서버를 끄려면 명시적으로 `--no-diarization`을 줘야 한다. 즉 **React가 별도 조치를 하지 않아도 기본적으로 화자 배정이 붙는다.** config 메시지에는 화자분할 여부 플래그가 따로 없으므로 **프론트는 `speaker` 값으로 다화자 여부를 추론**한다.

### 3.2 speaker 값 의미
| `speaker` | 의미 |
|---|---|
| `1,2,3,…` | 화자 번호(diar on이면 **1-base**: sortformer speaker+1, [tokens_alignment.py:395](../whisperlivekit/tokens_alignment.py#L395)) |
| `1` | diar off일 때 **모든** 세그먼트(원래 -1 → 1로 매핑, [timed_objects.py:192](../whisperlivekit/timed_objects.py#L192)) |
| `-2` | **침묵 세그먼트**(SilentSegment) — 침묵 아이콘으로 렌더 |
| `0` | (UI 한정) "화자분할 진행중" 로딩 표식([live_transcription.js:390-393](../whisperlivekit/web/live_transcription.js#L390-L393)) |

### 3.3 화자 라벨/색 (내장 UI 레퍼런스)
```js
// live_transcription.js:397-398
const speakerNum = `<span class="speaker-badge">${item.speaker}</span>`;
// + 사람 아이콘 + (선택)언어 배지(item.detected_language) + (선택)finalize_trigger 배지
```
⚠️ **내장 UI엔 화자별 색상 매핑이 없다**(단일 `speaker-badge` 클래스). 다화자 구분색이 필요하면 **React가 `speaker` 번호→색 매핑을 직접 구현**해야 한다. 침묵(`-2`)은 silence 아이콘, diar 진행중(`0`)은 스피너로 렌더([live_transcription.js:389-406](../whisperlivekit/web/live_transcription.js#L389-L406)). 문서 작성 이후 `finalize_trigger` 값을 배지로 표시하는 코드가 추가됐다(`item.finalize_trigger`, 같은 블록 404-405행) — React에서도 §2.3 필드를 그대로 활용해 동일 UX를 구현할 수 있다.

### 3.4 ✅ [해소됨] diar 모드에서도 `finalized` 정상 동작 → 인라인 번역 동작
> 최초 작성 당시엔 diar 모드에서 `finalized`가 항상 false라 인라인 번역이 붙지 않는 제약이 있었다. **커밋 `2af2765`(`fix(diar+translation): 화자전환 세그먼트 finalized=True 마킹`, `6a1458b`로 master 머지)로 해소됐다.** 아래는 현재 동작이다.

- **현재 동작**: `get_lines_diarization()`이 화자 전환 등으로 한 줄이 닫히면(=다음 줄로 넘어가면) **마지막 세그먼트(현재 발화 중)를 제외한 나머지 전부**에 `finalized=True`를 설정한다:
  ```python
  # tokens_alignment.py:425-427
  # 화자 전환이 발생한 세그먼트는 확정 완료 — 마지막 세그먼트(현재 발화 중)는 제외
  for seg in segments[:-1]:
      seg.finalized = True
  ```
  어떤 트리거로 닫혔는지는 같은 함수의 `finalize_trigger` 결정 로직 참고([tokens_alignment.py:410-423](../whisperlivekit/tokens_alignment.py#L410-L423) — `language_switch`/`silence`/`punctuation`/`speaker_change`).
- **비-diar 경로**도 동일하게 침묵·언어전환·온점분할 시점에 `finalized=True`를 설정한다(`get_lines()` 내 [tokens_alignment.py:504](../whisperlivekit/tokens_alignment.py#L504), [522](../whisperlivekit/tokens_alignment.py#L522), [534](../whisperlivekit/tokens_alignment.py#L534)행). dataclass 기본값은 `False`([timed_objects.py:154](../whisperlivekit/timed_objects.py#L154)).
- **번역**: LLM 번역 매니저는 여전히 `not seg.finalized`면 건너뛰지만([llm_translation/manager.py:38](../whisperlivekit/llm_translation/manager.py#L38)), 이제 diar 모드에서도 `finalized=True`가 정상적으로 세팅되므로 **화자분할 + 인라인 번역 동시 사용이 가능하다.**
- **프론트 대응**: 더 이상 diar/번역을 상호 배타로 다룰 필요 없음. `finalized`/`completed`를 diar on/off 관계없이 그대로 신뢰해서 렌더링하면 된다.

---

## 4. 오디오 송신 (클라이언트 → 서버)

`config` 메시지의 `useAudioWorklet`(= 서버 `--pcm-input` 여부)로 분기한다.

### 4.1 PCM 모드 (`useAudioWorklet === true`, 서버 `--pcm-input`)
1. AudioWorklet `pcm-forwarder` 로드([live_transcription.js:579-585](../whisperlivekit/web/live_transcription.js#L579-L585)).
2. `pcm_worklet.js`: 마이크 mono Float32를 메인스레드로 postMessage([pcm_worklet.js:1-16](../whisperlivekit/web/pcm_worklet.js#L1-L16)).
3. `recorder_worker.js`: 네이티브 SR→**16kHz 리샘플**, **s16le(Int16 little-endian) PCM** 변환, 0.5초 단위 ArrayBuffer 전송([recorder_worker.js:26-92](../whisperlivekit/web/recorder_worker.js#L26-L92), `view.setInt16(..., true)`).
4. 워커 출력 ArrayBuffer를 그대로 `websocket.send`([live_transcription.js:595-611](../whisperlivekit/web/live_transcription.js#L595-L611)).

### 4.2 WebM 모드 (`useAudioWorklet === false`, 기본)
`MediaRecorder(stream, {mimeType:"audio/webm"})`, 청크마다 Blob을 `websocket.send`([live_transcription.js:612-626](../whisperlivekit/web/live_transcription.js#L612-L626)). 서버가 FFmpeg로 디코딩.

### 4.3 React 주의
- 폐쇄망 운용이 `--pcm-input`이면 React도 **AudioWorklet+Worker(16kHz/s16le 변환)를 미러링** 해야 한다 — `pcm_worklet.js`/`recorder_worker.js` 로직을 그대로 포팅 권장. AudioWorklet 미지원 브라우저에선 throw.
- 마이크는 `autoGainControl/noiseSuppression/echoCancellation` 전부 false로 getUserMedia([live_transcription.js:560-570](../whisperlivekit/web/live_transcription.js#L560-L570)).
- 종료 프레임 `new ArrayBuffer(0)`은 두 모드 공통.
- (참고) 내장 UI에는 브라우저 **확장(extension)** 실행 시에만 동작하는 `chrome.tabCapture` 탭오디오 캡처 경로도 있다(`isExtension` 분기) — 일반 웹앱(React)에는 해당 없음, 무시해도 된다.

---

## 5. 번역(translation) 전달

- **세그먼트별 확정 번역**: `lines[].translation`(str). 조건: 번역 활성 + 해당 세그먼트 `finalized=true`. LLM 경로는 캐시 히트 시 채워지고, 미스면 비차단 task 생성 후 **다음 스냅샷부터** 채워진다([llm_translation/manager.py:35-50](../whisperlivekit/llm_translation/manager.py#L35-L50)).
- **진행중 번역**: 최상위 `buffer_translation`(str) — 마지막 줄에 "진행중" 스타일로 표시([live_transcription.js:446-449](../whisperlivekit/web/live_transcription.js#L446-L449)).
- ✅ **(정정) diar 모드 제약 해소**: §3.4대로 화자분할 ON에서도 이제 `finalized=true`가 정상 세팅되어 인라인 번역이 정상 동작한다(과거엔 안 붙었음).

---

## 6. (선택) 증분 프로토콜 `?mode=diff`

`/asr?mode=diff`로 연결하면 full 스냅샷 대신 증분을 받는다: 첫 메시지 `{"type":"snapshot","seq":1, ...}`, 이후 `{"type":"diff","seq":N,"new_lines":[...],"lines_pruned":k, ...}`([diff_protocol.py](../whisperlivekit/diff_protocol.py)). **내장 UI는 이를 무시**([live_transcription.js:278-281](../whisperlivekit/web/live_transcription.js#L278-L281))하므로 React도 **full 모드로 시작 권장**. 대역폭 최적화가 꼭 필요할 때만 고려.

---

## 7. React 측 변경 체크리스트

- [ ] `EventSource`/`POST start|stop` 제거 → `new WebSocket(".../asr")`.
- [ ] 첫 `{"type":"config"}` 처리 → `useAudioWorklet` 분기 후 녹음 시작.
- [ ] 매 스냅샷 메시지에서 transcript **전체 교체** 렌더(append/patch 아님). `lines[]` + `buffer_transcription`(마지막 줄 미확정) 합성.
- [ ] **확정(`finalized`) 줄 누적**: 서버 5분 슬라이딩 윈도우 대응 — 확정 줄은 프론트 상태에 누적, 미확정 줄만 매번 교체(§2 참조).
- [ ] 녹음 종료 시 `POST /api/save-transcript` 호출(§10) — 내장 UI와 동일하게 자동 저장하면 저장 로직이 통일된다.
- [ ] 오디오 캡처 구현: PCM(AudioWorklet+Worker) 또는 WebM(MediaRecorder).
- [ ] 필드 타입 변경: `start`/`end`는 `"HH:MM:SS"` 문자열(PC 실제 벽시계 시각 — 녹음 시작 시점이 아니라 발화 시각, 센티초 없음), `finalized`(=completed) bool, 언어는 `detected_language`(=lang). history Map 키는 `start` 단독이 아니라 `start`+`end`+`speaker` 복합키(같은 초 충돌 방지).
- [ ] 화자 UI: `speaker` 배지/색 직접 구현, `-2`=침묵, `0`=diar 진행중, `buffer_diarization` 표시.
- [ ] 종료: `send(new ArrayBuffer(0))` → `ready_to_stop` 수신 → `close()`.
- [ ] 번역 표시: 인라인 `translation` + `buffer_translation`. diar ON에서도 이제 정상 동작(§3.4, 과거엔 미지원이었음).
- [ ] (선택) 단어교정 사전 관리 UI가 필요하면 `/api/corrections` REST 호출(§9) — 필수는 아님.

---

## 8. SCHEMA_CHANGES.md 대비 보강/정정 (코드 대조 결과)

대체로 정확하나 다음을 보강한다:
1. **`error` 최상위 필드**: `status:"error"` 동반 `error`(str) 설명 추가 필요.
2. **`speaker === -2`(침묵)·`speaker === 0`(diar 진행중)** 특수값: 문서는 "미사용 시 1"만 언급 — 렌더에 필수.
3. **`?mode=diff`** 증분 프로토콜 존재(문서엔 없음).
4. **`?language=` 쿼리**로 세션별 언어 강제 가능(문서엔 없음).
5. **(정정, 2026-07-10 재대조)** 화자분할 finalized=false / 인라인 번역 미동작 제약은 SCHEMA_CHANGES §6·본 문서 최초판 작성 시점 기준으로는 코드와 일치했으나, **그 뒤 커밋 `2af2765`로 해소됐다**(§3.4). SCHEMA_CHANGES.md 해당 절도 이 문서와 함께 갱신이 필요하다.
6. **`/api/corrections`·`/health`·`/v1/listen`·`/v1/audio/transcriptions`·`/v1/models`·`/api/save-transcript` REST/WS 엔드포인트**는 SCHEMA_CHANGES.md에도 없다(§9·§10 참고).

---

## 9. (신규, 2026-07-10 추가) `/asr` 외 엔드포인트 — 문서 작성 이후 신설

`/asr` WebSocket이 React 메인 연동 대상이라는 결론은 그대로다. 아래는 그 이후 `basic_server.py`에 추가된
엔드포인트로, **React의 핵심 전사 흐름엔 필수가 아니지만** 운영 UI(사전 관리)·서드파티 클라이언트 호환에 쓰인다.

### 9.1 단어교정 사전 관리 REST — `/api/corrections` (§3.5·§3.6 관련, 실사용 가능성 높음)
CLAUDE.md §3.5·§3.6이 요구하는 "동적 단어교정 사전"에 대응하는 실제 REST API다([basic_server.py:361-381](../whisperlivekit/basic_server.py#L361-L381)):

| 메서드/경로 | 요청 | 응답 | 비고 |
|---|---|---|---|
| `GET /api/corrections` | — | `{"틀린단어": "교정단어", ...}` (`word_manager.user_replacements` dict 그대로) | 사전 전체 조회 |
| `POST /api/corrections` | `{"wrong_word": "6군", "correct_word": "육군"}` | `{"status": "success"}` | 추가, **즉시 반영**(다음 전사부터) |
| `DELETE /api/corrections/{wrong_word}` | — (path param) | `{"status": "success"}` | 삭제, **즉시 반영** |

React에 운영자용 사전 관리 화면이 필요하면 이 3개 엔드포인트로 충분하다. 번역 glossary(예 `공군`→`ROKAF`) 동적 관리 API는 **아직 이 REST 세트에 없다** — §3.6의 glossary 요구는 현재 코드 조사 시점(2026-07-10) 기준 미구현.

### 9.2 헬스체크 — `GET /health`
`{"status":"ok","backend":"whisper","ready":true}`([basic_server.py:62-71](../whisperlivekit/basic_server.py#L62-L71)). React가 WS 연결 전 서버 기동 여부를 폴링하는 용도로 쓸 수 있음(선택).

### 9.3 서드파티 호환 API (React 메인 연동과 무관, 참고용)
- **Deepgram 호환 WebSocket** `/v1/listen`([basic_server.py:154-159](../whisperlivekit/basic_server.py#L154-L159), 구현은 `whisperlivekit/deepgram_compat.py`) — Deepgram SDK를 쓰는 외부 클라이언트가 서버를 drop-in 교체할 수 있게 하는 경로. 인증 없음, 신뢰도 점수 0.0 고정 등 Deepgram과 차이 있음.
- **OpenAI 호환 REST** `POST /v1/audio/transcriptions`(파일 업로드 1회성 전사, `response_format`으로 `json`/`text`/`verbose_json`/`srt`/`vtt` 지원)와 `GET /v1/models`([basic_server.py:270-354](../whisperlivekit/basic_server.py#L270-L354)) — OpenAI Whisper API 클라이언트 호환용 배치 전사 엔드포인트. **실시간 스트리밍이 아니다**(파일 전체를 받아 처리 후 응답) — React 실시간 UI에는 해당 없음.
- 이 세 엔드포인트는 CLAUDE.md §3.1(폐쇄망) 제약과 무관하게 로컬 파이프라인만 태운다(외부 네트워크 호출 없음).

---

## 10. REST API — 전사 저장 (`/api/save-transcript`)

WS `/asr`와 별개로, 녹음 종료 시 누적 전사를 **서버 로컬 파일**로 저장하는 REST 엔드포인트다
(브라우저 다운로드가 아니라 서버 프로세스가 디스크에 씀). 단어 교정 API(`/api/corrections`,
[SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) §4)와 동일한 REST 계열이며, 내장 UI는 `ready_to_stop` 수신 직후
자동 호출한다([live_transcription.js:307-320](../whisperlivekit/web/live_transcription.js#L307-L320)).

| 메서드/경로 | 요청 body | 응답 | 비고 |
|---|---|---|---|
| `POST /api/save-transcript` | `{"lines":[{"speaker":int,"text":str,"translation":str\|undefined}, ...]}` | `{"status":"success","path":str,"line_count":int}` | 저장 경로는 서버 `--transcript-save-dir`(기본 `./transcripts`); 파일명 `transcript_YYYYMMDD_HHMMSS.txt` |

- 서버 구현: [basic_server.py](../whisperlivekit/basic_server.py) `save_transcript()`.
- txt 형식은 화자+텍스트(+번역)만 담는다(타임스탬프 없음): `[화자 N] 텍스트` 다음 줄에 `    ↳ 번역`(있을 때만).
- **React 권장 흐름**: `ready_to_stop` 처리 시 §2의 누적 history(`finalized` 줄 전체) + 마지막 미확정 줄을 합쳐
  `lines` payload로 구성해 fire-and-forget으로 호출(await/블로킹 금지 — 실패해도 녹음 종료 흐름을 막지 않아야 함).
  이렇게 하면 내장 UI와 React의 저장 로직이 통일된다.
