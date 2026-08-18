/**
 * @fileoverview 번역 진행 로더 — Loader2 아이콘 + "번역 중..." 텍스트 (stt-frontend 스타일)
 */
import { useSttTextStyle } from '@/components/SttThemeProvider';
import { useThemeStore } from '@/stores/theme.store';
import { Loader2 } from 'lucide-react';

export const SttTranslateLoader = () => {
  const transStyle = useSttTextStyle('translation');
  const { fontSizeSystem } = useThemeStore();

  // 투명도는 반드시 **바깥 래퍼**에 건다. 안쪽 div 는 animate-pulse 가 opacity 를 1↔.5 로
  // 애니메이션하므로, 같은 요소에 준 opacity 클래스·인라인 값은 애니메이션에 덮여 무시된다
  // (종전 opacity-40 이 사실상 먹지 않던 이유). 래퍼에 걸면 두 값이 곱해져 설정이 실제로 반영된다.
  return (
    <div style={{ opacity: 'var(--stt-processing-opacity)' }}>
      <div className="w-full text-gray-400 text-sm animate-pulse flex gap-1.5 items-center">
        <Loader2 className="animate-spin" size={fontSizeSystem} style={{ color: transStyle.color }} />
        <p style={transStyle}>번역 중...</p>
      </div>
    </div>
  );
};
