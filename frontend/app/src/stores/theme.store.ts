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

  // 전사 시각(HH:MM:SS) 표시 여부.
  showTimestamp: boolean;

  // 문장 확정 원인(finalize_trigger) 배지 표시 여부.
  showFinalizeTrigger: boolean;

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
  setShowTimestamp: (v: boolean) => void;
  setShowFinalizeTrigger: (v: boolean) => void;
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
  showTimestamp: true,
  showFinalizeTrigger: true,
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
      setShowTimestamp: (v: boolean) => set(() => ({ showTimestamp: v })),
      setShowFinalizeTrigger: (v: boolean) => set(() => ({ showFinalizeTrigger: v })),
      reset: () => set(() => ({ ...DEFAULTS })),
    }),
    {
      // 키는 올리지 않는다 — 올리면 저장돼 있던 색상·폰트 설정이 통째로 날아간다.
      // 대신 version + migrate 로 바뀐 기본값만 기존 저장분에 밀어넣는다.
      name: 'stt-theme-v2',
      version: 1,
      // v0 저장분은 showTimestamp:false 를 담고 있어(당시 기본값) DEFAULTS 만 true 로 바꿔도
      // persist 의 얕은 병합이 저장분으로 덮어써 여전히 꺼진 채로 뜬다. 시각 표시만 1회 끌어올린다.
      // showFinalizeTrigger 는 저장분에 키 자체가 없어 기본값 true 가 그대로 살아남으므로 손대지 않는다.
      migrate: (persisted, version) =>
        version < 1
          ? ({ ...(persisted as Partial<STTThemeState>), showTimestamp: true } as STTThemeState)
          : (persisted as STTThemeState),
    },
  ),
);
