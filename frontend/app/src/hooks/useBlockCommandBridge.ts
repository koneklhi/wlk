/**
 * @fileoverview 실시간 화면 창의 명령 수신부 — 관리자 창이 보낸 블록 명령을 처리한다.
 *
 * 이 훅은 실시간 화면(SttMain)에서 **한 번만** 마운트한다. 판정은 전부 순수 함수
 * `handleBlockRequest` 가 하고, 여기서는 store 액션 호출과 채널 수명만 관리한다.
 *
 * 상태를 구독하지 않고 `useSttStore.getState()` 로 그때그때 읽는다 — 20Hz 로 갱신되는 전사
 * 상태를 구독하면 매 tick 리스너를 다시 걸게 된다.
 */
import { useEffect } from 'react';
import { useSttStore } from '@/stores/stt.store';
import { toRowInput } from '@/hooks/useTranscriptRows';
import { buildRows } from '@/utils/transcriptRows';
import { handleBlockRequest, isBridgeSupported, listenBlockCommands, newId } from '@/utils/blockCommands';

export function useBlockCommandBridge(): void {
  useEffect(() => {
    if (!isBridgeSupported()) return;
    const clientId = newId();

    return listenBlockCommands(clientId, (req) => {
      const s = useSttStore.getState();
      const decision = handleBlockRequest(
        {
          rows: buildRows(toRowInput(s)),
          suppressedBlockNos: s.suppressedBlockNos,
          lastDeleted: s.lastDeleted,
        },
        req,
      );
      if (!decision) return null;

      const e = decision.effect;
      if (e?.type === 'delete') s.deleteBlock(e.blockNo);
      else if (e?.type === 'undo') s.undoDelete();
      else if (e?.type === 'override') s.applyTranslationOverride(e.blockNo, e.sourceText, e.translation);

      return decision.payload;
    });
  }, []);
}
