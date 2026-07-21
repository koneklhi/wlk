/**
 * @fileoverview 개별 문장 렌더링 — 원문 + 번역 (stt-frontend 스타일)
 */
import { useSttTextStyle } from '@/components/SttThemeProvider';
import { SttTranslateLoader } from '@/components/SttTranslateLoader';

interface SttTextViewerProps {
  content: string;
  translation?: string;
  status: 'process' | 'complete';
  index: number;
}

export const SttTextViewer = ({ content, translation, status, index }: SttTextViewerProps) => {
  const orgStyle = useSttTextStyle('original');
  const transStyle = useSttTextStyle('translation');

  const hasTranslation = translation && translation.length > 0;
  const isProcessing = status === 'process';

  return (
    <div className="flex flex-col gap-2">
      <div
        style={{
          ...orgStyle,
          opacity: isProcessing && !hasTranslation ? 0.4 : 1,
        }}
      >
        {content}
      </div>
      {isProcessing && !hasTranslation && <SttTranslateLoader />}
      {hasTranslation && (
        <div style={transStyle}>{translation}</div>
      )}
    </div>
  );
};
