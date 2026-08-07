# Goal Prompt — held/UTF-8 재조립 방출 손상(연속 발화 단어 유실) 근본원인 확정 + 수정 + 검증

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: 배포 PC 실사용 제보 증상 — **코드스위칭 없이 한 화자가 이어 말하는데 일부 단어가 누락**
> (`"중동전쟁"→"중쟁"`, `"이러한 플랫폼을 구축하는"→"이러한 구축하는"`) — 의 유력 경로로 이미 실측
> 규명된 **held/UTF-8 재조립 방출 손상**(Exp-172 경로 ⑷)을 단일 스코프로 수정한다.
> 디코더 컨텍스트에는 단어가 올바로 산출됐는데 **방출 계층이 손상/유실**시키는 순수 버그 성격이라,
> 고치면 트레이드오프 없는 순이득이어야 정상이다.
>
> ⚠️ **진행 규율 — 완전 자율 (사용자 장시간 부재 가정)**:
> - 모든 중간 판단(구현 세부·재측정 여부·스크리닝 기각·재시도)은 자율 결정하고 근거를 기록.
> - **유일한 사용자 질문 = 마지막 채택(머지) 여부.** master 머지는 절대 하지 않는다 — 브랜치 커밋까지만.
> - CLAUDE.md §3.8(범용 개선만, 데이터 특화 하드코딩 금지)·§3.3(Case B hard-fail) 우선.

---

## 0. 출발 지점 (2026-07-19 작성 — 반드시 먼저 확인)

- **master 상태 재확인**: 작성 시점 master = `8a9a8bd`(코드 최신분 = `03de591`, Exp-187/188/189 포함).
  `git log --oneline -10 master`로 최신화할 것 — **병렬 세션이 `exp/silence-hard-caseb-fix`(SILENCE_HARD
  Case B 루프, `docs/goal_prompt/GOAL_KOR1_SILENCEHARD_CASEB.md`)를 방금 완료**했으므로 그 머지 여부에
  따라 `tokens_alignment.py`가 전진했을 수 있다. 반드시 **세션 시작 시점 최신 master에서 분기**한다.
- **Exp 번호**: [EXPERIMENTS.md](../../EXPERIMENTS.md) 빠른참조에서 최신 번호 확인 후 +1 사용
  (작성 시점: **Exp-190은 SILENCEHARD 루프가 이미 사용** — 워크트리 `silence-hard-caseb-fix`에
  채택권고 상태로 기록됨, master 머지 여부는 사용자 결정 대기).
- **배포 실사용 제보 원문 (2026-07-19, 배포 PC = master `03de591` 적용 확인된 상태에서 발생)**:
  > 한국어, 영어 등 코드 스위칭 없이 한 발화자가 계속 이어서 말하는데 일부 단어가 누락되는 현상
  > — "중동전쟁" → "중쟁" / "이러한 플랫폼을 구축하는" → "이러한 구축하는"
- **기존 실측 근거 (Exp-172, `EXPERIMENTS_LOG.md`에서 `grep -n "held/UTF-8"` 원문 확인)**:
  - sbs1: 디코더 컨텍스트에 `"방어선이라는 겁니다"`·`"지상 플랫..."` **산출 확인**됐으나 방출은
    `"거대한 방 겁니다"`(음절 중간 손상)·`"지상 정의했습니다"`("플랫폼이라고" 통유실)로 나옴.
    컨텍스트에 mojibake(`방어�어�이라는어�`) 잔존 — held 재조립 경로 연루 정황.
  - 발생 카운트(R1 기준): bong1 Hold12/Prep13 · ytn2 Hold15/Prep15/**Drop2** · sbs1 Hold29/Prep29
    (한국어 비중 높은 파일일수록 다발 — 배포 제보의 한국어 낭독 증상과 정합).
  - 배포 제보 `"중동전쟁"→"중쟁"`은 sbs1 `"방어선이라는"→"방"`과 같은 **음절 중간 손상** 패턴,
    `"플랫폼을" 유실`은 sbs1 `"플랫폼이라고" 유실`과 동일 단어 수준으로 일치. **단 이 귀속은 아직
    정황**이다 — §3에서 로그로 확정하고, 다른 경로(QG streak 버퍼 폐기·세션초입 buffer 등)로 귀속되는
    사례는 스코프 격리(아래) 대상으로 보고만 한다.
- **문제의 코드 맵** ([align_att_base.py](../../whisperlivekit/simul_whisper/align_att_base.py),
  세션 시작 시 라인 재확인):
  - `:474-479` — 직전 청크의 `pending_incomplete_tokens`를 새 토큰 앞에 **prepend** 후 재분할.
  - `:535-543` (`_build_timestamped_words`) — U+FFFD(`�`) 포함 단어를 방출에서 **skip**.
    **위치 무관** — 중간 단어여도 skip된다.
  - `:567-597` (`_handle_pending_tokens`) — **마지막 단어(`split_words[-1]`)만** hold-for-retry.
    `MAX_PENDING_RETRIES=2` 초과 시 **drop**(`[UTF-8 Fix] Dropping` 로그), `MAX_PENDING_TOKENS=10`
    초과 시 즉시 폐기.
  - `:163` — `refresh_segment`가 `pending_incomplete_tokens`를 무조건 초기화(전환/refresh 상호작용 지점).
- **⚠️ 수정 이력 제약 (`:536-540` 주석)**: 현재 "부분 방출 대신 skip+hold" 동작 자체가 과거
  **선두조각 중복("미 미디어") 버그의 수정**이다. 이번 수정이 그 중복을 재발시키면 안 된다 —
  양방향(유실 금지 ∧ 중복 재발 금지)을 유닛테스트로 고정할 것.
- **스코프 격리 (이 루프에서 다루지 않는 것)**:
  - QG streak refresh **버퍼 폐기** 유실(Type B) → [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md) 별도 루프.
  - QG **텍스트 억제** 자체 → Exp-173에서 부당드롭 ≈1%로 개입 보류 확정([[project-exp173-logprob-separation-impossible]]).
  - 언어전환 경계 유실/중복 → [GOAL_BOUNDARY_TAIL_DUP.md](GOAL_BOUNDARY_TAIL_DUP.md) 별도 루프.
  - 세션초입 buffer 유실 → [docs/backlog/BACKLOG_CODESWITCH_FOLLOWUP.md](../backlog/BACKLOG_CODESWITCH_FOLLOWUP.md) §3.
- **공용 워크트리·venv 규약(반드시 준수)**: 새 워크트리의 `.venv`는 메인 저장소 Junction 공유
  (`mklink /J .venv ..\..\.venv`). `uv run`/`uv sync`/`uv pip`/`uv add`/`uv lock` **절대 금지**
  ([[shared-venv-uv-run-concurrency-hazard]]) — lint는 `.venv\Scripts\ruff.exe`, 테스트는
  `.venv\Scripts\python.exe -m pytest` 직접 호출. **측정은 반드시 cwd=워크트리에서**
  ([[worktree-eval-import-resolution]] — `.venv\Scripts\python.exe -c "import whisperlivekit;
  print(whisperlivekit.__file__)"`로 워크트리 경로 확인 후 진행). main 워크트리 코드 편집 금지.
- **측정 정본**: 경로 C만, provenance(`branch=…@… vbcable=ok`) 육안 확인. 스크리닝=`--repeat 1`,
  채택확정=`--repeat 3`(fail-fast 금지). diar-ON(Sortformer, CRT=3.0), turbo.
  **⚠️ 다른 세션과 경로 C 동시 측정 금지** — VBCable 루프백은 단일 물리 장치 + eval.py 고정 포트라
  병렬 측정 시 상호 전멸한다. 측정 전 다른 측정 세션 실행 여부를 확인한다.

---

## 1. 목표

방출 계층(held/UTF-8 재조립)이 디코더가 올바로 산출한 단어를 손상·유실시키는 것을 제거한다.
**목표 게이트**: ① 유닛 재현 케이스 전부 GREEN ② "미 미디어"류 선두조각 중복 재발 0
③ 실측에서 held/UTF-8 계열 유실 사례 감소(정답 대조) ④ WER worst-case 미회귀(순수 버그 수정이므로
회귀가 나오면 수정이 잘못된 것 — 원인 조사 우선).

## 2. 준비

- master 최신에서 분기 → 브랜치 `exp/utf8-held-emit-loss`, 워크트리 `worktrees/utf8-held-emit-loss`,
  `.venv` Junction 공유(§0).
- `EXPERIMENTS_LOG.md`에서 Exp-172 전체 블록(`grep -n "Exp-172"`)을 읽어 held/UTF-8 실측 정황
  (mojibake·Hold/Prep/Drop 카운트·sbs1 사례)을 파악한다.

## 3. 재현 + 정밀 진단

### 3-1. 오프라인 유닛 재현 (최우선 — 스트리밍 없이 RED 확보 가능성 높음)

tokenizer(byte-level BPE)로 한국어 다음절 단어가 토큰 경계에서 쪼개지는 시퀀스를 인위 구성해
`_split_tokens` → `_build_timestamped_words` → `_handle_pending_tokens` 경로를 직접 구동, 가설별
RED 케이스를 확보한다:

- **H1 (중간 단어 무보류 유실)**: U+FFFD가 **마지막이 아닌 중간 단어**에 있으면 `:535-543`이 방출
  skip하는데 `:567-597`은 마지막 단어만 hold → **재시도 없이 영구 유실**. 중간 단어에 U+FFFD가
  생기는 조건(prepend 재분할 불일치? rewind/철회 후 토큰 재조합?)을 함께 규명.
- **H2 (prepend 재조립 불일치)**: `:474-479` prepend 후 재분할 결과가 직전 청크에서 이미 방출된
  완성 단어와 어긋나거나(유실) 겹치는(중복) 케이스. 컨텍스트 mojibake(`방어�어�이라는어�`)의 생성
  경로가 여기인지 확인.
- **H3 (retry 소진/상한 drop)**: `MAX_PENDING_RETRIES=2` 초과 drop과 `MAX_PENDING_TOKENS=10` 초과
  폐기 — `[UTF-8 Fix] Dropping/Skipping` 로그로 실측 빈도 정량화(ytn2 Drop2 실측 있음).
- **H4 (상태 초기화 상호작용)**: `refresh_segment`(`:163`)·언어전환·화자전환 refresh가
  `pending_incomplete_tokens`를 초기화하거나 stale 재주입하는 시점에 hold 중이던 단어가 어떻게
  되는지(유실? 다음 세그먼트 오염?).

### 3-2. 실측 재현·귀속

- sbs1(실측 최다 Hold29) + kor1/kor2/kor3(한국어 낭독 — 배포 증상과 동일 성격)을 `--trace-tokens`
  + DEBUG 로그로 측정(sbs1·bong1·ytn2는 `--lan auto`, kor1~3은 `--lan ko` — run 분리).
- `[UTF-8 Filter] Skipping`/`[UTF-8 Fix] Holding/Prepending/Dropping` 로그를 전수 채집해 각 발생을
  정답 대조로 라벨링: **복구됨(다음 청크 재방출 성공) / 유실 / 손상 방출 / 중복**. 필요하면 skip
  시점에 단어·리스트 내 위치·hold 여부를 남기는 계측 로그를 먼저 추가(진단 전용, 게이팅 미연결)해도
  된다.
- 이 단계에서 배포 제보 패턴("음절 중간 손상"·"단어 통유실")이 어느 가설로 귀속되는지 확정한다.
  held/UTF-8이 아닌 다른 경로로 귀속되는 사례는 §0 스코프 격리에 따라 별도 보고 목록에 쌓는다.

## 4. 수정 방향 (자율 판단 — 로그·유닛 근거로 결정, 최소 변경 원칙)

- **A — hold 대상 확장**: 마지막 단어 한정(`split_words[-1]`)을 "모든 불완전 단어"로 확장하거나,
  중간 단어 U+FFFD 발생 자체가 상류(prepend/재분할) 버그면 상류를 수정. H1이 확정되면 최우선.
- **B — prepend 재조립 정합성**: 재주입 후 재분할 결과와 직전 방출분의 겹침/어긋남 처리(이미 방출된
  단어의 재방출 차단 ∧ 미방출 단어의 유실 차단). 토큰 시퀀스는 유지하고 텍스트 재조립만 방출 계층에서.
- **C — drop 시 완성 부분 구제**: retry 소진 drop 시 완성된 문자까지는 방출하는 방안 — 단 `:536-540`
  주석의 "미 미디어" 중복 이력과 정면 충돌 지점이므로, 도입하려면 중복 방지 조건을 유닛으로 고정.
- 새 상수·플래그 남발 금지. 어느 방향이든 **롤백 가능한 최소 diff**로.

## 5. TDD (필수, 이 순서로)

- 신규 `tests/test_utf8_held_emission.py`:
  - H1/H2/H3 각각의 RED 재현 케이스(수정 전 유실/손상 확인) → 수정 후 GREEN.
  - **회귀 고정**: 기존 "미 미디어" 시나리오(마지막 단어 불완전 → hold → 다음 청크 완전 단어 1회만
    방출)가 수정 후에도 그대로 동작 — 선두조각 중복 재발 0.
  - H4: refresh/전환 시 pending 상태 처리 케이스.
- `.venv\Scripts\python.exe -m pytest tests/ -q` 전체 통과, `.venv\Scripts\ruff.exe check .` clean.

## 6. 측정 계획

1. **스크리닝(`--repeat 1`)**: auto 세트(bong1/ytn2/sbs1, `--lan auto`) + ko 세트(kor1~3, `--lan ko`)
   — run 분리. 표적 지표 = held/UTF-8 계열 유실·손상 사례 수(§3-2 라벨링 재적용) + `[UTF-8 Fix]`
   Drop 카운트. WER은 방향 신호.
2. 유망하면 **채택확정(`--repeat 3`, fail-fast 금지)**: 동일 세트 + held-out 단회(ytn1 `--lan auto`,
   eng1 `--lan en`). 판정 = 화자분리 F1 worst-case 미회귀 → WER max 미회귀 → WER median → 문장분리 F1
   (CLAUDE.md §4). **Case B 0건 + 선두조각 중복 재발 0이 hard 게이트.**
3. **정성 필수**: 수정 전후 전사 대조 — 유실 복구 사례 before/after 인용, 신규 중복/환각 부작용 없음
   확인. 단일화자 파일 화자분리 F1 0%/100% 극단값은 지표 아티팩트([[Exp-186]], 판정 근거로 쓰지 않음).

## 7. 산출물

- `/log-experiment`로 Exp-N(§0에서 확인한 다음 번호) 기록(측정 언어모드 명시: ko+auto 양쪽).
- 문장 확정 로직 비대상(방출 계층)이므로 `docs/SENTENCE_FINALIZATION_LOGIC.md` 갱신은 원칙적으로
  불필요 — 단 수정이 확정 경계에 영향을 주게 되면 §7 규약대로 갱신.
- 브랜치 `exp/utf8-held-emit-loss` 커밋까지만. **master 머지 금지** — 사용자 승인 대기.

## 8. 완료 보고 (사용자에게 제시)

1. 한 줄 결론: 채택 권고 / 기각 권고 / 판단 유보.
2. 가설(H1~H4)별 판정 표 + 유닛 재현 결과.
3. 정량 표(스크리닝 + N=3 + held-out) + 표적 지표(유실·손상 사례 수, Drop 카운트) before/after.
4. 정성 핵심: 복구 사례 전사 인용, "미 미디어" 중복 재발 여부.
5. 스코프 밖으로 귀속된 사례 목록(다른 루프 인계용).
6. **사용자 질문**: `exp/utf8-held-emit-loss`를 master에 머지할지.

## 9. 회귀 교훈 (반드시 준수)

- **"미 미디어" 이력**: 현재 skip+hold 동작 자체가 과거 중복 버그의 수정 — 유실을 고치려다 중복을
  재발시키지 말 것(양방향 유닛 고정).
- **Exp-163 교훈의 역방향**: 이 루프는 출력 후처리 필터가 아니라 방출 계층 자체의 정합성 수정이다 —
  "필터 추가"로 흐르기 시작하면 스코프 이탈 신호.
- 배포 제보 특정 단어("중동전쟁" 등)를 하드코딩하는 수정 금지(§3.8) — 재조립 로직의 일반 수정만.
- 공유 `.venv` 가드레일·경로 C 동시 측정 금지(§0) 준수.
