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
import { isVisible, type ClientSegment } from '@/utils/blockNumbers';
import type { FinalizeTrigger, VolatileState } from '@/types/stt';

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
  /**
   * 이 줄이 확정된 계기. 쓰임이 둘이다 — ① 화면의 확정 원인 배지(설정으로 on/off, 기본 on)
   * ② DOM `data-trigger` 속성. ②는 경로 C 자동화(`scripts/vbcable_test.py`)가 전사 txt 의
   * `[문장별 확정 트리거]` 섹션을 만드는 입력이므로 배지 표시 여부와 무관하게 항상 붙는다.
   * 배지는 반드시 `data-testid="stt-text"` 바깥에 그린다(안에 넣으면 전사 텍스트가 오염된다).
   */
  trigger: FinalizeTrigger | null;
  /** 마지막 행에만 — 아직 확정 안 된 buffer 꼬리. */
  bufferText?: string;
  /** 마지막 행에만 — 실시간 번역 buffer 꼬리. */
  bufferTranslation?: string;
  /** 화면 표시용 블록 번호. 관리자 페이지가 이 번호로 블록을 지목한다(blockNumbers.ts). */
  blockNo?: number;
}

export interface RowInput {
  /** 이전 세션(일시중단/재연결 이전)에서 동결된 확정 줄. */
  committedLines: readonly ClientSegment[];
  /** 현 세션 확정 이력. key = String(id). */
  finalizedHistory: ReadonlyMap<string, ClientSegment>;
  /** 서버-권위 lines[] 미러 (확정·미확정 모두). */
  serverLines: readonly ClientSegment[];
  volatile: VolatileState;
  /** ready_to_stop 이후 최종 렌더 — buffer 를 꼬리가 아니라 본문에 정착시킨다. */
  isFinalizing: boolean;
  /** 관리자 페이지가 숨긴 블록 번호. 생략하면 아무것도 숨기지 않는다. */
  suppressedBlockNos?: ReadonlySet<number>;
  /** 관리자 페이지 재번역 결과. key = 블록 번호. */
  translationOverrides?: ReadonlyMap<number, { sourceText: string; translation: string }>;
}

export function buildRows(inp: RowInput): TranscriptRow[] {
  const {
    committedLines,
    finalizedHistory,
    serverLines,
    volatile: v,
    isFinalizing,
    suppressedBlockNos,
    translationOverrides,
  } = inp;

  const interim = serverLines.filter((l) => !isFinalized(l) && isVisible(l));
  const interimIds = new Set(interim.map(lineKey));

  const merged: Array<{ seg: ClientSegment; era: 'past' | 'now' }> = [
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
  const carrier: Array<{ seg: ClientSegment; era: 'past' | 'now' }> =
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
    blockNo: seg.blockNo,
    // 관리자 페이지 재번역 결과가 서버 번역을 이긴다. 단 그 사이 단어교정으로 원문이 바뀌었으면
    // 더 이상 이 문장의 번역이 아니므로 폐기하고 서버 번역으로 돌아간다.
    translation: pickTranslation(seg, translationOverrides),
    start: seg.start,
    end: seg.end,
    finalized: isFinalized(seg),
    trigger: seg.finalize_trigger ?? null,
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

  // 숨김 처리는 **맨 마지막**이다. 앞에서 걸러 정렬하거나 제거하면 세 가지가 깨진다:
  //   ① buffer 꼬리가 붙는 "마지막 행"이 달라져 실시간 발화가 엉뚱한 블록에 붙는다
  //   ② 숨긴 게 없을 때의 출력이 기존과 달라져 경로 C 측정(stt-row DOM 순서 스크래핑)이 흔들린다
  //   ③ 실행취소 시 복원 위치를 따로 계산해야 한다 — 여기서 거르면 자리가 그대로 남는다
  if (!suppressedBlockNos || suppressedBlockNos.size === 0) return rows;
  return rows.filter((r) => r.blockNo === undefined || !suppressedBlockNos.has(r.blockNo));
}

/** 재번역 override 가 유효하면 그것을, 아니면 서버 번역을 돌려준다. */
function pickTranslation(
  seg: ClientSegment,
  overrides: RowInput['translationOverrides'],
): string | undefined {
  if (overrides && seg.blockNo !== undefined) {
    const ov = overrides.get(seg.blockNo);
    if (ov && ov.sourceText === (seg.text ?? '')) return ov.translation || undefined;
  }
  return seg.translation || undefined;
}

/**
 * 세션 동결 — 일시중단/재연결 직전의 화면 내용을 확정 줄 목록으로 만든다.
 *
 * `buildRows` 가 화면에 그리는 것과 **같은 내용**이 나와야 한다. 그래서 serverLines 뿐 아니라
 * `volatile` 의 buffer 꼬리까지 흡수한다 — 이게 없으면 확정 전 발화가 재개 순간 사라진다.
 * 실제로 그랬다: 첫 문장이 확정되기 전에 일시중단하면 화면이 통째로 비었고(캐리어 행만
 * 있었으므로), 확정 줄이 있어도 마지막 buffer 꼬리는 매번 날아갔다.
 */
export function freezeLines(
  serverLines: readonly ClientSegment[],
  v: VolatileState,
): ClientSegment[] {
  const frozen: ClientSegment[] = serverLines
    .filter(isVisible)
    .map((seg) => ({ ...seg, finalized: true }));

  const tail = joinText(v.buffer_diarization ?? '', v.buffer_transcription);
  const tailTranslation = (v.buffer_translation ?? '').trim();
  if (!tail && !tailTranslation) return frozen;

  const last = frozen[frozen.length - 1];
  if (last) {
    last.text = joinText(last.text ?? '', tail);
    last.translation = joinText(last.translation ?? '', tailTranslation) || undefined;
    return frozen;
  }
  // 확정 줄이 하나도 없다 = 화면엔 캐리어 행 + buffer 뿐이었다. 그 내용을 담을 줄을 만든다.
  // id 는 buildRows 의 캐리어와 같은 규약(null)을 쓴다 — committedLines 는 순번으로 키를 만든다.
  frozen.push({
    id: null,
    speaker: 1,
    text: tail,
    translation: tailTranslation || undefined,
    start: '',
    end: '',
    finalized: true,
  });
  return frozen;
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
