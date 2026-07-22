/**
 * @fileoverview 개별 문장 렌더링 — 원문 + 번역 (stt-frontend 스타일)
 *
 * 기존 배포 UI 의 형태를 그대로 유지한다: 원문 div → (번역 대기 시)로더 → 번역 div.
 * 진행중이면서 번역이 아직 없을 때 원문을 연하게 하는 것도 기존 동작 그대로다.
 * 추가된 것은 ① 선택적 시각 표시 ② 미확정 buffer 꼬리를 원문 뒤에 이어붙이는 것 뿐이다.
 */
import { useSttTextStyle } from '@/components/SttThemeProvider';
import { SttTranslateLoader } from '@/components/SttTranslateLoader';
import type { TranscriptRow } from '@/utils/transcriptRows';
import { useState } from 'react';

interface SttTextViewerProps {
  row: TranscriptRow;
  /** 시각(HH:MM:SS) 표시 여부. 기본 off — 설정 드로어에서 켠다. */
  showTimestamp: boolean;
}

export const SttTextViewer = ({ row, showTimestamp }: SttTextViewerProps) => {
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

  return (
    <div className="flex flex-col gap-2">
      {showTimestamp && row.start && (
        <div className="opacity-50 leading-none" style={{ ...sysStyle, fontSize: '0.7em' }}>
          {row.start}
          {row.end && row.end !== row.start ? ` – ${row.end}` : ''}
        </div>
      )}

      <div
        style={{
          ...orgStyle,
          opacity: isProcessing && !hasTranslation ? 0.4 : 1,
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
