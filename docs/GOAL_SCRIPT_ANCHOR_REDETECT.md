# Goal Prompt — 서두유실 근본원인 수정: 스크립트-앵커 재감지 (8시간 무인 자율 루프)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> [GOAL_CODESWITCH_BOUNDARY.md](GOAL_CODESWITCH_BOUNDARY.md) Stage 1의 실행판이다. Stage 0 계측(Exp-172)과
> retract_floor 수정(Exp-174, master `500d175`)이 끝난 상태에서, **아직 남아있는 ① 코드스위칭 서두유실의
> 근본원인 — 무음·화자전환 없는 연속 코드스위칭에서 언어 재감지 트리거가 아예 안 걸리는 구멍 — 을 메운다.**
>
> ⚠️ **진행 규율 — 이 루프는 완전 자율이다 (원 GOAL 문서의 Stage 체크포인트 오버라이드)**:
> 사용자는 약 8시간 동안 어떤 조작·응답도 할 수 없다. 따라서:
> - **모든 중간 판단(구현 세부·임계값 선택·재측정 여부·스크리닝 기각·재시도)은 자율 결정**하고 근거를 기록한다.
> - 원 문서의 "Stage 종료 시 사용자 보고 후 정지" 규칙은 **이 루프에서 적용하지 않는다.**
> - CLAUDE.md §4의 "게이트 애매 시 사용자 질의" 규칙은 **"즉시 질의" 대신 "판단 보류 + 최종 보고서에 질의
>   항목으로 축적"**으로 대체한다. 애매하면 **머지하지 말고** 증거를 정리해 둔다.
> - **유일한 사용자 질문 = 마지막 채택(머지) 여부.** 루프의 최종 산출물은 "채택 권고/기각 권고/판단 유보 중
>   하나 + 전체 근거 + 사용자가 예/아니오만 답하면 되는 형태의 질문"이다.
> - **master 머지는 절대 하지 않는다** — 채택 확정 측정까지 끝내고 브랜치에 커밋만 남긴 뒤 사용자 승인 대기.

---

## 0. 현재 상태 / 준비된 것 (2026-07-08)

- **master = Epoch 5 (E5, turbo 기질), `500d175`** = Exp-173(VAD min_silence 200ms) + Exp-174(retract_floor) 머지 완료.
- **게이트(max)**: [EXPERIMENTS.md](../EXPERIMENTS.md) STATE 상단 확정 게이트를 따른다
  (작성 시점: bong1≤30.5% / ytn2≤34.5% / sbs1≤16.1% — STATE가 갱신됐으면 STATE 우선).
  단 bong1은 Exp-174 채택 확정에서 max 39.3%(기존 필러/웃음 실패모드, 수정과 무관 확인)로 이미 게이트를
  넘은 채 채택된 전례가 있다 — bong1 max 판정 시 이 전례(필러/웃음 정성 일치 여부)를 함께 본다.
- **워크트리 준비 완료**: `worktrees/script-anchor-redetect` (브랜치 `exp/script-anchor-redetect`,
  분기점 master `500d175`), `.venv`는 메인 저장소 Junction 공유로 연결됨. 새로 만들 필요 없다.
- **잔존 증상 (사용자 실사용 보고, 2026-07-08)**: ① 코드스위칭 서두유실 잔존 + 코드스위칭 이후 환각 빈발.
  이 루프의 대상은 **①의 근본원인(재감지 트리거 부재)만**이다. 환각(AnchorRepeatFilter 사각지대, Exp-169)은
  별도 루프(C안)로 분리 — 이 루프에서 손대지 않는다.

## 1. 근본원인 (규명 완료 — 재조사 불필요)

- `LanguageSwitch` 마커는 `_apply_detected_language`의 `is_switch`일 때만 arm된다
  ([align_att_base.py](../whisperlivekit/simul_whisper/align_att_base.py) `:198-231`).
- 상시 경로 `_detect_language_if_needed`는 **`detected_language is None`일 때만 동작**(`:233-`) —
  최초 언어 확정 후 상시 재감지 없음.
- 중간 재감지 트리거 4종(짧은침묵≥0.5s · 긴침묵≥2.0s · 화자전환 eager · PLC=기본 None 비활성)은
  **무음·화자전환 없는 연속 코드스위칭에서 전부 미발동** → 구언어 고착 → 새 언어 서두 오디코드/유실(①)
  + 경계 마커 미생성으로 같은 line 접착(②).
- **Exp-172 실측 근거**: bong1 2건에서 반대 스크립트 streak **3~4단어 · 2배치 · 약 1.0초** 시점에야
  기존 트리거(침묵)가 뒤늦게 발동 — 그 사이 방출분이 철회·유실됨. → **임계 후보 N=3단어 / T≈1.0s.**
- **①′ 음차 환각(스코프 밖)**: locked-lang 상태에서 반대 언어 발화가 아예 그 언어 음차로 환각 디코딩되면
  출력 스크립트 반전이 없어 이 설계로 원리상 포착 불가(Exp-172 실측, bong1 "plastic sorry malang").
  이 루프에서 해결하려 들지 말 것 — 발생 시 정성 기록만 남긴다.

## 2. 설계 — 스크립트-앵커 재감지 게이트 (신규 게이트 1개, 기존 경로 무변경)

- **트리거**: 실제 방출 토큰의 스크립트가 잠긴 `detected_language`와 **연속 N단어(기본 3) 또는 T초(기본 1.0)**
  반전 유지 시. 판정은 `_is_opposite_script`([tokens_alignment.py](../whisperlivekit/tokens_alignment.py)
  `:61-72`, TTR 게이트 없는 순수 스크립트) 재사용 — 기존 `_is_script_mismatch_filler`(TTR≤0.6 반복 전제)가
  정상 전환을 통과시키던 사각지대를 메운다. **같은 스크립트 배치가 섞이면 streak 리셋**
  ("I think 그건"류 1~2단어 정상 삽입 오탐 방어).
- **동작**: 트리거 시 `detect_current_language(window_secs=2.0, min_prob=0.90)` 재감지 →
  **다른 언어 확신 시에만** `_apply_detected_language(new_lang)`(2.5s 트림 + 마커 arm + retract arm +
  retract_floor 계산 — Exp-174 이후의 기존 메커니즘 그대로 재사용) + 해당 배치 `timestamped_words=[]` 드롭
  (마커가 다음 신언어 배치 앞으로 정확히 이연; `backend.py:608-609` 가드 활용). 드롭한 서두는 트림이 남긴
  경계 오디오 재디코딩으로 복구(①), 구언어 오스탬프 잔존은 retraction 구역2가 정리(②).
  **`refresh_segment` 호출 금지(Exp-163). 같은 언어 재확정(재감지 결과 = 잠긴 언어) 시 아무것도 하지 않고
  streak만 리셋(Exp-169).** `detect_current_language`가 None(불확신)이면 미적용 + streak 유지.
- **삽입점**: `backend.py` `process_iter`의 ScriptMismatchFilter 블록 직후 · AnchorRepeatFilter 앞 —
  `decoded_text`/`seg_lang` 재계산 불필요. 신규 상태 `self._script_anchor_streak`(단어 리스트 + 시작시각)은
  `__init__` 초기화, 그리고 **긴침묵 리셋 블록 · `new_speaker` · 기존 게이트(ScriptMismatch/AnchorRepeat)
  발동 직후에 리셋 합류**(기존 `_script_mismatch_streak`/`_anchor_repeat_window` 리셋 위치와 동일한 곳).
- **Exp-160 면역 논거**: 이 트리거는 lang_id **확률**이 아니라 **출력 스크립트의 지속 반전**에만 반응한다.
  ytn2 스퓨리어스 전환 당시 출력은 계속 한글이었으므로 streak이 쌓이지 않아 미발동 — 순수 확률 기반
  주기 체크(PLC) 재도입이 아니다.
- ko↔en 대칭. 특정 문구·데이터 특화 하드코딩 없음(CLAUDE.md §3.8). 라틴 숫자·기호만인 단어는
  스크립트 중립으로 취급해 streak에 넣지 않는다(기존 `_is_opposite_script` 의미론 따름).
- **롤백 장치**: 신규 게이트를 조기 return 플래그 1개(예: 모듈 상수 또는 config 필드)로 무력화 가능하게
  만들어 격리 용이하게 한다. 기존 경로 코드는 리셋 합류 지점 외 변경하지 않는다.

## 3. 실행 계획 (자율 — 순서대로, 각 단계 판단 근거를 기록하며)

1. **사전 확인**: 워크트리 cwd에서 import 경로 검증([worktree-eval-import-resolution] 함정 — 측정은
   반드시 cwd=워크트리에서, `--model-dir`·`--files`·`--sortformer-model`은 메인 저장소 절대경로 지정).
   VBCable 상태 확인(`verify_loopback`, `vbcable=ok`).
2. **유닛테스트 먼저 작성**: 신규 `tests/test_script_anchor_redetect.py`
   (`tests/test_lang_redetect.py`의 MagicMock 관례를 따른다) — 최소 다음 케이스:
   N-1 미발동 / N 발동, T초 경과 발동, 중간 같은스크립트 삽입 시 streak 리셋,
   `detect_current_language`=None 시 미적용 + streak 유지, 같은 언어 재확정 시 no-op + streak 리셋,
   트리거 시 배치 드롭 + `pending_language_switch` set, en↔ko 대칭, 긴침묵/`new_speaker` 후 streak 리셋,
   무력화 플래그 동작. 전부 통과 후 다음 단계.
3. **스크리닝 (`--repeat 1 --trace-tokens`)**: 테스트셋 3파일(bong1+ytn2+sbs1). diar-ON(Sortformer),
   CRT=3.0, PLC=None, beams=2, turbo — [.claude/commands/eval.md](../.claude/commands/eval.md) 기본 사용법.
   - 정성 확인 필수: 서버 로그에서 신규 게이트 발동 로그(`[ScriptAnchorRedetect]` 태그로 로깅할 것)와
     `[LangSwitch]` 마커·`[RetractScan]` 상호작용을 확인. Exp-172가 잡은 bong1 후보 구간(~12s, ~69s)에서
     기존 침묵 트리거보다 **먼저** 발동하는지 본다.
   - catastrophic(게이트 대폭 초과·환각 폭주·stall)이면: 원인 분석 → 파라미터(N/T/min_prob) 1~2회 조정
     재스크리닝 → 그래도 catastrophic이면 **기각 권고로 전환**하고 증거 정리(무한 튜닝 금지 — 조정은
     총 3회까지).
   - ytn2 방송클로징 환각·bong1 필러 storm이 **신규 게이트 발동과 인과로 엮여** 재발하면 즉시 해당 조정
     또는 기각 판단(Exp-160/163 회귀 교훈).
4. **채택 확정 (`--repeat 3 --trace-tokens`)**: 스크리닝이 유망할 때만. **fail-fast 금지** — 3회 전부 측정,
   median+min/max/stdev 기록. 하니스 버그(VBCable 무음/사망, 포트 충돌, sibling 세션 충돌)만 즉시
   중단·수리 후 재실행([vbcable-loopback-instability] — 재부팅은 불가하므로 Audiosrv 재시작·프로세스 정리로
   복구 시도, 복구 불가면 그 시점까지 결과로 보고서 작성).
5. **held-out (ytn1+eng1, 단회)**: 채택 확정이 게이트를 통과(또는 bong1 전례성 초과)할 때만.
6. **정성 평가**: `.omc/transcripts/` 전사를 정답과 대조 — ⓐ Exp-172 후보 구간 서두 보존 여부,
   ⓑ 신규 게이트 발동 위치가 전부 정당한 전환이었는지(오탐 0 확인), ⓒ ②(접착) 부수 개선 여부,
   ⓓ ①′ 음차환각 잔존 기록(스코프 밖, 기록만).
7. **기록**: `/log-experiment`로 Exp-175(또는 다음 번호) 작성 — EXPERIMENTS_LOG 전체 서술 +
   EXPERIMENTS.md 빠른참조 1행. 커밋은 워크트리 브랜치에만.
8. **최종 보고서 작성 후 정지**: 아래 §5 형식. **머지하지 않는다.**

## 3.5 잔여 시간 자율 탐사 (본 임무 완료 후 — 시간이 남는 동안 계속, 유휴 정지 금지)

본 임무(§3 1~8)가 끝났는데 시간이 남으면 정지하지 말고 아래를 우선순위 순으로 반복한다.
목적은 **다음 개선 루프의 착수 대상을 실측 근거와 함께 미리 준비해 두는 것**이다.

1. **N/T 임계 스윕**: N∈{2,3,4} 또는 T∈{0.8,1.0,1.5} 스크리닝을 추가해 보고서에 첨부 —
   단 채택 확정 측정(N=3)을 다시 하지는 않는다(스윕은 방향 신호용).
2. **실패 사례 수집 측정**: 테스트셋(+여유 시 held-out) 스크리닝 회차를 추가로 돌려
   (`--repeat 1 --trace-tokens`) 전사·서버 로그를 정성 분석하고, 잔존 실패 사례를
   **파일·시각·정답/전사 대조·로그 태그**와 함께 카탈로그화한다. 관심 유형:
   - ① 서두유실 잔존 사례(이번 수정이 못 잡은 케이스 — 트리거 미발동인지 재감지 불확신인지 구분)
   - ①′ locked-lang 음차 환각(스코프 밖이지만 발생 빈도·구간 축적)
   - ② 한↔영 접착(마커 미생성 잔존 여부)
   - 코드스위칭 직후 필러/웃음 환각(AnchorRepeatFilter 사각지대 — Exp-169의 3+2 서브클러스터 유형인지 판별)
   - 세션초입 buffer 유실 · held/UTF-8 재조립 손상(Exp-172 보조 경로)
3. **개선 방향 도출**: 수집된 실패 유형별로 근본원인 가설 + 개선 방향(수정 후보 파일:라인,
   예상 리스크, 관련 회귀 교훈)을 정리한다. **구현하지 않는다** — 분석·설계 제안까지만.
4. **산출물**: `docs/BACKLOG_CODESWITCH_FOLLOWUP.md`에 우선순위 순으로 기록(최종 보고서에서 링크).
   각 항목은 "증상 → 실측 근거(로그/전사 인용) → 가설 → 제안 방향 → 예상 게이트 리스크" 형식.

**탐사 규율**: ⓐ 코드 변경은 §3-3의 조정 3회 상한 안에서만 — 탐사 단계에서 신규 기능 구현 금지.
ⓑ 탐사 측정은 스크리닝(`--repeat 1`)만. ⓒ 매 회차 VBCable 상태 확인, 하니스 문제로 측정이
무의미해지면(복구 실패) 탐사를 중단하고 그때까지 결과로 보고서를 마무리한다. ⓓ 발견이 본 임무의
채택 판정을 뒤집을 증거(예: 신규 게이트발 환각의 인과 사례)라면 탐사 산출물이 아니라 **본 보고서의
게이트 판정에 반영**한다.

## 4. 채택 게이트 (hard — 최종 권고 판정 기준)

1. ytn2 방송클로징 환각 · bong1 필러 storm이 **신규 게이트 발동과 인과관계로** 재발한 사례 0건
   (인과 무관한 기존 실패모드 재현은 로그 시간순 대조로 구분 — Exp-174 판정 방법 재사용).
2. Exp-172 후보 구간(또는 동종 구간)에서 신규 게이트 발동 → `[LangSwitch]` 마커 방출 → 서두 보존이
   실제로 관측(정성).
3. 테스트셋 WER max 미회귀(bong1은 Exp-174 전례 — 필러/웃음 정성 일치 시 별도 표기하고 판단 유보 항목으로).
4. held-out 미회귀.

F1 변동은 지표한계(§3.3 온점 metric 미구현) 감안, WER 우선. **①은 §3.2 불변 제약(코드스위칭 무결성)
직결 기능이므로, 정량 게이트가 애매해도 자율 기각하지 않는다 — "판단 유보 + 증거 정리 + 사용자 질의"로
보고서에 남긴다**(CLAUDE.md §4 자율 기각 금지 조항의 이 루프 적용 형태).

## 5. 최종 보고서 형식 (루프 종료 시 사용자에게 제시)

1. **한 줄 결론**: 채택 권고 / 기각 권고 / 판단 유보 중 하나.
2. 정량 표(스크리닝·N=3·held-out, baseline 대비), 정성 핵심 사례(서두 보존 before/after 전사 인용),
   게이트 4항 판정 표.
3. 자율 결정 이력(임계값 선택·조정·재측정 근거 요약).
4. 미해결·후속 항목(①′ 음차환각 관측 기록, 환각 C안 연계 사항) + §3.5 탐사를 수행했으면
   `docs/BACKLOG_CODESWITCH_FOLLOWUP.md` 링크와 상위 3개 항목 요약.
5. **사용자 질문은 단 하나**: "master에 머지(채택)할까요?" — 예/아니오로 답할 수 있게.

## 6. 회귀 교훈 (반드시 준수 — 원 GOAL 문서에서 이월)

- **Exp-160**: 순수 확률 기반 주기 재감지 금지 — 실제 출력 스크립트 근거 트리거만.
- **Exp-163**: 드롭 시 `refresh_segment` 호출 금지(재환각+정렬 교란).
- **Exp-169**: `_apply_detected_language`는 실제 다른 언어 확신 시에만 호출(같은 언어 재확정 시 no-op).
- **Exp-166**: KEEP_SECS 스윕만으로는 서두유실 미완화 — 이 루프는 트리거 부재를 메우는 것이지
  파라미터 스윕이 아니다.
- **공유 .venv 가드레일**: `uv run`/`uv sync`/`uv pip` 절대 금지. lint는 `.venv\Scripts\python.exe -m ruff`
  직접 호출. pytest도 `.venv\Scripts\python.exe -m pytest`.

## 7. 기록·연동 문서 (채택 시 사용자 승인 후 동일 작업 단위 — 보고서에 체크리스트로 포함만)

- [docs/SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) §3.2(진입점 4종→5종에
  "스크립트-앵커 재감지" 추가) · §5(N·T·streak 상수 행 추가, "잠정" 태그).
- master 머지 후 `/update-master-changes`. epoch 판단: Exp-168/171/174 전례(경계 서브시스템 = E5 유지)를
  따르되 STATE 세대경계 규칙으로 최종 판단.
