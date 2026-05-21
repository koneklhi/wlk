# 미정 사항 — 구현 직전에 사용자와 합의

본 문서는 [CLAUDE.md](../CLAUDE.md)에서 분리한 **미정 설계 사항**이다. 해당 영역 구현 직전에
사용자와 합의해 확정한다. 진행 현황은 [ROADMAP.md](../ROADMAP.md) Phase 2와 교차 참조한다.

## 1. 문장 단위 확정 판단 알고리즘

기존 `whisperlive`의 임시방편(같은 문장 N회 반복 시 확정, 타임스탬프 변화량 임계치 등)은
**그대로 이식하지 않는다**. 후보 비교 후 본격 개발 시점에 사용자와 합의해 확정한다.

- 스트리밍 정책: SimulStreaming(AlignAtt + CIF 기반 단어 끝 감지, WLK 기본값, **채택됨** — ROADMAP 2-1) /
  LocalAgreement(가설 비교 기반 토큰 안정화)
- 확정 신호 후보: Whisper segment 경계, `no_speech_prob`, VAD 무음 구간, 구두점, 언어 전환 경계 등
  (이 목록에 한정하지 않음)
- 정책과 신호의 조합 방식은 설계 세션에서 비교 후 결정한다.

## 2. 한·영 Code-Switching 검출 방식과 문장 분할 트리거

- 한 발화 안에 한·영 혼용 상황에서 단어 유실 / 환각 / 문장 조기 확정이 발생하지 않도록 검출·분할 트리거 설계.

## 3. React에 보내는 메시지 스키마 + React UI 변경 범위

현 단계에서는 스키마 형태를 못박지 않는다. 의미상 가져갈 가능성이 높은 필드(기존 `whisperlive` 기준):
`text`(원본 메시지), `start` / `end`(타임스탬프), `completed`(확정/비확정 플래그), `lang`(언어 정보) 등.
`whisperlivekit` 기본 출력은 `lines[]` + `buffer_transcription` / `buffer_diarization` / `buffer_translation` 형태.

- **후보 A**: 기존 `whisperlive`의 세그먼트 스키마(`{text, start, end, completed, lang, …}`)를 가져가고
  백엔드에서 `whisperlivekit` 출력을 그에 맞춰 변환
- **후보 B**: `whisperlivekit` 출력에 맞춰 새 스키마를 정의하고 React UI를 그에 맞게 변경

STT 핵심 기능(ROADMAP Phase 1~3) 구현 완료 후, React UI 연결 단계(ROADMAP Phase 4) 진입 직전에 의논해 결정.

## 4. 폐쇄망용 모델 디렉터리 레이아웃과 배포 패키징 형태
