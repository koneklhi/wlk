# 일시중단 기록 — ScriptAnchor 약어 가드 (2026-07-16)

> 사용자 지시로 **일시 중단**. 진행 중이던 프로세스는 모두 이미 종료된 상태로 확인됨(추가 kill 불필요 —
> 아래 §2 참조). 이 문서는 재개 시 "어디서 멈췄고 무엇부터 해야 하는지"만 담는다. 원 계획은
> [GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md](GOAL_SCRIPTANCHOR_ACRONYM_GUARD.md) 그대로 유효 — 재설계 불필요.

## 0. 중단 시점 요약

- **중단된 작업**: Stage 3(채택 확정, `--repeat 3`) **ON 측정**. 대상 6파일(bong1/ytn2/sbs1/kor1/kor2/kor3) 중
  **첫 파일 `bong1.wav` 회차 2/3 도중** 프로세스가 끊겼다(`.omc/benchmarks/eval_20260716_stage3_ON_adoptN3.stdout.log`
  마지막 줄이 `[C] bong1.wav 회차 2/3` 로 재생/캡처 로그 없이 끝남 — 크래시 또는 중단, 정상 완료 아님).
- **OFF 대응 런은 완료됨**: `eval_20260716_stage3_OFF_adoptN3.json`(2026-07-16 10:31, `file_summaries` 6건 전부 존재) —
  아래 §1-3 표 참조.
- 브랜치: `exp/scriptanchor-acronym-guard`, 워크트리 `worktrees/scriptanchor-acronym-guard`, 커밋은 **`747e47f` 1개뿐**
  (P1 구현+단위테스트). 그 외 스테이지 산출물은 전부 `.omc/`(대부분 gitignore 대상 — 로컬 디스크에는 남아있음, 커밋 안 됨).

## 1. 프로세스/환경 상태 (확인 완료, 추가 조치 불필요)

- `eval.py`·`basic_server` 관련 python 프로세스: **없음** (재확인 시 `Get-CimInstance Win32_Process -Filter "name='python.exe'"`로 `eval.py`/`basic_server` 커맨드라인 검색).
- 포트 8901: `TimeWait`, OwningProcess=0 — 리스닝 중인 서버 없음.
- 백그라운드 서브에이전트(`afe39a42b1d682427`): `TaskStop` 시도 결과 "No task found" — 이미 자체 종료된 상태였음.
- `backend.py`의 `SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED`는 현재 **`True`(커밋된 기본값)로 깨끗한 상태** — 짝지음 A/B용 임시 토글이 남아있지 않음(`git status`/`git diff` 클린, untracked `.omc/**` 스크래치만 있음).
- 단위테스트: `pytest tests/test_script_anchor_redetect.py` **30 passed** (재개 시 재확인 권장, 1회 재실행이면 충분).

## 2. 완료된 측정 결과 (재사용 가능)

### 2-1. Stage 1 스크리닝 — 표적 코어 (`--repeat 2 --trace-tokens`, 2026-07-15)

| 파일 | OFF median WER (min/max) | ON median WER (min/max) | 비고 |
|---|---|---|---|
| kor2(표적) | 108.0% (93.8/122.2) | 98.6% (77.8/119.4) | 개선 방향이나 **N=2라 결론 아님**, 여전히 catastrophic — Stage3 N=3로 재확인 필요 |
| kor1 | 50.6% (36.8/64.3) | 26.3% (23.4/29.2) | 뚜렷한 개선 신호 |
| kor3 | 57.6% (55.6/59.6) | **77.5%** (72.2/82.8) | ⚠️ **악화 신호** — §3 참조, 최우선 확인 대상 |
| ytn2(커버리지 감시) | 19.5%, 화자F1 85.7% | 16.3%, 화자F1 82.0% | 대체로 유지, 화자F1 소폭 하락(N=2, 방향신호) |

출처: `.omc/benchmarks/eval_20260715_stage1_{OFF,ON}_core_R2.json` + 동명 `.stdout.log`.

### 2-2. Stage 1 회귀 감시 (`--repeat 1`, bong1+sbs1+kinno, 2026-07-16 08:20/08:43)

| 파일 | OFF (WER/화자F1/문장F1) | ON (WER/화자F1/문장F1) |
|---|---|---|
| bong1 | 32.3% / 53.7% / 16.0% | 37.5% / 58.5% / 24.0% |
| sbs1 | 8.3% / 100.0% / 94.7% | 13.1% / 50.0% / 84.2% |
| kinno(정성, 게이팅 제외) | 28.5% / 71.0% / 13.3% | 25.6% / 77.4% / 37.5% |

출처: `.omc/benchmarks/eval_20260715_stage1_{OFF,ON}_regress_R1.json`. N=1이라 편차 범위 내일 가능성 큼 — Stage3 N=3가 판정 기준.

### 2-3. Stage 3 채택 확정 OFF (`--repeat 3`, 전체 6파일, 2026-07-16 10:31 완료)

| 파일 | WER median (min/max) | 화자F1 median | 문장F1 median |
|---|---|---|---|
| bong1 | 35.6% (35.0/47.4) | 53.7% | 18.2% |
| ytn2 | 20.7% (18.7/21.2) | 72.0% | N/A |
| sbs1 | 10.1% (9.5/22.0) | 80.0% | 90.0% |
| kor1 | 31.6% (19.9/50.9) | 0.0%(단일화자) | 69.2% |
| kor2 | 79.2% (72.9/120.8) | 0.0%(단일화자) | 37.0% |
| kor3 | 71.5% (51.0/86.1) | 0.0%(단일화자) | 62.9% |

출처: `.omc/benchmarks/eval_20260716_stage3_OFF_adoptN3.json`. **이 OFF 결과는 유효 — 재실행 불필요.**

### 2-4. Stage 3 채택 확정 ON — **무효, 재실행 필요**

- `eval_20260716_stage3_ON_adoptN3.json` **파일 자체가 없음**(런이 끝까지 안 갔으므로 저장 안 됨).
- `.omc/transcripts/`에 `bong1_C_R1~R3.txt` 등 파일이 존재하지만, ON 런이 bong1 회차 2/3에서 끊겼기 때문에
  **R2/R3 전사가 ON의 것인지 이전 OFF 런의 잔재인지 신뢰 불가**(전사 파일명이 회차별로 덮어써지는 방식).
  **kor1/kor2/kor3/sbs1/ytn2 전사도 마찬가지로 이번 ON 런에서 갱신되지 않았으므로 OFF 시점 값으로 봐야 한다.**
  → **재개 시 Stage 3 ON은 6파일 전체를 처음부터 다시 돌려라.** 부분 재사용 시도 금지(짝지음 A/B 신뢰성 훼손).

## 3. 재개 전 반드시 먼저 확인할 이슈 — kor3 방향 신호 역전

Stage 1 스크리닝(N=2)에서 **kor3만 유일하게 OFF(57.6%)보다 ON(77.5%)이 더 나빴다**. 이 goal의 가드는
kor2류 "약어 철자 낭독" 오발동을 없애는 것이 목적인데, kor3에는 다른 결함(§스코프 밖 — 원 목표 문서
§3 "일반 재디코딩 중복 확정 churn" 부기 참조)이 있어 이 가드가 그 결함과 상호작용해 악화시켰을 가능성이 있다.
N=2 스크리닝은 방향 신호일 뿐이므로 **Stage 3 ON N=3 완주 전에는 결론 내지 마라** — 그러나 재개 후
가장 먼저 볼 지표가 이것이어야 한다. 만약 N=3에서도 kor3 악화가 재현되면:
- 원 목표 문서 §4 게이트 2번("WER max 미회귀")에 저촉 여부 판단,
- kor3 전사를 직접 읽어 이 가드의 `acronym-skip` 로그와 kor3의 오류 발생 지점이 실제로 연관되는지
  (즉 이 가드가 유발한 것인지, 무관한 기존 결함의 변동성인지) 인과 확인,
- 필요시 판단 유보 + 사용자 질의(원 목표 문서 §4 마지막 문단 규정대로).

## 4. 재개 시 실행 순서

1. `cd worktrees/scriptanchor-acronym-guard` (또는 이 경로를 서브에이전트 workdir로 재지시), `git status`로
   이 문서 작성 시점과 상태가 같은지 재확인.
2. VBCable 단일 자원 충돌 없는지 확인(다른 세션이 측정 중인지 프로세스 확인) 후에만 측정 시작.
3. **Stage 3 ON 전체 재실행**(`--repeat 3 --trace-tokens`, 6파일: bong1/ytn2/sbs1/kor1/kor2/kor3) →
   `eval_<ts>_stage3_ON_adoptN3.json`으로 저장.
4. §3의 kor3 역전 여부를 최우선으로 판정, OFF(§2-3)와 짝지음 비교해 원 목표 문서 §4 게이트 6항목 전부 판정.
5. Stage 2(`ACRONYM_MAX_ALLCAPS_LEN` {4,6,8} 로그 감사)가 착수됐는지 이 워크트리에 흔적이 없음 —
   **미착수로 보임**. Stage 3 결과가 애매하면(특히 kor3) 이 단계로 돌아가 파라미터 보수화 검토.
6. held-out(ytn1+eng1 단회, kinno N=3 정성 — 지금은 kinno N=1만 있음, 부족분 보완).
7. `docs/GOAL_SCRIPTANCHOR_ACRONYM_GUARD_REPORT.md` 작성(원 목표 문서 §5 형식) — 이 파일 내용을 흡수해서
   최종 보고서에는 이 파일 대신 정리된 결론만 남기고, 이 pause note는 보고서 완성 후 삭제하거나 "히스토리" 절로 축약해도 된다.
8. master 머지는 여전히 금지 — 사용자에게 머지 여부만 질의.

## 5. 산출물 경로 색인

- 구현 커밋: `747e47f` (`whisperlivekit/simul_whisper/backend.py`, `tests/test_script_anchor_redetect.py`)
- Stage1 core: `.omc/benchmarks/eval_20260715_stage1_{OFF,ON}_core_R2.{json,stdout.log}`
- Stage1 regress: `.omc/benchmarks/eval_20260715_stage1_{OFF,ON}_regress_R1.{json,stdout.log}`
- Stage3 OFF: `.omc/benchmarks/eval_20260716_stage3_OFF_adoptN3.{json,stdout.log}`
- Stage3 ON(무효, 참고용): `.omc/benchmarks/eval_20260716_stage3_ON_adoptN3.stdout.log`(json 없음)
- 서버 로그: `.omc/server_logs/server_<file>_C_R<n>_<ts>.log`
- 전사: `.omc/transcripts/*_C_R*.txt` (§2-4의 신뢰성 주의 적용)
- 토큰 트레이스 덤프(수동 분석용, 커밋 안 됨): `.omc/benchmarks/_bong1_{OFF,ON}_{full,snip}.txt`, `_ytn2_{OFF,ON}_dump.txt`

## 6. 가드레일 재확인 (원 목표 문서 §6과 동일, 재상기용)

- `uv run`/`uv sync`/`uv pip` 금지 — pytest/ruff는 `.venv\Scripts\python.exe -m ...` 직접 호출.
- 측정은 cwd=이 워크트리, `--model-dir`/`--sortformer-model`은 메인 저장소 절대경로.
- VBCable 단일 자원 — 동시 측정 금지, 시작 전 프로세스 확인.
- Stage 3(채택 확정)는 fail-fast 금지 — N=3 전부 측정, 중간에 나빠도 멈추지 않음(이번처럼 **환경 문제로 중단된 경우는 예외** — 그 경우 처음부터 다시).
- master 머지 금지, 브랜치 커밋만.

## 7. 재개 시도 기록 (2026-07-16, 이번 세션) — 공유 `.venv` 파손으로 재차 중단

**결론: 이번 세션에서 Stage 3 ON 측정에 착수조차 못 함.** 측정 시작 전 상태 확인 순서(§4)를 따르던 중
`.venv\Scripts\python.exe -m pytest tests/test_script_anchor_redetect.py -q` 1단계에서 즉시
`No pyvenv.cfg file` 에러로 실패.

**진단**:
- 메인 저장소 공유 `.venv`(`C:\Users\A040-000-0001\Desktop\260605wlk\wlk\.venv`, 이 워크트리는 Junction 공유)가
  **`Lib` 디렉터리 자체가 통째로 없음** — 루트에 `Scripts`(28개 항목만, 대부분 실행파일 자체는 남아있으나
  `pyvenv.cfg` 없음)와 `share`만 존재. `python.exe`를 직접 실행해도 `No pyvenv.cfg file`로 즉시 실패 —
  즉 torch/whisperlivekit/transformers 등 **패키지 전부 증발**, 인터프리터 자체가 기동 불가.
- `.venv` 폴더 mtime = `2026-07-16 12:38`(Scripts), `13:04`(venv 루트) — **오늘, 이 세션 시작 직전**. 이 goal
  루프와 무관한 **다른 세션의 작업(추정: 배포/wheelhouse 패키징 등에서 공유 venv에 실수로 `uv venv --clear`류를
  실행)이 원인일 가능성이 높음** — CLAUDE.md §4에 명시된 기지 사고 패턴("배포/wheelhouse 작업을 공유 Junction
  `.venv`에 실행 → clobber")과 정확히 일치. 단, IDE Jedi 언어서버 잠금으로 인한 반쪽 손상(memory
  `venv-clear-ide-lock` 케이스)보다 **더 심함** — 그때는 `pyvenv.cfg`만 소실됐지만 이번은 `Lib` 전체 소실.
- 확인한 것: 현재 `uv venv`/`uv sync`/`uv pip` 관련 프로세스는 **실행 중이 아님**(전체 프로세스 목록 조회,
  ouroboros mcp serve 프로세스들만 다수 — 무관). 즉 복구 작업이 진행 중도 아니고 그냥 깨진 채 방치된 상태.
  디스크 용량 문제 징후는 없음(`Get-PSDrive C` 조회, 특이사항 없음).
- 이 워크트리 자체 상태는 §0 기록 그대로 클린(`git status` 재확인 — untracked `.omc/**` 스크래치만, 커밋
  `ae8dd48` HEAD 동일). **이번 세션에서 코드/문서/커밋 변경 없음**(이 pause note 갱신 1건 제외) — Stage 3 ON
  측정을 포함해 아무 실행도 하지 못했다.

**시도하지 않은 것(의도적)**: `uv sync`로 직접 복구 시도 — 하지 않았다. 이유:
1. 이 goal의 가드레일과 CLAUDE.md §4가 공유 `.venv`에 대한 `uv run`/`uv sync`/`uv pip`를 **절대 금지**하고,
   복구 필요 시에도 **"사용자 확인 후"**로 명시.
2. 공유 자원이라 다른 워크트리/세션에 영향 — 내가 일방적으로 복구를 시도하다 실패하면 피해가 더 커질 수 있음
   (특히 IDE가 아직 옛 인터프리터를 물고 있다면 재손상 위험 — CLAUDE.md §4 캐비어트).
3. 원인이 확인되지 않은 채(어느 세션이 언제 무엇을 실행했는지 모름) 성급히 재생성하면 그 세션이 다시
   충돌할 수 있음.

**재개 시 필요 조치 (사람/사용자 판단 필요 — 다음 세션이 자율로 실행하지 말 것)**:
1. 사용자에게 공유 `.venv` 파손 사실 보고 및 복구 승인 요청.
2. 복구 시 CLAUDE.md §4 절차 준수: IDE(Antigravity/Jedi) Python 인터프리터를 공유 `.venv`에서 먼저 분리(또는
   IDE 종료) → 독립적인 위치(가급적 배포용 워크트리 등)에서 `uv sync --extra diarization-sortformer
   --extra vbcable --extra cu128`로 메인 `.venv` 재생성.
3. 복구 후 `.venv\Scripts\python.exe -m pytest tests/test_script_anchor_redetect.py -q`로 30 passed 재확인 —
   그 다음에만 §4의 3번(Stage 3 ON 전체 재실행)으로 진행.
4. 복구 전까지 이 goal 루프(및 이 `.venv`를 공유하는 다른 모든 워크트리)는 **측정 불가 상태**임을 인지.

이 goal 자체의 설계·게이트·§1~§5 내용은 전부 그대로 유효 — 재설계 불필요. 막힌 지점은 순수 인프라(공유
`.venv`) 문제다.

**추기 (같은 날, 복구 완료·재개함)**: 오케스트레이터가 사용자 확인 거쳐 공유 `.venv` 복구 완료
(IDE Jedi 프로세스 종료 → `uv sync --extra diarization-sortformer --extra vbcable --extra cu128 --inexact` →
`pyvenv.cfg` 수동 작성). 이 워크트리에서 `torch 2.11.0+cu128 cuda=True`/`transformers 4.53.3`/
`whisperlivekit`(워크트리 경로) import 정상 + `pytest tests/test_script_anchor_redetect.py -q` 30 passed
재확인. §4 재개 절차(Stage 3 ON 전체 재실행)로 진행한다.
