/**
 * @fileoverview 서버 상태 → 화면 행 목록 파생 (순수 함수 — 단위 테스트 대상).
 *
 * 병합 순서 (참조: whisperlivekit/web/live_transcription.js 의 상태 레이어링):
 *   [ ...committedLines, ...finalizedHistory(단, interim 과 같은 id 는 숨김), ...interimLines ]
 *
 * buffer_* 는 별도 줄이 아니라 **마지막 줄의 꼬리**로 붙는다(diarization → transcription 순).
 *
 * 표시 정책: 기존 배포 UI 형태를 유지한다 — 침묵 구간(speaker === -2)은 화면에 내보내지 않고,
 * 화자 번호도 표시하지 않는다(화자분리 UI 미도입). 화자 배정 대기(speaker === 0) 줄은
 * 별도 표시 없이 일반 전사 줄로 렌더한다.
 */
import { isFinalized, lineKey } from '@/utils/deltaProtocol';
import type { Segment, VolatileState } from '@/types/stt';

export interface TranscriptRow {
  /** React key. 세션 경계 접두사 + 안정 id. 배열 index 를 쓰면 소급 수정 때 오재사용된다. */
  key: string;
  id: number | null;
  speaker: number;
  text: string;
  translation?: string;
  /** 표시용 시각 문자열. "HH:MM:SS" 또는 "H:MM:SS.cc". */
  start?: string;
  end?: string;
  finalized: boolean;
  /** 마지막 행에만 — 아직 확정 안 된 buffer 꼬리. */
  bufferText?: string;
  /** 마지막 행에만 — 실시간 번역 buffer 꼬리. */
  bufferTranslation?: string;
}

export interface RowInput {
  /** 이전 세션(일시중단/재연결 이전)에서 동결된 확정 줄. */
  committedLines: readonly Segment[];
  /** 현 세션 확정 이력. key = String(id). */
  finalizedHistory: ReadonlyMap<string, Segment>;
  /** 서버-권위 lines[] 미러 (확정·미확정 모두). */
  serverLines: readonly Segment[];
  volatile: VolatileState;
  /** ready_to_stop 이후 최종 렌더 — buffer 를 꼬리가 아니라 본문에 정착시킨다. */
  isFinalizing: boolean;
}

/** 화면에 내보낼 줄인가. 침묵 구간과 빈 줄은 제외한다(기존 UI 동작 유지). */
function isVisible(seg: Segment): boolean {
  return seg.speaker !== -2 && Boolean(seg.text);
}

export function buildRows(inp: RowInput): TranscriptRow[] {
  const { committedLines, finalizedHistory, serverLines, volatile: v, isFinalizing } = inp;

  const interim = serverLines.filter((l) => !isFinalized(l) && isVisible(l));
  const interimIds = new Set(interim.map(lineKey));

  const merged: Array<{ seg: Segment; era: 'past' | 'now' }> = [
    // 이전 세션 확정분. 새 세션은 id 가 0부터 다시 매겨지므로 **interim 필터를 적용하면 안 된다** —
    // 우연히 같은 id 를 가진 옛 줄이 통째로 숨겨진다.
    ...committedLines.filter(isVisible).map((seg) => ({ seg, era: 'past' as const })),
    // 같은 id 의 interim 이 있으면 stale 확정판을 숨긴다.
    // 백엔드가 확정 세그먼트를 재개방하면 두 판이 공존하는데, interim 쪽이 최신이다.
    ...[...finalizedHistory.values()]
      .filter((l) => isVisible(l) && !interimIds.has(lineKey(l)))
      .map((seg) => ({ seg, era: 'now' as const })),
    ...interim.map((seg) => ({ seg, era: 'now' as const })),
  ];

  // 아직 확정 줄이 없는데 buffer 만 있는 초기 구간 — 빈 캐리어 행을 만들어 buffer 를 보여준다.
  // 없으면 녹음 시작 후 첫 몇 초 동안 화면이 완전히 비어 고장난 것처럼 보인다.
  const hasBuffer = Boolean(v.buffer_transcription || v.buffer_diarization);
  const carrier: Array<{ seg: Segment; era: 'past' | 'now' }> =
    merged.length === 0 && hasBuffer
      ? [
          {
            seg: { id: null, speaker: 1, text: '', start: '', end: '', finalized: false },
            era: 'now',
          },
        ]
      : merged;

  const rows: TranscriptRow[] = carrier.map(({ seg, era }, i) => ({
    // committed 는 era + 순번을 섞어 새 세션 id 와의 충돌을 원천 차단한다.
    key: era === 'past' ? `c${i}:${lineKey(seg)}` : `s:${lineKey(seg)}`,
    id: seg.id ?? null,
    speaker: seg.speaker ?? 1,
    text: seg.text ?? '',
    translation: seg.translation || undefined,
    start: seg.start,
    end: seg.end,
    finalized: isFinalized(seg),
  }));

  const last = rows[rows.length - 1];
  if (last) {
    // buffer_diarization 을 빼먹으면 화자분할 ON 일 때 최근 발화가 몇 초간 화면에서 증발한다.
    const tail = `${v.buffer_diarization ?? ''}${v.buffer_transcription ?? ''}`;
    if (isFinalizing) {
      // 종료/일시중단 flush: 꼬리가 아니라 본문에 정착시킨다.
      // 이 처리를 빼면 종료 순간 마지막 미확정 발화가 화면에서 사라진다.
      last.text = joinText(last.text, tail);
      last.translation = joinText(last.translation ?? '', v.buffer_translation) || undefined;
    } else {
      if (tail) last.bufferText = tail;
      if (v.buffer_translation) last.bufferTranslation = v.buffer_translation;
    }
  }
  return rows;
}

/**
 * 본문 + buffer 꼬리 결합. 서버 buffer 는 선행 공백을 포함해 오는 경우가 많으므로
 * 양쪽을 trim 한 뒤 공백 하나로 잇는다.
 */
function joinText(base: string, tail?: string): string {
  const a = base.trim();
  const b = (tail ?? '').trim();
  if (!a) return b;
  if (!b) return a;
  return `${a} ${b}`;
}

/** 저장용 평탄화 (POST /api/save-transcript 의 lines[] 형식). */
export function toSavePayload(rows: readonly TranscriptRow[]) {
  return rows
    .filter((r) => r.text.trim() || r.bufferText?.trim())
    .map((r) => ({
      speaker: r.speaker,
      // buffer 는 보통 선행 공백을 포함해 온다 — 그냥 이어붙이면 이중 공백이 생긴다.
      text: joinText(r.text, r.bufferText),
      translation: r.translation ?? null,
    }));
}
