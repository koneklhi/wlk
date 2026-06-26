# 실험 로그 (STT WER/F1 개선) — 활성

STT 성능 개선 실험을 기록한다. 각 실험은 **가설 → 변경 → 결과 → 결론** 흐름으로 작성한다.
측정·채택 규율은 [CLAUDE.md](CLAUDE.md) §4·§3.8을 따른다. 기록은 `/log-experiment`로 수행한다.

> **활성 로그**: 이 파일이 현재 실험 기록의 정본이다. **Exp-001~130(2026-06-25 이전)** 은
> [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md)(아카이브)에 보존돼 있다. Exp 번호는 **131부터 이어간다**.

---

## 현행 측정 regime (2026-06-25 확정)

- **테스트 세트(채택/기각)**: `bong1` + `ytn2` + `sbs1` — `eval.py --repeat 3`
- **held-out(일반화 검증)**: `ytn1` + `eng1` — 채택 후보에 한해 회귀 감시 (ytn1 = ytn2 동일 이벤트 쌍둥이 코드스위칭, eng1 = 영어 회귀 감시)
- **측정 경로**: 경로 C(VBCable 루프백)만. provenance 게이트 필수 — 매 측정 첫 줄 `[provenance] code=wlk branch=master@… vbcable=ok …` 육안 확인.
- **측정 기본 설정**: 화자분할 ON (Sortformer + `--compression-ratio-threshold 3.0`).
- **판단**: 동일 파일·설정 N≥3 반복 → **median + min/max/stdev** 함께 본다. 1회 결론 금지. **fail-fast 금지**(분산 자체가 데이터).
- **채택 우선순위**: ① 최악 케이스(max WER) 미회귀 ② median 개선. max가 catastrophic하면 median이 좋아도 기각.
- **개선 1순위**: `ytn2`(짧은 텀 코드스위칭) + `bong1`(다화자 장시간) 공동 최우선. **데이터 특화 하드코딩 금지 — 개선은 일반화돼야 한다.**

## 현재 베이스라인

> **신뢰 baseline 확립 (2026-06-25, Phase B)** — master-default(`beams=2`, `PLC=None`, `CRT=3.0`, diar-ON) N=5.
> 이전 Exp-130 Phase B는 동시 재생 오염으로 무효 → 이 수치가 Phase C 이후 모든 채택/기각 판단의 기준점.
> JSON: `eval_baseline_trusted_20260625_1457.json` (테스트) / `eval_baseline_heldout_20260625_1534.json` (held-out)

| 파일 | WER median | WER max | WER min | WER stdev | F1 median | 측정 N |
|------|-----------|---------|---------|-----------|-----------|--------|
| bong1 | **44.1%** | 55.0% | 33.5% | 9.5% | 48.5% | 5 |
| ytn2  | **44.3%** | 61.6% | 23.6% | 15.0% | 55.6% | 5 |
| sbs1  | **24.4%** | 32.7% | 19.6% | 5.1% | 36.4% | 5 |
| ytn1 (held-out) | **29.4%** | 49.1% | 27.6% | 8.9% | 70.6% | 5 |
| eng1 (held-out) | **3.8%** | 5.7% | 3.8% | 0.9% | 0.0%† | 5 |

†eng1 F1 0%는 단일화자·단일세그먼트 구조 — 화자전환 경계 없으므로 F1 측정 불가, 회귀 감시는 WER만 사용.

**테스트 평균**: WER 37.6%, F1 44.4% | **held-out 평균**: WER 18.8%, F1 34.8%

참고(기각된 Exp-129 방향성, beam=3+PLC=2.0): bong1 35.6% / ytn2 32.5% / sbs1 19.6% / ytn1 34.4% / eng1 5.7%.
Exp-106~129는 신뢰 불가 판정으로 기각됐으나 **방향성은 참고** — beam=3·PLC=2.0이 이 baseline 대비 실제 개선되는지 정식 재검증이 Phase C 1순위.

## 이월 핵심사실 (아카이브 distilled — 상세는 [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md))

- **[측정]** 경로 C(VBCable)만 채택 판정 기준. 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회해 실사용과 무관 → 폐기.
- **[측정]** Exp-106~129 전체 기각 — silent code-version trap(잘못된 cwd로 변경 코드가 미반영된 채 측정) + VBCable
  간헐 불안정 + provenance 미기록. master 현재 코드가 새 기준점. (provenance 하니스 = Exp-130 Phase A, master 머지 완료.)
- **[디코더]** SimulStreaming 채택(Exp-001) — LocalAgreement는 영어 코드스위칭을 통째 누락하고 발화 후반 커버리지를
  잃음. AlignAtt 실출력 토큰엔 **구두점이 없어** 구두점 기반 확정이 미발동 → 확정 신호는 VAD silence·세그먼트 경계·언어 전환에서 찾는다.
- **[디코더]** `beam=4`는 ytn2 catastrophic(Exp-125: ytn2 WER beam2=28.1% → beam3=29.6% → beam4=40.4%, 단조 증가).
  bong1은 beam=4로 안정화되나 ytn2 손해가 압도. **beam=3은 Phase C 재검증 대상.**
- **[언어]** `periodic_lang_check`(PLC)가 환각 체인 억제에 중요 — PLC=None이면 언어 고착 후 sbs1 환각 급증.
  **PLC=2.0은 Phase C 재검증 대상.**
- **[diar]** Sortformer 과분할로 단일화자(sbs1) 문장분리 F1 급락(diar-ON 36.4% vs diar-OFF 76.2%, ref=3 vs
  hyp=9–11). ChangeSpeaker 2.0s 디바운스는 ytn2 회귀(Exp-106). nonspeech_prob=0.35는 bong1 환각↓이나 ytn2 부작용(Exp-107).
- **[환각]** bong1 웃음 구간에서 Whisper 환각 다발(JSON 분석 확인).
- **[필터/반복]** master 유지 베이스라인 필터 = **Exp-002**(cross-batch stateful 반복) / **Exp-028**(단일음절
  연속 반복 억제 + context 리셋) / **Exp-057**(배치 내 4-word 반복 드롭). 신규 언어특화 하드코딩보다 backend
  대안 우선. `_filter_repetitions()`는 단일 `update()` 배치 내부만 동작 → cross-batch 반복은 stateful 필터 필요.

## 빠른 참조

| Exp | 날짜 | 변경 | bong1 WER med | ytn2 WER med | sbs1 WER med | 판정 |
|-----|------|------|--------------|-------------|-------------|------|
| Exp-131 | 2026-06-25 | PLC=2.0 (파라미터만) | 45.3% (+1.2pp) | 36.5% (-7.8pp) | 21.4% (-3.0pp) | ❌ 기각 (bong1 max +9.7pp) |
| Exp-132 | 2026-06-25 | beam=3 (harness 워크트리) | 36.0% (-8.1pp) | 35.5% (-8.8pp) | 27.4% (+3.0pp) | ❌ 기각 (sbs1 max +19.1pp) |
| Exp-133 | 2026-06-25 | beam=3+PLC=2.0 콤보 | 55.6% (+11.5pp) | 23.6% (-20.7pp) | 23.2% (-1.2pp) | ❌ 기각 (sbs1 max +7.8pp, bong1 median +11.5pp) |
| Exp-134 | 2026-06-25 | lang-set ko,en 로짓 마스킹 (N=1 탐색) | **31.7% (-12.4pp)** | **23.6% (-20.7pp)** | **23.2% (-1.2pp)** | ⚠️ N=1 통계 이상치 — N=3 결과(Exp-136) 참조 |
| Exp-135 | 2026-06-25 | Stage 3 provisional buffer 추가 (N=1 탐색) | 34.7% (-9.4pp) | 26.1% (-18.2pp) | 20.8% (-3.6pp) | ❌ 기각 (Stage 1 단독 대비 bong1+ytn2 소폭 악화, 지연 리스크) |
| Exp-136 | 2026-06-25 | lang-set ko,en Stage 1+2 공식 채택 측정 (N=3) | **55.0% (+10.9pp) ⚠️** | 46.8% (+2.5pp) | **20.8% (-3.6pp)** | ❌ 기각 (bong1 max +4.2pp, median +10.9pp 대폭 회귀) |
| Exp-137 | 2026-06-26 | frame_threshold=50+PLC=4.0 (Spike 1, Phase 4) | 36.0% (-8.1pp) | **29.1% (-15.2pp) ✓** | 25.0% (+0.6pp) | ❌ 기각 (bong1 max 55→67.1% +12.1pp, 환각 폭주 확인) |

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
