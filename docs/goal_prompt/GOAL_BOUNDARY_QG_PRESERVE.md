# Goal Prompt — 경계 복구 구간 QualityGate 버퍼 폐기 유실(Type B 삼킴) 제거 (무인 자율 루프)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: **화자/언어전환 경계 직후 QualityGate 연속 억제가 `refresh_segment(complete=True)`로
> 버퍼(=새 화자 발화 서두 오디오)를 통째로 폐기해, 실제 발화가 비가역 유실되고 그 자리를
> 같은 스크립트 환각("예수님과 관련 네, 감사합니다"류)이 채우는 삼킴(Type B)**을 제거한다.
> 근본원인은 실측 로그로 규명 완료(§1). 이 루프는 그 수정을 구현·측정·기록하고 채택 여부만 사용자에게 묻는다.
>
> ⚠️ **진행 규율 — 완전 자율 (사용자 장시간 부재 가정)**:
> - **모든 중간 판단(구현 세부·임계값 선택·재측정 여부·스크리닝 기각·재시도)은 자율 결정**하고 근거를 기록.
> - CLAUDE.md §4 "게이트 애매 시 사용자 질의"는 이 루프에서 **"판단 보류 + 최종 보고서에 질의 항목 축적"**으로 대체.
> - **유일한 사용자 질문 = 마지막 채택(머지) 여부.**
> - **master 머지는 절대 하지 않는다** — 채택 확정 측정까지 끝내고 브랜치에 커밋만 남긴 뒤 사용자 승인 대기.
> - ★ **사용자 명시 제약: 이 개선은 이전 성능을 저하시켜서는 안 된다.** 짝지음 A/B 순효과에서
>   화자분리 F1·WER worst-case가 회귀하면 파라미터 보수화 또는 기각 권고로 전환한다(§4).

---

## 0. 현재 상태 / 준비 (2026-07-13)

- **master = Epoch 5 (E5, turbo 기질), `6df6e2f`** (Exp-176 silence-grammar-gate 머지 포함 — 오늘 로그에 `[SilenceGate]` 발동 확인됨).
- **이 goal의 출발 증거 (같은 날 실측 — 반드시 먼저 읽을 것)**:
  - 벤치마크: `.omc/benchmarks/eval_20260713_1928_deploy_symptom_repro_N3.json`(테스트 3파일 N=3) ·
    `.omc/benchmarks/eval_20260713_1952_kinno_symptom_repro_N3.json`(kinno N=3)
  - 서버 로그(trace-tokens ON): `.omc/server_logs/server_{bong1,ytn2,sbs1,kinno}_C_R{1..3}_20260713_19*.log`
  - **핵심 사례 로그**: `server_ytn2_C_R1_20260713_193831.log` 라인 ~6460–6560 (§1의 전체 인과 사슬이 이 구간에 있다)
  - 전사: `.omc/transcripts/{파일}_C_R{n}.txt`
- **동일 날짜 baseline 수치 (참고용 — 판정은 짝지음 A/B 순효과로)**:

  | 파일 | WER med | WER max | 화자F1 med | 비고 |
  |---|---|---|---|---|
  | bong1 | 34.1% | 36.9% | 51.3% | |
  | ytn2 | 21.2% | 24.1% | 76.2% | R1에 Type B 삼킴 1건 실측 |
  | sbs1 | 13.1% | 13.7% | 100.0% | |
  | kinno | 30.5% | **72.0%** | 69.0% | R3 catastrophic(QG refresh 3회), R1 22.0%(0회) — 발생 횟수와 강한 상관 |

- **채택 우선순위 = regime v2** (EXPERIMENTS.md STATE 정본): 화자분리 F1 worst-case 미회귀 → WER max 미회귀 →
  WER median 개선 → 문장분리 F1(후순위·Case A 허용). Case B(단어 중간 분절)는 수치 무관 hard-fail.
  변동성이 크므로 STATE 게이트 표를 맹신하지 말고 **플래그 ON/OFF 짝지음 A/B(동일 세션)로 순효과를 직접 잰다**(Exp-175/176 방법).
- **워크트리 준비 (자율 수행)**: 현재 master(`6df6e2f`+)에서 `exp/boundary-qg-preserve` 브랜치 + `worktrees/boundary-qg-preserve` 워크트리.
  - `.venv`는 **메인 저장소 Junction 공유**(CLAUDE.md 워크트리 규약) — 새로 만들지 않는다.
  - **측정은 반드시 cwd=워크트리에서**([[worktree-eval-import-resolution]] editable 설치 함정), `--model-dir`·`--files`·
    `--sortformer-model`은 메인 저장소 절대경로. 측정 전 import 경로·`vbcable=ok`([[vbcable-loopback-instability]]) 확인.

## 1. 근본원인 (규명 완료 — 2026-07-13 실측 로그. 재조사 불필요)

**대표 사례 (ytn2 R1, 84s 부근)**: 정답 "해서 한국군 사령관 조건을 기초로 한 전작권 전환을 하는 방향으로
상당한 진전이 있었음에 합의를 했습니다"(EN→KO 통역 문장)가 통째로 사라지고
`예수님과 관련 네, 감사합니다. 네, 네, 감사합니다.` 환각으로 대체됐다. 인과 사슬(로그 순서 그대로):

1. **화자전환 eager 언어감지 실패**: diar `ChangeSpeaker` 도착 → `new_speaker()`가 경계창 1.5s로 감지
   ([backend.py](../../whisperlivekit/simul_whisper/backend.py) `:337-339`, `min_prob=0.85`) →
   `[ShortSilenceLangCheck] 최근 1.5s → en (p=0.54)` → **None**(경계 오디오가 EN 꼬리+KO 서두 혼합이라 확신도 붕괴).
   `[NewSpeaker] det_after=None keep_secs=1.34 kept_segments_len=1.53s`.
2. **폴백 감지는 곧 성공 — 감지 실패 자체는 치명 아님**: 다음 infer의 지연 감지
   ([align_att_base.py](../../whisperlivekit/simul_whisper/align_att_base.py) `_detect_language_if_needed` `:233-263`, eager 문턱 1.5s)가
   `Detected language: ko with p=0.9064` → `[LangSwitch] 토크나이저 적용: ko (prev=en, switch=True)` — 올바른 언어를 빠르게 잡았다.
3. **경계 오디오 저신뢰 디코드 → QG 연속 억제**: 유지된 1.53s 혼합 경계 오디오를 ko로 디코드 → `어`/`이`/`그` 파편,
   `avg_logprob -3.284 < -2.0` → `[QualityGate]` 억제 3연속(`quality_gate_reset_after=3`,
   [simul_whisper/config.py](../../whisperlivekit/simul_whisper/config.py) `:26`).
4. **★ 비가역 유실 지점**: `_on_quality_suppressed`(`:653-671`)가 `refresh_segment(complete=True)`(`:670`) 호출 →
   `state.segments = []` **버퍼 전량 폐기**(`refresh_segment` 폐기 분기 `:148-150`). **이 1.53s가 새 화자 문장의 서두 오디오다** —
   재디코딩으로 복구 불가능한 순유실.
5. **삼킴 완성**: 이후 도착 오디오를 문장 중간부터 맨땅 디코드 → 서두 문맥 없는 저신뢰 구간에서
   `예수님과 관련…` 오인식/환각이 방출돼 원문 자리를 채움.

**빈도·영향 (오늘 12 run 전수)**: QG streak refresh 총 **25회** 발생(bong1 2–4회/run, ytn2 2–3, sbs1 1–2, kinno 0–3).
kinno는 발생 횟수와 WER이 강상관(R1: 0회→22.0% / R3: 3회→**72.0%**). 모든 refresh가 경계 인접은 아니므로
Stage 0에서 경계인접/비인접을 분류한다(§3-3) — **보호는 경계 인접만** 건다(스코프 격리, §2).

**기존 분석과의 관계**: Exp-154(E4)·Exp-173(E5)의 "QualityGate 부당드롭 ≈0~1%" 결론은 **텍스트 억제(suppress)만**
전수 분석한 것이고, streak refresh의 **오디오 폐기 경로는 그 스코프 밖**이었다 — 이번이 신규 규명이다.
Exp-172의 "③ 중간 유실 = QualityGate 억제 + held/UTF-8 + 세션초입 buffer" 귀속에 **"경계 QG streak refresh 버퍼 폐기"가 추가**되는 셈.

**Type A와의 구분 (이 루프의 스코프 밖)**: 반대 스크립트 변주형 필러 storm("Thank you very much …" 연쇄,
Exp-169 사각지대)은 별도 goal(앵커 총량 게이트 재설계)로 다룬다. 이 루프는 **같은 스크립트 환각 + 오디오 폐기 유실(Type B)**만 표적.

## 2. 설계 — 경계 보호 보존형 refresh (boundary-protected preserving refresh)

**핵심 아이디어**: QG streak refresh의 목적은 "환각 루프를 끊는 것"이지 "오디오를 버리는 것"이 아니다.
경계 복구 구간에서는 **디코더 상태(토큰·컨텍스트·attend)만 리셋하고 오디오는 보존**해, 뒤이어 도착하는
오디오와 함께 서두를 재디코딩할 기회를 남긴다. 재발 시 기존 폐기로 폴백해 환각 루프 안전망(Exp-028/154 계열)은 그대로 유지한다.

### P1 (핵심) — 보존형 refresh

- **발동 조건 (모두 충족)**:
  1. `_on_quality_suppressed`의 streak 문턱 도달(현행 3회) 시점이 **경계 보호창 이내**:
     `self.end(오디오 절대시각) - state.last_boundary_event_at <= BOUNDARY_PROTECT_SECS`(신설 상수, 초안 **5.0s** — Stage 0 실측으로 확정).
     `last_boundary_event_at`은 `new_speaker()` 및 `_apply_detected_language(is_switch=True)`에서 스탬프(신설 state 필드,
     [decoder_state.py](../../whisperlivekit/simul_whisper/decoder_state.py)).
  2. 이 경계에서 보존 재시도 미소진: `state.qg_preserve_used == False`(경계 이벤트 스탬프 시 리셋).
- **동작**: `refresh_segment(complete=True)` 대신 `refresh_segment(complete=False, keep_secs=self.segments_len())` —
  기존 함수 재사용(키 유지 루프 `:136-145`가 전량 보존), 신규 경로 최소. 토큰/컨텍스트/`last_attend_frame`은 기존과 동일하게 리셋.
  `qg_preserve_used=True` 마킹. `quality_suppress_streak=0` 리셋(현행 동일).
- **폴백**: 같은 경계에서 다시 streak 도달(=보존 재시도로도 garbage 반복) → **현행 그대로 폐기**(complete=True).
  무한 재디코딩 루프 원천 차단 — 이 폴백이 "이전 성능 저하 금지"의 구조적 보증이다(보호창 밖·재시도 소진 시 동작은 현행과 100% 동일).
- **비대상(스코프 격리)**: 보호창 밖 QG streak refresh(예: bong1 웃음 구간 한복판) — 현행 유지.
  QG 억제 자체(텍스트 드롭)도 전부 현행 유지 — **방출되는 텍스트가 늘어나는 변경이 아니다**(환각 방출 증가 위험 없음).

### P1b (보조, P1과 함께 구현) — 보존 재시도 시 언어 재프로브

보존 refresh 직후 `detect_current_language(window_secs=min(segments_len, 2.5), min_prob=0.85)`로 1회 재확인
(이미 `@torch.no_grad()` — [[turbo-nograd-perf-cliff]] 안전). 현재 언어와 다르면 `_apply_detected_language`로 교정.
이번 사례는 언어가 옳았지만(ko p=0.91), **2.0s 무조건 적용 폴백(`:256-258`)이 잘못된 언어를 커밋한 케이스**에서
garbage 원인이 "오디오 난이도"가 아니라 "언어 오픽"일 때를 커버한다. 같으면 no-op — 회귀 위험 없음.

### P2 (계측 후 판단 — Stage 0 결과로 구현 여부 결정) — eager-fail 방출 hold

`new_speaker` eager=None 이후 언어 확정까지의 창에서 구언어 토크나이저 방출을 hold. **단 이번 실측에선 이 창이
≈0.5s로 짧았고 그 안의 방출은 이미 QG가 억제했으며**, 잔존 junk("Let's-")는 diar 지연으로 **전환 이벤트 이전**에
방출된 것이라 hold 스코프 밖이다. Stage 0에서 "eager=None → 언어 적용까지의 창 길이·창 내 실제 방출량" 분포를
계측해 **유의미할 때만** 구현한다(과잉설계 방지 — 기본 스킵 권고).

### 공통 장치

- **롤백 플래그**: `BOUNDARY_QG_PRESERVE_ENABLED = True`(모듈 상수, False면 완전 무동작 — 짝지음 A/B·격리용).
- **전수 로깅** `[QGPreserve]`: 발동 시각·`last_boundary_event_at`·streak·판정(preserve|fallback_discard|out_of_window)·
  보존 오디오 길이·재프로브 결과(P1b). Exp-175식 오탐 감사용.
- **불변 보존 (건드리지 않는 것)**: ① QG 억제 판정(`_quality_gate`)·임계값 무변경. ② 보호창 밖/재시도 소진 폐기 폴백 유지.
  ③ `audio_max_len=15.0`이 버퍼 상한이므로 보존해도 무한 성장 없음. ④ Exp-171/174 철회 상태
  (`pending_retract_from/floor`)는 보존 refresh가 **건드리지 않는다** — `refresh_segment`가 이를 초기화하는지 구현 전
  확인하고, 초기화한다면 보존 경로에서 승계(유닛테스트로 고정). ⑤ 번역/확정(finalized) 계약 — 이 변경은 디코더 내부 계층이라
  이미 방출·확정된 토큰을 재변경하지 않는다.

**구현 위치·규모**: [align_att_base.py](../../whisperlivekit/simul_whisper/align_att_base.py) `_on_quality_suppressed` 분기 ~15줄 +
상수 2개, [decoder_state.py](../../whisperlivekit/simul_whisper/decoder_state.py) state 필드 2개(`last_boundary_event_at`,
`qg_preserve_used`), [backend.py](../../whisperlivekit/simul_whisper/backend.py) `new_speaker` 스탬프 ~3줄,
`_apply_detected_language` 스탬프 ~3줄, P1b ~10줄. 합계 ≈35–50줄.

## 3. 실행 계획 (자율 — 순서대로, 각 단계 판단 근거를 기록하며)

1. **사전 확인**: §0 워크트리 준비 + import 경로 + `vbcable=ok`.
2. **유닛테스트 먼저 (TDD)**: 신규 `tests/test_boundary_qg_preserve.py`. 최소 케이스 —
   보호창 내 첫 streak→보존(segments 불변·토큰/컨텍스트 리셋) / 같은 경계 2번째 streak→폐기 폴백 /
   보호창 밖 streak→현행 폐기 / 경계 이벤트마다 `qg_preserve_used` 리셋 / P1b 재프로브(동일 언어 no-op·상이 언어 교정) /
   철회 상태(`pending_retract_*`) 보존 경로 승계 / 플래그 OFF 시 완전 현행 동작.
   **전부 통과 후 다음 단계**. (`.venv\Scripts\python.exe -m pytest` 직접 호출 — uv 금지.)
3. **Stage 0 — 오프라인 계측 (코드 무변경, 오늘 로그 재분석 우선)**: §0의 12개 서버 로그에서 25건 streak refresh를
   전수 분류 — ⓐ 경계 인접(마지막 `[NewSpeaker]`/`[LangSwitch] switch=True`로부터 Δt) vs 비인접 분포 →
   `BOUNDARY_PROTECT_SECS` 초기값 확정(초안 5.0s), ⓑ 각 refresh 직후 전사 유실/환각 여부(정답 대조) →
   보호가 커버할 유실 건수 추정, ⓒ eager=None 창 길이·창 내 방출량 → P2 구현 여부 결정(기본 스킵).
   분석 스크립트는 `scripts/analyze_qg_refresh_boundary.py`(신규, 오프라인 전용)로 남긴다.
4. **Stage 1 — P1(+P1b) 구현 + 짝지음 A/B 스크리닝**: 플래그 ON/OFF 동일 세션 짝지음
   (`--repeat 1 --trace-tokens`, bong1+ytn2+sbs1, diar-ON/Sortformer/CRT=3.0/PLC=None/beams=2/turbo) + **kinno 1회**(정성).
   - **정성 필수**(전사 대조): ⓐ ytn2 "예수님…감사합니다" 유형 삼킴이 ON에서 복구되는지(해당 경계 3/3 관찰 —
     확률적이므로 발생 회차만 대조), ⓑ `[QGPreserve]` 발동 전수 정당성(보호창 밖 오발동 0), ⓒ **경계 부근 중복 방출
     증가 여부**(보존 재디코딩의 예상 부작용 — "왕성한 왕성한"류 악화 시 flag), ⓓ Case B 0건, ⓔ 화자분리 경계 무결성.
   - catastrophic(게이트 대폭 초과·환각 폭주·stall·화자 F1 붕괴)이면: 원인 분석 → 파라미터(PROTECT_SECS·재시도 수) 1~2회
     조정 재스크리닝 → 그래도 catastrophic이면 **기각 권고로 전환**(조정 총 3회 상한 — 무한 튜닝 금지).
5. **Stage 2 — 파라미터 스윕 (방향 신호)**: `BOUNDARY_PROTECT_SECS` {3.0, 5.0, 8.0} 스크리닝. 판단 지표 =
   "경계 유실 복구 최대 ∧ 중복 방출/환각 재생성 증가 최소". 재시도 수는 1 고정(2 이상은 Exp-163 재생성 전례상 보수적으로 배제,
   Stage 0 증거가 강할 때만 예외 검토).
6. **Stage 3 — 채택 확정 (`--repeat 3 --trace-tokens`, 짝지음 ON/OFF)**: 스크리닝 유망 시만. **fail-fast 금지** — 3회 전부,
   median+min/max/stdev. 하니스 버그(VBCable 무음/사망·포트 충돌)만 즉시 중단·수리 후 재실행([[vbcable-loopback-instability]]).
   **kinno도 N=3 포함**(WER/F1 게이팅엔 제외하되 worst-case 재현률·refresh 발생수 변화를 부기 — 이 goal의 표적 지표).
7. **held-out (ytn1+eng1, 단회)**: 채택 확정이 게이트 통과 시만. ytn1은 동종 코드스위칭 경계 다수라 특히 중요.
8. **정성 종합**: `.omc/transcripts/` 전사 정답 대조 — Type B 삼킴 복구 사례 목록(before/after 인용),
   신규 부작용(중복 방출·환각 재생성·lag) 사례 수집.
9. **기록**: `/log-experiment`로 Exp-177(또는 다음 번호). 커밋은 워크트리 브랜치에만.
10. **최종 보고서 작성 후 정지**(§5 형식). **머지하지 않는다.**

## 4. 채택 게이트 (hard — 최종 권고 판정 기준, regime v2 + 사용자 명시 비회귀 제약)

우선순위 순서. **판정 도구 = 짝지음 A/B 순효과**(동일 세션 ON/OFF; 절대 수치는 §0 표를 참고만):

1. **화자분리 F1 worst-case 미회귀** (ON이 OFF보다 나쁘면 안 됨 — 3파일 전부).
2. **WER max 미회귀** — 특히 bong1(필러/웃음 기존모드 초과 시 Exp-174 전례처럼 로그 인과 대조로 무관 입증 필요, 못 하면 유보).
3. **Case B(단어 중간 분절) 0건** — 수치 무관 hard-fail.
4. **표적 지표 개선**: ⓐ 경계 인접 QG streak refresh에 의한 삼킴/유실 사례가 ON에서 감소(전사 대조),
   ⓑ kinno worst-case(오늘 72.0%) 재현 시 심도 완화 또는 refresh 발생수 감소. — 이게 없으면 "무해하지만 무익" = 기각 권고.
5. **신규 부작용 감시**: 경계 부근 중복 방출·환각 재생성(Exp-163 전례)·실시간 lag(보존 재디코딩 비용) 증가가
   정성/로그상 유의미하면 파라미터 보수화 후 재판정, 해소 불가면 기각 권고.
6. **WER median 개선(또는 중립)** — 발생이 확률적·국소적이므로 median 중립 + worst-case/정성 개선이어도 채택 권고 가능.
7. **held-out(ytn1+eng1) 미회귀**.

이 수정은 §3.1 폐쇄망·§3.2 두 언어 고정 불변 제약에 **간접 연관**(코드스위칭 경계 유실 감소)이나 직결 기반 기능은 아니므로
일반 채택 규율 적용 — 정량이 애매하면 자율 기각/채택 대신 **"판단 유보 + 증거 정리 + 사용자 질의"**로 보고서에 남긴다.

## 5. 최종 보고서 형식 (루프 종료 시 사용자에게 제시)

1. **한 줄 결론**: 채택 권고 / 기각 권고 / 판단 유보.
2. 정량 표(짝지음 A/B 스크리닝·N=3·held-out — 화자F1·WER median/max 분리) + 게이트 7항 판정 표.
3. **정성 핵심**: Type B 삼킴 복구 사례 before/after 전사 인용(ytn2 "예수님" 유형 필수), `[QGPreserve]` 발동 전수 감사 결과,
   부작용(중복/재생성/lag) 관측.
4. Stage 0 분류표(경계인접 vs 비인접, 유실 동반률) + 자율 결정 이력(PROTECT_SECS 선택·P2 스킵/구현 근거).
5. 미해결·후속: Type A(변주형 storm 앵커 총량 게이트) goal 착수 여부 · 비경계 QG refresh 유실(보호창 밖) 잔존 규모 ·
   kinno류 침묵-heavy 음원 테스트셋 편입 제안.
6. **사용자 질문은 단 하나**: "master에 머지(채택)할까요?" — 예/아니오로 답할 수 있게.

## 6. 회귀 교훈 (반드시 준수)

- **폐기 폴백 제거 금지**: 보존은 경계 보호창 내 1회뿐 — streak refresh의 환각 루프 차단 기능(Exp-028/154 계열)은 안전망으로 유지.
- **QG 억제 판정·임계값 무변경**: 이 goal은 "무엇을 방출하나"가 아니라 "오디오를 버리나"만 바꾼다. 방출량을 늘리는
  방향(임계 완화)은 환각 방출 증가라 스코프 밖.
- **출력 후처리의 한계(Exp-163)**: 디코더가 필러를 재생성하면 출력 필터로 못 막는다 — 이 goal이 오디오 계층(보존)에서
  개입하는 이유. 반대로 보존 재디코딩이 **재생성을 늘릴 수 있음**도 같은 교훈 — 게이트 5항으로 감시.
- **철회 상태 상호작용(Exp-171/174)**: `refresh_segment`가 `pending_retract_*`/`pending_language_switch`를 초기화하는지
  구현 전 확인, 보존 경로에서 승계·유닛테스트 고정.
- **no_grad(Exp-158, [[turbo-nograd-perf-cliff]])**: P1b 재프로브는 `detect_current_language` 재사용(이미 no_grad) — 신규 forward 경로 금지.
- **데이터 특화 하드코딩 금지(§3.8)**: 문구·언어 하드코딩 없음 — 시각·streak·경계 이벤트 신호만.
- **공유 .venv 가드레일**: `uv run`/`uv sync`/`uv pip` **절대 금지**([[shared-venv-uv-run-concurrency-hazard]]). lint·pytest는
  `.venv\Scripts\python.exe -m ruff` / `-m pytest` **직접** 호출.
- **측정 정본**: 경로 C만, provenance 육안 확인(`branch=…@… vbcable=ok`), 스크리닝=`--repeat 1`(방향 신호)·
  채택확정=`--repeat 3`(fail-fast 금지), 짝지음 A/B로 변동성 상쇄(Exp-175/176 방법).

## 7. 기록·연동 문서 (채택 시 사용자 승인 후 동일 작업 단위 — 보고서에 체크리스트로만 포함)

- `EXPERIMENTS_LOG.md` 전체 서술 + `EXPERIMENTS.md` 빠른참조 1행(`/log-experiment`).
- [docs/SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md): 직접 대상 아님(문장 확정 로직 무변경)이나,
  경계 복구 서술에 영향 있으면 §7 규약대로 갱신.
- **epoch 판단**: 디코더 실패 모드(경계 유실)를 바꾸는 구조 변경이므로 **bump 후보** — STATE "세대 경계 규칙"으로 머지 시 최종 판단.
- master 머지 후 `/update-master-changes`.
- Exp-172의 유실 경로 귀속(이월 핵심사실)에 "경계 QG streak refresh 버퍼 폐기" 추가 반영.
