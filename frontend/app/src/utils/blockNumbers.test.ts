/**
 * @fileoverview 블록 번호 발급·승계 단위 테스트.
 *
 * 여기서 잡으려는 실패는 셋이다:
 *   ① 승계 소스를 finalizedHistory 로 잡으면 미확정 줄이 매 tick 새 번호를 받아 카운터가 폭주한다
 *      (finalizedHistory 는 정의상 확정 줄만 담는다).
 *   ② 발급 게이트를 isRenderable 로 잡으면 침묵 세그먼트(speaker -2)가 번호를 먹어,
 *      아무것도 삭제하지 않았는데 화면에 결번이 생긴다.
 *   ③ 승계를 배열 index·객체 참조로 하면 full 모드(매번 raw 배열 전체 교체)에서 전멸한다.
 */
import { describe, expect, it } from 'vitest';
import { assignBlockNos, type ClientSegment } from './blockNumbers';
import type { Segment } from '@/types/stt';

function seg(id: number | null, text: string | null, extra: Partial<Segment> = {}): Segment {
  return { id, speaker: 1, text, start: '00:00:00', end: '00:00:01', finalized: true, ...extra };
}

/** 서버가 매 tick 새로 만들어 보내는 raw 줄 — blockNo 가 붙어 있지 않다. */
const raw = (segs: Segment[]): Segment[] => segs.map((s) => ({ ...s }));

const nos = (lines: readonly ClientSegment[]) => lines.map((l) => l.blockNo);

describe('assignBlockNos — 발급', () => {
  it('처음 보는 id 에 1 부터 순차 발급한다', () => {
    const r = assignBlockNos([], [seg(0.1, '가'), seg(1.2, '나'), seg(2.3, '다')], 1);
    expect(nos(r.lines)).toEqual([1, 2, 3]);
    expect(r.nextNo).toBe(4);
  });

  it('침묵 세그먼트(speaker -2)는 번호를 소비하지 않는다', () => {
    // isRenderable 은 침묵을 통과시키지만 화면에는 안 나온다 — 번호를 주면 결번이 생긴다.
    const r = assignBlockNos(
      [],
      [seg(0.1, '가'), seg(1.2, null, { speaker: -2 }), seg(2.3, '나')],
      1,
    );
    expect(nos(r.lines)).toEqual([1, undefined, 2]);
    expect(r.nextNo).toBe(3);
  });

  it('빈 텍스트 줄은 번호를 받지 않고, 텍스트가 생기는 tick 에 받는다', () => {
    const first = assignBlockNos([], [seg(0.1, '')], 1);
    expect(nos(first.lines)).toEqual([undefined]);
    expect(first.nextNo).toBe(1);

    const second = assignBlockNos(first.lines, raw([seg(0.1, '가')]), first.nextNo);
    expect(nos(second.lines)).toEqual([1]);
  });

  it('id 가 null 인 캐리어 줄은 발급 대상이 아니다', () => {
    const r = assignBlockNos([], [{ ...seg(null, '가') }], 1);
    expect(nos(r.lines)).toEqual([undefined]);
    expect(r.nextNo).toBe(1);
  });

  it('시작 카운터를 이어받는다', () => {
    const r = assignBlockNos([], [seg(0.1, '가')], 42);
    expect(nos(r.lines)).toEqual([42]);
    expect(r.nextNo).toBe(43);
  });
});

describe('assignBlockNos — 승계', () => {
  it('미확정 줄이 매 tick 같은 번호를 유지한다', () => {
    // 회귀 방지 최우선: 승계 소스를 finalizedHistory 로 잡으면 여기서 1,2,3... 으로 폭주한다.
    let prev: ClientSegment[] = [];
    let next = 1;
    for (let i = 0; i < 5; i += 1) {
      const r = assignBlockNos(prev, raw([seg(0.1, '자라는 중', { finalized: false })]), next);
      prev = r.lines;
      next = r.nextNo;
    }
    expect(nos(prev)).toEqual([1]);
    expect(next).toBe(2);
  });

  it('full 모드처럼 매번 raw 배열이 와도 id 로 승계한다', () => {
    const a = assignBlockNos([], raw([seg(0.1, '가'), seg(1.2, '나')]), 1);
    const b = assignBlockNos(a.lines, raw([seg(0.1, '가'), seg(1.2, '나 확장'), seg(2.3, '다')]), a.nextNo);
    expect(nos(b.lines)).toEqual([1, 2, 3]);
    expect(b.nextNo).toBe(4);
  });

  it('delta 꼬리 교체 후 prefix 줄의 번호가 보존된다', () => {
    const a = assignBlockNos([], raw([seg(0.1, '가'), seg(1.2, '나')]), 1);
    // reconstructLines 는 prefix 를 같은 객체 참조로 넘긴다 — 사본 없이 그대로 통과해야 한다.
    const reconstructed = [a.lines[0], ...raw([seg(1.2, '나 수정'), seg(2.3, '다')])];
    const b = assignBlockNos(a.lines, reconstructed, a.nextNo);
    expect(nos(b.lines)).toEqual([1, 2, 3]);
    expect(b.lines[0]).toBe(a.lines[0]); // 참조 공유 유지
  });

  it('lines_pruned 로 앞이 잘려도 잔존 줄의 번호가 유지된다', () => {
    const a = assignBlockNos([], raw([seg(0.1, '가'), seg(1.2, '나'), seg(2.3, '다')]), 1);
    const b = assignBlockNos(a.lines, raw([seg(1.2, '나'), seg(2.3, '다')]), a.nextNo);
    expect(nos(b.lines)).toEqual([2, 3]);
    expect(b.nextNo).toBe(4);
  });

  it('재개방(finalized → interim)돼도 번호가 같다', () => {
    const a = assignBlockNos([], raw([seg(0.1, '가')]), 1);
    const b = assignBlockNos(a.lines, raw([seg(0.1, '가', { finalized: false })]), a.nextNo);
    expect(nos(b.lines)).toEqual([1]);
  });

  it('prevLines 가 비면(snapshot·새 세션) 전부 신규 발급하되 카운터는 이어간다', () => {
    const a = assignBlockNos([], raw([seg(0.1, '가'), seg(1.2, '나')]), 1);
    const b = assignBlockNos([], raw([seg(0.1, '새 세션 첫 줄')]), a.nextNo);
    expect(nos(b.lines)).toEqual([3]);
  });

  it('침묵 줄은 승계 대상도 아니어서 계속 번호가 없다', () => {
    const a = assignBlockNos([], raw([seg(0.1, null, { speaker: -2 })]), 1);
    const b = assignBlockNos(a.lines, raw([seg(0.1, null, { speaker: -2 })]), a.nextNo);
    expect(nos(b.lines)).toEqual([undefined]);
    expect(b.nextNo).toBe(1);
  });
});
