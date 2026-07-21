/**
 * @fileoverview 번역 진행 로더 — Loader2 아이콘 + "번역 중..." 텍스트 (stt-frontend 스타일)
 */
import { useSttTextStyle } from '@/components/SttThemeProvider';
import { useThemeStore } from '@/stores/theme.store';
import { Loader2 } from 'lucide-react';

export const SttTranslateLoader = () => {
  const transStyle = useSttTextStyle('translation');
  const { fontSizeSystem } = useThemeStore();

  return (
    <div className="w-full text-gray-400 text-sm animate-pulse flex gap-1.5 items-center opacity-40">
      <Loader2 className="animate-spin" size={fontSizeSystem} style={{ color: transStyle.color }} />
      <p style={transStyle}>번역 중...</p>
    </div>
  );
};
