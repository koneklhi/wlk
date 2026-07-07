# 프론트엔드 인계 문서 — React UI ↔ whisperlivekit 백엔드 연결

> **대상 독자**: React UI를 백엔드에 연결할 프론트엔드 개발자.
> **목적**: 기존 `whisperlive`(SSE) 대비 달라진 **WebSocket 메시지 계약 + 연결 절차 + 신규 화자분할(speaker)**을
> 코드 근거와 함께 한 문서로 인계한다.
> 이 문서는 [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md)의 상위 확장본이다(코드 대조로 보강·정정 포함).
> 모든 인용은 `파일:라인`으로 근거를 명시했다.

---

## 0. 한눈에 보는 변경 (TL;DR)

| 축 | 기존 whisperlive | 신규 whisperlivekit |
|---|---|---|
| 전송 프로토콜 | SSE (`GET`, `text/event-stream`) + REST start/stop | **WebSocket** `ws://host:port/asr` |
| 전송 모델 | 이벤트 단위(세그먼트 1개 델타) | **전체 상태 스냅샷**(매 ~50ms `lines[]` 전체) — 매 메시지를 transcript 통째 교체로 처리 |
| 녹음 시작/종료 | `POST /api/recordings/start`·`/stop` | WS 연결=시작, **빈 프레임 `ArrayBuffer(0)`**=종료 |
| 번역 | 별도 `POST /api/translate` SSE | `lines[].translation` **인라인** + `buffer_translation` |
| 화자분할 | 없음 | **신규** `lines[].speaker`(int) + `buffer_diarization` |
| 시간 필드 | `start`/`end` float(초) | `start`/`end` **문자열** `"H:MM:SS.cc"` |
| 확정 표시 | `status: "process"/"complete"` | `finalized: bool`(별칭 `completed`) |

React가 반드시 새로 구현할 것: ① WS 연결·종료 시퀀스 ② config 메시지 처리 후 오디오 송신 ③ 매 메시지 전체교체 렌더 ④ 화자(speaker) 배지/색 ⑤ 오디오 캡처(PCM AudioWorklet 또는 WebM MediaRecorder).

---

## 1. 연결 라이프사이클

### 1.1 엔드포인트
- WebSocket: `ws://<host>:<port>/asr` (기본 `ws://localhost:8900/asr`), TLS면 `wss://`.
  - 핸들러: [basic_server.py:82](../whisperlivekit/basic_server.py#L82) `@app.websocket("/asr")`.
  - 내장 UI의 URL 구성 예: [live_transcription.js:180-190](../whisperlivekit/web/live_transcription.js#L180-L190).
- `GET /`는 내장 데모 UI(HTML 1파일)를 서빙한다([basic_server.py:48-50](../whisperlivekit/basic_server.py#L48-L50)). **React 배포 시엔 사용하지 않는다** — `/asr`만 쓰면 된다.
- 쿼리 파라미터(선택):
  - `?language=ko` — 세션별 소스 언어 강제([basic_server.py:87](../whisperlivekit/basic_server.py#L87)). 생략 시 서버 `--lan` 기본값/auto.
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
  # basic_server.py:106
  await websocket.send_json({"type": "config", "useAudioWorklet": bool(config.pcm_input), "mode": mode})
  ```
  클라이언트는 이 config를 받은 **뒤에** 녹음을 시작해야 한다(송신 방식이 여기서 정해짐). 내장 UI는 `configReady` Promise로 대기([live_transcription.js:265-274, 733-738](../whisperlivekit/web/live_transcription.js#L265-L274)).
- **오디오 수신 루프**(서버): [basic_server.py:113-116](../whisperlivekit/basic_server.py#L113-L116) — `receive_bytes()`로 바이너리만 받는다.
- **종료**: 빈 프레임 `new ArrayBuffer(0)` 송신([live_transcription.js:652-654](../whisperlivekit/web/live_transcription.js#L652-L654)) → 서버가 `is_stopping` 처리·잔여 flush([audio_processor.py:722-736](../whisperlivekit/audio_processor.py#L722-L736)).
- **완료 신호**: 서버가 처리 끝나면 `{"type":"ready_to_stop"}` 전송([basic_server.py:74-75](../whisperlivekit/basic_server.py#L74-L75)). 받으면 마지막 상태 렌더 후 `close()`.

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
`FrontData.to_dict()`가 생성([timed_objects.py:201-214](../whisperlivekit/timed_objects.py#L201-L214)). 매 사이클(~50ms) 중 **직전과 다를 때만** 전송([audio_processor.py:585-595](../whisperlivekit/audio_processor.py#L585-L595)).

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
| `status` | str | O | `active_transcription`/`no_audio_detected`/`error` | [audio_processor.py:571-576](../whisperlivekit/audio_processor.py#L571-L576) |
| `lines` | Segment[] | O(빈 배열 가능) | 확정/진행중 세그먼트 | §2.3 |
| `buffer_transcription` | str | O | 아직 확정 안 된 진행중 전사. **마지막 줄에 "진행중" 스타일로 표시** | |
| `buffer_diarization` | str | O | diar 지연으로 아직 화자배정 안 된 텍스트(diar 모드만 의미) | [tokens_alignment.py:184-214](../whisperlivekit/tokens_alignment.py#L184-L214) |
| `buffer_translation` | str | O | 진행중(미확정) 번역 | [tokens_alignment.py:276](../whisperlivekit/tokens_alignment.py#L276) |
| `remaining_time_transcription` | float(초) | O | 전사 처리 지연(랙) | [audio_processor.py:233-235](../whisperlivekit/audio_processor.py#L233-L235) |
| `remaining_time_diarization` | float(초) | O | 화자분할 처리 지연(diar off면 0) | [audio_processor.py:582](../whisperlivekit/audio_processor.py#L582) |
| `error` | str | status=="error"만 | 오류 메시지(FFmpeg 등) | [timed_objects.py:212-213](../whisperlivekit/timed_objects.py#L212-L213) |

### 2.3 `lines[]` 세그먼트 필드 (`Segment.to_dict()`)
```python
# timed_objects.py:161-176
_dict = {
  'speaker': int(self.speaker) if self.speaker != -1 else 1,
  'text':    self.text,
  'start':   format_time(self.start),   # "H:MM:SS.cc"
  'end':     format_time(self.end),
  'finalized': self.finalized,
  'completed': self.finalized,          # React 호환 별칭
  'finalize_trigger': self.finalize_trigger,  # 확정 트리거(silence/punctuation/language_switch/speaker_change|null)
}
if self.translation:        _dict['translation'] = self.translation
if self.detected_language:  _dict['detected_language'] = ...; _dict['lang'] = ...
```

| 필드 | 타입 | 항상? | 값/예시 | 의미 |
|---|---|---|---|---|
| `speaker` | int | O | `1`,`2`,… / `-2` | 화자 번호. **diar off면 항상 `1`**. **`-2`=침묵 세그먼트**. (§3) |
| `text` | str·null | O | `"안녕하세요"` | 전사 텍스트(침묵이면 `null`/`""`) |
| `start` | str | O | `"0:00:03.42"` | **포맷 문자열**(H:MM:SS.cc) — float 아님 ([format_time](../whisperlivekit/timed_objects.py#L6-L15)) |
| `end` | str | O | `"0:00:05.10"` | 동상 |
| `finalized` | bool | O | `true`/`false` | 문장 확정 여부. **diar 모드에선 항상 false(§3.4 제약)** |
| `completed` | bool | O | `finalized`와 동일 | React 호환 별칭 |
| `finalize_trigger` | str·null | O | `silence`/`punctuation`/`language_switch`/`speaker_change`/`null` | 문장이 어떤 로직으로 확정·분리됐는지. `null`=미확정. **additive** 필드 — 프론트에서 확정 트리거 배지 표시에 활용 가능(필수 아님) |
| `translation` | str | 번역 있을 때만 | `"Hello"` | 인라인 번역(§5). 확정+번역활성 세그먼트만 |
| `detected_language` | str | 감지됐을 때만 | `"ko"`,`"en"` | 언어 코드 |
| `lang` | str | detected_language 있을 때만 | 동일 값 | React 호환 별칭 |

> ⚠️ `text`가 없고 `speaker != -2`인 줄은 직렬화에서 빠진다([timed_objects.py:205](../whisperlivekit/timed_objects.py#L205) `line.text or line.speaker==-2`).

### 2.4 기존 ↔ 신규 필드 매핑
| 기존(whisperlive SSE) | 신규(whisperlivekit WS) | 비고 |
|---|---|---|
| `content` | `lines[].text` | |
| `language` | `lines[].detected_language`(별칭 `lang`) | |
| `status:"process"/"complete"` | `lines[].finalized`(별칭 `completed`) | bool로 변경 |
| `start`(float) | `lines[].start`(str) | **타입 변경** |
| `end`(float) | `lines[].end`(str) | **타입 변경** |
| (이벤트 단위 1개) | `lines[]`(전체 배열) | 매 메시지 전체교체 |
| — | `lines[].speaker` | **신규(화자분할)** |
| 별도 `POST /api/translate` | `lines[].translation` + `buffer_translation` | 인라인화 |
| — | `buffer_transcription` | 진행중 미확정 텍스트 |

---

## 3. 화자분할(speaker / diarization) — 신규 기능

기존 `whisperlive`에 **없던 기능**이다. 서버를 `--diarization`으로 켜면 각 세그먼트에 화자 번호가 붙는다.

### 3.1 활성화
서버 플래그 `--diarization`([parse_args.py:34-39](../whisperlivekit/parse_args.py#L34-L39)), 기본 백엔드 sortformer. config 메시지에는 화자분할 여부 플래그가 따로 없으므로 **프론트는 `speaker` 값으로 다화자 여부를 추론**한다.

### 3.2 speaker 값 의미
| `speaker` | 의미 |
|---|---|
| `1,2,3,…` | 화자 번호(diar on이면 **1-base**: sortformer speaker+1, [tokens_alignment.py:200](../whisperlivekit/tokens_alignment.py#L200)) |
| `1` | diar off일 때 **모든** 세그먼트(원래 -1 → 1로 매핑, [timed_objects.py:164](../whisperlivekit/timed_objects.py#L164)) |
| `-2` | **침묵 세그먼트**(SilentSegment) — 침묵 아이콘으로 렌더 |
| `0` | (UI 한정) "화자분할 진행중" 로딩 표식([live_transcription.js:390-393](../whisperlivekit/web/live_transcription.js#L390-L393)) |

### 3.3 화자 라벨/색 (내장 UI 레퍼런스)
```js
// live_transcription.js:394-401
const speakerNum = `<span class="speaker-badge">${item.speaker}</span>`;
// + 사람 아이콘 + (선택)언어 배지(item.detected_language)
```
⚠️ **내장 UI엔 화자별 색상 매핑이 없다**(단일 `speaker-badge` 클래스). 다화자 구분색이 필요하면 **React가 `speaker` 번호→색 매핑을 직접 구현**해야 한다. 침묵(`-2`)은 silence 아이콘, diar 진행중(`0`)은 스피너로 렌더([live_transcription.js:388-393](../whisperlivekit/web/live_transcription.js#L388-L393)).

### 3.4 ⚠️ [핵심 제약] diar 모드에서 `finalized` 항상 false → 인라인 번역 미동작
- **원인**: 화자분할 경로 `get_lines_diarization()`는 세그먼트에 `finalized=True`를 **한 번도 설정하지 않는다**([tokens_alignment.py:184-214](../whisperlivekit/tokens_alignment.py#L184-L214)). 비-diar 경로만 침묵 토큰에서 `finalized=True`를 명시한다([tokens_alignment.py:242-244](../whisperlivekit/tokens_alignment.py#L242-L244)). dataclass 기본값은 `False`([timed_objects.py:127](../whisperlivekit/timed_objects.py#L127)).
- **영향 1**: diar 모드에서 `finalized`/`completed`가 신뢰 불가(항상 false).
- **영향 2**: LLM 인라인 번역이 diar 모드에서 **안 붙는다**. 번역 매니저가 `not seg.finalized`면 건너뛰기 때문([llm_translation/manager.py:38](../whisperlivekit/llm_translation/manager.py#L38)).
- **프론트 대응**: 화자분할 + 번역 동시 표시는 현재 백엔드가 지원하지 않는다(Phase 5 이후 개선 예정, [SCHEMA_CHANGES.md:96-114](SCHEMA_CHANGES.md)). 번역 UI는 diar OFF 운용을 전제하거나, 백엔드 보강 전까지 diar 모드에서 번역 영역을 비활성 처리.

---

## 4. 오디오 송신 (클라이언트 → 서버)

`config` 메시지의 `useAudioWorklet`(= 서버 `--pcm-input` 여부)로 분기한다.

### 4.1 PCM 모드 (`useAudioWorklet === true`, 서버 `--pcm-input`)
1. AudioWorklet `pcm-forwarder` 로드([live_transcription.js:573-579](../whisperlivekit/web/live_transcription.js#L573-L579)).
2. `pcm_worklet.js`: 마이크 mono Float32를 메인스레드로 postMessage([pcm_worklet.js:1-16](../whisperlivekit/web/pcm_worklet.js#L1-L16)).
3. `recorder_worker.js`: 네이티브 SR→**16kHz 리샘플**, **s16le(Int16 little-endian) PCM** 변환, 0.5초 단위 ArrayBuffer 전송([recorder_worker.js:26-92](../whisperlivekit/web/recorder_worker.js#L26-L92), `view.setInt16(..., true)`).
4. 워커 출력 ArrayBuffer를 그대로 `websocket.send`([live_transcription.js:589-593](../whisperlivekit/web/live_transcription.js#L589-L593)).

### 4.2 WebM 모드 (`useAudioWorklet === false`, 기본)
`MediaRecorder(stream, {mimeType:"audio/webm"})`, 100ms 청크마다 Blob을 `websocket.send`([live_transcription.js:606-619](../whisperlivekit/web/live_transcription.js#L606-L619)). 서버가 FFmpeg로 디코딩.

### 4.3 React 주의
- 폐쇄망 운용이 `--pcm-input`이면 React도 **AudioWorklet+Worker(16kHz/s16le 변환)를 미러링** 해야 한다 — `pcm_worklet.js`/`recorder_worker.js` 로직을 그대로 포팅 권장. AudioWorklet 미지원 브라우저에선 throw.
- 마이크는 `autoGainControl/noiseSuppression/echoCancellation` 전부 false로 getUserMedia([live_transcription.js:561-563](../whisperlivekit/web/live_transcription.js#L561-L563)).
- 종료 프레임 `new ArrayBuffer(0)`은 두 모드 공통.

---

## 5. 번역(translation) 전달

- **세그먼트별 확정 번역**: `lines[].translation`(str). 조건: 번역 활성 + 해당 세그먼트 `finalized=true`. LLM 경로는 캐시 히트 시 채워지고, 미스면 비차단 task 생성 후 **다음 스냅샷부터** 채워진다([llm_translation/manager.py:35-50](../whisperlivekit/llm_translation/manager.py#L35-L50)).
- **진행중 번역**: 최상위 `buffer_translation`(str) — 마지막 줄에 "진행중" 스타일로([live_transcription.js:440-445](../whisperlivekit/web/live_transcription.js#L440-L445)).
- ⚠️ **diar 모드 제약**: §3.4대로 화자분할 ON이면 인라인 번역이 안 붙는다.

---

## 6. (선택) 증분 프로토콜 `?mode=diff`

`/asr?mode=diff`로 연결하면 full 스냅샷 대신 증분을 받는다: 첫 메시지 `{"type":"snapshot","seq":1, ...}`, 이후 `{"type":"diff","seq":N,"new_lines":[...],"lines_pruned":k, ...}`([diff_protocol.py](../whisperlivekit/diff_protocol.py)). **내장 UI는 이를 무시**([live_transcription.js:278-281](../whisperlivekit/web/live_transcription.js#L278-L281))하므로 React도 **full 모드로 시작 권장**. 대역폭 최적화가 꼭 필요할 때만 고려.

---

## 7. React 측 변경 체크리스트

- [ ] `EventSource`/`POST start|stop` 제거 → `new WebSocket(".../asr")`.
- [ ] 첫 `{"type":"config"}` 처리 → `useAudioWorklet` 분기 후 녹음 시작.
- [ ] 매 스냅샷 메시지에서 transcript **전체 교체** 렌더(append/patch 아님). `lines[]` + `buffer_transcription`(마지막 줄 미확정) 합성.
- [ ] 오디오 캡처 구현: PCM(AudioWorklet+Worker) 또는 WebM(MediaRecorder).
- [ ] 필드 타입 변경: `start`/`end`는 `"H:MM:SS.cc"` 문자열, `finalized`(=completed) bool, 언어는 `detected_language`(=lang).
- [ ] 화자 UI: `speaker` 배지/색 직접 구현, `-2`=침묵, `0`=diar 진행중, `buffer_diarization` 표시.
- [ ] 종료: `send(new ArrayBuffer(0))` → `ready_to_stop` 수신 → `close()`.
- [ ] 번역 표시: 인라인 `translation` + `buffer_translation`. **diar+번역 동시 미지원** 주의(§3.4).

---

## 8. SCHEMA_CHANGES.md 대비 보강/정정 (코드 대조 결과)

대체로 정확하나 다음을 보강한다:
1. **`error` 최상위 필드**: `status:"error"` 동반 `error`(str) 설명 추가 필요.
2. **`speaker === -2`(침묵)·`speaker === 0`(diar 진행중)** 특수값: 문서는 "미사용 시 1"만 언급 — 렌더에 필수.
3. **`?mode=diff`** 증분 프로토콜 존재(문서엔 없음).
4. **`?language=` 쿼리**로 세션별 언어 강제 가능(문서엔 없음).
5. 화자분할 finalized=false / 인라인 번역 미동작 제약은 SCHEMA_CHANGES §6과 코드가 **정확히 일치**(신뢰 가능).
