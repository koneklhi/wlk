/**
 * @fileoverview 델타 프로토콜 재구성 + 서버 메시지 판별 (순수 함수 — DOM/스토어 의존 없음).
 *
 * 정본 계약 = docs/API_SPEC.md §2.4.2, 전용 명세 = docs/DELTA_PROTOCOL_SPEC.md,
 * 서버측 구현 = whisperlivekit/diff_protocol.py,
 * 참조 구현 = whisperlivekit/web/live_transcription.js 의 DELTA_RECONSTRUCTION_BEGIN/END 블록.
 *
 * reconstructLines() 는 그 블록의 1:1 포팅이다 — 리뷰어가 양쪽을 나란히 diff 할 수 있도록
 * 일반화하지 않고 형태를 그대로 유지했다.
 */
import type {
  ConfigMessage,
  DiffMessage,
  FullState,
  Segment,
  SnapshotMessage,
} from '@/types/stt';

/** 판별된 수신 메시지. */
export type ClassifiedMessage =
  | { kind: 'config'; msg: ConfigMessage }
  | { kind: 'ready_to_stop' }
  | { kind: 'delta'; msg: SnapshotMessage | DiffMessage }
  | { kind: 'full'; msg: FullState }
  | { kind: 'unknown'; type: string };

/**
 * 수신 메시지를 종류별로 가른다.
 *
 * ⚠️ 판별 기준은 "`type` 필드가 **있는가**"가 아니라 "**값이 무엇인가**"다.
 *    full 모드 상태 메시지에는 `type` 이 아예 없고, snapshot/diff 에는 있다.
 *    "type 이 있으면 제어 메시지"로 가르면 snapshot/diff 가 제어 분기에 빠져 통째로 버려지고,
 *    서버가 delta 로 바뀌는 순간 에러 없이 화면이 백지가 된다(실제 있던 버그).
 */
export function classify(raw: unknown): ClassifiedMessage {
  const m = raw as { type?: unknown };
  if (typeof m?.type !== 'string') {
    return { kind: 'full', msg: raw as FullState };
  }
  switch (m.type) {
    case 'config':
      return { kind: 'config', msg: raw as ConfigMessage };
    case 'ready_to_stop':
      return { kind: 'ready_to_stop' };
    case 'snapshot':
    case 'diff':
      return { kind: 'delta', msg: raw as SnapshotMessage | DiffMessage };
    default:
      return { kind: 'unknown', type: m.type };
  }
}

/**
 * 이전 lines 배열과 수신 메시지로 새 lines 배열을 만든다.
 *
 * snapshot → 전체 교체. diff → ① 앞부분 prune ② 공통 prefix 계산 ③ **꼬리 교체** ④ 길이 검증.
 *
 * ⚠️ `new_lines` 는 append 대상이 **아니다**. "공통 prefix 이후의 꼬리 전체"다.
 *    백엔드는 최근 줄을 소급 수정하므로(reconcile / 침묵게이트 재개방, 대략 8초 이내)
 *    이미 보낸 줄이 갱신된 내용으로 다시 실려 온다. 그냥 이어붙이면 같은 줄의 옛 판과 새 판이
 *    함께 쌓여 전사가 조용히 중복된다 — 이 저장소의 파이썬 테스트 클라이언트가 실제로 그렇게
 *    잘못 구현돼 있었다.
 *
 * @returns desync=true 면 재구성 길이가 서버 `n_lines` 와 다르다. 자력 복구 수단이 없으므로
 *          호출측은 재연결(= 새 snapshot 수신)해야 한다.
 */
export function reconstructLines(
  prevLines: readonly Segment[],
  msg: SnapshotMessage | DiffMessage,
): { lines: Segment[]; desync: boolean } {
  if (msg.type === 'snapshot') {
    // 전체 교체 — 기존에 누적한 것은 버린다.
    return { lines: Array.isArray(msg.lines) ? msg.lines.slice() : [], desync: false };
  }
  let lines = prevLines.slice();
  if (msg.lines_pruned) {
    lines.splice(0, msg.lines_pruned); // ① 앞부분 prune
  }
  const newLines = msg.new_lines || [];
  const common = Math.max(0, (msg.n_lines || 0) - newLines.length); // ② 공통 prefix 길이
  lines = lines.slice(0, common).concat(newLines); // ③ 꼬리 교체 (append 아님!)
  return { lines, desync: lines.length !== (msg.n_lines || 0) }; // ④ 검증
}

// ── 세그먼트 유틸 ────────────────────────────────────────────────────────────

/**
 * 안정 세그먼트 키. **`id` 단독**을 쓴다 — `end`/`text` 를 섞은 복합키는 세그먼트가 자라면
 * 값이 바뀌어 같은 문장이 새 항목으로 누적된다(types/stt.ts `Segment` 주석 참조).
 */
export function lineKey(seg: Segment): string {
  return String(seg.id);
}

/** finalized / completed(별칭) 중 하나라도 true 면 확정. */
export function isFinalized(seg: Segment): boolean {
  return seg.finalized === true || seg.completed === true;
}

/** 화면에 표시할 내용이 있는 줄인가. 침묵 세그먼트는 text 가 null 이지만 표시 대상이다. */
export function isRenderable(seg: Segment): boolean {
  return Boolean(seg.text) || seg.speaker === -2;
}

/**
 * 확정 이력 Map 갱신 시 "실제로 바뀌었는가" 판정.
 * 렌더에 영향을 주는 필드만 본다 — 참조 구현의 렌더 시그니처와 같은 집합이다.
 */
export function sameSegment(a: Segment, b: Segment): boolean {
  return (
    a.text === b.text &&
    a.end === b.end &&
    a.start === b.start &&
    a.speaker === b.speaker &&
    a.translation === b.translation &&
    a.translation_pending === b.translation_pending &&
    a.finalize_trigger === b.finalize_trigger &&
    a.detected_language === b.detected_language
  );
}

/** volatile 필드 기본값. 서버가 생략한 필드를 안전하게 채운다. */
export const EMPTY_VOLATILE = {
  status: undefined,
  buffer_transcription: '',
  buffer_diarization: '',
  buffer_translation: '',
  remaining_time_transcription: 0,
  remaining_time_diarization: 0,
  error: undefined,
} as const;
