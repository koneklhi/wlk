/**
 * @fileoverview 델타 프로토콜 재구성 단위 테스트.
 *
 * 여기서 잡으려는 건 docs/DELTA_PROTOCOL_SPEC.md §5 의 "가장 흔한 실수" 두 가지다:
 *   실수 1 — new_lines 를 append 해서 문장이 중복되는 것
 *   실수 2 — 복합키를 써서 같은 문장이 새 항목으로 누적되는 것
 */
import { describe, expect, it } from 'vitest';
import { classify, lineKey, reconstructLines } from './deltaProtocol';
import type { DiffMessage, Segment, SnapshotMessage, VolatileState } from '@/types/stt';

const VOLATILE: VolatileState = {
  status: 'active_transcription',
  buffer_transcription: '',
  buffer_diarization: '',
  buffer_translation: '',
  remaining_time_transcription: 0,
  remaining_time_diarization: 0,
};

function seg(id: number, text: string, extra: Partial<Segment> = {}): Segment {
  return {
    id,
    speaker: 1,
    text,
    start: '00:00:00',
    end: '00:00:01',
    finalized: true,
    ...extra,
  };
}

const diff = (m: Partial<DiffMessage> & { seq: number; n_lines: number }): DiffMessage => ({
  type: 'diff',
  ...VOLATILE,
  ...m,
});

describe('classify', () => {
  it('type 필드가 없으면 full 모드 상태 메시지다', () => {
    expect(classify({ lines: [], ...VOLATILE }).kind).toBe('full');
  });

  it('snapshot·diff 를 제어 메시지가 아니라 delta 로 가른다', () => {
    // 예전 구현은 "type 이 있으면 제어 메시지"로 갈라서 이 둘을 통째로 버렸고,
    // 서버가 delta 로 바뀌는 순간 화면이 백지가 됐다.
    expect(classify({ type: 'snapshot', seq: 1 }).kind).toBe('delta');
    expect(classify({ type: 'diff', seq: 2 }).kind).toBe('delta');
  });

  it('config·ready_to_stop 은 제어 메시지로 가른다', () => {
    expect(classify({ type: 'config', useAudioWorklet: false }).kind).toBe('config');
    expect(classify({ type: 'ready_to_stop' }).kind).toBe('ready_to_stop');
  });

  it('모르는 type 은 상태 메시지로 오해하지 않는다', () => {
    const c = classify({ type: 'something_new' });
    expect(c.kind).toBe('unknown');
  });
});

describe('reconstructLines', () => {
  it('snapshot 은 누적분을 버리고 전체 교체한다', () => {
    const prev = [seg(0, '이전 세션')];
    const msg: SnapshotMessage = {
      type: 'snapshot',
      seq: 1,
      lines: [seg(1, '새로')],
      ...VOLATILE,
    };
    const { lines, desync } = reconstructLines(prev, msg);
    expect(lines.map((l) => l.text)).toEqual(['새로']);
    expect(desync).toBe(false);
  });

  it('new_lines 는 append 가 아니라 꼬리 교체다 (실수 1)', () => {
    // 백엔드가 마지막 줄을 소급 수정해 다시 실어 보내는 상황.
    const prev = [seg(0, '첫 줄'), seg(1, '두번째 줄 절단판')];
    const msg = diff({
      seq: 2,
      n_lines: 2,
      new_lines: [seg(1, '두번째 줄 완성본')],
    });
    const { lines, desync } = reconstructLines(prev, msg);

    expect(desync).toBe(false);
    // append 였다면 3줄이 되고 '절단판'이 화면에 남아 중복됐을 것이다.
    expect(lines).toHaveLength(2);
    expect(lines.map((l) => l.text)).toEqual(['첫 줄', '두번째 줄 완성본']);
  });

  it('꼬리가 여러 줄로 늘어나는 경우도 공통 prefix 만 보존한다', () => {
    const prev = [seg(0, 'A'), seg(1, 'B')];
    const msg = diff({ seq: 3, n_lines: 4, new_lines: [seg(1, 'B+'), seg(2, 'C'), seg(3, 'D')] });
    const { lines, desync } = reconstructLines(prev, msg);
    expect(desync).toBe(false);
    expect(lines.map((l) => l.text)).toEqual(['A', 'B+', 'C', 'D']);
  });

  it('lines_pruned 는 공통 prefix 계산보다 먼저 적용된다', () => {
    const prev = [seg(0, 'A'), seg(1, 'B'), seg(2, 'C')];
    const msg = diff({ seq: 4, n_lines: 2, lines_pruned: 1, new_lines: [seg(2, 'C+')] });
    const { lines, desync } = reconstructLines(prev, msg);
    expect(desync).toBe(false);
    expect(lines.map((l) => l.text)).toEqual(['B', 'C+']);
  });

  it('new_lines 가 없으면 줄은 그대로다', () => {
    const prev = [seg(0, 'A'), seg(1, 'B')];
    const { lines, desync } = reconstructLines(prev, diff({ seq: 5, n_lines: 2 }));
    expect(lines.map((l) => l.text)).toEqual(['A', 'B']);
    expect(desync).toBe(false);
  });

  it('재구성 길이가 n_lines 와 다르면 desync 를 보고한다', () => {
    // 메시지 유실 → 클라이언트가 모르는 줄이 생긴 상황. 자력 복구 수단이 없어 재연결해야 한다.
    const prev = [seg(0, 'A')];
    const { desync } = reconstructLines(prev, diff({ seq: 9, n_lines: 5, new_lines: [seg(4, 'E')] }));
    expect(desync).toBe(true);
  });

  it('입력 배열을 변형하지 않는다', () => {
    const prev = [seg(0, 'A'), seg(1, 'B')];
    reconstructLines(prev, diff({ seq: 2, n_lines: 1, lines_pruned: 1 }));
    expect(prev).toHaveLength(2);
  });
});

describe('lineKey', () => {
  it('세그먼트가 자라도 키가 변하지 않는다 (실수 2)', () => {
    const growing = seg(3.25, '올렸', { end: '00:00:02' });
    const grown = seg(3.25, '올렸습니다', { end: '00:00:04' });
    expect(lineKey(growing)).toBe(lineKey(grown));

    // 참고: 예전 구현이 쓰던 복합키는 여기서 갈라져 같은 문장이 두 항목으로 쌓였다.
    const composite = (s: Segment) => [s.start, s.end, s.speaker].join('|');
    expect(composite(growing)).not.toBe(composite(grown));
  });
});
