# 환각 빈도 저감 무정지 자율 루프 — 진행 리포트

> goal 프롬프트: [docs/goal_prompt/GOAL_HALLUCINATION_REDUCTION_LOOP.md](../goal_prompt/GOAL_HALLUCINATION_REDUCTION_LOOP.md)

## 상단 요약 (매 이터레이션 갱신)

- **루프 시작**: 2026-07-22 22:53 · **경과**: ~1시간 (갱신 시각 23:50 기준)
- **전체 상태**: **T1 완료·채택권고**(목표 결함 실측 확증). T2/T3 계측 코드 구현+테스트+커밋 완료, 실측은 이제 순번 확보(VBCable 단일 자원 — T1 확정측정 종료로 해제됨).
- 3줄 요약:
  1. T1(lang_locked new_speaker 재디코딩 스킵) — TDD 재현·수정 + **실측 확증 완료**: kor1 NewSpeaker 22~30회 발동 회차에서 Refresh가 3~4회로 0-firing과 동일 유지(수정 전이면 폭증), 중복 0건·Case B 0건, auto 무회귀. **브랜치 커밋(`9c17e0f`) → 채택권고, 머지는 사용자 확인 대기**(Exp-201 기록 완료).
  2. T2(침묵 클로징 환각 섀도우 계측)·T3(음차 경계 고아 토큰 계측) — 코드·유닛테스트·커밋 완료. 다음 이터레이션에서 VBCable로 실측 착수.
  3. 하니스 버그 1건 발견·즉시 수정(T1/T2/T3 워크트리 공통: `whisperlivekit/model/whisper-large-v3-turbo/` 디렉터리가 git으로 이미 체크아웃돼 있어 "이미 존재" 가드가 mklink를 건너뛰어 `model.safetensors`(gitignored) 누락 → returncode=3). 아래 §하니스 노트 참조.

## 이터레이션 로그

### It-1. T1 — lang_locked new_speaker 재디코딩 스킵 [완료·채택권고]

- **가설**: `backend.py new_speaker()`에서 `lang_locked` 세션은 eager 언어재감지를 안 돌려 eager/eager_cached가 항상 None → "동일 언어 확정" 스킵 조건이 절대 발동 못 함 → 모든 화자전환이 무조건 경계 재디코딩(refresh_segment)을 탐 → 중복 방출.
- **구현**: 워크트리 `worktrees/hallu-t1-lang-locked-skip`, 브랜치 `exp/hallu-t1-lang-locked-skip`. TDD:
  - RED 확인: `test_new_speaker_locked_skips_boundary_refresh` 추가 → `refresh_segment` 호출 1회 확인(버그 재현).
  - GREEN: `new_speaker()`에 `lang_locked` 조기 return(재감지 없이 곧장 스킵 경로) 추가. 화자 귀속만 갱신, `refresh_segment` 미호출. auto 경로는 무변경(대조군 `test_new_speaker_auto_still_calls_refresh_segment_when_lang_differs` 통과).
  - 전체 `pytest tests/` 744 passed, 1 skipped(무관) · `ruff` clean.
- **측정 1 — ko 스크리닝(kor1~3, `--lan ko`, N=1)**: WER 평균 19.0%(kor1 14.0%/kor2/kor3), seg_f1 0.667, sentence_f1 0.974. **NewSpeaker 이벤트 0회(전 3파일)** — Sortformer 화자전환 미재현 회차라 표적 지표(Refresh 카운트 감소) 검증 불가, **0-firing 노이즈 대조군**으로 판단(짝지음 원칙).
- **측정 2 — auto 무회귀(bong1/ytn2/sbs1, `--lan auto`, N=1)**: WER 30.1%/14.3%/13.7%. Exp-161 확정 게이트(bong1≤30.5%/ytn2≤34.5%/sbs1≤16.1%) **전부 이내** — 회귀 없음(fix가 `lang_locked` 분기만 건드려 auto 경로는 애초에 무관하므로 예상된 결과).
- **측정 3 — ko 확정측정(kor1~3, `--lan ko --repeat 3`)**: **NewSpeaker 발동 회차 포착 성공** — kor1 R1=0/R2=30/R3=22회. Refresh는 3/3/4회로 **발동 횟수와 무관하게 일정**(수정 전이면 30·22회로 폭증했을 자리). WER은 오히려 firing 회차(11.1~11.7%)가 0-firing(14.0%)보다 낮음. hyp_lines 전수 대조(3회차) 결과 **텍스트 중복·Case B 0건** — 화자전환 지점마다 문장이 더 잘게 나뉠 뿐 내용은 R1과 동일 순서로 이어짐. kor2/kor3은 3회차 전부 NewSpeaker 0(0-firing, 노이즈 대조군).
  - **부수 관찰**: kor1 firing 회차 화자분리 F1이 1.0→0.0으로 떨어짐 — 그러나 이는 **이 fix가 유발한 게 아니라 Sortformer가 단일화자 낭독을 flip-flop 오탐**하는 것(스킵 경로·재디코딩 경로 양쪽 다 `token.speaker` 갱신은 동일하게 수행). 별개 이슈로 분리 기록(§T5 예비 항목과 연결).
- **판정**: 목표 결함(중복방출) **실측 확증** + auto 무회귀 + Case B 0 → **브랜치 커밋 완료**(`9c17e0f`), **채택권고·머지는 사용자 확인 대기**. `/log-experiment` 기록 완료(EXPERIMENTS_LOG.md Exp-201, EXPERIMENTS.md STATE 빠른참조 1행).
- **하니스 버그 발견·수정**: `whisperlivekit/model/whisper-large-v3-turbo/`가 git 추적 대상(작은 config 파일들)이라 워크트리 생성 시 이미 존재 → `if (-not (Test-Path ...)) { mklink /J }` 가드가 스킵 → `model.safetensors`(807MB, gitignored)만 누락 → 서버 기동 즉시 FileNotFoundError(returncode=3, 3파일 전부). **원인 규명 후 `model.safetensors`만 개별 하드링크로 추가해 해결** — 코드 결함 아님(§CLAUDE.md 7-3 원칙대로 즉시 중단·수정). T2/T3 워크트리 셋업 시에도 동일 함정 회피(사전에 파일별 존재 확인 후 링크).
- **부가 관찰(cosmetic, 실측 무관)**: `_probe_provenance`의 메타데이터 프로브 서브프로세스(15s 타임아웃)가 동시 CPU 부하로 1회 타임아웃돼 provenance 표시줄이 "code=.venv beams=None"으로 잘못 보인 적 있음 — git_branch/sha는 별도 폴백 경로로 정확히 기록돼 실측 자체는 정상(JSON `provenance.git_branch`로 확인). 표시 줄 하나만의 아티팩트, 코드 결함 아님.

### It-2. T2 — 침묵 클로징 환각 섀도우 계측 (`[SilenceHalluProbe]`) [계측 구현 완료, 측정 대기]

- **배경**: `align_att_base.py infer()`의 `if not is_last and self._quality_gate(...)` — VAD 침묵 개시(`start_silence()`→`process_iter(is_last=True)`)로 진입하는 강제 flush는 **quality_gate를 항상 건너뛴다**. 이 지점에서 "attention reaches the end"이면서 직전 호출 대비 attended frame이 거의 전진 안 하거나(역행 포함) 텍스트가 커밋되면 "감사합니다"류 클로징 환각 후보.
- **구현**: 워크트리 `worktrees/hallu-t2-silence-hallu-probe`, 브랜치 `exp/hallu-t2-silence-hallu-probe`.
  - `prev_attend_frame`(호출 전 캡처) + `attention_reached_end`(기존 break 조건에 계측 플래그만 추가) → `_log_silence_hallu_probe()`가 `would_hold` 판정 + `[SilenceHalluProbe]`/`[SilenceHalluProbeStats]` 로깅.
  - `SILENCE_HALLU_PROBE_ENABLED`(짝지음 A/B 롤백 스위치) + `SILENCE_HALLU_FRAME_ADVANCE_MAX=3`(프레임, 0.06s).
  - 유닛테스트 11개(would_hold 조건별 참/거짓, 통계 누적, 예외 안전성, 롤백 스위치) 전부 GREEN. 전체 753 passed·ruff clean.
- **커밋 완료**(`0348f1d`). **측정 미실행** — VBCable 단일 자원이라 T1 확정측정 완료 후 순번.
- **다음**: kor1~3(`--lan ko`)+sbs1/bong1/ytn2(`--lan auto`, **bong1 필수** — 웃음 필러 T4 부수판정) 각 1회 이상 `--trace-tokens`로 계측 측정 → `[SilenceHalluProbe]` would_hold 전수 라벨링(환각 vs 정상 문장 꼬리) → 오탐 0 확인 전까지 게이트 배선 금지.

### It-3. T3 — 음차 경계 환각 고아 토큰 계측 (`[PreSwitchOrphan]`) [계측 구현 완료, 측정 대기]

- **배경**: sbs1 실측 — KO 문장 확정 → 0.55s 침묵 → **KO 잠금 상태로 영어 서두가 음차 방출**("사태라") → 그제서야 화자전환/언어전환 인지 → refresh → 언어전환. 마커 삽입 시점에 그 직전 커밋 run을 로깅.
- **구현**: 워크트리 `worktrees/hallu-t3-preswitch-orphan-probe`, 브랜치 `exp/hallu-t3-preswitch-orphan-probe`.
  - `_recent_commit_runs`(마커 아닌 실제 run 텍스트/시작/끝, 최근 5개) + `_last_long_silence_end`(진짜 문장 경계 = `end_silence()`의 long_silence 분기에서만 갱신) → `_log_preswitch_orphan(boundary_t)`가 마커 삽입 직전 최근 run을 `[PreSwitchOrphan]`으로 로깅(텍스트·길이·마커와의 시간 간격·post_silence_window 여부). **임계값으로 걸러 억제하지 않음** — 원시 수치만 남겨 3b 분석에서 기준을 정한다.
  - getattr 방어(기존 process_iter 단위테스트가 `__new__`로 이 신규 필드 없이 인스턴스를 만들어도 안 깨지게).
  - 유닛 5개 + 종단 1개(process_iter 2회 호출로 실제 커밋→마커 흐름) 전부 GREEN. 전체 748 passed·ruff clean.
- **커밋 완료**(`57e8b71`). **측정 미실행** — 순번 대기.
- **다음**: sbs1/ytn2/bong1(`--lan auto`, ytn1은 held-out 제외)로 측정 → 고아 run 분포에서 "환각만 잡고 정상 꼬리는 안 잡는" 철회 기준 도출 가능한지 판정.

## 아침 확인 요청

- **T1 머지 여부**: `exp/hallu-t1-lang-locked-skip@9c17e0f`(lang_locked new_speaker 경계 재디코딩 스킵) — 목표 결함 해소 실측 확증(Exp-201), auto 무회귀, Case B 0. **채택권고**, 이번 루프 규칙상 master 머지는 보류 — 머지 승인 여부 확인 요청.
- **kor1 Sortformer flip-flop 세그 F1 붕괴**(별개 이슈, T1이 유발한 게 아님): 단일화자 낭독(kor1)에서 화자전환 오탐이 반복 재현됨(R2 30회·R3 22회). §3 T5 예비 항목("kor1 flip-flop 버스트 상류 완화")으로 승격할지 확인 요청.

## 실패·막다른 길

- (없음 — T1은 목표대로 확증·채택권고까지 도달)

## 다음 할 일

1. T2 계측 측정 착수(kor1~3 ko + bong1/ytn2/sbs1 auto, `--trace-tokens`) → would_hold 전수 라벨링(§2c).
2. T3 계측 측정 착수(sbs1/ytn2/bong1 auto, `--trace-tokens`) → 고아 run 분포 분석(§3b).
3. 큐 소진 시 §3 T4/T5(예비 각도)로 이동.
