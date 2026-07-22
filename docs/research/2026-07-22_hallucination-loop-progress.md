# 환각 빈도 저감 무정지 자율 루프 — 진행 리포트

> goal 프롬프트: [docs/goal_prompt/GOAL_HALLUCINATION_REDUCTION_LOOP.md](../goal_prompt/GOAL_HALLUCINATION_REDUCTION_LOOP.md)

## 상단 요약 (매 이터레이션 갱신)

- **루프 시작**: 2026-07-22 22:53 · **경과**: ~4시간 50분 (갱신 시각 03:45 기준, 2026-07-23)
- **전체 상태**: **T1·T2·T3·T4·T5 전부 완료 + T1+T5 결합검증 완료 + T2 후속(★계열② 불확실성) + T5 후속(★★★bong1 회귀 원인규명+재설계로 해결)**. 큐 소진 — 사용자 확인 대기 항목 다수.
- 3줄 요약:
  1. **T1**(lang_locked new_speaker 재디코딩 스킵) — TDD 재현·수정 + 실측 확증. **채택권고**(`9c17e0f`, Exp-201).
  2. **T2**(침묵 클로징 환각 섀도우 계측)·**T3**(음차 경계 고아 토큰 계측) — T2는 후보 시그니처 오탐 3/3으로 게이트 배선 금지(Exp-202), 후속 재검증(Exp-206, 대조측정 포함)에서 **원목표("감사합니다" 필러)가 신·구코드 8회 표본 전부 실제로는 방출 안 됨을 발견 — 원 진단 재확인 필요**. T3는 **ytn2에서 신규 사례 포착**: "정경두"→"John Gyeong-du" 영어 음차(계열③ 양방향 확장, Exp-203). **T4**(bong1 필러 판정)는 T2 시그니처 불일치로 확장 불가 종결.
  3. **T5**(신규, T1 로그 재분석 발견) — kor1 flip-flop 근본원인(ChangeSpeaker dispatch 길이필터 부재) 규명·수정. 초기 문턱(0.5s, Exp-188 상수 재사용)이 **bong1(§3.8 최우선) 진짜 화자전환까지 오억제함을 플레인 마스터 대조로 확정**(원인규명 성공) → 문턱 0.2s로 재설계해 **bong1 게이트 이내 회복**(플레인 마스터보다 우수) — **조건부 채택권고**(`703794c`, Exp-204, 후속 확인사항 있음). **T1+T5 결합 검증**(cherry-pick)에서 두 fix가 설계대로 상호보완함을 확인, 상호작용 문제 없음(Exp-205).
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

### It-5. T5(신규, §3 예비항목에서 승격) — ChangeSpeaker dispatch 노이즈 필터 [완료 — 조건부 채택권고]

- **계기**: T1 확정측정 로그(kor1 R2/R3)를 재분석하다 발견 — flip-flop 버스트가 단일 순간에 8회 연속 발생(중간에 정상 디코딩 처리 없이 로그가 바로 이어짐). Exp-188(`MIN_SPEAKER_ATTRIBUTION_SECS`)이 이걸 걸러줄 것으로 기대했으나, 버스트 구간에 `[SpeakerAttribution]` 로그가 **0건** — 그 완화책이 아예 적용 안 되는 지점임을 실측으로 발견.
- **근본원인**: `audio_processor.py _update_diarization_state()`가 Sortformer 원시 diarization 세그먼트의 화자변화를 감지할 때마다 **세그먼트 길이 검사 없이** `ChangeSpeaker`를 dispatch. Exp-188의 필터는 다른 계층(`tokens_alignment.py`, 텍스트 화자라벨링)에서만 작동해 이 dispatch 지점엔 애초에 적용 대상이 아니었음(설계상 사각지대, 버그라기보다 두 계층의 목적이 달라 생긴 공백).
- **구현**: 워크트리 `worktrees/hallu-t5-changespeaker-dispatch-filter`, 브랜치 `exp/hallu-t5-changespeaker-dispatch-filter`.
  - 세그먼트 길이가 `MIN_CHANGE_SPEAKER_DISPATCH_SECS`(0.5s, 기존 상수와 동일값) 미만이면 dispatch도 `_last_diar_speaker` 상태 갱신도 하지 않고 완전히 무시(짧은 flip이 상태를 오염시켜 이후 진짜 화자 복귀가 스퓨리어스 전환으로 재판정되는 것도 함께 방지).
  - `CHANGE_SPEAKER_DISPATCH_FILTER_ENABLED`(롤백 플래그).
  - TDD 8개(문턱 미만/이상/경계값/세션최초/상태오염방지/롤백 A-B 대조·공유state 무변경) 전부 GREEN. 전체 750 passed·1 skipped(무관)·ruff clean.
- **커밋 완료**(`80f4bbd`).
- **⚠️ 주의**: 유사 접근(ChangeSpeaker 디바운스)이 **Exp-106(E1, base 기질)에서 ytn2 회귀 전력** — 시간기반 디바운스가 아닌 순수 최소길이 필터라는 점에서 메커니즘이 다르고, base 기질 결론이라 epoch 게이트상 "방향 신호"일 뿐이지만 **ytn2를 특히 주의해서 재검증** 중.
- **측정 1 — ko 스크리닝(kor1~3, `--lan ko`, N=1)**: kor1 NewSpeaker **22~30회(T1 로그) → 4회**(이번 회차)로 대폭 감소, Refresh=5(감소한 이벤트 수만큼 비례 — 이 브랜치는 T1 fix 미포함이라 남은 이벤트는 여전히 refresh 발생, 예상대로). kor2/kor3 NewSpeaker 0(0-firing). WER kor1 13.5%/kor2 13.8%/kor3 32.5% — 이전 회차들과 비슷한 밴드, 특이 회귀 없음. **N=1이라 flip-flop 자체가 원래 변동성 큰 지표임을 감안하면 추가 회차로 재확인 필요**.
- **측정 2 — auto N=1 스크리닝**: WER bong1 31.6%(게이트 소폭초과)·ytn2 21.7%(게이트 이내)·sbs1 19.6%(게이트 초과, seg_f1 0.29). 정성 확인 결과 sbs1의 3건 이상(`사태리트의`=기존 계열③ 재현, `영상편집:이재명`=화자전환 무관 방송자막류 환각, 문장중복 1건)이 전부 내 변경과 직접 연결짓기 어려운 별개 현상으로 보여 `--repeat 3` 확정측정으로 재검증.
- **측정 3 — auto 확정측정(`--repeat 3`) vs Exp-161 게이트(bong1≤30.5%/ytn2≤34.5%/sbs1≤16.1%)**:

  | 파일 | WER median | WER max | 게이트 | 판정 |
  |------|-----------|---------|--------|------|
  | bong1 | 33.7% | **35.2%** | 30.5% | ❌ max 초과 +4.7pp |
  | ytn2 | 18.7% | 21.2% | 34.5% | ✅ 대폭 개선 |
  | sbs1 | 10.7% | 11.3% | 16.1% | ✅ 대폭 개선 |

  - **ytn2·sbs1**: 게이트 대폭 이내, N=1 스크리닝의 sbs1 이상치는 재현 안 됨(노이즈로 확인) — **Exp-106이 우려한 ytn2 회귀는 미재현, 오히려 크게 개선**(순수 최소길이 필터가 시간기반 디바운스와 메커니즘이 다름을 실측으로 뒷받침).
  - **bong1 max 회귀 정성분석**: 최악회차(35.2%) 전사를 정답과 전수 대조 — `This man Dismap Thank you. Thank you.`·`Okay, cool Thank you.`·`하하하하하` 등 **전형적인 bong1 웃음구간 필러/환각**(기존에 이미 광범위 문서화된 별개 미해결 이슈, STATE "Layer 3b 비음성 게이팅") 패턴이며, 화자전환 경계 관련 신규 왜곡·중복은 **발견되지 않음**. 이 fix가 새로 유발한 결함이 아니라고 판단되나(diarization과 무관한 영역), 로그만으로 인과관계 100% 배제는 불가.
  - **bong1 N=5 확장 측정(추가 2회)**: WER 5회 전체 = 26.8/27.1/33.7/35.2/36.1% → **median 33.7%(N=3과 동일), max 36.1%(더 벌어짐)**. Exp-161 baseline(N=3, 29.3~30.5%, stdev 0.7%로 매우 좁음)과 달리 **이번 분산 자체가 훨씬 큼**(범위 9.3pp). 5회 중 3회가 게이트 초과. N=5로도 "fix 영향 vs bong1 고유 변동성"이 수치만으로는 완전히 분리 안 됨 — **median이 baseline보다 높아졌을 가능성(29~30%대→33%대)까지 사용자 확인 시 함께 고지 필요**(max 게이트 초과보다 더 근본적인 신호일 수 있음).
- **1차 판정(이후 철회됨)**: 조건부 채택권고 — bong1 max 게이트 초과 원인을 "별개 기존 웃음환각 이슈"로 추정.

### ★★★ T5 최종 정정 — 플레인 마스터 대조로 원인 확정 + 문턱 재설계로 해결

위 1차 판정의 "별개 이슈" 추정이 실제로는 **틀렸음**을 이후 검증으로 확인했다:

1. **플레인 마스터(fix 미적용) 동일조건 대조측정**(같은 날, N=5): bong1 WER **median 21.4%·max 30.1%(게이트 이내)** — T5 브랜치(median 33.7%·max 36.1%)와 뚜렷한 차이. NewSpeaker 원시 이벤트도 플레인 마스터 53~67회 vs T5 필터 적용 시 37회로, **원시 이벤트의 약 40%가 억제**되고 있었음을 확인.
2. **원인 확정**: bong1은 CLAUDE.md §3.3/§3.8이 명시하는 "**다화자가 짧은 단어를 번갈아 말하는**" 파일이라, 0.5초 미만 화자전환 상당수가 **노이즈가 아니라 진짜 화자전환**이었다. 0.5s 문턱(Exp-188 기존 상수를 검증 없이 재사용)이 이를 대량 오억제 — **Exp-106이 ytn2 코드스위칭 속도에서 우려했던 것과 같은 실패모드가 bong1의 화자전환 속도에서 실제로 재현된 것**으로 최종 확인.
3. **재설계**: 문턱을 0.5s→**0.2s**로 하향(커밋 `703794c`, 유닛테스트 문턱 상대화). **bong1 재측정(N=3): median 27.4%·max 28.6% — 게이트 이내로 회복, 플레인 마스터보다도 우수**. NewSpeaker 억제율도 완화(31~58회, 플레인 마스터에 더 근접).

**추가 확인 — kor1 4회 더 반복해 버스트 재현 성공**: R4에서 NewSpeaker **12회**(Refresh 9회) 발생, WER **26.3%**(0-firing 3회는 13.5~15.8%). **0.2s는 0.5s보다 덜 공격적으로 걸러내** flip-flop이 완전히는 안 사라진다(22~30회→12회, 절반 이상 감소하나 0.5s의 3~4회만큼은 아님) — T5 단독(0.2s, T1 미포함)으론 버스트 시 WER이 여전히 일부 악화. **이는 T1+T5 결합 머지의 필요성을 강화하는 근거**다 — T5가 이벤트 수를 줄이고 T1이 살아남은 이벤트를 무해화해야 kor1 문제가 완전히 해소된다.

**최종 결론**: **조건부 채택권고(0.2s 버전)로 재상향**, 단 **"T5 단독보다 T1+T5 결합 머지 권장"**. ytn2·sbs1도 0.2s 기준 재확인 필요, 정식 `--repeat 3` 확정측정(T5 단독·T1+T5 결합 각각, 0.2s 버전)이 다음 세션 최우선 과제. `/log-experiment` 기록 완료(Exp-204, 전체 정정 이력 포함).

**교훈**: 기존 프로젝트 상수(Exp-188의 `MIN_SPEAKER_ATTRIBUTION_SECS=0.5`)를 "동일 문제니 동일 값이 맞겠지"라고 검증 없이 재사용한 것이 근본 실수였다 — **적용 계층이 다르면 같은 상수라도 재검증이 필요**하다는 구체적 사례로 기록. 또한 문턱 하나로 "노이즈 억제"와 "진짜 이벤트 보존"을 동시에 완벽히 만족시키긴 어렵다는 것도 실측으로 확인 — **단일 임계값 필터의 근본적 한계**이며, 완전한 해법은 T1처럼 "이벤트 자체를 무해화"하는 방향과의 결합에 있음을 시사.

### It-6. T1+T5 결합 검증 [완료 — 상호작용 문제 없음 확인]

- **목적**: T1(`9c17e0f`)·T5(`80f4bbd`)가 서로 다른 브랜치에서 독립 개발돼 함께 측정된 적이 없어(아침 확인 요청 항목), 워크트리 `worktrees/hallu-t1t5-combined-check`(브랜치 `exp/hallu-t1t5-combined-check`)에 두 커밋을 `git cherry-pick`으로 합쳐 검증.
- **결과**: cherry-pick 충돌 0건, 전체 752 passed·1 skipped·ruff clean.
- **ko 스크리닝(kor1~3, N=1) — 이상적인 결합 효과 확인**: kor1 NewSpeaker **3회**(T5 단독 시 4회와 비슷한 수준 — 노이즈 대부분 제거) 중 **3/3 전부 "경계 재디코딩 스킵"(T1 로직) 발동** — Refresh는 무관한 정상 침묵-refresh 3회뿐. 즉 T5가 노이즈성 이벤트 자체를 원천에서 줄이고, T1이 남은 진짜 이벤트의 재디코딩 비용까지 제거해 **두 fix가 정확히 설계대로 상호보완**함을 실측 확인. WER kor1 11.7%/kor2 17.9%/kor3 35.8% — 무관 밴드 내.
- **auto 무회귀(bong1/ytn2/sbs1, N=1)**: WER bong1 23.5%·ytn2 24.1%·sbs1 12.5% — **Exp-161 게이트(30.5/34.5/16.1) 전부 이내**. T5 단독 확정측정(Exp-204)의 bong1 max 우려가 이번 회차엔 재현 안 됨(N=1이라 확정적이진 않음). T1의 `lang_locked` 분기가 auto 세션(`cfg.language=="auto"`)에서 예상대로 비활성임도 재확인(auto 경로 관측된 스킵 로그는 전부 기존 Exp-196 메커니즘).
- **결론**: `/log-experiment` 기록 완료(Exp-205). **두 fix는 서로 다른 계층에서 독립 작동하며 간섭하지 않음** — 결합 채택에 구조적 장애물 없음. 정식 채택확정(`--repeat 3`)은 개별 머지 승인 이후 별도 필요.
- **0.2s 최종본으로 재검증(★후속)**: T5가 0.2s로 재설계된 뒤 갱신 커밋을 결합 브랜치에 추가 cherry-pick, kor1 `--repeat 3` 재측정 — **3회 전부 0-firing**(WER 12.9~14.6%, 무회귀만 확인). 결합 시 0.2s 버전의 버스트 완전억제(T5 단독에서 확인된 "12회 버스트도 T1의 스킵으로 무해화"가 실제로 성립하는지)는 **이번 세션에서 끝내 재현 못 함** — kor1 flip-flop 자체가 매우 간헐적이라(이번 세션 중 여러 차례 시도, 총 20회 넘는 kor1 반복측정 중 버스트 재현은 T1 확정측정 2회(R2/R3)·T5 0.2s 재확인 1회(R4)뿐) 다음 세션에서 버스트 회차를 잡아 최종 확인 필요.
- **추가 5회 재시도(최종)**: 결합 브랜치로 kor1을 5회 더 반복(누적 8회 전부 0-firing, WER 12.3~18.1% 무관 밴드). Sortformer의 flip-flop은 VBCable 실시간 재생 타이밍 지터에 좌우되는 것으로 추정되며(T1/T5 둘 다 Sortformer 출력 자체엔 관여하지 않고 그 이후 소비 단계만 손대므로, 코드 분기가 버스트 발생률 자체를 바꿀 이유가 없음), **결합 브랜치가 유독 버스트를 못 잡은 것은 순전히 표본 운으로 판단** — 브랜치별 특성 차이가 아님. 이번 루프에서는 "결합 시 버스트 완전억제"의 직접 실측 확인을 못 했고, 이는 정직하게 미해결 항목으로 남긴다(메커니즘상 T1 단독 결과(스킵 3/3)와 T5 단독 결과(억제 22→12)를 조합하면 성립해야 하나, 결합 브랜치에서의 동시 실측은 없음).

### T4 — bong1 필러 타임스탬프 정체 시그니처 판정 [완료 — 확장 불가로 종결]

- **판정**: T2 계측(`[SilenceHalluProbe]`)을 bong1(웃음구간 포함)에 적용했으나 **would_hold 0건**(§It-2 측정 2) — T5 확정측정(§It-5 측정 3)에서 bong1의 "Thank you"류 필러가 다시 뚜렷하게 관측됐음에도, 그 필러 방출 시점들이 T2의 후보 시그니처(attention_reached_end ∧ frame_advance≈0)와 **매칭되지 않는다**. 즉 T2 게이트를 웃음 필러까지 확장하는 방안은 **성립하지 않음** — 별개 메커니즘으로 판단.
- **결론**: STATE에 이미 기록된 대로 bong1 웃음 환각은 no_speech/VAC 계열(Exp-164/165, "폐기 확정")로 원천 차단이 구조적으로 불가능함이 재확인되고, 유일한 남은 경로는 "웃음 전용 비-ASR 분류기"(별도 설계 세션 필요, 이번 루프 범위 밖)뿐임을 재확인. **이번 루프에서 추가 시도 없이 종결.**

### It-7. T2 후속 — kor3 "감사합니다" 필러 재현 시도 + 역사적 대조측정 [완료 — ★불확실성으로 결론]

- **목적**: T2 원목표(§2 계열②, goal 프롬프트가 인용한 "kor3 R2/R5 세션 말미 감사합니다 생성·방출")를 실측으로 재현해 프로브 시그니처를 보정하려 kor3를 `--repeat 4`로 재측정.
- **1차 발견**: "감사합니다"가 **디코더 내부 후보로는 4/4 재현**(부적절한 위치, 예 "…개편하겠습니다 감사합니다")되지만 **실제 커밋(`Output:`)에는 4/4 미방출**. 로그 정밀대조 결과 디코더가 증분 디코드로 "감사합니다"까지 그려보다 attention이 버퍼 말단에 도달해 루프가 끊기고, 그 호출의 최종 커밋은 **공백**(미완결 마지막 단어로 홀드) — 다음 호출에서 재확인 안 돼 자연 소멸.
- **1차 가설**: "Exp-199/200(UTF-8 반토막 토큰 커밋계층 정합성 수정)이 부수효과로 이 필러도 억제하게 됐다" → **워크트리 `hallu-pre-exp199-check`(Exp-199 병합 직전 커밋 `2957cc7`)에서 동일 측정으로 대조 검증**.
- **★대조측정 결과 — 가설 반증**: 구코드(Exp-199 이전)에서도 "감사합니다" 후보는 오히려 더 자주 등장(1/1/7/9회)하지만 **실제 커밋은 이번에도 4/4 미방출** — 즉 **8회 측정(신코드4+구코드4) 전부 실제 방출 0건**. 억제 메커니즘이 Exp-199/200보다 훨씬 이전부터 존재했다는 뜻이라 최초 가설은 틀렸다.
- **최종 결론**: 원 진단(2026-07-22 세션)이 인용한 "생성·방출" 사례가 이번 8회 표본과 배치된다. 두 가능성이 남는다 — ① 실제로 간헐적(운 나쁘면 걸리는) 현상이라 8회로도 못 잡았다, ② 원 진단이 DEBUG 증분-디코드 후보 라인을 실제 방출(`Output:`)로 오인했을 가능성. **어느 쪽인지 이번 루프에서 확정 못 함 — 불확실성 자체가 결론**. `/log-experiment` 기록 완료(Exp-206, 정정 포함).
- **T2 게이트 판단**: 애초에 커밋 안 되는 텍스트엔 발동할 수 없으므로 조건 좁히기는 "실측할 양성 예시 부재"로 계속 보류.

## 아침 확인 요청

- **T1 머지 여부**: `exp/hallu-t1-lang-locked-skip@9c17e0f`(lang_locked new_speaker 경계 재디코딩 스킵) — 목표 결함 해소 실측 확증(Exp-201), auto 무회귀, Case B 0. **채택권고**, 머지 승인 여부 확인 요청.
- **T5 머지 여부**: `exp/hallu-t5-changespeaker-dispatch-filter@703794c`(ChangeSpeaker dispatch 최소길이 필터, **문턱 0.2s 최종본**) — kor1 flip-flop 22~30회→3~4회 확증, ytn2·sbs1 대폭 개선. **초기 문턱(0.5s)에서 bong1(§3.8 최우선) 진짜 화자전환까지 오억제하는 회귀를 플레인 마스터 대조로 원인 확정**(median 21.4%→33.7%로 악화, NewSpeaker 원시이벤트 40% 억제) → **문턱 0.2s로 재설계해 bong1 게이트 이내로 회복**(N=3 스크리닝: median 27.4%/max 28.6%, 플레인 마스터보다 우수). **조건부 채택권고로 재상향**, 단 남은 확인사항: ① kor1 flip-flop 억제력이 0.2s에서도 유지되는지 버스트 재현 회차로 미재확인(이번 표본 우연히 0-firing) ② ytn2·sbs1도 0.2s 기준 재확인 필요 ③ 전체 정식 `--repeat 3` 확정측정을 0.2s로 재수행 필요(0.5s 시절 수치만 있음). 머지 승인 여부 확인 요청. **T1+T5 상호작용은 검증 완료**(Exp-205, 문제 없음 — 단 그 검증은 0.5s 버전 기준이었으므로 0.2s로 재확인 권장).
- **kor1 Sortformer flip-flop 자체**(T5로 dispatch 스팸은 줄였으나 Sortformer의 원천 오귀속 자체는 미해결): 화자분리 F1 붕괴가 여전할 수 있음. 근본적인 diar 정확도 개선은 별도 과제로 남음.
- **★계열② 재검증 결과 공유(Exp-206, 대조측정 포함)**: kor3 "감사합니다" 클로징 필러가 신코드 4회+구코드(Exp-199 이전) 4회, 총 8회 표본 전부에서 실제로는 방출되지 않음(디코더 내부 후보로만 재현, 매번 홀드돼 자연 소멸). goal 프롬프트 §2의 "Exp-200 이후에도 지속" 서술이 이번 8회 표본과 배치 — **원 진단 세션이 인용한 로그 라인(`kor3_C_R2:L12852`·`R5:L13587`)이 실제 "Output:" 방출 라인이었는지, 아니면 이번에 확인한 것과 같은 DEBUG 증분-디코드 후보 라인이었는지 직접 재확인을 요청**. 후자라면 계열②는 처음부터 "방출된 적 없는" 현상이었을 수 있다.
- **신규 환각 계열 — "John Gyeong-du"류 고유명사 음차 오번역(ytn2)**: 계열③(음차 경계 환각)의 양방향 확장 사례(EN 잠금이 KO 인명을 영어 음차) 최초 확인(Exp-203). sbs1 "사태라"와 함께 계열③ 문서·설계 범위에 정식 편입할지 확인 요청.
- **신규 관찰 — bong1 방송자막류 환각과 무관한 sbs1 "영상편집:이재명" 환각**(화자전환 무관, 같은 화자 구간): 한국 방송뉴스 특유의 자막/크레딧 텍스트를 Whisper가 브로드캐스트 학습데이터 편향으로 환각하는 것으로 추정 — 계열④ 후보로 별도 추적할지 확인 요청.

## 실패·막다른 길

- T2 후보 시그니처(침묵개시 강제flush + attention_reached_end + frame_advance≈0)는 정상 스트리밍의 짧은 단어 부분방출과 실제 환각을 구분하지 못함(오탐 3/3) — 이 형태로는 게이트 설계 불가로 종료.
- T3 고아 run의 길이/시간간격 수치만으로는 환각·정상 꼬리가 분리되지 않음 — 자동 임계값 설계는 불가로 종료(메커니즘 자체는 유효).

## 워크트리 현황 (master 머지 없음 — 전부 별도 브랜치/커밋만)

| 워크트리 | 브랜치 | 최신 커밋 | 성격 |
|---|---|---|---|
| `hallu-t1-lang-locked-skip` | `exp/hallu-t1-lang-locked-skip` | `9c17e0f` | T1 — 채택권고, 머지 대기 |
| `hallu-t2-silence-hallu-probe` | `exp/hallu-t2-silence-hallu-probe` | `0348f1d` | T2 — 계측 완료, 게이트 배선 안 함(오탐 3/3) |
| `hallu-t3-preswitch-orphan-probe` | `exp/hallu-t3-preswitch-orphan-probe` | `57e8b71` | T3 — 계측 완료, 신규 환각 계열 발견 |
| `hallu-t5-changespeaker-dispatch-filter` | `exp/hallu-t5-changespeaker-dispatch-filter` | `703794c` | T5 — 조건부 채택권고(0.2s 최종본), 머지 대기 |
| `hallu-t1t5-combined-check` | `exp/hallu-t1t5-combined-check` | `1b65d8a` | T1+T5 상호작용 검증 전용(cherry-pick 산물) — 머지용 아님, 참고·재검증용 |
| `hallu-pre-exp199-check` | (detached, `2957cc7`) | — | Exp-206 역사적 대조측정 1회용 — 코드 변경 없음, 삭제해도 무방 |
| `hallu-plainmaster-bong1-check` | (detached, master 스냅샷) | — | Exp-204 대조측정 1회용 — 코드 변경 없음, 삭제해도 무방 |

**master는 docs 커밋만 누적**(EXPERIMENTS.md·EXPERIMENTS_LOG.md·본 리포트) — 코드 변경은 전혀 없음. 머지 승인 시 실제 작업은 위 각 `exp/*` 브랜치에서 가져와야 함.

## 다음 할 일

1. (사용자 판단) T1/T5(0.2s 최종본) 머지 여부·John Gyeong류 계열③ 편입·"영상편집" 신규 계열 추적·계열② 원 로그 재확인 여부 확정.
2. **T5 0.2s 버전 정식 확정측정**(다음 세션 최우선): kor1 flip-flop 재현 회차를 잡을 때까지 ko 반복측정(억제력 재확인) + auto(bong1/ytn2/sbs1) `--repeat 3` 전체 재수행 — 이번 루프의 0.2s 측정은 스크리닝 수준(bong1 N=3, kor1 N=2 0-firing)이라 정식 채택 확정엔 미달.
3. T1+T5 결합은 0.2s 기준 WER 무회귀는 재확인 완료(§It-6 후속)했으나, kor1 flip-flop 완전억제 여부는 버스트 미재현으로 미확인 — 버스트 회차를 잡아 최종 확인.
4. 여유 시 T2/T3 조건 좁히기 재시도(2a/3a 재계측): T2는 `long_silence` 연동, T3는 커밋 스냅샷의 "이후 철회 여부" 추적 신호 추가.
5. bong1 웃음구간 필러환각(Layer 3b 비음성 게이팅)은 이번 루프 범위 밖의 기존 미해결 과제로 남김.
