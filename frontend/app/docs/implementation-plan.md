# Implementation Plan — 저작권/보안고지, 녹음제어, 종료확인팝업

## 개요
아래 3개 작업. 모두 `SttMain` 또는 `SttSettingDrawer`에 국한된 변경.

---

## 1. 사용권리 및 주의사항 (사이드바 우측 하단)

**파일**: `SttSettingDrawer.tsx`
**위치**: "설정 초기화" 버튼 아래, 사이드바 footer 영역

```
──────────────────────────────
[설정 초기화 버튼]

© 2026 Republic of Korea Air Force.
All Right Reserved V.1.0.0

본 프로그램의 대외유출을 금하며,
본 프로그램을 활용하여 생산한
자료는 군사기밀보호법 및 국방보안
업무훈령을 준수하여 운영 바랍니다.
──────────────────────────────
```

- `text-[11px]`, `text-white/40` (secondary text)
- `border-t` 구분선으로 위 섹션과 분리
- copyright는 현재 `SttMain` 바텀툴바에 중복 있으므로 제거해야 함

---

## 2. 음성인식 3버튼 (하단 툴바)

**파일**: `SttMain.tsx`, `types/stt.ts`, `stt.store.ts`, `useAudioRecorder.ts`

### 타입 변경
- `RecordFlow` → `'idle' | 'connecting' | 'recording' | 'paused' | 'stopping'`

### Store 변경
- `setRecordFlow('paused')` 호출하는 `pauseRecording` 액션 추가
- `setRecordFlow('recording')` 호출하는 `resumeRecording` 액션 추가

### Hook 변경 (useAudioRecorder)
- `MediaRecorder.pause()` / `MediaRecorder.resume()` 지원
- `pauseRecording`, `resumeRecording` 콜백 추가

### UI (SttMain 바텀툴바)
```
[누적 라인: N]  [▶ 실행] [⏸ 일시중지] [■ 종료]      © ...
```

| 버튼 | 상태 조건 | 동작 |
|------|----------|------|
| ▶ 실행 | `idle` | `startRecording()` → `recording` |
| ⏸ 일시중지 | `recording` | `pauseRecording()` → `paused` |
| ■ 종료 | `recording` 또는 `paused` | 확인팝업 → [확인] 시 `stopRecording()` → `stopping` → `idle` |
| ✕ 취소 | 팝업 내 | 팝업 닫음, 녹음 계속 |

- `일시중지` 시 상태바: `일시중지 중 // HH:MM:SS`
- `일시중지` 시 waveform 정지
- `실행` 시 일시중지 버튼 → 일시재계 버튼으로 변경 (또는 일시중지 버튼 유지)

---

## 3. 종료 확인 팝업

**파일**: `components/ConfirmDialog.tsx` (신규)
**참조**: `SttMain.tsx`에서 상태 관리

### ConfirmDialog 컴포넌트
```tsx
function ConfirmDialog({
  open,
  title,      // "녹음 종료"
  message,    // "종료 시 번역 기록이 초기화됩니다."
  confirmText,// "확인"
  cancelText, // "취소"
  onConfirm,
  onCancel,
}: ConfirmDialogProps)
```

- 백드롭 + 중앙 팝업 (BackendErrorOverlay 스타일 참고)
- `open=true` 일 때만 렌더링
- ESC / 백드롭 클릭으로 닫을 수 있음
- 포커스 트랩은 생략 (경량 팝업)

### SttMain 연동
- `showStopConfirm` 상태 추가 (`useState`)
- [■ 종료] 버튼 클릭 시 `setShowStopConfirm(true)`
- 팝업 [확인] → `setShowStopConfirm(false)`, `stopRecording()` + `endRecording()`
- 팝업 [취소] → `setShowStopConfirm(false)`

---

## 수정 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `types/stt.ts` | `RecordFlow`에 `'paused'` 추가 |
| `stt.store.ts` | `paused` 상태, `pauseRecording`/`resumeRecording` 액션 |
| `hooks/useAudioRecorder.ts` | `pauseRecording`/`resumeRecording` 메서드 추가 |
| `components/ConfirmDialog.tsx` | **신규** — 종료 확인 팝업 |
| `components/SttMain.tsx` | 바텀툴바 리모델 (3버튼), 팝업 연동, copyright 제거 |
| `components/SttSettingDrawer.tsx` | footer에 저작권/보안고지 추가 |

## 순서
1. `types/stt.ts` → 2. `stt.store.ts` → 3. `useAudioRecorder.ts` → 4. `ConfirmDialog.tsx` → 5. `SttMain.tsx` → 6. `SttSettingDrawer.tsx`

## 영향 범위
- **최소 변경**: 6파일, 약 120 라인 추가/수정
- **호환**: 기존 기능 중단 없음. `paused` 상태는 레이어 추가.
- **리스크 낮음**: 바텀툴바 레이아웃 변경, 팝업 오버레이 추가 외 영향 없음.
