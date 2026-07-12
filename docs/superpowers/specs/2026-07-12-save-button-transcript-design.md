# 저장 버튼 방식 전사 저장 — 설계

## 배경

`feat/frontend-transcript-history`(커밋 c016023, 머지 c759aad)에서 녹음 중지(`ready_to_stop`
수신) 시 누적 전사를 `/api/save-transcript`로 자동 POST해 서버 로컬 폴더(`--transcript-save-dir`,
기본 `./transcripts`)에 `.txt`로 저장하는 기능을 추가했다. 이를 항상 자동 저장이 아니라, UI의
"저장하기" 버튼을 사용자가 명시적으로 클릭했을 때만 저장하도록 변경한다.

## 범위

- 프론트엔드(`whisperlivekit/web/live_transcription.{html,js,css}`)만 변경.
- 서버 쪽 `POST /api/save-transcript` 엔드포인트([basic_server.py:401-416](../../../whisperlivekit/basic_server.py#L401-L416))는
  이미 요청 바디의 `lines`를 그대로 받아 저장하는 범용 구조라 **변경 불필요**.

## 동작 사양

- **버튼 위치**: `buttons-container` 안, `recordButton` 옆(`settingsToggle`과 나란히).
- **활성화 시점**: 언제든지 — 녹음 중이어도 그 시점까지 확정된 전사가 있으면 클릭 가능.
- **비활성 조건**: 저장할 내용(확정된 줄 + 화자 -2가 아닌 미확정 줄 중 텍스트/번역이 있는 것)이
  하나도 없으면 `disabled`.
- **클릭 동작**: 클릭 시점까지의 전체 누적 내용(`finalizedHistory` + 최신 미확정 줄)을 payload로
  구성해 `/api/save-transcript`에 POST. 성공 시 상태 텍스트에 저장 경로 표시, 실패 시 콘솔 에러 +
  상태 텍스트 안내. 요청 진행 중 버튼 일시 비활성화(중복 클릭 방지), 완료 후 재평가.
- **반복 클릭**: 한 세션 중 여러 번 클릭 가능. 매번 그 시점까지의 전체 누적 내용을 새 타임스탬프
  파일로 저장(서버 쪽 파일명 로직 그대로) — 이전 저장 이후 내용만 골라내는 diff 저장은 하지 않는다.
  같은 문장이 여러 파일에 중복 저장되는 것은 의도된 동작.
- **`ready_to_stop` 처리**: 화면 렌더 마무리(누적 히스토리 반영)만 수행하고, 더 이상 자동으로
  `/api/save-transcript`를 호출하지 않는다.

## 구현 계획

### JS (`live_transcription.js`)

1. 기존 `ready_to_stop` 핸들러 내 payload 생성 로직(현재 307-310행)을 함수로 분리:
   ```js
   function buildTranscriptPayload() {
     return [...finalizedHistory.values(), ...((lastReceivedData && lastReceivedData.lines) || []).filter((l) => !l.finalized)]
       .filter((l) => l.speaker !== -2 && (l.text || l.translation))
       .map((l) => ({ speaker: l.speaker, text: (l.text || "").trim(), translation: (l.translation || "").trim() || undefined }));
   }
   ```
2. `ready_to_stop` 핸들러에서 자동 `fetch("/api/save-transcript", ...)` 호출부(현재 311-320행) 제거.
3. 저장 버튼 클릭 핸들러 추가: `buildTranscriptPayload()` 호출 → 비어 있으면 조기 반환 → 버튼
   `disabled = true` → POST → 응답 처리(상태 텍스트 갱신) → `finally`에서 `updateSaveButtonState()`
   재호출로 버튼 상태 복원.
4. `updateSaveButtonState()` 헬퍼: `saveTranscriptButton.disabled = buildTranscriptPayload().length === 0`.
   호출 지점: `renderLinesWithBuffer()` 끝부분(매 스냅샷 렌더 후), `ready_to_stop` 핸들러 끝,
   `startRecording()`에서 `finalizedHistory.clear()` 직후.

### HTML (`live_transcription.html`)

- `buttons-container` 안에 버튼 추가:
  ```html
  <button id="saveTranscriptButton" class="settings-toggle" title="전사 저장" disabled>
      <img src="web/src/save.svg" alt="Save" />
  </button>
  ```

### CSS (`live_transcription.css`)

- `.settings-toggle:disabled` 규칙 신규 추가(흐리게 + `cursor: not-allowed`) — 기존 원형 버튼
  계열에 disabled 상태가 없었으므로 새로 정의.

### 신규 에셋

- `whisperlivekit/web/src/save.svg` — 기존 `settings.svg`와 동일한 Material Symbols 스타일
  (fill `#5f6368`)의 저장(플로피 디스크) 아이콘.

## 에러 처리

- `fetch` 실패(네트워크 오류, 서버 500 등): 콘솔에 에러 로그 + 상태 텍스트에 실패 안내. 예외를
  던지지 않고 버튼은 재평가를 통해 다시 활성화(재시도 가능).
- 빈 payload로 클릭 시도(버튼이 이론상 비활성이어야 하지만 방어적으로): 핸들러 초입에서 조기 반환,
  네트워크 요청 자체를 만들지 않는다.

## 테스트

- 기존 `pytest`(`tests/`), `ruff check` 통과 확인 — 서버 코드 변경이 없으므로 회귀 위험 낮음.
- 실제 서버 기동 후 브라우저로 수동 검증:
  1. 녹음 시작 직후(확정 줄 없음) → 저장 버튼 비활성 확인.
  2. 녹음 중 확정 줄 발생 후 → 저장 버튼 활성화 확인 → 클릭 → 서버 폴더에 `.txt` 생성 확인.
  3. 같은 세션에서 추가 발화 후 재클릭 → 새 타임스탬프 파일 추가 생성 확인(전체 누적 재저장).
  4. 녹음 중지(`ready_to_stop`) 시 자동 저장이 더 이상 발생하지 않는지 확인(저장 버튼을 누르지
     않고 중지만 했을 때 새 파일이 생기지 않아야 함).
  5. 새 녹음 시작 시 저장 버튼이 다시 비활성화되는지 확인(`finalizedHistory` 초기화 반영).

## 문서 연동

이 변경은 UI 동작 변경이며 `SaveTranscriptRequest`/`/api/save-transcript` 스키마 자체는 바뀌지
않으므로 `docs/SCHEMA_CHANGES.md` 갱신은 불필요. `docs/FRONTEND_HANDOFF.md`에 "종료 시 자동 저장"으로
기술된 부분이 있다면 "저장 버튼 클릭 시 저장"으로 정정 필요 — 구현 단계에서 확인 후 갱신한다.
