# 설계 결정 이력 — 대부분 해소됨 (정본 링크)

본 문서는 [CLAUDE.md](../CLAUDE.md)에서 분리했던 **초기 미정 설계 사항**이다.
아래 항목은 구현·합의로 **대부분 해소**됐으며, 각 항목의 현행 정본 문서를 가리킨다.
진행 현황은 [ROADMAP.md](../ROADMAP.md)와 교차 참조한다.

## 1. 문장 단위 확정 판단 알고리즘 — 해소

- 스트리밍 정책: **SimulStreaming(AlignAtt + CIF 기반 단어 끝 감지) 채택**(ROADMAP 2-1). 기존 `whisperlive`의 임시방편(N회 반복 확정 등)은 이식하지 않음.
- 확정 신호·경계 로직(구두점·VAD 무음·언어 전환 경계·retraction·온점 형태소 분할 등)은 구현·문서화 완료.
- 정본 = [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md), 요구사항·측정 = [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md).

## 2. 한·영 Code-Switching 검출·문장 분할 트리거 — 해소 (개선 지속)

- 언어 전환 마커·retraction·script-anchor 재감지(Exp-168~175)로 구현. 짧은 텀 코드스위칭(ytn2)·다화자(bong1) 역량은 Phase 2 개선 루프에서 지속 향상 대상.
- 정본 = [CODESWITCH_REALTIME_DESIGN.md](research/CODESWITCH_REALTIME_DESIGN.md), [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md).

## 3. React UI 연결 범위 — 스키마 해소, 통합 검증만 대기

- 메시지 스키마 **확정·구현 완료**(후보 A: `whisperlivekit` 출력 + `completed` / `lang` 등 React 호환 별칭 유지). 정본 = [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) / [API_SPEC.md](API_SPEC.md).
- React UI 실제 연결·표출 검증 완료됨(ROADMAP Phase 4-7, 배포 UI 반입·통합검증 2026-07-21).

## 4. 폐쇄망 모델 디렉터리 레이아웃·배포 패키징 — 해소

- 정본 = [DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md)(폐쇄망 반입·모델 경로·wheelhouse 패키징 절차).

## 5. 경로 C 자동화 대상 UI(내장→배포) 전환 — 정책 확정, 구현 대기

- **정책 확정(2026-07-22)**: 내장 UI(`whisperlivekit/web/`) 사용을 중단하고, 배포 UI(React, `frontend/app/`)를
  경로 B/C를 포함한 모든 테스트·검증 경로의 기본 UI로 삼는다(CLAUDE.md §3.3/§3.7).
- **구현 공백**: `scripts/vbcable_test.py`의 Playwright 자동화가 아직 내장 UI 전용 DOM(`#startButton` 등)에
  하드코딩돼 있고, 배포 React UI엔 대응하는 안정적 자동화 훅(`data-testid` 등)이 전혀 없다. §3.7 규약에 따라
  **React 쪽에 자동화용 속성을 추가할지 여부는 여기서 먼저 논의해 결정한다** — 예: `data-testid="start-button"`,
  `data-trigger` DOM 노출 등. 아직 미결정.
- **후속 작업 상세 계획** = [docs/backlog/BACKLOG_EVAL_DEPLOY_UI_MIGRATION.md](backlog/BACKLOG_EVAL_DEPLOY_UI_MIGRATION.md).
