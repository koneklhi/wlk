/**
 * @fileoverview 블록 재번역 REST (정본 = docs/API_SPEC.md §3.6).
 *
 * 실시간 파이프라인의 소급 재번역은 최근 N줄(기본 20)만 대상이라, 창 밖 오래된 문장이나
 * 일시중단 이전 세션 구간은 서버가 스스로 되살리지 못한다. 이 엔드포인트는 그 구간을
 * 세션과 무관하게 1건씩 다시 번역한다.
 */
import { Api } from '@/constants';
import { fetchJson } from '@/utils/fetchJson';

/** LLM 왕복 + 첫 호출의 RAG 로드까지 감안한 상한. 기본 5초로는 절대 완주하지 못한다. */
const RETRANSLATE_TIMEOUT_MS = 60_000;

export interface RetranslateResponse {
  status: 'success' | 'warning';
  translation: string;
  message?: string;
}

/**
 * 텍스트 1건을 지금의 용어집으로 다시 번역한다.
 *
 * `status: 'warning'`(= 빈 translation)은 에코 폐기다. **화면 번역을 덮어쓰면 안 된다** —
 * 덮어쓰면 번역이 사라진 것처럼 보인다.
 */
export const retranslateText = (text: string, srcLang = 'ko') =>
  fetchJson<RetranslateResponse>(
    Api.RETRANSLATE,
    { method: 'POST', body: JSON.stringify({ text, src_lang: srcLang }) },
    RETRANSLATE_TIMEOUT_MS,
  );
