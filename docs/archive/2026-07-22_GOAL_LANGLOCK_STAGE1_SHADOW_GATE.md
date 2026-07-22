# 안 B — Stage 1 섀도우 게이트 (samelang 머지 반영 후 재개)

## Context

**왜 이 작업을 하는가.** 한국어 발화가 영어로 번역 전사되는 "언어잠금" 실패가 bong1 WER median의 약 14%를
먹는다(Exp-195). 그 실패를 방출 **전에** 검출하는 신호(`p_opp` = 잠긴 언어의 반대쪽 재정규화 확률)를
Stage 0에서 찾아 계측까지 끝냈다. 남은 일은 **그 신호에 게이트를 씌웠을 때 실제로 몇 번 발동하는지**를
재는 것이다 — 단 **실제 언어 재감지는 트리거하지 않고 `would_fire` 로깅만** 한다(섀도우 모드).

**왜 멈춰 있었는가.** Exp-195의 표본 확대에서 ko 단일언어 세션 12개(3756 프로브)에 `p_opp≥0.97` 발동이
**23건(0.61%)** 나왔고 그중 2건은 정상 전사 구간의 순수 오탐이었다(kor2 `먼저 육군`, kor3 `원 거리 타격`).
사전 등록 조건("단일언어 세션 발동 0건")이 깨져 자율 진행을 멈추고 사용자 판단을 기다렸다.
**사용자가 진행을 승인**해 재개한다.

**완화 근거(이 작업의 전제)**: 발동 23건은 전부 `seglen ≤ 1.02s`·최대 연속 K=2라, 인계서 §4가 Exp-189
대응으로 **미리** 정해둔 게이트(`seglen≥2.0s ∧ K≥3 ∧ T≥1.0s`)에 오프라인 재현 기준 **23/23 전부 걸린다**.
반대로 ytn1의 참양성 run 2개는 통과한다. **이번 작업이 검증할 값이 바로 "런타임 게이트도 동일하게 막는가"다.**

**새 변수**: 다른 세션이 `fix/samelang-no-refresh`를 master에 머지했다(`3ad14a6`). 아래 §1이 그 영향 분석이다.

---

## 1. 사전 검증 결과 — samelang 머지와의 충돌 분석 (이미 완료, 재조사 불필요)

`3ad14a6` = 커밋 `47fd76c`(같은 언어 확정 화자전환에서 경계 재디코딩 스킵) + `4448288`(쿨다운으로 건너뛴
eager 감지의 직전 결과를 스킵 판정에 재사용). **두 커밋 모두 `whisperlivekit/simul_whisper/backend.py`만 수정.**

| 검증 항목 | 결과 |
|---|---|
| **코드 파일 충돌** | **0건.** 브랜치는 `align_att_base.py`·`simul_whisper.py`·`scripts/`·`metrics.py`, master는 `backend.py`만 — 파일 집합이 완전 분리 |
| 병합 충돌 (`git merge-tree` 시뮬레이션) | `.omc/transcripts/*.txt` 7개 + `docs/TRANSCRIPTION_REQUIREMENTS.md` 1개. **`.py` 충돌 0** |
| **ko/en 세션 영향** | **없음.** `_handle_change_speaker`의 `if lang_locked:` 분기가 `eager=None`으로 두고 `eager_cached`도 None이라 `lang_evidence=None` → early return 미진입. **Exp-195의 ko/en 수치(23건·0.61%·게이트 0/23)는 그대로 유효** |
| auto 세션 영향 | **있음.** 동일언어 화자전환에서 `refresh_segment` 미호출 → 버퍼가 안 잘림 → `seglen`이 극소가 되는 순간 감소. Exp-195의 auto 수치(ytn1 25건 등)는 **직접 비교 불가** |
| 섀도우 게이트 리셋 훅 | **오히려 단순해진다** (§3-3 참조) |

**재베이스 필요성 갱신**: goal 문서가 "master가 `whisperlivekit/`를 안 건드려 재베이스 불필요"라 적었던 근거는
**무효화됐다**. 반드시 master를 브랜치에 병합한 뒤 작업한다.

**머지의 미처리 항목** (인계서 §7이 검증을 권고했던 건이라 이번에 함께 정리):
- Exp 기록 없음. `EXPERIMENTS_LOG.md`에 samelang 항목이 없다(grep 결과 `Exp-155`만 나옴).
- **`Exp-155`가 사실상 같은 가설이었고 기각됐다** — 당시 사유: bong1 new_speaker 15/15가 동일언어라 100%
  스킵 → 진짜 다른 화자 블렌딩 → 화자F1 −4.1. 단 Exp-155는 **E4(base 기질)** 이고 리셋 범위도 더 넓었다.
  이번 머지는 커밋 메시지상 bong1 화자F1 73.7→78.8%, ytn2 90→94.7%로 **개선**으로 측정됐다.
- epoch 미갱신. `EXPERIMENTS.md`는 여전히 "현재 master = Epoch 5". new_speaker 실패모드를 바꾸는
  구조 변경이므로 CLAUDE.md 연동 갱신 표상 **E5 → E6 bump 대상**.

---

## 2. 작업 순서

### Step 0 — 환경 준비

작업 위치: `worktrees/bong1-eval-diagnostics/`, 브랜치 `exp/lang-lock-stage0`(현재 HEAD `61190c6`).

```bash
cd worktrees/bong1-eval-diagnostics
.venv\Scripts\python.exe -c "import whisperlivekit; print(whisperlivekit.__file__)"   # 워크트리 경로 확인 필수
git merge master
```

충돌 해소:
- `.omc/transcripts/*.txt` 7개 → **브랜치판 채택**(`git checkout --ours <파일>`). Exp-195 측정 산출물이라
  provenance를 유지한다. 어차피 다음 측정이 덮어쓴다.
- `docs/TRANSCRIPTION_REQUIREMENTS.md` → **수동 병합**. master +17줄 / 브랜치 +70줄로 서로 다른 절이라
  양쪽을 모두 살린다.

병합 후 `.venv\Scripts\python.exe -m pytest tests/ -q`로 기준선 확보(브랜치 기준 648 pass였음).

### Step 1 — samelang 후속 처리 (사용자 지시로 이 작업에 포함)

1. **`EXPERIMENTS_LOG.md`에 Exp-196 기록** — samelang 머지. 커밋 메시지의 측정치를 옮기되
   **Exp-155와의 관계를 반드시 명시**한다(같은 가설·E4에서 기각·이번엔 E5 turbo 기질에서 개선,
   리셋 범위 차이). `EXPERIMENTS.md` 빠른참조 1행 추가.
2. **epoch bump E5 → E6** — `EXPERIMENTS.md` "코드 세대(Epoch)" 절에 E6 항목 추가
   (경계 사유 = new_speaker 동일언어 스킵으로 실패모드 변경), 이전 세대 파라미터 결론에 `[E5·재검증]` 부여.
3. Exp-195는 **E5에서 측정된 것**으로 표기를 유지하고, 아래 Exp-197은 **E6**로 적는다.

### Step 2 — TDD: 테스트 먼저

신규 `tests/test_stage1_shadow_gate.py`. **기존 `tests/test_sot_lang_probe.py`의 픽스처를 재사용**한다 —
`_fake_base(detected_language=..., language=...)`(:257), `_fake_tokenizer()`(:54), `_make_decoder()`(:64).

| # | 검증 | 기대 |
|---|---|---|
| 1 | 전 조건 만족 | `would_fire=True` 로그 1회 |
| 2 | **G1 가드**: `cfg.language="ko"` / `"en"` | **절대 미발동** (인계서 §4 기각 조건) |
| 3 | G2: `detected_language=None` | 미발동 |
| 4 | **G3: `seglen=1.02`** (Exp-195 실측 최대값) | 미발동 — **Exp-195 회귀 테스트** |
| 5 | G3: `seglen=0.24` (실측 최빈값, 20/23건) | 미발동 |
| 6 | G4: `p_opp=0.96` | 미발동 |
| 7 | G5: K=2 (실측 최대 연속) | 미발동 |
| 8 | G5: K=3이나 지속 0.3s (10Hz) | 미발동 |
| 9 | G6: 쿨다운 3.0s 이내 | 미발동 |
| 10 | G7: `pending_language_switch` 세팅 / `eager_lang_detect=True` | 각각 미발동 |
| 11 | **행동 불변식**: 게이트 전부 통과 시에도 `_apply_detected_language` **미호출** | monkeypatch 호출 감시로 0회 |
| 12 | 리셋: `refresh_segment()` 후 증거 0 / `p_opp` 하락 후 증거 0 | |
| 13 | 롤백 스위치 `STAGE1_SHADOW_ENABLED=False` | 아무 동작 없음 |
| 14 | **Exp-195 실측 시퀀스 재현**(seglen 0.24·K=1 × 23) | `would_fire` 총 0 |

### Step 3 — 구현

**파일**: `whisperlivekit/simul_whisper/align_att_base.py` 단 1개.

**트리거 지점**: 이미 존재하는 프로브 호출부를 그대로 쓴다 — `infer()`의
`if new_segment: self._log_sot_lang_probe(logits)`(현재 :608-609). 여기가 encoder_feature를 손에 쥔
유일한 지점이고 추가 비용 0이다. `_sot_lang_probe_impl()`이 이미 `locked`/`p_ko`/`p_en`을 계산하므로
그 직후 `self._stage1_shadow_gate(locked, p_ko, p_en)` 한 줄을 호출한다.

**상수** (기존 `SOT_PROBE_*` 옆에 배치):
```python
STAGE1_SHADOW_ENABLED = True   # 짝지음 A/B 롤백 스위치
STAGE1_TAU = 0.97              # p_opp 문턱
STAGE1_MIN_SEGLEN = 2.0        # 최소 버퍼 — 가장 중요(Exp-189 고신뢰 오탐 배제)
STAGE1_MIN_BATCHES = 3         # 연속 K
STAGE1_MIN_DURATION = 1.0      # 지속 T (10Hz라 K만으론 0.3s)
STAGE1_COOLDOWN_SECS = 3.0     # last_lang_switch_time 재사용
```

**증거 상태**: `_sot_probe_stats()`와 동일한 **인스턴스 lazy 생성** 패턴(:443-459)을 따른다
— `{"count", "first_t", "lang", "would_fire", "blocked_by": {...}}`. `DecoderState`에 필드를 추가하지 않는다
(섀도우는 디코더 상태가 아니라 계측이다).

**게이트 (전부 AND, 통과해도 로깅만)**:

| | 조건 | 참조 |
|---|---|---|
| G1 | `cfg.language == "auto"` | ko/en 세션 원천 차단 |
| G2 | `state.detected_language is not None` | |
| G3 | `segments_len() >= STAGE1_MIN_SEGLEN` | :216 |
| G4 | `p_opp >= STAGE1_TAU` | `_sot_lang_probe_impl` 계산값 재사용 |
| G5 | `count >= K` **and** `t_abs - first_t >= T` | 증거 누적 |
| G6 | `t_abs - state.last_lang_switch_time >= STAGE1_COOLDOWN_SECS` | `decoder_state.py:38` |
| G7 | `state.pending_language_switch is None` **and** `not state.eager_lang_detect` | `decoder_state.py:31,39` |

**증거 누적/리셋 규칙**:
- G1~G4 만족 → `count += 1`, `first_t` 최초 1회 설정
- **G3 또는 G4 불만족 → 증거 리셋** (짧은 버퍼 발동이 K에 산입되면 안 된다)
- `refresh_segment()`(:171) 안에 리셋 1줄 — **이 한 곳이 긴침묵(`backend.py:376` `refresh_segment(complete=True)`)·
  QG refresh·new_speaker 전체재디코딩을 모두 커버**한다
- `_apply_detected_language()`(:256) 안에 리셋 1줄 — 언어가 바뀌면 이전 증거는 무효

> **samelang 머지와의 정합**: 동일언어 화자전환 skip 경로는 `refresh_segment`를 호출하지 않지만,
> 그 경로는 **버퍼도 언어도 바꾸지 않으므로 리셋이 불필요**하다. 즉 설계 문구
> "refresh·new_speaker·긴침묵 시 리셋"이 새 master에서는 **`refresh_segment()` 훅 한 곳**으로 정확히 표현된다.
> 별도 new_speaker 훅을 추가하지 말 것 — 불필요한 리셋은 참양성 증거를 깎는다.

**섀도우 규칙 (이 작업의 핵심 제약)**:
- 게이트가 전부 만족돼도 **`_apply_detected_language`를 절대 호출하지 않는다.**
- `logger.warning("[Stage1Shadow] would_fire=True lang=%s p_opp=%.4f t=%.2f seglen=%.2f k=%d dur=%.2f", ...)` 만 남긴다.
- 세션 요약은 기존 `_log_lang_drift_stats()`(:522) 옆에 **별도 `[Stage1ShadowStats]` WARNING 1줄**로 낸다
  (게이트별 차단 카운트 포함). 기존 `[LangDriftStats]` 포맷을 건드리지 않아
  `scripts/analyze_sot_lang_probe.py`의 파서 호환이 유지된다.

### Step 4 — 행동 변경 0 검증 (성공 기준)

```bash
.venv\Scripts\python.exe -m pytest tests/ -q          # 기존 전부 통과 + 신규 14개
.venv\Scripts\ruff.exe check whisperlivekit/simul_whisper/align_att_base.py tests/test_stage1_shadow_gate.py
git diff --stat                                        # align_att_base.py + 신규 테스트만
git diff | grep -n "_apply_detected_language"          # 신규 호출이 없어야 함
```

### Step 5 — 측정 (auto 4파일, `--repeat 1`)

ko/en은 **G1 가드로 구조적 발동 불가**이므로 런타임 측정 대신 Step 2 테스트 #2로 검증한다(사용자 결정).

```bash
.venv\Scripts\python.exe scripts/eval.py \
  --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 test_data/ytn1.mp3 \
  --lan auto --repeat 1 \
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo \
  --compression-ratio-threshold 3.0 --trace-tokens \
  --output .omc/benchmarks/eval_stage1_shadow_R1.json
```

**측정 전 필수**: 포트 8901 점유 확인, 다른 세션의 VBCable 캡처 겹침 확인, 서버 로그 provenance에
`vbcable=ok` 확인. 문제 있으면 멈추고 보고(원격 조치 불가).

**수집·판정할 것**:
1. 파일별 `would_fire` 카운트 + 게이트별 차단 카운트(`[Stage1ShadowStats]`)
2. **ytn1 참양성 2 run이 여전히 통과하는가** — Exp-195 오프라인 예측과 대조
3. WER/화자F1이 catastrophic 회귀가 아닌지 (행동 변경 0이므로 밴드 내여야 정상. **단 samelang 머지로
   auto 베이스라인이 이동했으므로 Exp-195 auto 수치와 직접 비교하지 말 것** — 회귀 판정이 아니라 sanity)
4. `would_fire` 지점의 전사를 대조해 참양성/오탐 정성 분류

### Step 6 — 기록·커밋

- `docs/research/SOT_LANG_PROBE_STAGE0.md` §11 신설 — 섀도우 게이트 설계·would_fire 결과
- `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` §4-0-3 — 안 B 완료·다음 결정(실제 게이트 적용 여부)
- `EXPERIMENTS_LOG.md` **Exp-197**(섀도우, **E6**) + `EXPERIMENTS.md` 빠른참조 1행
- 브랜치 `exp/lang-lock-stage0`에 커밋. **master 머지는 사용자 확인 후** (실제 적용은 별도 단계)

---

## 검증 (end-to-end)

| 무엇을 | 어떻게 | 통과 기준 |
|---|---|---|
| 행동 변경 0 | `pytest tests/ -q` | 병합 후 기준선 + 신규 14개 전부 통과, 기존 실패 0 |
| 가드 위반 없음 | 테스트 #2 | `--lan ko`/`en`에서 발동 0 |
| Exp-195 오탐 차단 | 테스트 #4·#5·#7·#14 | 실측 오탐 패턴(seglen≤1.02·K≤2) 전부 미발동 |
| 섀도우 불변식 | 테스트 #11 + `git diff` grep | `_apply_detected_language` 신규 호출 0 |
| 런타임 거동 | Step 5 측정 | `[Stage1Shadow]`/`[Stage1ShadowStats]` 로그 실제 출력, ytn1에서 would_fire ≥ 1 |
| lint | `.venv\Scripts\ruff.exe check` | 신규 위반 0 |

---

## 함정 (반드시 지킬 것)

- **`uv` 절대 금지** — 워크트리가 메인 `.venv`를 Junction 공유한다. `uv run`·`uv sync`가 진행 중인 측정을
  전멸시킨다. `.venv\Scripts\python.exe` / `.venv\Scripts\ruff.exe` **직접 호출**만.
- **워크트리 cwd에서 실행** — 메인에서 돌리면 editable 설치 때문에 다른 코드를 잰다. 첫 명령으로 import 경로 확인.
- **측정 중 워크트리 코드 mutation 금지** — eval은 파일마다 서버를 재기동하므로 중간에 코드를 고치면
  런마다 다른 코드를 재게 된다.
- **`_apply_detected_language`를 실제 트리거에 연결하지 말 것** — 연결하는 순간 auto 세션 전체의 언어 재감지
  거동이 바뀐다. 커밋 전 `git diff`로 재확인.
- **`refresh_segment` 호출 금지** — 인계서 §3이 반증한 항목(Exp-095/096/097에서 catastrophic).
- ko 세션 화자F1이 0.0%/100.0% 극단으로 나오는 것은 산식 경계 아티팩트이지 실패가 아니다.
- N=1 스크리닝 결과를 "확정"으로 쓰지 말 것 — 방향 신호로만 서술한다.
