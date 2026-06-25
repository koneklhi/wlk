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
| `start` (float, 초) | `start` (str, `"H:MM:SS.cc"`) | **타입 변경** — float에서 포맷 문자열로 |
| `end` (float, 초) | `end` (str, `"H:MM:SS.cc"`) | **타입 변경** |
| — | `translation` | 번역 결과 (문자열). 번역 활성 + 확정된 세그먼트에만 존재 |

### 비확정 텍스트 처리
기존: 동일 세그먼트를 `status:"process"`로 반복 전송 → React가 갱신 판단
신규: `lines[]`는 확정 세그먼트들, `buffer_transcription`은 아직 확정 안 된 진행중 텍스트.
React는 `buffer_transcription`을 마지막 줄에 `"진행중"` 스타일로 표시해야 함.

---

## 3. 연결 초기화 메시지 (WebSocket)

서버가 연결 직후 1회 전송:
```json
{"type": "config", "useAudioWorklet": bool, "mode": "full"}
```
- `useAudioWorklet: true` → PCM s16le AudioWorklet으로 오디오 송신
- `useAudioWorklet: false` → WebM MediaRecorder로 송신
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
