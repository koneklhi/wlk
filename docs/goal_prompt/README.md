# docs/goal_prompt — 자율 루프 Goal 프롬프트

새 Claude Code 세션의 첫 메시지로 붙여넣어 자율(또는 체크포인트 상의) 실험 루프를 구동하는
goal 프롬프트 지침 파일을 보관한다. **완료·머지된 goal은 [docs/archive/](../archive/)로 옮긴다** —
여기 있는 파일은 아직 미실행이거나 진행 중인 계획이다.

**앞으로 goal 프롬프트 생성 시 여기에 생성한다.**

| 파일 | 내용 | 상태 |
|---|---|---|
| [GOAL_CODESWITCH_BOUNDARY.md](GOAL_CODESWITCH_BOUNDARY.md) | 코드스위칭 경계 3증상 수정 루프 — Stage 0(Exp-172) 완료, Stage 1은 별도 goal(archive의 GOAL_SCRIPT_ANCHOR_REDETECT.md, Exp-175)로 분리 완료, **Stage 2(③ 계측기반 수정)는 미착수** | 부분 완료 — Stage 2 대기 |
| [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md) | 경계 복구 구간 QualityGate 버퍼 폐기 유실(Type B 삼킴) 제거 | 미실행 — 다음 예정 루프 |
| [GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md](GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md) | ScriptAnchorRedetect 철자 낭독(약어) 오발동 가드 | 진행 중(워크트리 `scriptanchor-acronym-guard`) |
