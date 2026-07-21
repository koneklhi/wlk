/**
 * @fileoverview 화면 행 파생 단위 테스트.
 *
 * 핵심 검증 대상은 세션 경계다 — 새 세션은 id 가 0부터 다시 매겨지므로, 이전 세션 줄과
 * id 가 충돌해도 서로를 지우면 안 된다.
 */
import { describe, expect, it } from 'vitest';
import { buildRows, freezeLines, toSavePayload, type RowInput } from './transcriptRows';
import { lineKey } from './deltaProtocol';
import type { Segment, VolatileState } from '@/types/stt';

const VOLATILE: VolatileState = {
  status: 'active_transcription',
  buffer_transcription: '',
  buffer_diarization: '',
  buffer_translation: '',
  remaining_time_transcription: 0,
  remaining_time_diarization: 0,
};

function seg(id: number, text: string | null, extra: Partial<Segment> = {}): Segment {
  return { id, speaker: 1, text, start: '00:00:00', end: '00:00:01', finalized: true, ...extra };
}

function input(over: Partial<RowInput> = {}): RowInput {
  return {
    committedLines: [],
    finalizedHistory: new Map(),
    serverLines: [],
    volatile: VOLATILE,
    isFinalizing: false,
    ...over,
  };
}

const historyOf = (...segs: Segment[]) => new Map(segs.map((s) => [lineKey(s), s]));

describe('buildRows — 병합 순서', () => {
  it('committed → finalized → interim 순으로 이어붙인다', () => {
    const rows = buildRows(
      input({
        committedLines: [seg(0, '이전 세션')],
        finalizedHistory: historyOf(seg(1, '확정')),
        serverLines: [seg(2, '진행중', { finalized: false })],
      }),
    );
    expect(rows.map((r) => r.text)).toEqual(['이전 세션', '확정', '진행중']);
  });

  it('같은 id 의 interim 이 있으면 stale 확정판을 숨긴다', () => {
    // 백엔드가 확정 세그먼트를 재개방하면 두 판이 공존한다 — interim 쪽이 최신이다.
    const rows = buildRows(
      input({
        finalizedHistory: historyOf(seg(5, '옛 확정본')),
        serverLines: [seg(5, '갱신된 내용', { finalized: false })],
      }),
    );
    expect(rows.map((r) => r.text)).toEqual(['갱신된 내용']);
  });

  it('committedLines 는 interim 필터를 적용받지 않는다 (세션 간 id 충돌)', () => {
    // 새 세션은 id 가 0 부터 다시 시작한다. committed 에도 필터를 걸면
    // 우연히 id 가 겹친 이전 세션 줄이 통째로 사라진다.
    const rows = buildRows(
      input({
        committedLines: [seg(0, '이전 세션 첫 줄')],
        serverLines: [seg(0, '새 세션 첫 줄', { finalized: false })],
      }),
    );
    expect(rows.map((r) => r.text)).toEqual(['이전 세션 첫 줄', '새 세션 첫 줄']);
  });

  it('React key 가 세션 경계를 넘어 중복되지 않는다', () => {
    const rows = buildRows(
      input({
        committedLines: [seg(0, 'A'), seg(1, 'B')],
        serverLines: [seg(0, 'C', { finalized: false })],
      }),
    );
    expect(new Set(rows.map((r) => r.key)).size).toBe(rows.length);
  });

  it('미확정 줄이 여러 개면 전부 렌더한다', () => {
    // 예전 구현은 마지막 미확정 줄 1개만 그려서 나머지가 화면에서 사라졌다.
    const rows = buildRows(
      input({
        serverLines: [
          seg(1, '미확정 1', { finalized: false }),
          seg(2, '미확정 2', { finalized: false }),
        ],
      }),
    );
    expect(rows).toHaveLength(2);
  });
});

describe('buildRows — buffer 처리', () => {
  it('buffer 는 마지막 줄 꼬리에 붙고, 앞줄은 건드리지 않는다', () => {
    const rows = buildRows(
      input({
        finalizedHistory: historyOf(seg(0, '앞줄'), seg(1, '뒷줄')),
        volatile: { ...VOLATILE, buffer_transcription: ' 이어지는말' },
      }),
    );
    expect(rows[0].bufferText).toBeUndefined();
    expect(rows[1].bufferText).toBe(' 이어지는말');
    expect(rows[1].text).toBe('뒷줄'); // 본문은 그대로
  });

  it('buffer_diarization 이 buffer_transcription 앞에 온다', () => {
    // 이걸 빼면 화자분할 ON 일 때 최근 발화가 몇 초간 화면에서 증발한다.
    const rows = buildRows(
      input({
        finalizedHistory: historyOf(seg(0, '줄')),
        volatile: { ...VOLATILE, buffer_diarization: '[diar]', buffer_transcription: '[tx]' },
      }),
    );
    expect(rows[0].bufferText).toBe('[diar][tx]');
  });

  it('확정 줄이 없고 buffer 만 있으면 캐리어 행을 만든다', () => {
    // 없으면 녹음 시작 후 첫 몇 초 동안 화면이 완전히 비어 고장난 것처럼 보인다.
    const rows = buildRows(
      input({ volatile: { ...VOLATILE, buffer_transcription: '첫 발화' } }),
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].bufferText).toBe('첫 발화');
  });

  it('isFinalizing 이면 buffer 를 본문에 정착시킨다', () => {
    // 종료 순간 마지막 미확정 발화가 사라지지 않게.
    const rows = buildRows(
      input({
        finalizedHistory: historyOf(seg(0, '본문')),
        volatile: { ...VOLATILE, buffer_transcription: ' 꼬리', buffer_translation: 'tail' },
        isFinalizing: true,
      }),
    );
    expect(rows[0].text).toBe('본문 꼬리');
    expect(rows[0].translation).toBe('tail');
    expect(rows[0].bufferText).toBeUndefined();
  });

  it('아무것도 없으면 빈 목록이다 (캐리어 행을 만들지 않는다)', () => {
    expect(buildRows(input())).toHaveLength(0);
  });
});

describe('buildRows — 특수 화자 값 (기존 UI 형태 유지)', () => {
  it('침묵 구간(speaker -2)은 화면에 내보내지 않는다', () => {
    // 기존 배포 UI 도 침묵 행을 표시하지 않았다. 빈 문단을 그리면 문단 간격만큼 유령 공백이 생긴다.
    const rows = buildRows(
      input({
        finalizedHistory: historyOf(seg(0, '보이는 줄'), seg(1, null, { speaker: -2 })),
      }),
    );
    expect(rows.map((r) => r.text)).toEqual(['보이는 줄']);
  });

  it('화자 배정 대기(speaker 0)는 별도 표시 없이 일반 전사 줄로 낸다', () => {
    const rows = buildRows(
      input({ serverLines: [seg(2, '처리중', { speaker: 0, finalized: false })] }),
    );
    expect(rows.map((r) => r.text)).toEqual(['처리중']);
  });
});

describe('toSavePayload', () => {
  it('빈 줄을 제외하고, buffer 꼬리는 본문에 합친다', () => {
    const rows = buildRows(
      input({
        finalizedHistory: historyOf(seg(0, '저장될 줄'), seg(1, null, { speaker: -2 })),
        serverLines: [seg(2, '진행중', { finalized: false })],
        volatile: { ...VOLATILE, buffer_transcription: ' 꼬리' },
      }),
    );
    expect(toSavePayload(rows)).toEqual([
      { speaker: 1, text: '저장될 줄', translation: null },
      { speaker: 1, text: '진행중 꼬리', translation: null },
    ]);
  });
});

describe('freezeLines — 일시중단 시 세션 동결', () => {
  it('미확정 줄을 확정으로 굳힌다', () => {
    const out = freezeLines([seg(1, '확정본'), seg(2, '진행중', { finalized: false })], VOLATILE);
    expect(out.map((s) => [s.text, s.finalized])).toEqual([
      ['확정본', true],
      ['진행중', true],
    ]);
  });

  it('buffer 꼬리를 마지막 줄 본문에 정착시킨다', () => {
    // 이게 없으면 일시중단 직전 buffer 에만 있던 발화가 재개 순간 통째로 사라진다.
    const out = freezeLines([seg(1, '앞부분')], {
      ...VOLATILE,
      buffer_transcription: ' 뒷부분입니다.',
      buffer_translation: ' the rest.',
    });
    expect(out).toHaveLength(1);
    expect(out[0].text).toBe('앞부분 뒷부분입니다.');
    expect(out[0].translation).toBe('the rest.');
  });

  it('확정 줄이 하나도 없고 buffer 만 있으면 캐리어 줄을 만든다', () => {
    // 첫 문장이 확정되기 전에 일시중단하면 화면의 전사가 전부 buffer 뿐이다.
    const out = freezeLines([], { ...VOLATILE, buffer_transcription: '첫 문장이요' });
    expect(out.map((s) => [s.text, s.finalized])).toEqual([['첫 문장이요', true]]);
  });

  it('buffer_diarization 을 buffer_transcription 앞에 붙인다', () => {
    const out = freezeLines([], {
      ...VOLATILE,
      buffer_diarization: '화자대기 ',
      buffer_transcription: '전사꼬리',
    });
    expect(out[0].text).toBe('화자대기 전사꼬리');
  });

  it('침묵 세그먼트는 동결 대상에서 제외한다', () => {
    const out = freezeLines([seg(1, null, { speaker: -2 }), seg(2, '내용')], VOLATILE);
    expect(out.map((s) => s.text)).toEqual(['내용']);
  });

  it('아무것도 없으면 빈 배열', () => {
    expect(freezeLines([], VOLATILE)).toEqual([]);
  });
});
