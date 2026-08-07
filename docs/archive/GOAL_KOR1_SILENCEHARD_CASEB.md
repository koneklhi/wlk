# Goal Prompt — `SILENCE_HARD_SECS` 안전망발 Case B(단어 중간 분절) 근본원인 확정 + 수정 + 검증

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: `docs/goal_prompt/GOAL_AUTO_KOREAN_FOLLOWUP.md`(3-Stage 루프, Exp-187/188/189, **완료·master 머지됨**)가
> 최종 보고서에서 명시적으로 후속 세션에 인계한 **유일한 미해결 hard-fail 항목** — kor1.wav "국방환경을" 지점의
> Case B — 를 단일 스코프로 마무리한다. CLAUDE.md §3.3 hard-fail 규정(Case B는 F1/WER 무관 즉시 조사 대상)과
> §3.8(범용 개선만, 데이터 특화 하드코딩 금지) 우선.

---

## 0. 출발 지점 (2026-07-19 14:39 기준, 반드시 먼저 읽을 것)

- **master = `03de591`**(Epoch 5, turbo). `git log --oneline -10 master`로 최신 상태 재확인할 것 — 병렬
  세션들이 활발히 머지 중이므로 이 커밋보다 앞서 있을 수 있다.
- **이미 완료·머지된 것 (재작업 금지)**: `GOAL_AUTO_KOREAN_FOLLOWUP.md`의 3-Stage 루프 전체.
  - Exp-187(`aec666e`) — 화자전환 `finalize_trigger` 라벨 손실 수정.
  - Exp-188(`8ea32ef`) — kor1 Case B 중 **diarization 순간 오귀속(diar-flip)이 유발하는 유형** 수정
    (`tokens_alignment.py`에 `MIN_SPEAKER_ATTRIBUTION_SECS=0.5s` 도입, N=8 재발 0건으로 검증 완료).
  - Exp-189(`2e4b58b`) — kor1 auto 모드 언어오검출(ko→en) 수정(`backend.py`
    `_EAGER_LANG_COOLDOWN_SECS=1.5s`), `--repeat 3` 채택 확정 완료.
  - 3개 브랜치 전부 `c2e6b86`(Exp-187+188 머지) → `80e3127`(Exp-189 머지) 경로로 master에 있다.
  - **이 diar-flip 계열 Case B(예: "소모 강요"→"강."+"요 등")를 다시 조사하지 않는다** — Exp-188이 메커니즘
    규명·TDD·N=8 재발 0건으로 이미 닫은 사안이다. 단, §4-2에서 확인하겠지만 **이번 세션에서 재현되는 개별
    사례가 실제로 이 계열인지 아래 §1의 잔존 계열인지는 매번 로그로 구분**해야 한다(겉보기 패턴이 비슷해도
    원인이 다를 수 있음 — 아래 참조).

- **후속 과제로 명시적으로 인계된 미해결 항목 (이 세션의 대상)**: Exp-189 "다음 가설/미해결" §1
  (`EXPERIMENTS_LOG.md` `grep -n "SILENCE_HARD_SECS 유발 Case B"`로 원문 확인):
  > "`SILENCE_HARD_SECS` 유발 Case B(kor1 '국방환경을' 지점)" — Exp-188의 diar-flip 유발 Case B와는 다른
  > 원인(순수 침묵-길이 안전망이 진짜 긴 낭독 pause에 반응)으로, 이번 Stage 범위 밖. 후속 세션에서
  > `SILENCE_HARD_SECS` 값 재검토 또는 grammar-conditional 판정 강화 필요.

- **오늘(2026-07-19) 재확인 측정**: master `80e3127`(Exp-187/188/189 전부 반영된 시점) 위에서 경로 C·
  `--lan auto --repeat 1`(스크리닝, 전체 9파일 1회씩)를 돌렸을 때도 kor1.wav에서 Case B가 **2건** 관찰됐다.
  - `"...2040년 국방환."` ⏎ `"경을 고려한 중구조 개편과..."` — Exp-189가 이미 로그로 특정한 바로 그 지점
    (`[SilenceGate] d_eff=3.59 last_word='국방환경' next_word='을' ... path=split_hard`)과 일치.
  - `"...무기체계 소모 강."` ⏎ `"요 등 저비용 고효율..."` — Exp-186/188이 다뤘던 "소모 강요" 지점과 표면
    패턴은 같지만, **이번 재현이 Exp-188 이전(diar-flip)의 재발인지 SILENCE_HARD_SECS의 또 다른 발현
    지점인지 미확인**(이번 스크리닝 run은 `--trace-tokens` 없이 돌려 `[SilenceGate]`/`[SpeakerAttribution]`
    로그가 없다 — §4-2에서 반드시 재측정으로 확정할 것).
  - 원본 산출물: `.omc/benchmarks/eval_allauto_20260719_1408.json`, 전사
    `.omc/transcripts/kor1_C_R1.txt`, 시각화 `.omc/transcripts/eval_report_allauto_20260719_1408.html`.
    이번 세션 재현에는 참고만 하고, **판단 근거는 반드시 이 세션에서 새로 뜨는 `--trace-tokens` 로그**로
    삼는다(구 로그는 `[SilenceGate]` 상세가 없어 근거로 부족).

- **문제의 정확한 코드 위치** (이미 특정됨 — 재탐색 불필요):
  [whisperlivekit/tokens_alignment.py](../../whisperlivekit/tokens_alignment.py) `_gate_decide()`(현재
  383~430행 부근, 세션 시작 시 라인 번호 재확인):
  ```python
  d_eff = silence_seg.end - silence_seg.start  # (None 가드 생략)
  if d_eff is not None and d_eff >= self.silence_hard_secs:   # SILENCE_HARD_SECS=1.2s (65행)
      return "split", "split_hard"   # ← 문법/화자/언어 판정 전부 건너뛰고 무조건 분할
  # ...화자불일치·hard_boundary·언어전환·should_split_after_silence 문법판정은 이 아래에서만 실행됨
  ```
  `SILENCE_HARD_SECS`(65행, 현재 1.2s, Exp-185가 0.8→1.2로 올림)는 diarization pending 상태가 무한정
  늘어지는 것을 막는 **안전망**이지만, **단어 중간(형태소 경계가 아닌 지점)의 긴 호흡 pause에도 그대로
  적용**돼 kor1처럼 낭독체로 긴 들숨을 쉬는 발화에서 Case B를 만든다. `should_split_after_silence`
  (문법 판정 함수)는 이 하드 세이프넷 분기 **아래에 있어 전혀 호출되지 않는다** — 이게 근본 구조적 원인.

- **공용 워크트리·venv 규약(반드시 준수)**: 새 워크트리 생성 시 `.venv`는 메인 저장소 Junction 공유
  (`mklink /J .venv ..\..\.venv`) — 새로 만들지 않는다. `uv run`/`uv sync`/`uv pip`/`uv add`/`uv lock`/
  extras 없는 `uv sync` **절대 금지**([[shared-venv-uv-run-concurrency-hazard]]) — lint는
  `.venv\Scripts\ruff.exe`(또는 `.venv\Scripts\python.exe -m ruff`), 테스트는
  `.venv\Scripts\python.exe -m pytest` 직접 호출. **측정은 반드시 cwd=워크트리에서**
  ([[worktree-eval-import-resolution]] editable 설치 함정 — `.venv\Scripts\python.exe -c
  "import whisperlivekit; print(whisperlivekit.__file__)"`로 워크트리 경로가 찍히는지 먼저 확인).
  main 워크트리에서는 코드 편집 금지(CLAUDE.md 워크트리 규약) — 반드시 새 브랜치+워크트리에서 작업.

- **측정 정본**: 경로 C만. provenance 로그(`branch=…@… vbcable=ok`) 육안 확인. 스크리닝=`--repeat 1`
  (방향 신호), 채택확정=`--repeat 3`(fail-fast 금지, median+min/max/stdev). diar-ON(Sortformer,
  CRT=3.0), turbo. **이 이슈는 언어모드와 무관**(§0 코드 위치 분석 — diar/언어감지 어느 쪽도 개입하지
  않는 순수 침묵-길이 경로)하므로 kor1은 `--lan auto`와 `--lan ko` **양쪽 다** 재현 시도한다(Exp-189는
  auto에서, Exp-186 최초 발견은 ko에서 — 두 모드 모두에서 나온다는 뜻이므로 수정도 양쪽 다 검증 필요).

---

## 1. 목표

kor1.wav(및 일반적으로 한국어 낭독체 긴 호흡 pause가 있는 모든 입력)에서 `SILENCE_HARD_SECS` 안전망이
**단어 중간에서 강제 분할하는 것을 막는다** — 단, 원래 안전망의 목적(diarization/문법판정이 영영 `pending`
상태로 머무는 것 방지)은 유지해야 한다. **목표 게이트 = Case B 신규 발생 0건**(CLAUDE.md §3.3 hard-fail,
수치 무관 최우선).

---

## 2. 준비

- 워크트리: master(`03de591` 또는 세션 시작 시점 최신)에서 분기 → 브랜치 `exp/silence-hard-caseb-fix`,
  워크트리 `worktrees/silence-hard-caseb-fix`. `.venv`는 Junction 공유(§0).
- `docs/SENTENCE_FINALIZATION_LOGIC.md`(§3.3·§5 부근 — `_gate_decide`/`split_hard` 서술 위치)를 먼저 읽어
  이 안전망이 원래 왜 필요했는지(설계 의도) 파악한다 — Exp-185(SILENCE_HARD_SECS 0.8→1.2 도입 배경)도
  `EXPERIMENTS_LOG.md`에서 `grep -n "Exp-185"`로 확인.

---

## 3. 재현 + 정밀 진단

### 3-1. 재현 측정
- kor1 단독, `--lan auto --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo
  --compression-ratio-threshold 3.0 --trace-tokens --repeat 5`(회차 변동이 크므로 5회 — Exp-189도 동일
  이유로 5회 사용). 이어서 `--lan ko`로 동일하게 5회(코드 위치상 언어모드 무관이 맞는지 교차검증).
- **cwd=워크트리, provenance(`branch=exp/silence-hard-caseb-fix@... vbcable=ok`) 확인 후 진행.**

### 3-2. 로그 분석
1. Case B가 발생한 회차마다 `[SilenceGate]` 로그에서 `d_eff`, `last_word`, `next_word`, `decision`,
   `path`를 추출 — `path=split_hard`인 것과 `path=split_grammar`(diar-flip 계열, Exp-188이 이미 고침)인
   것을 **반드시 구분**한다. 오늘 재현된 "소모 강요" 건이 어느 쪽인지 이 단계에서 확정할 것 — `split_hard`면
   이 세션의 대상, `split_grammar`인데도 재발했다면(Exp-188의 N=8 검증에서 놓친 케이스) 그 자체가 중요한
   별도 발견이므로 §6에서 다루되 이번 수정 범위에 억지로 끼워 넣지 말고 명확히 구분해 보고한다.
2. `path=split_hard`로 확정된 각 사례에 대해 `d_eff`(실측 침묵 길이) 분포를 모은다 — Exp-189 사례는 3.59초.
   진짜 문장/화자 경계의 긴 침묵(정상적으로 분할돼야 하는 경우, 예: 문단 전환)과 낭독체 들숨 pause를
   길이만으로 구분할 수 있는지, 아니면 반드시 다른 신호(형태소 종결 여부 등)가 필요한지 이 분포로 가늠한다.
3. `should_split_after_silence(closing.text, next_seg.text)`를 그 시점의 `closing.text`/`next_seg.text`로
   직접 호출해보고(단위테스트 스타일로) 무엇을 반환하는지 확인 — 만약 이 함수가 이미 "미종결(분할하면 안
   됨)"을 정확히 판정할 수 있다면, **`split_hard` 분기를 완전히 무조건으로 두지 않고 이 판정을 참고하도록
   바꾸는 것**(§4 방향 B)이 가장 안전한 수정이 된다.

---

## 4. 수정 방향 (자율 판단 — 아래 두 후보를 로그 근거로 비교 후 결정, 임의로 셋째 안을 만들어도 됨)

- **방향 A — 임계값 조정**: `SILENCE_HARD_SECS`(현재 1.2s)를 올린다. 단 `assert SILENCE_HARD_SECS <= 2.0`
  (backend.py long-silence 하드리셋 상한과의 관계, 65~66행 주석)이 있어 상한 2.0s를 넘길 수 없다. 3.59초
  같은 실측 사례를 못 막을 수 있고, 값을 올리면 진짜 pending 안전망 발동이 늦어지는 트레이드오프가 있다 —
  단순하지만 근본 해결이 아닐 가능성이 높다는 점을 유닛테스트로 먼저 확인할 것(3.59초 케이스를 2.0s로도
  못 막으면 이 방향은 기각).
- **방향 B — grammar-conditional 강화**: `split_hard` 분기 진입 시에도 `should_split_after_silence`(또는
  최소한 "직전 단어가 조사/어미로 안 끝나는 명백한 미종결 형태"인지의 경량 판정)를 참고해, 명백히 단어
  중간(예: "국방환경" 같은 복합명사가 아직 조사 없이 끝난 경우)이면 **아주 짧게(예: 0.3~0.5s)만 유예해
  다음 토큰을 흡수한 뒤 분할**하는 방식 — 안전망의 목적(무한 pending 방지)은 유지하면서 단어를 살린다.
  구현 시 `pending` 상태를 하나 더 늘리는 셈이라 `PENDING_RESOLVE_CAP`과의 상호작용을 반드시 확인.
- 어느 방향이든 **최소 변경**을 원칙으로 하고(§3.8 카펜터-가이드라인/karpathy-guidelines 스킬 원칙),
  가짜 문제 해결을 위한 새 상수·설정 플래그를 남발하지 않는다.

---

## 5. TDD (필수, 이 순서로)

- 참고 패턴: [tests/test_silence_grammar_gate.py](../../tests/test_silence_grammar_gate.py)의
  `test_diar_short_segment_speaker_flip_does_not_force_case_b_split`(485행 부근, Exp-188)와
  `test_diar_speaker_change_blocks_merge`(265행 부근) — 이번에도 같은 파일에 같은 스타일로 추가한다.
- 신규 테스트(가칭 `test_silence_hard_secs_does_not_split_mid_word`): kor1 실측 패턴을
  `TimedText`/`PuncSegment` 구성으로 재현 — `closing.text`가 조사 없이 끝나는 명사(`"...국방환경"`),
  `silence_seg` 길이 3.59s(또는 발견된 실측값), `next_seg.text`가 `"을 고려한..."`으로 이어지는 경우
  → 수정 전 RED(3분할 또는 `split_hard` 즉시 반환) 확인 → 수정 후 GREEN.
- 기존 회귀 방지 테스트도 유지: **진짜 문장/화자 경계의 긴 침묵은 여전히 분할돼야 한다** — 예를 들어
  `closing.text`가 종결어미로 끝나고 침묵이 3초 이상이면 여전히 `split`이어야 하는 케이스를 반드시 추가해,
  이번 수정이 "안전망을 사실상 무력화"하지 않았음을 검증한다(Exp-188의 `test_diar_speaker_change_blocks_merge`
  가 같은 역할을 한 전례를 따름).
- `.venv\Scripts\python.exe -m pytest tests/ -q` 전체 통과(신규 테스트 포함, 기존 회귀 없음),
  `.venv\Scripts\ruff.exe check .` clean.

---

## 6. 측정 계획

1. **스크리닝(`--repeat 1`)**: kor1(auto + ko 양쪽) + auto 표준세트(bong1/ytn2/sbs1) + ko 세트
   (kor2/kor3) — Case B 재발 여부·방향 신호 확인.
2. 유망하면 **채택확정(`--repeat 3`, fail-fast 금지)**: 위와 동일 파일군 + held-out 단회(ytn1 auto,
   eng1 en) — 화자분리 F1 worst-case 미회귀 → WER max 미회귀 → WER median 개선 → 문장분리 F1 순서로 판정
   (CLAUDE.md §4). **Case B 0건이 최우선 하드 게이트** — 이거 하나만은 수치 트레이드오프로 타협 불가.
3. §0에서 언급한 "겉보기엔 같아 보이지만 diar-flip 계열(Exp-188 대상)일 수 있는 사례"가 이번 측정에서 또
   나오면, 그건 이번 수정과 무관한 별개 재발이니 **로그로 반드시 원인 계열을 구분해 보고**(Exp-188/189가
   해온 "0-firing 노이즈 대조", "정상발동 대조로 인과관계 배제" 방식을 그대로 따른다).

---

## 7. 산출물

- `docs/SENTENCE_FINALIZATION_LOGIC.md` §3.3·§5 갱신(연동 문서 규약 — `_gate_decide`/`split_hard` 서술 갱신).
- `/log-experiment`로 `EXPERIMENTS_LOG.md`에 Exp-N(다음 번호, `EXPERIMENTS.md`에서 최신 번호 확인 후
  이어서) 전체 서술 + `EXPERIMENTS.md` 빠른참조 1행(Epoch 열 포함).
- 브랜치 `exp/silence-hard-caseb-fix`에 커밋 (**master 머지는 하지 않는다** — 사용자 확인 후).

---

## 8. 완료 보고 (사용자에게 제시)

1. 한 줄 결론: 채택 권고 / 기각 권고 / 판단 유보.
2. 정량 표(스크리닝 + 채택확정 N=3 + held-out) + Case B 발생 건수(수정 전/후).
3. 정성 핵심: 수정 전/후 kor1 "국방환경을" 지점 전사 인용, "소모 강요" 재현 건의 원인 계열 판정 결과.
4. 미해결·후속 제안(있다면 — 예: 방향 A/B 둘 다 부분적이라 판단되면 제3의 방향 제안).
5. **사용자 질문**: `exp/silence-hard-caseb-fix`를 master에 머지할지.

---

## 9. 회귀 교훈 (반드시 준수)

- auto 표준세트(bong1/ytn2/sbs1) + ko 세트(kor2/kor3, `--lan ko`) 무회귀 확인 — kor1 표적 수정이 다른
  파일·다른 언어모드를 회귀시키면 안 된다(§3.8 범용 개선 원칙, 데이터 특화 하드코딩 금지).
- 단일화자 파일(kor1/kor2/kor3/eng1)의 화자분리 F1이 0.0%/100.0%로 극단으로 나오는 것은 **지표 산식
  경계값 아티팩트**(Exp-185/187/188/189에서 반복 확인)이지 실제 화자분리 실패가 아니다 — 이 세션의 판정
  근거로 쓰지 않는다.
- Case B는 어느 방향으로 수정하든 **신규 발생 0건**이 하드 게이트 — 다른 파일에서 새 Case B가 생기면
  그 즉시 원인 조사·수정 우선(머지 보류).
