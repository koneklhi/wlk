# docs/backlog — 개선 백로그

구현하지 않은 잔존 실패 사례 카탈로그 + 개선 방향 제안 문서를 보관한다. 분석·설계 제안까지만 담고
실측 없이 구현하지 않는다 — 착수 시 별도 goal 프롬프트([docs/goal_prompt/](../goal_prompt/))로 분리한다.

**앞으로 백로그 문서는 여기에 생성한다.**

| 파일 | 내용 |
|---|---|
| [BACKLOG_CODESWITCH_FOLLOWUP.md](BACKLOG_CODESWITCH_FOLLOWUP.md) | 코드스위칭 후속 개선 백로그(GOAL_SCRIPT_ANCHOR_REDETECT §3.5 탐사 산출물) — 미방출형 서두유실·locked-lang 음차 환각·세션초입 buffer 유실·bong1 필러/웃음 환각·문장 중복 재방출 우선순위 카탈로그 |
| [BACKLOG_EVAL_DEPLOY_UI_MIGRATION.md](BACKLOG_EVAL_DEPLOY_UI_MIGRATION.md) | 경로 C 자동화(`scripts/vbcable_test.py`)를 내장 UI DOM 하드코딩에서 배포 UI(React) 타깃으로 전환하는 구현 계획 — Playwright 재작성 + React 자동화 훅 필요 여부 + `--server-frontend-dir` 의미 재정립 |
