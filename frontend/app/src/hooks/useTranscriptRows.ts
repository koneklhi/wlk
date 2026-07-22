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
import { buildRows, type TranscriptRow } from '@/utils/transcriptRows';

export function useTranscriptRows(): TranscriptRow[] {
  const committedLines = useSttStore((s) => s.committedLines);
  const finalizedHistory = useSttStore((s) => s.finalizedHistory);
  const serverLines = useSttStore((s) => s.serverLines);
  const volatile = useSttStore((s) => s.volatile);
  const isFinalizing = useSttStore((s) => s.isFinalizing);

  return useMemo(
    () => buildRows({ committedLines, finalizedHistory, serverLines, volatile, isFinalizing }),
    [committedLines, finalizedHistory, serverLines, volatile, isFinalizing],
  );
}
