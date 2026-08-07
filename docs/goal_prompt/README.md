# docs/goal_prompt — 자율 루프 Goal 프롬프트

새 Claude Code 세션의 첫 메시지로 붙여넣어 자율(또는 체크포인트 상의) 실험 루프를 구동하는
goal 프롬프트 지침 파일을 보관한다. **완료·머지된 goal은 [docs/archive/](../archive/)로 옮긴다** —
여기 있는 파일은 아직 미실행이거나 진행 중인 계획이다.

**앞으로 goal 프롬프트 생성 시 여기에 생성한다.**

| 파일 | 내용 | 상태 |
|---|---|---|
| [GOAL_HALLUCINATION_REDUCTION_LOOP.md](GOAL_HALLUCINATION_REDUCTION_LOOP.md) | **환각 빈도 저감 무정지 자율 루프(6h/토큰 소진)** — 2026-07-22 로그 분석으로 확정한 환각 3계열(① ko 고정 세션 refresh 폭주 중복 — `backend.py:449-501` 코드 갭 확정 ② 침묵 클로징 "감사합니다" — 타임스탬프 정체 시그니처 ③ 잠금언어 음차 "사태라" — Exp-172 사각지대)을 T1→T5 큐로 순회. master 머지 금지(채택권고까지만), 진행 리포트 = `docs/research/2026-07-22_hallucination-loop-progress.md` | **루프 종료**(2026-07-23, ~5시간17분) — T1/T5 채택권고(머지 대기), T2/T3 계측완료, T4 종결. 결과 = Exp-201~206 |
| [GOAL_CODESWITCH_BOUNDARY.md](GOAL_CODESWITCH_BOUNDARY.md) | 코드스위칭 경계 3증상 수정 루프 — Stage 0(Exp-172) 완료, Stage 1은 별도 goal(archive의 GOAL_SCRIPT_ANCHOR_REDETECT.md, Exp-175)로 분리 완료, **Stage 2(③ 계측기반 수정)는 미착수** | 부분 완료 — Stage 2 대기 |
| [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md) | 경계 복구 구간 QualityGate 버퍼 폐기 유실(Type B 삼킴) 제거 | 미실행 — 다음 예정 루프(자체 §0에 2026-07-19 시점 stale 경고 있음, 재개 전 baseline 재확인 필요) |
| [GOAL_BOUNDARY_TAIL_DUP.md](GOAL_BOUNDARY_TAIL_DUP.md) | 배포 실사용 제보 코드스위칭 2증상 — 경계 직전 단어 유실("반갑습니다" 소실) + 경계 첫 단어 중복 확정("nice"/"nice to meet you") 공동 루프. 창 확대↔중복의 트레이드오프라 반드시 한 루프에서 동시 판정 | 시도됨(Exp-191, 기각) — 관련 부분은 Exp-192 boundary_reconcile(master 머지 `b001e38`)가 커버. 잔여 재현 확인 필요 |
| ~~GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md~~ → [archive](../archive/GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md) | ScriptAnchorRedetect 철자 낭독(약어) 오발동 가드 | 루프 종료 — **판단 유보**(archive의 `..._REPORT.md`, 커밋 `747e47f`, `exp/scriptanchor-acronym-guard` master 미머지) |
| ~~GOAL_AUTO_KOREAN_FOLLOWUP.md~~ → [archive](../archive/GOAL_AUTO_KOREAN_FOLLOWUP.md) | auto 모드 한국어 후속조치 3단계 | **완료·master 머지됨**(Exp-187/188/189) |
| ~~GOAL_KOR1_SILENCEHARD_CASEB.md~~ → [archive](../archive/GOAL_KOR1_SILENCEHARD_CASEB.md) | `SILENCE_HARD_SECS` 안전망 Case B(단어 중간 강제분할) 수정 | **완료·master 머지됨**(Exp-190, `2a1391f`) |
| ~~GOAL_UTF8_HELD_EMIT_LOSS.md~~ → [archive](../archive/GOAL_UTF8_HELD_EMIT_LOSS.md) | held/UTF-8 재조립 방출 손상 수정 | **완료·master 머지됨**(Exp-199 `f9f9cc5`, Exp-200 `76150ca`) |
| ~~GOAL_LANGLOCK_STAGE0_SAMPLE_EXPANSION.md~~ → [archive](../archive/2026-07-21_GOAL_LANGLOCK_STAGE0_SAMPLE_EXPANSION.md) | 언어잠금 환각(`docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md`) 안 A(단일언어 세션 오탐률 표본 확대, 코드변경 0) 실행 → 안전하면 자율로 안 B(Stage 1 섀도우 게이트)까지, 위험 신호면 정지·보고 | **실행 완료(2026-07-21) = Exp-195**. §3 **"위험" 분기** 선택 — ko 12세션 3756프로브에서 발동 23건(0.61%)·순수 오탐 2건 확정으로 안전 조건 불충족 → **안 B 미착수**. 안 A는 ko/en `--repeat 3`까지 초과 달성(16세션). 후속 = `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` §4-0~§4-0-2 |
