/**
 * @fileoverview 개별 문장 렌더링 — 원문 + 번역 (stt-frontend 스타일)
 *
 * 기존 배포 UI 의 형태를 그대로 유지한다: 원문 div → (번역 대기 시)로더 → 번역 div.
 * 진행중이면서 번역이 아직 없을 때 원문을 연하게 하는 것도 기존 동작 그대로다.
 * 추가된 것은 ① 선택적 시각·확정 원인 메타 줄 ② 미확정 buffer 꼬리를 원문 뒤에 이어붙이는 것 뿐이다.
 */
import { useSttTextStyle } from '@/components/SttThemeProvider';
import { SttTranslateLoader } from '@/components/SttTranslateLoader';
import type { FinalizeTrigger } from '@/types/stt';
import type { TranscriptRow } from '@/utils/transcriptRows';
import { useState } from 'react';

/**
 * 확정 원인 배지 표기 — 내장 UI(`whisperlivekit/web/live_transcription.js` `TRIGGER_LABELS`,
 * `live_transcription.css` `.label_trigger`)와 같은 라벨·색을 쓴다. 두 UI 의 표기가 갈리면
 * 같은 전사를 보고도 서로 다른 원인을 읽게 된다 — 라벨을 바꿀 땐 양쪽을 함께 고친다
 * (동기화 규약 = docs/SENTENCE_FINALIZATION_LOGIC.md §7).
 */
const TRIGGER_LABELS: Record<FinalizeTrigger, string> = {
  silence: '침묵',
  punctuation: '종결',
  language_switch: '언어전환',
  speaker_change: '화자전환',
};

const TRIGGER_COLORS: Record<FinalizeTrigger, string> = {
  silence: '#8b9096',
  punctuation: '#4caf50',
  language_switch: '#5b9bd5',
  speaker_change: '#a586d8',
};

interface SttTextViewerProps {
  row: TranscriptRow;
  /** 시각(HH:MM:SS) 표시 여부. 설정 드로어에서 끈다. */
  showTimestamp: boolean;
  /** 확정 원인 배지 표시 여부. 설정 드로어에서 끈다. */
  showFinalizeTrigger: boolean;
  /** 블록 번호(#N) 표시 여부. 설정 드로어에서 끈다. */
  showBlockNo: boolean;
}

export const SttTextViewer = ({
  row,
  showTimestamp,
  showFinalizeTrigger,
  showBlockNo,
}: SttTextViewerProps) => {
  const orgStyle = useSttTextStyle('original');
  const transStyle = useSttTextStyle('translation');
  const sysStyle = useSttTextStyle('system');

  // 확정 순간 세그먼트 translation 미도착 + buffer 리셋으로 잠깐 비는 구간에도 직전 번역을 유지한다.
  // render 중 ref 접근은 react-hooks/refs 로 금지되므로, '이전 렌더 값 저장' state 를
  // render 중 조건부로 갱신하는 React 표준 패턴을 쓴다(가드된 setState — 무한루프 없음).
  const [lastTranslation, setLastTranslation] = useState<string | undefined>(undefined);
  const incoming = row.translation ?? row.bufferTranslation;
  if (incoming && incoming.length > 0 && incoming !== lastTranslation) setLastTranslation(incoming);
  const translation = incoming && incoming.length > 0 ? incoming : lastTranslation;
  const hasTranslation = Boolean(translation && translation.length > 0);
  const isProcessing = !row.finalized;

  // 메타 줄(시각 + 확정 원인)은 둘 다 없으면 아예 렌더하지 않는다 — 빈 div 를 남기면
  // 부모의 flex gap 만 잡아먹어 행 간격이 벌어진다. 미확정 줄은 trigger 가 null 이라 배지가 없다.
  const timestampVisible = showTimestamp && Boolean(row.start);
  const triggerLabel = row.trigger ? TRIGGER_LABELS[row.trigger] : undefined;
  const triggerVisible = showFinalizeTrigger && Boolean(triggerLabel);
  // 번호는 시각·배지와 독립적으로 켜진다 — 둘 다 꺼도 관리자 페이지에서 블록을 지목할 수
  // 있어야 하므로, 번호만 켜진 경우에도 메타 줄을 렌더한다.
  const blockNoVisible = showBlockNo && row.blockNo !== undefined;

  // data-* 는 화면에 영향을 주지 않는 자동화 계약이다 — 경로 C 하니스(scripts/vbcable_test.py)가
  // 확정 줄 경계와 확정 계기를 여기서 읽는다. 제거·개명하면 측정이 조용히 깨진다.
  // 메타 줄은 반드시 `stt-text` div **바깥**에 둔다 — 하니스가 원문 div 의 innerText 만 읽으므로
  // 안에 넣으면 시각·배지 문구가 전사에 섞여 WER 이 조용히 오염된다.
  return (
    <div
      className="flex flex-col"
      // 블록 내부 간격([메타줄↔원문]·[원문↔번역])은 '문장 간격' 배율에서 파생된다 — 설정 하나로
      // 줄 안 간격과 함께 움직이는 것이 의도다(블록↔블록 간격은 SttMain 의 --stt-block-gap).
      style={{ gap: 'var(--stt-sentence-gap)' }}
      data-testid="stt-row"
      data-trigger={row.trigger ?? ''}
      data-finalized={row.finalized}
      data-speaker={row.speaker}
      data-block-no={row.blockNo ?? ''}
    >
      {(blockNoVisible || timestampVisible || triggerVisible) && (
        <div className="flex items-center gap-2 leading-none">
          {blockNoVisible && (
            // 실시간 전사를 방해하지 않도록 시각과 같은 톤·크기로 작게 둔다.
            <span className="opacity-40" style={{ ...sysStyle, fontSize: '0.7em' }}>
              #{row.blockNo}
            </span>
          )}
          {timestampVisible && (
            <span className="opacity-50" style={{ ...sysStyle, fontSize: '0.7em' }}>
              {row.start}
              {row.end && row.end !== row.start ? ` – ${row.end}` : ''}
            </span>
          )}
          {triggerVisible && row.trigger && (
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5 text-[12px] font-semibold"
              style={{
                color: TRIGGER_COLORS[row.trigger],
                // 배경/테두리는 같은 색의 저채도 tint — 배경색(기본 검정)이 바뀌어도 읽힌다.
                backgroundColor: `${TRIGGER_COLORS[row.trigger]}2b`,
                border: `1px solid ${TRIGGER_COLORS[row.trigger]}66`,
              }}
            >
              {triggerLabel}
            </span>
          )}
        </div>
      )}

      <div
        data-testid="stt-text"
        style={{
          ...orgStyle,
          opacity: isProcessing && !hasTranslation ? 'var(--stt-processing-opacity)' : 1,
        }}
      >
        {/* buffer 꼬리는 같은 문단 안에서 이어 붙인다 — 줄을 새로 만들면 화면이 출렁인다. */}
        {row.bufferText ? `${row.text}${row.bufferText}` : row.text}
      </div>
      {isProcessing && !hasTranslation && <SttTranslateLoader />}
      {hasTranslation && <div style={transStyle}>{translation}</div>}
    </div>
  );
};
