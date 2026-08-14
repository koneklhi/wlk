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

## 5. 경로 C 자동화 대상 UI(내장→배포) 전환 — 해소

- **정책 확정(2026-07-22)**: 내장 UI(`whisperlivekit/web/`) 사용을 중단하고, 배포 UI(React, `frontend/app/`)를
  경로 B/C를 포함한 모든 테스트·검증 경로의 기본 UI로 삼는다(CLAUDE.md §3.7).
- **구현 완료(2026-08-14)**: `scripts/vbcable_test.py`가 배포 UI(`/wlkies/`)를 몰고, `--browser-ui inline`으로
  내장 UI(`/dev`)를 A/B 대조군으로 쓴다. `eval.py`·`closed_test.py`가 같은 경로를 공유한다.
- **미결이었던 "React 자동화 속성 추가 여부" = 추가하기로 결정(사용자 승인)**. 근거와 범위:
  - 추가한 것: 컨트롤·상태·전사행에 `data-testid`, 상태에 `data-phase`(raw enum), 전사행에
    `data-trigger`/`data-finalized`/`data-speaker`. 전부 **순수 속성 추가**라 렌더 트리·스타일·동작 무변경.
  - 대안(텍스트·Tailwind 클래스 셀렉터)은 레이아웃 클래스와 버튼 문구를 암묵적 측정 계약으로 만든다 —
    디자인 리팩터링 한 번이 측정을 조용히 0줄로 만들 수 있다. `data-phase`는 지역화 문구("인식 중")가
    아니라 enum(`recording`)을 노출해 문구 변경에 견딘다.
  - `finalize_trigger`는 이미 서버 계약(`types/stt.ts`)에 있던 필드이며 DOM 노출만 추가했다 —
    전사 txt의 `[문장별 확정 트리거]` 섹션과 `/eval` 정성 절차를 그대로 유지하기 위함이다.
- **지표 정본 = 배포 UI DOM**, WS 프레임 캡처는 병행 검증(누락·중복 경고)으로만 쓴다. 화면이 곧 제품이므로
  "렌더 버그가 지표에 잡히는" 성질은 결함이 아니라 기능이다(Exp-181/182 전례).
