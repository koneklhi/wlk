/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 라우팅 prefix. vite.config.ts 의 base 와 같아야 한다. 기본 '/wlkies'. */
  readonly VITE_BASE_URL?: string;
  /** 설정 드로어 footer 에 표시할 버전 문자열. */
  readonly VITE_APP_VERSION?: string;
  /**
   * WS origin 오버라이드 (예: ws://127.0.0.1:8900). **개발 전용.**
   * 배포 빌드에 넣지 말 것 — 그 PC 에서만 동작하게 된다. 기본은 window.location 기준 자동 조립.
   */
  readonly VITE_WS_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
