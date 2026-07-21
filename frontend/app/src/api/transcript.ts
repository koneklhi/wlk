/**
 * @fileoverview 전사 저장 (POST /api/save-transcript).
 *
 * 저장 위치는 **서버 로컬**이다 — `--transcript-save-dir`(기본 ./transcripts)에 .txt 로 떨어진다.
 * 배포는 단일 PC 로컬 구성이라 사용자가 앉아 있는 그 PC 의 디스크다.
 * 브라우저 다운로드가 아닌 이유: 폐쇄망 PC 에서 파일이 다운로드 폴더로 흩어지고
 * 파일명 규칙을 프론트가 따로 정해야 하기 때문. 서버가 규칙을 단일 관리한다.
 */
import { Api } from '@/constants';
import type { SaveTranscriptRequest, SaveTranscriptResponse } from '@/types/stt';
import { fetchJson } from '@/utils/fetchJson';

export const saveTranscript = (body: SaveTranscriptRequest) =>
  fetchJson<SaveTranscriptResponse>(Api.SAVE_TRANSCRIPT, {
    method: 'POST',
    body: JSON.stringify(body),
    // 장시간 세션이면 줄 수가 많아 기본 5초로는 모자랄 수 있다.
  }, 15_000);
