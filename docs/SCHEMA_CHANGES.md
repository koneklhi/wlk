# 스키마 변경점 명세 — 프론트엔드 개발자 인계용

## 개요

기존 `whisperlive`(SSE) → `whisperlivekit`(WebSocket) 전환에 따른 통신 계약 변경 사항.
React UI 연결 시 이 문서를 기준으로 수정 범위를 결정한다.

---

## 1. 전송 방식 변경

| 항목 | 기존 (whisperlive) | 신규 (whisperlivekit) |
|------|-------------------|----------------------|
| 프로토콜 | SSE (`GET /api/recordings`, `text/event-stream`) | WebSocket (`ws://host:port/asr`) |
| 전송 모델 | 이벤트 단위 — 세그먼트 하나가 바뀔 때 해당 세그먼트만 전송 | 전체 상태 스냅샷 — 매 사이클(~50ms) 전체 `lines[]` 전송. React는 매 메시지를 전체 transcript의 완전 교체로 처리해야 함 |
| 연결 개시/종료 | `GET /api/recordings/start`, `/stop` REST 호출 | WebSocket 연결 개시(= 녹음 시작), 빈 프레임 `ArrayBuffer(0)` 전송(= 녹음 종료) |
| 번역 | 별도 `POST /api/translate` SSE | `lines[]` 내 각 세그먼트의 `translation` 필드에 인라인 포함 |

---

## 2. 세그먼트 필드 매핑

기존 SSE 이벤트 페이로드: `data: {"content": str, "language": str, "status": str}`

신규 WebSocket 메시지 전체 구조:
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

**권장 = 전체 교체 렌더**: `lines[]`는 세션 전체 히스토리를 무제한 유지·전량 재전송(§1 표·§6)하므로, 매 스냅샷
`lines[]`를 통째로 다시 그리기만 하면 ①②가 자동으로 맞춰진다 — 확정 줄을 직접 누적할 필요가 없다.

**클라이언트 누적을 굳이 한다면(선택) — 키는 반드시 `id`:**
- ❌ **`start`+`end`+`speaker` 복합키 금지** — `end`가 자라면 매번 "새 항목"으로 취급돼 같은 문장의 절단판들이
  화면에 누적(growing-prefix 중복 표시)된다. *(과거 이 문서·API_SPEC이 복합키를 권장했으나 이 버그의 직접 원인이라 폐기)*
- ❌ **`start` 단독 키도 부적합** — `start`/`end`는 1초 해상도 벽시계 문자열이라 같은 초에 시작한 서로 다른
  세그먼트(특히 다화자)가 충돌한다.
- ✅ **`id` 단독 키** — `end`가 자라거나 재개방돼도 불변, float라 같은-초 충돌 없음. `id`로 upsert + **진행중 줄 우선**
  (같은 `id`의 이전 확정판보다 `finalized:false` 줄을 우선 렌더 → 재개방 시 stale 확정판 가림).
  `status:"no_audio_detected"`(빈 `lines[]`)에서 누적을 비우지 말 것.

> 내장 테스트 UI(`whisperlivekit/web/live_transcription.js`)가 `id` 누적 방식의 참조 구현이다. 배포 React는 전체 교체
> 렌더만 해도 충분하며, React key는 `id`를 쓰면 `end` 성장 시 불필요한 remount를 막는다.

### 비확정 텍스트 처리
기존: 동일 세그먼트를 `status:"process"`로 반복 전송 → React가 갱신 판단
신규: `lines[]`는 확정 세그먼트들, `buffer_transcription`은 아직 확정 안 된 진행중 텍스트.
React는 `buffer_transcription`을 마지막 줄에 `"진행중"` 스타일로 표시해야 함.

`buffer_translation`(str)은 **LLM 번역기(`TranslationManager.apply_interim_translation()`)가 채우는 진행중
번역**이다 — 아직 확정되지 않은 마지막 진행중 문장(`lines[]`의 `finalized:false` 항목)에 대응하는 번역이
필요할 때 이 필드가 대신 채워진다. 번역 비활성(`--llm-translation` OFF)이면 항상 `""`.

---

## 3. 연결 초기화 메시지 (WebSocket)

서버가 연결 직후 1회 전송:
```json
{"type": "config", "useAudioWorklet": bool, "mode": "full", "language": "auto"}
```
- `useAudioWorklet: true` → PCM s16le AudioWorklet으로 오디오 송신
- `useAudioWorklet: false` → WebM MediaRecorder로 송신
- `language`(str) — **신설(2026-07-17, 응답 config 메시지에 필드 추가. 요청 스키마가 아니라 서버→클라이언트
  응답 필드. 하위호환 — 기존 필드 불변, 추가만)**: 그 세션에 실제 적용된 소스 언어(`auto`/`ko`/`en`). 세션이
  `?language=` 쿼리파라미터로 언어를 지정했으면 그 값, 미지정이면 서버 전역 `--lan`(`config.lan`, 기본 `auto`).
  React는 무시해도 되는 additive 필드지만, 세션 언어가 의도대로 걸렸는지 확인용으로 읽을 수 있다.
- 서버 종료 신호: `{"type": "ready_to_stop"}`

---

## 4. REST API 변경 사항

### 유지되는 엔드포인트
- `GET /api/corrections` — 단어 교정 사전 조회
- `POST /api/corrections` — 단어 추가 (body: `{"wrong_word": str, "correct_word": str}`)
- `DELETE /api/corrections/{wrong_word}` — 단어 삭제

### 연기된 엔드포인트 (React 연결 단계에서 구현)
- `GET /api/recordings/start|stop|status` — WS 자체가 녹음 제어하므로 React 연결 시 추가

### Phase 5로 연기
- `GET/POST /api/prompts/*` — 번역 Glossary 동적 관리

---

## 5. 오디오 전송 형식

| 항목 | 기존 | 신규 |
|------|------|------|
| 형식 | 서버→클라이언트 SSE (오디오는 별도 WebSocket) | 클라이언트→서버 바이너리 WebSocket 프레임 |
| PCM 모드 | — | `--pcm-input` 서버 플래그 활성 시 s16le 16kHz 원시 PCM |
| WebM 모드 | — | PCM 미활성 시 WebM(Opus) MediaRecorder 청크 |
| 종료 신호 | REST 호출 | 빈 `ArrayBuffer(0)` 프레임 전송 |

---

## 6. 알려진 제한 사항

### 화자분리 활성 시 finalized/completed 동작

`--diarization` 플래그를 사용할 때 `Segment.finalized`(및 React 호환 별칭 `completed`)는
현재 항상 `false`로 반환된다. 화자분리 경로(`get_lines_diarization`)에서는 세그먼트 확정 신호가
별도 구현돼 있지 않기 때문이다.

**영향:**
- `completed` 필드가 화자분리 모드에서 신뢰할 수 없음
- LLM 인라인 번역이 화자분리 모드에서 동작하지 않음 (확정 세그먼트 없음)

**해결 (feat/closed-network-deploy에서 구현 완료):** `tokens_alignment.py`
`get_lines_diarization()` — 화자 전환이 발생한 세그먼트(`segments[:-1]`)에 `finalized=True`
설정. 마지막(현재 발화 중) 세그먼트는 제외. 이 수정으로 화자분리 ON 상태에서도
LLM 번역이 동작한다.
