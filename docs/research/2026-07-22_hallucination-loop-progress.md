# 환각 빈도 저감 무정지 자율 루프 — 진행 리포트

> goal 프롬프트: [docs/goal_prompt/GOAL_HALLUCINATION_REDUCTION_LOOP.md](../goal_prompt/GOAL_HALLUCINATION_REDUCTION_LOOP.md)

## 상단 요약 (매 이터레이션 갱신)

- **루프 시작**: 2026-07-22 22:53 · **경과**: ~2시간 (갱신 시각 00:50 기준, 2026-07-23)
- **전체 상태**: **T1 완료·채택권고**. **T2 완료(계측전용) — 후보 시그니처 오탐 3/3, 게이트 배선 금지**. **T3 완료(계측전용) — 신규 환각 계열 발견**("John Gyeong-du" 고유명사 음차, 사태라의 반대방향 사례).
- 3줄 요약:
  1. T1(lang_locked new_speaker 재디코딩 스킵) — TDD 재현·수정 + 실측 확증 완료. **브랜치 커밋(`9c17e0f`) → 채택권고, 머지는 사용자 확인 대기**(Exp-201).
  2. T2(침묵 클로징 환각 섀도우 계측) — would_hold 3건 전수 라벨링 결과 **전부 오탐**(정상 단어의 버퍼경계 부분방출) — 게이트 배선 금지(Exp-202).
  3. T3(음차 경계 고아 토큰 계측) — 22건 라벨링. sbs1 "사태라" 자체는 이번 회차 미재현이나, **ytn2에서 반대방향 신규 사례 포착**: EN 잠금 세션이 한국 국방장관 이름 "정경두"를 듣고 "John Gyeong-du"로 영어 음차(§계열③의 양방향 확장, Exp-203). 자동 임계값은 미도출.
  4. 하니스 버그 2건 발견·즉시 수정(모델/데이터 하드링크 누락, T1/T3 각각 1회) — 아래 §하니스 노트.

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

### It-2. T2 — 침묵 클로징 환각 섀도우 계측 (`[SilenceHalluProbe]`) [ko 계측 완료 — 오탐 발견, 게이트 보류]

- **배경**: `align_att_base.py infer()`의 `if not is_last and self._quality_gate(...)` — VAD 침묵 개시(`start_silence()`→`process_iter(is_last=True)`)로 진입하는 강제 flush는 **quality_gate를 항상 건너뛴다**. 이 지점에서 "attention reaches the end"이면서 직전 호출 대비 attended frame이 거의 전진 안 하거나(역행 포함) 텍스트가 커밋되면 "감사합니다"류 클로징 환각 후보.
- **구현**: 워크트리 `worktrees/hallu-t2-silence-hallu-probe`, 브랜치 `exp/hallu-t2-silence-hallu-probe`.
  - `prev_attend_frame`(호출 전 캡처) + `attention_reached_end`(기존 break 조건에 계측 플래그만 추가) → `_log_silence_hallu_probe()`가 `would_hold` 판정 + `[SilenceHalluProbe]`/`[SilenceHalluProbeStats]` 로깅.
  - `SILENCE_HALLU_PROBE_ENABLED`(짝지음 A/B 롤백 스위치) + `SILENCE_HALLU_FRAME_ADVANCE_MAX=3`(프레임, 0.06s).
  - 유닛테스트 11개(would_hold 조건별 참/거짓, 통계 누적, 예외 안전성, 롤백 스위치) 전부 GREEN. 전체 753 passed·ruff clean.
- **커밋 완료**(`0348f1d`).
- **측정 1 — ko(kor1~3, `--lan ko`, N=1, `--trace-tokens`)**: is_last_calls kor1=26/kor2=35/kor3=40(대부분 VAD 미세 호흡pause마다 발동 — 문장 최종경계뿐 아니라). **would_hold=True 총 2건, 전부 kor3**(`위한`@t=3.10s, `위해`@t=15.20s).
  - **라벨링(2c)**: 전사·정답 대조 결과 **둘 다 오탐(정상 문장 일부)** — "위한"/"위해"는 한국어에서 극히 흔한 연결어(~을 위한, ~하기 위해)로 정답에도 동일 문맥으로 존재. 짧은 단어라 원래 attended frame 전진폭이 작을 뿐, 새 음성 없이 이어 생성된 클로징 환각이 아님(§목표 시그니처인 "감사합니다"류 필러와 무관).
  - **원인 추정**: `start_silence()`는 `Silence.is_starting`(VAD가 아주 짧은 호흡 pause만 감지해도 발동)에서 호출되어 **문장 최종 경계뿐 아니라 모든 미세 pause에서 매번** is_last=True 강제 flush가 일어난다 — 이 시점엔 아직 그 pause가 "긴 침묵"으로 판정되기 전이라, 짧은 정상 단어의 자연스러운 flush와 실제 환각을 프레임 전진폭만으로 구분 못 함.
  - **판정(§2c 규칙)**: 오탐 1건 이상 확인 → **게이트 배선 금지**. 조건을 좁히려면(다음 세션 후보): `is_starting` 시점 대신 `end_silence()`의 `long_silence`(실제 긴 침묵 확정) 시점과 연동하거나, 커밋된 run의 절대 길이가 아주 짧은 경우(1~2음절)는 애초에 후보에서 제외하는 정규화가 필요.
- **측정 2 — auto(bong1/ytn2/sbs1, `--lan auto`, N=1, `--trace-tokens`)**: bong1 would_hold 0건(웃음구간 포함, T4 부수판정 — 이번 회차 신호 없음, 재현성 낮을 가능성). sbs1 0건. **ytn2 would_hold 1건**(`control`@t=7.22s).
  - **라벨링**: **오탐**. TokenTrace 대조 결과 디코더가 "…transfer of operational control"까지 디코드하다 buffer 말단(`attention reaches the end: 361/362`)에 걸려 `control`만 우선 커밋하고 `control,`/`control and` continuation을 hold한 **정상 스트리밍 부분방출** — 새 텍스트를 지어낸 흔적 없음.
- **최종 집계**: would_hold 총 3건(kor3 2 + ytn2 1) — **전수 오탐(3/3, 100%)**. §2c 규칙에 따라 **게이트 배선 금지**로 최종 확정. `/log-experiment` 기록 완료(Exp-202).
- **결론**: 후보 시그니처(attention_reached_end ∧ frame_advance≈0 ∧ 텍스트커밋)는 `start_silence()`가 모든 미세 호흡 pause에서 발동한다는 구조적 특성상 특이도가 낮다 — 정상 스트리밍의 짧은 단어 부분방출과 실제 클로징 환각을 구분 못 함. 원 목표(kor3 "감사합니다"/sbs1 "다음은" 폭주 재현) 사례는 이번 N=1 측정에서 재현되지 않음(다음 세션 조건 좁히기 필요 시 재시도).

### It-3. T3 — 음차 경계 환각 고아 토큰 계측 (`[PreSwitchOrphan]`) [완료 — 신규 환각 계열 발견]

- **배경**: sbs1 실측 — KO 문장 확정 → 0.55s 침묵 → **KO 잠금 상태로 영어 서두가 음차 방출**("사태라") → 그제서야 화자전환/언어전환 인지 → refresh → 언어전환. 마커 삽입 시점에 그 직전 커밋 run을 로깅.
- **구현**: 워크트리 `worktrees/hallu-t3-preswitch-orphan-probe`, 브랜치 `exp/hallu-t3-preswitch-orphan-probe`.
  - `_recent_commit_runs`(마커 아닌 실제 run 텍스트/시작/끝, 최근 5개) + `_last_long_silence_end`(진짜 문장 경계 = `end_silence()`의 long_silence 분기에서만 갱신) → `_log_preswitch_orphan(boundary_t)`가 마커 삽입 직전 최근 run을 `[PreSwitchOrphan]`으로 로깅(텍스트·길이·마커와의 시간 간격·post_silence_window 여부). **임계값으로 걸러 억제하지 않음** — 원시 수치만 남겨 3b 분석에서 기준을 정한다.
  - getattr 방어(기존 process_iter 단위테스트가 `__new__`로 이 신규 필드 없이 인스턴스를 만들어도 안 깨지게).
  - 유닛 5개 + 종단 1개(process_iter 2회 호출로 실제 커밋→마커 흐름) 전부 GREEN. 전체 748 passed·ruff clean.
- **커밋 완료**(`57e8b71`).
- **하니스 오류·수정**: T3 워크트리 셋업 시 model.safetensors·sortformer.nemo·wav 하드링크 작업 자체를 빠뜨림(T1/T2엔 했으나 T3만 누락) → `sbs1/ytn2/bong1 auto` 측정 1차 시도가 `[오류] 파일 없음: test_data\bong1.wav`로 즉시 실패. 발견 후 누락 링크 전부 추가하고 재실행 — 코드 결함 아님(작업자 체크리스트 누락).
- **측정(sbs1/ytn2/bong1, `--lan auto`, N=1, `--trace-tokens`)**: 발동 sbs1=2·ytn2=9·bong1=11건, 총 22건 전수 라벨링.
  - **sbs1**: 목표 결함("사태라") **이번 회차 미재현**(KO→EN 전환이 깨끗함) — 2건 모두 정상 문장 꼬리(대조군).
  - **ytn2 — ★신규 발견**: `John Gyeong`@t=55.18(→최종 출력엔 `John Gyeong-`까지 남음)이 **국방장관 "정경두"의 영어 음차 오번역**임을 TokenTrace 디코드 시도 로그로 확정(`John` → `John G` → `John Gyeong` → `John Gyeongdu` → `John Gyeong-du` 등 여러 continuation을 시도한 흔적). **이것은 sbs1 "사태라"(EN 단어를 KO로 음차)의 정반대 방향(KO 고유명사를 EN으로 음차) 사례** — 계열③(음차 경계 환각)이 **양방향**이며 **일반 단어뿐 아니라 고유명사(인명)에도 적용됨**을 처음으로 확인. quality_gate가 억제 못 하고 최종 커밋됨(계열③ 기존 진단 "선행 조각은 억제되나 최종형은 문턱 통과"와 정합).
  - **ytn2 추가 관찰**: `You`@84.34(최종 출력은 `Let's.`)·`Minister Liu:`@104.10(최종 출력은 `Prime.`) — probe가 로깅한 커밋 스냅샷이 **이후 철회·대체**됐고, 대체된 최종형("Let's."/"Prime.") 자체도 정답에 없는 소규모 삽입 환각. **언어전환 경계가 여러 차례 불안정하게 재추정**되는 정황.
  - **bong1**: 11건 중 1건(`틀렘이까? 죄송합니다 형`)이 정답과 부분 대응하며 일부 왜곡 포함 — 혼재 사례(기존 bong1 웃음/중첩발화 환각과 정성 일치), 나머지 10건은 정상 대조군.
  - **구현 한계**: 일부 run의 `dur`/`gap_to_marker`가 음수로 나옴(토큰 타임스탬프가 경계 부근에서 항상 단조증가하지 않음, 철회·재정렬 영향 추정) — 계측값 자체의 비단조성, 디코딩엔 영향 없음.
- **최종 판정(§3b 규칙)**: 22건 표본에서 "환각만 잡고 정상 꼬리는 안 잡는" **단순 수치 임계값은 도출 안 됨**(길이 0.1~2s·gap -0.6~3s 구간에 진짜 환각과 정상 꼬리가 뒤섞여 분포) → **자동 게이트 미설계, 억지 문턱 안 만듦**. 그러나 **메커니즘 자체는 유효**함을 신규 사례로 재확증. `/log-experiment` 기록 완료(Exp-203).

## 아침 확인 요청

- **T1 머지 여부**: `exp/hallu-t1-lang-locked-skip@9c17e0f`(lang_locked new_speaker 경계 재디코딩 스킵) — 목표 결함 해소 실측 확증(Exp-201), auto 무회귀, Case B 0. **채택권고**, 이번 루프 규칙상 master 머지는 보류 — 머지 승인 여부 확인 요청.
- **kor1 Sortformer flip-flop 세그 F1 붕괴**(별개 이슈, T1이 유발한 게 아님): 단일화자 낭독(kor1)에서 화자전환 오탐이 반복 재현됨(R2 30회·R3 22회, 로그상 단일 시점에 8연속 flip 확인). §3 T5 예비 항목("kor1 flip-flop 버스트 상류 완화")으로 승격할지 확인 요청.
- **신규 환각 계열 — "John Gyeong-du"류 고유명사 음차 오번역(ytn2)**: 계열③(음차 경계 환각)의 양방향 확장 사례(EN 잠금이 KO 인명을 영어 음차) 최초 확인(Exp-203). sbs1 "사태라"와 함께 계열③ 문서·설계 범위에 정식 편입할지, 별도 하위계열로 분리 추적할지 확인 요청.

## 실패·막다른 길

- T2 후보 시그니처(침묵개시 강제flush + attention_reached_end + frame_advance≈0)는 정상 스트리밍의 짧은 단어 부분방출과 실제 환각을 구분하지 못함(오탐 3/3) — 이 형태로는 게이트 설계 불가로 종료. 조건 좁히기 방향은 기록해뒀으나 이번 루프에서 재시도는 안 함(시간 배분상 T3로 이동).
- T3 고아 run의 길이/시간간격 수치만으로는 환각·정상 꼬리가 분리되지 않음 — 자동 임계값 설계는 불가로 종료(메커니즘 자체는 유효, §3b 규칙대로 억지 문턱 안 만듦).

## 다음 할 일

1. (사용자 판단) T1 머지 여부·kor1 flip-flop 승격 여부·John Gyeong류 계열③ 편입 여부 확정.
2. 큐 진행: §3 T5 예비 각도로 이동 — kor1 Sortformer flip-flop 버스트 상류 원인(Exp-188 `MIN_SPEAKER_ATTRIBUTION_SECS` 재분석, T1 확정측정 로그 이미 확보) 우선 착수.
3. 여유 시 T2/T3 조건 좁히기 재시도(2a/3a 재계측) — T2는 `long_silence` 연동, T3는 커밋 스냅샷의 "이후 철회 여부" 추적 신호 추가.
