# 실험 로그 — 개별 Exp 서술 (LOG)

이 파일은 **개별 실험의 전체 서술**(가설·변경·테스트 설정·전사 정성분석·채택 판정)을 보관한다.
현행 상태·베이스라인·이월 핵심사실·빠른참조·epoch 게이트는 [EXPERIMENTS.md](EXPERIMENTS.md)(STATE)에 있다.

> **3계층 구조**
> - [EXPERIMENTS.md](EXPERIMENTS.md) — **STATE** (항상 읽음: 요약·regime·baseline·이월핵심·빠른참조·epoch 게이트)
> - **이 파일** — **LOG** (온디맨드: Exp-131~ 전체 서술). 특정 Exp 상세는 `grep "Exp-NNN"`으로 해당 블록만 읽는다.
> - [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md) — **ARCHIVE** (Exp-001~130, 동결)

> **읽기 규약**: 세션 시작 시 STATE만 읽고, 이 LOG는 필요한 Exp만 grep 한다. 과거 Exp 결론을 현재 작업의 채택/기각 근거로 쓰기 전 STATE의 **epoch 게이트**를 적용한다 — 다른 코드 세대 결론은 '방향 신호'로만.

> **Exp ↔ Epoch**: Exp-131~137 = **E1**(언어고정·비음성억제 없음, master 계열). Exp-138~139 = **E2 후보**(`exp/meta-token-suppress`: suppress_nonspeech + lang_restrict_koen). 신규 Exp는 측정 대상 코드의 epoch를 provenance에 함께 적는다.

---

<!-- 신규 실험(Exp-131+)은 이 아래에 추가.
     섹션 순서: 가설 / 변경(브랜치) / 테스트 설정 / ### 테스트 세트 결과(N=3 표) /
               ### 분석(전사 정성 대조 — 수치 표 직후·채택 판정 직전) /
               ### 채택 (조건) 판정(①max ②median) / 원인 분석 / 다음 가설 / JSON 경로

     ### 분석 형식 예시:
     ### 분석 (전사 내용 정성 대조)
     **bong1** (R_median 기준):
     - **비언어 토큰**: 전사 `"(웃음) 그래서…"` / 정답 `"그래서…"` — 3회.
     - **환각 폭주**: 전사 `"네 네 네 네 네"` / 정답 `"네."` — 무음 구간.
     **ytn2** (R_median 기준):
     - **코드스위칭 실패**: 전사 `"그건 trust"` 잘림 / 정답 `"그건 trust 있는"`.
     **이번 변경 영향**: (개선/악화/무관 1~2줄 요약)
     ※ eval JSON(`.omc/benchmarks/`)의 files[].transcription·reference를 직접 읽어 작성. 추측 금지. -->

## Exp-131 — PLC=2.0 단독 (2026-06-25)

**가설**: `periodic_lang_check=2.0` 활성화 시 언어 고착 후 환각 체인 억제 → sbs1/ytn2 WER 개선.
**변경**: 파라미터만 (`--periodic-lang-check 2.0`), 코드 수정 없음. master cwd.
**브랜치**: master (파라미터 전달)

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0, beams=2)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| bong1 | 64.7% | 45.3% | 34.1% | 45.3% | **64.7%** | 15.4% | 42.9% | +1.2pp | **+9.7pp ⚠️** |
| ytn2  | 36.5% | 60.1% | 34.5% | 36.5% | 60.1% | 14.3% | 60.0% | **-7.8pp** | -1.5pp |
| sbs1  | 23.8% | 20.8% | 21.4% | 21.4% | 23.8% | 1.6%  | 36.4% | **-3.0pp** | **-8.9pp** |

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 max: 55.0% → 64.7% (+9.7pp) | ❌ **위반** |
| ② median 개선 | ytn2 -7.8pp, sbs1 -3.0pp / bong1 +1.2pp | △ 혼합 |

**판정: ❌ 기각**
- 이유: bong1 max 55.0% → 64.7% (+9.7pp) — 1순위 기준(max 미회귀) 위반.
- 관찰: ytn2·sbs1은 median과 max 모두 개선 → PLC=2.0이 언어고착 억제·환각 체인 차단에 효과적임을 확인.
  bong1 max 악화는 웃음 구간 환각과의 복합 상호작용 또는 N=3 분산 노이즈 가능성 있음.
- 다음: Exp-132(beam=3 단독) → Exp-133(beam=3 + PLC=2.0 콤보)로 PLC=2.0 효과를 조합에서 재검증.

**JSON**: `.omc/benchmarks/eval_exp131_plc20_20260625_1548.json`

---

## Exp-132 — beam=3 단독 (2026-06-25)

**가설**: `beams=2→3` 증가 시 다화자(bong1)·코드스위칭(ytn2) WER 개선. 탐색 폭 확장으로 혼재 언어 처리 정확도 상승.
**변경**: `--beams 3` 전달 (eval.py harness `--beams` pass-through 신규 추가). 코드 브랜치: `harness/eval-beams-flag`(`90acece`).
**측정 cwd**: `worktrees/harness-eval-beams-flag`

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0, PLC=None)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| bong1 | 36.0% | 35.3% | 39.0% | 36.0% | 39.0% | 1.9% | 52.6% | **-8.1pp** | **-16.0pp** |
| ytn2  | 36.0% | 29.6% | 35.5% | 35.5% | 36.0% | 3.6% | 40.0% | **-8.8pp** | **-25.6pp** |
| sbs1  | 18.5% | 27.4% | 51.8% | 27.4% | **51.8%** | 17.3% | 36.4% | +3.0pp | **+19.1pp ⚠️** |

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | sbs1 max: 32.7% → 51.8% (+19.1pp); bong1 max: 55.0% → 39.0% (-16pp); ytn2 max: 61.6% → 36.0% (-25.6pp) | ❌ **sbs1 위반** |
| ② median 개선 | bong1 -8.1pp, ytn2 -8.8pp / sbs1 +3.0pp | △ 혼합 |

**판정: ❌ 기각**
- 이유: sbs1 max 32.7% → 51.8% (+19.1pp), stdev 5.1% → 17.3% — 1순위 기준(max 미회귀) 위반. R3 51.8%는 catastrophic.
- 관찰: bong1·ytn2 WER은 극적 개선 (bong1 max -16pp, ytn2 max -25.6pp) — beam=3이 다화자·코드스위칭에 강력한 효과.
  단일화자(sbs1)에서는 분산 폭발 → 언어 고착 후 환각 체인과 상호작용 가능성.
- 다음: Exp-133(beam=3 + PLC=2.0) — PLC=2.0이 Exp-131에서 sbs1 max를 -8.9pp 개선했으므로 콤보에서 sbs1 상쇄 기대.

**JSON**: `.omc/benchmarks/eval_exp132_beam3_20260625_1615.json`

---

## Exp-133 — beam=3 + PLC=2.0 콤보 (2026-06-25)

**가설**: beam=3이 bong1·ytn2 WER을 개선하고 PLC=2.0이 sbs1 max를 억제 → 콤보에서 세 파일 모두 개선.
**변경**: `--beams 3 --periodic-lang-check 2.0`. 코드 브랜치: `harness/eval-beams-flag`(`90acece`).
**측정 cwd**: `worktrees/harness-eval-beams-flag`

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| bong1 | 55.6% | 32.9% | 55.9% | 55.6% | 55.9% | 13.2% | 57.1% | **+11.5pp ⚠️** | +0.9pp |
| ytn2  | 36.5% | 21.2% | 23.6% | 23.6% | 36.5% | 8.2% | 63.2% | **-20.7pp** | **-25.1pp** |
| sbs1  | 40.5% | 23.2% | 22.6% | 23.2% | 40.5% | 10.1% | 36.4% | -1.2pp | **+7.8pp ⚠️** |

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | sbs1 max: 32.7%→40.5% (+7.8pp); bong1 max: 55.0%→55.9% (동일수준); ytn2 max: 61.6%→36.5% (-25.1pp) | ❌ **sbs1 위반** |
| ② median 개선 | ytn2 -20.7pp, sbs1 -1.2pp / bong1 +11.5pp | ❌ **bong1 대폭 회귀** |

**판정: ❌ 기각**
- 이유: ① sbs1 max +7.8pp (1순위 위반) ② bong1 median +11.5pp (공동 1순위 타겟 대폭 회귀).
- 관찰:
  - ytn2는 극적 개선 (median -20.7pp, max -25.1pp, F1 +7.6pp) — beam=3+PLC=2.0 콤보가 코드스위칭에 매우 강력.
  - bong1은 R2=32.9%(매우 좋음)인데 R1·R3=55~56%(나쁨) — 콤보가 bong1에서 bimodal 분포를 유발.
  - sbs1은 R1=40.5% 한 번 터지면서 max 회귀; R2·R3=22~23%는 baseline보다 좋음.
  - **패턴**: beam=3은 ytn2에 일관되게 강력하지만 bong1·sbs1에서 간헐적 catastrophic run 유발.

### 3회 연속 기각 패턴 요약

| Exp | 핵심 변경 | ytn2 median Δ | bong1 max Δ | sbs1 max Δ |
|-----|---------|-------------|------------|-----------|
| Exp-131 | PLC=2.0 | -7.8pp ✓ | **+9.7pp ❌** | -8.9pp ✓ |
| Exp-132 | beam=3 | -8.8pp ✓ | -16.0pp ✓ | **+19.1pp ❌** |
| Exp-133 | beam=3+PLC=2.0 | **-20.7pp ✓** | +0.9pp ≈ | **+7.8pp ❌** |

**공통 신호**: beam=3이 ytn2에 강력한 효과(일관). bong1/sbs1의 간헐적 catastrophic run이 채택을 막음.
**다음 방향 후보**: (1) beam=3+PLC=2.0에서 sbs1 bad run의 원인 진단(JSON 분석) → CRT 조정으로 억제 시도; (2) bong1 catastrophic run 원인 분석(웃음 구간 환각 vs beam 상호작용); (3) 다른 접근(VAD·no_speech_threshold 등)으로 방향 전환.

**JSON**: `.omc/benchmarks/eval_exp133_beam3_plc20_20260625_1638.json`

---

## Exp-134 — lang-set ko,en 언어 집합 로짓 마스킹 (2026-06-25)

**가설**: Whisper 디코더가 한국어/영어 발화에 CJK·키릴·아랍 문자 등 무관한 스크립트 토큰을 확률 경쟁에 포함시켜 코드스위칭 환경에서 혼동 및 WER 증가를 유발한다. 허용 스크립트(Hangul·Latin)에 속하는 알파벳 문자를 가진 토큰만 살리고 나머지를 `-inf`로 마스킹하면 디코딩 공간이 좁아져 인식률이 향상될 것이다.

**변경**: 신규 모듈 + CLI 파라미터 추가. 코드 브랜치: `feat/lang-set-mask`(`fb439b3`). 워크트리: `worktrees/lang-set-mask/`.

| 파일 | 변경 내용 |
|------|----------|
| `whisperlivekit/simul_whisper/language_set_mask.py` | 신규 — `LanguageSetLogitFilter` 클래스. init 시 vocab 전수 스캔 → Hangul·Latin 이외 알파벳 포함 토큰 suppression mask 생성. `apply(logits)` = `masked_fill_(-inf)` |
| `whisperlivekit/simul_whisper/config.py` | `AlignAttConfig`에 `lang_set: Optional[str] = None` 필드 추가 |
| `whisperlivekit/simul_whisper/decoder_state.py` | `DecoderState`에 `lang_set_filter: Any = None` 필드 추가 |
| `whisperlivekit/simul_whisper/simul_whisper.py` | `_init_state()` — `cfg.lang_set` 있으면 `LanguageSetLogitFilter` 초기화; `_apply_token_suppression()` — 매 디코드 스텝마다 마스크 적용 |
| `whisperlivekit/simul_whisper/backend.py` | `AlignAttConfig(...)` 생성 시 `lang_set=getattr(self, "lang_set", None)` 전달 |
| `whisperlivekit/config.py` | `WhisperLiveKitConfig`에 `lang_set: Optional[str] = None` 추가 |
| `whisperlivekit/parse_args.py` | SimulStreaming 그룹에 `--lang-set` 인수 추가 |
| `whisperlivekit/core.py` | `simulstreaming_params`에 `"lang_set": config.lang_set` 추가 |
| `scripts/eval.py` | `--lang-set` 인수 추가 + provenance 게이트에 `backend_policy` 포함 |

**마스크 설계 원칙**:
- Byte-fallback 토큰(UTF-8 디코드 실패) → 항상 유지
- Special token(id ≥ eot) → 항상 유지
- 알파벳이 아닌 문자(digits, punct, space) → 항상 유지
- LATIN·HANGUL 이외 스크립트 알파벳 포함 토큰 → `-inf` 억제

### 테스트 설정

```
python scripts/eval.py \
  --model-dir "C:/…/whisperlivekit/model/whisper-large-v3-turbo" \
  --files ".../test_data/bong1.wav" test_data/ytn2.mp3 test_data/sbs1.mp3 \
  --diarization \
  --sortformer-model "C:/…/model/sortformer-4spk-v2.nemo" \
  --compression-ratio-threshold 3.0 \
  --lan auto --lang-set ko,en --repeat 1 --paths C --expect-code-root .
```
provenance: `code=lang-set-mask, branch=feat/lang-set-mask@fb439b3, beams=2, CRT=3.0, PLC=4.0(server default), diar=on, vbcable=ok`

### 테스트 세트 결과 (N=1 탐색, diar-ON, CRT=3.0, beams=2, PLC=4.0)

> ⚠️ **N=1 탐색 결과** — 방향 확인용. 채택/기각 판정을 위해 N≥3 측정 필요.

| 파일 | R1 WER | F1 | vs baseline WER Δ | vs baseline F1 Δ |
|------|--------|-----|------------------|-----------------|
| bong1 | **31.7%** | 42.4% | **-12.4pp** (base 44.1%) | -6.1pp (base 48.5%) |
| ytn2  | **23.6%** | 52.6% | **-20.7pp** (base 44.3%) | -3.0pp (base 55.6%) |
| sbs1  | **23.2%** | **76.2%** | **-1.2pp** (base 24.4%) | **+39.8pp** (base 36.4%) |

### 주요 관찰

- **bong1 WER 31.7%**: 베이스라인 min(33.5%)보다 낮음 — 최선 케이스를 넘는 수치. 다화자+긴 발화 환경에서도 마스킹이 효과적.
- **ytn2 WER 23.6%**: 베이스라인 min(23.6%)과 동일 — Exp-133에서 beam=3+PLC=2.0 콤보와 같은 최저치를 beams=2만으로 달성.
- **sbs1 F1 76.2%**: 베이스라인 36.4%(diar-ON) 대비 +39.8pp 급등. diar-OFF 기준치(76.2%, EXPERIMENTS.md §이월 핵심사실)와 정확히 일치 → 마스킹이 Sortformer 과분할 억제 또는 환각 감소를 통해 문장 경계 정확도를 대폭 향상시킨 것으로 추정.
- **코드스위칭 억제 효과**: Exp-131~133에서 해결하지 못했던 ytn2·bong1 동시 개선을 N=1에서 달성.
- WER 전 파일 개선이지만 F1은 bong1(-6.1pp)·ytn2(-3.0pp) 소폭 하락 → N=3에서 변동 확인 필요.

### 채택 조건 예비 판정 (N=1 기준, 참고용)

| # | 조건 | 예비 판정 |
|---|------|---------|
| ① max WER 미회귀 | N=1이므로 판정 불가 | ⏳ |
| ② median 개선 | bong1 -12.4pp, ytn2 -20.7pp, sbs1 -1.2pp — 전 파일 개선 | ✅ 긍정 |

**현재 판정: ⏳ N=3 측정 대기**
- N=1 방향 지표는 매우 강력 — 3회 연속 기각됐던 ytn2·bong1 동시 개선을 단번에 달성.
- 분산이 큰 VBCable 환경 특성상 운 좋은 단일 측정일 가능성 배제 불가 → N≥3 필수.
- N=3 명령: `--repeat 3` 동일 설정으로 재측정.

### 다음 가설

- **N=3 측정(최우선)**: 동일 설정 3회 반복 → median/max/stdev 공식 산출 → 채택/기각 확정.
- **채택 시 held-out**: ytn1(코드스위칭 일반화) + eng1(영어 회귀 감시) 단회 측정.
- **Stage 2(언어 전환 컨텍스트 리셋)**: 언어 전환 감지 시 컨텍스트 토큰을 리셋해 이전 언어 편향 제거. Stage 1 채택 후 진행.

**JSON**: 미저장 (N=1 탐색 모드, `--repeat 1` 임시 실행)

> **주의**: 이 N=1 수치는 통계 이상치로 밝혀짐. N=3 공식 측정(Exp-136)에서 bong1 55.0%(+10.9pp 회귀). N=1 탐색 결과를 그대로 신뢰하면 안 된다는 경고 사례.

---

## Exp-135 — Stage 3 provisional buffer (N=1 탐색) (2026-06-25)

**가설**: 언어 전환 감지가 `_maybe_periodic_lang_check()` 에서 일어날 때, 그 직전 `_split_tokens()`에서 잘못된 언어로 디코딩한 토큰이 이미 `state.tokens.append()`로 확정된다. 1-스텝 지연 버퍼(provisional)를 두면 다음 `infer()` 시작 시 언어 전환이 감지됐으면 해당 토큰을 버리고, 아니면 정상 확정할 수 있어 경계 오류를 줄일 수 있다.

**변경**: Stage 2(언어 전환 시 `pending_incomplete_tokens` 클리어) 위에 Stage 3 추가.

| 파일 | 변경 내용 |
|------|----------|
| `worktrees/lang-set-mask/whisperlivekit/simul_whisper/decoder_state.py` | `provisional_tokens`, `provisional_words` 필드 추가; `reset()` 에서 클리어 |
| `worktrees/lang-set-mask/whisperlivekit/simul_whisper/align_att_base.py` | `_commit_provisional()` 메서드 추가; `_apply_detected_language()` Stage 3 클리어 블록 추가; `refresh_segment()` provisional 클리어 추가; `infer()` 토큰 append를 provisional 지연으로 교체 |

**측정 설정**: Stage 1+Stage 2+Stage 3 결합, N=1 탐색. `code=lang-set-mask, branch=feat/lang-set-mask@fb439b3(uncommitted), beams=2, CRT=3.0, diar=on, vbcable=ok`

### 테스트 세트 결과 (N=1 탐색, diar-ON, CRT=3.0, beams=2)

> ⚠️ **N=1 탐색 결과** — 방향 확인용.

| 파일 | R1 WER | F1 | vs baseline Δ | vs Exp-134(Stage1) Δ |
|------|--------|-----|--------------|---------------------|
| bong1 | 34.7% | 37.5% | -9.4pp | **+3.0pp (악화)** |
| ytn2  | 26.1% | 63.2% | -18.2pp | **+2.5pp (악화)** |
| sbs1  | 20.8% | 66.7% | -3.6pp | **-2.4pp (개선)** |

### 채택 판정

**판정: ❌ 기각 (N=1 탐색 기준, 정식 N=3 불필요)**
- N=1이지만 Stage 1 단독 대비 bong1(+3.0pp)·ytn2(+2.5pp) 소폭 악화, sbs1만 소폭 개선.
- Stage 3의 1-스텝 지연은 latency 증가 + 코드 복잡도 추가 대비 WER 개선 없음.
- 우선순위 타겟(bong1·ytn2) 악화 방향이므로 Stage 1+2 단독이 더 나은 후보.
- **다음**: Stage 3 코드 제거 후 Stage 1+2 단독으로 N=3 공식 채택 측정(Exp-136).

**JSON**: 미저장 (N=1 탐색 모드)

---

## Exp-136 — lang-set ko,en Stage 1+2 공식 채택 측정 N=3 (2026-06-25)

**가설 (Exp-134 이어받기)**: N=1 탐색에서 bong1 -12.4pp, ytn2 -20.7pp 극적 개선 → N=3 정식 채택 판정.
**변경**: Stage 1(LanguageSetLogitFilter: `--lang-set ko,en`) + Stage 2(언어 전환 시 `pending_incomplete_tokens` 클리어). Stage 3(provisional buffer)는 N=1 탐색 후 기각하여 제거함.
**브랜치**: `feat/lang-set-mask` (uncommitted Stage 2 포함, `fb439b3` base)

### 테스트 설정

```
cd worktrees/lang-set-mask
python scripts/eval.py \
  --model-dir ".../whisper-large-v3-turbo" \
  --files ".../bong1.wav" ytn2.mp3 sbs1.mp3 \
  --diarization \
  --sortformer-model ".../sortformer-4spk-v2.nemo" \
  --compression-ratio-threshold 3.0 \
  --lan auto --lang-set ko,en --repeat 3 --paths C --expect-code-root .
```
provenance: `code=lang-set-mask, branch=feat/lang-set-mask@fb439b3, beams=2, CRT=3.0, PLC=None, diar=on, vbcable=ok`

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0, beams=2, PLC=None)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| bong1 | 59.2% | 55.0% | 54.1% | **55.0%** | **59.2%** | 2.7% | 55.6% | **+10.9pp ⚠️** | **+4.2pp ⚠️** |
| ytn2  | 37.9% | 46.8% | 47.8% | 46.8% | 47.8% | 5.4% | 52.2% | +2.5pp | **-13.8pp** ✓ |
| sbs1  | 22.6% | 20.8% | 19.6% | **20.8%** | 22.6% | 1.5% | 76.2% | **-3.6pp** ✓ | **-10.1pp** ✓ |

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 max: 55.0%→59.2% (+4.2pp) | ❌ **위반** |
| ② median 개선 | bong1: 44.1%→55.0% (+10.9pp); ytn2: 44.3%→46.8% (+2.5pp); sbs1: 24.4%→20.8% (-3.6pp) | ❌ **bong1·ytn2 회귀** |

**판정: ❌ 기각**
- **bong1 대폭 회귀**: median +10.9pp, max +4.2pp — 공동 1순위 타겟(bong1)에서 baseline보다 일관되게 나쁨 (N=3 전 회차 54~59%, baseline median 44.1%).
- **ytn2 소폭 악화**: median +2.5pp — N=1 탐색의 23.6% 대비 N=3 median 46.8% (baseline 44.3%보다도 나쁨).
- **sbs1 개선**: median -3.6pp, max -10.1pp, stdev 안정 — 단일화자 환경에서만 효과.

### 원인 분석

1. **N=1 탐색 이상치**: Exp-134 N=1에서 bong1 31.7%(baseline min 33.5% 아래)는 통계 이상치였음. 동일 설정 N=3에서 54~59% 일관 → 마스킹이 bong1에 체계적으로 해로움.
2. **bong1 마스킹 역효과**: bong1에는 웃음/비음성 구간이 많음(Exp-107 분석 참조). 무관 스크립트 토큰 억제 시 Whisper가 의미 없는 영어/한국어 토큰을 강제 출력 → 환각형 WER 증가.
3. **PLC 표기 오류 가능성**: Exp-134 provenance 'PLC=4.0(server default)'는 부정확 가능성. 서버 기본값은 `config.py` 기준 PLC=None — N=1과 N=3이 실제로는 동일 조건이었을 것.
4. **sbs1은 개선**: 단일화자 한국어에서는 non-Latin/Hangul 토큰 억제가 효과적 → 마스킹 자체의 아이디어는 유효하나 적용 대상 제한 필요.

### 이 결과가 시사하는 다음 방향

- lang-set 전역 마스킹은 bong1 유형(다화자+비음성 구간)에 부적합. 조건부 마스킹(언어 감지 후 해당 언어 스크립트만 허용, 비음성 구간은 비활성) 가능성 존재.
- **1순위 재탐색 방향**: 다화자 환경(bong1)에서 VBCable 분산 자체가 크므로 → diar 개선, no_speech_threshold 조정, 오디오 전처리 방향.
- `sbs1` 개선 데이터는 유효 — 단일화자 코드스위칭 환경에는 lang-set이 도움. 배포 환경 특성에 따라 선택적 활성화 옵션으로 보존 가능.

**JSON**: 미저장 (UnicodeEncodeError로 JSON 출력 실패했으나 수치 정상 수집)

---

## Exp-137 — frame_threshold=50 + PLC=4.0 (Phase 4 Spike 1) (2026-06-26)

**가설**: AlignAtt의 `frame_threshold`를 25→50으로 높이면 코드스위칭 경계에서 더 많은 미래 프레임을 확인 후 확정 → 잘못 확정한 단어 비율 감소 → ytn2(짧은 텀 코드스위칭) WER 개선. PLC=4.0(서버 default)와의 조합은 Exp-036·048 당시 PLC가 없어 시도되지 않은 신규 조합이다.

**배경**: 이 실험은 Phase 4 "늦은 확정(late-commit)" 개선 계획의 Phase A Spike 1 — 파라미터/소규모 변경으로 worst-case 게이트 통과 여부를 먼저 검증하는 저비용 탐색.

**변경**: eval.py harness에 `--frame-threshold` 플래그 추가(서버에 forwarding). 서버 코드 수정 없음.

| 파일 | 변경 내용 |
|------|----------|
| `worktrees/exp/spike1-frame-threshold/scripts/eval.py` | `--frame-threshold` 인자 추가; 서버 기동 시 `extra_server_args`에 전달; provenance에 `frame_threshold` 기록 |

**브랜치**: `exp/spike1-frame-threshold` (`7cb05f9` base)
**측정 cwd**: `worktrees/exp/spike1-frame-threshold`

### 테스트 설정

```powershell
$root = "C:\Users\A040-000-0001\Desktop\260605wlk\wlk"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir "$root\whisperlivekit\model\whisper-large-v3-turbo" `
  --files "$root\test_data\bong1.wav" "$root\test_data\ytn2.mp3" "$root\test_data\sbs1.mp3" `
  --diarization `
  --sortformer-model "$root\whisperlivekit\model\sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --frame-threshold 50 `
  --repeat 3 `
  --output "$wt\.omc\benchmarks\eval_exp137_ft50_$ts.json"
```
provenance: `code=spike1-frame-threshold, branch=exp/spike1-frame-threshold@7cb05f9, beams=2, CRT=3.0, PLC=None(eval.py 미전달→서버 parse_args.py default=4.0 적용), diar=on, vbcable=ok`

> **PLC 주의**: provenance의 `PLC=None`은 eval.py가 `--periodic-lang-check`를 서버에 전달하지 않았다는 뜻이며, 서버는 자체 `parse_args.py` default(4.0)를 사용했다. 실질 측정 조건은 **frame_threshold=50 + PLC=4.0**.

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0, beams=2, PLC=4.0[서버default])

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| bong1 | 36.0% | 67.1% | 32.6% | **36.0%** | **67.1%** | 19.0% | 25.0% | **-8.1pp** | **+12.1pp ⚠️** |
| ytn2  | 29.1% | 40.4% | 26.1% | **29.1%** | **40.4%** | 7.5% | 33.3% | **-15.2pp ✓** | **-21.2pp ✓** |
| sbs1  | 16.7% | 36.3% | 25.0% | 25.0% | 36.3% | 9.9% | 18.2% | +0.6pp | +3.6pp |

### 분석 (전사 내용 정성 대조)

**bong1** (R_median=R1=36.0% 기준):
- **단어 유실/대치**: 전사 `"저한테 아들 롬이"` / 정답 `"저 돌 들고 있는 저 아들놈이"` — `돌 들고 있는`이 통째 누락.
- **단어 대치**: 전사 `"보시셔서 안시겠지만"` / 정답 `"보셔서 아시겠지만"` — 음절 혼동.
- 비언어 토큰·환각 폭주 없음 (R_median 기준).

**bong1** (R_max=R2=67.1% — catastrophic 확인):
- **환각 폭주**: 전사 `"[구독] [좋아요] [구독] [구독] [구독] '구독' [구독] [구] []"` / 정답 `"So my son who is holding up the rock…"` — YouTube 구독/좋아요 메타 토큰 연쇄 환각. 웃음 구간에서 Whisper가 비음성 패턴을 YouTube 콘텐츠로 오인한 것으로 보임.
- **VBCable 이상 아님**: R1·R3는 160초 정상 완주 후 합리적 전사 → 오디오 수신 정상, 환각만 발생.

**ytn2** (R_median=R1=29.1% 기준):
- **코드스위칭 처리 양호**: 영어(`First among those were our efforts…`) → 한국어(`우선 왕성한 연합방위태세…`) 전환 인식 정상.
- **단어 대치**: 전사 `"경제하자는"` / 정답 `"경주하자는"`, 전사 `"취재에 논의를"` / 정답 `"취지의 논의를"` — 한국어 음절 혼동.

**sbs1** (R_median=R3=25.0% 기준):
- **고유명사 교정 오류 지속**: 전사 `"6군 전쟁 대학"` / 정답 `"육군 전쟁 대학"` — 기존부터 있는 숫자/한자 혼동.
- **단어 대치**: 전사 `"연구적인 지상 플랫폼"` / 정답 `"영구적인 지상 플랫폼"` — 음절 혼동.

**이번 변경 영향**: frame_threshold=50이 ytn2 코드스위칭 처리를 크게 개선(더 많은 컨텍스트 후 확정 → 전환점 오인식 감소). 그러나 bong1 웃음/비음성 구간에서 환각 시작 후 더 많은 토큰이 누적되어 확정 → R2 YouTube 환각 폭주 규모 증대. **파라미터 조정 단독으로 두 문제를 동시 해결하기 어려움이 명확해짐**.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 max: 55.0%→67.1% (+12.1pp) — YouTube 환각 폭주 원인 확인 | ❌ **위반** |
| ② median 개선 | ytn2 -15.2pp ✓ / bong1 -8.1pp ✓ / sbs1 +0.6pp ≈ | △ 혼합 (ytn2 극적) |

**판정: ❌ 기각**
- **bong1 max catastrophic**: 55.0%→67.1% (+12.1pp). 전사 분석으로 VBCable 불안정이 아닌 YouTube 환각 폭주(구독/좋아요 연쇄) 확인 → 1순위 기준(max 미회귀) 위반.
- **ytn2 극적 개선**: median -15.2pp, max -21.2pp — frame_threshold=50이 코드스위칭에 강력한 효과 확인. 단 bong1 max가 막음.
- **F1 전반 하락**: bong1 48.5%→25.0%, ytn2 55.6%→33.3% — 확정 지연으로 문장 분리 타이밍이 전반적으로 어긋남.

### 원인 분석

- **트레이드오프 구조**: frame_threshold↑은 코드스위칭 경계에서 인식 정확도↑(ytn2)이지만, 비음성/환각 구간에서 잘못된 토큰이 더 오래 누적된 후 한꺼번에 확정(bong1). 두 효과가 상반된 방향.
- **단일 파라미터의 한계**: bong1 worst-case를 잡으려면 환각 시작 시 조기 차단이 필요하지만, frame_threshold↓은 ytn2 코드스위칭을 다시 해침. 파라미터만으로는 동시 해결 불가.
- **frame_threshold=100 추가 시도 불필요**: 동일 방향이므로 bong1 환각 악화만 더 심해질 것. Spike 1 Arm 2 그리드에서 frame_threshold=100은 생략.

### 다음 가설

**Phase B Spike 2 — full-buffer 재디코딩 타당성 프로브(오프라인 마이크로벤치)**:
- Spike 1(싼 레버)이 bong1 max 게이트를 통과하지 못했으므로 Phase B로 이동.
- **2a** RTF 벤치: `WhisperASR.transcribe`를 large-v3-turbo·beam=2로 15/30/45s 고정 버퍼 단독 실행 → decode time → RTF.
- **2b** 동시 경합: 재디코딩 백그라운드 스레드 + live AlignAtt + Sortformer 동시 가동 → live RTF 증가분 + peak VRAM.
- **2c** 언어 누락: `language=auto`로 ytn2 한↔영 발췌 재디코딩 → 영어 recall 측정 (Exp-001 재현 여부).
- 게이트: 단독 RTF<0.5 + 동시 live 안정 + 언어 해결가능 → 2-pass 구축(분기 2). 불가 → AlignAtt 보강(분기 4, 사용자 보고).

**JSON**: `worktrees/exp/spike1-frame-threshold/.omc/benchmarks/eval_exp137_ft50_20260626_1114.json`

---

## Exp-138 — SimulStreaming non_speech_tokens 억제 추가 (`suppress_nonspeech=True`)

**날짜**: 2026-06-30
**브랜치**: `exp/meta-token-suppress` (SHA: 627f52f)

### 가설

표준 Whisper 디코더는 기본적으로 `non_speech_tokens`(음악 기호 ♪·괄호·대괄호·따옴표 기호·`--`·`---` 등 비음성 주석 기호)를 억제하지만, SimulStreaming(AlignAtt/CIF) 경로의 `_init_state()`는 이 목록을 적용하지 않고 있었다. Exp-137 bong1 max(67.1%)에서 `[구독][좋아요]` 같은 YouTube 메타 토큰 연쇄 환각이 관측됐으며, `[`·`]` 등 비음성 기호 토큰을 억제하면 bong1 worst-case를 개선할 수 있다는 가설.

### 변경 내용

| 파일 | 변경 |
|------|------|
| `whisperlivekit/simul_whisper/simul_whisper.py` (lines 104-116) | `_init_state()`의 suppress_tokens 목록에 `non_speech_tokens` 조건부 추가 |
| `whisperlivekit/simul_whisper/config.py` | `AlignAttConfig`에 `suppress_nonspeech: bool = True` 필드 추가 |
| `whisperlivekit/simul_whisper/backend.py` (~line 402) | `AlignAttConfig` 생성자 호출 시 `suppress_nonspeech` 전달 |
| `whisperlivekit/parse_args.py` (simulstreaming group) | `--suppress-nonspeech` / `--no-suppress-nonspeech` 플래그 추가 (default=True) |
| `whisperlivekit/config.py` | `WhisperLiveKitConfig`에 `suppress_nonspeech: bool = True` 필드 추가 |
| `whisperlivekit/core.py` (simulstreaming_params) | `"suppress_nonspeech": config.suppress_nonspeech` 전달 |

### 테스트 설정

```bash
# 테스트 세트 (bong1 / ytn2 / sbs1)
python scripts/eval.py `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --server-model-dir "c:/Users/A040-000-0001/Desktop/260605wlk/wlk/whisperlivekit/model/whisper-large-v3-turbo" `
  --diarization `
  --sortformer-model "c:/Users/A040-000-0001/Desktop/260605wlk/wlk/whisperlivekit/model/sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --repeat 3 `
  --output "worktrees/exp-meta-token-suppress/eval_exp138_test_r3.json"
```

provenance: `branch=exp/meta-token-suppress@627f52f, beams=2, CRT=3.0, PLC=None(eval.py 미전달→서버 PLC 버그로 실질 PLC=None), diar=on, vbcable=ok`

> **PLC 주의**: `periodic_lang_check_secs`는 `backend.py`의 `AlignAttConfig` 생성자에 전달되지 않는 버그가 있어 서버도 실질적으로 PLC=None으로 동작한다.

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0, beams=2, PLC=None)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| bong1 | 44.7% | 34.1% | 55.0% | **44.7%** | **55.0%** | 10.4% | 34.0% | **+0.6pp** | **0.0pp** |
| ytn2  | 34.0% | 20.2% | 49.8% | **34.0%** | **49.8%** | 14.8% | 58.3% | **-10.3pp ✓** | **-11.8pp ✓** |
| sbs1  | 19.6% | 26.2% | 20.2% | **20.2%** | **26.2%** | 3.6% | 18.2% | **-4.2pp ✓** | **-6.5pp ✓** |

베이스라인 (N=5, 2026-06-25): bong1 44.1%/55.0%, ytn2 44.3%/61.6%, sbs1 24.4%/32.7%

### 분석 (전사 내용 정성 대조)

**bong1** (R_median=R1=44.7% 기준):
- **환각 폭주 — 웃음 캐스케이드**: 전사 `"네하하하! 하하하! 하하하! 하하하! 하하! 하하하! 하하하, 하하하! ..."` 28회 이상 연속 / 정답: 해당 구간에 웃음 텍스트 없음. 웃음·박수 오디오 구간에서 `하하하` 텍스트 연쇄. `non_speech_tokens` 억제 후에도 **텍스트 형태 웃음(`하하하`)은 차단되지 않음** — 이 토큰은 일반 언어 어휘라 억제 대상이 아님.
- **음절 혼동**: 전사 `"멀ang 멀ang한 곧 도만들의 소리가"` / 정답 `"플라스틱 말랑말랑한 것도 만들었죠"` — 웃음 직후 구간에서 음절 혼동·환각 삽입.
- hyp_sentences=34 / ref_sentences=15 (over-segmented x2.3) → F1 34.0%

**bong1** (R_max=R3=55.0% — catastrophic 확인):
- **환각 폭주 — 일본어·중국어 캐스케이드**: 전사 `"Ha ha何もとんぐ いるんすでん えみわん"` (일본어) 이후 `"主委員工也沒有打仗 主委員工仗. 阿滋勒咪啊..."` → `"你一句話說的,他們是什麼東西,什麼東西都是說的..."` 수백 글자의 중국어 환각 폭주 / 정답: 정상 영어·한국어 대화.
- **가설 수정**: Exp-137 bong1 max(67.1%)에서 `[구독][좋아요]` 연쇄가 원인이라 추정했으나, Exp-138에서 `[`·`]` 억제 후에도 bong1 max=55.0% 유지 → **실제 bong1 worst-case 원인은 웃음·박수 구간 트리거 중국어·일본어 환각 캐스케이드**임이 새로 확인됨. 이 패턴은 억제 목록으로 해결 불가(중국어 자체는 정상 언어 토큰).

**ytn2** (R_median=R1=34.0% 기준):
- **코드스위칭 처리 양호**: 전사 `"where our efforts"` / 정답 `"were our efforts"` — 동음이의어 수준 미세 오류. 한↔영 전환 구간 전반은 정상.
- **단어 대치**: 전사 `"취재에 논의를"` / 정답 `"취지의 논의를"` — 음절 혼동. `"Ngu MBC 뉴스 우선입니다"` — 방송국 태그 형태 환각 삽입.

**ytn2** (R_max=R3=49.8% — 환각 캐스케이드 확인):
- **정중어 반복 환각**: 전사 `"고맙습니다. 고맙습니다. 고맙겠습니다. ..."` 10회 이상 + `"Thank you, Mr. Kim. Thank you, Mr. Lee. Thank you, Mr. Park..."` 연쇄 / 정답: 정상 대화. 무음·화자 전환 구간에서 bong1과 유사한 환각 트리거 패턴.

**sbs1** (R_median=R3=20.2% 기준):
- **환각 접두사**: 전사 `"JBR 브런스는 주한미군 사령관"` / 정답 `"제이비어 브런슨 주한미군 사령관"` — `JBR` 접두사 환각.
- **`. ` 아티팩트**: 전사 내 여러 위치에 `. ` 삽입 → hyp_sentences=11 / ref_sentences=3 (x3.7 over-segmented) → F1 16.7%.
- **단어 대치**: `"연구적인 지상 플랫폼"` / 정답 `"영구적인 지상 플랫폼"`, `"6군 전쟁 대학"` / `"육군 전쟁 대학"` — 기존부터 있는 숫자·한자 혼동.

**이번 변경 영향**:
- **ytn2 WER 개선**: baseline 44.3%→34.0% (-10.3pp), sbs1 24.4%→20.2% (-4.2pp). non_speech_tokens 억제가 일부 비정상 토큰을 차단했을 가능성 있으나 N=3 분산(ytn2 min 20.2%/max 49.8%)이 커 단정 불가.
- **bong1 max 미변화**: 이번 억제로 괄호·특수기호 토큰은 차단됐지만 bong1 max WER를 야기하는 **중국어·일본어 환각 캐스케이드는 억제 목록과 무관한 실패 모드**임 확인.
- **sbs1 F1 저하**: `. ` 아티팩트 기인 over-segmentation(hyp >> ref)이 F1을 낮게 유지시킴. 이 패턴 자체는 이번 변경과 직접 관계 불분명.

### held-out 결과 (N=3, diar-ON, CRT=3.0, beams=2)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | vs baseline Δmed | vs baseline Δmax |
|------|--------|--------|--------|--------|-----|-------|--------|-----------------|-----------------|
| ytn1 | 35.6% | 49.7% | 74.8% | **49.7%** | **74.8%** | 19.9% | 55.6% | **+20.3pp ❌** | **+25.7pp ❌** |
| eng1 | 86.7% | 83.8% | 41.0% | **83.8%** | **86.7%** | 25.6% | 100.0% | **+80.0pp ❌** | **+81.0pp ❌** |

베이스라인 held-out (N=5, 2026-06-25): ytn1 29.4%/49.1%, eng1 3.8%/5.7%

> **eng1 catastrophic + 분산 극심**: 위 terminal 회차(11:07)는 86.7/83.8/41.0%. 그러나 이후 덮어쓴 JSON(11:09)의 별도 eng1 3회차는 41.9%/**100.0%(빈 전사)**/**2.86%(거의 완벽)**로, 같은 설정에서 빈 전사·거의 완벽 회차가 공존한다. → eng1 결과는 **단일 회귀라기보다 측정 불안정 + 간헐 catastrophic**의 혼합. (2.86% 회차에 `"UK's"` 정상 출력 → 아래 근본원인 정정 참조.)

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 (테스트) | bong1 max 0pp / ytn2 max -11.8pp ✓ / sbs1 max -6.5pp ✓ | △ 테스트만 보면 통과 |
| ② median 개선 | ytn2 -10.3pp ✓ / sbs1 -4.2pp ✓ / bong1 +0.6pp 중립 | △ 혼합 (ytn2·sbs1 개선) |
| ③ held-out 회귀 없음 | eng1 median +80.0pp ❌ / ytn1 median +20.3pp ❌ | ❌ **치명적 위반** |

**판정: ❌ 기각** (held-out 회귀로 기각은 유지하되, 기각 사유의 **근본 원인 설명을 아래와 같이 정정**한다.)
- **eng1 회귀**: baseline 3.8% → 측정셋별 median 83.8%(11:07) / 41.9%(11:09). 간헐 catastrophic.
- **ytn1 회귀**: median +20.3pp, max +25.7pp. 코드스위칭 일반화 역행.

### 원인 분석 (정정 — 2026-06-30 워크플로 코드 조사)

> **⚠️ 최초 추정 철회**: 기각 직후 "`non_speech_tokens` 안의 `" '"`(공백+아포스트로피)가 `don't`/`it's` 축약형을 깬다"고 적었으나 **실측으로 반증됨**. 아래가 정정된 분석이다.

1. **아포스트로피 가설 반증 (실측)**: 워크트리 토크나이저로 직접 인코딩한 결과 영어 축약형은 `don't`→`[13966, 380]`, `it's`→`[270, 311]`, `they've`→`[13162, 600]`로 쪼개지며, 접미 토큰(`'t`=380, `'s`=311, `'ve`=600 등)은 **non_speech_tokens 82개 집합에 하나도 없다**(SUPPRESSED_HITS=[]). 집합 내에서 영어에 닿는 토큰은 359(`' -'`)·922(`" '"` 단어머리 아포스트로피)·따옴표뿐. 결정적 반례 둘: ① 표준 Whisper도 동일 집합을 기본(`suppress_tokens=-1`) 적용하지만 영어를 안 깬다(`whisper/decoding.py:617`). ② held-out JSON(11:09)에 suppress_nonspeech ON 상태에서 **eng1 2.86% 거의 완벽 회차**가 있고 그 전사에 `"UK's"`가 정상 출력됨.
2. **eng1 회귀의 진짜 원인 = 미규명**. 후보 둘: (a) non_speech_tokens 추가와 SimulStreaming 스트리밍 디코드(notimestamps + 스텝별 억제 `align_att_base.py:306`)의 상호작용, (b) 측정 불안정(eng1 회차가 빈 전사~2.86%~86.7%로 분산 극심). **suppress_nonspeech 채택/기각을 확정하려면 깨끗한 N≥3 재측정으로 이 둘을 분리**해야 한다.
3. **bong1 중국어·일본어 환각 메커니즘 (코드 규명)**: `--language auto`(기본값, `parse_args.py:127`·`config.py:45`)에서 SimulStreaming은 화자 세그먼트마다 `lang_id()`로 언어를 자동 감지해 그 언어로 고정한다(`align_att_base.py:178-204`, `_apply_detected_language` 143-151; 화자 전환 시 `backend.py:134-156`에서 1.5s 윈도우로 재감지). 웃음·박수 등 **비음성 구간이 감지 윈도우에 들어가면 언어 분류기가 중국어/일본어로 오감지** → 토크나이저가 그 언어로 재설정 → 이후 한자·히라가나 단어 토큰을 자유 생성한다. `suppress_tokens`의 `all_language_tokens`는 `<|zh|>` 같은 **언어 마커 special token만** 막을 뿐 한자 단어 토큰은 못 막는다. **ko/en 전용 제한은 현재 코드에 없다** — Exp-134/136에서 lang-set ko,en 로짓 마스킹을 시도했으나 기각·완전 제거됨.
4. **non_speech_tokens 억제의 실제 효과 = 환각 "제거"가 아닌 "형태 변경"**: Exp-137(억제 OFF)의 `[구독][LAUGHTER][NON-ENGLISH SPEECH][MUSIC PLAYING]` 대괄호 캐스케이드가, Exp-138(억제 ON)에선 같은 웃음 구간에서 `하하하` 연쇄·중국어 수백 글자로 대체됐다. 여는 괄호/대괄호 첫 토큰(`(`=7, `[`=58, `♪`=3961)은 -inf로 막혀 주석 시퀀스 진입이 차단되지만(=당신 관찰대로 `(laughter)`류는 사라짐), 환각의 빈도·구간·파괴력은 유지 → bong1 max 55.0%로 미해소.

### 다음 가설 (재설정 — 원래 Exp-139 "음악기호 전용 억제"안은 전제 붕괴로 폐기)

진짜 과제 둘로 분리. **major 방향 전환이므로 사용자 합의 후 진행**:
- **(A) worst-case 환각 캐스케이드 = 비음성 구간 언어 오감지**가 1차 동인(§3.8 worst-case 우선과 직결). 후보: ① 언어감지 신뢰도 임계 상향(현재 0.85)·비음성 구간 lang 재감지 게이팅, ② no_speech_threshold/VAD로 웃음·박수 구간을 전사에서 배제, ③ ko/en soft bias 재검토(Exp-136 hard 마스킹과 달리 약하게).
- **(B) suppress_nonspeech 자체 재평가**: 테스트셋 이득(ytn2 -10.3pp, sbs1 -4.2pp)이 실재하는지, eng1 회귀가 측정노이즈인지 **깨끗한 N≥3 재측정**(test+held-out)으로 분리. 실재 이득이고 eng1이 노이즈면 부분 채택 후보.

**JSON**: `worktrees/exp-meta-token-suppress/eval_exp138_test_r3.json` (timestamp 10:43) / `eval_exp138_heldout_r3.json` (held-out terminal 결과 기준 11:07; JSON 파일은 이후 덮어씌워짐)

---

## Exp-139 — 언어 불변식 잠금: Layer 1 후처리 필터 + Layer 2 lang_id 제한 (2026-06-30)

### 가설

배포 환경(§3.2)은 한국어·영어만 존재한다. 전사 출력에 나타나는 중국어/일본어(한자·가나) 세그먼트와
`(laughter)`·`[구독]`·`♪` 같은 비음성 주석은 WER/F1와 무관하게 **제품 정의상 오류**다.
결정론적 후처리(Layer 1) + 언어 감지 후보 제한(Layer 2)으로 이 두 가지를 보장한다.
WER 개선이 목적이 아니라 §3.2 불변식을 코드로 못박는 것이 목적이다.

### 변경 내용

| 파일 | 변경 |
|------|------|
| `whisperlivekit/filtering/__init__.py` | `filter_segments()` 내 `_CJK_KANA_RE`(한자+히라가나+가타카나) 세그먼트 드롭 + `_ANNOTATION_RE`(`(…)·[…]·♪`) 스팬 strip — always-on |
| `whisperlivekit/simul_whisper/simul_whisper.py:214-228` | `lang_id()` — `lang_restrict_koen=True` 시 {ko,en} 외 언어토큰 -inf 마스킹(Strategy B) |
| `whisperlivekit/simul_whisper/config.py:28-29` | `lang_restrict_koen: bool = True` 추가 |
| `whisperlivekit/config.py:70-71` | `lang_restrict_koen: bool = True` 추가 |
| `whisperlivekit/core.py:182-183` | simulstreaming_params에 `lang_restrict_koen` 전달 |
| `whisperlivekit/simul_whisper/backend.py:404` | `AlignAttConfig` 생성 시 `lang_restrict_koen` 전달 |
| `whisperlivekit/parse_args.py:382+` | `--lang-restrict-koen` `BooleanOptionalAction` default=True 추가 |
| `tests/test_filtering.py` | `TestFilterSegmentsInvariants` 11개 케이스 (한자드롭·가나드롭·주석strip·한영보존·임베디드) — 전체 29개 통과 |

커밋: `40e702b` (branch `exp/meta-token-suppress`)

### 테스트 설정 (스크리닝 N=1)

```powershell
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_20260630_1408.json"
```

beams=2, CRT=3.0, diar=ON, repeat=1(스크리닝), VBCable=ok

### 테스트 세트 결과 (N=1 스크리닝, 경로 C)

베이스라인 = master (Exp-105 diar-ON): bong1 44.1%, ytn2 44.3%, sbs1 24.4%

| 파일 | WER | Δ vs baseline | F1 |
|------|-----|--------------|-----|
| bong1 | 53.8% | **+9.7pp ❌** | 43.2% |
| ytn2 | 55.7% | **+11.4pp ❌** | 62.1% |
| sbs1 | 20.8% | **-3.6pp ✓** | 18.2% |
| **avg** | **43.4%** | **+5.8pp** | **41.2%** |

### 불변식 검증 (핵심 목표)

Python 검증 스크립트로 세 파일 전사 결과 전수 확인:
- **CJK/가나 문자 출현 횟수**: 0건 ✓ (Layer 1 필터 동작)
- **비음성 주석 스팬 출현 횟수**: 0건 ✓ (Layer 1 필터 동작)
- 한국어·영어 코드스위칭 정상 출력 확인 ✓

### 분석 (전사 내용 정성 대조)

**bong1** (N=1 단일 회차):
- **불변식 달성**: 한자·가나·`(laughter)` 0건. 이전 baseline에서 나오던 웃음 구간 CJK 환각 완전 소멸.
- **환각 대체 현상**: 웃음 구간에서 `"Malang Malang ng kotomantra suri ng anzadaan sofomorumulun"` — CJK 대신 라틴 문자 환각으로 대체. lang_restrict_koen이 CJK 언어 토큰을 막았으나, 비음성 구간에서 모델이 라틴 스크립트 형태의 쓰레기를 생성(Exp-136과 구조 동일 — 형태만 변경).
- **후미 반복 환각**: `"고맙습니다"` 7회 연속 — 비음성(박수·정리) 구간에서 의례적 문구 생성.

**ytn2** (N=1 단일 회차):
- **불변식 달성**: 한자·주석 0건.
- **환각 삽입**: `"Ngu MBC 뉴스 이재연"` (정답 없음), `"These are the goals to achieve the best we can..."` (정답 없음) — 비음성 전환 구간에서 영어 환각 생성.
- **가장 심한 환각**: `"Uh, you are going to go on a. date with me? Uh, uh, you're going to go on a dating date?..."` 5회 반복 — 무음 구간에서 영어 환각 캐스케이드 발생. WER +11.4pp의 주원인.
- **코드스위칭 정상 구간**: `"최종적 그리고 완전히 검증된 비핵화"` / `"전작권 전환"` 한·영 혼용 정상 처리.

**sbs1** (N=1 단일 회차):
- **불변식 달성**: 한자·주석 0건 (원래 없음).
- **WER 개선**: baseline 24.4% → 20.8% (-3.6pp). lang_restrict_koen이 불필요한 언어 후보를 제거해 한국어 집중도 향상 추정.
- **기존 단어 대치**: `"6군"→"육군"`, `"연구적인"→"영구적인"`, `"공군역"→"공군력"` — 기존부터 있는 Whisper 한계.

**이번 변경 영향**: CJK·주석 불변식은 완전 달성. 그러나 bong1/ytn2 비음성 구간에서 Exp-136과 동일한 구조적 문제 재현 — 한자 토큰을 막으면 모델이 라틴 문자 환각으로 대체. WER 개선은 Layer 1·2만으로는 불가능하며, 비음성 구간 자체를 전사에서 배제하는 Layer 3b(VAD/no_speech_threshold)가 필요함.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| 불변식 달성 | CJK/주석 0건 | ✓ **완전 달성** |
| ① max WER 미회귀 (테스트) | bong1 +9.7pp ❌ / ytn2 +11.4pp ❌ / sbs1 -3.6pp ✓ | ❌ 회귀 |
| ② median 개선 | (N=1, 방향 신호만) | — 판정 보류 |

**판정: ⚠️ hold — 목표 필수 기능 예외(§3.2 직결) 적용**
- §3.2 불변 제약(한/영 전용) 달성에 필요한 기반 기능 → WER 게이트만으로 자율 기각 금지.
- WER 회귀 원인 = 비음성 구간 환각 대체(Exp-136과 동일 구조). Layer 1·2만으로는 해소 불가.
- **master 머지 hold** → Layer 3b(Exp-140) 해결 후 함께 채택 평가.

### 다음 가설 (Exp-140)

**Layer 3b — no_speech_threshold 또는 VAD 강화로 비음성 구간 전사 자체를 스킵**:
웃음·박수·무음 구간이 전사 파이프라인에 진입하지 않으면 환각 대체 현상도 원천 차단된다.
후보:
1. `no_speech_threshold` 인자 조정 (현재 미설정 → 명시적으로 낮춰 비음성 감도 높임)
2. `vad_filter` 또는 기존 VAC(Voice Activity Controller) 파라미터 조정으로 비음성 구간 제거 강화

**JSON**: `worktrees/exp-meta-token-suppress/.omc/benchmarks/eval_20260630_1408.json`
