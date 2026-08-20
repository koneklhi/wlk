# 스키마 변경점 명세 — React ↔ 백엔드 계약 이력

## 개요

기존 `whisperlive`(SSE) → `whisperlivekit`(WebSocket) 전환에 따른 통신 계약 변경 이력. React UI(배포 UI,
`frontend/app/`) 연결은 완료됐다 — 이 문서는 그 변경 이력 참조용이며, 현재 계약 정본은 [API_SPEC.md](API_SPEC.md)다.

---

## 1. 전송 방식 변경

| 항목 | 기존 (whisperlive) | 신규 (whisperlivekit) |
|------|-------------------|----------------------|
| 프로토콜 | SSE (`GET /api/recordings`, `text/event-stream`) | WebSocket (`ws://host:port/asr`) |
| 전송 모델 | 이벤트 단위 — 세그먼트 하나가 바뀔 때 해당 세그먼트만 전송 | **기본 = full**(매 사이클 전체 `lines[]` 스냅샷) — 누적 불필요. **`?mode=delta` opt-in** 시 연결 직후 `snapshot` 1회 + 이후 `diff`(바뀐 꼬리만)이며 **클라이언트가 상태를 누적해야 한다**(§1.1) |
| 연결 개시/종료 | `GET /api/recordings/start`, `/stop` REST 호출 | WebSocket 연결 개시(= 녹음 시작), 빈 프레임 `ArrayBuffer(0)` 전송(= 녹음 종료) |
| 번역 | 별도 `POST /api/translate` SSE | `lines[]` 내 각 세그먼트의 `translation` 필드에 인라인 포함 |

### 1.1 델타 전송 (`?mode=delta` opt-in)

> **왜 있나**: full 모드는 매 메시지가 전체 상태 스냅샷이라 세션이 길어질수록 WebSocket 페이로드와 전체 재렌더
> 비용이 누적 줄 수에 비례해 커진다. 델타는 매 메시지 1~2줄만 실어 이 증가를 없앤다(실측 4.7배 절감).
> **기본값은 `full`이므로 델타 미대응 클라이언트는 무수정으로 그대로 동작한다** — 델타는 명시적 opt-in이다.

- 첫 메시지: `{"type":"snapshot","seq":1, ...전체 상태(§2와 동일 필드)...}`
- 이후 메시지: `{"type":"diff","seq":N,"n_lines":M,"status":...,"buffer_*":...,"remaining_time_*":...,`
  `(선택)"lines_pruned":K,(선택)"new_lines":[<Segment>,...],(선택)"error":...}`

**`new_lines`는 append 대상이 아니다.** `new_lines`는 직전에 보낸 상태와의 **공통 prefix 이후 꼬리 전체**다.
백엔드는 최근 줄을 **소급 수정**할 수 있고(경계 재조정·침묵 게이트 재개방, 대략 8초 이내), 그러면 이미 보낸 줄이
갱신된 내용으로 `new_lines`에 다시 실린다. append 하면 같은 줄이 중복된다 — **꼬리 교체**가 정답이다.

```js
// 클라이언트 재구성 (내장 UI live_transcription.js: reconstructLines 참조 구현)
function applyMessage(lines, msg) {
  if (msg.type === "snapshot") return msg.lines.slice();          // 전체 교체
  if (msg.lines_pruned) lines.splice(0, msg.lines_pruned);        // ① 앞부분 prune
  const newLines = msg.new_lines || [];
  const common = msg.n_lines - newLines.length;                   // ② 공통 prefix 길이
  lines = lines.slice(0, common).concat(newLines);                // ③ 꼬리 교체(append 아님)
  if (lines.length !== msg.n_lines) console.warn("desync — 재연결 필요"); // ⑤ 검증
  return lines;
}
// ④ status / buffer_transcription / buffer_diarization / buffer_translation /
//    remaining_time_transcription / remaining_time_diarization / error 는 매 메시지 값으로 그대로 교체.
```

- 렌더는 **증분**으로: `common` 이전 줄은 DOM을 건드리지 않고, 꼬리만 교체한다(내장 UI `reconcileTranscriptDom` 참조).
- 재동기 방법은 **재연결뿐**이다(새 연결 = 새 `snapshot`). `n_lines` 불일치를 감지하면 재연결한다.
- 줄 dedup·React key는 여전히 **`id` 단독**(§2 "라인 dedup·렌더 규칙"). 복합키 금지.
- 서버 기본값은 `--ws-protocol {delta,full}`(기본 `full`)로 바꿀 수 있고, 쿼리파라미터 `?mode=delta|full`이
  이를 오버라이드한다(`?mode=diff`는 `delta`의 하위호환 별칭). 실제 적용값은 `config` 메시지의 `protocol` 필드로 통지된다(§3).

---

## 2. 세그먼트 필드 매핑

기존 SSE 이벤트 페이로드: `data: {"content": str, "language": str, "status": str}`

신규 WebSocket **상태 페이로드** 구조(델타 모드의 `snapshot`, full 모드의 매 메시지가 이 모양이다.
`diff` 메시지는 여기서 `lines` 대신 `n_lines`+`new_lines`만 싣는다 — §1.1):
```json
{
  "status": "active_transcription" | "no_audio_detected" | "error",
  "lines": [ <Segment>, ... ],
  "buffer_transcription": str,
  "buffer_diarization": str,
  "buffer_translation": str,
  "remaining_time_transcription": float,
  "remaining_time_diarization": float
}
```

각 `lines[]` 세그먼트 필드:
| 기존 필드 | 신규 필드 | 비고 |
|-----------|-----------|------|
| `content` | `text` | 전사 텍스트 |
| `language` | `detected_language` | 언어 코드 (`"ko"`, `"en"` 등) |
| — | `lang` | `detected_language` 와 동일 값 (React 호환 별칭) |
| `status: "process"/"complete"` | `finalized: bool` | `false`=비확정(진행중), `true`=확정 |
| — | `completed` | `finalized` 와 동일 값 (React 호환 별칭) |
| — | `speaker` | 화자 번호 (`int`). 화자분리 미사용 시 `1` |
| — | `id` | **안정 세그먼트 식별자**(`number`, 세션상대 시작초). **세그먼트를 스냅샷 간 추적하는 유일한 안정 키** — `end`가 자라거나 `finalized`가 `true→false`로 재개방돼도 불변. **React는 라인 dedup·React key에 반드시 `id`를 쓸 것**(`start\|end\|speaker` 복합키 금지 — 아래 "라인 dedup·렌더 규칙" 참조). 신설(2026-07-17, master 머지 시). |
| — | `finalize_trigger` | 문장이 **어떤 로직으로 확정·분리됐는지**(`string`\|`null`). 값: `silence`/`punctuation`/`language_switch`/`speaker_change`/`null`(미확정). React는 무시 가능한 **additive** 필드(배지 표시 등에 선택 활용). *Exp-170~: 값 집합 불변이나 `punctuation` 의미 확장 — 온점 형태소 종결이 독립적으로 문장을 분할하는 경우도 포함(기존 침묵/화자경계 세분 라벨 + 신규 독립 원인).* |
| `start` (float, 초) | `start` (str, `"HH:MM:SS"`) | **타입 변경** — float에서 포맷 문자열로. **PC 실제 벽시계 시각**(예 `"13:15:30"`) — 녹음 시작 시점(0초) 기준 경과시간이 아니라 그 세그먼트가 실제로 발화된 현재 시각. 초 단위(센티초 없음), 24시간제 |
| `end` (float, 초) | `end` (str, `"HH:MM:SS"`) | **타입 변경** — 위와 동일 |
| — | `translation` | 번역 결과 (문자열). 번역 활성 + 확정된 세그먼트에만 존재 |

> `start`/`end`는 `whisperlivekit/timed_objects.py`의 `Segment.to_dict(session_start=...)` → `format_walltime(session_start, offset)`으로 계산된다. `session_start`는 `whisperlivekit/audio_processor.py`의 `AudioProcessor.beg_loop`(첫 유효 오디오 청크 수신 시점의 `time.time()` epoch, 즉 세션/녹음 시작 시각)이며, `whisperlivekit/basic_server.py`의 `handle_websocket_results()`가 `audio_processor.beg_loop`를 읽어 매 응답마다 전달한다. `session_start`가 없으면(예: 업로드 파일 배치 처리 — `/v1/audio/transcriptions`, `/v1/listen`) 기존 경과시간 포맷(`format_time`, `"H:MM:SS.cc"`)으로 폴백한다 — 이 두 REST/WS 배치 엔드포인트는 여전히 파일 기준 경과시간을 쓰며 이번 변경의 영향을 받지 않는다.

### 라인 dedup·렌더 규칙 (중요 — 미준수 시 중복 표시 버그)

백엔드는 **문장 확정 판정을 뒤에 오는 발화 맥락에 따라 사후에 조정**한다(문법-조건부 침묵 게이트). 그 결과
같은 세그먼트가 스냅샷마다 이렇게 변할 수 있다:

1. **`end`가 자란다** — 같은 논리적 문장이 더 길어진 채 다시 전송된다(같은 `id`, 커진 `end`·`text`).
2. **확정 세그먼트가 다시 미확정(진행중)으로 재개방된다** — `finalized`가 `true`→`false`로 돌아오고
   같은 `id`로 계속 자란다(예: 스퓨리어스 온점으로 조기 확정 → 온점 철회 후 문장 계속).

**델타 프로토콜(`?mode=delta`)에서는 이 재조정이 곧 `new_lines` 꼬리 재전송으로 나타난다** — §1.1의 꼬리 교체를
그대로 수행하면 ①②가 자동으로 맞춰진다(재조정된 줄이 같은 `id`로 갱신 내용을 실어 다시 온다). full 모드(기본)에서는
매 스냅샷 `lines[]`를 통째로 다시 그리면 동일한 결과가 된다.

**클라이언트가 별도 누적 Map을 둔다면 — 키는 반드시 `id`:**
- ❌ **`start`+`end`+`speaker` 복합키 금지** — `end`가 자라면 매번 "새 항목"으로 취급돼 같은 문장의 절단판들이
  화면에 누적(growing-prefix 중복 표시)된다. *(과거 이 문서·API_SPEC이 복합키를 권장했으나 이 버그의 직접 원인이라 폐기)*
- ❌ **`start` 단독 키도 부적합** — `start`/`end`는 1초 해상도 벽시계 문자열이라 같은 초에 시작한 서로 다른
  세그먼트(특히 다화자)가 충돌한다.
- ✅ **`id` 단독 키** — `end`가 자라거나 재개방돼도 불변, float라 같은-초 충돌 없음. `id`로 upsert + **진행중 줄 우선**
  (같은 `id`의 이전 확정판보다 `finalized:false` 줄을 우선 렌더 → 재개방 시 stale 확정판 가림).
  `status:"no_audio_detected"`(빈 `lines[]`)에서 누적을 비우지 말 것.

> 내장 테스트 UI(`whisperlivekit/web/live_transcription.js`)가 델타 재구성(`reconstructLines`) + `id` 누적 +
> 증분 렌더(`reconcileTranscriptDom`)의 참조 구현이다. React key는 `id`를 쓰면 `end` 성장 시 불필요한 remount를 막는다.

### 비확정 텍스트 처리
기존: 동일 세그먼트를 `status:"process"`로 반복 전송 → React가 갱신 판단
신규: `lines[]`는 확정 세그먼트들, `buffer_transcription`은 아직 확정 안 된 진행중 텍스트.
React는 `buffer_transcription`을 마지막 줄에 `"진행중"` 스타일로 표시해야 함.

`buffer_translation`(str)은 **LLM 번역기(`TranslationManager.apply_interim_translation()`)가 채우는 진행중
번역**이다 — 아직 확정되지 않은 마지막 진행중 문장(`lines[]`의 `finalized:false` 항목)에 대응하는 번역이
필요할 때 이 필드가 대신 채워진다. 번역 비활성(`--llm-translation` OFF)이면 항상 `""`.

미리보기 번역의 발동 임계는 **문자 수가 아니라 `effective_len`(한글 가중, 기본 4.0배) 기준**이다
(`translator.effective_len`, CLI `--interim-hangul-weight`). raw 문자 수로 재면 한글이 라틴보다 정보
밀도가 높아 같은 임계에 훨씬 늦게 도달하고, 그 결과 **한→영 미리보기 번역만 늦게 뜬다**(실측: 한국어
2.2초 vs 영어 0.8초). effective 기준으로 재면 한국어(약 0.55~0.75초)가 영어(약 0.8초)보다 빨리 뜬다 —
대칭점(가중치 2.8, 양쪽 약 0.9초)에서 배포 요청(2026-08-20)에 따라 한국어를 한 단계 더 당긴 값이다.

### `lines[].translation_pending` (bool, optional)

확정됐지만 번역 왕복이 **아직 끝나지 않은** 줄에만 `true`로 실린다(`false`는 방출하지 않는다).
프론트는 이 값으로 **확정 이후에도** '번역 중…' 표시를 유지한다. 번역이 빈값으로 정착한 줄
(에코 재시도 실패 → `_MAX_FINAL_ATTEMPTS`)이나 소급 창 밖이라 재번역을 포기한 줄에는 오지 않으므로,
프론트가 영영 도착하지 않을 번역을 기다리며 로더를 영구히 남기지 않는다.

---

## 3. 연결 초기화 메시지 (WebSocket)

서버가 연결 직후 1회 전송:
```json
{"type": "config", "useAudioWorklet": bool, "protocol": "delta", "mode": "delta", "language": "auto"}
```
- `useAudioWorklet: true` → PCM s16le AudioWorklet으로 오디오 송신
- `useAudioWorklet: false` → WebM MediaRecorder로 송신
- `protocol`(str) — **신설**: 이 세션에 실제 적용된 출력 프로토콜(`"delta"`|`"full"`, §1.1). `mode`는 같은 값을 싣는
  구 클라이언트 호환 별칭이다. 클라이언트는 `protocol ?? mode`를 읽어 누적 여부를 결정하면 된다.
- `language`(str) — **신설(2026-07-17, 응답 config 메시지에 필드 추가. 요청 스키마가 아니라 서버→클라이언트
  응답 필드. 하위호환 — 기존 필드 불변, 추가만)**: 그 세션에 실제 적용된 소스 언어(`auto`/`ko`/`en`). 세션이
  `?language=` 쿼리파라미터로 언어를 지정했으면 그 값, 미지정이면 서버 전역 `--lan`(`config.lan`, 기본 `auto`).
  React는 무시해도 되는 additive 필드지만, 세션 언어가 의도대로 걸렸는지 확인용으로 읽을 수 있다.
- 서버 종료 신호: `{"type": "ready_to_stop"}`

### 세션 언어모드 선택 (클라이언트 → 서버)

배포 UI는 녹음 시작 전 사용자가 고른 **세션 언어모드**(한국어/영어/자동, CLAUDE.md §3.2)를 WebSocket 연결 시
쿼리 파라미터로 전달한다:

```
ws://host:port/asr?language=<auto|ko|en>
```

- 값은 ISO 639-1 코드 `ko`/`en` 또는 `auto`(생략 시 서버 기본값 `--lan`을 따름).
- 이 필드는 **입력(소스) 언어 지정**이며, §2의 `detected_language`/`lang`(세그먼트별 **감지된** 출력 언어)과는
  방향이 반대인 별개 필드다 — 혼동 금지.
- 세션 시작 후에는 값을 바꿀 수 없다(재연결 필요). 언어 셀렉터의 참조 구현 위치는 배포 UI
  (`frontend/app/`, `SttSettingDrawer`) — 이 문서는 계약만 기술한다.

---

## 4. REST API 변경 사항

### 유지되는 엔드포인트
- `GET /api/corrections` — 단어 교정 사전 조회
- `POST /api/corrections` — 단어 추가 (body: `{"wrong_word": str, "correct_word": str}`)
- `DELETE /api/corrections/{wrong_word}` — 단어 삭제

### 폐기된 엔드포인트 (구현 안 함)
- `GET /api/recordings/start|stop|status` — WS 연결수명주기(연결=시작, 빈 프레임=종료) 자체가 녹음
  제어를 대체해 별도 REST가 필요 없어짐.

### 구현 완료 (Phase 5)
- `GET/POST /api/prompts/*` — 번역 Glossary 동적 관리. 상세 = [API_SPEC.md](API_SPEC.md) §3.4.

---

## 5. 오디오 전송 형식

| 항목 | 기존 | 신규 |
|------|------|------|
| 형식 | 서버→클라이언트 SSE (오디오는 별도 WebSocket) | 클라이언트→서버 바이너리 WebSocket 프레임 |
| PCM 모드 | — | `--pcm-input` 서버 플래그 활성 시 s16le 16kHz 원시 PCM |
| WebM 모드 | — | PCM 미활성 시 WebM(Opus) MediaRecorder 청크 |
| 종료 신호 | REST 호출 | 빈 `ArrayBuffer(0)` 프레임 전송 |

---

## 6. 해결 이력

### 화자분리 활성 시 finalized/completed 동작 (해결 완료)

**과거 문제**: `--diarization` 플래그 사용 시 `Segment.finalized`(및 React 호환 별칭 `completed`)가
항상 `false`로 반환돼 `completed` 필드를 신뢰할 수 없고, 확정 세그먼트가 없어 LLM 인라인 번역이
화자분리 모드에서 동작하지 않았다.

**해결 (feat/closed-network-deploy에서 구현 완료):** `tokens_alignment.py`
`get_lines_diarization()` — 화자 전환이 발생한 세그먼트(`segments[:-1]`)에 `finalized=True`
설정. 마지막(현재 발화 중) 세그먼트는 제외. 이 수정으로 화자분리 ON 상태에서도
LLM 번역이 정상 동작한다(ROADMAP Phase 4 완료 상태와 일치).
