/**
 * @fileoverview 블록 명령 판정 단위 테스트.
 *
 * 화면 창이 관리자 창의 명령을 어떻게 해석하는지가 전부 여기 있다 — 프런트에 jsdom 이 없어
 * 컴포넌트 경로를 테스트할 수 없으므로, 판단은 순수 함수로 몰아두고 여기서 잠근다.
 */
import { describe, expect, it } from 'vitest';
import { handleBlockRequest, type BlockRequest, type ViewerState } from './blockCommands';
import type { TranscriptRow } from './transcriptRows';

function row(blockNo: number, text: string, over: Partial<TranscriptRow> = {}): TranscriptRow {
  return {
    key: `s:${blockNo}`,
    id: blockNo,
    speaker: 1,
    text,
    start: '00:00:0' + blockNo,
    end: '00:00:09',
    finalized: true,
    trigger: null,
    blockNo,
    ...over,
  };
}

function state(over: Partial<ViewerState> = {}): ViewerState {
  return {
    rows: [row(1, '가'), row(2, '나')],
    suppressedBlockNos: new Set(),
    lastDeleted: null,
    ...over,
  };
}

const req = (action: BlockRequest['action'], extra: Partial<BlockRequest> = {}): BlockRequest => ({
  kind: 'req',
  reqId: 'r1',
  action,
  ...extra,
});

describe('query', () => {
  it('블록을 찾으면 원문·시각·확정여부를 돌려준다', () => {
    const d = handleBlockRequest(state(), req('query', { blockNo: 2 }));
    expect(d?.payload).toEqual({
      ok: true,
      blockNo: 2,
      text: '나',
      start: '00:00:02',
      translation: undefined,
      finalized: true,
    });
    expect(d?.effect).toBeUndefined();
  });

  it('미확정 블록은 buffer 꼬리까지 합쳐 보여준다', () => {
    const d = handleBlockRequest(
      state({ rows: [row(1, '자라는', { finalized: false, bufferText: ' 중' })] }),
      req('query', { blockNo: 1 }),
    );
    expect(d?.payload).toMatchObject({ ok: true, text: '자라는 중', finalized: false });
  });

  it('없는 번호는 not_found 다', () => {
    expect(handleBlockRequest(state(), req('query', { blockNo: 9 }))?.payload).toEqual({
      ok: false,
      reason: 'not_found',
    });
  });

  it('이미 지운 번호는 already_deleted 로 구분한다 — 실행취소를 안내하기 위함', () => {
    const s = state({ rows: [row(1, '가')], suppressedBlockNos: new Set([2]) });
    expect(handleBlockRequest(s, req('query', { blockNo: 2 }))?.payload).toEqual({
      ok: false,
      reason: 'already_deleted',
    });
  });

  it('번호가 없는 요청은 무시한다', () => {
    expect(handleBlockRequest(state(), req('query'))).toBeNull();
  });
});

describe('delete', () => {
  it('확정 블록은 삭제 효과를 낸다', () => {
    const d = handleBlockRequest(state(), req('delete', { blockNo: 1 }));
    expect(d?.payload).toEqual({ ok: true });
    expect(d?.effect).toEqual({ type: 'delete', blockNo: 1 });
  });

  it('미확정 블록은 거부한다 — 확정되며 갈라지면 뒤 조각이 새 번호로 부활한다', () => {
    const s = state({ rows: [row(1, '자라는 중', { finalized: false })] });
    const d = handleBlockRequest(s, req('delete', { blockNo: 1 }));
    expect(d?.payload).toEqual({ ok: false, reason: 'not_finalized' });
    expect(d?.effect).toBeUndefined();
  });

  it('없는 번호는 거부한다', () => {
    expect(handleBlockRequest(state(), req('delete', { blockNo: 9 }))?.payload).toEqual({
      ok: false,
      reason: 'not_found',
    });
  });

  it('이미 지운 번호는 상태를 건드리지 않고 성공으로 접는다(중복 클릭 무해)', () => {
    const s = state({ suppressedBlockNos: new Set([1]) });
    const d = handleBlockRequest(s, req('delete', { blockNo: 1 }));
    expect(d?.payload).toEqual({ ok: true });
    expect(d?.effect).toBeUndefined();
  });
});

describe('undo', () => {
  it('되돌릴 게 있으면 undo 효과를 낸다', () => {
    const d = handleBlockRequest(state({ lastDeleted: 4 }), req('undo'));
    expect(d?.effect).toEqual({ type: 'undo' });
  });

  it('되돌릴 게 없으면 알린다', () => {
    expect(handleBlockRequest(state(), req('undo'))?.payload).toEqual({
      ok: false,
      reason: 'nothing_to_undo',
    });
  });
});

describe('applyTranslation', () => {
  it('원문과 번역을 함께 실어 override 효과를 낸다', () => {
    const d = handleBlockRequest(
      state(),
      req('applyTranslation', { blockNo: 2, sourceText: '나', translation: 'Me' }),
    );
    expect(d?.effect).toEqual({ type: 'override', blockNo: 2, sourceText: '나', translation: 'Me' });
  });

  it('지워졌거나 없는 블록에는 붙이지 않는다', () => {
    const d = handleBlockRequest(
      state({ rows: [row(1, '가')] }),
      req('applyTranslation', { blockNo: 2, sourceText: '나', translation: 'Me' }),
    );
    expect(d?.payload).toEqual({ ok: false, reason: 'not_found' });
  });

  it('인자가 빠지면 무시한다', () => {
    expect(handleBlockRequest(state(), req('applyTranslation', { blockNo: 2 }))).toBeNull();
  });
});
