/**
 * @fileoverview 블록 관리 액션 + 번호 발급 배선 테스트.
 *
 * `beginSession` 은 `new WebSocket` 을 부르므로 node 환경에서 돌릴 수 없다. 여기서는
 * setState 로 상태를 심고 **순수 액션과 메시지 처리 경로만** 검증한다.
 * (프런트에 jsdom·testing-library 가 없다 — 컴포넌트 테스트는 애초에 불가능하다.)
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { useSttStore } from './stt.store';
import type { Segment } from '@/types/stt';

const get = () => useSttStore.getState();

/** 새 세션 직후와 같은 상태. */
function reset(): void {
  useSttStore.setState({
    phase: 'recording',
    ws: null,
    serverLines: [],
    finalizedHistory: new Map(),
    committedLines: [],
    nextBlockNo: 1,
    suppressedBlockNos: new Set(),
    translationOverrides: new Map(),
    lastDeleted: null,
  });
}

function seg(id: number, text: string, extra: Partial<Segment> = {}): Segment {
  return { id, speaker: 1, text, start: '00:00:00', end: '00:00:01', finalized: true, ...extra };
}

/** full 모드 상태 메시지(= type 필드 없음). */
const fullMessage = (lines: Segment[]) =>
  JSON.stringify({
    lines,
    status: 'active_transcription',
    buffer_transcription: '',
    buffer_diarization: '',
    buffer_translation: '',
    remaining_time_transcription: 0,
    remaining_time_diarization: 0,
  });

beforeEach(reset);

describe('deleteBlock / undoDelete', () => {
  it('삭제하면 숨김 목록에 들어가고 실행취소 대상이 된다', () => {
    get().deleteBlock(3);
    expect([...get().suppressedBlockNos]).toEqual([3]);
    expect(get().lastDeleted).toBe(3);
  });

  it('실행취소하면 숨김이 풀린다', () => {
    get().deleteBlock(3);
    get().undoDelete();
    expect(get().suppressedBlockNos.size).toBe(0);
    expect(get().lastDeleted).toBeNull();
  });

  it('연속 삭제 후 실행취소는 **최근 1건만** 되돌린다', () => {
    get().deleteBlock(3);
    get().deleteBlock(5);
    get().undoDelete();
    expect([...get().suppressedBlockNos]).toEqual([3]);
  });

  it('되돌릴 게 없으면 실행취소는 무해하다', () => {
    get().undoDelete();
    get().undoDelete();
    expect(get().suppressedBlockNos.size).toBe(0);
  });

  it('이미 지운 번호를 다시 지워도 실행취소 대상이 바뀌지 않는다', () => {
    get().deleteBlock(3);
    get().deleteBlock(5);
    get().deleteBlock(3);
    expect(get().lastDeleted).toBe(5);
  });

  it('Set 을 새로 만든다 — 참조가 같으면 화면이 갱신되지 않는다', () => {
    const before = get().suppressedBlockNos;
    get().deleteBlock(1);
    expect(get().suppressedBlockNos).not.toBe(before);
  });
});

describe('applyTranslationOverride', () => {
  it('블록 번호별로 원문과 번역을 함께 보관한다', () => {
    get().applyTranslationOverride(2, '원문', '번역');
    expect(get().translationOverrides.get(2)).toEqual({ sourceText: '원문', translation: '번역' });
  });

  it('Map 을 새로 만든다', () => {
    const before = get().translationOverrides;
    get().applyTranslationOverride(1, 'a', 'b');
    expect(get().translationOverrides).not.toBe(before);
  });
});

describe('리셋 지점', () => {
  const dirty = () => {
    get().deleteBlock(1);
    get().applyTranslationOverride(1, 'a', 'b');
    useSttStore.setState({ nextBlockNo: 438 });
  };

  const expectClean = () => {
    expect(get().nextBlockNo).toBe(1);
    expect(get().suppressedBlockNos.size).toBe(0);
    expect(get().translationOverrides.size).toBe(0);
    expect(get().lastDeleted).toBeNull();
  };

  it('resetTranscript 가 블록 상태를 전부 비운다', () => {
    dirty();
    get().resetTranscript();
    expectClean();
  });

  it("endSession('stop') 이 블록 상태를 전부 비운다", () => {
    // resetTranscript 와 별개의 set() 블록이다 — 한쪽만 고치면 조용히 새 세션으로 넘어간다.
    dirty();
    get().endSession('stop');
    expectClean();
  });
});

describe('번호 발급 배선 (handleMessage → applyState)', () => {
  it('확정 줄에 1 부터 번호를 매긴다', () => {
    get().handleMessage(fullMessage([seg(0.1, '가'), seg(1.2, '나')]));
    expect(get().serverLines.map((l) => l.blockNo)).toEqual([1, 2]);
    expect(get().nextBlockNo).toBe(3);
  });

  it('미확정 줄이 매 tick 같은 번호를 유지한다', () => {
    for (let i = 0; i < 5; i += 1) {
      get().handleMessage(fullMessage([seg(0.1, `자라는 중 ${i}`, { finalized: false })]));
    }
    expect(get().serverLines.map((l) => l.blockNo)).toEqual([1]);
    expect(get().nextBlockNo).toBe(2);
  });

  it('침묵 세그먼트는 번호를 소비하지 않는다', () => {
    get().handleMessage(
      fullMessage([seg(0.1, '가'), { ...seg(1.2, ''), speaker: -2, text: null }, seg(2.3, '나')]),
    );
    expect(get().serverLines.map((l) => l.blockNo)).toEqual([1, undefined, 2]);
  });

  it('확정 이력에도 번호가 실려 들어간다', () => {
    get().handleMessage(fullMessage([seg(0.1, '가')]));
    expect([...get().finalizedHistory.values()][0].blockNo).toBe(1);
  });
});
