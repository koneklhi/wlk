/**
 * @fileoverview 백엔드 헬스체크 REST API (§3.1)
 */
import { fetchJson } from '@/utils/fetchJson';

export interface HealthResponse {
  status: 'ok';
  backend: string;
  ready: boolean;
}

export const getHealth = () => fetchJson<HealthResponse>('/wlkies/health');
