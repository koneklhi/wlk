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

  // 블록 번호(#N) 표시 여부. 관리자 페이지가 이 번호로 블록을 지목한다.
  showBlockNo: boolean;

  // 화면 레이아웃 — 배포 현장(화면 크기·시청 거리)에 맞춰 운용자가 조절한다.
  screenPaddingXPercent: number; // 전사 영역 좌우 여백 (화면 너비 %)
  blockGapPx: number; // 블록(원문+번역) 사이 간격 (px)
  lineSpacingRatio: number; // 줄간격 배율. 원문↔번역 간격도 여기서 파생한다(SttThemeProvider).
  processingOpacity: number; // 미확정(진행중) 전사·번역 대기 로더의 불투명도
  bottomPaddingPercent: number; // 전사 목록 하단 여백 (화면 높이 %, vh)

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
  setShowBlockNo: (v: boolean) => void;
  setScreenPaddingXPercent: (v: number) => void;
  setBlockGapPx: (v: number) => void;
  setLineSpacingRatio: (v: number) => void;
  setProcessingOpacity: (v: number) => void;
  setBottomPaddingPercent: (v: number) => void;
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
  // 저장분에 이 키가 없으므로 얕은 병합으로 기본값이 살아난다 — persist version 을 올릴 필요가 없다.
  showBlockNo: true,
  // 레이아웃 기본값: 문단 간격 56 = 종전 gap-14, 줄간격 1.75 = 종전 하드코딩,
  // 투명도 0.4 = 종전 미확정 opacity. 좌우 여백·하단 여백만 종전(px-16=64px, pb-12=48px)에서
  // 화면 비례값으로 바뀐다 — 큰 화면일수록 여백이 함께 커지도록 한 의도된 변경이다.
  screenPaddingXPercent: 5,
  blockGapPx: 56,
  lineSpacingRatio: 1.75,
  processingOpacity: 0.4,
  bottomPaddingPercent: 20,
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
      setShowBlockNo: (v: boolean) => set(() => ({ showBlockNo: v })),
      setScreenPaddingXPercent: (v: number) => set(() => ({ screenPaddingXPercent: v })),
      setBlockGapPx: (v: number) => set(() => ({ blockGapPx: v })),
      setLineSpacingRatio: (v: number) => set(() => ({ lineSpacingRatio: v })),
      setProcessingOpacity: (v: number) => set(() => ({ processingOpacity: v })),
      setBottomPaddingPercent: (v: number) => set(() => ({ bottomPaddingPercent: v })),
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
