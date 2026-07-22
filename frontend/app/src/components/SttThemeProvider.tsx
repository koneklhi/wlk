/**
 * @fileoverview STT 테마 Provider — CSS 변수 주입 + 텍스트 스타일 훅
 */
import { useThemeStore } from '@/stores/theme.store';
import { CSSProperties, ReactNode } from 'react';

export function STTThemeProvider({ children }: { children: ReactNode }) {
  const {
    backgroundColor,
    titleBackgroundColor,
    fontFamily,
    fontSizeOriginal,
    fontSizeTranslation,
    fontSizeSystem,
    colorOriginalForeground,
    colorTranslationForeground,
    colorSystemForeground,
    colorTitleForeground,
    fontSizeTitle,
    fontSizeSubtitle,
    imageSizeLogo,
  } = useThemeStore();

  const cssVars = {
    ['--stt-bg']: backgroundColor,
    ['--stt-title-bg']: titleBackgroundColor,
    ['--stt-font']: fontFamily,
    ['--stt-font-size-original']: `${fontSizeOriginal}px`,
    ['--stt-font-size-translation']: `${fontSizeTranslation}px`,
    ['--stt-font-size-system']: `${fontSizeSystem}px`,
    ['--stt-color-original-fg']: colorOriginalForeground,
    ['--stt-color-translation-fg']: colorTranslationForeground,
    ['--stt-color-system-fg']: colorSystemForeground,
    ['--stt-color-title-fg']: colorTitleForeground,
    ['--stt-font-size-title']: `${fontSizeTitle}px`,
    ['--stt-font-size-subtitle']: `${fontSizeSubtitle}px`,
    ['--stt-image-size-logo']: `${imageSizeLogo}px`,
  } as CSSProperties;

  return (
    <div className="w-full h-full relative flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--stt-bg)', ...cssVars }}>
      {children}
    </div>
  );
}

/** inline style 객체 반환 — Tailwind dynamic class 대신 사용 (JIT 호환) */
export const useSttTextStyle = (kind: 'original' | 'translation' | 'system'): CSSProperties => {
  if (kind === 'original') {
    return {
      fontFamily: 'var(--stt-font)',
      fontSize: 'var(--stt-font-size-original)',
      color: 'var(--stt-color-original-fg)',
      fontWeight: 'bold',
      lineHeight: '1.75',
    };
  }
  if (kind === 'translation') {
    return {
      fontFamily: 'var(--stt-font)',
      fontSize: 'var(--stt-font-size-translation)',
      color: 'var(--stt-color-translation-fg)',
      fontWeight: '500',
      lineHeight: '1.75',
    };
  }
  return {
    fontFamily: 'var(--stt-font)',
    fontSize: 'var(--stt-font-size-system)',
    color: 'var(--stt-color-system-fg)',
    fontWeight: '500',
    lineHeight: '1.75',
  };
};
