/**
 * @fileoverview 블록 번호 발급·승계 (순수 함수 — 단위 테스트 대상).
 *
 * 관리자 페이지에서 "몇 번 블록을 지울지"를 지목하려면 화면의 각 블록에 **안정된 번호**가
 * 있어야 한다. 서버는 이 번호를 모른다 — 일시중단→재개하면 새 세션이라 서버의 줄 번호와
 * 화면의 줄 번호가 어긋나기 때문이다. 그래서 번호는 클라이언트가 발급한다.
 *
 * 규약 두 가지:
 *   ① **번호는 세그먼트를 따라다닌다.** id→번호 영구 Map 을 두면 안 된다 — 새 세션은 id 가
 *      0부터 다시 매겨지므로(types/stt.ts `Segment`) 즉시 오배정된다. 번호를 세그먼트에
 *      심어두면 finalizedHistory → committedLines 로 옮겨가도 그대로 유지된다.
 *   ② **승계 소스는 직전 `serverLines` 다.** finalizedHistory 는 확정 줄만 담으므로
 *      (stt.store.ts `applyState`) 거기서 승계하면 미확정 줄이 매 tick(20Hz) 새 번호를
 *      받아 카운터가 폭주하고 화면 마지막 블록의 번호가 계속 바뀐다.
 *
 * 번호는 **결번을 허용한다** — 삭제해도 뒤 블록을 당기지 않는다. 한 번 읽은 번호가 계속
 * 유효해야 연속 삭제가 안전하고, 결번 자체가 "여기 지웠다"는 표시가 된다.
 */
import { lineKey } from '@/utils/deltaProtocol';
import type { Segment } from '@/types/stt';

/**
 * 서버 계약 세그먼트 + 클라이언트 전용 필드.
 *
 * `blockNo` 를 `types/stt.ts` 의 `Segment` 에 넣지 않는 이유: 그 파일은 서버
 * `timed_objects.py Segment.to_dict()` 의 미러다. 클라이언트 전용 필드를 섞으면
 * "서버가 blockNo 를 보낸다"는 오해를 만든다.
 */
export interface ClientSegment extends Segment {
  /** 화면 표시용 블록 번호(1-based). 번호를 받을 자격이 없는 줄에는 없다. */
  blockNo?: number;
}

/**
 * 화면에 내보낼 줄인가 — 침묵 구간(speaker -2)과 빈 줄은 제외한다.
 *
 * `deltaProtocol.isRenderable` 과 다르다: 그쪽은 침묵을 **통과**시킨다. 번호 발급에
 * isRenderable 을 쓰면 화면에 없는 침묵 줄이 번호를 먹어, 아무것도 삭제하지 않았는데
 * 결번이 생긴다.
 */
export function isVisible(seg: Segment): boolean {
  return seg.speaker !== -2 && Boolean(seg.text);
}

/**
 * `lines` 의 각 줄에 블록 번호를 승계하거나 새로 발급한다.
 *
 * @param prevLines 직전 `serverLines`(번호가 심어진 상태). 승계 소스.
 * @param lines     이번 tick 의 줄 목록. delta 재구성 결과라 앞부분은 prevLines 와 같은
 *                  객체 참조일 수 있고, 꼬리·full 모드는 raw 객체다.
 * @param nextNo    다음에 발급할 번호.
 */
export function assignBlockNos(
  prevLines: readonly ClientSegment[],
  lines: readonly Segment[],
  nextNo: number,
): { lines: ClientSegment[]; nextNo: number } {
  const inherited = new Map<string, number>();
  for (const p of prevLines) {
    if (p.id !== null && p.blockNo !== undefined) inherited.set(lineKey(p), p.blockNo);
  }

  let no = nextNo;
  const out = lines.map((ln) => {
    const self = ln as ClientSegment;
    // 이미 번호가 심어진 객체(= delta 꼬리 교체의 prefix)는 사본을 만들지 않는다.
    // 전량 복사하면 참조 공유가 깨져 불필요한 할당이 매 tick 발생한다.
    if (self.blockNo !== undefined) return self;
    if (ln.id === null) return self;

    const prev = inherited.get(lineKey(ln));
    if (prev !== undefined) return { ...ln, blockNo: prev };
    if (!isVisible(ln)) return self;
    return { ...ln, blockNo: no++ };
  });

  return { lines: out, nextNo: no };
}
