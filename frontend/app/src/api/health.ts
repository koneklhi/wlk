/**
 * @fileoverview 백엔드 헬스체크 (GET /health).
 *
 * ⚠️ 경로에 base(/wlkies)를 붙이면 안 된다 — 백엔드는 /health 를 루트에 등록하고
 *    /wlkies/* 는 SPA fallback 으로 index.html(HTML, 200)을 돌려준다. 그러면 res.json() 이
 *    throw 하고 status 도 없어 헬스가 영원히 unhealthy 로 남는다(실제로 그 상태였다).
 */
import { Api } from '@/constants';
import type { HealthResponse } from '@/types/stt';
import { fetchJson } from '@/utils/fetchJson';

export type { HealthResponse };

export const getHealth = () => fetchJson<HealthResponse>(Api.HEALTH);
