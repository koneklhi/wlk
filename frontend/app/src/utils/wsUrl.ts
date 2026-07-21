/**
 * @fileoverview 전사 WebSocket URL 조립.
 *
 * 기본은 **현재 origin 기준 절대 URL**이다. 이유가 둘 있다.
 *
 * ① 배포 PC 는 백엔드가 dist 를 직접 서빙하므로(localhost:8900) 어떤 env 도 필요 없다.
 *    예전에는 VITE_WS_URL 에 특정 PC IP(ws://48.2.40.30:8900)가 박힌 채 빌드돼
 *    그 PC 밖에서는 동작하지 않았다.
 * ② 상대 URL(`new WebSocket('/asr')`)은 배포 PC 의 구형 브라우저가 'URL is invalid' 로 거부한다.
 *    그래서 백엔드가 index.html <head> 에 WS URL 정규화 shim(`_WS_SHIM`)을 주입해 우회 중인데,
 *    프론트가 처음부터 절대 URL 을 만들면 그 우회를 걷어낼 수 있다.
 *    (docs/FRONTEND_HANDOFF_NEXT_DEV.md '고쳐야 할 것' 4번)
 */
import type { SourceLanguage, WsMode } from '@/types/stt';

/** 백엔드 전사 엔드포인트 경로. */
const WS_PATH = '/asr';

/**
 * @param language 세션 소스 언어. 'auto' 도 **명시적으로 보낸다** —
 *   파라미터를 생략하면 서버 전역 `--lan` 을 따르므로, 운영자가 `--lan ko` 로 띄운 서버에서
 *   사용자가 AUTO 를 골라도 한국어로 고정되어 버린다.
 * @param mode 전송 프로토콜. 기본 delta(대역폭 4.7배 절감). 문제 발생 시 'full' 로 탈출 가능.
 */
export function buildWsUrl(language: SourceLanguage, mode: WsMode = 'delta'): string {
  const url = new URL(WS_PATH, resolveWsOrigin());
  url.searchParams.set('language', language);
  url.searchParams.set('mode', mode);
  return url.toString();
}

/**
 * WS origin 결정. VITE_WS_URL 이 있으면 그것을 쓰고(프론트를 백엔드와 다른 호스트에서
 * 띄우는 개발 상황 전용), 없으면 현재 페이지 origin 에서 유도한다.
 *
 * vite dev(5173)에서는 env 없이도 동작한다 — vite.config.ts 의 '/asr' 프록시가 받아준다.
 */
function resolveWsOrigin(): string {
  const override = import.meta.env.VITE_WS_URL;
  if (override) return override;
  const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${scheme}//${window.location.host}`;
}
