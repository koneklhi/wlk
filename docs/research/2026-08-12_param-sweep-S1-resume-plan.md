# 인계: 파라미터 튜닝 캠페인 S1 재개 (2026-08-12)

> ⚠️ **SUPERSEDED (2026-08-19)** — 이 문서 기준의 재개는 더 이상 불가능하다: 캠페인 워크트리가 삭제돼
> 미커밋 원장(S1 9 arm 결과)이 유실됐고, master가 E6→E8(Exp-210/214/215/218)·하니스 H1→H2(Exp-207)로
> 바뀌어 §3 중간 결과는 전량 stale(방향 신호로만 유효)이며, Track B는 Exp-212~219로 전면 종결됐다.
> **후속 정본 = [2026-08-19_param-sweep-restart-plan.md](2026-08-19_param-sweep-restart-plan.md).**
> 이 파일은 구 S1 중간 결과 표(§3)의 보존용으로만 남긴다.

> **이 파일을 새 Claude Code 세션의 첫 메시지로 통째로 붙여넣으면 이어서 진행할 수 있다.**
> 전체 캠페인 지침 정본 = [docs/goal_prompt/GOAL_PARAM_TUNING_CAMPAIGN.md](../goal_prompt/GOAL_PARAM_TUNING_CAMPAIGN.md)
> (master `c9f8a74`). 이 문서는 그 위에 **직전 세션에서 새로 확정된 사실 + 지금 당장 할 일**만 얹은 인계장이다.
> 아래 §1~§4를 읽고 **§5부터 바로 실행**하면 된다. 사용자 확인을 기다리지 말 것(§4 자율 판단 규칙).

---

## 0. 30초 요약

- **무엇**: 실시간 STT(whisperlivekit/turbo)의 파라미터 58개 arm을 계통 스윕해 성능 개선 방향을 찾는 캠페인.
- **왜**: 최근 T1~T5 미세 필터 트랙이 전부 "0-firing·재현 실패"로 끝나 수확 체감. 반면 과거 "방향 종료"
  선언 다수가 **한쪽 방향만 탐색**했거나 **base 기질(74M)에서 정해진 뒤 turbo로 바뀐 채 재검증 안 됨**.
- **지금**: S1(넓게) 스크리닝이 58 arm 중 **9개 완료**된 상태에서 **사용자 PC 수동 종료로 중단**됨.
  코드·하네스 문제 아님. 원장이 보존해 손실 0.
- **할 일**: `--track A B C D`로 S1 재개(Track E 20개는 유예). 29 arm ≈ 13.8시간.
- **이미 나온 성과**: `speech_pad_ms` 상향이 파국률을 17%→0%로 낮추는 유력 신호(실험 기록 0건이던 knob).
  `min_silence_duration_ms` 상향은 유해 확정(전사 완전 무출력).

---

## 1. 작업 환경 (경로·브랜치·커밋)

| 항목 | 값 |
|---|---|
| 작업 위치 | `c:\Users\A040-000-0001\Desktop\260605wlk\wlk\worktrees\param-tuning-campaign` |
| 브랜치 | `feat/param-tuning-campaign` (HEAD `845c89b`) |
| 메인 저장소 | `c:\Users\A040-000-0001\Desktop\260605wlk\wlk` (master `c9f8a74`) |
| 준비 상태 | `.venv` Junction · `test_data/*.wav` · 모델 하드링크 · `.omc/` 디렉터리 **전부 완료** — 추가 셋업 불필요 |

**브랜치 커밋 이력** (전부 이 캠페인)

```
845c89b docs(sweep): S1 넓게 스크리닝 착수 기록
fc90956 fix(sweep): 파국 발생률 기반 재설계 — 저분산 채널 전제가 실측으로 무너짐
f483c97 fix(sweep): 스모크에서 잡힌 드라이버 버그 2건 (server-arg 등호 형식 + repeat=1 결과 추출)
e99f501 feat(sweep): Stage 0 하네스 — server-arg 패스스루 + 신규 knob 4종 CLI 노출 + sot_index 보정
```

**핵심 파일**

| 파일 | 역할 |
|---|---|
| `scripts/sweep_runner.py` | 무인 연속 실행 드라이버(중단 내성·재개·파국 집계). **이것으로만 측정 실행** |
| `docs/research/2026-08-07_param-sweep-arms.json` | arm 58개 정의(id·track·server_args) |
| `docs/research/2026-08-07_param-sweep-ledger.json` | **원장 = 세션 간 유일한 상태 저장소.** append-only |
| `docs/research/2026-08-07_param-sweep-progress.md` | 사람이 읽는 진행 리포트 |
| `docs/research/2026-08-07_noise-floor-ledger.json` | 노이즈 바닥 실측(BASE-0 ×5) 원본 |
| `scripts/eval.py` | 경로 C 측정 하니스(`--server-arg` 패스스루가 Stage 0에서 추가됨) |

> 미커밋 상태로 원장(`...ledger.json`)이 수정돼 있다(중단 시점 레코드). 정상이며, 재개 후 함께 커밋하면 된다.

---

## 2. 직전 세션에서 확정된 것 (재발굴 금지 — 여기서 출발)

### 2-1. Stage 0 하네스 — 완료

측정 자체가 불가능했던 병목을 뚫었다. `eval.py`가 서버 인자를 **하드코딩 화이트리스트**로만 넘겨서
계획한 knob 대부분이 경로 C로 측정할 방법이 없었다.

- `--server-arg` 범용 패스스루 추가(+ provenance/결과 JSON에 arm 원문 기록). 기존 provenance의 `beams=`는
  정적 기본값을 프로브한 **cosmetic 값**이라 arm 라벨로 쓸 수 없다 — 반드시 `server_args` 기록을 볼 것.
- **신규 CLI knob 4종 노출**: `--min-silence-duration-ms`(200) · `--speech-pad-ms`(30, 그동안 전달조차
  안 되던 값) · `--quality-gate-reset-after`(3) · `--rewind-threshold`(200).
  전부 기본 `None` → 기존 하드코딩 상수 폴백(무회귀 검증됨).
- `AlignAtt._check_no_speech`의 `sot_index` 문맥 오프셋 버그 수정(Track C 선행 조건).
- 검증: ruff GREEN · pytest **818 passed** · 58 arm 전부 서버 파서 파싱·값 반영 확인.

> **배선 함정(반복 금지)**: 신규 knob은 `WhisperLiveKitConfig` 필드 + `core.simulstreaming_params`에
> **동시** 등록해야 한다. 한쪽만 하면 `from_namespace`가 값을 조용히 버려 죽은 플래그가 된다
> (`--periodic-lang-check`가 정확히 그 상태로 죽어 있음). 또 `getattr(...) or default` 금지 —
> 명시적 `0`이 falsy로 삼켜진다. `is None`을 쓸 것.

### 2-2. ★ "저분산 채널" 전제가 무너졌다 → 파국 발생률 기반으로 재설계

Stage 0 스모크 검증 중 노이즈 바닥을 재측정했다. **동일 코드(BASE-0)로 6회 반복**한 결과:

| file | 실측 sd (n=6) | range | 이전에 N=3이 보고한 sd |
|---|---|---|---|
| ytn2 | **10.8%p** | 11.8~38.9 | 1.5 |
| sbs1 | **5.8%p** | 7.7~23.2 | 1.4 |
| kor2 | **6.7%p** | 15.9~31.0 | 1.4 |
| eng1 | 0.9%p | 4.8~6.7 | 1.5 |

N=3 sd는 자유도 2짜리라 운 좋게 뭉친 값이었다. 2026-08-07 마스터 9파일 N=3을 재구성하면
**27 file-run 중 3건(11%)이 median+8%p 초과** — bong1·ytn1·kinno에 떨어졌을 뿐 파국은 항상 있었다.
`git diff master..HEAD`(무회귀)와 master 대조군 재측정(sd 1.3/1.5/2.4/1.0)으로 **Stage 0 코드가 원인이
아님**을 확인했다. 시스템 자체의 성질이다.

→ **median 서열 비교는 N≤3에서 검정력이 없다**("어느 arm이 운이 좋았나"를 재는 수준).
그래서 판정을 **파국 발생률**(파일별 baseline median + 8%p 초과 회차 비율)로 바꿨다.
구현 = `sweep_runner.py`의 `_extract_raw_wers` / `_catastrophe_summary` (`BASELINE_MEDIAN_WER`,
`CATASTROPHE_MARGIN_PP`가 SoT). 관측 밀도를 위해 파국이 잘 나는 **bong1·kor3을 스크리닝 세트에 포함**.

**재설계된 단계 정의** (`STAGES` dict):

| 단계 | 세트 | repeat | 목적 |
|---|---|---|---|
| **S1 넓게** | 6파일(bong1·ytn2·sbs1·kor2·kor3·eng1) | 2 | 서열 안 매김. 거동 변화 + 확실히 나쁜 것만 거름 |
| **S2 깊게** | 동일 6파일 | 16 | `--only`로 생존 arm만. 96 file-run으로 발생률 비교 |
| S3 채택확정 | 테스트 6파일(bong1·ytn2·sbs1·kor1~3) | 3 | CLAUDE.md §4 게이트 |
| S4 최종검증 | bong1 | 5 | 최악값 확인 |

### 2-3. S1 중단 원인 — 코드 문제 아님, 사용자 수동 전원 끄기

> `2026-08-11 20:41:33` Event 1074 — StartMenuExperienceHost가 **전원 끄기** 실행(user `A040-000-0001`)
> → 20:41:52 이벤트 로그 중지 → `2026-08-12 08:31:04` 재부팅

두 `error` 레코드의 NTSTATUS가 확증한다 — `A4-0.1` = `0x40010004`(DBG_TERMINATE_PROCESS, 11/12 file-run
정상 완료 후 강제 종료), `A4-0.32` = `0xC000026B`(STATUS_DLL_INIT_FAILED_LOGOFF, 0.3초).
스윕은 15:58~20:41 **4시간 43분** 실행. **원장 중단 내성이 정상 작동해 완료된 9 arm은 온전**하고,
`error` 2건은 `done`이 아니므로 재실행 시 자동 재시도된다.

---

## 3. S1 중간 결과 (9/58 완료, arm당 12 file-run)

| arm | 파국 | bong1 / ytn2 / sbs1 / kor2 / kor3 / eng1 |
|---|---|---|
| **BASE-0 (대조군)** | 2/12 (17%) | 1/2 · 1/2 · 0/2 · 0/2 · 0/2 · 0/2 |
| A1-min-silence-300 | 2/12 (17%) | 0/2 · 1/2 · 0/2 · 1/2 · 0/2 · 0/2 |
| **A1-min-silence-400** | **5/12 (42%)** | 0/2 · 1/2 · **2/2** · **2/2** · 0/2 · 0/2 |
| A1-min-silence-500 | 3/12 (25%) | 2/2 · 0/2 · 0/2 · 1/2 · 0/2 · 0/2 |
| A2-speech-pad-60 | 1/12 (8%) | 0/2 · 1/2 · 0/2 · 0/2 · 0/2 · 0/2 |
| A2-speech-pad-100 | 1/12 (8%) | 0/2 · 1/2 · 0/2 · 0/2 · 0/2 · 0/2 |
| **A2-speech-pad-150** | **0/12 (0%)** | 전부 0/2 |
| **A3-vad-0.25** | **0/12 (0%)** | 전부 0/2 |
| A3-vad-0.2 | 2/12 (17%) | **2/2** · 0/2 · 0/2 · 0/2 · 0/2 · 0/2 |

**① `speech_pad_ms` 상향이 유력** — 30(기본)=17% → 60=8% → 100=8% → **150=0%**. 세 값 모두 대조군보다
낫고 단조 경향. WER median도 kor2 19.0→13.1, sbs1 10.1→9.5 개선. **실험 기록 0건이던 knob**이며,
goal 프롬프트 §2-3 조준점("실발화를 덜 자르게 → 조각→환각 연쇄 차단")과 정합한다.

**② `vad_threshold` 0.25가 최적점** — 0.25=0%, 0.2=17%(bong1 2/2). 하향은 맞되 과하면 역효과.

**③ `min_silence_duration_ms` 상향은 유해 확정 (Exp-173 외삽 가설 반증)** —
`400`에서 sbs1·kor2 전사가 **0자(완전 무출력)**. 지표 아티팩트가 아니라 진짜 실패다. 연속 발화
파일(뉴스·낭독)은 400ms 침묵이 안 생겨 VAD 종료 이벤트가 뜨지 않고, 아무것도 확정되지 않는다.

> **표본 주의**: arm당 12 file-run은 작아 `0/12`가 우연일 수 있다. 확정은 S2(96 file-run)에서.
> 사용자 결정(2026-08-12): **S2는 S1 전수 완료 후** 일괄 수행(트랙 간 비교 공정성).

---

## 4. 행동 규칙 (반드시 지킬 것)

- **사용자에게 묻지 않고 자율 진행한다.** 결정 지점별 기본 선택지는 goal 프롬프트 **§0-2 표**에 명문화돼
  있다(S1→S2 승격 기준, S2→S3 후보 수, Track F 착수 조건 등). 판단 근거는 원장·진행 리포트에 남긴다.
- **여전히 사용자 확인 대상**(자율화 제외): master 머지, `.venv`/의존성 변경, 워크트리 삭제, force-push.
  이 캠페인 범위에선 전부 금지돼 있어 마주칠 일이 없어야 한다.
- **master 머지 금지** — 채택 게이트를 통과해도 "채택권고·머지 대기"로 기록만 한다.
- **`uv run`·`uv pip`·`uv add/remove/lock/venv`·extras 없는 `uv sync` 절대 금지**(공유 `.venv` Junction
  오염 = 측정 전멸). lint는 `.venv\Scripts\ruff.exe`, 테스트는 `.venv\Scripts\python.exe -m pytest` 직접 호출.
- **측정은 메인 세션에서 직접**(서브에이전트 위임 금지 — 조기 정지 전력). 측정 중 워크트리 코드 수정 금지.
- **측정 언어모드 = `--lan auto` 단일**. kor·eng 포함 예외 없음.
- **닫힌 knob 스윕 금지**: `beams`·`PLC`·`init_prompt`/`static_init_prompt`·**`--no-speech-threshold`**
  (turbo에서 no_speech 헤드가 항상 0.000000이라 물리적으로 발동 불가 — 플래그는 살아 있어 함정).
  VAD 문턱 **상향**, CRT **하향**, logprob **강화** 방향도 전부 기각 완료. 상세 = goal 프롬프트 §10.
- **이상 수치는 모델보다 추출 계층을 먼저 의심**(과거 kor1~3 WER 과대평가가 UI 렌더 아티팩트였던 전례).
  단 이번 A1-400 무출력은 전사 0자를 직접 확인한 **진짜 실패**다.

---

## 5. 지금 할 일

### 5-1. (선행, 소규모) 무출력 실패를 파국과 분리 집계 — `scripts/sweep_runner.py`

A1-400에서 드러났듯 파국에는 성격이 다른 두 부류가 있다: **환각 폭주**(WER↑)와 **완전 무출력**(전사 0자).
지금은 둘 다 `catastrophe`로만 센다. 무출력은 knob이 파이프라인을 깨뜨렸다는 뜻이라 즉시 기각 근거이므로
분리한다.

- `_extract_raw_wers`가 순회하는 같은 `files` 배열에서 전사 길이도 수집(추가 I/O 없음)
- 레코드에 `empty_transcripts: {count, total, by_file}` 추가 + 콘솔 1줄 표시
- 회귀 테스트 2건(무출력 감지 / 정상 전사 오탐 없음)
- 검증: 이미 저장된 A1-400 결과 JSON(전사 0자 확인됨)에 적용해 감지되는지 확인 — **재측정 불필요**

### 5-2. S1 재개 (Track E 유예)

```powershell
# 사전: 다른 세션의 VBCable 점유 확인(포트 8901 · python 프로세스)
$wt = "c:\Users\A040-000-0001\Desktop\260605wlk\wlk\worktrees\param-tuning-campaign"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUNBUFFERED = "1"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
Start-Process -FilePath "$wt\.venv\Scripts\python.exe" `
  -ArgumentList @("-u","scripts/sweep_runner.py",
    "--arms","docs/research/2026-08-07_param-sweep-arms.json",
    "--stage","S1",
    "--ledger","docs/research/2026-08-07_param-sweep-ledger.json",
    "--track","A","B","C","D") `
  -WorkingDirectory $wt `
  -RedirectStandardOutput "$wt\.omc\benchmarks\sweep_S1_${ts}_console.log" `
  -RedirectStandardError  "$wt\.omc\benchmarks\sweep_S1_${ts}_console.err" `
  -WindowStyle Hidden -PassThru
```

- `done`인 9 arm 자동 skip, `error` 2건은 재시도 — **추가 조치 불필요**
- 대상 **29 arm**(A잔여 6 · B 9 · C 4 · D 10) ≈ **13.8시간**(arm당 ~28.5분). `arms.json` 순서가
  A→B→C→D라 별도 정렬 불필요
- **Track E(문장확정·화자 20 arm)는 사용자 결정으로 유예** — D까지 끝난 뒤 별도 판단
- **detached로 기동**(도구 세션과 독립). 기동 후 `Wait-Process`를 background로 걸어 완료 알림을 받고,
  **폴링하지 말 것**
- 근무시간(~12h) 내 **A·B·C 전부(19 arm) + D 일부** 소화 예상. 퇴근 시 전원이 꺼지면 다음날 같은 명령으로
  재개(원장이 이어받음)

### 5-3. 완료 후

1. 원장에서 파국률 분석 — **`(id, stage)` 중복 주의**: append-only라 A4는 error 레코드와 재시도 done
   레코드가 공존한다. 분석은 `status=='done'` 중 **최신 것**만 취할 것
2. goal 프롬프트 §0-2 기준으로 S2 승격 arm 선정 → S2(repeat=16) 실행
3. 진행 리포트 갱신 + 트랙 종료 시 `/log-experiment`(Exp-207부터, 측정 언어모드 명시)

### 5-4. 검증 체크포인트

| 시점 | 확인 |
|---|---|
| 재개 직후 1분 | 콘솔에 `대상 arm 29개 (전체 58개 중, 완료분 제외)` — 9개 skip 반영. 다르면 원장 경로/필터 오류 |
| 첫 arm 완료(~28분) | 원장 append + `catastrophe`·`empty_transcripts` 채워짐 + `vbcable_ok=true` |
| 코드 변경 시 | `ruff check` + `pytest tests/ -q` (직전 **818 passed** 유지) |
