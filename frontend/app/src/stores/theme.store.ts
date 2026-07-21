/**
 * @fileoverview STT 테마 설정 persist store (stt-frontend 스타일)
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type STTThemeState = {
  backgroundColor: string;
  titleBackgroundColor: string;
  fontFamily: string;

  // 원본, 번역, 시스템 폰트 크기
  fontSizeOriginal: number;
  fontSizeTranslation: number;
  fontSizeSystem: number;

  // 원본, 번역, 시스템 폰트 색상
  colorOriginalForeground: string;
  colorTranslationForeground: string;
  colorSystemForeground: string;

  // 타이틀
  colorTitleForeground: string;
  fontSizeTitle: number;
  fontSizeSubtitle: number;
  imageSizeLogo: number;
  logoSize: 'sm' | 'md' | 'lg' | 'xl';

  // 액션
  setBackgroundColor: (v: string) => void;
  setTitleBackgroundColor: (v: string) => void;
  setFontFamily: (v: string) => void;
  setFontSizeOriginal: (v: number) => void;
  setFontSizeTranslation: (v: number) => void;
  setFontSizeSystem: (v: number) => void;
  setColorOriginalForeground: (v: string) => void;
  setColorTranslationForeground: (v: string) => void;
  setColorSystemForeground: (v: string) => void;
  setColorTitleForeground: (v: string) => void;
  setLogoSize: (size: 'sm' | 'md' | 'lg' | 'xl') => void;
  reset: () => void;
};

const DEFAULTS = {
  backgroundColor: '#000000',
  titleBackgroundColor: '#000000',
  fontFamily: "'Pretendard Variable'",
  fontSizeOriginal: 24,
  fontSizeTranslation: 24,
  fontSizeSystem: 16,
  fontSizeTitle: 24,
  fontSizeSubtitle: 14,
  imageSizeLogo: 80,
  logoSize: 'sm' as 'sm' | 'md' | 'lg' | 'xl',
  colorOriginalForeground: '#ffffff',
  colorTranslationForeground: '#C88C14',
  colorSystemForeground: '#9cdcfe',
  colorTitleForeground: '#ffffff',
};

// ponytail: 4-digit hex (#rgb) → 6-digit (#rrggbb) for <input type="color">
function normalizeHex(v: string): string {
  if (/^#[0-9A-Fa-f]{6}$/.test(v)) return v;
  if (/^#[0-9A-Fa-f]{3}$/.test(v)) return '#' + v.slice(1).split('').map(c => c + c).join('');
  return v;
}

export const useThemeStore = create<STTThemeState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      setBackgroundColor: (v: string) => set(() => ({ backgroundColor: normalizeHex(v) })),
      setTitleBackgroundColor: (v: string) => set(() => ({ titleBackgroundColor: normalizeHex(v) })),
      setFontFamily: (v: string) => set(() => ({ fontFamily: v })),
      setFontSizeOriginal: (v: number) => set(() => ({ fontSizeOriginal: v })),
      setFontSizeTranslation: (v: number) => set(() => ({ fontSizeTranslation: v })),
      setFontSizeSystem: (v: number) => set(() => ({ fontSizeSystem: v })),
      setColorOriginalForeground: (v: string) => set(() => ({ colorOriginalForeground: normalizeHex(v) })),
      setColorTranslationForeground: (v: string) => set(() => ({ colorTranslationForeground: normalizeHex(v) })),
      setColorSystemForeground: (v: string) => set(() => ({ colorSystemForeground: normalizeHex(v) })),
      setColorTitleForeground: (v: string) => set(() => ({ colorTitleForeground: normalizeHex(v) })),
      setLogoSize: (size: 'sm' | 'md' | 'lg' | 'xl') => {
        switch (size) {
          case 'sm':
            set(() => ({ fontSizeTitle: 24, fontSizeSubtitle: 14, imageSizeLogo: 80, logoSize: 'sm' }));
            break;
          case 'md':
            set(() => ({ fontSizeTitle: 30, fontSizeSubtitle: 16.925, imageSizeLogo: 100, logoSize: 'md' }));
            break;
          case 'lg':
            set(() => ({ fontSizeTitle: 36, fontSizeSubtitle: 19.75, imageSizeLogo: 120, logoSize: 'lg' }));
            break;
          case 'xl':
            set(() => ({ fontSizeTitle: 44, fontSizeSubtitle: 23.725, imageSizeLogo: 160, logoSize: 'xl' }));
            break;
        }
      },
      reset: () => set(() => ({ ...DEFAULTS })),
    }),
    { name: 'stt-theme-v1' },
  ),
);
