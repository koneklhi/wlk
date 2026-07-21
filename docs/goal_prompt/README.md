# docs/goal_prompt — 자율 루프 Goal 프롬프트

새 Claude Code 세션의 첫 메시지로 붙여넣어 자율(또는 체크포인트 상의) 실험 루프를 구동하는
goal 프롬프트 지침 파일을 보관한다. **완료·머지된 goal은 [docs/archive/](../archive/)로 옮긴다** —
여기 있는 파일은 아직 미실행이거나 진행 중인 계획이다.

**앞으로 goal 프롬프트 생성 시 여기에 생성한다.**

> **미실행 3루프 권장 실행 순서(2026-07-19)**: ① [GOAL_UTF8_HELD_EMIT_LOSS.md](GOAL_UTF8_HELD_EMIT_LOSS.md)
> (방출 계층 순수 버그 — 트레이드오프 없음, 유닛 재현 가능성 높아 짧은 루프) →
> ② [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md)(설계 완료 상태로 대기 중) →
> ③ [GOAL_BOUNDARY_TAIL_DUP.md](GOAL_BOUNDARY_TAIL_DUP.md)(트레이드오프 커서 측정 무게 최대).
> 세 루프 모두 `align_att_base.py`/`backend.py`/`tokens_alignment.py`를 겹쳐 만지므로 **동시 진행보다
> 순차(각 루프 머지 결론 후 다음 분기)를 권장**하고, 경로 C 측정은 VBCable 단일 장치라 어떤 경우에도
> **동시 실행 금지**.

| 파일 | 내용 | 상태 |
|---|---|---|
| [GOAL_CODESWITCH_BOUNDARY.md](GOAL_CODESWITCH_BOUNDARY.md) | 코드스위칭 경계 3증상 수정 루프 — Stage 0(Exp-172) 완료, Stage 1은 별도 goal(archive의 GOAL_SCRIPT_ANCHOR_REDETECT.md, Exp-175)로 분리 완료, **Stage 2(③ 계측기반 수정)는 미착수** | 부분 완료 — Stage 2 대기 |
| [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md) | 경계 복구 구간 QualityGate 버퍼 폐기 유실(Type B 삼킴) 제거 | 미실행 — 다음 예정 루프 |
| [GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md](GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md) | ScriptAnchorRedetect 철자 낭독(약어) 오발동 가드 | 진행 중(워크트리 `scriptanchor-acronym-guard`) |
| [GOAL_AUTO_KOREAN_FOLLOWUP.md](GOAL_AUTO_KOREAN_FOLLOWUP.md) | auto 모드 한국어 후속조치 3단계(Exp-186) — ①speaker_change 트리거 손실 규명 ②kor1 Case B 수정 ③kor1 언어오검출(ko→en) 원인조사, `feat/debug-diagnostics-logging`(67a58ad) 기반 | **완료·master 머지됨**(Exp-187/188/189, 커밋 c2e6b86·80e3127) |
| [GOAL_KOR1_SILENCEHARD_CASEB.md](GOAL_KOR1_SILENCEHARD_CASEB.md) | 위 3-Stage 루프가 후속 과제로 인계한 유일한 미해결 hard-fail — `SILENCE_HARD_SECS` 안전망이 kor1 "국방환경을" 지점 등 낭독체 긴 pause에서 단어 중간 강제분할(Case B)하는 문제. 근본원인(`tokens_alignment.py` `_gate_decide` 383~430행)까지 특정된 상태로 시작 | **실행 완료(Exp-190, 채택권고)** — 브랜치 `exp/silence-hard-caseb-fix`, master 머지는 사용자 결정 대기 |
| [GOAL_UTF8_HELD_EMIT_LOSS.md](GOAL_UTF8_HELD_EMIT_LOSS.md) | 배포 실사용 제보 "연속 발화 중 단어 누락"("중동전쟁"→"중쟁", "플랫폼을" 유실) — held/UTF-8 재조립 방출 손상(Exp-172 경로 ⑷) 수정. 방출 계층 순수 버그 성격, 유닛 재현 우선 | 미실행 — 신규 작성(2026-07-19) |
| [GOAL_BOUNDARY_TAIL_DUP.md](GOAL_BOUNDARY_TAIL_DUP.md) | 배포 실사용 제보 코드스위칭 2증상 — 경계 직전 단어 유실("반갑습니다" 소실) + 경계 첫 단어 중복 확정("nice"/"nice to meet you") 공동 루프. 창 확대↔중복의 트레이드오프라 반드시 한 루프에서 동시 판정 | 미실행 — 신규 작성(2026-07-19) |
| ~~GOAL_LANGLOCK_STAGE0_SAMPLE_EXPANSION.md~~ → [archive](../archive/2026-07-21_GOAL_LANGLOCK_STAGE0_SAMPLE_EXPANSION.md) | 언어잠금 환각(`docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md`) 안 A(단일언어 세션 오탐률 표본 확대, 코드변경 0) 실행 → 안전하면 자율로 안 B(Stage 1 섀도우 게이트)까지, 위험 신호면 정지·보고 | **실행 완료(2026-07-21) = Exp-195**. §3 **"위험" 분기** 선택 — ko 12세션 3756프로브에서 발동 23건(0.61%)·순수 오탐 2건 확정으로 안전 조건 불충족 → **안 B 미착수**. 안 A는 ko/en `--repeat 3`까지 초과 달성(16세션). 후속 = `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` §4-0~§4-0-2 |
