/**
 * @fileoverview 관리자 창 ↔ 실시간 화면 창 명령 브리지 (BroadcastChannel).
 *
 * 관리자 페이지는 `/admin` 별도 라우트라 실시간 전사를 전혀 모른다. 그런데 "몇 번 블록"이라는
 * 지목은 **화면 상태**여서 서버가 해석할 수 없다 — 서버엔 진행 중 세션을 찾아갈 경로가 없고,
 * 일시중단→재개하면 새 세션이라 서버의 줄 번호와 화면의 번호가 어긋난다. 그래서 번호 해석은
 * 화면 창이 하고, 관리자 창은 명령만 보낸다.
 *
 * 전제: **같은 브라우저의 다른 창**(다른 모니터). BroadcastChannel 은 같은 origin 이면 창·모니터가
 * 달라도 통하지만, 다른 PC·다른 브라우저에서는 통하지 않는다.
 *
 * 안전장치 — 화면 창이 2개면 각 창이 서로 다른 WebSocket 세션을 열어 **번호 체계가 서로 다르다**.
 * 그대로 명령을 뿌리면 두 창에서 다른 문장이 지워진다. 그래서 흐름을 둘로 나눈다:
 *   ① `queryBlock` (비파괴) — 수집 창 동안 응답한 clientId 를 세어 0개·2개 이상을 걸러낸다
 *   ② `commandBlock` (파괴) — ①에서 확인된 clientId 앞으로만 보낸다. 다른 창은 무시한다
 */

import type { TranscriptRow } from '@/utils/transcriptRows';

const CHANNEL_NAME = 'wlk-block-cmd';

/** 화면 창이 몇 개인지 세려면 첫 응답으로 확정하면 안 된다 — 이 시간 동안 전부 받는다. */
const COLLECT_MS = 700;
/** 대상이 정해진 명령의 응답 대기 상한. 화면 창은 동기로 응답하므로 여유값이다. */
const ACK_TIMEOUT_MS = 3_000;

export type BlockAction = 'query' | 'delete' | 'undo' | 'applyTranslation';

export interface BlockRequest {
  kind: 'req';
  reqId: string;
  action: BlockAction;
  /** 지정하면 이 clientId 를 가진 창만 처리한다. 파괴적 명령은 항상 지정한다. */
  targetClientId?: string;
  blockNo?: number;
  sourceText?: string;
  translation?: string;
}

/** 블록 조회 결과. 관리자 페이지 미리보기의 입력이다. */
export type QueryOutcome =
  | {
      ok: true;
      blockNo: number;
      text: string;
      start?: string;
      translation?: string;
      /** 미확정 블록은 삭제할 수 없다(확정되며 두 조각으로 갈라지면 뒤 조각이 부활한다). */
      finalized: boolean;
    }
  | { ok: false; reason: 'not_found' | 'already_deleted' };

export type AckOutcome = { ok: true } | { ok: false; reason: 'not_found' | 'not_finalized' | 'nothing_to_undo' };

export interface BlockResponse {
  kind: 'res';
  reqId: string;
  clientId: string;
  payload: QueryOutcome | AckOutcome;
}

/** 관리자 창에서 본 명령 결과. */
export type BridgeResult<T> =
  | { status: 'ok'; clientId: string; value: T }
  | { status: 'no-viewer' }
  | { status: 'multiple-viewers'; count: number };

export function isBridgeSupported(): boolean {
  return typeof BroadcastChannel !== 'undefined';
}

export function newId(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function isResponse(data: unknown, reqId: string): data is BlockResponse {
  const m = data as Partial<BlockResponse> | null | undefined;
  return Boolean(m) && m?.kind === 'res' && m?.reqId === reqId;
}

/**
 * 조회 — 수집 창 동안 응답한 화면 창을 **전부** 받아 개수를 센다.
 * 0개면 화면이 안 열려 있는 것이고, 2개 이상이면 번호 체계가 갈라져 있어 조작을 막아야 한다.
 */
export function queryBlock(blockNo: number): Promise<BridgeResult<QueryOutcome>> {
  const reqId = newId();
  const req: BlockRequest = { kind: 'req', reqId, action: 'query', blockNo };

  return new Promise((resolve) => {
    const ch = new BroadcastChannel(CHANNEL_NAME);
    const seen = new Map<string, QueryOutcome>();

    ch.onmessage = (e) => {
      if (isResponse(e.data, reqId)) seen.set(e.data.clientId, e.data.payload as QueryOutcome);
    };
    ch.postMessage(req);

    setTimeout(() => {
      ch.close();
      const ids = [...seen.keys()];
      if (ids.length === 0) return resolve({ status: 'no-viewer' });
      if (ids.length > 1) return resolve({ status: 'multiple-viewers', count: ids.length });
      return resolve({ status: 'ok', clientId: ids[0], value: seen.get(ids[0]) as QueryOutcome });
    }, COLLECT_MS);
  });
}

/** 파괴적 명령 — 조회에서 확인된 창 하나에만 보낸다. 그 창이 응답하면 즉시 끝난다. */
export function commandBlock(
  action: Exclude<BlockAction, 'query'>,
  targetClientId: string,
  payload: { blockNo?: number; sourceText?: string; translation?: string } = {},
): Promise<BridgeResult<AckOutcome>> {
  const reqId = newId();
  const req: BlockRequest = { kind: 'req', reqId, action, targetClientId, ...payload };

  return new Promise((resolve) => {
    const ch = new BroadcastChannel(CHANNEL_NAME);
    let done = false;
    const finish = (r: BridgeResult<AckOutcome>) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      ch.close();
      resolve(r);
    };

    ch.onmessage = (e) => {
      if (isResponse(e.data, reqId) && e.data.clientId === targetClientId) {
        finish({ status: 'ok', clientId: targetClientId, value: e.data.payload as AckOutcome });
      }
    };
    ch.postMessage(req);

    // 조회 직후 화면 창이 닫혔을 수 있다 — 무응답은 'no-viewer' 로 접는다.
    const timer = setTimeout(() => finish({ status: 'no-viewer' }), ACK_TIMEOUT_MS);
  });
}

/** 화면 창 쪽 리스너 등록. 반환값을 호출하면 해제된다. */
export function listenBlockCommands(
  clientId: string,
  handle: (req: BlockRequest) => QueryOutcome | AckOutcome | null,
): () => void {
  const ch = new BroadcastChannel(CHANNEL_NAME);
  ch.onmessage = (e) => {
    const req = e.data as BlockRequest | null;
    if (!req || req.kind !== 'req') return;
    // 대상이 지정된 명령은 지목된 창만 처리한다(화면 창이 둘일 때 오조작 방지).
    if (req.targetClientId && req.targetClientId !== clientId) return;
    const payload = handle(req);
    if (payload === null) return;
    const res: BlockResponse = { kind: 'res', reqId: req.reqId, clientId, payload };
    ch.postMessage(res);
  };
  return () => ch.close();
}

// ── 화면 창 쪽 판정 (순수 함수 — 단위 테스트 대상) ────────────────────────────

export interface ViewerState {
  /** 현재 화면 행. 숨긴 블록은 이미 빠져 있다(buildRows). */
  rows: readonly TranscriptRow[];
  suppressedBlockNos: ReadonlySet<number>;
  lastDeleted: number | null;
}

export type BlockEffect =
  | { type: 'delete'; blockNo: number }
  | { type: 'undo' }
  | { type: 'override'; blockNo: number; sourceText: string; translation: string };

export interface BlockDecision {
  payload: QueryOutcome | AckOutcome;
  /** 있으면 store 액션을 호출한다. 없으면 응답만 한다. */
  effect?: BlockEffect;
}

/**
 * 명령 1건에 대한 판정. 상태 변경은 하지 않고 "무엇을 응답하고 무엇을 실행할지"만 정한다.
 * (프런트에 jsdom 이 없어 컴포넌트 테스트가 불가능하므로, 판단 로직은 전부 여기에 둔다.)
 */
export function handleBlockRequest(state: ViewerState, req: BlockRequest): BlockDecision | null {
  const find = (no: number) => state.rows.find((r) => r.blockNo === no);

  switch (req.action) {
    case 'query': {
      if (req.blockNo === undefined) return null;
      if (state.suppressedBlockNos.has(req.blockNo)) {
        return { payload: { ok: false, reason: 'already_deleted' } };
      }
      const row = find(req.blockNo);
      if (!row) return { payload: { ok: false, reason: 'not_found' } };
      return {
        payload: {
          ok: true,
          blockNo: req.blockNo,
          text: row.bufferText ? `${row.text}${row.bufferText}` : row.text,
          start: row.start,
          translation: row.translation ?? row.bufferTranslation,
          finalized: row.finalized,
        },
      };
    }

    case 'delete': {
      if (req.blockNo === undefined) return null;
      // 이미 지운 블록 — 상태를 건드리지 않고 성공으로 접는다(중복 클릭 무해).
      if (state.suppressedBlockNos.has(req.blockNo)) return { payload: { ok: true } };
      const row = find(req.blockNo);
      if (!row) return { payload: { ok: false, reason: 'not_found' } };
      // 미확정 블록은 확정되며 두 세그먼트로 갈라질 수 있고, 뒤 조각은 새 번호를 받아 부활한다.
      if (!row.finalized) return { payload: { ok: false, reason: 'not_finalized' } };
      return { payload: { ok: true }, effect: { type: 'delete', blockNo: req.blockNo } };
    }

    case 'undo': {
      if (state.lastDeleted === null) return { payload: { ok: false, reason: 'nothing_to_undo' } };
      return { payload: { ok: true }, effect: { type: 'undo' } };
    }

    case 'applyTranslation': {
      if (req.blockNo === undefined || req.sourceText === undefined || req.translation === undefined) {
        return null;
      }
      if (!find(req.blockNo)) return { payload: { ok: false, reason: 'not_found' } };
      return {
        payload: { ok: true },
        effect: {
          type: 'override',
          blockNo: req.blockNo,
          sourceText: req.sourceText,
          translation: req.translation,
        },
      };
    }

    default:
      return null;
  }
}
