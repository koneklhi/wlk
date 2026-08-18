/**
 * @fileoverview 관리자 페이지 — 실시간 전사 블록 삭제 / 재번역 패널.
 *
 * 환각만 담긴 블록이 통째로 확정되거나 번역이 비는 일이 있어, 운용 중에 그 블록만 골라
 * 지우거나 다시 번역한다. 대상 지목은 실시간 화면에 표시된 **블록 번호**로 한다.
 *
 * 이 페이지는 실시간 화면과 다른 창이라 전사를 직접 갖고 있지 않다. 번호 해석은 화면 창이
 * 하고(BroadcastChannel), 여기서는 ① 조회로 대상을 확인시켜 오삭제를 막고 ② 확인 후에만
 * 파괴적 명령을 보낸다. 조회 단계에서 화면 창 개수도 함께 세어 0개·2개 이상을 걸러낸다 —
 * 창이 둘이면 각자 다른 세션이라 **번호 체계가 서로 다르다**.
 *
 * 재번역 REST 는 화면 창이 아니라 **이 창이 직접** 호출한다(조회 때 원문을 이미 받았다).
 * 그래야 브리지에 LLM 왕복만큼의 긴 대기가 생기지 않고, 화면 창이 중간에 닫혀도 부작용이 없다.
 */
import { useCallback, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { Languages, Loader2, Search, Trash2, Undo2 } from 'lucide-react';
import { toast } from 'react-toastify';
import { retranslateText } from '@/api/retranslate';
import { Input } from '@/components/ui/input';
import {
  commandBlock,
  isBridgeSupported,
  queryBlock,
  type AckOutcome,
  type BridgeResult,
  type QueryOutcome,
} from '@/utils/blockCommands';
import { cn } from '@/utils';

/** 조회로 확정된 대상. clientId 를 함께 들고 있어야 그 창에만 명령을 보낼 수 있다. */
interface Target {
  clientId: string;
  blockNo: number;
  text: string;
  start?: string;
  translation?: string;
  finalized: boolean;
}

const BTN =
  'h-9 px-4 text-sm border transition-colors flex items-center justify-center gap-1.5 disabled:opacity-30 disabled:cursor-not-allowed';

const ACK_MESSAGES: Record<string, string> = {
  not_found: '대상 블록을 찾을 수 없습니다. 번호를 다시 확인해 주세요.',
  not_finalized: '아직 확정되지 않은 블록입니다. 확정된 뒤에 삭제해 주세요.',
  nothing_to_undo: '되돌릴 삭제가 없습니다.',
};

/** 브리지 실패(화면 창 0개·2개 이상)를 알리고 실패 여부를 돌려준다. */
function reportBridgeFailure(r: BridgeResult<unknown>): boolean {
  if (r.status === 'no-viewer') {
    toast.error('실시간 화면이 열려 있지 않습니다. 같은 브라우저에서 전사 화면을 먼저 여세요.');
    return true;
  }
  if (r.status === 'multiple-viewers') {
    toast.error(
      '실시간 화면이 ' +
        r.count +
        '개 열려 있습니다. 화면마다 블록 번호가 다르므로 하나만 남기고 닫아 주세요.',
    );
    return true;
  }
  return false;
}

export function BlockControlPanel({ className }: { className?: string }) {
  const [input, setInput] = useState('');
  const [target, setTarget] = useState<Target | null>(null);
  const [busy, setBusy] = useState<null | 'query' | 'delete' | 'retranslate' | 'undo'>(null);
  const [undoable, setUndoable] = useState<number | null>(null);

  const supported = isBridgeSupported();

  const lookup = useCallback(async () => {
    const blockNo = Number(input.trim());
    if (!Number.isInteger(blockNo) || blockNo < 1) {
      toast.warn('블록 번호를 숫자로 입력해 주세요.');
      return;
    }
    setBusy('query');
    setTarget(null);
    try {
      const r = await queryBlock(blockNo);
      if (reportBridgeFailure(r)) return;
      if (r.status !== 'ok') return;
      if (!r.value.ok) {
        toast.warn(
          r.value.reason === 'already_deleted'
            ? '#' + blockNo + ' 은 이미 삭제된 블록입니다.'
            : '#' + blockNo + ' 블록을 찾을 수 없습니다.',
        );
        return;
      }
      setTarget({ clientId: r.clientId, ...r.value });
    } finally {
      setBusy(null);
    }
  }, [input]);

  /** 파괴적 명령 1건. 성공했으면 true. */
  const runCommand = useCallback(
    async (
      action: 'delete' | 'undo' | 'applyTranslation',
      clientId: string,
      payload: { blockNo?: number; sourceText?: string; translation?: string } = {},
    ): Promise<boolean> => {
      const r: BridgeResult<AckOutcome> = await commandBlock(action, clientId, payload);
      if (reportBridgeFailure(r)) return false;
      if (r.status !== 'ok') return false;
      if (!r.value.ok) {
        toast.warn(ACK_MESSAGES[r.value.reason] ?? '명령을 처리하지 못했습니다.');
        return false;
      }
      return true;
    },
    [],
  );

  const remove = useCallback(async () => {
    if (!target) return;
    setBusy('delete');
    try {
      if (await runCommand('delete', target.clientId, { blockNo: target.blockNo })) {
        toast.success('#' + target.blockNo + ' 블록을 화면에서 지웠습니다.');
        setUndoable(target.blockNo);
        setTarget(null);
        setInput('');
      }
    } finally {
      setBusy(null);
    }
  }, [target, runCommand]);

  const undo = useCallback(async () => {
    if (undoable === null) return;
    setBusy('undo');
    try {
      // 실행취소는 조회를 거치지 않으므로 여기서 화면 창을 한 번 세어 대상을 확정한다.
      const probe: BridgeResult<QueryOutcome> = await queryBlock(undoable);
      if (reportBridgeFailure(probe)) return;
      if (probe.status !== 'ok') return;
      if (await runCommand('undo', probe.clientId)) {
        toast.success('#' + undoable + ' 블록을 되살렸습니다.');
        setUndoable(null);
      }
    } finally {
      setBusy(null);
    }
  }, [undoable, runCommand]);

  const retranslate = useCallback(async () => {
    if (!target) return;
    setBusy('retranslate');
    try {
      const res = await retranslateText(target.text);
      if (res.status !== 'success' || !res.translation) {
        toast.error(res.message ?? '번역 결과를 얻지 못했습니다.');
        return;
      }
      if (res.translation === target.translation) {
        // 번역 온도가 0 이라 같은 원문 + 같은 용어집이면 결과가 같다. 버튼 고장으로 오해하지
        // 않도록 명시한다 — 결과를 바꾸려면 번역용어를 먼저 등록해야 한다.
        toast.info('번역 결과가 이전과 같습니다. 번역용어를 등록한 뒤 다시 시도해 보세요.');
        return;
      }
      const ok = await runCommand('applyTranslation', target.clientId, {
        blockNo: target.blockNo,
        sourceText: target.text,
        translation: res.translation,
      });
      if (ok) {
        toast.success('#' + target.blockNo + ' 번역을 갱신했습니다.');
        setTarget({ ...target, translation: res.translation });
      }
    } catch (e) {
      toast.error((e as Error).message || '번역 요청에 실패했습니다.');
    } finally {
      setBusy(null);
    }
  }, [target, runCommand]);

  const onKeyDown = (e: ReactKeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') void lookup();
  };

  if (!supported) {
    return (
      <div className={cn(className, 'rounded border border-dashed border-white/[0.06] p-6 text-center')}>
        <p className="text-sm text-white/30">이 브라우저에서는 블록 관리를 쓸 수 없습니다</p>
        <p className="text-xs text-white/15 mt-1">BroadcastChannel 미지원</p>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      <div className="flex items-center gap-2">
        <Trash2 size={18} className="text-white/30" />
        <h3 className="text-base font-bold text-white/80 uppercase tracking-wider">블록 관리</h3>
        <span className="text-sm text-white/25 font-normal">실시간 화면의 #번호로 지목</span>
      </div>

      <div className="flex items-center gap-2">
        <Input
          placeholder="블록 번호 (예: 7)"
          inputMode="numeric"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          className="bg-[#080808] border-white/[0.06] text-sm h-9 flex-1"
        />
        <button
          onClick={() => void lookup()}
          disabled={busy !== null}
          className={cn(BTN, 'border-white/10 text-white/50 hover:bg-white/5 hover:text-white/70 shrink-0')}
        >
          {busy === 'query' ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          조회
        </button>
      </div>

      {target && (
        <div className="rounded-lg border border-white/[0.08] bg-[#141414] px-4 py-3 flex flex-col gap-2">
          <div className="flex items-center gap-2 text-xs text-white/35 font-mono">
            <span className="text-white/60">#{target.blockNo}</span>
            {target.start && <span>{target.start}</span>}
            {!target.finalized && <span className="text-amber-400/70">미확정</span>}
          </div>
          <p className="text-base text-white/90 break-words">{target.text}</p>
          {target.translation && (
            <p className="text-sm text-[#C88C14] break-words">{target.translation}</p>
          )}

          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => void remove()}
              disabled={busy !== null || !target.finalized}
              title={target.finalized ? undefined : '확정된 블록만 삭제할 수 있습니다'}
              className={cn(BTN, 'border-red-500/20 text-red-400/80 hover:bg-red-500/10 flex-1')}
            >
              {busy === 'delete' ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              삭제
            </button>
            <button
              onClick={() => void retranslate()}
              disabled={busy !== null}
              className={cn(BTN, 'border-white/10 text-white/60 hover:bg-white/5 hover:text-white/80 flex-1')}
            >
              {busy === 'retranslate' ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Languages size={14} />
              )}
              다시 번역
            </button>
          </div>
        </div>
      )}

      {undoable !== null && (
        <button
          onClick={() => void undo()}
          disabled={busy !== null}
          className={cn(BTN, 'border-white/10 text-white/40 hover:bg-white/5 hover:text-white/70 self-start')}
        >
          {busy === 'undo' ? <Loader2 size={14} className="animate-spin" /> : <Undo2 size={14} />}
          #{undoable} 삭제 취소
        </button>
      )}
    </div>
  );
}
