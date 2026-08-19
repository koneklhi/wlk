# 인계: 파라미터 튜닝 캠페인 재시작 (2026-08-19) — 12시간 자율 실행

> **이 파일을 새 Claude Code 세션의 첫 메시지로 통째로 붙여넣으면 바로 진행할 수 있다.**
> 전체 캠페인 지침 정본 = [docs/goal_prompt/GOAL_PARAM_TUNING_CAMPAIGN.md](../goal_prompt/GOAL_PARAM_TUNING_CAMPAIGN.md).
> 직전 인계장 = [2026-08-12_param-sweep-S1-resume-plan.md](2026-08-12_param-sweep-S1-resume-plan.md) — **그 문서는 이 문서로 대체(superseded)됐다.**
> 이 문서와 goal 프롬프트가 충돌하면(§2-1 베이스라인·§4 arm 원장·§10 금지 목록) **이 문서가 우선한다** —
> goal 프롬프트는 2026-08-07~14 시점 기준이고, 이 문서가 2026-08-19 master(E8) 기준 갱신판이다.
> 시간 예산 = **약 12시간**. 사용자 확인 없이 §0 행동 규칙대로 자율 진행한다.

---

## 0. 30초 요약

- **무엇**: 실시간 STT(turbo) 파라미터 계통 스윕(S1 넓게 스크리닝)을 **처음부터 재시작**한다.
- **왜 재시작인가 (이어달리기가 아니라)**: 2026-08-12 중단 이후 ① 캠페인 워크트리가 삭제돼 미커밋
  원장(9 arm 결과)이 **유실**됐고(브랜치에 커밋된 원장 = 레코드 0건), ② master가 58커밋 전진하며
  **epoch E6→E8**(QG refresh 보존형 전환 + 콜드스타트 보호창)·**하니스 H1→H2**(배포 UI 스크래핑)로
  바뀌어 구 S1 결과가 어차피 **전량 stale**이다(파국 실패모드 자체가 바뀜).
- **그 사이 확정된 것**: Track B(QualityGate) 3축이 **전부 종결**됐다(Exp-212~219가 스윕 없이 해치움).
  arm 55개 → **27개**로 준다. 구 S1의 `speech_pad_ms↑`·`vad 0.25` 유력 신호는 '방향 신호'로 승계.
- **할 일**: ① Stage 0′(워크트리 재생성 + master 리베이스 + 하니스 3건 갱신, ~1.5~2h) →
  ② S1 v2(27 arm, 우선순위 순, ~12.8h — 12h 내 20 arm 내외 소화 예상, 잔여는 원장이 이어받음).

---

## 1. 2026-08-12 인계장 이후 달라진 것 (전제 갱신 — 재발굴 금지)

### 1-1. 워크트리 삭제·원장 유실 → S1은 0에서 재시작

`worktrees/param-tuning-campaign`이 제거됐다(`git worktree list`에 없음). 브랜치
`feat/param-tuning-campaign`(HEAD `845c89b`, master@`2b017d2` 분기)은 살아 있으나, 커밋된 원장
`docs/research/2026-08-07_param-sweep-ledger.json`은 **records: [] (0건)** — S1 9 arm 진행분은
워크트리의 미커밋 상태로만 있다가 함께 사라졌다. **구 S1 중간 결과 표는 직전 인계장 §3에만 남아 있다**
(BASE-0 17% / A2-speech-pad-150 0/12 / A3-vad-0.25 0/12 / A1-400 무출력 등). 아래 §1-2에 따라
그 수치는 **재사용 불가, 방향 신호로만** 쓴다.

### 1-2. Epoch E6→E7→E8 — 구 S1 결과가 stale인 첫째 이유

구 S1은 master@`2b017d2`(E6) 위에서 측정됐다. 이후:

| Epoch | Exp | 변경 (파국 실패모드를 직접 바꿈) |
|---|---|---|
| E7 (08-18) | Exp-210 | QG streak 도달 시 **무조건 버퍼 폐기 → 조건부 보존**(`_try_preserving_refresh`, 언어확신 p≥0.85 시 오디오 보존). 유실+환각의 공통 원인이던 경로가 바뀜 |
| E8 (08-19) | Exp-214 | 콜드스타트 보호창 Δt 상한 버그 수정(실경계 스탬프 후에만 상한 적용) + `quality_gate_reset_after` 기본값 **3→5** |
| E8 보정 | Exp-215 | `COLD_START_PROTECT_SECS=10.0` 유한 상한(kor3 성장루프 91.4%→41.7% 해소) |
| E8 필터 | Exp-218 | 성장형 프리픽스 반복루프 게이트 `_find_growing_repeat_storm`(`[AnchorRegrowFilter]`, 기존 AnchorRepeat와 OR) |

스윕이 재던 파국(bong1 환각 폭주·ytn2 코드스위칭 붕괴·kor3 반복루프)의 발생 경로가 전부 이 변경들에
걸린다 — **epoch 게이트상 구 S1 파국률은 E8 코드의 근거가 될 수 없다.**

### 1-3. 하니스 H1→H2 — stale의 둘째 이유 + 새 셋업 요건

Exp-207(`dbc70fa`, 08-14)로 경로 C가 내장 UI(`/dev`) → **배포 React UI(`/wlkies/`) DOM 스크래핑**으로
전환됐다(`eval.py --browser-ui deploy` 기본). 구 S1은 H1 측정이라 H2 수치와 직접 비교 불가.
**새 요건**: 워크트리에서 측정하려면 `frontend/static/` dist가 소스보다 최신이어야 한다
(`cd frontend/app; pnpm install; pnpm build` 선행 — gitignore라 새 워크트리엔 없다).
**측정 중 `pnpm build` 금지**(`emptyOutDir`가 서빙 중 dist를 비운다).

### 1-4. Track B(QualityGate) 전면 종결 — arm 9개 삭제

스윕이 하려던 일을 Exp-212~219가 표적 실험으로 끝냈다:

| 구 arm | 종결 근거 |
|---|---|
| B1 logprob −2.5/−3.0/−4.0/−10.0 | **완화 방향 영구 기각**(Exp-216): E8 fix 결합 재시도에서도 held-out ytn1 세션 서두 은닉번역 재현(WER 30.1%·LMR 19.7%). 기전 확정 — QG의 "쓰레기 직접 억제" 역할은 폐기 타이밍과 독립이라, 완화하면 확신에 찬 은닉번역이 그대로 커밋된다. 더 완화(−3.0 이하)는 더 악화. −1.5(강화)도 비채택(Exp-217, 회귀는 없으나 우위 없음) |
| B2 reset_after 5/8/999 | **축 종결 at 5**(Exp-219): 5가 이미 기본값(Exp-214), 6·8 재확인 무우위 + val=8은 9/9회차 0-firing 상태라 999는 무의미 |
| B3 CRT 3.5/4.0 | **CRT 자체가 사문**(Exp-212/213 실증): 스트리밍 세그먼트가 짧아 압축비 문턱 미달 + `_quality_gate`가 logprob 먼저 검사 후 즉시 반환 → CR 검사 미도달. 3.0·2.5 양쪽 0-firing. 값을 뭘 줘도 무효 |

추가 종결: **`BOUNDARY_PROTECT_SECS` 5.0→6.0 확대 기각**(Exp-211) — 이 축 상향도 닫힘.

### 1-5. 베이스라인·노이즈 정보 갱신 → 파국 기준값 교체 필수

현재 master(E8·H2) 베이스라인(N=3, diar-ON, `--lan auto`, EXPERIMENTS.md STATE 표 = SoT):

| 파일 | median | max | **파국 임계(median+8)** | 구 기준(08-07) |
|---|---|---|---|---|
| bong1 | 22.3 | 31.0 | **30.3** | 29.2→37.2 |
| ytn2 | 14.3 | 19.7 | **22.3** | 13.8→21.8 |
| sbs1 | 9.5 | 10.1 | **17.5** | 11.3→19.3 |
| kor1 | 16.4 | 22.2 | **24.4** (Track C 전용) | — |
| kor2 | 16.6 | 17.2 | **24.6** | 14.5→22.5 |
| kor3 | 33.1 | 44.4 | **41.1** | 38.4→46.4 |
| eng1 | 4.8 | 4.8 | **12.8** | 4.8→12.8 |

`sweep_runner.py`의 `BASELINE_MEDIAN_WER`(현재 08-07 값 하드코딩)를 이 표의 median으로 교체해야
한다(§3-3). 참고 노이즈 밴드(Exp-212, 동일 코드 N=9): bong1 19.9~34.6% · ytn2 10.8~21.7% ·
sbs1 8.3~10.7% — **bong1은 무개입으로도 임계 30.3을 넘는 회차가 나온다.** 절대 파국률이 아니라
**같은 세션에서 측정한 BASE-0 대비 비교**가 판정 기준인 이유다(BASE-0 재측정이 그래서 1순위 arm).

### 1-6. 리베이스 필요 — 충돌 6파일 예상

브랜치는 master 대비 58커밋 뒤처졌고, 겹치는 파일 = `scripts/eval.py`·`whisperlivekit/audio_processor.py`·
`config.py`·`core.py`·`parse_args.py`·`simul_whisper/backend.py`. 특히 **`quality_gate_reset_after`는
양쪽에서 독립적으로 CLI 승격**됐다(브랜치 S0-4 vs master `0217d66`) — 충돌 확실. 해소 지침 = §3-1.

참고로 master엔 그 사이 **시나리오 튜닝 그룹**(`--vad-threshold`·`--min-real-silence-secs`·
`--finalize-grace-secs` 등 Track A3/A5/E knob 전부)이 이미 CLI 노출돼 있다. 브랜치 고유로 남는 것은
③가지뿐: `--min-silence-duration-ms`·`--speech-pad-ms`·`--rewind-threshold` CLI + **eval.py
`--server-arg` 범용 패스스루**(master eval.py는 여전히 화이트리스트 방식) + sot_index 수정 + sweep_runner.

---

## 2. S1 v2 arm 목록 — 27개, 우선순위 순

원칙: OFAT(1 arm = 1 knob), `--server-arg=--<knob> --server-arg=<값>` 형태. 구 arm id 유지(교차 참조).
**우선순위 = 파일 순서**(runner가 순서대로 처리) — 12h 안에 끝까지 못 가도 위에서부터 소화된다.

| 순위 | arm | 값 | 근거 |
|---|---|---|---|
| 1 | **BASE-0** | (없음) | **필수 선행 대조군** — E8+H2 파국률 기준 재수립. 이것 없이는 어떤 arm도 판정 불가 |
| 2~4 | A2-speech-pad-ms | 60 / 100 / 150 | 구 S1 최유력(150=0/12, 단조 개선 경향, kor2 WER median −5.9). **실험 기록 0건**이던 knob + §2-3 기전 정합(실발화 덜 자르기) |
| 5~6 | A3-vad-threshold | 0.25 / 0.2 | 구 S1에서 0.25=0/12, 0.2=17%(bong1 2/2) — "하향은 맞되 과하면 역효과" 재확인 |
| 7 | A1-min-silence-duration-ms | 300 | 구 S1 동률(17%). **400·500은 제외** — 연속 발화 파일에서 완전 무출력(전사 0자) 기전 확정, VAD 계층이라 epoch 무관 유해 |
| 8~10 | D2-audio-max-len | 10 / 12 / 20 | Exp-161이 30→15만 확인 — 최적점이 15 아래일 수 있음 |
| 11~13 | D1-frame-threshold | 22 / 20 / 18 | 하향(조기 커밋) 미탐색. 상향(35)은 Exp-193 배포 opt-in으로 종결 |
| 14~17 | C1-max-context-tokens | 25 / 50 / 100 / 200 | turbo 미검증 + sot_index fix(브랜치) 선행 조건 충족. 스크리닝 세트에 kor1 자동 추가(`TRACK_C_EXTRA_FILES`). lmr_ko·AnchorRepeat 급증 시 즉시 탈락 |
| 18~20 | A5-min-real-silence-secs | 0.3 / 0.5 / 0.6 | base 실험만 존재 |
| 21~23 | A4-vac-chunk-size | 0.1 / 0.32 / 0.5 | Exp-075(base) 값 → turbo 재검증 |
| 24~25 | D3-min-chunk-size | 0.2 / 0.3 | 실험 0건 |
| 26~27 | D4-rewind-threshold | 100 / 400 | 실험 0건 |

**삭제된 arm** (v1 55개 → v2 27개): Track B 9개(§1-4) · A1-400/500(무출력 유해 확정) ·
**Track E 20개 = 유예 유지**(사용자 결정 2026-08-12: D까지 끝난 뒤 별도 판단 — 이 결정은 아직 유효).

**신규 축 후보 (이번 12h 범위 밖, 메모만)**: E8이 만든 CLI 미노출 상수들 —
`COLD_START_PROTECT_SECS`(10.0, Exp-215가 방금 보정) · `BOUNDARY_QG_REPROBE_WINDOW`(2.5) /
`_MIN_PROB`(0.85) · `_ANCHOR_REGROW_*` 4종(오프라인 스윕에서 넓은 평지 확인 — window 60/80/100 동일,
coverage 0.70~0.90 동일 → 우선순위 낮음). `BOUNDARY_PROTECT_SECS`는 상향 기각(Exp-211), 하향은
미탐색이나 Exp-213이 규명한 reset_after 상호작용 리스크가 있어 표적 실험감이지 스윕감이 아니다.
전부 CLI 승격 작업이 선행돼야 하므로 **S1 v2 완주 후 사용자 보고 시 후보로만 제시**한다.

---

## 3. Stage 0′ — 재부팅 작업 (예산 ~1.5~2h)

### 3-1. 워크트리 재생성 + master 리베이스

```powershell
# 메인 저장소에서
git worktree add worktrees/param-tuning-campaign feat/param-tuning-campaign
cd worktrees\param-tuning-campaign
cmd /c mklink /J .venv ..\..\.venv          # 공유 .venv Junction (새로 만들지 않는다)
git rebase master
```

충돌 해소 지침 (예상 6파일):

| 파일 | 지침 |
|---|---|
| `parse_args.py` / `config.py` / `core.py` | `quality_gate_reset_after` 중복 → **master 쪽 채택**(기본 5, `0217d66`), 브랜치 S0-4 hunk 폐기. 브랜치 신규 3 knob(`min-silence-duration-ms`·`speech-pad-ms`·`rewind-threshold`)은 유지 — **Config 필드 + `core.simulstreaming_params` 동시 등록** 확인(한쪽만 있으면 조용히 죽은 플래그) |
| `scripts/eval.py` | master H2 변경(`--browser-ui`·`--continue-on-harness-error` 등) + 브랜치 `--server-arg` 패스스루/`server_args` 결과 기록 → **양쪽 합집합** |
| `audio_processor.py` | master 로그 DEBUG 강등(`e2ca6ed`) + 브랜치 speech_pad/min_silence 배선 → 합집합 |
| `backend.py` | master 대규모 변경(regrow 게이트 등) 우선, 브랜치 hunk는 의도(스윕 knob 배선) 확인 후 이식 |

공통 함정: 충돌 해소 시 `getattr(...) or default` 금지 — 명시적 `0`이 falsy로 삼켜진다. **`is None`** 패턴 유지.
리베이스가 과도하게 꼬이면(동일 지점 3회 이상 재충돌) 대안: master에서 새 브랜치를 따고 4커밋을
cherry-pick — 충돌 내용은 같으니 보통 이득 없다. 완료 후 `git worktree` 제거는 이번 세션에서 하지 않는다.

### 3-2. 검증 (측정 시작 전 전부 GREEN이어야 함)

1. `.venv\Scripts\python.exe -m pytest tests/ -q` — master 874개 + 브랜치 스윕 테스트(≈20개) 전부 통과.
2. `.venv\Scripts\ruff.exe check` GREEN. (**`uv run` 절대 금지** — §6)
3. knob 배선 스모크: `tests/test_param_sweep_knobs.py` + v2 arm 27개 전부 서버 파서 파싱·값 반영 확인
   (구 세션이 58 arm에 했던 검증의 v2판).
4. 워크트리 셋업: `test_data/*.wav`(부재 시 mp3에서 ffmpeg 재생성 후 하드링크)·
   `model.safetensors`·`sortformer-4spk-v2.nemo` 하드링크 · `.omc/benchmarks`·`.omc/transcripts` 생성.
   returncode=3이면 venv 오염으로 속단하지 말고 **서버 로그부터** 읽는다.
5. `cd frontend/app; pnpm install; pnpm build` → 하니스 dist 신선도 검사 통과 확인(§1-3).
6. provenance 스모크 1회: `[provenance] ... QGreset=5 ... vbcable=ok` 확인 + 다른 세션 VBCable
   겹침(포트 8901·python 프로세스) 확인.

### 3-3. `scripts/sweep_runner.py` 갱신 3건

1. **파국 기준 교체**: `BASELINE_MEDIAN_WER`를 §1-5 표의 E8 median으로(kor1 16.4 **추가** — Track C의
   kor1 회차가 집계에 빠지지 않게). `CATASTROPHE_MARGIN_PP = 8.0` 유지. 주석에 근거(Exp-215/218 병합
   N=3, E8·H2) 명기.
2. **E8 거동 증거 태그 추가**: `BEHAVIOR_PATTERNS`에 `"qg_preserve": r"\[QGPreserve\]"` ·
   `"anchor_regrow": r"AnchorRegrowFilter"` 추가(기존 `AnchorRepeat` 패턴과 미중첩 확인됨).
   E7/E8 신설 경로의 발동량이 잡혀야 noise-control 판정이 정확해진다.
3. **무출력 분리 집계** (구 인계장 §5-1, 미구현 확인됨): `_extract_raw_wers`가 순회하는 `files` 배열에서
   전사 길이도 수집, 레코드에 `empty_transcripts: {count, total, by_file}` 추가 + 콘솔 1줄. 무출력은
   "knob이 파이프라인을 깼다"는 즉시 기각 신호라 파국(환각 폭주)과 분리한다. 회귀 테스트 2건.

추가 스모크: `_extract_results`가 **H2 eval.py 출력 스키마**(`file_summaries`/`files`)와 여전히 호환되는지
BASE-0 첫 실행에서 원장 레코드가 온전히 채워지는 것으로 확인(Exp-207이 eval.py를 +75줄 고쳤다).

### 3-4. arm·원장 v2 파일 생성

- `docs/research/2026-08-19_param-sweep-arms-v2.json` — §2 순서대로 27 arm(id·track·server_args 스키마는
  v1과 동일). Track C arm의 `track: "C"` 유지(`TRACK_C_EXTRA_FILES` kor1 추가 로직이 걸리게).
- `docs/research/2026-08-19_param-sweep-ledger-v2.json` — 신규 원장(빈 records로 초기화).
  구 원장·백업·노이즈플로어 파일은 그대로 동결(참고용).
- `docs/research/2026-08-19_param-sweep-progress-v2.md` — 진행 리포트 신설(구조 = goal 프롬프트 §8-2).

Stage 0′ 완료 시점에 브랜치에 커밋한다(메시지에 "Stage 0′ 재부팅: E8 리베이스 + 파국기준 갱신" 취지).

---

## 4. 12시간 실행 계획

| 구간 | 내용 | 예산 |
|---|---|---|
| 0~2h | Stage 0′ (§3) | 리베이스·검증·하니스 갱신·스모크 |
| 2~12h | S1 v2 무인 실행 | 27 arm × ~28.5분 ≈ 12.8h → **~20 arm 소화 예상**(BASE-0 + A2 + A3 + A1 + D2 + D1 + C1 + A5 언저리). 잔여는 원장이 이어받음 |

실행 명령 (detached — 도구 세션과 독립, 직전 중단 원인이 **사용자 수동 전원 끄기**였음을 기억하고
가능하면 전원 유지 요청을 진행 리포트 상단에 남긴다):

```powershell
$wt = "c:\Users\A040-000-0001\Desktop\260605wlk\wlk\worktrees\param-tuning-campaign"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONUNBUFFERED = "1"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
Start-Process -FilePath "$wt\.venv\Scripts\python.exe" `
  -ArgumentList @("-u","scripts/sweep_runner.py",
    "--arms","docs/research/2026-08-19_param-sweep-arms-v2.json",
    "--stage","S1",
    "--ledger","docs/research/2026-08-19_param-sweep-ledger-v2.json") `
  -WorkingDirectory $wt `
  -RedirectStandardOutput "$wt\.omc\benchmarks\sweep_S1v2_${ts}_console.log" `
  -RedirectStandardError  "$wt\.omc\benchmarks\sweep_S1v2_${ts}_console.err" `
  -WindowStyle Hidden -PassThru
```

- 기동 후 `Wait-Process`를 background로 걸어 완료 알림을 받는다. **폴링 금지.**
- 측정은 **메인 세션에서 직접**(서브에이전트 위임 금지 — 조기 정지 전력). **측정 중 워크트리 코드 mutation 금지.**
- 중단돼도 같은 명령 재실행이면 원장의 `done` arm을 건너뛰고 이어간다.

체크포인트:

| 시점 | 확인 |
|---|---|
| 기동 직후 1분 | 콘솔 `대상 arm 27개` + BASE-0부터 시작. 다르면 arms/ledger 경로 오류 |
| 첫 arm(BASE-0) 완료 ~28분 | 원장 append + `catastrophe`(신 임계 기준)·`empty_transcripts`·`qg_preserve`/`anchor_regrow` 카운트 채워짐 + `vbcable_ok=true`. **여기서 H2 스키마 호환(§3-3)도 함께 확정** |
| 이후 arm마다 | 원장 flush 확인만. VBCable 무음/100% WER 연속이면 §6 복구 플레이북 |

---

## 5. 판정·기록 규칙

- **S1 판정 = goal 프롬프트 §5 준용** (서열 없음): ① 거동이 실제로 바뀌었는가(§5-1 로그 증거 —
  이제 `qg_preserve`·`anchor_regrow` 포함) ② 파국이 BASE-0 대비 뚜렷이 늘었는가(방향 신호). 증거 0이면
  `noise-control`(0-firing 회차 = 동일 코드 = 노이즈 대조군 — Exp-219 val=8이 정확히 그 사례).
- **파국 판정은 반드시 같은 세션 BASE-0와 비교**한다 — bong1은 무개입 노이즈 밴드(19.9~34.6)가 신 임계
  (30.3)를 걸치므로 절대율만 보면 오판한다(§1-5).
- **무출력(`empty_transcripts`) > 파국**: 무출력이 잡히면 그 arm은 즉시 `prune`(파이프라인 파괴).
- S1 완료(또는 12h 소진) 후: §0-2 자율 규칙(goal 프롬프트)대로 S2 승격 후보를 정해 진행 리포트에
  기록하되, **S2(repeat 16)는 이번 12h에 시작하지 않는다**(예산상 불가) — "다음 밤 S2 후보" 목록화까지.
- **기록**: 트랙 단위로 `/log-experiment` — **Exp-221부터**(220까지 사용됨), 측정 언어모드 `--lan auto` 명시,
  Epoch 열 = E8. 구 S1 유실 사실과 승계한 방향 신호(A2·A3)를 첫 기록에 남긴다.
- 원본 발화 확인 규칙·이상 수치 추출계층 우선 의심 등 정성 규칙 = goal 프롬프트 §7·§9-3 그대로.

---

## 6. 행동 규칙 (반드시 지킬 것 — 갱신판)

- **자율 진행** — 질문하지 않고 goal 프롬프트 §0-2 기본 선택지로 결정, 사유는 원장·리포트에 기록.
  예외(여전히 사용자 확인 대상): **master 머지 금지**(채택권고까지만), `.venv`/의존성 변경, 워크트리
  삭제, force-push.
- **`uv run`·`uv pip`·`uv add/remove/lock/venv`·extras 없는 `uv sync` 절대 금지**(공유 Junction `.venv`
  오염 = 측정 전멸). lint = `.venv\Scripts\ruff.exe`, 테스트 = `.venv\Scripts\python.exe -m pytest` 직접.
- **측정 언어모드 = `--lan auto` 단일**(kor·eng 포함 예외 없음). 경로 C만. diar-ON + Sortformer.
- **닫힌 knob 스윕 금지 (갱신판)** — 구 §10에 아래가 추가됐다:
  - `beams`(Exp-162 종결) · `PLC`(Exp-160 종결·배선상 되켤 수 없음) · `init_prompt`류(Exp-148) ·
    `--no-speech-threshold`(**turbo에서 물리적 발동 불가 — 살아있는 함정 플래그**)
  - VAD 문턱 상향 · `min_silence_duration_ms` 400 이상(무출력 확정)
  - **`logprob_threshold` 양방향 종결**(강화 Exp-140/141/217 · 완화 Exp-216 영구 기각)
  - **`quality_gate_reset_after` 종결 at 5**(Exp-219) · **CRT 전체 사문**(Exp-212 — 상향·하향 모두 무효)
  - **`BOUNDARY_PROTECT_SECS` 상향**(Exp-211 기각)
  - 경계 강제 재디코딩/flush 계열(Exp-193/194 재시도 금지 명문)
- ytn2 "한국군 사성자…"·"상당한.. 상당한" = **실발화**(사용자 청취 확정) — 반복 억제 근거 금지.
- held-out(ytn1·kinno) 튜닝 사용 금지(eng1은 승인된 스크리닝 채널 용도만).
- 워크트리를 제거해야 할 일이 생기면 **반드시 `cmd /c rd .venv`로 Junction부터 해제**(공유 .venv 파괴
  사고 2회 전력 — 단 이번 캠페인에서 워크트리 삭제는 사용자 확인 대상이라 마주칠 일 없어야 한다).

---

## 7. 종료 시퀀스 · 다음 세션 재개

1. 진행 중 arm은 arm 단위로 마무리(강제 종료 금지) → 원장 최종 flush(미처리 arm은 `pending` 유지).
2. 진행 리포트 v2 최종 갱신: 트랙별 결론 / S2 승격 후보와 근거 / noise-control 목록 / 아침 확인 요청
   (신규 축 후보 §2 포함).
3. `/log-experiment`(Exp-221~) 완료 확인 → 워크트리 `.omc/` 산출물 메인 복사 → 브랜치 커밋.
4. **다음 세션 재개**: 이 파일을 다시 첫 메시지로 붙여넣는다. Stage 0′ 완료 여부는 브랜치에 리베이스
   커밋이 있는지로 판단하고, 있으면 §4 실행 명령만 다시 돌리면 원장이 이어받는다.
