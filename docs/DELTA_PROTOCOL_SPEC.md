# 델타 전송 프로토콜 명세 — 프론트엔드 작업 지시서

> **대상**: 배포 PC React UI 담당 개발자
> **한 줄 요약**: 장시간 세션에서 전사가 점점 느려지는 문제를 없애는 **선택 기능**이다.
> 지금 코드를 안 고쳐도 기존 그대로 동작하며, 아래 작업 2개를 하면 전환된다.
> **정본 계약** = [API_SPEC.md](API_SPEC.md) §2.4.2 · **참조 구현** = `whisperlivekit/web/live_transcription.js`

---

## 1. 배경 — 무엇이 느렸나

서버는 약 50ms마다 전사 상태를 WebSocket으로 보낸다. 기존(=현재 기본) 방식은 매 메시지가
**그때까지 전사된 전체 `lines[]`** 를 담는다. 그래서 세션이 길어질수록

- 메시지 크기가 누적 줄 수에 비례해 커지고,
- 프론트는 매번 전체 목록을 다시 그린다.

둘 다 브라우저 메인 스레드에서 일어나므로, 오래 틀어둘수록 화면이 밀린다.

**실측**(ytn2, 109초, 동일 입력 재생 비교):

| | 총 전송량 | 후반 메시지 1건 |
|---|---|---|
| full (현재 기본) | 169.3 KB | ~5,576 B |
| delta | **35.9 KB** | **~562 B** |
| | **4.72배 절감** | **약 10배 절감** |

핵심은 배수가 아니라 **기울기**다. delta의 메시지당 전송 줄 수는 누적 줄 수와 무관하게 **항상 1~2줄**로
평평하다(측정 63개 메시지 중 0줄 5회 / 1줄 39회 / 2줄 14회 / 3줄 4회 / 4줄 1회). 즉 109초에서 이미
10배이고, 세션이 길어질수록 격차가 계속 벌어진다.

---

## 2. 무엇을 해야 하나 — 작업은 2개

### 작업 ① WebSocket URL에 `?mode=delta` 추가

```
ws://<host>:<port>/asr?mode=delta
```

기존 파라미터와 병용한다: `/asr?language=ko&mode=delta`

**이것만으로 서버가 델타를 보내기 시작하므로, 작업 ②를 함께 반영해야 한다.**
(파라미터를 빼면 즉시 기존 동작으로 롤백된다 — 서버 재배포 불필요.)

### 작업 ② 상태 누적 + 재구성

지금은 받은 메시지의 `lines`를 그대로 렌더할 것이다. 델타에서는 **클라이언트가 서버-권위 `lines[]` 미러를
누적 유지**해야 한다. 아래 §4 함수를 그대로 쓰면 된다.

> 그 외 필드(`Segment` 구조, `speaker`, `translation`, `buffer_*` 표시 규칙 등)는 **하나도 바뀌지 않는다.**
> 이 문서는 오직 "메시지를 어떻게 상태로 합치는가"만 다룬다.

---

## 3. 메시지 형식

### 3.1 연결 직후 — `config`

```jsonc
{"type":"config","useAudioWorklet":false,"protocol":"delta","mode":"delta","language":"auto"}
```

`protocol` 필드로 **실제 적용된** 모드를 확인할 수 있다(`"delta"` | `"full"`). 오타 등으로 잘못된 `mode` 값을
보내면 서버는 경고 로그를 남기고 기본값(`full`)으로 폴백하므로, 이 필드로 전환 성공 여부를 확인하는 것을 권장한다.

### 3.2 첫 상태 메시지 — `snapshot` (연결당 1회)

```jsonc
{"type":"snapshot","seq":1, /* ...전체 상태(기존 스키마와 동일)... */ }
```

`lines[]`를 포함한 전체 상태다. **기존 메시지와 같은 필드 구성**에 `type`·`seq`만 얹혀 있다.

### 3.3 이후 상태 메시지 — `diff`

```jsonc
{
  "type": "diff",
  "seq": 2,
  "n_lines": 17,
  "status": "active_transcription",
  "buffer_transcription": "...",
  "buffer_diarization": "",
  "buffer_translation": "",
  "remaining_time_transcription": 1.2,
  "remaining_time_diarization": 0.0,
  "lines_pruned": 0,          // 선택 — 없으면 0
  "new_lines": [ /* Segment[] */ ],  // 선택 — 없으면 변경 없음
  "error": "..."              // 선택 — status=="error"일 때만
}
```

| 필드 | 타입 | 항상? | 의미 |
|---|---|---|---|
| `seq` | number | O | 연결 단위 1부터 증가하는 순번 |
| `n_lines` | number | O | 이 메시지를 적용한 **후** 가져야 할 총 줄 수 — **검증 기준** |
| `lines_pruned` | number | ✕ | 앞에서 잘려나간 줄 수. 있으면 **가장 먼저** 앞에서 그만큼 제거 |
| `new_lines` | Segment[] | ✕ | **공통 prefix 이후의 꼬리 전체** (⚠️ append 대상 아님 — §5) |
| 나머지 | — | O | `status`·`buffer_*`·`remaining_time_*`는 **매 메시지 전체 값**이므로 그대로 덮어쓴다 |

---

## 4. 재구성 알고리즘 (복사해 쓸 것)

참조 구현 원본은 `whisperlivekit/web/live_transcription.js`의 `reconstructLines()`이며,
소스에 `>>> DELTA_RECONSTRUCTION_BEGIN` / `<<< DELTA_RECONSTRUCTION_END` 마커로 표시해 뒀다.
**DOM·전역에 의존하지 않는 순수 함수**이므로 그대로 가져다 쓸 수 있다.

```js
// 이전 lines 배열과 수신 메시지로 새 lines 배열을 만든다.
function reconstructLines(prevLines, msg) {
  if (msg.type === "snapshot") {
    // 전체 교체 — 기존에 누적한 것은 버린다.
    return { lines: Array.isArray(msg.lines) ? msg.lines.slice() : [], desync: false };
  }
  let lines = prevLines.slice();
  if (msg.lines_pruned) {
    lines.splice(0, msg.lines_pruned);              // ① 앞부분 prune
  }
  const newLines = msg.new_lines || [];
  const common = Math.max(0, (msg.n_lines || 0) - newLines.length);  // ② 공통 prefix 길이
  lines = lines.slice(0, common).concat(newLines);  // ③ 꼬리 교체 (append 아님!)
  return { lines, desync: lines.length !== (msg.n_lines || 0) };     // ④ 검증
}
```

수신 핸들러 쪽:

```js
const { lines, desync } = reconstructLines(serverLines, msg);
serverLines = lines;
if (desync) {
  // 메시지 유실 또는 오적용 — 자력 복구 수단이 없으므로 재연결한다.
  reconnect();
}
// volatile 필드는 매 메시지 값으로 그대로 교체
setState({
  status: msg.status,
  error: msg.error,
  lines: serverLines,
  buffer_transcription: msg.buffer_transcription || "",
  buffer_diarization: msg.buffer_diarization || "",
  buffer_translation: msg.buffer_translation || "",
  remaining_time_transcription: msg.remaining_time_transcription || 0,
  remaining_time_diarization: msg.remaining_time_diarization || 0,
});
```

**재연결 시 주의**: 새 연결에는 서버가 새 트래커를 붙여 `seq=1` `snapshot`부터 다시 보낸다.
따라서 **연결을 새로 열 때 누적 배열을 반드시 비운다**(안 비우면 이전 세션 줄이 남는다).

---

## 5. ⚠️ 가장 흔한 실수 2가지

### 실수 1 — `new_lines`를 append 한다 → 문장 중복

`new_lines`는 "새로 추가된 줄"이 아니라 **"공통 prefix 이후의 꼬리 전체"** 다.

백엔드는 최근 줄을 **소급 수정**한다(언어전환 경계 재조정·침묵 게이트 재개방 — 대략 8초 이내).
그러면 **이미 보낸 줄이 갱신된 내용으로 `new_lines`에 다시 실린다.** 그냥 이어붙이면 같은 줄의 옛 판과
새 판이 함께 쌓여 화면에 중복 표시된다.

> 실제로 이 저장소의 파이썬 테스트 클라이언트가 append로 잘못 구현돼 있었고, 델타를 켰을 때 전사가
> 조용히 중복되는 것을 발견해 수정했다. 반드시 **꼬리 교체**로 구현할 것.

### 실수 2 — 렌더 key를 복합키로 쓴다 → 같은 문장이 새 항목으로 누적

**렌더 key·dedup 키는 `id` 단독**을 쓴다(`id` = 안정 세그먼트 식별자, number).

```jsx
{lines.map(line => <Line key={line.id} {...line} />)}   // O
{lines.map(line => <Line key={`${line.id}-${line.text}`} .../>)}  // X
{lines.map(line => <Line key={`${line.start}-${line.end}`} .../>)} // X
```

같은 `id`의 `text`·`end`는 문장이 자라면서 **계속 바뀐다**(실측에서 마지막 두 상태 사이에 바뀐 필드 =
`text`, `end`). 복합키를 쓰면 매 갱신마다 새 항목으로 인식돼

- 같은 문장의 절단판이 쌓여 중복 표시되고,
- React가 매번 노드를 새로 만들어 **델타의 렌더 이득이 사라진다.**

`start`/`end`는 초 해상도 벽시계 문자열이라 같은 초에 여러 세그먼트가 시작될 수 있어(빠른 화자전환·
코드스위칭) 키로 부적합하다. **표시 전용**으로만 쓸 것.

---

## 6. 렌더 최적화 — React에서는 추가 작업 없음

내장 UI는 순수 JS라 DOM 증분 교체를 직접 구현해야 했지만(`reconcileTranscriptDom`),
React는 `key={line.id}`로 렌더하면 재조정이 알아서 바뀐 항목만 갱신한다. **§5 실수 2만 지키면 된다.**

장시간 세션에서 목록 자체가 길어지는 것이 부담되면 가상 스크롤을 추가로 고려할 수 있다(선택).
델타 전송 + `id` key만으로도 "앞부분을 매번 다시 그리는" 비용은 사라진다.

---

## 7. 검증 체크리스트

- [ ] `config` 메시지의 `protocol`이 `"delta"`로 온다
- [ ] 10분 이상 연속 전사에서 **중복 줄이 없다** (실수 1 검증)
- [ ] 전사 중 앞부분 줄이 사라지거나 순서가 바뀌지 않는다
- [ ] `n_lines` 불일치 경고가 뜨지 않는다 (개발 중 `console.warn`으로 찍어두면 좋다)
- [ ] 침묵 구간(`status: "no_audio_detected"`)에서 누적 상태를 **비우지 않는다** — 비우면 침묵마다 자막이 영구 소실된다
- [ ] 중지 후 재연결하면 자막이 처음부터 정상 누적된다 (연결 시 누적 배열 초기화 확인)
- [ ] 장시간 세션에서 화면 밀림이 사라졌다 (본래 목적)

---

## 8. 롤백

`?mode=delta`를 **URL에서 빼면 즉시 기존 동작**으로 돌아간다. 서버 재배포나 설정 변경이 필요 없다.
서버 기본값은 `full`이며, 모든 클라이언트가 델타를 지원하게 되면 운영자가 `--ws-protocol delta`로
기본값을 올릴 수 있다(그때는 URL 파라미터 없이도 델타가 적용된다).

---

## 9. 참고 문서

| 문서 | 내용 |
|---|---|
| [API_SPEC.md](API_SPEC.md) §2.4.2 | 델타 계약 정본 + 전체 메시지 스키마 |
| [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md) §4 | `Segment` 필드·`buffer_*` 표시·화자분할 등 전체 렌더 규칙 |
| [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) §1.1 | 기존 `whisperlive` SSE 대비 변경 이력 |
| `whisperlivekit/web/live_transcription.js` | 참조 구현(내장 UI, 실제로 `?mode=delta`로 접속) |
| `whisperlivekit/diff_protocol.py` | 서버측 구현 — 모듈 docstring에 알고리즘 명세 |
