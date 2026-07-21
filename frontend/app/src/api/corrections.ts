/**
 * @fileoverview 단어교정 사전 REST API (§3.3)
 */
import { Server } from '@/constants';
import { fetchJson } from '@/utils/fetchJson';

// --- 타입 ---

export interface CorrectionItem {
  wrong_word: string;
  correct_word: string;
}

export type CorrectionsList = Record<string, CorrectionItem>;

// --- API ---

export const getCorrections = () => fetchJson<CorrectionsList>(Server.CORRECTIONS_URL);

export const addCorrection = (item: CorrectionItem) =>
  fetchJson<{ status: string }>(Server.CORRECTIONS_URL, {
    method: 'POST',
    body: JSON.stringify(item),
  });

export const deleteCorrection = (wrongWord: string) =>
  fetchJson<{ status: string }>(`${Server.CORRECTIONS_URL}/${encodeURIComponent(wrongWord)}`, {
    method: 'DELETE',
  });
