/**
 * @fileoverview 화면 행 목록 파생 훅.
 *
 * Zustand 5 는 셀렉터 결과를 자동 얕은비교하지 않는다 — 매 호출 새 배열을 만드는 셀렉터를
 * 넘기면 "getSnapshot should be cached" 무한 루프가 난다. 그래서 원시 슬라이스만 구독하고
 * 파생은 useMemo 로 한다. (store 의 finalizedHistory 는 실제 변경이 있을 때만 새 Map 을
 * 만들도록 copy-on-write 로 짜여 있어 이 useMemo 가 실제로 캐시된다.)
 */
import { useMemo } from 'react';
import { useSttStore } from '@/stores/stt.store';
import { buildRows, type RowInput, type TranscriptRow } from '@/utils/transcriptRows';

/**
 * store 스냅샷 → buildRows 입력. 훅(구독 경로)과 브리지(getState 경로)가 **같은 매핑**을 쓰도록
 * 한 곳에 둔다 — 갈라지면 관리자 페이지가 화면과 다른 블록 목록을 보게 된다.
 */
export function toRowInput(s: {
  committedLines: RowInput['committedLines'];
  finalizedHistory: RowInput['finalizedHistory'];
  serverLines: RowInput['serverLines'];
  volatile: RowInput['volatile'];
  isFinalizing: boolean;
  suppressedBlockNos: ReadonlySet<number>;
  translationOverrides: RowInput['translationOverrides'];
}): RowInput {
  return {
    committedLines: s.committedLines,
    finalizedHistory: s.finalizedHistory,
    serverLines: s.serverLines,
    volatile: s.volatile,
    isFinalizing: s.isFinalizing,
    suppressedBlockNos: s.suppressedBlockNos,
    translationOverrides: s.translationOverrides,
  };
}

export function useTranscriptRows(): TranscriptRow[] {
  const committedLines = useSttStore((s) => s.committedLines);
  const finalizedHistory = useSttStore((s) => s.finalizedHistory);
  const serverLines = useSttStore((s) => s.serverLines);
  const volatile = useSttStore((s) => s.volatile);
  const isFinalizing = useSttStore((s) => s.isFinalizing);
  const suppressedBlockNos = useSttStore((s) => s.suppressedBlockNos);
  const translationOverrides = useSttStore((s) => s.translationOverrides);

  return useMemo(
    () =>
      buildRows(
        toRowInput({
          committedLines,
          finalizedHistory,
          serverLines,
          volatile,
          isFinalizing,
          suppressedBlockNos,
          translationOverrides,
        }),
      ),
    [
      committedLines,
      finalizedHistory,
      serverLines,
      volatile,
      isFinalizing,
      suppressedBlockNos,
      translationOverrides,
    ],
  );
}
