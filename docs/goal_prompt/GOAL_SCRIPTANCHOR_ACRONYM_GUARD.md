# Goal Prompt — ScriptAnchorRedetect 철자 낭독(약어) 오발동 가드 (무인 자율 루프)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: 한국어 문장 내 **영문 약어 철자 낭독**("GP·GOP" → 방출 토큰 `G`/`P`/`GOP`/`GPGOP`)이
> Exp-175 스크립트-앵커 재감지 게이트의 Latin 3단어 streak을 채워 **ko→en 오전환 + 전환 트림으로
> 직전 오디오 9.7~12.0s 비가역 폐기 + 복귀 전환 + 재디코딩 중복 확정 폭주**(kor2 WER 70~101%)를
> 일으키는 오발동을 제거한다. 근본원인은 실측 로그로 규명 완료(§1). 이 루프는 가드를 구현·측정·기록하고
> 채택 여부만 사용자에게 묻는다.
>
> ⚠️ **진행 규율 — 완전 자율 (사용자 장시간 부재 가정)**:
> - **모든 중간 판단(구현 세부·임계값 선택·재측정 여부·스크리닝 기각·재시도)은 자율 결정**하고 근거를 기록.
> - CLAUDE.md §4 "게이트 애매 시 사용자 질의"는 이 루프에서 **"판단 보류 + 최종 보고서에 질의 항목 축적"**으로 대체.
> - **유일한 사용자 질문 = 마지막 채택(머지) 여부.**
> - **master 머지는 절대 하지 않는다** — 채택 확정 측정까지 끝내고 브랜치에 커밋만 남긴 뒤 사용자 승인 대기.
> - ★ **비회귀 제약: Exp-175 게이트의 기존 커버리지(진짜 코드스위칭 감지)를 잃으면 안 된다.**
>   ytn2 짝지음 A/B에서 게이트 정상 발동이 사라지거나 화자분리 F1·WER worst-case가 회귀하면
>   파라미터 보수화 또는 기각 권고로 전환한다(§4).

---

## 0. 현재 상태 / 준비 (2026-07-15)

- **master = E5(turbo), `d847cfd`** (Exp-179 세션 초입 언어 프로브 머지 `27f3f3c` 포함). 이 goal은 그 위에서 출발한다.
- **출발 증거 (같은 날 실측 — 반드시 먼저 읽을 것)**:
  - Exp 기록: `EXPERIMENTS_LOG.md`의 **Exp-178·Exp-179 블록**(`grep "Exp-178"` / `"Exp-179"`) — 특히 Exp-179
    "분석 (정성)"의 [신규 규명 ①] 항목이 이 goal의 근본원인 서술이다.
  - **핵심 사례 로그 (OFF=master)**: `.omc/server_logs/server_kor2_C_R1_20260715_094510.log` 라인 ~923-925 ·
    `server_kor2_C_R2_20260715_094722.log` 라인 ~1103-1105 — `[ScriptAnchorRedetect] 반대스크립트 streak 3단어/0.56s
    → 재감지 ko→en — 전환 적용·배치 드롭: G` → `[LangSwitch] 전환 전 오디오 9.68s/12.02s 절단` 인과가 그대로 있다.
  - ON(워크트리 `session-start-lang-probe`) 로그에서도 동일 발생 — 프로브와 무관한 master 결함임을 교차 확인 가능.
  - 벤치마크: OFF `.omc/benchmarks/eval_20260715_0940_kor_trace_x2.json` ·
    ON 확정 `worktrees/session-start-lang-probe/.omc/benchmarks/eval_confirm_{test3_N3,kor_N3,kinno_N3,heldout}.json`.
  - 전사(중복 폭주 육안 확인): `.omc/transcripts/kor2_C_R{1,2}.txt` — "DUP에 대한/GPGOP에 대한 …" 프리픽스 4~5회 누진 재확정.
- **음원**: `test_data/kor2.wav`(표적 — 군 브리핑 낭독체, "GP·GOP" 철자 낭독 포함) + 정답 `test_data/kor2_speak,sentence_sperate.txt`(canonical, 커밋됨).
  kor1/kor3도 존재하나 이 goal의 표적 오발동은 kor2에서만 재현 확인됨.
- **동일 날짜 기준 수치 (참고용 — 판정은 짝지음 A/B 순효과로)**:

  | 파일 | WER med / max | 화자F1 med | 비고 |
  |---|---|---|---|
  | kor2 (표적) | 95.8 / 101.4% (master 시절 70.8 / 71.5) | — (단일화자) | ScriptAnchor 오발동 2회/런 고정 재현 |
  | bong1 | 34.4 / 39.9% | 60.5% | Exp-179 확정 N=3 |
  | ytn2 | 17.7 / 30.0% | 72.7% | 진짜 코드스위칭 — **커버리지 감시 대상** |
  | sbs1 | 10.1 / 15.5% | 80.0% | |
  | ytn1 / eng1 (held-out) | 12.3% / 2.9% | 73.7 / 100% | 단회 |

- **워크트리 준비 (자율 수행)**: 최신 master에서 `exp/scriptanchor-acronym-guard` 브랜치 + `worktrees/scriptanchor-acronym-guard` 워크트리.
  - `.venv`는 **메인 저장소 Junction 공유**(`cmd /c mklink /J .venv ..\..\.venv`) — 새로 만들지 않는다.
  - **측정은 반드시 cwd=워크트리에서**(editable 설치 함정 — `.venv\Scripts\python.exe -c "import whisperlivekit; print(whisperlivekit.__file__)"`로
    워크트리 경로 확인). `--model-dir`·`--files`·`--sortformer-model`은 메인 저장소 절대경로. 측정 전 provenance `vbcable=ok` 육안 확인.
  - **동시 측정 금지**: VBCable은 단일 자원 — 다른 세션이 음성 재생/측정 중이면 겹쳐서 양쪽 다 오염된다(금일 실사고 1회).

## 1. 근본원인 (규명 완료 — 2026-07-15 실측 로그. 재조사 불필요)

**인과 사슬 (kor2, 두 런 모두 동일)**:

1. 한국어 낭독 중 "GP·GOP 유무인 GP·GOP에 대한 …" 구간에서 디코더가 라틴 토큰(`G`/`P`/`GOP`/`GPGOP`류)을 연속 방출.
2. `[ScriptAnchorRedetect]`(Exp-175, [backend.py](../../whisperlivekit/simul_whisper/backend.py) `_update_script_anchor_streak`)가
   이를 "잠긴 언어(ko)와 반대 스크립트 3단어 연속"으로 집계 → streak 충족 → `detect_current_language(2.0s, p≥0.90)` 재감지.
3. 재감지 창(2.0s)이 철자 낭독 음향으로 지배돼 **en 고확신 반환** — 음향적으로는 "정당"하므로 확신도 강화로는 못 막는다.
4. `_apply_detected_language(en)` → **전환 트림이 직전 오디오 9.68~12.02s 절단 폐기**(진짜 전환에선 재디코딩 세금 절감용 정상 동작).
5. 발화는 계속 한국어 → 1~2s 뒤 en→ko 복귀 전환(**추가 2.4~2.7s 절단**).
6. 절단·재디코딩 후 tokens_alignment가 같은 문장 프리픽스를 **4~5회 누진 재확정**(중복 폭주) → WER 70~101%.

**Exp-175 채택 당시 미노출 사유**: 테스트셋(bong1/ytn2/sbs1)에 철자 낭독이 없어 짝지음 18런에서 게이트 발동 0회였음
(발동 없으면 완전 수동). 군 브리핑처럼 약어가 많은 실사용 환경에서 처음 노출된 사각지대다.

**관찰된 판별 신호**: 진짜 코드스위칭 방출(`There`/`is`/`more`/`work` — 소문자/두문자 대문자 자연 단어) vs
철자 낭독 방출(`G`/`P` 길이 1~2 낱글자, `GOP`/`GPGOP`/`AI`/`DUP` **전부 대문자** 덩어리). Whisper가 자연 영어
발화를 ALL-CAPS로 방출하는 일은 사실상 없다 — 이 **표기 속성**이 가드 기준이다(§3.8 단어 암기 하드코딩 아님).

**스코프 밖 (별개 goal)**: ① 경계 QG streak refresh 버퍼 폐기(Type B) = [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md).
② 일반 재디코딩 중복 확정 churn(kor3 등, ScriptAnchor 미발동에도 발생) — 이 goal은 kor2의 **오발동 유발분**만 제거한다.
③ Case B(SILENCE_HARD_SECS 낭독체 pause) — 별도.

## 2. 설계 — streak 집계 중립 스킵 (acronym-neutral streak)

**핵심 아이디어**: 게이트의 증거 수집 단계에서 "약어/철자 낭독처럼 생긴 라틴 토큰"을 언어 전환의 증거로
세지 않는다(중립 스킵 — 숫자·기호와 동일 취급: streak에 **산입도 리셋도 하지 않음**).

### P1 (핵심) — `_update_script_anchor_streak` 집계 규칙 수정

[backend.py](../../whisperlivekit/simul_whisper/backend.py)의 streak 집계에서, 반대 스크립트(Latin) 판정된 토큰이
아래 중 하나면 **중립 스킵**:

1. **알파벳 길이 ≤ `ACRONYM_MAX_SINGLE_LEN`(초안 2)** — 낱글자 철자 낭독(`G`, `P`, `A.`류). 구두점·공백 제거 후 판정.
2. **전부 대문자 && 알파벳 길이 ≤ `ACRONYM_MAX_ALLCAPS_LEN`(초안 6)** — 약어 덩어리(`GOP`, `GPGOP`, `AI`, `DUP`, `NATO`).

- 소문자 자연 단어(`There`, `is`, `work`)와 두문자 대문자(`The`, `Thank`)는 기존대로 streak 산입 — **Exp-175 커버리지 유지**.
- 한글 쪽(en 잠금 중 한글 방출)은 대소문자 개념이 없어 이 가드의 영향 없음(비대칭이지만 의도된 것 — 철자 낭독 문제는 라틴 방향에서만 발생).
- 스킵 시 로그 `[ScriptAnchorRedetect] acronym-skip: <token>`(debug) — 발동/스킵 전수 감사용.
- **중립 스킵 선택 이유**(리셋 아님): 철자 낭독이 여러 토큰 연속돼도 streak이 0에 머물러야 하고, 사이에 낀 진짜
  전환 증거를 지우지도 말아야 한다. 한글 단어가 이어지면 기존 규칙대로 리셋된다.
- 롤백 플래그 `SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED = True`(모듈 상수, False = 완전 기존 동작 — 짝지음 A/B용).
- **건드리지 않는 것**: 재감지 호출·확신도(p≥0.90)·전환 트림·`_is_opposite_script`·N=3/T=1.0s 임계·기존 리셋 합류점.
  이 goal은 "무엇을 증거로 셀 것인가"만 바꾼다.

### P2 (예비 — P1 불충분 시에만, 기본 스킵) — 오전환 피해 축소

P1 후에도 kor2류 오발동이 잔존하면(예: 소문자 혼합 철자 방출) 전환 트림 보류(새 언어가 M단어 이상 이어질 때까지
절단 유예)를 검토한다. 단 Exp-174 철회(`retract_floor`)·Exp-171 keep_secs 메커니즘과 얽혀 침습적이므로
**P1 실측 결과가 불충분하다는 증거가 있을 때만** 착수(과잉설계 방지).

**구현 위치·규모**: `backend.py` streak 집계 분기 ~10-15줄 + 상수 3개, 단위테스트 확장. 합계 ≈30줄.

## 3. 실행 계획 (자율 — 순서대로, 판단 근거 기록)

1. **사전 확인**: §0 워크트리 준비 + import 경로 + `vbcable=ok`.
2. **유닛테스트 먼저 (TDD)**: 기존 `tests/test_script_anchor_redetect.py`(17건) 위에 신규 케이스 —
   낱글자 연쇄 스킵 / ALL-CAPS 약어 스킵 / 소문자 자연 단어는 기존대로 산입 / 약어+자연단어 혼합 시 자연단어만 카운트 /
   한글 단어 리셋 유지 / 플래그 OFF 시 완전 기존 동작. 전부 통과 후 다음 단계.
   (`.venv\Scripts\python.exe -m pytest` 직접 호출 — **uv 금지**.)
3. **Stage 1 — 짝지음 A/B 스크리닝** (`--repeat 2 --trace-tokens`, ON/OFF 동일 세션):
   - **표적**: kor2 — ON에서 `[ScriptAnchorRedetect]` ko→en 오발동 0회 + `acronym-skip` 로그로 스킵 전수 확인 + WER 대폭 개선 기대
     (완전 정상화는 아닐 수 있음 — kor2에는 別 결함(중복 churn·Case B) 잔존. **오발동 유발분 제거**가 판정 기준).
   - **커버리지 감시**: ytn2 — 진짜 코드스위칭에서 게이트가 기존대로 발동하는지(발동 로그 대조), WER·화자분리 F1 미회귀.
   - **회귀 감시**: bong1 + sbs1 ×1.
4. **Stage 2 — 파라미터 확인**: `ACRONYM_MAX_ALLCAPS_LEN` {4, 6, 8} 중 스킵/오스킵 로그 감사로 확정(측정 반복보다
   로그 전수 감사 우선 — 발동이 희소하므로 Exp-175 방법론과 동일).
5. **Stage 3 — 채택 확정** (`--repeat 3 --trace-tokens`): 테스트 3파일(bong1/ytn2/sbs1) + kor1~3. **fail-fast 금지.**
6. **held-out (ytn1+eng1 단회 + kinno N=3 정성)**: 채택 확정 게이트 통과 시만. eng1(영어 단독)에서 가드가
   영어 감지를 방해하지 않는지 특히 확인.
7. **정성 종합**: kor2 전사 before/after(중복 폭주 소멸 여부), 발동/스킵 전수 감사표.
8. **기록**: `/log-experiment`(Exp-180 또는 다음 번호). 커밋은 워크트리 브랜치에만.
9. **최종 보고서 작성 후 정지**(§5). **머지하지 않는다.**

## 4. 채택 게이트 (hard — regime v2 + 커버리지 비회귀)

판정 도구 = 짝지음 A/B 순효과(동일 세션 ON/OFF). 우선순위 순:

1. **화자분리 F1 worst-case 미회귀** (3파일 전부).
2. **WER max 미회귀** — 특히 ytn2(게이트 실사용 파일)·bong1(기존 필러/웃음 변동은 로그 인과 대조로 무관 입증).
3. **Case B 0건** (이 변경 유발분 — 기존 kor3 Case B는 별개 결함으로 부기).
4. **표적 지표**: ⓐ kor2 ScriptAnchor ko→en 오발동 ON에서 0회(로그 전수), ⓑ kor2 WER 개선(중복 폭주 유발분 소멸),
   ⓒ `acronym-skip` 오스킵(진짜 전환 서두를 스킵해 감지 지연·미감지) 사례 0 — ytn2 발동 로그 대조. 이게 없으면 기각 권고.
5. **held-out 미회귀** (eng1 영어 단독 포함).
6. WER median 개선(또는 중립) — 발동이 국소적이므로 median 중립 + 표적 개선이어도 채택 권고 가능.

이 가드는 §3.2(두 언어 강제) 보전 기능의 오작동 수정이므로 정량이 애매하면 자율 기각 대신
**"판단 유보 + 증거 정리 + 사용자 질의"**로 보고서에 남긴다.

## 5. 최종 보고서 형식

1. 한 줄 결론: 채택 권고 / 기각 권고 / 판단 유보.
2. 정량 표(짝지음 A/B·확정 N=3·held-out — WER median/max·화자F1 분리) + 게이트 6항 판정.
3. 정성 핵심: kor2 오발동·중복 폭주 before/after 전사 인용, 발동/스킵 전수 감사표(오스킵 0 증빙), ytn2 커버리지 유지 증빙.
4. 자율 결정 이력(ALLCAPS_LEN 선택 근거·P2 스킵/착수 근거).
5. 미해결·후속: kor2 잔여 결함(중복 churn — GOAL_BOUNDARY_QG_PRESERVE 연계·Case B), kor1~3 테스트셋 편입 제안.
6. **사용자 질문은 단 하나**: "master에 머지(채택)할까요?"

## 6. 회귀 교훈 (반드시 준수)

- **Exp-175 성질 보존**: 미발동 시 완전 수동. 이 가드는 발동 조건을 **좁히기만** 한다 — 넓히는 방향 변경 금지.
- **데이터 특화 하드코딩 금지(§3.8)**: "GP·GOP" 등 특정 문자열 매칭 금지 — 길이·대소문자 등 **표기 속성만** 사용.
- **전환 트림·재감지 로직 무변경**(P1 범위): Exp-171/174의 keep_secs·retract_floor 상호작용 지뢰를 피한다.
- **공유 .venv 가드레일**: `uv run`/`uv sync`/`uv pip` 절대 금지. pytest·ruff는 `.venv\Scripts\python.exe -m …` 직접 호출.
- **측정 정본**: 경로 C만, provenance 육안 확인, 스크리닝 `--repeat 1~2`(방향 신호)·채택확정 `--repeat 3`(fail-fast 금지),
  짝지음 A/B로 변동성 상쇄. VBCable 단일 자원 — 타 세션과 동시 측정 금지.
- **kor2 완전 정상화를 게이트로 삼지 말 것**: kor2에는 이 goal 스코프 밖 결함이 잔존 — 판정은 "오발동 유발분 제거"로 한정.

## 7. 기록·연동 문서 (채택 시 사용자 승인 후 동일 작업 단위)

- `EXPERIMENTS_LOG.md` 전체 서술 + `EXPERIMENTS.md` 빠른참조 1행(`/log-experiment`).
- [MASTER_CHANGES.md](../MASTER_CHANGES.md) §3-6c(스크립트-앵커 게이트)에 가드 추가 서술 + §8 TODO 최우선 항목 제거 — `/update-master-changes`.
- [SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md) §5 파라미터 표에 신설 상수 추가(잠정 태그).
- **epoch 판단**: 발동 조건을 좁히는 가드(미발동 시 수동)이므로 **미bump 예상**(Exp-175/179 전례) — 머지 시 최종 판단.
