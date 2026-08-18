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
    screenPaddingXPercent,
    blockGapPx,
    lineSpacingRatio,
    processingOpacity,
    bottomPaddingPercent,
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
    ['--stt-padding-x']: `${screenPaddingXPercent}%`,
    ['--stt-block-gap']: `${blockGapPx}px`,
    ['--stt-line-height']: `${lineSpacingRatio}`,
    // 원문↔번역 간격은 줄간격 배율에서 파생시킨다 — 사용자가 '문장 간격' 하나만 움직이면
    // 줄 안 간격과 원문/번역 사이 간격이 같은 비율로 함께 움직여야 한다는 요구 때문이다.
    // 기본값 검산: (1.75-1) × 24px × 0.5 = 9px ≈ 종전 gap-2(8px) — 안 건드리면 화면이 그대로다.
    ['--stt-sentence-gap']: `${Math.max(0, (lineSpacingRatio - 1) * fontSizeOriginal * 0.5)}px`,
    ['--stt-processing-opacity']: `${processingOpacity}`,
    // %가 아니라 vh 인 이유: CSS 의 padding/height 백분율은 높이가 아니라 **컨테이너 너비** 기준이라
    // "화면 높이 %" 라는 설정 의미를 그대로 담으려면 vh 여야 한다.
    ['--stt-bottom-pad']: `${bottomPaddingPercent}vh`,
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
      lineHeight: 'var(--stt-line-height)',
    };
  }
  if (kind === 'translation') {
    return {
      fontFamily: 'var(--stt-font)',
      fontSize: 'var(--stt-font-size-translation)',
      color: 'var(--stt-color-translation-fg)',
      fontWeight: '500',
      lineHeight: 'var(--stt-line-height)',
    };
  }
  return {
    fontFamily: 'var(--stt-font)',
    fontSize: 'var(--stt-font-size-system)',
    color: 'var(--stt-color-system-fg)',
    fontWeight: '500',
    lineHeight: 'var(--stt-line-height)',
  };
};
