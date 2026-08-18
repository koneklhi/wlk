/**
 * @fileoverview 단어교정 사전 + 번역 사전 REST API (정본 = docs/API_SPEC.md §3).
 */
import { Api } from '@/constants';
import { fetchJson } from '@/utils/fetchJson';

// ── 단어교정 (전사 후처리 대치) ──────────────────────────────────────────────

/**
 * GET /api/corrections 응답은 **평평한 dict** `{ "<wrong_word>": "<correct_word>" }` 다
 * (filtering/manager.py `word_manager.user_replacements`). **사용자가 추가한 DB 항목만**
 * 반환된다 — 서버 내장 기본 사전(base JSON)은 관리자 페이지에 노출하지 않는다.
 * 숨겨진 base 항목도 실제 전사 후처리 치환에는 그대로 적용된다.
 */
export type CorrectionsMap = Record<string, string>;

export const getCorrections = () => fetchJson<CorrectionsMap>(Api.CORRECTIONS);

export const addCorrection = (wrongWord: string, correctWord: string) =>
  fetchJson<{ status: string }>(Api.CORRECTIONS, {
    method: 'POST',
    body: JSON.stringify({ wrong_word: wrongWord, correct_word: correctWord }),
  });

/**
 * 삭제. 기본(base JSON) 항목은 HTTP 200 + `{status:'warning'}`로 온다(에러가 아니다) —
 * 호출측에서 status를 확인할 것 (deletePromptItem과 동일 패턴).
 */
export const deleteCorrection = (wrongWord: string) =>
  fetchJson<{ status: string; message?: string }>(`${Api.CORRECTIONS}/${encodeURIComponent(wrongWord)}`, {
    method: 'DELETE',
  });

// ── 번역 사전 (LLM 프롬프트 블록) ────────────────────────────────────────────

/** 번역 사전 블록. glossary = 용어 대응, sentence = 번역 예시. */
export type PromptBlockKey = 'glossary_block' | 'sentence_block';

export interface PromptsResponse {
  glossary_block: Record<string, string>;
  sentence_block: Record<string, string>;
}

export const getPrompts = () => fetchJson<PromptsResponse>(Api.PROMPTS);

export const addPromptItem = (blockKey: PromptBlockKey, origin: string, translation: string) =>
  fetchJson<{ status: string }>(Api.PROMPTS_ADD, {
    method: 'POST',
    body: JSON.stringify({ block_key: blockKey, origin, translation }),
  });

/**
 * 삭제. 항목이 없거나 기본 glossary 항목이면 HTTP 200 + `{status:'warning'}` 로 온다
 * (에러가 아니다) — 호출측에서 status 를 확인할 것.
 */
export const deletePromptItem = (blockKey: PromptBlockKey, origin: string) =>
  fetchJson<{ status: string; message?: string }>(Api.PROMPTS_DELETE, {
    method: 'POST',
    body: JSON.stringify({ block_key: blockKey, origin }),
  });
