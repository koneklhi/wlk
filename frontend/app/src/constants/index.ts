/**
 * @fileoverview 백엔드 REST 엔드포인트 경로 (정본 = docs/API_SPEC.md).
 *
 * 전부 **base(/wlkies) 없는 절대 경로**다. 백엔드는 API 를 루트에 등록하고 `/wlkies/*` 는
 * SPA fallback 으로 index.html 을 돌려주므로, base 를 붙이면 JSON 대신 HTML 이 와서
 * 조용히 실패한다(예전 `/wlkies/health` 가 그래서 항상 unhealthy 였다).
 *
 * WS URL 은 여기가 아니라 utils/wsUrl.ts 에서 조립한다(쿼리 파라미터가 붙으므로).
 */
export const Api = {
  HEALTH: '/health',

  /** 단어교정 사전. GET / POST / DELETE `${CORRECTIONS}/{wrong_word}` */
  CORRECTIONS: '/api/corrections',

  /**
   * 번역 사전(glossary/예시 블록). 정본 경로는 `/api/prompts*` 다.
   * 백엔드에 `/api/corrections/prompts*` alias 도 있지만 그건 구버전 배포 프론트를 받아주려고
   * 임시로 넣어둔 우회이므로 쓰지 않는다(제거 예정).
   */
  PROMPTS: '/api/prompts',
  PROMPTS_ADD: '/api/prompts/add-item',
  PROMPTS_DELETE: '/api/prompts/delete-item',

  /** 전사 저장. 서버 로컬(`--transcript-save-dir`, 기본 ./transcripts)에 .txt 로 떨어진다. */
  SAVE_TRANSCRIPT: '/api/save-transcript',
} as const;

/** 라우팅 prefix. vite.config.ts 의 `base` 와 반드시 일치해야 한다. */
export const BASE_PATH = import.meta.env.VITE_BASE_URL ?? '/wlkies';

export const APP_VERSION = import.meta.env.VITE_APP_VERSION ?? '';
