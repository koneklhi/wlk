# GOAL: 파라미터 튜닝 캠페인 — 전 knob 계통 스윕 무정지 자율 루프 (다중 야간)

> **이 파일은 새 Claude Code 세션의 첫 메시지로 붙여넣는 goal 프롬프트다.**
> 작성: 2026-08-07. 근거 = 2026-08-07 전 9파일 `--lan auto --repeat 3` 베이스라인
> (`.omc/benchmarks/eval_20260807_1114_full9_auto_N3.json`, master@2b017d2) + 서버로그 27개 필터 발동 집계
> + EXPERIMENTS 3계층 전수 조사. 승인된 계획 원본 = `C:\Users\A040-000-0001\.claude\plans\2-3-compressed-bentley.md`
>
> **2026-08-10 재설계 — §0-1·§5를 먼저 읽을 것.** Stage 0 하네스 스모크 검증 중 실제로 노이즈 바닥을
> 재측정했더니(BASE-0 동일 코드 6회 반복) "저분산 채널" 전제가 무너졌다(ytn2 sd 10.8%p — N=3에서
> 보고됐던 1.4%p는 자유도2짜리 운 좋은 표본). median 서열 비교 대신 **파국(catastrophe) 발생률**로
> arm을 비교하도록 §5 프로토콜 전체를 재설계했다. 사용자 승인(2026-08-10): 캠페인 형태 = "파국 원인
> 규명 먼저"(넓게 거르고 깊게 확인), 스크리닝 세트 = bong1·kor3 추가. 이후 사용자가 "15시간 이상
> 응답 불가, 이후 전부 자율 판단으로 진행"을 명시(2026-08-10) — §0-2에 그 결정 규칙을 명문화했다.

---

## 0. 루프 성격 — 무정지 조항 (최상위 지시)

- **멈추지 않는다.** **토큰 예산 임박** 또는 **§4 원장의 전 arm 소진** 시에만 §11 종료 시퀀스로 마무리한다.
  그 전에는 어떤 실패·에러·불확실성에서도 정지하지 않는다. 이 캠페인은 여러 세션·여러 밤에 걸쳐 이어지도록
  설계됐다 — **§8 원장 파일이 세션 간·컨텍스트 압축 간 유일한 상태 저장소**다.
- **사용자에게 질문하지 않는다.** 판단이 필요한 지점은 §9 기본값 규칙으로 스스로 결정하고, 사용자 확인이
  필요한 사안은 진행 리포트에 "아침 확인 요청"으로 기록한 뒤 **다음 arm으로 이동**한다.
- **한 arm이 막히면 그 자리에서 고민하지 말고** 원장에 `blocked` + 사유를 적고 다음 arm으로 간다.
- **측정 결과가 나쁜 것 = 데이터이지 정지 사유가 아니다.** arm 하나가 회귀하면 원장에 기록하고 다음으로 간다.
  이 캠페인은 **어떤 값이 나쁜지 확정하는 것도 성과**다(다음 세션이 반복하지 않는다).
- **에러는 자가 복구한다** — §9-3. 측정 불가 하드블록이면 측정이 필요 없는 작업(다음 arm 준비·기존 로그
  재분석·원장 정리·문서화)으로 전환하고 30분마다 재확인한다.
- **컨텍스트 압축이 일어나도 원장을 다시 읽으면 즉시 재개할 수 있어야 한다.** 매 arm 종료 시 원장을 갱신한다.

## 0-1. 재설계 근거 — "저분산 채널"은 측정 아티팩트였다

Stage 0 하네스 스모크(BASE-0 + A1-400) 결과를 검증하던 중, S1 설정(당시 4파일 N=1)으로 BASE-0(동일
마스터 코드, 대조군)를 **6회 반복**했더니:

| file | 실측 sd (n=6) | range | 2026-08-07 N=3이 보고한 sd |
|---|---|---|---|
| ytn2 | **10.8%p** | 11.8~38.9 | 1.5 |
| sbs1 | **5.8%p** | 7.7~23.2 | 1.4 |
| kor2 | **6.7%p** | 15.9~31.0 | 1.4 |
| eng1 | 0.9%p | 4.8~6.7 | 1.5 |

어제 N=3 sd는 자유도 2짜리 추정치라 운 좋게 뭉친 값이었다. **어제 마스터 9파일 N=3을 재구성해도
27 file-run 중 3건(11%)이 median+8%p를 초과했다** — bong1·ytn1·kinno에 떨어졌을 뿐 파국은 항상 있었다.
`git diff master..HEAD`(무회귀 검증)와 master 대조군 재측정(sd 1.3/1.5/2.4/1.0, 어제와 동일)으로
**Stage 0 코드 변경이 원인이 아님**을 확인했다 — 시스템 자체의 성질이다.

**함의**: median 서열 비교는 N≤3에서 통계적으로 무의미하다("어느 arm이 운이 좋았나"를 재는 수준). 그래서
§5를 **median 서열 → 파국 발생률 비교**로 재설계했다. 파국은 file-run의 10~25%에서 일어나는 드문
이산 이벤트이므로, 관측 밀도를 올리려고 스크리닝 세트에 파국이 잘 나는 bong1·kor3을 추가한다(6파일:
bong1·ytn2·sbs1·kor2·kor3·eng1). 판정 로직은 `scripts/sweep_runner.py`의
`_extract_raw_wers`/`_catastrophe_summary`(파일별 2026-08-07 baseline median + 8%p 초과 회차 비율)로
구현했다 — median/min/max 기반 §5 구버전 텍스트가 남아있다면 이 절이 우선한다.

## 0-2. 무응답 구간 자율 판단 규칙 (2026-08-10, 사용자 명시)

> "앞으로 15시간이상 답변을 못하니깐 사람의 답변이 필요한 부분이 있다면 너 스스로 생각했을때 가장
> 최적의 선택지를 선택해서 답변을 물어보지 말고 계속 진행해." — 이 지시는 **§0의 "질문 금지" 원칙을
> 강화**한다. 아래는 이 구간에 실제로 마주칠 결정 지점과 기본 선택지다. 전부 §0의 "질문하지 않는다"
> 원칙의 구체화이며, 결정 사유는 원장/진행 리포트에 남긴다(사후 검토 가능하게).

| 결정 지점 | 기본 선택지 |
|---|---|
| S1(넓게) 완료 후 S2로 넘길 arm 선정 | 파국률이 baseline(BASE-0)보다 **유의하게 낮은** 상위 arm(트랙당 최소 1개는 포함해 전 트랙 커버리지 유지) + 파국률이 baseline보다 **뚜렷이 높아** 나쁜 방향임을 확정한 arm은 즉시 기각(재측정 불필요) |
| S1에서 거동 무변화(noise-control) arm | S2로 승격하지 않는다 — 배선 문제일 수 있으므로 원장에 flag만 남기고 하네스 점검은 진행 리포트 "아침 확인 요청"에 적은 뒤 계속 진행 |
| S2(깊게) 완료 후 S3로 넘길 후보 수 | 파국률이 baseline 대비 명확히 낮은 순으로 최대 3개(적으면 그 수만큼) — CLAUDE.md §4 채택 게이트 순서(화자F1→WER max→median→문장F1)를 S3에서 그대로 적용 |
| S3 채택 게이트 탈락 | 자율 기각(§CLAUDE.md 예외 조항 — 불변 제약 §3.1·§3.2 직결 기능이 아니면 자율 기각 가능) |
| Track F(조합) 착수 여부 | S3 통과 후보가 2개 이상이면 착수, 1개 이하면 스킵하고 그 후보로 S4 직행 |
| 하니스 버그 vs 실측 이상치 판단이 애매함 | 재측정 1회로 재현 여부 확인(§9-3 규칙 그대로) — 재현되면 실측, 안 되면 하니스 의심 후 원장에 기록 |
| 예상치 못한 새 현상 발견(이 문서가 다루지 않는 것) | 캠페인 목표(§1)에 부합하는 방향으로 판단해 진행하되, **코드를 커밋하기 전에** 진행 리포트에 근거를 먼저 적는다(판단 과정 추적 가능하게) |
| 토큰/컨텍스트 압축 임박 | §11 종료 시퀀스 없이 그냥 원장을 flush하고 자연 종료 — 다음 호출(알림 또는 새 세션)이 §6-1대로 원장을 읽고 이어간다 |

**단, 아래는 여전히 예외 없이 사용자 확인 대상**(§0-2가 이것까지 자율화하지 않는다):
master 머지, `.venv`/의존성 변경, 워크트리 삭제, git force-push류 파괴적 작업. 이 캠페인 범위에서는
전부 금지돼 있으므로(§9·§10) 실제로 마주칠 일은 없어야 한다.

## 1. 목표 · 제약

- **목표**: 열려 있는 전 파라미터 knob을 계통적으로 스윕해 **개선 방향을 찾고, 나쁜 방향을 확정 배제**한다.
  단일 대박이 아니라 **전 knob의 turbo 기질 지도를 완성**하는 것이 성과다.
- **왜 지금 파라미터인가**: 최근 T1~T5 미세 필터 트랙이 "0-firing·재현 실패·불확실"로 끝나 수확 체감에
  도달했다. 반면 기존 "방향 종료" 선언의 상당수가 **한쪽 방향만 탐색**했거나 **base 기질(whisper-base 74M)에서
  측정된 뒤 turbo로 기질이 바뀐 채 재검증되지 않았다**(`[base전용·재검증]`). **실험 기록이 0건인 knob**도 여럿이다.
- **일반화 원칙(CLAUDE.md §3.8)**: 데이터 특화 튜닝 금지. 특정 파일에만 좋은 값은 채택하지 않는다.
- **이번 캠페인에서 master 머지 금지.** 모든 코드는 워크트리 + `feat/param-tuning-campaign` 브랜치에
  커밋만 한다. 채택 게이트를 통과한 값은 "채택권고·머지 대기"로 기록한다(머지는 사용자 몫).
- **파라미터 값 변경은 epoch를 올리지 않는다**(`EXPERIMENTS.md:32`). 단 Track C(문맥 재활성화)가 머지되면
  구조 변경이므로 그때 사용자가 epoch를 올린다 — 루프는 기록만 한다.

## 2. Context — 이미 확정된 사실 (재발굴 금지, 여기서 시작)

### 2-1. 베이스라인 (master@2b017d2, `--lan auto`, diar ON, N=3)

| file | WER med | min | max | **sd** | 화자F1 med | lmr_ko med |
|---|---|---|---|---|---|---|
| bong1 | 29.2 | 28.6 | 41.6 | **7.3** | 66.7 | 37.0 |
| ytn2 | 13.8 | 11.8 | 14.8 | 1.5 | 94.7 | 0.0 |
| sbs1 | 11.3 | 8.9 | 11.3 | 1.4 | 80.0 | 0.0 |
| kor1 | 18.7 | 16.4 | 21.6 | 2.6 | 0.0* | 0.0 |
| kor2 | 14.5 | 13.8 | 16.6 | 1.4 | 100.0 | 0.0 |
| kor3 | 38.4 | 30.5 | 42.4 | **6.1** | 0.0* | 0.0 |
| ytn1 | 15.3 | 12.3 | 32.5 | **10.9** | 94.1 | 1.3 |
| eng1 | 4.8 | 3.8 | 6.7 | 1.5 | 0.0* | n/a |
| kinno | 28.9 | 27.6 | 37.8 | **5.5** | 75.9 | 0.0 |

\* 단일화자 정답 → 화자F1 0/100 **이분 아티팩트**(Exp-186). 결함 아님, **게이팅 제외**.
과거 N=5 교차확인: sbs1 sd **0.7**, kor2 sd **1.1**, kor1 sd 7.5, kor3 sd **13.9**.

**노이즈 바닥이 이원화돼 있다 — 이 캠페인의 설계 근간이다.**
- **저분산 채널** = `ytn2 · sbs1 · kor2 · eng1` (sd 1.4~1.5%p) → **arm 우열은 여기서만 가린다.**
- **고분산 채널** = `bong1 · ytn1 · kor3 · kinno` (sd 5.5~13.9%p) → sd 7%p에서 5%p 차이를 N=3으로 판별하려면
  N≈30이 필요하다. **median 비교 금지**, 최악값·파국 발동률로만 읽는다.

### 2-2. QualityGate가 실단어를 대량 억제하고 있다 (신규 실측)

`.omc/server_logs/*_20260807_*.log` 27개 집계 (**주의: `.omc/`는 gitignore라 ripgrep 디렉터리 검색이 조용히
스킵된다 — 파일 경로를 명시해 검색할 것**):

| 항목 | 27회 합계 |
|---|---|
| `[QualityGate] avg_logprob … suppressing` | **636회** |
| 그중 구두점-only(streak 미산입) | ~216회 |
| **실단어 억제** (`also`·`I`·`through`·`is`·`coordination`·`해서` …) | **~420회** |
| `3 consecutive suppressions — refresh_segment` (**버퍼 전체 폐기**) | **22회** |
| `AnchorRepeat` | 53회 |
| `BatchRepeatFilter` / `no speech, stop` / `ScriptMismatch` | **0회** |

파일별(실단어억제/QG reset): bong1 22/2·38/9·46/9 (WER 29.2/28.6/41.6, lmr_ko 14.1/37.0/54.3) ·
ytn2 24/0·26/0·28/1 · kinno 15/0·18/0·12/1 · kor3 15/2·10/0·14/1 · ytn1 23/1·10/0·11/1 ·
sbs1 1/0·4/0·6/1 · kor2 8/0·2/1·5/0 · eng1 1/0·2/0·1/0.

문턱 `logprob_threshold=-2.0`은 **E2(base 기질) Exp-142에서 채택**됐고 epoch 게이트상 `[E2·재검증]` 미완이다.

### 2-3. VAD 가설의 조준점 (중요 — 방향을 틀리면 시간을 버린다)

Exp-164 기전 결론(verbatim): *"VAC(Silero)는 '음성 에너지가 있는가'를 판정하지 '어휘적으로 이해 가능한
발화인가'를 판정하지 않는다. 웃음·필러성 발성은 실제 음성 에너지를 동반하므로 어떤 합리적 VAC 임계값을
써도 speech로 통과된다."*

→ **"문턱을 올려 웃음/환각을 차단"하는 경로는 막혀 있다(Exp-084/117/164 전부 기각).**
→ 열려 있는 것은 **반대 경로**: **실발화를 덜 자르게 만들어 "조각 → 재디코딩 → 환각" 연쇄를 끊는다.**

직접 선례: **Exp-173**이 `min_silence_duration_ms` 100→200으로 올려 bong1 max 46.8→37.2% 개선했고,
기록된 개선 기전이 **"발화 반복/필러 환각 감소"**다. 그리고 **200 위로는 한 번도 안 올려봤다.**
`speech_pad_ms`(Silero 기본 30ms, 미전달)는 단어 onset/offset을 자르는 직접 원인 후보인데 **실험 0건**이다.

### 2-4. 이전 문맥 — 기각 근거가 부실하다

`max_context_tokens`는 `whisperlivekit/simul_whisper/backend.py:1007-1008`에서 `None → 0` 강제.
채택 근거는 Exp-075 *"컨텍스트 오염 완전 차단"*(base 기질).

널리 인용되는 반대 결론(Exp-126 *"이전 컨텍스트는 필수적 — 제거하면 전사 붕괴"*)은 **인용 금지**:
통째로 무효화된 Exp-106~129 블록 소속이고, 이미 기본값이 0인 코드에 `0`을 준 **no-op 실험**인데 sbs1
WER 100%가 나왔다 — 측정이 깨졌다는 자기증거다. **turbo에서는 한 번도 테스트된 적이 없다.**

**구조적 제약(기대치 조정)**: `init_context()`가 `align_att_base.py:217`에서 **모든 `refresh_segment()`마다
무조건** 문맥을 지운다(침묵·화자전환·언어전환·QG 3연속). 문맥은 `simul_whisper.py:177-178`에서 오디오
버퍼가 `audio_max_len`을 넘겨 축출할 때만 쌓인다. → **효과 구간은 연속 단일화자·단일언어 낭독(kor1~3)에
국한**되고, 코드스위칭·다화자에선 문맥이 거의 안 쌓여 base 시대를 망친 오염 위험도 낮다.

---

## 3. Stage 0 — 하네스 ✅ **완료 (2026-08-07, `feat/param-tuning-campaign@e99f501`)**

> **다음 세션은 이 절을 건너뛰고 §6부터 시작한다.** 아래 표는 무엇이 왜 만들어졌는지의 기록이다.
>
> **작업 위치** (이미 준비 완료 — `.venv` Junction · `test_data/*.wav` · 모델 하드링크 · `.omc/` 디렉터리 전부 생성됨):
> ```
> c:\Users\A040-000-0001\Desktop\260605wlk\wlk\worktrees\param-tuning-campaign
> ```
> **arm 목록**(58개, 전 arm 서버 파서 파싱·값 반영 검증 완료): `docs/research/2026-08-07_param-sweep-arms.json`
> **원장**: `docs/research/2026-08-07_param-sweep-ledger.json` (sweep_runner가 자동 생성·append)
> **검증 상태**: ruff GREEN · pytest **793 passed, 1 skipped** · 신규 테스트 18개(`tests/test_param_sweep_knobs.py`)
>
> **무인 실행 명령** (background로 띄우고 완료 알림을 기다린다 — 폴링 금지):
> ```bash
> cd .../worktrees/param-tuning-campaign
> PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/sweep_runner.py \
>   --arms docs/research/2026-08-07_param-sweep-arms.json \
>   --stage S1 \
>   --ledger docs/research/2026-08-07_param-sweep-ledger.json
> ```
> `--track A B` 로 트랙 한정, `--only <id>...` 로 개별 arm 지정 가능. **이미 `done`인 arm은 자동으로
> 건너뛰므로** 중단 후 같은 명령을 다시 실행하면 이어서 돈다.

### (기록) Stage 0에서 무엇을 왜 했나

`scripts/eval.py`는 서버로 넘길 인자를 **하드코딩 화이트리스트**로만 관리한다(`eval.py:733-753`) —
`logprob-threshold`·`CRT`·`beams`·`frame-threshold`·`audio-max-len`·`PLC`·`silence-hard-secs`·
`silence-grammar-gate`·`trace-tokens`·`frontend-dir`뿐. **`--vad-threshold`·`--max-context-tokens` 등
12개 knob은 전달 수단이 아예 없다.** 이걸 먼저 뚫지 않으면 캠페인의 3/4가 실행 불가다.

| # | 파일 | 변경 | 목적 |
|---|---|---|---|
| S0-1 | `scripts/eval.py` | `--server-arg`(`action="append"`) 범용 패스스루 → `extra_server_args`에 extend | 이미 CLI인 12 knob 일괄 해금. `start_server()`가 이미 리스트를 `cmd.extend`(`eval.py:326-327`) |
| S0-2 | `scripts/eval.py` | `_probe_provenance()` 반환 dict + 출력 JSON에 넘긴 server-arg 원문 기록 | **arm 오라벨 방지**. 현 provenance의 `beams=` 값은 빈 인자로 `parse_args`를 프로브한 **cosmetic 표시**라 오버라이드를 반영조차 안 한다 |
| S0-3 | `whisperlivekit/audio_processor.py:128,130` + `parse_args.py` | `min_silence_duration_ms`(200)·`speech_pad_ms`(Silero 기본 30, 현재 미전달) CLI 노출 | **Track A 핵심 2 knob이 하드코딩** |
| S0-4 | `whisperlivekit/simul_whisper/config.py:26` + `parse_args.py` | `quality_gate_reset_after`(3) CLI 노출 | Track B2 |
| S0-5 | `whisperlivekit/simul_whisper/config.py:10` + `parse_args.py` | `rewind_threshold`(200) CLI 노출 | Track D4 |
| S0-6 | `whisperlivekit/simul_whisper/simul_whisper.py:347` | `_check_no_speech` sot_index 문맥 오프셋 수정 (§3-1) | Track C 선행 |
| S0-7 | `scripts/sweep_runner.py` (신규) | arm 목록 JSON을 받아 eval.py를 연속 실행하고 원장 JSON에 결과 append (§3-2) | **무인 야간 실행의 핵심** |

**`or` 폴백 함정**: 신규 노출 knob에 `getattr(...) or default` 패턴을 쓰지 말 것 — 명시적 `0`이 falsy로
삼켜져 조용히 기본값으로 되돌아간다(`backend.py:1078`·`audio_processor.py:103-106`·
`tokens_alignment.py:114-127`에 이미 있는 버그). **`is None` 검사로 쓴다.**
**무회귀 불변식**: 신규 플래그 전부 기본 `None` → 미지정 시 기존 하드코딩 상수로 폴백. 미지정 상태의 거동이
plain master와 100% 동일해야 한다.

### 3-1. sot_index 버그 (Track C 선행 필수)

`simul_whisper.py:146`이 `sot_index`를 **문맥 길이를 반영하지 않는 절대 인덱스**로 잡는데,
`simul_whisper.py:186-190`의 `_current_tokens()`가 문맥 토큰(`<|startofprev|>` 시작)을 **앞에 붙인다**.
결과적으로 `simul_whisper.py:347`의 `logits[:, self.state.sot_index, :]`가 `<|sot|>` 대신
`<|startofprev|>` 위치를 읽는다. `align_att_base.py:388-390`에 잠재 버그로 주석돼 있다.

**수정**: 실제 문맥 길이만큼 오프셋. 문맥이 비면 오프셋 0 → 기존 동작 그대로.
**검증**: 문맥 0(기본값)에서 수정 전/후 동일 파일 측정이 같은 밴드여야 한다(달라지면 수정이 잘못된 것).

### 3-2. `scripts/sweep_runner.py` 사양 (무인 실행의 핵심)

야간 무인 실행을 위해 arm을 연속 처리하는 드라이버. **에이전트가 arm마다 붙어 있지 않아도 되게** 만든다.

```
입력 : --arms <arms.json>  --stage S1|S2|S3|S4  --ledger <ledger.json>
동작 : arms.json의 각 arm에 대해
        1) 이미 ledger에 done으로 있으면 skip (재개 안전 — 중단 후 재실행 시 이어감)
        2) eval.py를 arm의 server_args + stage별 --files/--repeat로 실행
        3) 결과 JSON에서 파일별 wer/seg_f1/sentence_f1/lmr 추출
        4) 해당 arm의 서버로그에서 거동 증거 카운트 집계
           (QualityGate 억제·QG reset·RefreshSegment·AnchorRepeat·Silence 토큰 수)
        5) ledger.json에 append + 즉시 flush (중단 내성)
        6) 다음 arm
출력 : ledger.json (append-only), 각 arm의 eval JSON은 .omc/benchmarks/ 에 arm 라벨 포함해 저장
규칙 : 한 arm 실패해도 중단하지 않고 status=error+사유 기록 후 다음 arm.
       단 VBCable 무음·포트 충돌 등 하니스 버그는 3연속 발생 시 중단(전멸 방지).
```

**stage별 기본 인자**
| stage | `--files` | `--repeat` |
|---|---|---|
| S1 | ytn2.mp3 sbs1.mp3 kor2.wav eng1.mp3 | 1 |
| S2 | ytn2.mp3 sbs1.mp3 kor2.wav eng1.mp3 | 3 |
| S3 | bong1.wav ytn2.mp3 sbs1.mp3 kor1.wav kor2.wav kor3.wav | 3 |
| S4 | bong1.wav | 5 |

Track C(문맥)만 S1/S2에 `kor1.wav kor3.wav`를 추가한다(가설 성립 구간).

---

## 4. 스윕 arm 원장 (전체 목록)

굵은 값 = 현재 기본값(대조군, 별도 측정 불필요 — §2-1 베이스라인 사용). **각 arm은 1개 knob만 변경**(OFAT).
`--server-arg` 형태로 전달한다. 예: `--server-arg=--vad-threshold --server-arg=0.25`

### Track A — VAD/VAC (환각 저감 조준, §2-3)

| id | knob | arm 값 | 가설 |
|---|---|---|---|
| A1 | `--min-silence-duration-ms` | **200** / 300 / 400 / 500 | Exp-173 100→200이 필러 환각 감소로 bong1 max -9.6pp. 더 밀면 조기 분절·조각 재디코딩이 더 줄어든다 |
| A2 | `--speech-pad-ms` | **30** / 60 / 100 / 150 | 30ms는 너무 짧아 단어 onset/offset이 잘린다. 패딩↑ → 조각 단어↓ → 환각 씨앗↓ |
| A3 | `--vad-threshold` | **0.3** / 0.25 / 0.2 | 상향만 기각됐다. 하향 = 조용한 실발화 클리핑 감소 |
| A4 | `--vac-chunk-size` | **0.2** / 0.1 / 0.32 / 0.5 | Exp-075(base) 값 → turbo 재검증 |
| A5 | `--min-real-silence-secs` | **0.4** / 0.3 / 0.5 / 0.6 | base 실험만 존재 |

### Track B — QualityGate (§2-2)

| id | knob | arm 값 | 가설 |
|---|---|---|---|
| B1 | `--logprob-threshold` | **-2.0** / -2.5 / -3.0 / -4.0 / -10.0 | turbo logprob 분포가 base와 달라 -2.0이 과잉 발동. **완화 방향만** — 강화(-1.5·-1.0)는 E2에서 catastrophic 기각 |
| B2 | `--quality-gate-reset-after` | **3** / 5 / 8 / 999 | 발동 시 버퍼 전체 폐기(22회). 실험 0건 |
| B3 | `--compression-ratio-threshold` | **3.0** / 3.5 / 4.0 | 하향(2.5·2.8)만 기각됐다. **상향만** |

### Track C — 이전 문맥 (§3-1 선행 필수)

| id | knob | arm 값 |
|---|---|---|
| C1 | `--max-context-tokens` | **0** / 25 / 50 / 100 / 200 |

**필수 감시(문맥 오염 회귀)**: bong1·ytn2의 `lmr_ko` 상승 / 자기강화 반복 환각 체인 /
`AnchorRepeat`·`[RefreshSegment]` 발동량 급증. 하나라도 보이면 그 arm은 즉시 탈락 처리하고 정성 근거를 기록.

### Track D — 버퍼·디코딩 지평

| id | knob | arm 값 | 가설 |
|---|---|---|---|
| D1 | `--frame-threshold` | **25** / 22 / 20 / 18 | 상향(35)만 탐색됐고 화자F1 1순위 회귀로 배포 opt-in에 그침(Exp-193). 하향 = 조기 커밋 |
| D2 | `--audio-max-len` | **15.0** / 10 / 12 / 20 | turbo에서 30→15만 확인(Exp-161). 최적점이 15 아래일 수 있음 |
| D3 | `--min-chunk-size` | **0.1** / 0.2 / 0.3 | 실험 0건 |
| D4 | `--rewind-threshold` | **200** / 100 / 400 | 실험 0건 |

### Track E — 문장확정·화자 (화자F1 1순위 겨냥). 현재 최약체 = bong1 화자F1 66.7%

| id | knob | arm 값 |
|---|---|---|
| E1 | `--finalize-grace-secs` | **2.0** / 1.2 / 2.8 |
| E2 | `--pending-resolve-cap-secs` | **2.0** / 2.4 / 2.5 |
| E3 | `--min-speaker-attribution-secs` | **0.5** / 0.4 / 0.7 |
| E4 | `--silence-hard-secs` | **1.2** / 1.5 / 1.8 / 2.0 (서버 상한 2.0, 초과 시 assert) |
| E5 | `--short-lang-reset-secs` | **0.5** / 0.4 / 0.7 |
| E6 | `--lang-detect-general-secs` | **2.0** / 1.5 / 2.5 |
| E7 | `--script-anchor-n-words` | **3** / 2 / 4 |
| E8 | `--new-speaker-max-keep-secs` | **5.0** / 4.0 / 6.0 |
| E9 | `--scenario` 프리셋 통짜 | `mono` / `codeswitch` / `multi` (문서가 "미검증 방향값"이라 자인) |

> Track E는 고분산 채널(bong1) 중심 지표라 **S1/S2에서 화자F1이 저분산 4파일에서 안 움직여도 탈락시키지
> 말 것** — S3(6파일)까지 올려 bong1 화자F1으로 판정한다. 대신 S1에서 **WER catastrophic 회귀만** 거른다.

### Track F — 조합 (A~E 소진 후에만)

각 트랙 최적값을 **누적 적용**한 뒤 하나씩 되돌리는 **ablation**으로 상호작용 확인.
knob 상호작용은 실재한다 — `frame_threshold`↑는 확정 지연을 늘리므로 `finalize_grace_secs`도 같이 키워야
정합적이다(`docs/OPERATOR_TUNING_GUIDE.md` §2 정합성 노트).

**총 arm 수 ≈ 55개**(대조군 제외).

---

## 5. 4단계 캠페인 프로토콜 (2026-08-10 재설계 — 파국 발생률 기반)

§0-1 근거로 median 서열 비교를 버리고 **파일별 baseline median+8%p를 넘긴 회차 비율("파국 발생률")**로
arm을 비교한다. baseline·margin은 `scripts/sweep_runner.py`의 `BASELINE_MEDIAN_WER`/
`CATASTROPHE_MARGIN_PP`(코드가 SoT — 값이 바뀌면 이 문서보다 코드를 믿을 것). 스크리닝 세트는
6파일(`bong1·ytn2·sbs1·kor2·kor3·eng1`) — 파국이 잘 나는 bong1·kor3을 포함해 관측 밀도를 올린다.

| 단계 | 대상 | 세트 | repeat | arm당 시간 | 총 |
|---|---|---|---|---|---|
| **S1 넓게** | 전 arm ~58(BASE-0 포함) | screening 6파일 | **2** | ~28분 | **~27시간** |
| **S2 깊게** | S1 생존 arm(`--only`로 선정, §0-2 기준) | screening 6파일 | **16** | ~3.7시간 | 후보수×3.7h |
| **S3 채택 확정** | S2 상위 후보 (CLAUDE.md §4 게이트) | 테스트 6파일(bong1·ytn2·sbs1·kor1~3) | 3 | ~45분 | ~수시간 |
| **S4 최종 검증** | 최종 후보 1~2 | bong1 단독 | 5 | ~15분/회 | ~수십분 |

`sweep_runner.py --stage S1/S2`가 파일·repeat을 자동으로 맞춘다(`STAGES` dict) — 수동으로 `--files`를
조립하지 말고 반드시 드라이버를 통해 실행한다(그래야 원장에 파국 판정까지 자동 기록된다).

**S1(넓게) 판정 — 서열을 매기지 않는다.** 두 가지만 확인한다:
1. **거동이 실제로 바뀌었는가** — §5-1 로그 증거. 안 바뀌었으면 `verdict: noise-control`, S2 승격 후보에서 제외.
2. **파국이 뚜렷이 늘었는가(방향 신호)** — arm의 파국 카운트가 같은 회차에서 측정한 BASE-0보다
   명백히 높으면(육안 판단 — 아직 통계 검정할 표본이 아니다) `verdict: prune`. 애매하면 기각하지 말고
   S2 후보로 남긴다 — S1은 "확실히 나쁜 것"만 거르는 단계다.

**S2(깊게) 판정 — 여기서 처음으로 arm을 비교한다.**
- 각 후보 arm의 파국 발생률(`catastrophe.rate`, 파일별 회차 통합)을 BASE-0의 S2 파국률과 비교.
- **파국률이 유의하게 낮은 arm만 S3로 승격**한다(§0-2 표의 기본 선택 규칙 — 최대 3개).
- 표본이 arm당 96 file-run(6파일×16회)이라 이항비율 차이를 눈대중이 아니라 실제로 비교할 수 있다
  — 예: BASE-0가 15/96(15.6%)이고 arm이 5/96(5.2%)이면 유의미한 개선으로 본다. 둘 다 한 자릿수
  퍼센트대에서 겹치면(예 15% vs 12%) 판단 유보하고 진행 리포트에 "판단 유보" 표기 후 다음으로.

**S3 채택 게이트 (CLAUDE.md §4 순서 엄수, S2를 통과한 후보에게만 적용)**
1. **화자분리 F1 worst-case 미회귀** (단일화자 kor1/kor3/eng1의 0/100 이분값은 게이팅 제외)
2. **WER max 미회귀**
3. WER median 개선
4. 문장분리 F1 (하락 단독은 기각 근거 아님 — Case A 허용)
- **Case B(단어 중간 분절)는 수치 무관 hard-fail**
- bong1·kor3은 여전히 고분산이므로 median이 아니라 **최악값·파국 발생률**로 읽는다(S3 repeat=3이라
  파국 표본은 부족 — S2에서 이미 걸러졌다는 전제로 정성 확인 위주)

### 5-1. 거동 변화 증거 규칙 (이 캠페인에서 가장 자주 틀리는 지점)

**knob을 바꿨는데 로그상 거동이 안 바뀐 arm은 "동일 코드 = 노이즈 대조군"이다.** 그 arm의 WER 차이를
개선·회귀로 귀속하지 말 것. 매 arm에서 아래를 집계해 원장에 남긴다:

| Track | 확인할 거동 증거 |
|---|---|
| A | `Silence` 토큰 수 · 세그먼트 분할 횟수 · `[RefreshSegment]` 횟수 |
| B | `[QualityGate] … suppressing` 횟수 · `3 consecutive suppressions` 횟수 |
| C | 문맥 누적 발생 여부(디버그 로그 `Context:`) · `lmr_ko` |
| D | `[RefreshSegment]` · 커밋 타이밍 분포 |
| E | `finalize_trigger` 라벨 분포(전사 txt `[문장별 확정 트리거]`) |

증거가 0이면 원장 `behavior_changed: false` + `verdict: "noise-control"`로 기록하고 다음으로 간다.

---

## 6. 이터레이션 프로토콜

1. **원장 확인** — §8 원장 파일을 읽어 다음 미처리 arm을 정한다. (**세션 시작·컨텍스트 압축 직후 필수**)
2. **실행** — `sweep_runner.py`를 background로 띄운다. 여러 arm을 한 번에 넘겨 무인 연속 실행.
3. **분석** — 완료 알림이 오면 원장에서 결과를 읽고 §5 기준으로 판정. 정량 + 정성(전사 대조) 병행.
4. **기록** — 원장 갱신 + 진행 리포트(§8) 갱신. 트랙 하나가 끝날 때마다 `/log-experiment`
   (Exp-207부터 이어서, **측정 언어모드 `--lan auto` 명시**).
5. **다음** — 즉시 다음 배치 시작. 폴링하지 않는다(background 완료 알림에 의존).

---

## 7. 측정 규율

- **경로 C만.** 측정은 **메인 세션에서 직접**(서브에이전트 위임 금지 — 첫 run 후 조기정지 전력).
  측정 중 워크트리 코드 mutation 금지.
- **측정 전 확인**: 다른 세션의 VBCable 겹침(포트 8901 점유·python 프로세스), provenance 줄 `vbcable=ok`.
  **arm 식별은 provenance가 아니라 S0-2에서 추가한 server-arg 기록으로 한다**(provenance `beams=`는 cosmetic).
- **측정 언어모드 = `--lan auto` 단일.** kor1~3·eng1도 auto. 예외 없음.
- **`--server-frontend-dir .omc/eval_empty_frontend` 필수** — 로컬 React dist가 있으면 Playwright 레거시 UI
  테스트가 깨진다.

표준 명령(`.claude/commands/eval.md` 정본):

```powershell
$env:PYTHONIOENCODING = "utf-8"; $ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/ytn2.mp3 test_data/sbs1.mp3 test_data/kor2.wav test_data/eng1.mp3 --lan auto `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 1 --server-frontend-dir .omc/eval_empty_frontend `
  --server-arg=--vad-threshold --server-arg=0.25 `
  --output .omc/benchmarks/eval_${ts}_A3-vad025_S1.json
```

- **원본 발화 확인 규칙**: 전사 중복·반복을 결함으로 단정하기 전에 **원본이 실제로 그렇게 발화됐을
  가능성을 먼저 의심**한다. 로그 1차 선별(아티팩트 = 두 방출 타임스탬프 겹침 + 직전 `Refreshing segment` /
  실발화 = 시각 안 겹치고 0.3s 이상 인접·리프레시 없음). 확정은 사용자 청취 → "아침 확인 요청"에 기록.

---

## 8. 상태 저장 — 원장 + 진행 리포트 (세션 간 유일한 기억)

### 8-1. 원장 `docs/research/2026-08-07_param-sweep-ledger.json` (기계 판독, SoT)

```jsonc
{
  "campaign": "param-tuning-2026-08",
  "baseline_ref": ".omc/benchmarks/eval_20260807_1114_full9_auto_N3.json",
  "arms": [
    {
      "id": "A3-vad-0.25",
      "track": "A", "knob": "--vad-threshold", "value": "0.25",
      "server_args": ["--vad-threshold", "0.25"],
      "stage": "S1",
      "status": "done",            // pending | running | done | blocked | error
      "eval_json": ".omc/benchmarks/eval_20260807_2210_A3-vad025_S1.json",
      "results": { "ytn2": {"wer": 0.131, "seg_f1": 0.947}, "...": {} },
      "raw_wers": { "ytn2": [13.1, 14.0], "...": [] },
      "catastrophe": { "count": 1, "total": 12, "rate": 0.083, "by_file": {"...": {}} },
      "behavior_evidence": { "qg_suppress_word": 38, "qg_reset": 3, "refresh_segment": 0 },
      "verdict": "advance",        // advance | prune | noise-control | blocked
      "note": "한 줄 사유"
    }
  ]
}
```

**append-only로 다룬다.** arm을 지우지 않고 status/verdict만 갱신한다 — 어떤 값이 나빴는지도 성과다.

### 8-2. 진행 리포트 `docs/research/2026-08-07_param-sweep-progress.md` (사람 판독)

- 상단: 캠페인 시작 시각·경과·현재 stage·트랙별 진척(예: `A 12/19 · B 5/9 · C 0/4 …`)·전체 요약 3줄
- 트랙별: 무엇이 이겼고 무엇이 졌는지 표. **나쁜 값도 반드시 남긴다**(다음 세션이 반복 안 하게).
- **"아침 확인 요청"**: 사용자 판단 필요 사안(머지 여부·청취 확인·게이트 승격) 누적
- **"실패·막다른 길"**: 시도했으나 안 된 것 + 이유
- **"거동 무변화(noise-control) arm"**: 별도 목록 — knob 배선이 안 됐을 가능성이므로 하네스 점검 후보

---

## 9. 안전 규칙 · 복구 플레이북

### 9-1. 워크트리 · 브랜치
- **main 브랜치 위 코드 편집 금지.** 작업 위치 = `worktrees/param-tuning-campaign`
  (브랜치 `feat/param-tuning-campaign`, master@2b017d2에서 분기, **생성·`.venv` Junction 완료됨**).
- `test_data/*.wav`·`model.safetensors`·`sortformer-4spk-v2.nemo` **하드링크 필요** — 누락 시 returncode=3.
  **venv 오염으로 속단하지 말고 서버 로그부터 읽을 것.**
- 측정은 **cwd=워크트리**에서. import 경로가 워크트리로 해석되는지 provenance fail-fast로 확인.
- **워크트리 삭제 전**: ① `.omc/` 산출물을 메인으로 복사 ② `cmd /c rmdir .venv`로 Junction 먼저 해제
  (따라가서 메인 `.venv`를 지운 사고 2회 전력).

### 9-2. uv 가드레일 (공유 `.venv` 오염 = 캠페인 전멸)
`uv run`·`uv pip`·`uv add/remove/lock/venv`·extras 없는 `uv sync` **절대 금지**.
lint는 `.venv\Scripts\ruff.exe` 직접 호출, 테스트는 `.venv\Scripts\python.exe -m pytest`.
의존성 변경은 이 캠페인에 불필요 — 필요해 보이면 그 arm을 스킵하고 기록한다.

### 9-3. 에러 복구
- **서버 기동 실패/returncode=3**: 서버 로그 먼저(모델 경로·하드링크·포트 충돌). 포트 8901 점유 시 잔존
  프로세스 종료 후 재시도.
- **VBCable 무음/100% WER/분산 폭증**: 케이블 사망 의심 — `verify_loopback` 진단, Audiosrv 재시작.
  복구 불가면 **측정 불가 모드**로 전환(다음 arm 준비·기존 로그 재분석·원장 정리)하고 30분 간격 재확인.
  **측정 실패를 코드 결함으로 오귀속 금지.**
- **하니스 버그 3연속**(무음 캡처·포트 충돌 등): 스윕 중단하고 원인 수정 우선. 개별 arm 실패는 계속 진행.
- **pytest 기존 실패**: plain master 단독 실행과 대조해 이번 변경 무관이면 기록만 하고 진행.
- **arm 결과가 비상식적**(예: WER 100%): 재측정 1회 → 재현되면 원장에 기록, 안 되면 `error`로 표기.
  과거 kor1~3 WER 과대평가가 **UI 렌더 아티팩트**였던 전례(Exp-182, kor2 95.1→25.0%)를 기억할 것 —
  이상 수치는 모델보다 **추출 계층을 먼저 의심**한다.

---

## 10. 절대 금지 (알려진 막다른 길 — 시간 낭비 방지)

- **닫힌 knob을 스윕하지 말 것**:
  - `beams` — turbo 재검증 완료(Exp-162, 2 확정)
  - `PLC` — turbo 재검증 완료(Exp-160, None 확정). 게다가 `core.py`의 `simulstreaming_params`에 필드가
    빠져 **서버에 도달조차 못 한다**(되켤 수 없음)
  - `init_prompt` / `static_init_prompt` — Exp-148(E2·provenance 유효) 전 파일 catastrophic. 기전 무관
  - **`--no-speech-threshold`(`nonspeech_prob`)** — **turbo에서 물리적으로 발동 불가.** Exp-164/165가
    2000+ 샘플 전부 `0.000000` 실측, 이번 27개 로그에서도 `no speech, stop` **0회**.
    **플래그가 살아 있어 스윕 대상으로 오해하기 쉬운 함정이다. 값을 아무리 바꿔도 무효.**
- **VAD 문턱 상향(0.4·0.5)** — Exp-084/117/164 전부 기각 + 기전 설명 확정(§2-3). 하향만 볼 것.
- **CRT 하향(2.5·2.8)** — Exp-146/147/162 기각. 상향만 볼 것.
- **logprob 강화(-1.5·-1.0)** — Exp-140/141 catastrophic. 완화만 볼 것.
- 경계 강제 재디코딩/flush 계열 — Exp-193/194 2회 기각·`EXPERIMENTS.md:110-117` 재시도 금지 명문.
- ytn2 "한국군 사성자…"·"상당한.. 상당한" 구간은 **실발화**(사용자 청취 확정) — 반복 억제 근거 금지.
- **held-out(ytn1·eng1·kinno)을 튜닝·조건 도출에 사용 금지** — 검증 단회만.
  (예외: eng1은 §5 저분산 스크리닝 채널로만 쓴다. 이 용도는 사용자 승인된 계획에 포함돼 있다.)
- **master 머지 금지** — 채택권고까지만.

---

## 11. 종료 시퀀스 (토큰 임박 또는 전 arm 소진 시에만)

1. 진행 중 측정은 **arm 단위로 마무리**(중간 강제 종료 금지). 워크트리 `.omc/` 산출물을 메인으로 복사.
2. 원장 JSON 최종 flush — 미처리 arm은 `pending`으로 남겨 **다음 세션이 그대로 이어받게** 한다.
3. 진행 리포트 최종 갱신 — 상단 요약: 트랙별 결론(승/패/판단유보/미착수), 채택권고 후보 목록과 근거 수치,
   거동 무변화 arm 목록, 아침 확인 요청 전체.
4. 측정 동반 트랙 전부 `/log-experiment` 기록 완료 확인(Exp-207~).
5. 이 goal 파일 상단에 실행 상태 1줄 추가 + `docs/goal_prompt/README.md` 표에 행 추가/갱신.
   **완료 시 archive 이동은 사용자 검토 후.**

### 다음 세션 재개 방법 (이어서 돌릴 때)

이 파일을 다시 첫 메시지로 붙여넣으면 된다. §6-1대로 **원장 JSON을 먼저 읽고** `pending` arm부터 이어간다.
Stage 0가 이미 끝나 있으면(브랜치에 커밋 존재) 건너뛴다.
