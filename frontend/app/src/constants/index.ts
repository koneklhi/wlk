/**
 * @fileoverview 서버 URL 상수
 */

/** 백엔드 WS 경로 */
const WS_PATH = import.meta.env.VITE_WS_PATH ?? '/asr';

/** 백엔드 서버 URL */
export const Server = {
  WS_PATH,
  // VITE_WS_URL이 설정되면 절대 URL, 아니면 로컬 경로
  WS_URL: import.meta.env.VITE_WS_URL ? import.meta.env.VITE_WS_URL + '/asr' : WS_PATH,
  // 단어교정 사전
  CORRECTIONS_URL: import.meta.env.VITE_CORRECTIONS_URL ?? '/api/corrections',
} as const;
