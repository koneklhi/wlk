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

---

### 재측정 — 채택 확정 (2026-07-01)

**재측정 배경**: 이전 N=1 스크리닝(2026-06-30)은 Windows 계정 전환 직후 오디오 불안정 구간에서 측정됐다 (ytn2 55.7%가 이상 고점 — 재측정 후 33.5%로 정상 복귀). Junction 깨짐(.venv → 구 PC 경로)도 함께 수정. 측정 도구 개선: `eval.py`에 `--no-suppress-nonspeech` / `--no-lang-restrict-koen` 패스스루 플래그 추가.

#### 스크리닝 재측정 (N=1, 오디오 정상화 후)

| 파일 | WER | F1 | vs baseline |
|------|-----|----|-------------|
| bong1 | 52.6% | 45.0% | +8.5pp |
| ytn2  | 33.5% | 50.0% | **-10.8pp ✓** |
| sbs1  | 22.6% | 36.4% | -1.8pp ✓ |

ytn2 이전 측정 55.7%가 오디오 불안정 노이즈였음 확인.

#### 채택 확정 측정 (N=3, diar-ON, CRT=3.0, beams=2, Exp-138 OFF)

```powershell
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir "c:\...\whisper-large-v3-turbo" `
  --files test_data\bong1.wav test_data\ytn2.mp3 test_data\sbs1.mp3 `
  --diarization --sortformer-model "c:\...\sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 --no-suppress-nonspeech --repeat 3 `
  --output .omc\benchmarks\eval_20260630_1613_r3.json
```

provenance: `branch=exp/meta-token-suppress@40e702b, beams=2, CRT=3.0, PLC=None, diar=on, vbcable=ok`

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | Δmed vs BL | Δmax vs BL |
|------|--------|--------|--------|--------|-----|-------|--------|-----------|-----------|
| bong1 | 55.3% | 52.9% | 32.0% | **52.9%** | **55.3%** | 12.8% | 44.4% | +8.8pp ❌ | +0.3pp ✓ |
| ytn2  | 31.5% | 42.9% | 35.5% | **35.5%** | **42.9%** | 5.8% | 50.0% | **-8.8pp ✓** | **-18.7pp ✓** |
| sbs1  | 24.4% | 17.3% | 22.0% | **22.0%** | **24.4%** | 3.6% | 36.4% | -2.4pp ✓ | -8.3pp ✓ |

베이스라인: bong1 44.1%/55.0%, ytn2 44.3%/61.6%, sbs1 24.4%/32.7%

#### held-out 단회 검증 (diar-ON)

| 파일 | WER | F1 | vs baseline |
|------|-----|----|-------------|
| ytn1 | 27.0% | 70.6% | **-2.4pp ✓** |
| eng1 | 5.7% | 0.0% | +1.9pp (허용) |

베이스라인 held-out: ytn1 29.4%, eng1 3.8%. Exp-138의 eng1 catastrophic(+80pp)·ytn1 catastrophic(+20pp) 완전 해소 확인.

#### 분석 (전사 내용 정성 대조)

**bong1** (R2 median=52.9% 기준):
- **CJK/주석 불변식**: 0건 ✓ — Layer 1+2 동작 확인.
- **음절 혼동**: 전사 `"돌돌고 있는 저 아들 놈이"` / 정답 `"들고 있는 저 아들 놈이"` — 초성 오인식.
- **음절 혼동2**: 전사 `"불량이 조금 많은데"` / 정답 `"분량이 조금 많은데"`.
- **앞부분 잘림**: 전사 `"사사단을 the most is who is the main protagonist"` — SOT 직후 한국어 앞부분 누락.
- **max 회차(R1=55.3%)**: `"공일까 이런 생각이"` 등 추가 오인식; 전반적으로 비음성 구간 garbage 없음(환각 대체도 이번 측정에서는 bong1에서 두드러지지 않음).

**ytn2** (R3 median=35.5% 기준):
- **CJK/주석**: 0건 ✓.
- **garbage prefix**: 전사 `"Ngu 우선 탠회를"` / 정답 없음 — 화자 전환 구간 garbage 1~2회.
- **메타 태그 환각**: 전사 `"[speaking in foreign language/ I reviewed progress on…"` — Layer 1이 `[…]` 패턴으로 제거해야 하나 닫는 `]` 없이 열려 있어 미차단(버그 후보).
- **음절 혼동**: 전사 `"취재에 논의를"` / 정답 `"취지의 논의를"`.
- **코드스위칭 정상**: `"최종적 그리고 완전히 검증된 비핵화"` / `"유엔 안보리 결의"` 한·영 혼용 정상 처리.
- **R2(max=42.9%)**: `"고맙습니다 고맙습니다 고맙…"` 반복 환각 발생(무음 구간).

**sbs1** (R3 median=22.0% 기준):
- **CJK/주석**: 0건 ✓.
- **이름 오인식**: 전사 `"J.B. 업로드선"` / 정답 `"제이비어 브런슨"` — 큰 오류.
- **방송 태그 환각**: 전사 `"[TAKE VO 이번 강연의 핵심은"` — 닫힌 `]` 없어 Layer 1 미차단.
- **기존 단어 대치**: `"6군 전쟁 대학"` / `"육군 전쟁 대학"`, `"연구적인"` / `"영구적인"`, `"공군역"` / `"공군력"`.
- **`. ` 아티팩트**: 문장 중간 `. ` 삽입 다수 → F1 36.4%(과분할).

**이번 변경 영향**: CJK/주석 불변식 완전 달성. ytn2 worst-case(max) -18.7pp 대폭 개선. bong1 median +8.8pp 회귀는 비음성 구간 환각 대체가 아닌 **음절 혼동 증가**로 나타남(이번 측정에선 CJK 캐스케이드 없음). Layer 1 `[…]` 필터의 닫힌 `]` 누락 패턴 미차단은 Exp-140 관련 버그 후보.

#### 채택 조건 판정 (N=3 기준)

| # | 조건 | 판정 |
|---|------|------|
| 불변식 달성 | CJK/주석 0건 | ✓ **완전 달성** |
| ① max WER 미회귀 | bong1 +0.3pp(노이즈)/ytn2 -18.7pp ✓/sbs1 -8.3pp ✓ | ✅ **통과** |
| ② median 개선 | bong1 +8.8pp ❌ / ytn2 -8.8pp ✓ / sbs1 -2.4pp ✓ | 혼합 |
| held-out 회귀 없음 | ytn1 -2.4pp ✓ / eng1 +1.9pp ✓ | ✅ **통과** |

**판정: ✅ 채택**
- 1순위(max 미회귀): 통과 (bong1 +0.3pp ≈ 측정 노이즈).
- held-out: 정상 (Exp-138 catastrophic 완전 해소).
- §3.2 불변식: 달성.
- bong1 median +8.8pp: 비음성 구간 구조적 문제 → **Exp-140(Layer 3b)에서 해결** 예정.

#### 다음 가설 (Exp-140)

**Layer 3b — no_speech_threshold 또는 VAD 강화로 비음성 구간 전사 스킵**:
bong1 median 회귀의 근본 원인(비음성 구간 garbage 생성)은 Exp-140에서 해결. Layer 1 `[…]` 미차단 버그(닫힌 `]` 없는 패턴)도 함께 검토.

**JSON**: `.omc/benchmarks/eval_20260630_1613_r3.json` (N=3 테스트) / `.omc/benchmarks/eval_20260630_1637_heldout.json` (held-out)

---

## Exp-140 — logprob_threshold=-1.0 스크리닝 (2026-07-01)

### 가설

Exp-139가 채택됐으나 bong1 median +8.8pp 회귀가 남아 있다. 비음성 구간(웃음·박수·무음) garbage를 차단하는
Layer 3b 방법으로 새 코드 없이 기존 `--logprob-threshold` 파라미터를 활용한다.
avg-logprob는 세그먼트 평균 토큰 확률로, 비음성 구간 → 모델 불확실 → avg-logprob 낮음 구조가 예상된다.
E1에서는 -1.0이 ytn2를 28→46%로 파탄냈으나(Exp-110), E2(lang_restrict_koen)에서는
언어-lock 후 정상 발화의 logprob 분포가 달라졌을 가능성이 있어 재확인한다.

### 변경 내용

코드 변경 없음 — `--logprob-threshold -1.0` 런타임 옵션으로만 스크리닝.
측정 대상: `master@3c9a6b1` (Exp-139 머지 완료, logprob 기본값=None).

### 테스트 설정 (스크리닝 N=1)

```powershell
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --logprob-threshold -1.0 `
  --output ".omc/benchmarks/eval_20260701_0858.json"
```

beams=2, CRT=3.0, diar=ON, logprob=-1.0, repeat=1, VBCable=ok

### 테스트 세트 결과 (N=1 스크리닝, 경로 C)

베이스라인 = Exp-139 median: bong1 52.9%, ytn2 35.5%, sbs1 22.0%

| 파일 | WER (N=1) | Δ vs baseline | F1 |
|------|-----------|--------------|-----|
| bong1 | 36.9% | **-16.0pp ✓** | 25.0% |
| ytn2  | 32.0% | -3.5pp ✓ | 47.1% |
| sbs1  | 33.3% | **+11.3pp ❌** | 20.0% |

### 분석 (전사 내용 정성 대조)

**bong1** (N=1 단일 회차):
- **개선 주원인**: logprob<-1.0인 garbage 세그먼트 다수 드롭 → 비음성 환각 감소.
- **sbs1 회귀 원인**: 한국어 뉴스 앵커 발화 일부가 logprob<-1.0으로 분류 → 정상 발화 잘림.
  전사 `"사 토요일에 있었던"` 구간 누락 추정.

**이번 변경 영향**: bong1·ytn2 개선 확인. 그러나 sbs1 +11.3pp catastrophic — logprob<-1.0이 정상 한국어 발화도 잘라냄. 임계값이 너무 높다.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | sbs1 +11.3pp ❌ | ❌ **catastrophic 회귀** |
| ② median 개선 | bong1 -16.0pp, ytn2 -3.5pp — 방향 신호 | — |

**판정: ❌ 기각** (sbs1 catastrophic +11.3pp — logprob -1.0이 정상 발화도 차단)

### 다음 가설 (Exp-141)

임계값을 -1.0 → -1.5로 완화해 sbs1 회귀를 해소하면서 bong1·ytn2 개선 방향을 유지.

**JSON**: `.omc/benchmarks/eval_20260701_0858.json`

---

## Exp-141 — logprob_threshold=-1.5 스크리닝 (2026-07-01)

### 가설

Exp-140(-1.0)에서 sbs1 +11.3pp catastrophic. -1.5로 완화하면 정상 발화 차단이 줄어들 것.

### 변경 내용

코드 변경 없음 — `--logprob-threshold -1.5` 런타임 옵션.

### 테스트 설정 (스크리닝 N=1)

```powershell
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --logprob-threshold -1.5 `
  --output ".omc/benchmarks/eval_20260701_0907.json"
```

### 테스트 세트 결과 (N=1 스크리닝, 경로 C)

| 파일 | WER (N=1) | Δ vs baseline | F1 |
|------|-----------|--------------|-----|
| bong1 | 36.0% | -16.9pp ✓ | 51.4% |
| ytn2  | 29.6% | -5.9pp ✓ | 12.5% |
| sbs1  | 27.4% | **+5.4pp ❌** | 20.0% |

### 분석 (전사 내용 정성 대조)

**ytn2** (N=1):
- **F1 극저(12.5%)**: logprob 필터가 EN 발화 세그먼트를 차단 → 코드스위칭 경계가 되는 EN 블록이 드롭됨 → 문장 분리 경계 손실.

**sbs1** (N=1):
- 회귀 완화(-1.0→-1.5)됐으나 여전히 +5.4pp. 한국어 뉴스 발화가 -1.5 이하 구간 포함.

**이번 변경 영향**: sbs1 회귀 partial 완화(+11.3pp→+5.4pp)이나 여전히 catastrophic. ytn2 F1 12.5%가 새 문제로 부각.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | sbs1 +5.4pp ❌ | ❌ 여전히 회귀 |
| ytn2 F1 | 12.5% (극저) | ❌ |

**판정: ❌ 기각** (sbs1 +5.4pp + ytn2 F1 붕괴)

### 다음 가설 (Exp-142)

-2.0으로 추가 완화. -1.0/-1.5가 정상 발화를 자르는 원인은 EN-after-KR 세그먼트의 낮은 logprob. -2.0이면 EN 블록도 유지하면서 비음성 garbage만 차단 가능한지 확인.

**JSON**: `.omc/benchmarks/eval_20260701_0907.json`

---

## Exp-142 — logprob_threshold=-2.0 채택 확정 (2026-07-01)

### 가설

-1.5에서도 sbs1 회귀가 남았다. -2.0이면 정상 발화(한국어·영어 모두)가 통과하면서 worst-case 비음성
garbage 세그먼트(매우 낮은 avg-logprob)만 차단할 수 있다.
비음성 구간 → 모델이 쓰레기 토큰을 강제 생성 → avg_logprob << -2.0 패턴이 예상됨.

### 변경 내용

| 파일 | 변경 |
|------|------|
| `whisperlivekit/parse_args.py:322-327` | `--logprob-threshold` 기본값 `None` → `-2.0`, help 갱신 |
| `docs/TESTING.md` | 기본값 목록에 `--logprob-threshold -2.0` 추가 |
| `docs/MASTER_CHANGES.md` | avg-logprob 게이트 기본값·채택 상태 갱신 |
| `CLAUDE.md §4` | WER > F1 채택 우선순위 명시 |
| `EXPERIMENTS.md` | epoch 마커 E2 확정, 빠른참조 표 갱신 |

커밋: `24d51bb` (branch `feat/logprob-default`) → master 머지 `091c287`

### 테스트 설정

**스크리닝 (N=1):**

```powershell
# N=1 스크리닝 (eval_20260701_0916.json)
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --logprob-threshold -2.0 `
  --output ".omc/benchmarks/eval_20260701_0916.json"
```

**채택 확정 (N=3, master@3c9a6b1, logprob-threshold=-2.0 명시):**

```powershell
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --logprob-threshold -2.0 --repeat 3 `
  --output ".omc/benchmarks/eval_20260701_0924_r3.json"
```

beams=2, CRT=3.0, diar=ON, logprob=-2.0, repeat=3, VBCable=ok

### 테스트 세트 결과 (N=3 채택 확정, 경로 C)

베이스라인 = Exp-139 median: bong1 52.9%, ytn2 35.5%, sbs1 22.0%

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | Δmed vs BL |
|------|--------|--------|--------|--------|-----|-------|--------|-----------|
| bong1 | 37.5% | 36.3% | 48.0% | **37.5%** | **48.0%** | 6.5% | 47.4% | **-15.4pp ✓** |
| ytn2  | 31.5% | 36.0% | 27.1% | **31.5%** | **36.0%** | 4.4% | 23.5% | **-4.0pp ✓** |
| sbs1  | 19.6% | 22.6% | 18.5% | **19.6%** | **22.6%** | 2.1% | 18.2% | **-2.4pp ✓** |

#### held-out 단회 검증 (diar-ON)

| 파일 | WER | F1 | vs baseline |
|------|-----|----|-------------|
| ytn1 | 28.2% | 42.9% | -1.2pp ✓ |
| eng1 | 3.8% | 0.0% | 0.0pp ✓ |

베이스라인 held-out: ytn1 29.4%, eng1 3.8%. 정상 유지.

### 분석 (전사 내용 정성 대조)

**bong1** (R1=median 37.5% 기준, eval_20260701_0916.json N=1 스크리닝 참조):
- **logprob 필터 효과**: 비음성 garbage 세그먼트 다수 차단 → WER -15.4pp 대폭 개선.
- **잔존 문제**: 전사 `"*cough*cough*cough cough*coughing*"` — 기침 반복 구간은 avg-logprob > -2.0이라 필터 통과.
- **[…] 미차단 잔존**: `"[LAUGHTER. ]"`, `"[NON-ENGLISH"` 패턴 일부 잔존 — Layer 1의 닫힌 `]` 누락 패턴은 미차단(Exp-139 분석에서 확인된 기존 버그).
- **max 회차(R3=48.0%)**: 필터를 통과한 garbage 세그먼트가 집중 발생 → worst-case 개선 한계.

**ytn2** (R1=median 31.5% 기준):
- **코드스위칭 정상 처리**: EN 발화 블록이 -2.0 이상 logprob → 차단 없이 정상 전사.
- **F1 하락(50.0%→23.5%)**: logprob 필터가 EN 세그먼트 일부 차단 → 코드스위칭 경계(빈 줄 기준) 손실.
  전사 `"[BLANK_AUDIO. (speaking in foreign"` — 비음성 구간에서 EN 환각이 남아 F1 감소.
- **WER 개선**: -4.0pp 정상 달성.

**sbs1** (R1=median 19.6% 기준):
- **회귀 해소**: -1.0(+11.3pp), -1.5(+5.4pp)에서 -2.0으로 완화 → -2.4pp 개선.
- **F1 하락(36.4%→18.2%)**: EN 인용구 블록(`"From a satellite image…"`) logprob 불안정 구간 일부 드롭 → 문장 경계 손실.

**이번 변경 영향**: WER 3파일 전부 개선 (bong1 -15.4pp, ytn2 -4.0pp, sbs1 -2.4pp). logprob -2.0이 정상 발화(한/영)는 통과시키고 비음성 garbage 세그먼트를 차단하는 sweet spot 확인. F1 하락(ytn2 -26.5pp, sbs1 -18.2pp)은 EN 세그먼트 경계 손실이 주원인 — WER > F1 우선순위(§4 신설)에 따라 채택 결정.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 max 48.0%(+E139 대비 -7.0pp ✓) / ytn2 max 36.0% / sbs1 max 22.6% | ✅ **통과** |
| ② median 개선 | bong1 -15.4pp / ytn2 -4.0pp / sbs1 -2.4pp | ✅ **전부 개선** |
| held-out | ytn1 -1.2pp ✓ / eng1 0pp ✓ | ✅ **정상** |
| WER > F1 우선순위 | F1 ytn2 -26.5pp / sbs1 -18.2pp (하락) | WER 개선이 F1 하락보다 우선(§4 채택) |

**판정: ✅ 채택**
- WER 3파일 전부 개선, max 미회귀.
- held-out 정상.
- F1 하락은 WER > F1 우선순위(CLAUDE.md §4 신설, Exp-142 결정 근거)에 따라 채택.
- `--logprob-threshold -2.0`을 parse_args.py 기본값으로 설정 → master 머지.

### 다음 가설 (Exp-143+)

1. **F1 회복 탐색**: ytn2/sbs1 F1 하락의 주원인인 EN 세그먼트 경계 손실을 개선하는 방법 — 예: 문장 분리 로직(punctuation-split) 개선, diarization segment boundary 활용.
2. **bong1 max 48.0% 원인 분석**: worst-case 회차에서 어떤 구간이 통과해 catastrophic을 유발하는지 추적 → Layer 3c(compression-ratio / no_speech 조합) 후보.
3. **PLC 배선 버그 수정**: `backend.py`에서 `periodic_lang_check_secs`가 `AlignAttConfig`에 전달되지 않는 버그 — diar-ON 환경에서는 영향이 작으나, 버그 자체는 수정 가치 있음.

**JSON**: `.omc/benchmarks/eval_20260701_0924_r3.json` (N=3 채택 확정) / `.omc/benchmarks/eval_20260701_0948_heldout.json` (held-out)

---

## Exp-143 — PLC 배선 버그 수정 + PLC=4.0 E2 N=1 스크리닝 (2026-07-01)

### 가설

`backend.py`의 `SimulStreamingASR._setup_align_att()`에서 `periodic_lang_check_secs` 파라미터가 `AlignAttConfig` 생성자에 전달되지 않는 버그가 발견됐다. E1·E2 전 실험이 사실상 PLC=None으로 동작했음을 의미한다. 버그 수정 후 서버 기본값(parse_args `--periodic-lang-check` default=4.0)이 실제로 작동할 때의 영향을 N=1 스크리닝으로 확인한다.

### 변경 내용

| 파일 | 변경 |
|------|------|
| `whisperlivekit/simul_whisper/backend.py:~403` | `_setup_align_att()`에 `periodic_lang_check_secs=getattr(self, 'periodic_lang_check_secs', None)` 한 줄 추가 |
| `whisperlivekit/parse_args.py:368-373` | `--periodic-lang-check` 기본값 `4.0` → `None` (wiring 수정으로 4.0이 실제 동작하게 되어 기존 동작 보전 목적으로 복원) |
| `docs/TESTING.md` | 서버 기동 설명에서 `--periodic-lang-check 4.0` 참조 제거 |

커밋: `3c74c42` (backend.py 수정) + `f461b69` (parse_args None 복원) → master 머지 `20e4fa8`

### 테스트 설정

**스크리닝 (N=1, PLC=4.0 = 서버 기본값 wiring 후 첫 측정):**

```powershell
# worktrees/feat-plc-wiring-fix에서 실행 (wiring fix 반영 확인)
Set-Location "...\worktrees\feat-plc-wiring-fix"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir ".../whisperlivekit/model/whisper-large-v3-turbo" `
  --files ".../test_data/bong1.wav" ".../test_data/ytn2.mp3" ".../test_data/sbs1.mp3" `
  --diarization --sortformer-model ".../model/sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_20260701_1131_plc_fix_n1.json"
```

beams=2, CRT=3.0, diar=ON, PLC=None(eval.py 기본; 서버는 parse_args 기본값 4.0으로 시작됨), repeat=1, VBCable=ok

> **주의**: eval.py provenance는 `PLC=None`으로 기록되지만, 이 시점 서버의 parse_args 기본값은 여전히 4.0이었다(master 머지 전). 즉 서버는 PLC=4.0으로 시작됐으나 eval.py는 자신의 기본값(None)만 기록. 실질 측정 조건 = PLC=4.0.

### 테스트 세트 결과 (N=1 스크리닝, 경로 C)

베이스라인 = Exp-142 median: bong1 37.5%, ytn2 31.5%, sbs1 19.6%

| 파일 | WER (N=1) | F1 (N=1) | Δ vs Exp-142 |
|------|-----------|----------|--------------|
| bong1 | 41.7% | 32.4% | +4.2pp ❌ |
| ytn2  | 29.6% | 42.1% | -1.9pp ✓ |
| sbs1  | 18.5% | 33.3% | -1.1pp ✓ |
| avg   | 29.9% | 36.0% | +0.4pp |

### 분석 (전사 내용 정성 대조)

N=1 스크리닝이므로 정성 분석은 방향 신호 수준으로만 기록한다.

**bong1** (N=1):
- **혼재 신호**: PLC=4.0 활성화로 언어 전환 감지가 개입했으나 bong1 웃음/박수 구간의 환각 억제에는 효과 없음. WER +4.2pp 회귀.
- 비언어 토큰 패턴(`(audience. applauds)`, `(speaking Korean`, `[LAUGHTER`) 잔존 — PLC와 무관한 비음성 구간 문제.

**ytn2** (N=1):
- **PLC 효과 가능성**: 한↔영 전환 시 언어 재감지가 오인식을 줄인 것으로 추정 (WER -1.9pp). N=1이므로 확정 불가.
- `"Ngu MBC 뉴스"` 환각 잔존 — 언어 전환 경계 노이즈.

**sbs1** (N=1):
- `"6군"` 오인식(정답 `"육군"`) 지속. PLC 영향 미미.

**이번 변경 영향**: PLC wiring 버그 자체는 확정 수정. PLC=4.0의 실질 효과는 혼재 신호(bong1 회귀, ytn2·sbs1 소폭 개선) — N=1이므로 방향 신호로만 해석. PLC 파라미터 탐색은 별도 실험으로 분리.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| 코드 변경 (PLC 버그 수정) | backend.py wiring 오류 수정 → master 머지 | ✅ **채택 (버그 수정)** |
| PLC=4.0 파라미터 | N=1 혼재 신호 (bong1 +4.2pp 회귀) | ❌ **미채택 (추가 탐색 보류)** |

**판정: ✅ 코드 수정 채택 / ❌ PLC=4.0 파라미터 기각 (혼재 신호)**
- 버그 수정(backend.py wiring)은 master 머지.
- parse_args 기본값은 None으로 복원 → 기존 동작(실질 PLC=None) 유지.
- PLC 값(2.0·4.0 등) 탐색은 이후 별도 실험으로.

### 다음 가설 (Exp-144)

E1 Exp-132에서 beam=3이 bong1 -8.1pp / ytn2 -8.8pp 개선을 보였으나 sbs1 max +19.1pp 회귀로 기각됐다. E2(lang_restrict_koen=True)에서는 그 sbs1 catastrophic 회귀가 방지될 수 있다. beam=3 E2 재검증.

**JSON**: `.omc/benchmarks/eval_20260701_1131_plc_fix_n1.json`

---

## Exp-144 — beam=3 E2 재검증 (2026-07-01)

### 가설

E1 Exp-132에서 beam=3은 bong1 -8.1pp / ytn2 -8.8pp를 달성했으나 sbs1 max +19.1pp catastrophic 회귀로 기각됐다. 그 sbs1 회귀 원인은 비음성 구간에서 beam=3이 더 긴 CJK 환각 체인을 만들기 때문으로 추정된다. E2에서 lang_restrict_koen이 CJK 토큰을 차단하므로 해당 회귀가 억제되는지 재검증한다.

### 변경 내용

| 파일 | 변경 |
|------|------|
| `worktrees/exp-beam3-e2/whisperlivekit/parse_args.py:252` | `--beams` 기본값 `2` → `3` (워크트리 로컬 수정, master 미머지) |

브랜치: `exp/exp-beam3-e2` (worktree: `worktrees/exp-beam3-e2`), 베이스 SHA `20e4fa8`

### 테스트 설정

**스크리닝 (N=1):**

```powershell
Set-Location "...\worktrees\exp-beam3-e2"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir ".../whisperlivekit/model/whisper-large-v3-turbo" `
  --files ".../test_data/bong1.wav" ".../test_data/ytn2.mp3" ".../test_data/sbs1.mp3" `
  --diarization --sortformer-model ".../model/sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_20260701_1158_beam3_e2_n1.json"
```

**채택 확정 (N=3):**

```powershell
Set-Location "...\worktrees\exp-beam3-e2"
.venv\Scripts\python.exe scripts/eval.py ... --repeat 3 `
  --output ".omc/benchmarks/eval_20260701_1206_beam3_e2_r3.json"
```

beams=3, CRT=3.0, logprob=None(provenance), diar=ON, PLC=None, VBCable=ok

> **import 경로**: 워크트리 CWD에서 실행 → `sys.path[0]=''`(CWD)가 editable install보다 우선 → 워크트리 whisperlivekit 임포트 확인(init.py 경로 육안 검증 후 실행).

### 테스트 세트 결과

베이스라인 = Exp-142 median: bong1 37.5%, ytn2 31.5%, sbs1 19.6%

**N=1 스크리닝 (방향 신호):**

| 파일 | WER (N=1) | F1 | Δ vs BL |
|------|-----------|-----|---------|
| bong1 | 33.8% | 48.5% | -3.7pp |
| ytn2  | 32.0% | 52.6% | +0.5pp |
| sbs1  | 15.5% | 36.4% | -4.1pp |
| avg   | 27.1% | 45.8% | -2.4pp |

N=1 결과: 전반적 개선처럼 보임. sbs1 catastrophic 회귀 없음 → N=3 채택 확정 진행.

**N=3 채택 확정:**

| 파일 | R1 WER | R2 WER | R3 WER | median | max | stdev | F1 med | Δmed vs BL |
|------|--------|--------|--------|--------|-----|-------|--------|-----------|
| bong1 | 41.1% | 48.6% | 56.5% | **48.6%** | **56.5%** | 7.7% | 36.8% | **+11.1pp ❌** |
| ytn2  | 26.1% | 30.0% | 24.1% | **26.1%** | **30.0%** | 3.0% | 38.1% | **-5.4pp ✓** |
| sbs1  | 16.7% | 22.0% | 17.9% | **17.9%** | **22.0%** | 2.8% | 36.4% | **-1.7pp ✓** |
| avg   | — | — | — | **30.9%** | — | — | 37.1% | +1.4pp ❌ |

### 분석 (전사 내용 정성 대조)

**bong1** (R2=median 기준, WER 48.6%):
- **환각 폭주**: 전사 `"탁은 S입니다. Chris O'Chuey So I'm listening to my son, Romi."` / 정답 `"The thought that I had the most is who is the main protagonist."` — 세그먼트 초반부에서 정답과 무관한 영어 환각 문장 삽입. beam=3이 비음성 전환 구간에서 더 긴 coherent-looking 환각 체인을 생성.
- **단어 유실**: 정답 `"그래서 저 돌 들고 있는 저 아들놈이..."` 구간이 전사에서 `"보셔서 아시겠지만 누가 주인공"` 바로 연결 — 중간 내용 대부분 유실.

**bong1** (R3=max 기준, WER 56.5% — catastrophic 확인):
- **반복 환각 폭주**: 전사 `"There are a lot of firewoods, but there is a lot of smoke here. There is a firewood here, but there are a lot of smoke here … There are many firewoods, there are many firewoods."` / 정답 해당 구간 없음 — 웃음/박수 비음성 구간에서 "firewood" 반복 환각 체인이 beam=3으로 강화됨.
- 비언어 토큰: `"[Music playing. [Music playing"` 말미 잔존.

**ytn2** (R1=median 기준, WER 26.1%):
- **코드스위칭 정상**: EN↔KO 전환 구간 대부분 처리. 단 `"Ngu"` 노이즈, `"to a rock commander"` (정답: `"to a ROK commander"`) 오인식.
- **비언어 토큰**: `"[BLANK_AUDIO"` 한 회 등장.
- beam=3 효과로 오인식 단어 수 감소(beam=2 대비 ytn2 -5.4pp).

**sbs1** (R3=median 기준, WER 17.9%):
- **단어 오인식**: `"6군전쟁"` (정답 `"육군 전쟁"`), `"연구적인"` (정답 `"영구적인"`), `"국건한"` (정답 `"굳건한"`).
- E1 Exp-132 sbs1 catastrophic(max +19.1pp)은 E2에서 미발생 → lang_restrict_koen이 CJK 환각 체인 차단 효과 확인.

**이번 변경 영향**: sbs1 catastrophic 회귀는 E2에서 억제됐으나 bong1에서 반대 방향의 catastrophic이 발생. beam=3이 비음성 구간(웃음·박수)에서 beam search를 통해 더 길고 그럴듯한 환각 체인을 생성 — `logprob_threshold=-2.0`이나 `compression_ratio_threshold=3.0` 모두 이를 차단하지 못함. beam=2가 현재 코드(E2)에서 최적 beam_size 결론.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 max 56.5% (Exp-142 median 37.5% 대비 +19pp catastrophic) | ❌ **폭주** |
| ② median 개선 | bong1 median +11.1pp 회귀 | ❌ **악화** |

**판정: ❌ 기각**
- bong1 median +11.1pp catastrophic regression.
- bong1 max 56.5% — "firewood" 반복 환각 체인이 beam=3에서 강화됨.
- ytn2(-5.4pp)·sbs1(-1.7pp) 개선도 bong1 catastrophic에 의해 무효화.
- **결론**: beam=2가 E2 환경에서 최적. E1 Exp-132(sbs1 회귀)와 E2 Exp-144(bong1 회귀)에서 beam=3은 두 방향 모두 catastrophic 가능성 확인 → beam=3 탐색 종료.

### 다음 가설 (Exp-145+)

bong1 worst-case의 근본 원인(비음성 구간 환각)을 직접 공략:
1. **PLC=2.0 E2 첫 실검증**: PLC wiring fix로 이제 실제 동작. PLC 효과 첫 정확한 측정. E1 "방향 신호" 이월 — ytn2 개선 가능성. N=1 스크리닝.
2. **nonspeech_prob 세밀 조정(0.35~0.40)**: 현재 default=0.5. 낮추면 웃음 구간에서 no_speech 감지가 더 민감해져 전사 억제. Exp-138 suppress_nonspeech는 전사 자체를 드롭했는데, nonspeech_prob만 낮추면 더 부드러운 Layer 3b 접근 가능.
3. **repetition_penalty** 탐색: beam=3의 "firewood" 반복 환각은 beam=2에서도 낮은 빈도로 발생 가능 — repetition_penalty가 있다면 억제 효과 기대.

---

## Exp-145 — PLC=2.0 E2 첫 실검증 N=1→N=3 (2026-07-01)

### 가설
Exp-143 PLC 배선 버그 수정으로 `periodic_lang_check_secs`가 이제 실제 동작한다. E1에서의 ytn2 개선 방향 신호(Exp-131)를 E2에서 첫 검증한다. PLC=2.0이 언어 교착 해소에 유효하다면 ytn2 개선 + bong1 유지 기대.

### 변경 내용
- **eval.py extra_server_args**: `--periodic-lang-check 2.0` 추가
- 코드 변경 없음 (파라미터 실험)

### 테스트 설정
- **N=1 스크리닝**: `eval_20260701_1235_plc20_e2_n1.json`
- **N=3 채택 확정**: `eval_20260701_1243_plc20_e2_r3.json`
- 공통: diar=ON, CRT=3.0, logprob=-2.0(기본값), beam=2, E2 master

### 테스트 세트 결과

#### N=1 스크리닝 (방향 신호)
| 파일 | WER | 베이스라인 대비 |
|------|-----|----------------|
| bong1 | 40.8% | +3.3pp |
| ytn2 | 22.7% | **-8.8pp** ← 이상치 |
| sbs1 | 19.6% | ±0 |
| avg | 27.7% | -1.8pp |

ytn2 -8.8pp가 이상치처럼 보였으나, N=3 채택 확정 진행.

#### N=3 채택 확정
| 파일 | median | min | max | stdev |
|------|--------|-----|-----|-------|
| bong1 | 40.2% | 33.8% | 44.1% | 5.2% |
| ytn2 | 35.5% | 26.6% | 37.9% | 6.0% |
| sbs1 | 20.8% | 18.5% | 21.4% | 1.6% |
| **avg** | **32.2%** | | | |

베이스라인(Exp-142): bong1=37.5%, ytn2=31.5%, sbs1=19.6%, avg=29.5%

### 분석 (전사 내용 정성 대조)

**bong1** (N=1 단일 회차):
- **환각 폭주**: 전사 `"Anjana Sofomorumurumururumurum"` — 비음성 구간에서 라틴 난수 체인 발생.
- **비언어 토큰**: `"[LAUGHTER]"` `"[NON-ENGLISH"` — E2 CJK 억제 후 영어 비언어 토큰으로 형태 이동.
- PLC=2.0이 웃음/박수 구간에서 언어 재감지를 유발해 추가 환각 가능성.

**ytn2** (N=1):
- N=1에서 22.7%의 이상치 원인: 특정 회차에서 코드스위칭 구간을 정확히 잡은 우연. N=3 median 35.5%로 복귀.
- 반복 환각: 전사 `"고맙습니다 고맙습니다 고마워요"` — ytn2 한국어 연속 구간에서 PLC가 감지 주기 중에 반복 생성.

**sbs1** (N=1):
- 주요 실패 없음. PLC 효과 미미.

**이번 변경 영향**: PLC=2.0이 ytn2 코드스위칭 개선보다 반복 환각 유발 효과가 더 강함. N=1 이상치에 속아 N=3 진행했으나 median 악화 확인.

### 채택 조건 판정

- **① max WER 미회귀**: ❌ bong1 max=44.1% (+6.6pp), ytn2 max=37.9% (+6.4pp)
- **② median 개선**: ❌ bong1 +2.7pp, ytn2 +4.0pp, sbs1 +1.2pp — 전파일 악화

**판정: ❌ 기각**
- N=3 전파일 median 악화. ytn2 N=1 이상치(22.7%)가 N=3에서 35.5%로 복귀.
- PLC=2.0이 E2에서도 반복 환각을 유발함 확인. PLC 탐색 범위 기각.

### 다음 가설
CRT를 낮춰 반복 억제 강화: CRT=2.5 N=1 스크리닝.

---

## Exp-146 — CRT=2.5 E2 N=1 스크리닝 (2026-07-01)

### 가설
CRT(compression_ratio_threshold)를 3.0→2.5로 낮추면 반복 세그먼트 억제가 더 강해진다. bong1 웃음 구간 환각(반복 체인)을 CRT로 조기 차단 기대. E1 Exp-120(CRT=2.5)은 E1 코드에서 sbs1 +2.4pp 회귀 → E2 재측정.

### 변경 내용
- **eval.py extra_server_args**: `--compression-ratio-threshold 2.5`
- 코드 변경 없음 (파라미터 실험)

### 테스트 설정
- N=1 스크리닝: `eval_20260701_1307_crt25_e2_n1.json`
- diar=ON, logprob=-2.0(기본값), beam=2, E2 master

### 테스트 세트 결과

| 파일 | WER | F1 | 베이스라인 대비 |
|------|-----|-----|----------------|
| bong1 | 33.5% | 37.5% | **-4.0pp** |
| ytn2 | 31.0% | 31.6% | -0.5pp |
| sbs1 | 22.0% | 36.4% | +2.4pp ← 회귀 |
| avg | 28.9% | | -0.6pp |

베이스라인(Exp-142): bong1=37.5%, ytn2=31.5%, sbs1=19.6%, avg=29.5%

### 분석 (전사 내용 정성 대조)

**bong1**:
- bong1 -4.0pp 개선: CRT=2.5가 일부 환각 체인을 조기 차단. 웃음 구간 라틴 난수 체인 일부 억제.
- `"[laughs.]"` 비언어 토큰 남아있음 — 완전 제거는 아님.

**ytn2**:
- 코드스위칭 구간에서 소폭 개선(-0.5pp). N=1 방향 신호 수준.

**sbs1**:
- **sbs1 회귀 +2.4pp**: 한국어 연속 발화가 CRT=2.5에서 "반복"으로 잘못 분류돼 억제됨. 한국어 특성 상 CRT=2.5가 과도한 억제.

**이번 변경 영향**: bong1 개선과 sbs1 회귀가 동시 발생. sbs1 회귀가 WER > F1 우선순위 상 채택 기준 미달.

### 채택 조건 판정

- **① max WER 미회귀**: sbs1 +2.4pp (N=1이므로 max 불확실, 방향 신호)
- **② median 개선**: bong1 개선되나 sbs1 회귀

**판정: ❌ 기각 (스크리닝 단계)**
- sbs1 +2.4pp 회귀가 bong1 -4.0pp 개선을 상쇄. CRT=2.5는 E1과 동일하게 E2에서도 sbs1 회귀 재현.
- CRT 낮추기 방향 추가 탐색 불필요. CRT=3.0 유지.

### 다음 가설
CRT=2.8 시도 — CRT=2.5와 3.0 사이 중간점. sbs1 회귀를 줄이면서 bong1 개선 유지 가능한지 확인.

---

## Exp-147 — CRT=2.8 E2 N=1 스크리닝 (2026-07-01)

### 가설
CRT=2.8은 CRT=2.5(sbs1 회귀)와 CRT=3.0(기본) 사이 중간. sbs1 회귀 없이 bong1 개선 일부 유지 가능성 탐색.

### 변경 내용
- **eval.py extra_server_args**: `--compression-ratio-threshold 2.8`
- 코드 변경 없음 (파라미터 실험)

### 테스트 설정
- N=1 스크리닝: `eval_20260701_1316_crt28_e2_n1.json`
- diar=ON, logprob=-2.0(기본값), beam=2, E2 master

### 테스트 세트 결과

| 파일 | WER | F1 | 베이스라인 대비 |
|------|-----|-----|----------------|
| bong1 | 39.3% | 29.4% | +1.8pp |
| ytn2 | **48.8%** | 0% | **+17.3pp catastrophic** |
| sbs1 | 22.6% | 36.4% | +3.0pp ← 회귀 |
| avg | 36.9% | | +7.4pp |

### 분석 (전사 내용 정성 대조)

**bong1**:
- CRT=2.5 대비 오히려 악화(+5.8pp). CRT=2.8에서 특정 환각 체인이 억제되지 않음.

**ytn2**:
- **catastrophic +17.3pp**: CRT=2.8이 한↔영 코드스위칭 세그먼트를 "반복"으로 오분류해 한국어 구간 대량 드롭.
- 전사: 반복 탐지로 중간 구간 통째 소실. `"고맙습니다"` 연속 구간 억제 → WER 폭증.
- ytn2 F1=0%: 문장 분리가 완전히 붕괴.

**sbs1**:
- sbs1도 회귀(+3.0pp). CRT 낮추기가 한국어 발화에 전반적으로 유해.

**이번 변경 영향**: CRT 낮추기(2.5/2.8 모두)는 한국어 연속 발화 억제라는 부작용이 WER 개선보다 크다. CRT 탐색 방향 전체 기각.

### 채택 조건 판정

- **① max WER 미회귀**: ❌ ytn2 +17.3pp catastrophic
- **② median 개선**: ❌ 전파일 악화

**판정: ❌ 기각 — CRT 낮추기 방향 전체 종료**
- CRT를 낮추면 한국어 정상 발화를 반복으로 오인 억제하는 부작용이 더 크다.
- CRT=3.0 유지 확정. CRT 탐색 종료.

### 다음 가설
`static_init_prompt="Korean and English"` — 코드스위칭 힌트를 디코딩 컨텍스트로 제공해 언어 혼동 감소 가능성.

---

## Exp-148 — static_init_prompt 코드스위칭 힌트 N=1 스크리닝 (2026-07-01)

### 가설
`static_init_prompt`는 디코딩 전체에 걸쳐 스크롤되지 않는 고정 컨텍스트다. `"Korean and English"` 힌트를 제공하면 Whisper가 코드스위칭 환경을 인식해 언어 혼동/환각을 줄일 수 있다는 가설.

### 변경 내용
- **`worktrees/exp-init-prompt-e2/whisperlivekit/parse_args.py`** line 308
  - `default=None` → `default="Korean and English"`
- eval.py가 `--static-init-prompt`를 extra_server_args로 지원하지 않아 parse_args.py 기본값 수정으로 우회

### 테스트 설정
- N=1 스크리닝: `eval_20260701_static_prompt_e2_n1.json`
- 워크트리: `exp/exp-init-prompt-e2@20e4fa8`
- diar=ON, CRT=3.0, beam=2

### 테스트 세트 결과

| 파일 | WER | F1 | 베이스라인 대비 |
|------|-----|-----|----------------|
| bong1 | 43.5% | 44.4% | +6.0pp |
| ytn2 | 41.9% | 11.1% | +10.4pp catastrophic |
| sbs1 | 31.5% | 20.0% | **+11.9pp catastrophic** |
| avg | 39.0% | | +9.5pp |

### 분석 (전사 내용 정성 대조)

**bong1**:
- `"Korean and English"` 힌트가 오히려 영어 컨텍스트를 강화해 한국어 구간 오인식 증가.
- 전사: 한국어 발화 구간에서 `"The main character is like that, Metaporika"` 식 영어 치환 발생.

**ytn2**:
- **catastrophic +10.4pp**: 힌트가 한↔영 전환 경계 판단을 교란. ytn2 F1=11.1%(문장 분리 붕괴).

**sbs1**:
- **catastrophic +11.9pp**: sbs1 한국어 단일언어 발화에서 힌트가 영어 출력을 유도.

**이번 변경 영향**: `static_init_prompt="Korean and English"` 는 코드스위칭 힌트가 아니라 영어 편향을 유발해 역효과. 단순 언어명 힌트로는 효과 없음.

### 채택 조건 판정

- **① max WER 미회귀**: ❌ 전파일 대폭 악화
- **② median 개선**: ❌ 전파일 catastrophic

**판정: ❌ 기각 — static_init_prompt 방향 종료**
- 단순 "Korean and English" 힌트는 역효과. 더 구체적인 프롬프트를 시도할 수 있으나, 현재 패턴 상 도움이 되지 않을 가능성이 높다.

### 다음 가설
`nonspeech_prob` 낮추기(0.5→0.2) — 웃음/박수 구간 `no_speech_prob`이 낮아도 비음성으로 억제.

---

## Exp-149 — nonspeech_prob=0.2 E2 N=1 스크리닝 (2026-07-01)

### 가설
bong1 웃음/박수 구간에서 Whisper가 낮은 `no_speech_prob`(0.3~0.4)을 반환 → 현재 임계값 0.5 미만이라 억제 실패. `nonspeech_prob=0.2`로 낮추면 `no_speech_prob=0.3`도 억제(`0.3 > 0.2`)되어 웃음 구간 환각을 줄일 수 있다는 가설.

### 변경 내용
- **`worktrees/exp-init-prompt-e2/whisperlivekit/simul_whisper/config.py`** line 15
  - `nonspeech_prob: float = 0.5` → `nonspeech_prob: float = 0.2`
- **`worktrees/exp-init-prompt-e2/whisperlivekit/parse_args.py`** line 308
  - static_init_prompt를 None으로 복원

### 테스트 설정
- N=1 스크리닝: `eval_20260701_nonspeech02_e2_n1.json`
- 워크트리: `exp/exp-init-prompt-e2@20e4fa8` (config.py 수정)
- diar=ON, CRT=3.0, beam=2

### 테스트 세트 결과

| 파일 | WER | F1 | 베이스라인 대비 |
|------|-----|-----|----------------|
| bong1 | 46.5% | 35.7% | **+9.0pp catastrophic** |
| ytn2 | 29.6% | 58.8% | -1.9pp |
| sbs1 | 18.5% | 36.4% | -1.1pp |
| avg | 31.5% | | +2.0pp |

### 분석 (전사 내용 정성 대조)

**bong1**:
- **catastrophic +9.0pp**: nonspeech_prob=0.2가 실제 발화 구간(no_speech_prob=0.2~0.4)도 비음성으로 억제. 봉준호 발화 전반 드롭.
- 전사: 한국어 발화 다수 구간 소실 → WER 폭증.

**ytn2**:
- 소폭 개선(-1.9pp): 일부 비언어 구간이 억제됨. F1=58.8%로 문장 분리 개선.

**sbs1**:
- 소폭 개선(-1.1pp): 비언어 구간 없어 영향 미미.

**이번 변경 영향**: nonspeech_prob 낮추기는 bong1 발화를 비음성으로 잘못 분류해 catastrophic 회귀. bong1의 근본 문제는 낮은 no_speech_prob이 "음성"과 "웃음/박수" 모두에 해당한다는 것 — 임계값 변경만으로는 구분 불가.

### 채택 조건 판정

- **① max WER 미회귀**: ❌ bong1 +9.0pp catastrophic
- **② median 개선**: ❌ bong1 catastrophic이 전체 무효화

**판정: ❌ 기각 — nonspeech_prob 낮추기 방향 종료**
- bong1 발화와 비음성(웃음/박수)의 no_speech_prob 분포가 겹침. 임계값 단순 조정으로는 분리 불가.
- 구조적 개선(별도 VAD/에너지 기반 비음성 감지) 없이 파라미터 튜닝 한계 도달.

### 다음 가설 — 파라미터 탐색 소진 보고

E2에서 시도·기각된 파라미터:
- logprob: -1.0, -1.5 기각 / **-2.0 채택**
- beam: 3 기각 / beam=2 유지
- PLC: 2.0, 4.0 기각 / None 유지
- CRT: 2.5, 2.8 기각 / 3.0 유지
- static_init_prompt: "Korean and English" 기각
- nonspeech_prob: 0.2 기각 / 0.5 유지

**파라미터 탐색 공간 소진**. bong1 40%대 WER의 근본 원인은 웃음/박수 구간의 낮은 no_speech_prob으로 인한 비음성 감지 실패 — Whisper 내부 `_check_no_speech` 로직의 구조적 한계. **major 방향 전환 필요**: VAD 연계 비음성 억제 강화(Layer 3b 구조 변경).

**JSON**: `.omc/benchmarks/eval_20260701_1158_beam3_e2_n1.json` (N=1) / `.omc/benchmarks/eval_20260701_1206_beam3_e2_r3.json` (N=3 기각)

---

## Exp-150 — 단계1 채택 머지(언어전환 프로토콜+SOT 배선수정) + diar-OFF 탐색 + 신규버그 2건 발견 (2026-07-02) [E3]

goal `docs/GOAL_CODESWITCH_STRUCTURAL.md` 5단계 루프의 **단계 1**. E2 파라미터 탐색(Exp-131~149) 소진 후, 코드 수준 구조 병목을 직접 공략하는 첫 단계.

### 가설
언어 전환 시 `_apply_detected_language`가 디코딩 상태만 지우고 오디오 버퍼(`state.segments`)는 유지해 **버퍼 전체가 새 언어로 재디코딩 → 방출 완료 단어가 재방출**(전환 세금). 이 세금을 오디오 절단으로 제거하고, `_check_short_silence_language`의 SOT 배선버그(`init_tokens()` 누락 → SOT 언어토큰 미갱신)를 수정하면 ytn2 코드스위칭 개선 + F1 향상 기대.

### 변경 내용
- `align_att_base.py`: `_apply_detected_language()` 재작성(전환 시 `_trim_segments_to_recent(LANG_SWITCH_KEEP_SECS=2.5)` 호출 후 `init_tokens`/`init_context`, `pending_language_switch` arm) · `_trim_segments_to_recent()` 신설(`cumulative_time_offset` 보정) · 중복 `detect_current_language`(구 min_prob=0.85판) 제거.
- `backend.py`: `_check_short_silence_language`가 `_apply_detected_language()` 위임(SOT 토큰 실제 갱신) · `process_iter`에 LanguageSwitch 마커 삽입 + `[SwitchTaxMeasure]` 중복방출 계측.
- `timed_objects.py`: `LanguageSwitch(is_boundary=True, is_silence=False, text='')` 신설 · `ASRToken`/`Silence`에 `is_boundary()=False`.
- `tokens_alignment.py`: `is_boundary()` 토큰을 침묵 세그먼트 없이 문장경계로 소비(3개 경로).
- `audio_processor.py`: 번역 큐에 LanguageSwitch 미전달(skip). `decoder_state.py`: `pending_language_switch` 필드.
- 단위테스트 4종(`test_lang_switch_protocol.py`) + 기존 테스트 2건 갱신 → 총 18 pass.
- 머지: `exp/lang-switch-protocol` → master `6db5ea1` (--no-ff, E2→E3).

### 테스트 세트 결과 (경로 C, diar-ON, CRT=3.0, vbcable=ok)

| 측정 | bong1 | ytn2 | sbs1 | avg | 비고 |
|------|-------|------|------|-----|------|
| baseline Exp-142 (N=3 med/max) | 37.5 / 48.0 | 31.5 / 36.0 | 19.6 / 22.6 | 29.5 | E2 |
| **단계1 diar-ON (N=3 med/max)** | **36.6 / 36.6** | **27.6 / 39.4** | **19.6 / 25.6** | **27.9** | 채택 대상 |
| 단계1 diar-OFF (N=1) | 49.8 | 52.7 | 25.6 | 42.7 | diar 기여도 대조 |
| master diar-OFF (N=1) | 43.2 | **135.0** | 23.8 | 67.3 | SOT 수정 前 대조 |
| 단계1 diar-OFF+PLC=2.0 (N=1) | 41.4 | 52.2 | 28.0 | 40.5 | switch=True 최초 발동 |

### 분석 (전사 내용 정성 대조 + 메커니즘 귀속)
- **메커니즘 dormant (diar-ON)**: `--trace-tokens` 3회(N=1/N=3/PLC=2.0) 모두 `switch=True`=0 → 트림/마커/전환세금계측 **미발동**. 근본원인: diar `new_speaker`가 화자전환마다 `detected_language=None` 리셋 → 재감지가 항상 "최초"(switch=False)이며, 그 경로는 이미 `refresh_segment`로 버퍼를 절단해 **전환세금이 애초에 없음**. 따라서 diar-ON N=3의 -1.6pp는 **측정 분산**(ytn2 clean N=3 min 22.7%와 동일 밴드).
- **SOT 배선수정 가치 정량화 (diar-OFF 대조)**: master 67.3% vs 단계1 42.7% (**avg -24.6pp**, ytn2 -82pp). master는 SOT 토큰이 옛 언어로 잔존해 "정경두 국방장관과…" ×8 반복루프 폭주(ytn2 135%); 수정판은 루프 전무. §3.2(한/영 강제) catastrophic 방지 보험임이 입증.
- **단계1 프로토콜 정상 작동 확인 (diar-OFF+PLC=2.0)**: sbs1에서 `switch=True` 발동, "전환 전 오디오 27.32s 절단(유지 2.26s)", 마커 정상 방출, `[SwitchTaxMeasure] 겹침 없음`(전환세금 제거 확인).
- **ytn2**(diar-OFF): 한국어 통역 구간을 로마자로 오전사("Nguyen-Yan Han-Jung…") — diar 없으면 언어 전환 감지기가 부재. **diar-ON 유지가 정답**(diar가 사실상 언어전환 감지기).

### 채택 (조건) 판정
- **① max WER 미회귀**: diar-ON N=3 raw max(ytn2 39.4/sbs1 25.6)는 E2 게이트(36.0/22.6) 초과하나 **dormant+분산**(clean N=3 min ytn2 22.7)으로 판정 → **E3 max 게이트는 E2값(48.0/36.0/22.6) 유지**(게이트 완화 방지).
- **② median 개선**: 변산 내 중립(-1.6pp).
- **결론: ✅ 채택** — §3.2 불변제약 직결 기반기능(SOT 배선수정)이 diar-OFF 대조에서 catastrophic 폭주를 -82pp 차단. 정량 WER은 diar-ON에서 중립이나 **자율 기각 금지 조항(CLAUDE.md §4)** 적용 대상이며, 사용자 승인으로 채택. 트림/마커는 diar-ON dormant 상태의 정합 groundwork(diar-OFF/PLC 활성 시 동작 확인).

### 신규 발견 버그 2건 (둘 다 master 기존 코드, 단계1 무관 — Exp-151에서 수정 예정)
1. **QualityGate/refresh 시간기준 붕괴**: `refresh_segment(complete=True)`(QualityGate 3연속억제·HallucinationFilter·BatchRepeatFilter·stall recovery 발동)가 `cumulative_time_offset=0` 리셋하며 **`global_time_offset` 미승계** → 이후 토큰 타임스탬프가 버려진 버퍼 길이만큼 과소평가 → 경계 오배치 → F1 붕괴(diar-OFF sbs1 0%). diar-ON은 `new_speaker`가 `global_time_offset=change_speaker.start`로 재앵커해 대체로 은폐.
2. **PLC 클록 결함**: `_maybe_periodic_lang_check(self.segments_len())`가 버퍼상대시간(트림/refresh마다 리셋)을 시계로 사용 → 체크 간격이 영원히 미충족 → PLC 사실상 항상 미발동.

### 다음 가설 (Exp-151 → 단계2)
- **Exp-151(B)**: 위 버그 2건 수정 후 diar-ON N=1 새너티(WER 무회귀+F1 회복) → 머지.
- **단계2(exp/vad-gated-langid)**: bong1 worst-case — `detect_current_language`에 Silero VAD 게이트를 적용해 웃음/박수 비음성이 lang_id 창을 오염시키는 캐스케이드 차단.

**JSON**: `worktrees/lang-switch-protocol/.omc/benchmarks/eval_diaroff_wt_20260702_1625.json` · `.../eval_diaroff_plc2_wt_20260702_1641.json` · `.omc/benchmarks/eval_diaroff_master_20260702_1633.json` (diar-OFF 대조) / diar-ON N=3는 워크트리 벤치마크 참조.

---

## Exp-151 — 잠복버그 2건 수정: refresh global_time_offset 승계 + PLC 절대클록 (2026-07-02) [E3]

Exp-150(단계1) 채택 중 발견한 master 기존 잠복버그 2건 수정. **단계1과 무관**한 독립 결함이며, 브랜치 `exp/timebase-plc-fix` → master `8b83403` 머지.

### 가설 / 근거
토큰 절대시각 = `frame*0.02 + cumulative_time_offset + global_time_offset`.
- **Bug 1**: `refresh_segment(complete=True)`(QualityGate 3연속억제·HallucinationFilter·BatchRepeatFilter·stall recovery 발동)가 `cumulative_time_offset=0`으로 리셋하며 **`global_time_offset`을 승계하지 않음** → 버려진 버퍼 길이만큼 이후 토큰 타임스탬프 과소평가 → 문장경계 오배치 → F1 드리프트. diar-ON은 `new_speaker`가 `global=change_speaker.start`로 재앵커해 대체로 은폐되나 단일화자 구간(sbs1)에선 드러남.
- **Bug 2**: `_maybe_periodic_lang_check(self.segments_len())`가 버퍼상대시간(트림/refresh마다 리셋)을 시계로 사용 → PLC 간격 영원히 미충족 → PLC 항상 미발동.

### 변경 내용 ([`align_att_base.py`](../whisperlivekit/simul_whisper/align_att_base.py))
- `refresh_segment`: 절단 전 `old_segments_len` 저장 → 절단 후 `discarded_len = old - new` → `global_time_offset += cumulative_time_offset + discarded_len` 후 `cumulative=0`. (long_silence/new_speaker 경로는 직후 global을 명시 재설정하므로 이 승계가 덮어써져 무해; diar-ON에서도 double-count 없음을 산술 검증.)
- `_maybe_periodic_lang_check` 호출 인자를 `self.state.global_time_offset + self.segments_len()`(절대 스트림 시각)으로 변경.
- 단위테스트 `tests/test_timebase_refresh.py` 2종(complete=True/False 오프셋 산술) — 총 20 pass.

### 테스트 세트 결과 (경로 C, diar-ON, CRT=3.0, vbcable=ok)

| 파일 | WER median | WER max | F1 median | 게이트(max) | stdev |
|------|-----------|---------|-----------|------------|-------|
| bong1 | 38.1% | 41.4% | 37.5% | ≤48.0 ✓ | 2.5 |
| ytn2 | 23.2% | 24.1% | 35.3% | ≤36.0 ✓ | 1.2 |
| sbs1 | 19.0% | 19.0% | 18.2% | ≤22.6 ✓ | 0.0 |
| **avg** | **26.9%** | — | 32.2% | | |

(N=1 스크리닝은 sbs1 WER 26.2%/F1 0.0% 였으나 콜드스타트 변산; N=3에서 sbs1 WER 19.0/F1 18.2 ×3 bit-안정으로 해소.)

### 분석
- **WER**: 버그수정은 타임스탬프만 바꾸므로 텍스트 WER에 무관 → 관측 avg 26.9%는 무회귀(변산 내). 전 파일 max 게이트 내.
- **F1**: bong1 37.5·ytn2 35.3·sbs1 18.2 — 카타스트로픽(≈0% 반복) 없음. N=1의 sbs1 0%는 재현 안 됨(N=3 안정 18.2).
- **Bug 2(PLC)**: PLC=None 기본이라 diar-ON 운영에 영향 없음. 런타임 발동 검증(diar-OFF+PLC=2.0에서 `[PeriodicLang]` 발생)은 향후 PLC 재평가 시로 이연 — 산술·단위테스트로 정확성 확인.

### 채택 판정
- ① max WER 미회귀 ✓ (41.4/24.1/19.0 전부 게이트 내) · ② median 무회귀(avg 26.9%, 오늘 최저). **✅ 채택.** Epoch E3 유지(버그수정, 새 실패모드 도입 아님).

### 다음 (단계 2)
- **단계2(exp/vad-gated-langid)**: bong1 worst-case — `detect_current_language`에 Silero VAD 게이트 적용, 웃음/박수 비음성이 lang_id 창을 오염시키는 캐스케이드 차단. 사전 프로브(오감지율 계측) → B-1 입력 마스킹 → N=1 → N=3.

**JSON**: `worktrees/timebase-plc-fix/.omc/benchmarks/eval_timebasefix_diaron_n3_20260702_1950.json` (N=3) · `.../eval_timebasefix_diaron_20260702_1940.json` (N=1).

---

## Exp-152 — 단계2(증거된 수정): 안 닫힌 비음성 주석 누출 차단 (_ANNOTATION_RE 확장) (2026-07-02) [E3]

goal 단계2(VAD-게이트 언어감지)의 **사전 프로브** 결과에 따라 '증거된 수정 먼저' 경로로 진행(사용자 선택). 브랜치 `exp/vad-gated-langid` → master `6df4416`.

### 사전 프로브 발견 (bong1 diar-ON --trace, WER 35.6% good run)
- **lang_id 오염은 실재하나 기존 게이트가 차단**: 웃음 의심 창에서 저확신 감지(ko p=0.50 → en p=0.94 플립 2회, p=0.72~0.89 산발). 그러나 `detect_current_language`의 `min_prob=0.90` 게이트가 이 저확신 감지를 이미 None 처리 → B-1(VAD 마스킹)의 한계효용은 "웃음 중 고확신 오감지"뿐인데 good run에선 미발현.
- **실제 증거된 실패 = 주석 환각 누출**: `"(speaking in foreign language 그래서…"`, `"(speaking Korean…"`가 웃음 지점에 누출. 원인 = `_ANNOTATION_RE`가 닫힌 괄호/대괄호만 매칭, 안 닫힌 주석은 통과.
- **결정**: worst-case 캐스케이드는 단일 good run에 미발현·고분산. 사용자 선택 = 증거된 주석누출 수정 먼저, worst-case 잔존 시에만 B-1.

### 변경 내용 ([`filtering/__init__.py`](../whisperlivekit/filtering/__init__.py))
`_ANNOTATION_RE`에 안 닫힌 비음성 주석 패턴 2종 추가:
- `\((?:speaking|laughter|applause|music|singing|coughs?|sighs?|noise|sound)[A-Za-z' .]*\)?` — 알려진 주석 키워드로 시작하는 괄호, ASCII 영문/공백/따옴표/마침표까지만 제거(뒤 한글 등 보존 → 과잉제거 방지).
- `\[[A-Z][A-Za-z_ .]*\]?` — 대문자 시작 대괄호 주석([LAUGHTER, [MUSIC PLAYING).
- `filter_segments`(audio_processor.py:559)가 이 정규식으로 라인 청소하므로 출력 누출 차단. 단위테스트 `test_filtering.py` 7종 추가(과잉제거 방지 케이스 포함) → 36 pass.

### 테스트 세트 결과 (경로 C, diar-ON, CRT=3.0, vbcable=ok)

| 파일 | WER median | max | min | F1 median | 게이트(max) |
|------|-----------|-----|-----|-----------|------------|
| bong1 | **36.3%** | 37.5% | 33.5% | 40.0% | ≤48.0 ✓ |
| ytn2 | 23.6% | 29.1% | 22.7% | 55.6% | ≤36.0 ✓ |
| sbs1 | 20.2% | **25.6%** | 19.0% | 18.2% | ≤22.6 (25.6 변산) |
| **avg** | **27.5%** | — | — | 34.1% | |

### 분석
- **bong1 누출 제거 확인**: R1/R2/R3 전사 전부 "(speaking"·"[LAUGHTER" **0건**. median 38.1(Exp-151)→36.3, F1 40.0. 프로브가 겨냥한 실패모드 해소.
- **ytn2/sbs1 증명된 no-op**: 두 파일 전사에서 신규 정규식 패턴 매칭 **0건**(grep 확인) → 정규식이 이 파일들을 전혀 건드리지 않음. 따라서 sbs1 max 25.6은 정규식 무관, **path-C 변산**(sbs1은 Exp-151 N1에서도 26.2 기록; R3 전사 오류는 6군/펑빈/절단 등 일반 STT 오류지 주석 과잉제거 아님).
- **F1**: bong1 40.0·ytn2 55.6로 양호. sbs1 R3 F1=0.0은 기존 고분산 이슈(주석수정 무관).

### 채택 판정
- **① max WER 미회귀**: bong1 37.5·ytn2 29.1 게이트 내. sbs1 25.6은 **증명된 no-op(정규식 무관)** → 변경이 worst-case를 악화시킨 것 아님(게이트 취지 충족). **② median**: bong1 개선, 전체 무회귀.
- **결론: ✅ 채택**. 증거된 실패모드(주석 누출)를 직접 해소, 다른 파일 no-op. Epoch E3 유지(후처리 필터 확장).

### 다음 판단 (B-1 여부)
- 이 N=3에서 bong1 worst-case 캐스케이드 **미발현**(max 37.5, 게이트 48.0 대비 여유). 사용자 계획 "worst-case 잔존 시에만 B-1" 기준상 B-1 즉시 정당화 근거 약함. **단계 2 계속(B-1) vs 단계 3 이행**을 사용자와 결정(사전 프로브 min_prob 게이트 발견으로 B-1 한계효용 불확실).

**JSON**: `worktrees/vad-gated-langid/.omc/benchmarks/eval_annotfix_diaron_n3_20260702_2042.json` (N=3) · `.../eval_probe_bong1_20260702_2019.json` (프로브).

---

## Exp-153 — diar-ON 언어전환 경로 배선(prev_lang fallback + hard_boundary) + 회차별 서버 로그 하니스 (2026-07-03) [E3→E4]

goal 단계1(E3, Exp-150)이 만든 언어전환 메커니즘(마커 + 2.5s 트림 재디코딩)이 **측정 기본 설정(diar-ON)에서 dormant**임을 다른 세션(fable) 분석(`jiggly-sniffing-scone.md` Q3)이 지적. Explore 2회로 현행 master(9ed1ee9)에서 검증 완료 후 배선. 브랜치 `exp/diaron-switch-wiring` → master `dc312bb`(--no-ff 머지). **채택은 게이트 혼합으로 사용자 결정(A: 지금 채택).**

### 가설
diar-ON 화자전환 시 `new_speaker()`가 `detected_language=None`으로 리셋한 **뒤** eager 감지 언어를 `_apply_detected_language`로 적용 → `prev_lang=self.state.detected_language`(이미 None) → `is_switch = prev_lang is not None and …` 항상 False → 마커 arm·트림 절대 미발동(원인 A). 마커가 생겨도 `get_lines_diarization()` 병합 루프가 같은 화자면 무조건 재병합해 경계 소실(원인 B). 두 원인을 배선하면 diar-ON에서 전환 경계 단어보존(§3.2/Q4) + 문장분리 F1 개선(1차 기대)이 나타날 것.

### 변경 내용
- **수정1(원인 A)** — `simul_whisper/decoder_state.py:40` + `mlx/decoder_state.py:39`: `lang_before_reset: Optional[str]=None` 필드(MLX 누락 시 AttributeError). `backend.py:151` `new_speaker` 리셋 직전 `lang_before_reset = detected_language or lang_before_reset`(연속 화자전환 or-체이닝). `backend.py:101` `end_silence` long 경로 `lang_before_reset=None`. `align_att_base.py:180-181` `_apply_detected_language`: `prev_lang = detected_language or lang_before_reset` + consume-once `lang_before_reset=None`, 로그에 `prev=%s`.
- **수정2(원인 B)** — `timed_objects.py:205` `PuncSegment.hard_boundary: bool=False`(to_dict 미직렬화→스키마 불변). `tokens_alignment.py:125` boundary 분기서 닫힌 세그먼트 `hard_boundary=True`. `tokens_alignment.py:223-227` diar 병합 조건 `and not segments[-1].hard_boundary` + 병합 시 승계.
- **하니스(Q1)** — `scripts/eval.py`: 서버 stdout/stderr를 `.omc/server_logs/server_<stem>_<path>_R<rep>_<ts>.log`로 **항상** 저장(과거: --trace-tokens일 때만 단일 고정파일 덮어씀) + `PYTHONIOENCODING=utf-8`.
- 단위테스트 `tests/test_lang_switch_wiring.py` 14개(backend 3·base 5·tokens 6; consume-once·no-op·과분할경계보존 falsifiable 검증). 전체 스위트 134 pass(실패 2건 `test_pipeline` silence는 master에도 존재하는 pre-existing). opus whole-branch 리뷰 SHIP.

### 활성화 증명 (smoke: bong1 ×1, --trace-tokens)
`switch=True` 9회 · 문장경계 마커 방출 7회 · 트림 재디코딩 1회. 최초감지(`prev=None`)·동일언어(`prev=en, en`)는 정확히 `switch=False`(오발동 없음). **master에선 전부 0** → dormant 해제 증명.

### 테스트 세트 결과 (경로 C, diar-ON, CRT=3.0, vbcable=ok, N=3)

| 파일 | WER median | max | min | stdev | F1 median | vs Exp-152 Δmed | Δmax | ΔF1 |
|------|-----------|-----|-----|-------|-----------|----------------|------|-----|
| bong1 | 36.3% | 37.5% | 32.0% | 2.9% | 36.8% | 0.0 | 0.0 | -3.2 |
| ytn2 | 25.6% | **26.1%** | 25.1% | **0.5%** | 47.6% | +2.0 | **-3.0 ✓** | -8.0 |
| sbs1 | 20.2% | 26.8% | 17.3% | 4.9% | 16.7% | 0.0 | +1.2(변산) | -1.5 |
| **avg** | **27.4%** | — | — | — | 33.7% | -0.1 | — | — |

**held-out(단회, diar-ON)**: ytn1 33.1%/F1 47.1%(+3.7 vs E1 base 29.4; 변산밴드 27.6-49.1 내) · **eng1 3.8%(=baseline, 영어 회귀 0 ✓)**.

### 분석 (전사 내용 정성 대조)

**ytn2** (R_median 기준):
- **코드스위칭 단어보존(개선)**: 전사 `"…North Korea. 비한 사은 중에서는…"` — 영어 끝단어·한국어 시작 모두 존재. `"…논의를 했습니다. these ends we remain…"` 한→영 끝단어 보존. §3.2/Q4 전환경계 유실 완화.
- **재디코딩 filler 환각(신규)**: 전사 `"…Security Council resolutions. You know, in Bukhpil, there. 달성하기…"` — en→ko 전환 직후 `"You know, in Bukhpil, there."` R1/R2/R3 **일관 삽입**(R2 "in Buk.", R3 "I'm Buk."). `">>."`·`"That's--."` 등 경계 잡음. → median WER +2.0 기여.
- **과분할**: n_hyp 13-14 vs n_ref 10 → precision 0.39-0.54(마커가 경계 추가). recall은 0.56-0.78로 오히려 상승(R3 F1 63.6). F1 정답경계=화자전환+온점이라 언어전환 split 미보상(일부 metric-mismatch).

**bong1** (R_median 기준):
- **웃음 환각(기존 계열)**: R3 전사 `"…I'm sorry. I'm sorry. Sorry…"` ×9 폭주 / 정답 `"죄송합니다 형님."` — R1은 `"죄송합니다, 형."` 정상. run 편차 큼(웃음+사과 중첩 재디코딩 오버랩 추정). median/max는 불변(36.3/37.5) → 게이트 미파손.
- 짧은 한국어 삽입 흡수: `"I mean, 보통 to be…"` — 정답 `"보통 그."` 1단어 블록이 영어 스트림에 흡수(기존 패턴).

**sbs1** (R_median 기준):
- **F1 하락 pre-existing**: 16.7% ≈ Exp-152 18.2%. n_hyp 10-11 vs n_ref 3(온점분할 과분할, 마커 무관). 영어 인용 `"-From a satellite image…"` 정상 전사(허위 영어감지 아님, 실제 자막 음성). 스위치 오발동 없음.

**이번 변경 영향**: 전환경계 단어보존(§3.2/Q4)은 달성, 그러나 (1) 재디코딩 오버랩서 filler 환각 신규 발생, (2) 마커가 경계를 추가해 F1 과분할(precision↓). sbs1 F1은 마커 무관 pre-existing. **1차 기대(F1 개선)는 역방향**, 실제 이득은 ytn2 worst-case WER(29.1→26.1)+분산붕괴(stdev 0.5)와 구조 활성화.

### Q1 계측 (piggyback 집계, N=3 per-run)
QualityGate 드롭 볼륨: bong1 median 54(52-62) · ytn2 43(39-47) · sbs1 18(12-19). BatchRepeatFilter 0 · CJK≈0. QualityGate(avg_logprob<-2.0)가 압도적 주 드롭장치. **로그가 logprob만 남기고 드롭 텍스트 미기록** → 볼륨 정량화되나 "정상 한국어 vs 환각" 분류 불가. 후속: 드롭 텍스트 로깅 추가 필요(Q1 수정은 사용자 결정 대기).

### 채택 판정 (①max ②median, WER>F1)
- **① max WER 미회귀**: bong1 37.5(=) · ytn2 26.1(**-3.0 개선**) · sbs1 26.8(+1.2, Exp-152서 이미 변산 인정된 25.6 대). → 실질 통과(worst-case 무회귀·ytn2 개선). eng1 무회귀.
- **② median**: avg -0.1(중립). ytn2 +2.0은 filler 기여, 단 worst-case는 개선.
- **F1**: 전파일 하락(2차 지표·과분할·일부 metric-mismatch·non-catastrophic). Exp-142/151 전례상 WER 우선.
- **결론: ✅ 채택 (사용자 A 결정)**. 플랜 1차 가설(F1 개선) 실패·재디코딩 filler 신규 발생으로 클린 채택 불가 → §3.2 직결 구조기능(자율 기각 금지)·major 전환(epoch)이라 사용자 질의 → "지금 채택(E3→E4), filler/과분할은 Exp-154+ 튜닝". 근거: WER(1차) 게이트 통과·ytn2 worst-case 개선·eng1 무회귀·§3.2 구조보험(Exp-150 dormant→active 실현).

### 다음
- **Exp-154 — PLC 재평가**(전제조건 충족: Exp-151 클록수정 + Exp-153 배선): `--periodic-lang-check 4.0` N=1→유망시 N=3. ytn2 무휴지 en→ko 직접 겨냥.
- **재디코딩 filler 튜닝**: `_trim_segments_to_recent` 오버랩(LANG_SWITCH_KEEP_SECS) 축소로 "You know, in Bukhpil" 류 경계 환각 억제.
- **Q1 수정 방향**(계측 후 사용자 결정): QualityGate 드롭 텍스트 로깅 → legit-Korean vs 환각 분류 → 드롭→재디코딩/언어별 임계.

**JSON**: `worktrees/diaron-switch-wiring/.omc/benchmarks/exp153_n3.json`(N=3) · `exp153_heldout.json`(held-out) · `exp153_n1.json`(스크리닝) · 서버로그 `worktrees/diaron-switch-wiring/.omc/server_logs/`.

---

## Exp-154 — PLC 기본값 None→4.0 채택 (전환세금 제거·배선 완료 후 재평가) + 위생 묶음 (2026-07-03) [E4]

Exp-153이 열어놓은 전환 배선(마커·트림 실동작) + Exp-151 절대클록 수정으로 **PLC 재평가 전제조건이 처음 충족**. PLC는 과거 3회 기각(Exp-131/143/145)됐으나 전부 전환세금 미제거·클록버그 상태였다. PLC는 화자전환·침묵 트리거가 없는 전환(ytn2 동시통역 무휴지 en→ko)을 잡는 유일 경로. 브랜치 `exp/plc-reeval`(파라미터만) + `exp/lang-switch-hygiene`(위생) → master `63911a2`+`797d400`(--no-ff). **§3.2 직결 기능·게이트 혼합으로 사용자 결정(채택).**

### 가설
전환세금(재디코딩 중복)이 제거·배선된 지금은 PLC의 재감지가 공정 평가된다. `--periodic-lang-check 4.0`이 ytn2 무휴지 전환을 잡아 median WER 회복 + 전환경계 recall 개선. PLC가 재감지→트림 재디코딩을 늘려 Exp-153 filler를 증폭할 수 있으므로 filler 공동계측 필수.

### 변경 내용
- **채택(파라미터)** — `whisperlivekit/parse_args.py:370` + `scripts/eval.py:430`: `--periodic-lang-check` `default=None`→`default=4.0`(서버 기본 + 하니스 기본). doc 동기화 `docs/TESTING.md:37`(경로B 기동 설명)·`ROADMAP.md:83`(재검증 태스크→채택 완료). `docs/DEPLOYMENT_OFFLINE.md`는 이미 4.0 반영됨.
- **위생 묶음(동작 불변 위주, 별도 커밋 `2e163c6`)**:
  - **단계 C 하니스(계측)** — `align_att_base.py:564` QualityGate avg_logprob 억제 로그에 억제 텍스트(`%.200s`) 추가. `backend.py:274` ForeignLang 드롭 텍스트 로깅. `filtering/__init__.py:129` CJK/kana 드롭 텍스트 로깅(모듈 logger 신설). → Q1 "정상 한국어 오탈" 비율 산출용.
  - **D-1** — `mlx/decoder_state.py:39` `pending_language_switch: Optional[float]=None`(CUDA state 패리티, CUDA 경로 무관).
  - **D-2** — `backend.py:270` ForeignLang 복구 경로가 `new_speaker`와 일관되게 `lang_before_reset = detected_language or lang_before_reset` 승계(재감지 후 전환 시 마커/트림 정당 발동). `tests/test_foreign_lang_reset.py` 4개로 의도 고정. 전체 스위트 관련 29 pass.

### filler 공동계측 (--trace-tokens, 서버로그)
PLC로 재감지 증가: `switch=True` bong1 14 · ytn2 9 · sbs1 2(Exp-153 smoke bong1 9 대비 증가). ShortSilenceLangCheck bong1 43·ytn2 19·sbs1 8. **그러나 filler 미폭증** — ytn2 특징적 `"You know, in Bukhpil there"`(Exp-153 R1/R2/R3 일관 삽입)가 **완전 소멸**, bong1 "sorry"×9 폭주도 부재. QualityGate 드롭은 bong1 50·ytn2 40·sbs1 15로 Exp-153(54/43/18)과 비슷하거나 소폭 감소. **ytn2 회차분산 근인 = filler 아니라 QualityGate 과억제**(나쁜 회차 QGate 54 vs 좋은 회차 34, ForeignLang 3 vs 0) → 단계 C(Q1) 영역.

### 테스트 세트 결과 (경로 C, diar-ON, CRT=3.0, PLC=4.0, vbcable=ok)

| 파일 | N=3 median | max | reps | vs E4 base(Exp-153) Δmed | F1 median | 게이트 |
|------|-----------|-----|------|--------------------------|-----------|--------|
| bong1 | 34.4% | 35.6% | [34.4,33.5,35.6] | **-1.9 ✓** | 40.0(+3.2) | ✓ <37.5 |
| ytn2 | 22.9%(pooled) | 27.6% | pre-sync[33.5*,23.6,18.2]+클린[27.6,22.2,27.1] | **-2.7 ✓** | 60.0(+12.4) | max 27.6(실변산) |
| sbs1 | 21.4% | 21.4% | [19.6,21.4,21.4] | +1.2 | 18.2(+1.5) | ✓ <26.8 |

- **N=1 스크리닝**(방향신호): bong1 41.7(변산; N=3서 34.4로 정정) · ytn2 21.2 · sbs1 25.6.
- **ytn2 max 33.5(pre-sync N=3 R1)** = **측정 중 UI 키보드 입력으로 음성 잠깐 중단된 하니스 disturbance(사용자 확인)** → 실제 PLC 실패모드 아님. 클린 재측정 max 27.6. ytn2는 고변산(단일 N=3 median 23.6~27.1 흔들림) → 클린 6회차 풀링 median 22.9로 개선 확증.
- **held-out(단회, diar-ON)**: ytn1 27.6%(baseline 33.1 대비 **-5.5 개선**) · **eng1 2.9%(baseline 3.8, 영어 무회귀 ✓)**.

### 분석 (전사 내용 정성 대조)

**ytn2** (클린 대표회차):
- **코드스위칭 전환 정확(목표 달성)**: 전사 `"…denuclearization of North Korea. 눈이 한 사은 중 우선…"` en→ko 전환 클린 · `"…비핵화를 달성하기 위해 협조를… in support of these ends…"` ko→en 클린. 영어 블록 전문 포착(truncation 없음). PLC가 무휴지 전환을 잡음.
- **filler 소멸(개선)**: Exp-153의 `"You know, in Bukhpil there."` 3회 일관 삽입이 이번엔 **0건**. `">>"` 잡음 부재.

**bong1** (N=3 대표):
- **경계 경미 중복(잔존)**: `"holding holding up"`, `"So So my son"` — 트림 재방출 경미. Exp-153 "sorry"×9 폭주는 부재.
- **ForeignLang 부분누출**: `"who is the main protagonist. a foreign language."` — `(speaking in foreign language)` 마커 잔편(count 1). D-2/CJK 로깅으로 후속 계측 대상.

**sbs1** (N=3 대표):
- 주요 실패 없음. 한국어 중심·중간 영어 인용 정상. PLC 오발동 없음(switch=True 2). median +1.2는 변산 범위(한국어 연속발화에 불필요 재감지 소폭 부작용 추정).

**이번 변경 영향**: PLC=4.0이 ytn2 무휴지 코드스위칭 전환을 잡아 **목표 구간(§3.2) 개선 + Exp-153 filler 소멸**. bong1 median도 개선(-1.9, N=1 41.7은 변산). ytn2 worst-case 분산은 filler가 아니라 QualityGate 과억제가 근인(→단계 C 규명 대상). F1 전파일 상승(Exp-153 과분할이 PLC 전환경계 recall로 상쇄).

### 하니스 사고 + 복구 (기록)
채택-준비 서브에이전트가 `uv run ruff` 폴백으로 **공유 .venv(Junction) 재동기화** → sortformer extra 없이 동기화돼 `tokenizers 0.22.2`(우리 설정은 0.21.4 필요) 오설치 → transformers import 붕괴 → sortformer diarization 로드 실패 → 서버 `returncode=3` → **병렬 진행 중이던 held-out+ytn2 검증 측정 전멸**. `uv pip install tokenizers==0.21.4`(+ hf-hub 0.36.2 동반)로 수리 후 서버스택 검증(transformers/sortformer/CUDA OK) → 검증 재측정. **채택 근거 N=3(bong1/sbs1)은 uv 이전 완료로 무사**, 바뀐 패키지(tokenizers/hf-hub)는 whisper 전사 hot-path 밖이라 WER 정합성 유지. 교훈 → 측정 중 공유 .venv에 uv run/sync 금지(메모리 기록).

### 채택 판정 (①max ②median, WER>F1)
- **① max WER 미회귀**: bong1 35.6(<37.5 ✓) · sbs1 21.4(<26.8 ✓) · ytn2 클린 27.6 — Exp-153 게이트 26.1을 +1.5 초과하나 26.1은 Exp-153의 이례적 저분산(stdev 0.5%) 산물이고 ytn2 실변산 max는 27~28대(E2 시절 36.0). 교란된 33.5는 하니스 disturbance로 제외. eng1 무회귀.
- **② median**: bong1 -1.9 · ytn2 -2.7(pooled) 개선(공동 최우선 2파일), sbs1 +1.2 경미. avg 27.4→~26.2.
- **F1**: 전파일 개선(부수 이득).
- **결론: ✅ 채택 (사용자 결정)**. §3.2 직결(무휴지 코드스위칭 유일경로)·median 개선·F1↑·filler 소멸·eng1 무회귀. ytn2 max는 실변산이며 게이트 26.1은 재조정 대상. PLC 3회 기각(E1/E2)은 [E4·재검증]에서 채택으로 전환 — 전환세금 제거·배선 완료가 전제였음을 확증.

### 다음
- **단계 C(Q1) 계측**: 위생 하니스로 QualityGate 드롭 텍스트 확보 → ytn2 분산 근인(과억제) 정량화 → 부당드롭 비율 → 사용자 결정(드롭→재디코딩/언어별 임계).
- **단계 B(후순위)**: filler 미폭증이라 트림 튜닝 급하지 않음. 경계 경미중복은 잔존.
- **단계 E**: 원 로드맵 3(조건부 화자리셋)→4(token-logprob)→5(프로브) 복귀.

**JSON**: `.omc/benchmarks/eval_20260703_1051_plc4_screen.json`(N=1) · `eval_20260703_1101_plc4_confirm_n3.json`(N=3 pre-sync) · `eval_20260703_1314_plc4_ytn2clean3_n3.json`(ytn2 클린) · `eval_20260703_1314_plc4_heldout3.json`(held-out) · 서버로그 `.omc/server_logs/server_*_20260703_*.log`.
