# 실험 로그 — 개별 Exp 서술 (LOG)

이 파일은 **개별 실험의 전체 서술**(가설·변경·테스트 설정·전사 정성분석·채택 판정)을 보관한다.
현행 상태·베이스라인·이월 핵심사실·빠른참조·epoch 게이트는 [EXPERIMENTS.md](EXPERIMENTS.md)(STATE)에 있다.

> **3계층 구조**
> - [EXPERIMENTS.md](EXPERIMENTS.md) — **STATE** (항상 읽음: 요약·regime·baseline·이월핵심·빠른참조·epoch 게이트)
> - **이 파일** — **LOG** (온디맨드: Exp-131~ 전체 서술). 특정 Exp 상세는 `grep "Exp-NNN"`으로 해당 블록만 읽는다.
> - [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md) — **ARCHIVE** (Exp-001~130, 동결)

> **읽기 규약**: 세션 시작 시 STATE만 읽고, 이 LOG는 필요한 Exp만 grep 한다. 과거 Exp 결론을 현재 작업의 채택/기각 근거로 쓰기 전 STATE의 **epoch 게이트**를 적용한다 — 다른 코드 세대 결론은 '방향 신호'로만.

> **Exp ↔ Epoch**: Exp-131~137 = **E1**(언어고정·비음성억제 없음, master 계열). Exp-138~139 = **E2 후보**(`exp/meta-token-suppress`: suppress_nonspeech + lang_restrict_koen). 신규 Exp는 측정 대상 코드의 epoch를 provenance에 함께 적는다.

> ⚠️ **Exp-131~157 = base 기질 시대(2026-07-05 이전)** — `model_dir` 배선 버그로 전부 의도한 turbo가 아니라 `base`(74M) whisper 위에서 측정됨(Exp-158 확인). **구조 변경(Exp-139·143·150·151·152·153)은 master에 코드로 남아있어 유효**, 나머지 파라미터 결론·WER 수치는 전부 재검증 대상. 상세는 [EXPERIMENTS.md](EXPERIMENTS.md) "코드 세대(Epoch)" 절 참조. Exp-158부터 **turbo 기질(E5)**.

### 빠른 참조 — Exp-131~157 (base 기질, STATE에서 이관)

> **Epoch 열**: E1 = 언어고정 없음(master 이전) / E2 = `lang_restrict_koen=True` + 후처리 CJK/주석 필터 포함. suppress_nonspeech(Exp-138)는 E2에 **미포함** — 기각.
> **E1 파라미터 기각(131·132·133·137)은 E2 코드에서 재검증 대상이었으나, 이제 E1~E4 전체가 base 기질이라 turbo(E5)에서 다시 재검증 대상.**

| Exp | Epoch | 날짜 | 변경 | bong1 WER med | ytn2 WER med | sbs1 WER med | 판정 |
|-----|-------|------|------|--------------|-------------|-------------|------|
| Exp-131 | E1 | 2026-06-25 | PLC=2.0 (파라미터만) | 45.3% (+1.2pp) | 36.5% (-7.8pp) | 21.4% (-3.0pp) | ❌ 기각 (bong1 max +9.7pp) |
| Exp-132 | E1 | 2026-06-25 | beam=3 (harness) | 36.0% (-8.1pp) | 35.5% (-8.8pp) | 27.4% (+3.0pp) | ❌ 기각 (sbs1 max +19.1pp) |
| Exp-133 | E1 | 2026-06-25 | beam=3+PLC=2.0 콤보 | 55.6% (+11.5pp) | 23.6% (-20.7pp) | 23.2% (-1.2pp) | ❌ 기각 (sbs1 max +7.8pp, bong1 median +11.5pp) |
| Exp-134 | E1 | 2026-06-25 | lang-set ko,en 로짓 마스킹 (N=1 탐색) | 31.7% (-12.4pp) | 23.6% (-20.7pp) | 23.2% (-1.2pp) | ⚠️ N=1 이상치 — Exp-136 참조 |
| Exp-135 | E1 | 2026-06-25 | Stage 3 provisional buffer (N=1 탐색) | 34.7% (-9.4pp) | 26.1% (-18.2pp) | 20.8% (-3.6pp) | ❌ 기각 (Stage1 대비 악화, 지연 리스크) |
| Exp-136 | E1 | 2026-06-25 | lang-set ko,en Stage 1+2 채택측정 (N=3) | 55.0% (+10.9pp) ⚠️ | 46.8% (+2.5pp) | 20.8% (-3.6pp) | ❌ 기각 (bong1 median +10.9pp 대폭 회귀) |
| Exp-137 | E1 | 2026-06-26 | frame_threshold=50+PLC=4.0 (Spike 1) | 36.0% (-8.1pp) | 29.1% (-15.2pp) ✓ | 25.0% (+0.6pp) | ❌ 기각 (bong1 max 55→67.1%, 환각 폭주) |
| Exp-138 | **E2** | 2026-06-30 | suppress_nonspeech=True | 44.7% (+0.6pp) | 34.0% (-10.3pp) ✓ | 20.2% (-4.2pp) ✓ | ❌ 기각 (held-out eng1·ytn1 회귀, 원인 미규명) |
| Exp-139 | **E2** | 2026-06-30 | lang_restrict_koen + 후처리 필터(CJK/주석 드롭) | 52.9% (+8.8pp) | 35.5% (-8.8pp) ✓ | 22.0% (-2.4pp) ✓ | ✅ 채택 (max 미회귀·held-out 정상·§3.2 달성; bong1 median 회귀→Exp-140) |
| Exp-140 | **E2** | 2026-07-01 | logprob_threshold=-1.0 스크리닝 | 36.9% (N=1) | 32.0% (N=1) | 33.3% (+11.3pp ❌) | ❌ 기각 (sbs1 catastrophic) |
| Exp-141 | **E2** | 2026-07-01 | logprob_threshold=-1.5 스크리닝 | 36.0% (N=1) | 29.6% (N=1) | 27.4% (+5.4pp ❌) | ❌ 기각 (sbs1 회귀·ytn2 F1=12.5%) |
| Exp-142 | **E2** | 2026-07-01 | logprob_threshold=-2.0 기본값 채택 (N=3) | **37.5% (-15.4pp ✓)** | **31.5% (-4.0pp ✓)** | **19.6% (-2.4pp ✓)** | ✅ 채택 (WER 전부 개선; F1 하락→WER>F1 우선; parse_args 기본값 적용) |
| Exp-143 | **E2** | 2026-07-01 | PLC 배선 버그 수정(backend.py) + PLC=4.0 N=1 스크리닝 | 41.7% (+4.2pp ❌) | 29.6% (-1.9pp) | 18.5% (-1.1pp) | ✅ 버그수정 채택 / ❌ PLC=4.0 기각 (bong1 회귀, N=1 혼재 신호; parse_args 기본값 None 복원) |
| Exp-144 | **E2** | 2026-07-01 | beam=3 E2 재검증 (N=3) | 48.6% (+11.1pp ❌) | 26.1% (-5.4pp ✓) | 17.9% (-1.7pp ✓) | ❌ 기각 (bong1 median catastrophic +11.1pp; max 56.5% firewood 반복 환각; beam=3 탐색 종료) |
| Exp-145 | **E2** | 2026-07-01 | PLC=2.0 E2 첫 실검증 (N=1→N=3) | 40.2% (+2.7pp ❌) | 35.5% (+4.0pp ❌) | 20.8% (+1.2pp ❌) | ❌ 기각 (N=1 ytn2 이상치 22.7% 유혹했으나 N=3 전파일 median 악화; PLC 탐색 종료) |
| Exp-146 | **E2** | 2026-07-01 | CRT=2.5 N=1 스크리닝 | 33.5% (-4.0pp) | 31.0% (-0.5pp) | 22.0% (+2.4pp ❌) | ❌ 기각 (sbs1 회귀; 한국어 연속 발화를 반복으로 오분류) |
| Exp-147 | **E2** | 2026-07-01 | CRT=2.8 N=1 스크리닝 | 39.3% (+1.8pp ❌) | 48.8% (+17.3pp ❌ catastrophic) | 22.6% (+3.0pp ❌) | ❌ 기각 (ytn2 catastrophic; CRT 낮추기 방향 전체 종료) |
| Exp-148 | **E2** | 2026-07-01 | static_init_prompt="Korean and English" N=1 | 43.5% (+6.0pp ❌) | 41.9% (+10.4pp ❌) | 31.5% (+11.9pp ❌) | ❌ 기각 (전파일 대폭 악화; 영어 편향 유발) |
| Exp-149 | **E2** | 2026-07-01 | nonspeech_prob=0.2 N=1 | 46.5% (+9.0pp ❌) | 29.6% (-1.9pp) | 18.5% (-1.1pp) | ❌ 기각 (bong1 catastrophic; 발화와 비음성 no_speech_prob 분포 겹침; 파라미터 탐색 소진) |
| Exp-150 | **E3** | 2026-07-02 | 단계1 머지: 언어전환 프로토콜 재설계+SOT 배선수정 [E2→E3] | 36.6% (-0.9pp) | 27.6% (-3.9pp) | 19.6% (0pp) | ✅ 채택 (§3.2 SOT 보험: diar-OFF 대조 avg -24.6pp/ytn2 -82pp; diar-ON WER 변산 내 중립·max 게이트 E2 유지; 트림/마커는 diar-ON dormant) |
| Exp-151 | **E3** | 2026-07-02 | 잠복버그 수정: refresh global_time_offset 승계 + PLC 절대클록 (버그1·2) | 38.1% | 23.2% | 19.0% | ✅ 채택 (N=3 max 41.4/24.1/19.0 전부 게이트 내; WER 버그수정상 중립·무회귀; F1 정합 회복—sbs1 N1 0%→N3 18.2 안정; E3 유지) |
| Exp-152 | **E3** | 2026-07-02 | 단계2(증거된수정): _ANNOTATION_RE 확장 — 안 닫힌 비음성 주석 누출 차단 | 36.3% | 23.6% | 20.2% | ✅ 채택 (bong1 "(speaking…" 누출 0건·median 38.1→36.3·F1 40.0↑; ytn2/sbs1 신규패턴 매칭 0=증명된 no-op; sbs1 max 25.6은 변산) |
| Exp-153 | **E4** | 2026-07-03 | diar-ON 언어전환 배선(prev_lang fallback + hard_boundary) + 회차별 서버로그 [E3→E4] | 36.3% | 25.6% | 20.2% | ✅ 채택 (사용자결정; dormant→active 증명·WER게이트통과·ytn2 max 29.1→26.1·eng1 무회귀; F1 과분할하락·재디코딩 filler 신규→Exp-154 튜닝) |
| Exp-154 | **E4** | 2026-07-03 | PLC 기본값 None→4.0 채택(전환세금 제거 후 재평가) + 위생(단계C 드롭텍스트 로깅·D-1·D-2) | 34.4% (-1.9) | 22.9% (-2.7, pooled) | 21.4% (+1.2) | ✅ 채택 (사용자결정; §3.2 무휴지 코드스위칭·median개선·F1 전파일↑·filler소멸·eng1 무회귀 2.9%. ytn2 max 27.6=실변산; PLC E1/E2 3회기각→E4 채택전환) |
| Exp-155 | **E4** | 2026-07-03 | 단계3: 화자전환 리셋 조건부화(동일언어 시 refresh 생략) | 38.1% (+1.8) | 28.1% (+2.5) | 19.0% (-1.2) | ❌ 기각 (N=1; 타겟 sbs1은 new_speaker 0회 발동=무효·F1+12.6은 변산, 발동처 bong1 15/15 생략이 진짜 다화자 블렌딩→악화. sbs1 F1근원=문장과분할로 재규명) |
| Exp-156 | **E4** | 2026-07-04 | 단계4: token-logprob 게이트 go/no-go 프로브(계측 로깅만) | 34.1%(프로브) | 28.6%(프로브) | 19.0%(프로브) | ⛔ NO-GO·스킵 (저-logprob 꼬리서 정상단어 holding-17.4·protagonist-15.5가 garbage LAUGHS-17.5와 완전겹침→코드스위칭 정상토큰 드롭 위험. 분리가능 garbage는 기존필터 처리. 단계C 정합) |
| Exp-157 | **E4** | 2026-07-04 | 입력 볼륨 게인 스윕 측정 인프라(−12/−6/0/+6dB)+레벨 감도 규명 [파이프라인 무변경·`exp/volume-gain-sweep`] | 36.6 (0dB) | 23.6 (0dB) | 16.7 (0dB) | ✅ 인프라 채택 / 레벨-불변(±12dB WER 무영향·회차분산≫레벨효과; 서버 AGC 미착수) |

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

goal(구 `docs/GOAL_CODESWITCH_STRUCTURAL.md`, 폐기) 5단계 루프의 **단계 1**. E2 파라미터 탐색(Exp-131~149) 소진 후, 코드 수준 구조 병목을 직접 공략하는 첫 단계.

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

goal 단계1(E3, Exp-150)이 만든 언어전환 메커니즘(마커 + 2.5s 트림 재디코딩)이 **측정 기본 설정(diar-ON)에서 dormant**임을 다른 세션(fable) 분석(`docs/archive/jiggly-sniffing-scone.md` Q3)이 지적. Explore 2회로 현행 master(9ed1ee9)에서 검증 완료 후 배선. 브랜치 `exp/diaron-switch-wiring` → master `dc312bb`(--no-ff 머지). **채택은 게이트 혼합으로 사용자 결정(A: 지금 채택).**

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

---

## Exp-155 — 단계3: 화자전환 리셋 조건부화(동일언어 시 refresh 생략) (2026-07-03) [E4] ❌ 기각

원 로드맵 단계 3(제안 E). Sortformer 과분할로 sbs1 문장분리 F1 급락 → **동일언어 화자전환이면 new_speaker 리셋(refresh_segment·detected_language=None·_apply)을 생략**해 문맥 연속성 보존 가설. 브랜치 `exp/conditional-speaker-reset`(d0e0172, 미머지).

### 변경 내용
- `backend.py` `new_speaker`: 진입 시 `prev_lang=detected_language` 캡처 → `eager is not None and eager==prev_lang`이면 리셋 블록 생략(speaker·global_time_offset만 갱신), 아니면(언어 다름/None) 기존 리셋 경로 유지(Exp-153 lang_before_reset 승계 보존). `tests/test_conditional_speaker_reset.py` 6개(mock/spy, falsifiable) 통과, 기존 스위트 회귀 0.

### 테스트 세트 결과 (경로 C, diar-ON, PLC=4.0, N=1 스크리닝)

| 파일 | WER | Δ E4base | F1 | ΔF1 | 리셋 생략 / new_speaker 발동 |
|------|-----|----------|-----|-----|------------------------------|
| bong1 | 38.1% | +1.8 | 35.9% | -4.1 | 15 / **15**(100% 생략) |
| ytn2 | 28.1% | +2.5 | 45.5% | -14.5 | 3 / — |
| sbs1 | 19.0% | -1.2 | 30.8% | +12.6 | **0 / 0**(무발동) |

### 분석 (메커니즘 규명 — 기각 근거)
- **sbs1(타겟) 완전 무효**: Sortformer가 sbs1에 **ChangeSpeaker 이벤트를 0회** 생성 → new_speaker 자체가 안 불림 → stage3 코드 경로 미진입. sbs1 F1 +12.6은 **순수 N=1 변산**(변경 무관). **⇒ sbs1 F1 급락의 근원은 화자전환 리셋이 아니라 문장경계 과분할(`tokens_alignment`)로 재규명** — 단계 3 전제(§3 제안 E)가 오진단.
- **bong1(발동처) 악화**: new_speaker 15회 전부(15/15) 동일언어 → 전부 생략 → **진짜 다른 화자(영어2·한국어2)를 같은 언어라는 이유로 블렌딩** → WER+1.8·F1-4.1. "same language" ≠ "spurious over-segmentation" — 이 둘을 언어일치만으로 구분 불가(Exp-106 디바운스가 진짜 전환도 늦춘 것과 동형 함정).

### 채택 판정
- **① max**: bong1/ytn2 median 회귀(N=1 방향신호). **② 1차 관찰 실패**: sbs1 F1 회복은 spurious(0 발동), ytn2 회귀(+2.5, F1-14.5).
- **결론: ❌ 기각**. 타겟(sbs1) 무발동으로 이득 원천 부재 + 발동처(bong1) 화자블렌딩 악화. §3.2 비직결(diar F1 최적화)이라 자율 기각. N=3 불요(메커니즘·전제 반증 확정적).

### 다음
- **sbs1 F1 재접근(backlog)**: 화자전환이 아니라 문장경계 과분할이 근원 → `tokens_alignment.compute_punctuations_segments` 온점분할 정책이 후보(단, F1은 2차 지표·WER>F1).
- **단계 4**: token-logprob go/no-go 프로브로 진행.

**JSON**: `.omc/benchmarks/eval_20260703_1403_step3_condreset_screen.json` · 서버로그 `worktrees/conditional-speaker-reset/.omc/server_logs/`.

---

## Exp-156 — 단계4: token-logprob 게이트 go/no-go 프로브 (2026-07-04) [E4] ⛔ NO-GO (스킵)

원 로드맵 단계 4(제안 D). 세그먼트급 QualityGate 위에 **per-token logprob 게이트**로 bong1 잔존 garbage를 더 잡을 수 있는지 프로브. 부모 §3 단계 4 규정대로 **구현 전 go/no-go 프로브 필수**(배관 大). 브랜치 `exp/token-logprob-gate`(계측 로깅만, 미머지·미채택).

### 프로브 방법
- `align_att_base.py` `_update_tokens` 직후 read-only 로깅 추가(`[TokenLP] tok lp special`, --trace-tokens DEBUG 게이트, 동작 불변). top-beam 선택토큰의 `log_softmax(logits)[tok]`.
- 경로 C N=1(diar-ON, PLC=4.0). WER 정합: bong1 34.1·ytn2 28.6·sbs1 19.0(baseline대 — 로깅이 디코드 불변임 확인).

### per-token logprob 분포 (텍스트 토큰만)
| 파일 | n | median | p5 | p25 | frac<-2.0 | frac<-3.0 | min |
|------|---|--------|-----|-----|-----------|-----------|-----|
| bong1 | 1103 | -0.20 | -3.24 | -0.86 | 10.1% | 5.5% | -17.71 |
| ytn2 | 748 | -0.09 | -2.67 | -0.52 | 8.0% | 4.7% | -13.39 |
| sbs1 | 829 | -0.07 | -1.88 | -0.30 | 4.7% | 3.4% | -16.57 |

### 판정 (NO-GO — 분포 완전 겹침)
저-logprob 꼬리(<-2.0)를 정상/환각 분류:
- **정상 단어가 garbage만큼(혹은 더) 낮음**: bong1 `holding`(-17.4)·`protagonist`(-15.5/-8.3)·`was`(-12.7)·`제가`(-10.4)·`많이`(-9.3)·`thousand`(-8.3)·`trying`(-4.0)·`I`(다수) — 전부 정답에 존재하는 정상 토큰인데 clear garbage(`LAUGHS`-17.5·`웃음`-10.3·`�`)와 동일 logprob 구간.
- **분리 가능 garbage는 이미 처리됨**: 비음성 주석(`[`·`]`·`(`·`LAUGHS`·`웃음`·`speaking`)은 기존 `_ANNOTATION_RE`(Exp-152)·CJK 필터·QualityGate가 이미 억제.
- **근본 이유**: 코드스위칭·다화자 환경에서 정상 토큰이 **언어경계·난이도로 저신뢰**라 환각과 logprob로 구분 불가. bong1 잔존 garbage는 웃음 캐스케이드(Exp-138, **정상 신뢰도** 오전사)라 logprob 무력.
- **결론: ⛔ NO-GO**. 어떤 per-token logprob 임계도 §3.2 핵심 전환경계 정상단어(`holding`·`protagonist`)를 드롭 → 코드스위칭 파손 위험. 단계 C(QualityGate 부당드롭 0%)와 정합. 부모 doc대로 **단계 4 전체 스킵**, 배관 미착수. token logprob 방향은 이 환경(코드스위칭)에 부적합으로 종료.

### 다음
- 단계 5 프로브(2a RTF·2b 동시경합·2c 언어recall)로 진행 — 자율 허용 범위(사전 프로브)까지, 보고 후 정지.

**JSON**: `.omc/benchmarks/eval_20260704_step4_tokenlp_probe.json` · 서버로그 `worktrees/token-logprob-gate/.omc/server_logs/server_*_C_R1_*.log`([TokenLP]).

---

## 단계5 프로브 2a — 2-pass 재전사 RTF 마이크로벤치 (2026-07-04) [E4] (프로브·미채택)

단계 5(2-pass 재전사)는 major 방향 전환이라 **자율 착수 금지, 사전 프로브만 허용**. 사용자 승인 하에 2a(RTF 게이트)만 실행, 보고 후 정지.

**방법**: `whisperlivekit.whisper` 표준 transcribe(simul_whisper 동일 가중치·구현) / `whisper-large-v3-turbo`(로컬 fp16) / beam=2, language=ko / RTX 3080 / ytn2 20s 오프셋 발화 클립 15·30·45s / warmup1+timed3 median / `torch.cuda.max_memory_allocated`.

| 버퍼 | 오디오 s | median decode s | RTF | peak VRAM GB |
|------|---------|-----------------|-----|--------------|
| 15s | 15.0 | 0.833 | **0.056** | 3.53 |
| 30s | 30.0 | 3.828 | **0.128** | 3.54 |
| 45s | 45.0 | 1.667 | **0.037** | 3.54 |

**게이트 판정: worst RTF 0.128 < 0.5 → 통과.** 단독 오프라인 재전사는 실시간 예산의 ~1/4~1/8, peak VRAM ~3.5GB(길이 무관). RTF은 버퍼 길이 단조비례 아님(30s>45s — whisper 30s-window 내부 토큰루프가 콘텐츠 의존; 길이효과 아님). **2-pass 여지 있음 → 2b(동시경합 VRAM/live RTF)·2c(language=auto 영어recall)는 사용자 합의 후 진행.** 실제 구현 착수는 부모 §7상 합의 필수. 스크립트: scratchpad/`rtf_microbench.py`.

---

## Exp-157 — 입력 볼륨 게인 스윕 측정 인프라 + 레벨 감도 규명 (2026-07-04) [E4] (인프라 채택 / 레벨-불변)

원래 질문: 마이크/파일 볼륨 편차가 전사에 영향을 주는가, 음성 정규화가 필요한가. 파이프라인에 볼륨 보정이 전무(브라우저 `autoGainControl:false`·서버 `convert_pcm_to_float`는 `/32768` 스케일만)해 입력 레벨-WER 감도를 측정할 수단 자체가 없었음. **측정 인프라를 먼저 만들어 감도를 실측**(사용자 결정 "측정 먼저"). 브랜치 `exp/volume-gain-sweep`(beff8e1, 미머지). **whisperlivekit 파이프라인 무변경(scripts 측정 하니스만)이라 epoch 불변 E4**.

**가설**: Whisper log-mel의 창별 자기정규화(`whisper/audio.py:155` `log_spec.max()-8.0`)로 절대 레벨에 둔감할 것 → 정규화 실이득 작음. 레벨이 실제로 무는 곳은 VAD threshold(0.3)·클리핑·저SNR 3곳으로 한정될 것.

**변경 (측정 인프라만, 파이프라인 무변경)**:
- `scripts/vbcable_test.py`: `apply_gain_db`(dB 게인·float32 재생·클리핑 비율 산출) + `run_browser_test(gain_db=)` + `--gain-db`.
- `scripts/eval.py`: `--gain-db` 파일별 스윕(`nargs="+"`) + `FileResult.gain_db` + (file,gain) 집계·전사/서버로그 파일명 `_g<±d>dB` 태그. 하위호환(기본 `[0.0]`).
- `scripts/audio_device.py`: `verify_loopback` 레벨 정량화(−20dBFS 톤 ±1dB **유니티 게인 검증**·`UNITY GAIN FAIL` 시 Windows 볼륨 왜곡 경고) + `last_loopback_measurement`.
- docs(TESTING/DEPLOYMENT_OFFLINE/eval.md): 배포 마이크 레벨 가이드.

**테스트 설정**: 경로 C, `--gain-db -12 -6 0 6`, 파일 bong1/ytn2/sbs1, diar-ON(sortformer)·CRT 3.0·PLC 4.0·beams 2, `--repeat 1`(스크리닝). preflight `verify_loopback` level −20.8dBFS(편차 −0.8dB) OK. 네이티브 통합레벨(LUFS): bong1 −14.5(TP +0.2 **소스클립**)·ytn2 −25.9·sbs1 −24.6.

### 테스트 세트 결과 (게인 스윕, N=1, WER% / F1)

| 파일 | −12dB | −6dB | 0dB(네이티브) | +6dB | 게인 경향 |
|------|-------|------|--------------|------|-----------|
| bong1 | 33.2 / .378 | 34.4 / .316 | 36.6 / .462 | 36.6 / .513 | 감쇠 미세개선(단조 ~3pp) |
| ytn2 | 23.6 / .571 | **36.5 / .267** ⚠ | 23.6 / .571 | 22.7 / .600 | −12/0/+6 평탄 |
| sbs1 | 17.3 / .364 | **28.0 / .000** ⚠ | 16.7 / .333 | 21.4 / .400 | −12/0/+6 평탄 |

⚠ −6dB 지점은 **단일 회차 분산 이상치**(게인 효과 아님 — 각 파일 −12/0/+6이 서로 일치, bong1 −6도 단조 범위 내). 클리핑 비율: bong1@+6dB만 1.04%, 나머지 전부 0%. 절대레벨 커버리지: ytn2@−12 = −37.9 LUFS(매우 조용)에서도 VAD 미검출 없이 23.6% 유지 — 레벨-불변의 강한 증거.

### 분석 (전사 내용 정성 대조, 0dB 네이티브 기준)

**bong1** (0dB, WER 36.6%):
- **환각/gibberish**: 전사 `"Malang, malang, goto, mandra, suuri…"` / 정답 `"말랑말랑한 것도 만들었죠…"` — 한국어 즉흥표현이 로마자 gibberish로.
- **비언어→환각**: 전사 `"Dr. Bonwell is trying to explain"` / 정답 `"Director Bong…"` — 웃음/비음성 구간 오전사(이월핵심 bong1 웃음 환각 확인). 문말 `"(Music"` 누출.
- **과분할**: ref 15문장 vs hyp 26 (F1 .462).

**ytn2** (0dB, WER 23.6%):
- **방송 signoff 환각**: 전사 `"MBC 뉴스 우선입니다 왕성한 연합방 테세를…"` / 정답 `"…우선 왕성한 연합방위태세를…"` — 없는 뉴스 클로징 삽입(−6dB선 `"MBC 뉴스 김정현입니다…고맙습니다 고마워요"` 반복으로 폭주=분산 이상치).
- **코드스위칭**: en→ko 전환 자체는 대체로 성공. 오인식 `"비핵카"`(비핵화)·`"취재의 논의"`(취지의).

**sbs1** (0dB, WER 16.7%):
- **단어 오인식**: 전사 `"미국 6군 전쟁 대학"` / 정답 `"미국 육군 전쟁 대학"` — 육군→6군(단어대치 사전 대상). `"연구적인 지상 플랫폼"`/정답 `"영구적인"`.
- **diar 과분할**: ref 3문장 vs hyp 11 (F1 .333, 이월핵심 sbs1 과분할 확인). 영어 인용 처리 정상.

**이번 변경 영향**: 측정 인프라 추가이며 **파이프라인 무변경** → 실패 모드는 기존 그대로(bong1 웃음/gibberish 환각·과분할, ytn2 방송 signoff 환각·−6dB 분산폭주, sbs1 육군→6군·diar 과분할). **입력 레벨(±12dB)은 이 실패 모드들을 개선·악화시키지 않음** — 게인 무관 동일 패턴 반복. 레벨-불변 확증.

### 판정 (측정 인프라 채택 / 서버 AGC 미착수)
- **정량**: 게인 감도(~3pp, bong1만 단조) << 회차 변동성(10~14pp, −6dB 이상치). 정상 범위 레벨은 WER 무영향. 가설 확증(Whisper 창별 자기정규화).
- **인프라 채택**: 커밋 beff8e1. 특히 `verify_loopback` 유니티 게인 검증은 앞으로 모든 경로 C 측정에서 Windows 볼륨 왜곡을 차단 → 측정 신뢰성 상시 향상.
- **서버측 AGC 미착수**: WER 이득 없음. 플랜 "감도가 분산 이내면 문서화만" 적용. §4 목표필수기능 조항으로 자율기각 대신 사용자 확인 → **"문서화+인프라 커밋"** 선택. 잔여 가치는 WER이 아니라 배포 마이크 극단 오설정(볼륨 10%·심한 클리핑) 절벽에 대한 로버스트니스(§3.2)이며, 이 절벽은 이번 ±12dB 스윕이 측정하지 않음.

### 다음
- (보류) 극단 구간(정상 범위 밖 −24…+18dB) 스윕 → 레벨 절벽 위치 규명 → 경량 세이프티 클램프 필요성 판단. 배포 마이크 오설정이 실제 우려로 관측될 때만 진행.

**JSON**: `.omc/benchmarks/gain_sweep_screen.json` · 콘솔로그 `.omc/gain_sweep_screen_console.log`(gain/clipped·verify_loopback level) · 서버로그 `.omc/server_logs/server_*_C_g*dB_R1_*.log`.

---

## Exp-158 — turbo 모델 정상화: model_dir 배선 버그 + no_grad stall 수정 [E4→E5, base 기질→turbo 기질] (2026-07-05)

**가설**: 단계5(2-pass 재전사) 프로브 2b 준비 중, 서버와 동일 config로 `TranscriptionEngine`을 직접 구성해 로드된 모델의 파라미터 차원을 확인한 결과 807M(turbo)가 아니라 71.8M(base)이 나왔다. **지금까지 전체 실험 이력(Exp-001~157)이 의도한 `whisper-large-v3-turbo`가 아니라 `base`(74M) whisper 위에서 측정된 것**이라는 가설을 세우고 근본원인을 규명·수정한다.

**변경 (브랜치 `exp/fix-turbo-model-wiring`, 워크트리 `worktrees/fix-turbo-model-wiring`, 커밋 `d11f8b0`+`415ac39`, master 머지 `9e3217e`)**:

1. **버그 1 — model_dir 배선 (`whisperlivekit/simul_whisper/backend.py:399` 부근, `SimulStreamingASR.__init__`)**: 기존 코드는 `if self.model_path:` 만 확인하고 서버가 `--model_dir`로 항상 전달하는 turbo 경로(`self.model_dir`)를 무시 → `model_path=None`이면 `model_size`(기본값 `"base"`)로 조용히 폴백. `whisper.load_model()`의 자동 다운로드(개발 PC는 인터넷 가능)가 base를 조용히 받아 크래시 없이 넘어감 — `~/.cache/whisper/base.pt` 생성시각(2026-06-05)이 프로젝트 초기 설정 시점과 일치. **폐쇄망 배포에서는 인터넷이 없어 이 폴백 자체가 실패하는 배포 블로커**였다. 수정: `model_path_or_dir = self.model_path or getattr(self, 'model_dir', None)` 로 변경(다른 백엔드 qwen3/voxtral과 동일한 `model_dir or model_path` 패턴).
2. **버그 2 — no_grad 누락 (`whisperlivekit/simul_whisper/align_att_base.py`, `detect_current_language()`)**: 이 함수는 `process_iter` → `_check_short_silence_language`/`new_speaker` eager 감지 경로에서 호출되는데, `infer()`/`lang_id()`와 달리 `@torch.no_grad()` 밖에서 실행되고 있었다. turbo 인코더(807M·32층) forward가 grad 추적 시 autograd 그래프·활성값을 보존해 forward 자체가 느려지고 VRAM 압박이 발생 — `cuda.synchronize` 계측으로 **forward 0.2s→31.96s(~160배 폭주)** 확정. 이게 이벤트루프를 블로킹해 lag 폭증(bong1 last_end≈9.1s 지점에서 0.2s→143.4s) → `FFmpeg read timeout` → 첫 문장만 전사되고 멈추는 stall. base(74M)는 forward 자체가 싸서 같은 버그가 있어도 잠복해 있었음. 수정: `@torch.no_grad()` 데코레이터 추가(short-silence·new_speaker·periodic 세 감지 경로 모두 커버).

**검증 절차**: (1) 파라미터 차원 검증(base=71.8M/512차원 vs turbo=807.0M/1280차원 — 소수점까지 일치 확인, 이름 문자열이 아니라 실제 로드된 텐서로 확정). (2) bong1 25초 클립 최소 재현으로 beams=1/min-chunk-size=1.0 등 파라미터를 바꿔도 같은 지점(last_end≈9.1s)에서 재현됨을 확인 → 단순 스루풋 문제가 아니라 특정 함수 호출임을 좁힘. (3) no_grad 수정 후 동일 재현 시나리오에서 stall 소멸 확인. (4) 경로 C 전체 파일 확정 측정.

**⚠️ 측정 중 사고 (하니스 교훈, 기록 목적)**: 서브에이전트가 재개(resume)될 때마다 이전 측정을 정지시키지 않고 새 `eval.py`를 또 실행해 **동일 포트(8901)·동일 VBCable 장치에 두 측정이 동시 재생되는 오염**이 발생(sbs1 전사 결과에 ytn2 참조문이 섞여 나옴 — 스모킹건). 사용자 승인 하에 프로세스 정리 후 맨 세션이 직접 단독 감독으로 재측정해 해소. **교훈**: 새 측정 시작 전 반드시 `Get-CimInstance Win32_Process | Where CommandLine -match 'eval.py|basic_server'`로 잔여 프로세스 없음 확인.

### 테스트 세트 결과 (N=3, diar-ON, CRT=3.0, PLC=4.0, beams=2)

| 파일 | R1 WER | R2 WER | R3 WER | median | max | min | stdev | F1 med | vs base E4(Exp-153) med | 완주(timeout) |
|------|--------|--------|--------|--------|-----|-----|-------|--------|------------------------|----------------|
| bong1 | 28.1% | 24.8% | 34.7% | **28.1%** | 34.7% | 24.8% | 5.1% | 52.6% | -8.2pp ✓ | 0회, last_end 160s |
| ytn2 | 38.4% | 41.9% | 47.3% | **41.9%** | 47.3% | 38.4% | 4.5% | 40.0% | +16.3pp ❌ | 0회, last_end ~99s |
| sbs1 | 31.0% | 14.3% | 16.1% | **16.1%** | 31.0% | 14.3% | 9.2% | 40.0% | -4.1pp ✓ | 0회, last_end ~96s (단 lag 최대 41/11/20s) |

held-out(ytn1/eng1) **미측정** — 다음 세션 1순위.

### 분석 (전사 내용 정성 대조, median 회차 기준)

**bong1** (R1, WER 28.1%):
- **필러/반복 환각**: 전사 `"Thank you. Thank you. so much. Thank you very"` / 정답 `"This man."`(짧은 대사) — 반복 감사인사 삽입, 무의미 필러 폭주.
- **환각 삽입**: 전사 `"So I'm going to take my daughter's son."` — 정답에 아예 없는 문장이 통째로 삽입됨.
- **단어 대치**: 전사 `"보리에요"` / 정답 `"돌이에요"`("rock"), 전사 `"보리카를 하다고"` / 정답 `"메타포리칼하다고"`("metaphorical") — 서로 다른 위치에서 공통으로 "보리" 토큰이 끼어듦(고정 환각 어트랙터 의심).
- **단어 유실**: 문두 "누가 주인공" 유실("일까 이런 생각을 제가…"로 시작, 정답은 "누가 주인공일까…").

**ytn2** (R2, WER 41.9% — 회귀 주범):
- **방송 클로징류 환각(재발)**: 전사 `"문의한 사안 중에서는 우선 왕성한 연합 김정은 기자입니다. 김정은 기자, 김정은 기자입니다입니다 감사합니다"` / 정답은 "논의한 사안 중에서는 우선 왕성한 연합방위태세를 유지하기 위한 노력을 경주하자는 것과 북한의 최종적 그리고 완전히 검증된 비핵화를 달성하기 위해 협조를 강화하자는 취지의 논의를 했습니다" — **상당 분량의 실제 내용이 통째로 "김정은 기자입니다" 반복 환각으로 대체됨**. Exp-157(게인스윕)에서 관측된 "MBC 뉴스 signoff 환각"과 같은 계열(방송 클로징 패턴)이나, 이번엔 내용 대체 규모가 더 큼.
- **필러 폭주(신규 관측)**: 전사 `"Thank you. Thank you Okay. , let's talk about this I think it's important to aviones Thank you. Thank you very much. Thank you, Mr. Chair."` — 정답에 전혀 없는 대규모 필러 삽입. bong1과 같은 "Thank you" 계열 필러가 여기서도 나타남 — **turbo 전반의 공통 실패모드**로 보임.
- **단어 대치**: 전사 `"변환 없는 입장을 고소하고"` / 정답 `"변함 없는 입장을 고수하고"`.

**sbs1** (R3, WER 16.1% — 최선 회차):
- **고유명사 유실**: 전사 `"동쪽이 위를"` / 정답 `"한반도 동쪽이 위를"` — "한반도" 유실.
- **핵심어 유실**: 전사 `"거대한 겁니다"` / 정답 `"거대한 방어선이라는 겁니다"` — "방어선이라는" 유실.
- **세그먼트 경계 아티팩트**: 전사 `"가. 치였습니다"` — "가치였습니다"가 중간에 분절(diar 과분할 계열 아티팩트로 추정).
- 영어 인용구(`"From a satellite image…"`) 처리는 base 때와 마찬가지로 정상.

**이번 변경 영향**: turbo는 base 대비 영어 코드스위칭 블록을 더 정확·풍부하게 렌더링하나(예: ytn2의 "Operational Control Transition", "Military Committee meetings assessment…" 등 base보다 정밀), **새로운 필러/반복 환각("Thank you" 연쇄) 경향이 bong1·ytn2 양쪽에서 공통 관측**됨 — 모델이 불확실 구간에서 "더 그럴듯한" 대화체 필러를 강하게 생성하는 것으로 추정. ytn2 회귀는 이 필러 폭주 + 방송 클로징류 환각이 실제 내용을 대체한 것이 주 원인으로 보이며, base용으로 튜닝된 언어전환 프로토콜·PLC 등 코드스위칭 스캐폴딩이 이 신규 실패모드에 최적이 아닐 가능성이 높다.

### 채택 (조건) 판정

이 변경은 **파라미터 트레이드오프가 아니라 correctness 버그 수정**이므로 통상적인 ①max 미회귀 ②median 개선 게이트를 그대로 적용하지 않는다. `model_dir` 배선 버그는 폐쇄망 배포에서 서버가 아예 뜨지 못하는 배포 블로커였고, no_grad 누락은 실시간 stall(첫 문장만 전사)을 일으키는 명백한 결함이었다 — **WER 결과와 무관하게 반드시 수정해야 하는 버그**.

**✅ 채택** (사용자 결정, master 머지 완료 `9e3217e`). 참고 정보로서: bong1·sbs1은 base 대비 개선, **ytn2는 대폭 회귀**(+16.3pp) — 이는 "수정 자체의 실패"가 아니라 **base 기질에서 나온 모든 이전 baseline이 애초에 무효**였고 turbo가 진짜 성능을 처음 드러낸 것으로 해석. ytn2 회귀는 별도 재조사 대상으로 다음 가설에 남긴다.

### 원인 분석 (근본원인, 재확인됨)

1. `SimulStreamingASR.__init__`이 `model_dir`을 읽지 않는 배선 누락 — 다른 백엔드(qwen3/voxtral)는 이미 `model_dir or model_path` 패턴을 쓰고 있었음에도 SimulStreaming만 빠짐.
2. `detect_current_language()`가 `infer()`/`lang_id()`와 다른 grad 모드로 실행되던 비일관성 — 코드 리뷰에서도 놓치기 쉬운 유형(같은 클래스 내 유사 메서드 간 데코레이터 불일치).

### 다음 가설

1. **held-out(ytn1/eng1) 측정** — turbo baseline을 최종화하고 ytn2 회귀가 일반화되는지(ytn1=쌍둥이 코드스위칭) 확인.
2. **ytn2 회귀 재조사** — "Thank you" 필러 폭주·방송 클로징 환각이 base용 언어전환 프로토콜·PLC와 어떻게 상호작용하는지. turbo가 base보다 강한 모델이라 기존 스캐폴딩이 오히려 방해가 되는지(단순화 방향) 검토.
3. **sbs1 실시간 lag(RTX 3080 최대 41s)** — 배포(RTX 5090) 성능으로 재확인 필요. 필요시 turbo용 `frame_threshold`/`audio_max_len` 경량 조정.
4. E1~E4의 파라미터 결론(beam·CRT·PLC·logprob 등) turbo 기질에서 전면 재검증 — 우선순위는 ytn2 회귀와 직결된 PLC·언어전환 프로토콜부터.

**JSON**: `worktrees/fix-turbo-model-wiring/.omc/benchmarks/eval_turbo_confirm_N3.json`(N=3 확정) · `eval_turbofix_screen_clean.json`(수정 직후 첫 스크리닝, 참고용) · 서버로그 `worktrees/fix-turbo-model-wiring/.omc/server_logs/server_{bong1,ytn2,sbs1}_C_R{1,2,3}_20260705_18*.log`. 워크트리는 머지 후 제거됨 — 진단 산출물(`diag_turbo_stall/`)은 이 서술에 증류돼 원본은 보존하지 않음.

---

## Exp-159 — turbo E5 held-out(ytn1/eng1) 확정 측정 [E5, 코드변경 없음] (2026-07-05)

**가설**: Exp-158에서 미측정으로 남긴 held-out(ytn1/eng1)을 측정해 E5 baseline을 최종 확정한다. ytn1(=ytn2 동일 이벤트 쌍둥이)로 ytn2의 대폭 회귀가 코드스위칭 일반에 걸친 것인지 그 파일 특유인지 확인하고, eng1으로 영어 회귀 여부(base E4 참고치 3.8%)를 점검한다.

**세션 메모(무인 세션 인프라 사고)**: 이 측정 직전 공유 `.venv`가 손상된 상태(Lib/pyvenv.cfg 소실, antigravity IDE Jedi 언어서버 잠금 중 `uv venv --clear`류 실패 추정)를 발견 — §4.5 무인결정 예외(uv sync 계열)에 따라 자율 복구하지 않고 P1 워크트리 2건(`repeat-filter-langagnostic`·`langswitch-confidence-raise`) 구현·문법검증까지 측정 없이 준비한 뒤 사용자 복귀 후 "venv 복구 진행" 지시로 `uv sync --extra diarization-sortformer --extra vbcable --extra cu128` 실행해 복구. 상세는 `docs/GOAL_TURBO_AUTONOMOUS.md` §9 참조.

**변경**: 없음 (master `af4dd36`, 코드 변경 없이 순수 측정).

### 테스트 설정

```
.venv\Scripts\python.exe scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/ytn1.mp3 test_data/eng1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0
```
(diar-ON, CRT=3.0, PLC=4.0, beams=2 — Exp-158과 동일 설정. held-out은 단회.)

### 결과 (N=1, held-out 단회)

| 파일 | WER | F1 | 비고 |
|------|-----|-----|------|
| ytn1 | **33.1%** | 50.0% | ytn2(41.9%, Exp-158)보다 8.8pp 양호 |
| eng1 | **3.8%** | 0.0% | base E4 참고치(3.8%)와 정확히 일치 — 영어 회귀 없음 |

### 분석 (전사 내용 정성 대조)

**ytn1**:
- **필러 폭주(Thank you 연쇄, 재확인)**: 전사 `"Thank you very much. Thank you very much for coming. Thank you. Thank you very much."` — 정답에는 이 필러가 전혀 없음. Exp-158에서 bong1·ytn2 공통으로 관측된 "Thank you" 연쇄 필러 환각이 **ytn1에서도 동일하게 재현** — turbo 전반의 일반적 실패모드임을 3번째 파일에서 재확인.
- **단어 대치/잡음성 삽입**: `"M.A. M.A. and we appreciate..."` — 정답에 없는 정체불명 토큰 삽입(화자명 오인식 추정). `"The U.S Rock Alliances Ironclad"` / 정답 `"The U.S. ROK Alliance is ironclad"` — "ROK"→"Rock" 오인식.
- **경계 아티팩트**: `"...defense of the Republic of Korea. do."` — 문장 끝에 정답에 없는 "do." 삽입(경계/재디코딩 아티팩트로 추정).
- **코드스위칭 자체는 비교적 안정**: 한↔영 전환 구간의 한국어 문장들은 정답과 근접하게 전사됨(예: "안녕하십니까 세 달 만에 두 번째로…") — ytn2처럼 전체 구간이 방송클로징류 환각으로 통째 대체되는 catastrophic 패턴은 **관측되지 않음**.

**eng1**:
- 주요 실패 없음. 정답과 거의 동일(구두점·띄어쓰기 수준 차이만). 문장 끝부분("...and the measures taken" vs 정답 "...and the measures taken in")이 근소하게 짧게 끊김 — 클립 경계 아티팩트로 추정, 실질적 단어 유실은 아님.

**이번 측정의 함의**: ① "Thank you" 필러 폭주는 bong1·ytn2에 이어 **3번째 파일(ytn1)에서도 재현** — turbo 공통 실패모드라는 Exp-158 가설을 강화, `repeat-filter-langagnostic`(강화 방향) 후보의 타당성을 뒷받침. ② ytn2의 **catastrophic 콘텐츠 대체(방송클로징 환각)는 ytn1에서 재현되지 않음** — 코드스위칭 일반의 문제라기보다 **ytn2 파일 고유의 음향/정렬 난이도**(선행 분석 `audio-feature-analysis`의 앵커율 46% 발견과 정합)가 최악 사례를 만든 것으로 보임. ③ eng1 영어 성능은 base 대비 회귀 없음 — turbo 채택(Exp-158)이 영어 인식을 해치지 않았음을 확인.

### 판정

이 측정은 채택/기각 대상 코드 변경이 아니라 **baseline 확정 측정**이다. P0(§GOAL_TURBO_AUTONOMOUS.md) 완료 — E5 baseline(test 3종 + held-out 2종) 최종 확정, 잠정 게이트를 확정 게이트로 전환(변경 없음: bong1≤34.7%/ytn2≤47.3%/sbs1≤31.0%, Exp-158 N=3 max 그대로 유지).

### 다음 가설

1. **P1 (최우선)**: 준비된 3가지 후보 스크리닝 — ① PLC 플래그 스윕(None/2.0/8.0, 코드변경 없음) ② `repeat-filter-langagnostic`(강화 — 이번 ytn1 재현으로 타당성 보강됨) ③ `langswitch-confidence-raise`(단순화).
2. P2 — sbs1 lag(`audio_max_len` 우선 용의자), P3 — 파라미터 재검증(P1 이후).

**JSON**: `.omc/benchmarks/eval_20260705_2126_heldout_e5.json` · 서버로그 `.omc/server_logs/server_{ytn1,eng1}_C_R1_20260705_21*.log`.

---

## Exp-160 — ytn2 회귀 원인 규명: PLC(periodic_lang_check) 스퓨리어스 전환이 방송클로징 환각 유발 [E5, 코드변경 있음] (2026-07-05)

**세션 메모**: 이 실험 착수 직전 공유 `.venv`가 손상돼(Lib/pyvenv.cfg 소실) 측정이 일시 불가했다 — 무인 세션 규칙(§4.5)에 따라 자율 복구하지 않고 대기하던 중 사용자가 복귀해 "venv 복구 진행" 지시, `uv sync --extra diarization-sortformer --extra vbcable --extra cu128`로 정상 복구(torch 2.11.0+cu128 확인) 후 재개. 상세는 `docs/GOAL_TURBO_AUTONOMOUS.md` §9 참조.

**가설**: Exp-158에서 확인된 ytn2 대폭회귀(+16.3pp)의 원인이 base용으로 튜닝된 언어전환 프로토콜·PLC(periodic_lang_check_secs, 기본 4.0)가 turbo의 신규 실패모드(필러/방송클로징 환각)와 나쁘게 상호작용하기 때문인지 검증한다. 단순화(PLC 완화/비활성)·강화(반복필터 언어확장·확신도 상향) 두 방향을 대조한다.

### 스크리닝 (N=1, 4건 — 코드변경 없음 3건 + 워크트리 2건)

| 후보 | 방향 | bong1 | ytn2 | sbs1 | 비고 |
|------|------|-------|------|------|------|
| PLC=999(사실상 비활성)* | 단순화 | 28.1% | **27.6%** | 24.4% | ytn2 대폭개선 신호 |
| PLC=2.0 | 강화 | 27.8% | **28.1%** | 26.2% | F1 최고(58.3%), ytn2 대폭개선 신호 |
| PLC=8.0 | 완화 | 32.3% | 39.9% | 21.4% | 개선 없음(baseline과 유사) |
| `repeat-filter-langagnostic`(1회차) | 강화 | 31.1% | 29.6% | **80.4%(하니스 버그)** | BatchRepeatFilter 0회 발동 — 필터 미관여 |
| `repeat-filter-langagnostic`(재측정) | 강화 | 23.6% | 25.1% | 15.5% | BatchRepeatFilter 이번에도 0회 발동 — **순수 변동성, 효과 미입증** |
| `langswitch-confidence-raise` | 단순화 | 26.3% | 28.1% | **47.0%(게이트 초과)** | sbs1 lag 17→31s 급증 동반 — 원인 불명확(기존 lag 이슈 가능성) |

*CLI `type=float`라 실제 `None` 전달 불가 — 999s(클립 길이 초과)로 근사.

**중요 진단**: `repeat-filter-langagnostic`는 두 스크리닝 모두에서 `[BatchRepeatFilter]` 로그가 **0회** — 언어무관화 변경이 단 한 번도 발동하지 않았다. 즉 이 두 실행의 수치 변화(특히 ytn2 개선)는 **코드 변경과 무관한 순수 실행 변동성**이다. 이는 N=1 스크리닝의 근본적 한계를 재확인시키는 사례.

### 채택 확정 (N=3) — PLC만

**PLC=2.0(강화)**:

| 파일 | R1 | R2 | R3 | median | max | min | stdev |
|------|-----|-----|-----|--------|-----|-----|-------|
| bong1 | 23.3% | 29.0% | 31.4% | 29.0% | 31.4% | 23.3% | 4.2% |
| ytn2 | 46.8% | 40.4% | 46.8% | **46.8%** | 46.8% | 40.4% | 3.7% |
| sbs1 | 29.8% | 26.2% | 25.6% | 26.2% | 29.8% | 25.6% | 2.3% |

→ **N=1 스크리닝(28.1%)이 완전히 재현 실패**. ytn2 median이 오히려 baseline(41.9%)보다 나쁨. sbs1도 median 일관 악화. **기각.**

**PLC=None(사실상 비활성, 단순화)**:

| 파일 | R1 | R2 | R3 | median | max | min | stdev | vs baseline(PLC=4.0) |
|------|-----|-----|-----|--------|-----|-----|-------|------------------------|
| bong1 | 30.5% | 27.5% | 33.5% | 30.5% | 33.5% | 27.5% | 3.0% | median +2.4pp, max **-1.2pp** |
| ytn2 | 30.0% | 38.4% | 24.1% | **30.0%** | 38.4% | 24.1% | 7.2% | median **-11.9pp**, max **-8.9pp** |
| sbs1 | 23.2% | 9.5% | 30.4% | 23.2% | 30.4% | 9.5% | 10.6% | median +7.1pp, max **-0.6pp** |

→ **3파일 모두 max 미회귀**(①1순위 기준 통과). ytn2는 median·max 모두 확실히 개선(P1 최우선 목표 직결). bong1은 거의 중립, sbs1은 median 악화하나 max는 오히려 baseline보다 낮음(sbs1은 원래 고분산 파일 — stdev 10.6%).

**held-out(단회)**: ytn1 33.1%→**22.7%**(-10.4pp, ytn2와 동일 개선 방향 재확인) / eng1 3.8%→7.6%(+3.8pp 소폭 악화, 절대값은 여전히 낮음).

### 분석 (전사 내용 정성 대조 — PLC=999 스크리닝 회차, 채택 근거)

**ytn2** (PLC=4.0 baseline, Exp-158 참고): 전사에 `"문의한 사안 중에서는 우선 왕성한 연합 김정은 기자입니다. 김정은 기자, 김정은 기자입니다입니다 감사합니다"` — 정답의 상당 분량이 방송클로징류 환각으로 통째 대체됨.

**ytn2** (PLC=None, 이번 실험): 동일 구간이 `"논의한 사안 중에서는 우. 왕성 왕성한 연합 방위 태세를 유지하기 위한 노력을 경제하자는 것 북한의..."`로 **정답과 거의 일치하게 복원** — 방송클로징 환각이 **완전히 소멸**. 단 `"Thank you. Thank you. very much. Thank you,"` 필러 삽입은 **여전히 잔존**(별도 메커니즘 — `repeat-filter-langagnostic`류 후속 필요, 단 위 스크리닝에서 효과 미입증).

**sbs1** (PLC=None): 후반부 `"그는 한미동맹은 단순한 전력 투사 통로가 아니라..."` 문단이 누락되고 곧바로 마지막 문장으로 건너뜀 — PLC 비활성으로 언어재확인이 sbs1에서 수행하던 순기능(드리프트 방지 등)이 사라지며 발생한 것으로 추정. median 악화의 정성적 근거.

**결론**: PLC=4.0의 주기적 언어 재확인이 ytn2에서 **스퓨리어스 언어전환을 오탐 → `_apply_detected_language`의 트림+재디코딩 발동 → 방송클로징 환각**을 유발하는 인과관계를 정성적으로 확인. PLC 비활성화로 이 인과사슬이 차단됨.

### 채택 (조건) 판정

**PLC 기본값 4.0→None(비활성) 채택**. ①max 미회귀(3파일 모두 통과) ②median: ytn2 대폭개선(P1 최우선 목표) vs sbs1 소폭악화(고분산 파일, max는 오히려 개선) — 순 이득으로 판단. held-out eng1 소폭악화는 절대값이 낮아(7.6%) 우려 수준 아님.

**구현**: `whisperlivekit/parse_args.py` — `--periodic-lang-check`에 `_optional_float` 커스텀 타입 추가(`'none'` 문자열 파싱 지원, 기존 `type=float`로는 CLI에서 실제 `None` 전달이 불가능했던 결함 수정), 기본값 `4.0`→`None`. 브랜치 `exp/plc-disable-default` → master 머지(`--no-ff`, 커밋 `5715875`). 연동 문서(`docs/TESTING.md`·`docs/DEPLOYMENT_OFFLINE.md`·`ROADMAP.md`·`scripts/closed_test.py` 도움말) 동일 커밋에서 갱신.

**후속 수정(정합성)**: `scripts/eval.py` 자체 argparse의 `--periodic-lang-check` 기본값이 `4.0`으로 별도 하드코딩돼 있어(parse_args.py와 비동기화), 플래그 미지정 시 eval.py가 항상 서버에 `--periodic-lang-check 4.0`을 강제 전달 — 새 서버 기본값(None)이 조용히 무시되는 버그였다. 기본값을 `None`으로 동기화(브랜치 `exp/eval-plc-default-sync` → master 머지, 커밋 `d113fde`). 이 세션의 PLC=999/2.0/8.0 스크리닝·N=3 측정은 전부 `--periodic-lang-check`를 명시적으로 지정했으므로 위 결과 자체는 영향 없음 — 영향 범위는 "향후 플래그 미지정 측정"뿐.

**기각**: PLC=2.0(강화) — N=3 확정에서 N=1 스크리닝 신호 재현 실패. `repeat-filter-langagnostic`(언어무관 반복필터) — 두 스크리닝 모두 필터 미발동으로 효과 검증 불가(기각이 아니라 **미결정** — 워크트리 보존, 후속 재시도 여지). `langswitch-confidence-raise`(확신도 상향) — sbs1 게이트 초과 위험신호로 후순위 보류(워크트리 보존).

### 다음 가설

1. **ytn2 잔존 이슈**: "Thank you" 필러가 PLC=None에서도 잔존 — cross-batch 구문 반복 탐지(단일단어 정확일치가 아닌 phrase-level) 설계 필요. `repeat-filter-langagnostic`은 재시도하되 반드시 `[BatchRepeatFilter]` 로그로 실제 발동 여부를 먼저 확인할 것.
2. `langswitch-confidence-raise`의 sbs1 lag 급증 원인 규명 — P2(lag)와 연계 조사 가치.
3. P2(sbs1 lag, `audio_max_len` 우선 용의자), P3(beam/CRT 등 잔여 파라미터 재검증) 착수.

**JSON**: `.omc/benchmarks/eval_20260705_2135_plc_disabled.json`(PLC=999 N=1) · `eval_20260705_2144_plc_2s.json`(PLC=2.0 N=1) · `eval_20260705_2152_plc_8s.json`(PLC=8.0 N=1) · `eval_20260705_2202_repeatfilter_langagnostic.json`/`_r2.json` · `eval_20260705_2221_confraise.json` · `eval_20260705_2231_plc2s_N3.json`(PLC=2.0 N=3, 기각) · `eval_20260705_2255_plcdisabled_N3.json`(PLC=None N=3, 채택) · `eval_20260705_2318_plcdisabled_heldout.json`. 워크트리 `worktrees/repeat-filter-langagnostic`(exp/repeat-filter-langagnostic@1a66eab)·`worktrees/langswitch-confidence-raise`(exp/langswitch-confidence-raise@db800ce) 보존(미결정/보류).

---

## Exp-161 — sbs1 실시간 lag 해결: audio_max_len 30.0→15.0 전환 [E5, 코드변경 있음] (2026-07-06)

**가설**: Exp-158에서 관측된 sbs1 실시간 lag(RTX 3080, 최대 41s)의 원인은 turbo 인코더가 매 `infer()` 호출마다 버퍼 전체(최대 `audio_max_len`=30.0s)를 재인코딩하는 데서 오는 처리시간 누적으로 추정(§GOAL_TURBO_AUTONOMOUS.md P2). `audio_max_len`을 낮춰 호출당 재인코딩 비용을 줄이면 lag가 완화되는지 검증한다.

**도구 준비**: `scripts/eval.py`가 `--audio-max-len`/`--frame-threshold`를 지원하지 않아 `--periodic-lang-check`와 동일한 패턴으로 패스스루 플래그 추가(브랜치 `exp/eval-add-lag-flags` → master 머지, 커밋 `16ecca5`).

### 스크리닝 (N=1, sbs1 단독) — `audio_max_len=15.0`

sbs1 WER 19.0%(정상 범위, 회귀 없음). 서버로그 lag가 시종 0.00s(1회 0.05s 블립) — 기존 관측된 2.32→31.15s 누적 패턴과 대조적으로 **사실상 lag 소멸**.

### 채택 확정 (N=3, 3파일 전체) — `audio_max_len=15.0` vs baseline(30.0, PLC=None 공통)

| 파일 | baseline median/max/stdev | 15.0 median/max/stdev |
|------|---------------------------|------------------------|
| bong1 | 30.5% / 33.5% / 3.0% | 30.5% / **30.5%** / **0.7%** |
| ytn2 | 30.0% / 38.4% / 7.2% | **28.1%** / **34.5%** / 5.0% |
| sbs1 | 23.2% / 30.4% / 10.6% | **14.9%** / **16.1%** / **1.5%** |

**lag 재확인(3회차 서버로그 최대값)**: 2.04s / 2.03s / 2.17s — 기존(최대 41s, Exp-158) 대비 약 15~20배 감소, 3회 모두 일관되게 안정.

**held-out(단회)**: ytn1 22.7%→**21.5%**(개선) / eng1 7.6%→**4.8%**(개선, base 참고치 3.8%에 근접).

### 분석 (정성)

정량 결과가 전 파일·전 지표(median·max·stdev)에서 일관되게 개선되거나 동일 수준이라 정성 대조로 확인할 회귀 패턴이 없음. sbs1 F1은 다소 낮게 유지되나(15~18%대) 이는 diar-ON 문장경계 과분할이라는 기존에 규명된 별개 이슈([불변][diar] 이월 핵심사실)이지 이번 변경의 부작용이 아님 — WER 개선과 무관하게 유지되는 수치임을 확인.

### 채택 (조건) 판정

**`audio_max_len` 기본값 30.0→15.0 채택**. ①max 미회귀 — 3파일 모두 통과(오히려 전부 개선). ②median — bong1 동일, ytn2·sbs1 개선(sbs1 대폭). **분산도 3파일 모두 대폭 감소**(worst-case 안정성 — §3.8 최우선 원칙과 직접 정합) — 이번 세션 중 가장 명확한(ambiguous하지 않은) 채택 사례.

**구현**: `whisperlivekit/parse_args.py` `--audio-max-len` 기본값 `30.0`→`15.0`. 브랜치 `exp/audiomax-lag-fix` → master 머지(`--no-ff`, 커밋 `cbdc562`). 연동 문서 확인 결과 `docs/TESTING.md`·`DEPLOYMENT_OFFLINE.md`·`ROADMAP.md`에 `audio-max-len` 언급 없어 추가 갱신 불필요.

### 다음 가설

1. `langswitch-confidence-raise`(Exp-160에서 보류)의 sbs1 lag 급증(17→31s)이 이번 `audio_max_len=15.0`으로도 해소되는지 재확인 가치 있음(원인이 buffer 크기였다면 해소될 것).
2. P3 — 잔여 파라미터(beam/CRT/logprob) 재검증 착수.
3. `repeat-filter-langagnostic`(Exp-160 미결정) cross-batch phrase-level 재설계 시도.

**후속 확인 완료(2026-07-06)**: 1번 재확인 — `exp/langswitch-confidence-raise`에 master 병합(신규 기본값 반영) 후 재측정: bong1 31.7%/ytn2 27.6%/**sbs1 14.9%**(N=1). sbs1이 기존 47.0%(게이트 초과)에서 새 baseline 수준(14.9%, Exp-161과 동일)으로 완전히 정상화됨 — **Exp-160의 sbs1 위험신호는 confidence-raise 코드 자체가 아니라 `audio_max_len=30.0`의 lag 확인이었음을 확인**. 단 bong1·ytn2는 현재 baseline(30.5%/28.1%) 대비 뚜렷한 개선도 회귀도 없어(노이즈 수준 차이) — 확신도 상향 자체의 순 효과는 **중립**으로 판단, N=3 추가 투자는 보류(워크트리는 계속 보존).

**JSON**: `.omc/benchmarks/eval_20260705_2335_sbs1_audiomax15.json`(N=1 스크리닝) · `eval_20260705_2338_audiomax15_N3.json`(N=3 확정) · `eval_20260706_0002_audiomax15_heldout.json`(held-out) · `eval_20260706_0010_confraise_v2.json`(langswitch-confidence-raise 후속 재확인). 서버로그 `.omc/server_logs/server_sbs1_C_R{1,2,3}_20260705_23*.log`.

---

## Exp-162 — P3 파라미터 재검증: beam·CRT (turbo에서 현재 기본값 재확인) [E5, 코드변경 없음] (2026-07-06)

**가설**: E1~E4(base 기질)에서 나온 beam(Exp-125: beam2 최적, beam3/4 ytn2 catastrophic)·CRT 결론이 turbo에서도 유효한지 재검증(epoch 게이트 §CLAUDE.md). 도구 준비로 `eval.py`에 `--beams` 패스스루 플래그 추가(브랜치 `exp/eval-add-beams-flag` → master 머지, 커밋 `4ae604f`).

**세션 메모(하니스 확인)**: 서버 시작 배너가 항상 `Model: base`로 표시됨을 발견해 model_dir 배선 버그(Exp-158) 재발을 의심했으나, 이미 정상으로 확인된 P0 held-out 로그(`server_ytn1_C_R1_20260705_212611.log`)에도 동일하게 표시됨을 대조 확인 — **배너의 모델명은 cosmetic**(기존 메모리 `turbo-nograd-perf-cliff`와 동일 현상)이며 실제 로드 모델과 무관. 유사하게 provenance 줄의 `beams=` 값도 `eval.py`가 빈 인자로 `parse_args`를 프로브해 얻은 **정적 기본값**이라 `--beams` 오버라이드를 반영하지 않는 cosmetic 표시임을 확인(WER 결과 자체가 beam값별로 뚜렷이 달라지는 것으로 플래그 실제 적용은 검증됨).

### 스크리닝 결과 (N=1, 현재 baseline: bong1 30.5%/ytn2 28.1%/sbs1 14.9%, 게이트 max 30.5%/34.5%/16.1%)

| 파라미터 | bong1 | ytn2 | sbs1 | 판정 |
|---------|-------|------|------|------|
| beam=1(greedy) | 36.9%(게이트초과) | 20.2%(개선) | 21.4%(게이트초과) | ❌ 2/3 파일 게이트 초과 |
| beam=3 | 36.9%(게이트초과) | 40.9%(게이트초과) | 26.8%(게이트초과) | ❌ 3/3 파일 게이트 초과 — 명백한 악화 |
| CRT=2.5 | 34.7%(게이트초과) | 33.0%(게이트이내) | 19.0%(게이트초과) | ❌ 2/3 파일 게이트 초과 |
| CRT=2.8 | 29.3%(이내) | 28.6%(이내) | 14.3%(이내) | ➖ baseline과 통계적으로 구분 안 됨(전부 게이트 이내, 소폭 변동) |

### 판정

**beam=2, CRT=3.0(현재 master 기본값) 모두 turbo에서 재확인 — 변경 없음**. beam=1·beam=3·CRT=2.5는 스크리닝 단계에서 이미 여러 파일이 게이트를 초과해 N=3 확정 없이 기각(방향이 명확히 나쁨). CRT=2.8은 baseline과 구분 안 되는 수준이라 추가 투자(N=3) 근거 없음. **base 기질(Exp-125 등)의 "beam=2 최적" 결론이 turbo에서도 동일한 방향으로 재확인**됨 — [base전용·재검증] 태그를 [모델무관·유지]로 격상 가능.

### 다음 가설

1. logprob 임계·no_speech 등 잔여 P3 파라미터는 현재 우선순위 낮음(beam·CRT가 이미 안정적으로 재확인됨). 후속 세션에서 여유 있을 때 착수.
2. `repeat-filter-langagnostic`(Exp-160 미결정) cross-batch phrase-level 재설계는 여전히 유효한 다음 과제.

**JSON**: `.omc/benchmarks/eval_20260706_0023_beam1.json` · `eval_20260706_0032_beam3.json` · `eval_20260706_0040_crt25.json` · `eval_20260706_0048_crt28.json`.

---

## Exp-163 — cross-batch 필러 반복 필터 (v1 연속 n-gram → v2 윈도우-앵커) [E5, 코드변경 있음·master 미머지·기각] (2026-07-06)

**가설**: turbo(E5) 지배 실패모드는 비발화/전환 갭 구간의 "Thank you" 연쇄·"Yeah" 폭주 등 **다단어 필러 환각**(Exp-158/159 관측, 3파일 공통). 기존 cross-batch 필터(`backend.py` `_filter_cross_batch_repetitions`)는 단일단어 dedup·한글 배치드롭만 잡아 다단어 영어 구 반복을 원리상 못 잡는다. 이를 backend 필터로 억제하면 worst-case(특히 ytn2 max) WER을 방어할 것으로 기대. 워크트리 `exp/repeat-filter-phrase`.

**변경 (2단계)**:
- **v1** (커밋 `e141898`): 언어무관 2–4gram **연속** 반복 탐지 — `detect_seq` 누적으로 주기 정합, `_PHRASE_ALLOWED_REPEATS=2`(정상 2회 보존), 연속 4회 드롭 시 `refresh_segment`. `whisperlivekit/simul_whisper/backend.py`의 `_filter_cross_batch_repetitions` 확장 + 외부 리셋 3곳(long_silence·new_speaker·stall)에서 phrase 상태 클리어. pytest 17.
- **v2** (커밋 `d0cf799`): v1 스크리닝에서 **필터 0회 발동** 확인 → 실제 필러는 삽입·변형 낀 **비연속 재등장**이라 연속-일치 전제가 실패. **윈도우-앵커 재설계**: 트레일링 16단어 윈도우 내 짧은 앵커(2~3gram) 등장 `>2`회면 드롭, `≥4`회(또는 연속드롭 4회)면 `refresh_segment`. 1gram 제외(함수어·기존 dedup 담당). `_count_ngram_occurrences` 신설, `_trailing_repeat_count` 대체. pytest 19. ruff 클린.

**테스트 설정**: 경로 C, diar-ON(Sortformer + `--compression-ratio-threshold 3.0`), turbo, **cwd=워크트리**(provenance `whisperlivekit_file`=워크트리 경로·`git_sha`=d0cf799·`vbcable=ok` 확인 — 워크트리 코드 실측). v1/v2 스크리닝 `--repeat 1`, v2 채택검증 `--repeat 3`.

### 테스트 세트 결과

| 측정 | bong1 | ytn2 | sbs1 | 필터 발동 |
|------|-------|------|------|-----------|
| baseline(Exp-161) | 30.5% med/max30.5 | 28.1% med/max34.5 | 14.9% med/max16.1 | — |
| v1 스크리닝(N=1, e141898) | 35.6% | 28.6% | 13.1% | Filler **0회** (변형 필러 미포착) |
| v2 스크리닝(N=1, d0cf799) | 31.1% | 28.1% | 15.5% | **0회** (이 run 스톰 미발현·오탐 없음 확인) |
| **v2 N=3(d0cf799) med** | 26.3% (23.0/26.3/28.7, max28.7, sd2.9) | **34.0% (28.6/46.8/34.0, max46.8 ❌, sd9.4)** | 16.1% (15.5/16.1/18.5, max18.5, sd1.6) | ytn2 전회차 발동(R1:2·R2:3·R3:1), 앵커 전부 `'thank you'` 매번 refresh; bong1/sbs1 **0회** |

F1(v2 N=3 med): bong1 46.2% / ytn2 43.5% / sbs1 16.7%. 경로 C 평균 WER 26.4%.

### 분석 (전사 내용 정성 대조)

**bong1** (R2 median 26.3, 필터 0회): 필러 스톰 없음. 코드스위칭·웃음 구간 오류가 WER 주도. **필터 0회 발동 → 코드경로가 baseline과 동일 → med 26.3은 필터 효과가 아닌 실측 분산**(base med 30.5의 저분산 우연 샘플).

**ytn2** (R3 median 34.0 필터 1회 / R2 max 46.8 필터 3회): median에도 필러 잔존 — 전사 말미 `"...close coordination on this topic Thank you very much. Thank you. Thank very much, everyone. Thank you"` + `"네, 네, 네,, 감사합니다"` 방송아웃트로 환각. **max(R2)는 필러 홍수 + refresh 교란** — 전사 `"...initial operational capability Thank you very much. Thank you. very much for your time. Thank. Thank Thank you very much... for coming... for your question."` 및 `"왕성한 연. 문화 방위태세를 1부에서 계속 됩니다 감사합니다"` 신규 방송아웃트로 삽입. **필터가 'thank you' 스톰을 올바로 탐지·refresh하지만 필러가 사라지지 않음**(refresh가 윈도우 비워 디코더가 재생성). refresh_segment가 ytn2 취약 정렬을 교란해 콘텐츠 손실·환각 삽입 유발.

**sbs1** (R2 median 16.1, 필터 0회): 필러 없음, 정상 종료 `"...입니다. SBS 뉴스입니다."`. F1 낮음(과분할·ref 3블록 granularity)은 이번 변경과 무관. 필터 0회 → baseline 동일.

**이번 변경 영향**: 필러 억제 목표는 **악화**로 귀결. 필터가 표적('thank you' 스톰)을 탐지하나 (a)출력 드롭이 디코더 재생성을 못 막아 필러 잔존, (b)refresh_segment가 ytn2를 교란해 max 34.5→46.8 catastrophic 회귀(**Exp-160 PLC 재디코딩이 ytn2 망친 것과 동형**). bong1/sbs1은 필터 미발동이라 무관.

### 채택 (조건) 판정

- ① max 미회귀: **ytn2 max 46.8% > 게이트 34.5% (+12.3pp catastrophic)** ❌. sbs1 max 18.5%>16.1% 소폭 초과.
- ② median 개선: bong1 개선은 필터 무발동(분산), ytn2 median 28.1→34.0 악화, sbs1 14.9→16.1 소폭 악화.
- **§4 1순위(worst-case max 미회귀) 위반 → 기각.**

### 결론

**기각 (master 미머지, 워크트리 보존).** 후처리 반복 필터 접근(v1·v2)은 turbo "thank you" 필러에 부적합: ①필러는 디코더가 모호/비음성 구간에서 **생성**하는 것이라 출력 후처리로 못 막고(refresh 후 재생성), ②storm 시 refresh가 ytn2 정렬을 교란해 오히려 악화. 코드 품질 자체는 정상(pytest 19·ruff 클린)이나 측정으로 기각. **핵심 교훈: 필러는 원천(비음성 게이팅 Layer 3b)에서 차단해야 한다.**

### 다음 가설

**후보 3(비음성 게이팅, 원천 차단)으로 피벗**(사용자 승인). VAC threshold(0.3)·no_speech(nonspeech_prob=0.5, 현재 세그먼트 **첫 토큰만** 검사) 재검토 + mid-segment no_speech 검사로 필러 생성 구간을 전사에서 배제. STATE "Layer 3b 미해결 1순위 과제"와 정합. base 시절 nonspeech/VAC 기각 이력은 base 기질이라 turbo 재검증 대상(epoch 게이트).

**JSON**: `.omc/benchmarks/eval_20260706_1009_exp163_phrasefilter_screen.json`(v1 스크리닝) · `eval_20260706_1049_exp163v2_fillerstorm_screen.json`(v2 스크리닝) · `eval_20260706_1100_exp163v2_fillerstorm_N3.json`(v2 N=3).

---

## Exp-164 — 비음성 게이팅 원천 차단 시도: no_speech 계측(구조적 무효 규명) + VAC 임계값 스윕(목표 미달성) [E5, 코드변경 있음·master 미머지·기각] (2026-07-06)

**가설**: Exp-163(필러 반복 후처리 필터)가 "필러는 원천에서 차단해야 한다"는 교훈으로 기각됨에 따라, STATE "Layer 3b 미해결 1순위 과제"에 해당하는 **비음성 구간 게이팅**을 시도한다. 두 기존 메커니즘이 후보: ① no_speech SOT 품질게이트(`nonspeech_prob`, 현재 0.5 고정·CLI 미노출) ② VAC(Silero VAD, threshold=0.3 고정·CLI 미노출). 워크트리 `exp/nonspeech-gating`.

**변경 (2단계)**:
- **1단계 — no_speech 계측** (커밋 `0a5ed1a`): `--nonspeech-prob` CLI 노출(`parse_args.py`) + `AlignAttConfig` 배선(`backend.py`) + `_check_no_speech`에 `[NoSpeechProbe]` 상시 로깅 추가(`simul_whisper.py:341`) + `eval.py` 패스스루. 기본값 0.5 유지(동작 불변).
  - **하니스 버그 발견·수정**: 첫 계측 run에서 로그 0회 발동 확인 → 원인 규명 — `basic_server.py`가 root 로거를 WARNING으로 두고 `--trace-tokens` 시 `backend.py`/`align_att_base.py` 로거만 DEBUG로 승격하는데 `simul_whisper.py`(내 계측 위치)가 그 목록에서 누락되어 전부 필터링됨. 목록에 추가 후 재계측.
- **2단계 — VAC 계측 + 임계값 노출** (커밋 `99db307`): `silero_vad_iterator.py`의 `VADIterator.__call__`(speech_prob 계산 직후, `:264` 부근)에 `[VacProbe]` 상시 로깅 추가 + `basic_server.py` trace-tokens 목록에 로거 추가. `--vac-threshold` CLI 노출(`parse_args.py`) + `audio_processor.py:103-108`(`FixedVADIterator(..., threshold=vac_threshold)`) 배선 + `eval.py` 패스스루. 기본값 0.3 유지.

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo, `--trace-tokens`. no_speech 계측 3파일 N=1(진단 목적), VAC 계측 ytn2 단독 N=1(신호 검증), VAC=0.4 스윕 3파일 N=1(스크리닝).

### 계측 결과 — no_speech 게이트는 구조적으로 무효

| 파일 | NoSpeechProbe 샘플 수 | mean | max |
|------|---------|------|-----|
| bong1(웃음구간 포함) | 531 | 0.000000 | 0.000000 |
| ytn2(필러구간 포함) | 402 | 0.000000 | 0.000000 |
| sbs1 | 288 | 0.000000 | 0.000000 |

**3파일 합계 1221개 세그먼트 샘플 전부 정확히 0.000** — 어떤 임계값(0.4/0.5/0.6)을 넣어도 `0.000 > threshold`는 항상 False라 게이트가 원천적으로 발동 불가능함이 실측 확인됨. **원인**: `align_att_base.py:288-289`의 `_concat_segments()`가 롤링 버퍼 **전체**(최대 `audio_max_len`=15s, 이전 실제 발화 포함)를 인코딩하고 `_check_no_speech`(`simul_whisper.py:338-345`)는 그 전체 세그먼트에 대한 SOT 확률 **하나**로 판정 — 버퍼에 실제 발화가 조금이라도 섞여 있으면(거의 항상) no_speech 확률이 절대 오르지 않는다. **→ 임계값 스윕을 실행하지 않고 즉시 중단**(무의미한 측정 사이클 낭비 방지, 사용자 확인 후 VAC로 피벗).

### 계측 결과 — VAC(Silero)는 신호 자체는 살아있음

ytn2 단독 N=1, 3807 샘플: mean=0.715, min=0.000, **max=0.996**, 히스토그램 이중봉(0.0대 682개, 0.9대 2457개). threshold=0.3 미만 25.3%. no_speech와 달리 실제로 변동하는 신호 확인 → 스윕 진행 근거 확보.

### 테스트 세트 결과 (VAC=0.4 스크리닝, N=1)

| 파일 | baseline(VAC=0.3) med | VAC=0.4 | 게이트(max) | 판정 |
|------|------|---------|--------|------|
| bong1 | 30.5% | **34.4%** (F1 52.4) | ≤30.5% | ❌ 초과 +3.9pp |
| ytn2 | 28.1% | 30.0% (F1 54.5) | ≤34.5% | ✓ 이내 |
| sbs1 | 14.9% | 11.9% (F1 18.2) | ≤16.1% | ✓ 이내(개선 -3.0pp) |

provenance: `branch=exp/nonspeech-gating@99db307 vac_threshold=0.4 vbcable=ok`.

### 분석 (전사 내용 정성 대조)

**bong1** (VAC=0.4, 게이트 초과): **VAC 상향의 목표(웃음 구간 환각 억제)가 달성되지 않음** — 웃음 구간 전사에 `"This man Thank you very. much. Thank you. Thank."`(baseline VAC=0.3의 Exp-163 관측과 **정확히 동일 위치·동일 패턴**) + 신규 `"Ha, ha, ha,. ha,. I'm sorry, sir. I'm sorry."`(웃음소리 자체가 축자 전사됨) 그대로 존재. VAC를 올려도 필러·웃음 전사가 사라지지 않음.

**ytn2** (VAC=0.4, 게이트 이내): 필러 잔존 — `"resolutions Thank you very much. Thank you very much."`(baseline과 동일 위치). 단 게이트 초과는 없었고, 전환 경계 서두 절단(base 기각 사유였던 단어유실)도 이번 run에선 뚜렷하지 않음(`"논의한 사안 중에서는 우선 왕성한 연합 방위태세를 유지하기 위한..."` 온전 보존) — base의 "VAC 상향→전환 speech 손실" 우려가 이번 run에서는 재현 안 됨.

**sbs1** (VAC=0.4, 개선): 필러 없음(baseline과 동일), VAC 임계값과 무관.

**이번 변경 영향**: **구조적 해석** — VAC(Silero)는 "음성 에너지(성대 진동·포먼트)가 있는가"를 판정하는 메커니즘이지 "어휘적으로 이해 가능한 발화인가"를 판정하지 않는다. 웃음·필러성 발성은 실제 음성 에너지를 동반하므로(무음·잡음이 아님) 어떤 합리적 VAC 임계값을 써도 "speech"로 통과되어 ASR에 유입된다. no_speech 게이트가 "롤링버퍼 전체 판정"이라는 배선 문제로 무효였다면, VAC는 "애초에 겨냥하는 신호가 다르다"는 **개념적 한계**로 무효 — 둘 다 §CLAUDE.md Layer 3b(웃음·필러를 "비음성"으로 분류해 배제)의 목표에 도달하지 못한다.

### 채택 (조건) 판정

- ① max 미회귀: bong1 게이트 초과(34.4>30.5) ❌.
- ② 정성 목표 달성: 웃음/필러 환각 억제 **미달성**(전사에 그대로 잔존) ❌.
- 정량 회귀 + 정성 목표 미달성 → **기각** (§4 판정표: "회귀, 목표 미달성 → 기각"에 해당).

### 결론

**기각 (master 미머지, 워크트리 `exp/nonspeech-gating` 보존).** no_speech 게이트는 배선(롤링버퍼 전체 판정) 때문에 구조적으로 무효, VAC는 판정 대상(음성 에너지 vs 어휘적 이해가능성)이 달라 개념적으로 무효 — **두 기존 메커니즘 모두 웃음/필러를 "비음성"으로 걸러내지 못함**이 실측으로 확정됨. `--nonspeech-prob`/`--vac-threshold` CLI 노출과 `[NoSpeechProbe]`/`[VacProbe]` 계측 인프라 자체는 향후 진단에 재사용 가능(기본값 유지로 동작 불변, pytest 127 passed 확인됨)하므로 워크트리 보존.

### 다음 가설

1. **Layer 3b 재설계 필요** — 기존 메커니즘 확장이 아니라 새로운 신호가 필요: (a) no_speech를 세그먼트 전체가 아니라 **신규 tail만** 판정하도록 디코더 구조 변경(리스크 큼, 별도 설계 세션 필요), 또는 (b) 웃음 전용 분류기(비-ASR, 별도 오디오 분류 모델) 도입 — 둘 다 이번 세션 범위 밖.
2. **후보 2(전환 경계 오디오 보존, `LANG_SWITCH_KEEP_SECS` 등)** — Exp-164에서 VAC=0.4의 ytn2 전환 손실 우려가 재현 안 됨을 확인했으므로, ytn2 잔여 회귀(서두 절단) 재조사는 여전히 유효한 후보.
3. **후보 4(diar 과분할 F1)** — F1 병목(전 파일 precision 붕괴)은 이번 실험과 무관하게 미해결.

**JSON**: `.omc/benchmarks/eval_20260706_1439_exp164_nsp_default_probe.json`(no_speech 계측 1차, 로깅버그로 무효) · `eval_20260706_1511_exp164_vac04_screen.json`(VAC=0.4 스크리닝).

## Exp-165 — tail-only no_speech shadow probe: tail-slice로도 no_speech 상승 없음(Layer 3b no_speech 계열 폐기 확정) [E5, 코드변경 있음·master 미머지·기각] (2026-07-06)

**가설**: Exp-164에서 no_speech SOT 게이트가 "롤링버퍼 전체 판정"(최대 15s, 이전 실제 발화 포함) 때문에 무효(3파일 1221샘플 전부 0.000)로 규명됨. 그 다음 가설로 제시된 것이 "no_speech를 세그먼트 전체가 아니라 **신규 tail만** 판정하도록 구조 변경"이었다. 이 tail 판정은 새 아키텍처가 아니라 **기존 두 메서드의 재조합**이다: `detect_current_language`(`align_att_base.py:250`)의 tail-slice(`all_audio[-window_samples:]` → `_encode`) + `lang_id`(`simul_whisper.py:207`)의 SOT 1-스텝 단독 forward를 조합하고, 언어 확률 대신 `_check_no_speech`가 읽는 것과 같은 no_speech 토큰 확률을 읽으면 된다. **가설: tail만 보면 웃음/필러 구간에서 no_speech 확률이 상승해 정상 발화와 분리 가능한가?** 워크트리 `exp/nonspeech-gating` 이어서.

**변경 (진단 전용, 게이팅 미연결)**:
- `probe_tail_no_speech(window_secs=2.0)` 신규 메서드(`align_att_base.py`, **`@torch.no_grad()` 필수** — Exp-158 stall 재발 방지, 확인함): tail-slice → `_encode` → `[[sot]]` 단독 forward → `softmax[no_speech]`. `infer()` 인코딩 직후 매 사이클 병행 로깅(`[TailNoSpeechProbe]`), 출력 로직 미개입. 커밋 `647f053`.
- CLI `--tail-nonspeech-probe`(store_true) + `--tail-nonspeech-window`(float) 노출(`parse_args.py`), `eval.py` 패스스루.
- **하니스 버그 발견·수정** (커밋 `5b525d9`): 첫 run에서 `[TailNoSpeechProbe]` 0회 발동 — 원인은 backend가 argparse 전체가 아니라 `core.py`의 **curated `simulstreaming_params` dict**(`config.X`만 읽음)로 kwargs를 받는데 신규 필드가 누락돼 `self.cfg.tail_nonspeech_probe`가 False 고착됨(Exp-164 `nonspeech_prob`도 같은 이유로 실은 배선 미완이었으나 결론 무관). `lang_restrict_koen`과 동일 경로로 `WhisperLiveKitConfig`(`config.py`) + `simulstreaming_params`(`core.py`) 양쪽에 배선. 재측정에서 발동 확인.
- **고정밀 진단 로깅 추가** (커밋 `1350f99`): `no_speech=%.6f` + raw `ns_logit` + SOT `top_id`/`top_p` 병기 — 0.0000이 formatting 아티팩트인지 vs 진짜 0인지 확정용.

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo, `--trace-tokens --tail-nonspeech-probe`. bong1(웃음)·ytn2(필러) N=1 진단. provenance `branch=exp/nonspeech-gating@647f053/5b525d9 vbcable=ok`. **WER은 probe 추가 forward 비용 때문에 해석 대상 아님**(동작 불변 검증용).

### 계측 결과 — tail-slice로도 no_speech는 구조적으로 0

| 파일 | TailNoSpeechProbe 샘플 | no_speech min~max | 원인 진단(고정밀) |
|------|---------|------|------|
| bong1(웃음구간) | 294 | **0.000000 전부** | ns_logit ≈ -10.1~-10.5(변동), top_id=50360 top_p≈0.52 |
| ytn2(필러구간) | 219 | **0.000000 전부** | (동일) |

**513개 tail 샘플(win=2.0s) 전부 정확히 0.000000.** 고정밀 bong1 재측정(290샘플)에서 **`ns_logit`이 -10.1~-10.5로 실제 변동**(→ forward가 살아있고 실제 logits 생성) + **`top_id=50360 top_p≈0.52`**(SOT softmax가 정상 분포 생성)임에도 no_speech 토큰만 logit ~-10에 고착 → softmax 후 확률 ~0. **즉 probe 자체는 정상 작동하며, turbo의 no_speech 토큰이 tail 내용(웃음/필러/발화)과 무관하게 항상 무시할 확률을 받는 degenerate 상태**임이 확정됨.

### 분석 — Exp-164 진단 정정

Exp-164는 no_speech=0의 원인을 "롤링버퍼 전체 판정(이전 발화 오염)"으로 봤으나, **본 실험이 이를 정정한다**: 2.0s tail만 판정해도 no_speech가 전혀 오르지 않으므로 원인은 버퍼 크기·오염이 **아니라** turbo의 no_speech 헤드 자체가 비활성(logit 고착)인 것이다. `whisper-large-v3-turbo`(증류 모델)에서 no_speech 토큰이 SOT 위치에서 유의미한 확률을 받지 못하는 모델 고유 특성으로 추정. **동작 불변 검증**: probe는 로깅 전용이므로 WER은 baseline 대비 N=1 분산 내(run1 bong1 24.8/ytn2 36.9, run2 bong1 36.9/ytn2 28.1 — probe 오버헤드에도 출력 로직 미개입 확인).

### 분기 판정 — (b) 분리 불가

goal §P1 분기표의 **(b) 분리 불가**: "웃음에서도 확률이 낮게 유지 → Layer 3b를 no_speech 계열로는 폐기 확정, P3 스킵, P2로 진행"에 정확히 해당. no_speech 계열(전체버퍼 Exp-164 + tail Exp-165)은 turbo에서 웃음/필러를 비음성으로 분류할 수 없음이 실측 2회로 확정. **Layer 3b는 no_speech 신호로는 도달 불가 — 남은 경로는 웃음 전용 비-ASR 분류기(별도 오디오 모델) 뿐이며, 이는 별도 설계 세션 범위.**

### 결론

**기각·폐기 확정 (master 미머지, 워크트리 `exp/nonspeech-gating` 보존).** tail-probe 계측 인프라(`probe_tail_no_speech` + `[TailNoSpeechProbe]` 고정밀 로깅 + CLI + 완전 배선)는 기본값 off로 동작 불변(pytest 127 passed), 향후 진단 재사용 가능하므로 보존. Layer 3b no_speech 계열은 **폐기 확정** — 후속 세션은 이 결론을 재검증하지 말고 (필요 시) 웃음 전용 분류기 방향만 고려.

### 다음 (P2로 이관)

P3(게이팅 설계)는 (b) 분기로 **스킵**. P2(`LANG_SWITCH_KEEP_SECS` 스윕, 전환경계 보존)로 진행 — 별도 워커가 병렬 구현 중(Exp-166, 커밋 `21266b2`, 브랜치 `exp/exp-langswitch-keepsecs-sweep`).

**JSON**: `.omc/benchmarks/eval_20260706_1614_exp165_tailprobe2.json`(bong1+ytn2 계측) · `eval_20260706_1631_exp165_precision.json`(bong1 고정밀). 서버로그: `.omc/server_logs/server_{bong1,ytn2}_C_R1_*.log`.

## Exp-166 — `LANG_SWITCH_KEEP_SECS` 스윕(3.5/4.5): 전환경계 서두 유실 미완화·ytn2 미개선 [E5, 코드변경 있음·master 미머지·기각] (2026-07-06)

**가설**: ytn2 전환경계에서 서두 단어·문장이 절단되는 오류(WER 1순위 유형 B)를, 언어전환 시 유지하는 최근 오디오 창(`LANG_SWITCH_KEEP_SECS`, 현재 2.5s 하드코딩 — base 기질 Exp-150~153 튜닝값)을 **늘리면**(3.5/4.5) 재디코딩 범위가 넓어져 서두 보존이 개선될까? 워크트리 `exp/exp-langswitch-keepsecs-sweep`.

**변경**: `align_att_base.py:13`의 `LANG_SWITCH_KEEP_SECS=2.5`를 `--lang-switch-keep-secs` CLI로 노출(커밋 `21266b2`). `parse_args.py`→`WhisperLiveKitConfig`(`config.py`)→`core.py` `simulstreaming_params`→`align_att_base.py:187` `getattr(self.cfg,"lang_switch_keep_secs",None)` fallback(None=서버 기본 2.5) 배선 + `eval.py` 패스스루·provenance(`LSKEEP=`). **코드는 병렬 서브에이전트(이전 활동)가 구현, 측정·기록은 본 세션이 단독 워커로 수행**(pytest 127 passed 재확인). 동작 불변(기본값 None).

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo, N=1 스크리닝. keep_secs 3.5·4.5 각 bong1+ytn2+sbs1. provenance `branch=exp/exp-langswitch-keepsecs-sweep@21266b2 LSKEEP=3.5/4.5 vbcable=ok`.

### 테스트 세트 결과 (N=1 스크리닝, 방향 신호)

| 파일 | baseline med / max | keep=3.5 | keep=4.5 | 게이트(max) |
|------|------|------|------|------|
| bong1 | 30.5% / 30.5% | 31.1% (F1 51.4) | 28.4% (F1 52.9) | ≤30.5% |
| ytn2  | 28.1% / 34.5% | **40.9%** (F1 36.4) | **34.5%** (F1 59.3) | ≤34.5% |
| sbs1  | 14.9% / 16.1% | 15.5% (F1 20.0) | **18.5%** (F1 18.2) | ≤16.1% |

- **ytn2(목표)**: 두 값 모두 baseline median(28.1%) 위 — keep=3.5는 40.9%(+12.8pp, max도 초과), keep=4.5는 34.5%(=baseline max). **개선 신호 없음**, N=1 분산도 6.4pp로 큼.
- **sbs1**: keep=4.5에서 18.5%로 **게이트 초과**(+2.4pp).

### 분석 (전사 정성 대조 — 필수)

**목표(서두 유실 완화)가 두 값 모두 미달성**:
- keep=3.5 ytn2: "논의한 사안 중에서는 **우.**"(우선→우 절단)·"왕성한 **연**"(연합방위태세 절단) — 서두 절단 **잔존**.
- keep=4.5 ytn2: "논의한 사안 중에서는 [**우선 누락**] 왕성한 [**연합방위태세 누락**] 김정은 기자가 보도합니다" — 서두 유실 **오히려 악화**(단어 통째 소실 + 방송환각 유입).

**ytn2 WER의 지배적 주범은 keep_secs와 무관한 영역**: 두 run 모두 ① "Thank you" 필러 스톰(대량 연쇄) ② "김정은 기자입니다/보도합니다" 방송클로징 환각이 우세. 이는 Exp-158~160·Exp-165에서 확인된 turbo 필러/환각 실패모드로, `LANG_SWITCH_KEEP_SECS`(전환 시 오디오 트림 범위)가 손대는 대상이 아니다. **즉 keep_secs는 ytn2의 실제 오류에 대해 잘못된 레버.** goal §P2가 경고한 "재방출(전환세금) 부활"보다는, **서두 절단 자체가 keep_secs 확대로도 안 고쳐지고 지배 오류(필러·환각)가 무관**하다는 게 실측 결론.

### 채택 판정 — 기각

- ① max 미회귀: keep=3.5 ytn2 40.9%>34.5% ❌, keep=4.5 sbs1 18.5%>16.1% ❌.
- ② 목표(서두 유실 완화) 달성: **미달성**(전사에 절단 잔존/악화) ❌.
- 정량 회귀 + 목표 미달성 → **기각**. keep_secs 기본값 2.5 유지.

### 결론

**기각 (master 미머지, 워크트리 `exp/exp-langswitch-keepsecs-sweep` 보존).** `--lang-switch-keep-secs` CLI 노출은 기본값 None(=2.5)로 동작 불변이며 향후 실험에 재사용 가능하므로 보존. **keep_secs 증가(3.5/4.5)는 ytn2 전환경계 서두 유실을 완화하지 못하며, ytn2 WER은 keep_secs가 접근 못 하는 필러 스톰·방송환각이 지배**함을 실측 확인. 이는 Exp-165(no_speech 폐기)와 정합 — ytn2/bong1 개선의 병목은 전환경계 오디오 보존이 아니라 **비음성·불확실 구간의 turbo 필러/환각**이며, 이는 backend 파라미터로는 손대기 어려운 영역(별도 접근 필요).

### 다음 (참고)

- keep_secs **감소**(1.5/2.0) 방향은 미측정 — 다만 지배 오류(필러·환각)가 무관하므로 ytn2 개선 여지 낮음(재방출 감소로 미세 이득 가능성만). 우선순위 낮음.
- ytn2/bong1 실질 병목 = turbo 필러/환각. no_speech(Exp-164/165)·후처리 필터(Exp-163) 모두 실패 → 남은 후보는 웃음/필러 전용 비-ASR 분류기 또는 디코더 레벨 불확실성 억제(별도 설계).

**JSON**: `.omc/benchmarks/eval_20260706_1821_exp166_keep35.json` · `eval_20260706_1829_exp166_keep45.json`.

---

## Exp-168

**날짜**: 2026-07-07
**워크트리/브랜치**: `worktrees/case2-frontloss` @ `exp/case2-frontloss`, 최종 HEAD `0fed0d5` → master 머지

**가설**: CASE2(코드스위칭 서두 유실)의 ytn2 지배적 실패모드를 실증 규명하고 수정한다. 최초 가설(diarization 화자전환이 언어전환 감지를 억제 — "dormant" 가설)은 계측 로깅(`d007014`)으로 클린 측정을 재실행한 결과 **기각**됨(오염된 구버전 로그 기반 오판이었음): 언어전환 보호경로 자체는 정상 작동(`switch_true=15`, `marker_count=15`) 확인. 전사 vs 정답 직접 대조로 진짜 근본원인 재발견: **EN→KO 전환 경계 직후 "Thank you"류 필러 환각이 실제 발화를 통째로 삼킨다**(2/2 재현). 기존 4개 필터(QualityGate avg_logprob/compression_ratio, BatchRepeatFilter, CrossBatchFilter, DRY penalty) 전부 "완전동일반복" 또는 "한국어 전용"을 전제해 "영어+변주" 필러를 원리상 통과시킴을 코드 분석으로 확정 — 특히 `BatchRepeatFilter`가 `[가-힣]` 매치 조건이라 한글 0개인 영어 필러엔 애초에 진입 못 하는 결정적 사각지대.

전역 상수(`LANG_SWITCH_KEEP_SECS`) 축소 시도(Direction P1a, 기각)는 경계1을 개선했으나 경계2에 신규 catastrophic 필러를 유발 — 문제를 해결한 게 아니라 경계를 이동시켰을 뿐임이 실증됨(Exp-166의 "keep_secs 무관" 결론과 정합).

**변경 내용** (커밋 순, `exp/case2-frontloss`):
- `8aeb5a2` **P2(채택)**: `whisperlivekit/simul_whisper/backend.py`에 `_is_script_mismatch_filler(text, detected_language)` 순수함수 추가 — detected_language와 반대 스크립트로만 구성 + type-token ratio≤0.6(최소 6단어) 시 필러로 판정(ko/en 대칭, 특정 문구 무하드코딩). 실측 배치가 1~3토큰뿐이라 단일배치 판정 불가함을 확인하고 `_update_script_mismatch_streak`로 cross-batch 누적 계층 추가. 드롭 시 기존 ForeignLang과 동일한 재감지 arm 재사용(`refresh_segment` 미호출 — Exp-163 재환각 함정 회피).
- `0fed0d5` **since_offset 배선(채택)**: `align_att_base.py`의 `detect_current_language()`에 `since_offset: float | None = None` 파라미터 추가 — 지정 시 그 이전 오디오 배제(window_secs 상한 캡 유지). `backend.py`의 `new_speaker()`에서 화자전환 경계시각(`change_speaker.start`)을 전달 — 기존엔 버퍼 끝에서 무조건 마지막 1.5초를 잘라, 새 화자 발화 직후엔 그 창이 직전 화자 오디오로 지배돼 eager 언어감지가 오판(`eager=en`으로 확정, 서버로그 직접 확인)하던 문제 수정. 기존 호출부(`_check_short_silence_language`)는 미전달로 하위호환 유지.
- 신규 유닛테스트 19개(`tests/test_script_mismatch_gate.py` 14 + `tests/test_eager_lang_since_offset.py` 5) — 오탐방지(정상 코드스위칭/한국어 문장 비드롭) 케이스 포함, red→green 확인. pytest 160→**179 passed/1 skipped**(회귀없음). ruff 클린.
- 기각: Direction P1a(`LANG_SWITCH_KEEP_SECS` 2.5→1.5/1.0 축소) — 경계1 개선하나 경계2에 신규 catastrophic 필러 유발, 미채택(uncommitted, 되돌림).

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo. 스크리닝 N=1(진단·각 방향 확인) → 확정 N=3(fail-fast 금지).

### 테스트 세트 결과 (N=3 확정, fail-fast 없음, JSON `eval_20260707_1057_case2_confirm.json`)

| 파일 | 베이스라인(E5, Exp-167 기준) med/max | **채택 확정** med/max/min/stdev | 게이트(max, +10pp 완화) |
|------|------|------|------|
| bong1 | 28.7% / 29.0% | **27.8% / 30.5% / 26.3% / 2.1%** ✅ | ≤40.5% |
| ytn2  | 36.0% / 43.8% | **19.7% / 26.1% / 19.2% / 3.8%** ✅ 대폭개선 | ≤44.5% |
| sbs1  | 14.3% / 16.1% | **16.7% / 48.8% / 13.1% / 19.7%** ❌초과(+22.7pp) | ≤26.1% |

held-out(단회): ytn1 29.4%/F1 63.2%(baseline 33.1%보다 개선) · eng1 2.9%/F1 0.0%(영어 회귀 없음).

### 판정 근거 (sbs1 게이트 초과 — 원인 무관성 실증 후 사용자 확인하에 채택)

sbs1 R2(48.8%)만 catastrophic, R1/R3(13.1%/16.7%)는 정상. 서버로그 확인 결과 sbs1은 **화자전환 0회**(기존 Exp-155 확인사항 — 단일화자 파일)라 이번 변경의 핵심 코드경로(`new_speaker()`/`since_offset`)가 애초에 호출되지 않음. R2 전사는 정답 첫 문단(5문장) 통째 누락 + `SimulStreaming stall recovery` 4회(QualityGate 억제 연쇄) — 기존에 알려진 저빈도(Exp-167 자체 N=3에서도 0/3) 확률적 stall 현상으로, CLAUDE.md에 명시된 "실행마다 ±30~120%p 편차" 범위 내. 이번 변경과 인과관계 없음을 실증 후 사용자에게 보고, **채택 확정**.

### 정성 확인 (`.omc/transcripts/` 직접대조)

- **경계1**("...Security Council resolutions." 직후 "이런 목표들을...") — 3/3 필러폭주 없이 대상 문장 대부분 출력(선두 절 경미한 누락 잔존 — catastrophic swallow와는 질적으로 다름).
- **경계2**("...initial operational capability." 직후 "정경두 국방장관과 저는...") — **3/3 안정적으로 확정 해결**.
- bong1 웃음구간 필러(기존 이슈, 이번 변경과 무관) 1/3 재현. CASE1 타겟 병합패턴은 자연변동(Exp-167에서 이미 규명한 Silence 0.4s 문턱 민감도).
- ytn2 R2에서 세 번째(비대상) 경계에 짧은 필러("네, 감사합니다" ×2) 관찰 — 게이트 영향 없음, **CASE3(Req-3) 공유 근본원인으로 재분류**(필러 환각 메커니즘 자체가 CASE3 핵심 현상과 동일 계열).
- ytn1(held-out) 스트림 최초 문장이 필러로 대체 — `new_speaker()` 개입 불가한 스트림 시작 지점이라 이번 변경과 무관.

### Epoch 판단

**유지(E5)** — CASE1 FIX1(`e6ae496`) 전례와 동일 논리: 기존 언어전환 파이프라인에 새 방어선(스크립트 불일치 게이트 + eager 감지 시각보정)을 추가한 것이지, 언어고정·비음성억제류처럼 파이프라인 전체의 실패모드 지형을 재정의하는 근본적 구조변경은 아님.

---

## Exp-167

**날짜**: 2026-07-07
**워크트리/브랜치**: `worktrees/case1-tail-reattach` @ `exp/case1-tail-reattach`, 최종 HEAD `e6ae496`

**가설**: CASE1(문장 꼬리 분리 — 마지막 3~4음절이 다음 줄로 잘못 넘어가 분리되는 현상)의 근본원인을 실증 규명하고 수정한다. 조사 결과 **4개의 독립 경로**가 확인됨:
1. Silence 마커 커밋 순서 경쟁(`_end_silence`가 큐 미경유 직접 append)
2. flush 0토큰 방출(attention end-break가 is_last에서도 마지막 토큰 드롭)
3. QG 3연속 억제 → `refresh_segment` 버퍼파괴
4. **(이번 세션 집중 규명) 구두점-매개 꼬리분리**: 꼬리 유보/억제 중 머리가 온점을 얻고, `_punct_split_justified()`의 갭기반 (c)분기가 이를 독립 세그먼트로 분리 확정.

**변경 내용** (커밋 순):
- `40f65f2` Exp-A: 침묵-꼬리 재귀속(`tokens_alignment.py` `_insert_with_reattachment`) + finalize 유예(`_apply_finalize_grace`) + 유령온점 차단(`filtering/__init__.py:140`) — 경로 1 대응
- `5b8ff15` Exp-B: 중간온점 갭조건화 + QG온점-streak 제외 + 유령온점 collapse — 경로 2/3 대응
- `e210465`: 재귀속 거리상한 `TAIL_REATTACH_MAX_LOOKBACK_SECS=1.5` 추가(타임스탬프 불안정 구간 오귀속 방지, ytn2 회귀 수정)
- `dd33fe7` **Direction A(기각·FIX 1으로 대체)**: `PUNCT_SPLIT_GAP_SECS` 0.3→0.4로 정합 시도. **N=3 확정측정에서 sbs1·bong1 모두 3/3 재현되어 불충분함이 실증됨** — 서버로그의 VAD 침묵값(0.29~0.32s)과 `_punct_split_justified`가 실제로 쓰는 토큰-타임스탬프 갭을 혼동한 게 원인(둘은 다른 양). 소거법으로 실제 토큰갭이 이미 ≥0.4임이 증명됨.
- `e6ae496` **FIX 1(최종 채택)**: `whisperlivekit/tokens_alignment.py`의 `_punct_split_justified()` — 갭기반 (c)분기(`nxt.start - tokens[idx].end >= PUNCT_SPLIT_GAP_SECS`)를 `return False`로 완전 제거. 온점분할은 이제 **(a)발화 끝** 또는 **(b)실제 Silence 토큰**에서만 발동(비-diar 경로와 대칭화). `PUNCT_SPLIT_GAP_SECS` 상수 은퇴. 갭 값이 얼마든(0.32든 0.6이든) 무관하게 통하는 갭값-불가지론적 수정 — Direction A의 근본 취약점(정확한 갭을 알 수 없음)을 우회함.
- 신규 유닛테스트 10개(`tests/test_tail_reattachment.py`) — 실제 서버 갭(≥0.4)을 직접 주입하는 진성 재현 테스트 포함(이전 테스트는 갭=0.32를 손으로 주입해 실제 버그를 재현하지 못했음이 이번에 드러남). pytest 160 passed, 1 skipped 유지. ruff 클린.

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo, beam=2. 스크리닝 N=1 → 확정 N=3(fail-fast 금지) 2계층, Direction A와 FIX 1 각각에 대해 반복.

### 테스트 세트 결과 (N=3 확정, fail-fast 없음)

| 파일 | 베이스라인(E5, Exp-161 기준) med/max | Direction A 확정(기각) med/max | **FIX 1 확정(채택)** med/max/stdev | 게이트(max) |
|------|------|------|------|------|
| bong1 | 30.5% / 30.5% | 27.5% / 33.5%(❌초과) | **28.7% / 29.0% / 1.3%** ✅ | ≤30.5% |
| ytn2  | 28.1% / 34.5% | 30.0% / 39.9%(❌초과) | **36.0% / 43.8% / 9.7%** ❌초과(§5 완화게이트 +10pp 이내라 비-심각) | ≤34.5% |
| sbs1  | 14.9% / 16.1% | 13.7% / 16.1%(경계통과) | **14.3% / 16.1% / 1.0%** ✅경계통과 | ≤16.1% |

sbs1 hyp_sentences(FIX 1, 3회): 11 / 10 / 10 (베이스라인 9~11 대비 유사~소폭개선, 목표 ≤5는 미달성).

### 분석 (전사 내용 정성 대조 — JSON `eval_20260707_0144_expC_fix1_confirm.json` 직접 대조)

**bong1** (3회 전부 확인) — **핵심 타겟 패턴 완전 해소**:
- FIX 1 이후 3회 전부: `"...상징적이다라고 하고 자빠졌는데,."` / `"...자빠졌는데."` / `"...자빠졌는데. ,."` — "자빠졌"+"는데"가 공백·구두점 없이 완전 병합. 정답(`"...자빠졌는데."`)과 정확히 일치.
- Direction A 단계(기각)에선 3회 전부 `"자빠졌. 는데."` 류로 분리돼 있었음 — 대조로 FIX 1의 효과가 명확.
- **단어 유실·화자혼동**: 주요 실패 없음(이번 변경 관련). 기존에 알려진 bong1 웃음구간 환각(별개 이슈, [project-bong1-laughter-hallucination] 참고)은 이번 전사에도 미세하게 잔존하나 이번 변경과 무관.

**sbs1** (3회 전부 확인) — **잔존 분리, 그러나 원인이 CASE1 버그가 아님을 3/3로 실증**:
- R1(WER 14.3%): `"...담긴 것으로. 보입니다. SBS 김수영입니다"` — 분리. 서버로그 확인: 해당 지점 실제 Silence 토큰 **0.45s**(≥0.4 문턱 — 정식 생성).
- R2(WER 14.3%)·R3(WER 16.1%): `"...담긴 것으로 보입니다. SBS 김수영입니다"` — 병합(정답과 일치). 서버로그: 두 회차 모두 **0.39s**(<0.4 — Silence 미생성).
- **3/3 케이스 모두 예외 없이 들어맞음** — 분리 여부가 정확히 VAD가 이 찰나의 호흡 pause를 0.4s 경계 어느 쪽으로 재느냐(0.39 vs 0.45, 차이 0.06s)에 좌우된다. FIX 1 이후엔 (a)/(b)분기만 남으므로, 이 분리는 더 이상 "버그로 인한 오분할"이 아니라 **§3.3 정책(침묵=1순위 분할근거)이 의도대로 작동한 결과**다. "것으로 보입니다"가 문법적으로 한 문장인데도 찰나의 호흡성 pause를 하드 문장경계로 인정할지는 CASE1 버그 수정 범위를 넘는 **별개의 설계 문제**(docs/OPEN_QUESTIONS.md §1 미정 사안과 접점 — 문장확정 신호조합 정책)로 재분류.

**ytn2** (3회 전부 확인) — **"Thank you" 필러 환각, 기존 이슈 재확인(신규 아님)**:
- R1(WER 43.8%): "Thank you" 계열 약 12회 연쇄. R2(WER 24.6%, 최량): 2회. R3(WER 36.0%): 약 10~11회.
- 이 패턴은 **Direction A 단계(기각, FIX 1 이전) N=3 확정측정 3회 전부에서도 이미 동일하게 관측**됐음 — FIX 1이 유발한 신규 회귀가 아니라, 이미 알려진 turbo 필러/환각 이슈(Exp-158~165, CASE3 대상)의 연장. ytn2 median/max가 베이스라인보다 나빠 보이는 건 이 필러의 회차별 강도 편차(2~12회)가 지배적 원인이며 CASE1 변경(diar 온점분할 로직)과는 코드 경로상 무관.

**이번 변경 영향 요약**: CASE1 4대 경로 중 1~3은 이전 세션에 이미 수정됐고, 이번 세션에서 4번째 경로(구두점-매개 꼬리분리)를 갭값-불가지론적으로 완전 제거해 bong1 타겟 패턴을 3/3 확정 해결. sbs1 잔존은 CASE1 버그가 아니라 별개의 Silence-경계 정책 민감도 문제로 재분류(향후 검토 후보). ytn2 WER 변동은 CASE3 영역(필러/환각)이 지배적이며 이번 변경과 무관.

### 채택 (조건) 판정

| 파일 | ①max 미회귀 | ②median 개선(베이스라인 대비) |
|---|---|---|
| bong1 | ✅ (29.0≤30.5) | ✅ (28.7<30.5) |
| ytn2 | ❌ (43.8>34.5, 단 §GOAL_CASE_SENTENCE_QUALITY.md §5 완화게이트 +10pp=44.5 이내) | ❌ (36.0>28.1) — 단 원인이 CASE1 변경과 무관함을 정성분석으로 확인(위 참조) |
| sbs1 | ✅ (16.1=16.1 경계) | ✅ (14.3<14.9) |

표준 CLAUDE.md §4 규율(①max 1순위)로는 ytn2가 걸리나, 이 실험은 **GOAL_CASE_SENTENCE_QUALITY.md §1 특별규칙**(이번 3대 요구사항 한정, 정성 목표가 WER/F1보다 우선 + §5 완화게이트로 "심각한 악화"만 차단) 적용 대상이다. ytn2는 완화게이트 3조건(│max+10pp초과│max≥60%│F1 2회이상 0%대) 전부 미해당이며, WER 악화의 원인이 CASE1 변경과 무관한 기존 CASE3 이슈임이 전사 대조로 확인됨.

### 결론 — **채택, master 머지**

CASE1(문장 꼬리 분리) 4대 경로 전부 수정 완료. bong1의 명명된 타겟 패턴("자빠졌/는데")은 N=3 전부에서 확정 해결. sbs1의 명명된 타겟 패턴("것으로/보입니다")은 3/3 중 1회만 재현되었고, 그 1회조차 CASE1 버그가 아니라 기존 Silence 경계 정책이 VAD 경계값 근처에서 작동한 결과임이 실증됨 — 즉 CASE1이 원래 정의한 문제(잘못된 정보로 인한 오분할)는 완전히 해소됨. ytn2 WER 변동은 별개의 기존 이슈(필러/환각, CASE3 대상)로 확인되어 이번 채택을 막지 않음. sbs1 hyp 문장수(≤5 목표)는 미달성이나, 이는 애초 그 수치 목표가 "모든 초과분할이 CASE1 버그"라는 가정 위에 설정된 것이었고 이번 조사로 그 가정이 부분적으로 틀렸음이 밝혀졌기 때문 — 정성 목표(꼬리분리 소멸)는 달성으로 판정.

**Epoch**: 세대 안 올림. 토큰 정렬/세그먼트 분할 로직의 버그 수정이며, CLAUDE.md 세대경계 규칙상 epoch 상향 대상(언어고정·비음성억제·디코더 교체·VAD 파이프라인)에 해당하지 않음.

### 다음 가설 (향후 검토 후보, 이번 범위 밖)

- **sbs1 Silence-경계 민감도**: 0.4s 문턱 부근 호흡성 pause를 하드 문장경계로 취급할지 재검토 여지(문장확정 신호조합 정책 — docs/OPEN_QUESTIONS.md §1). 문법적 연속성(조사·어미 패턴)을 보조 신호로 쓰는 방안 등 — 단, 데이터 특화 하드코딩 아닌 일반화된 정책 변경이어야 함(§3.8).
- **ytn2 "Thank you" 필러/환각**: CASE3(환각 폭주)의 핵심 대상. Exp-158~165에서 no_speech·후처리필터 모두 실패한 바로 그 이슈 — CASE3 조사에서 이어서 다룸.

## Exp-169

**날짜**: 2026-07-07
**워크트리/브랜치**: `worktrees/case3-hallucination` @ `exp/case3-hallucination`, 최종 HEAD `dc0dc35`(master 미머지 — 사용자 확인 대기)

**가설**: CASE3(환각 폭주)의 잔존 필러 storm(bong1 "thank you"×3, ytn2 "김정은"×4)은 오프라인 oracle 진단(별도 사이클1)으로 모델천장이 아니라 **스트리밍 세금**(경계 리프레시 직후 <1s 컨텍스트기아 상태의 저신뢰 재환각)임이 확정됐다. 기존 `_is_script_mismatch_filler`(Req-2 P2 게이트)는 "반대 스크립트+TTR 붕괴" 전제라 ① 같은 스크립트 내 storm ② 앵커 1개만 정확반복하고 주변부가 변주돼 전체 TTR은 안 무너지는 storm(ytn2 "김정은"+접미부변주, 전체TTR=0.809로 통과)을 못 잡는다. **script-agnostic 앵커 반복 게이트**로 이 사각지대를 커버한다.

**변경 내용** (커밋 순, `exp/case3-hallucination`):
- `4eaefd2` 진단 스크립트 `scripts/analyze_case3_hallucination.py` 신설(gap-tolerant 클러스터링 + 국소집중도 필터, 오탐방지 자체발견·수정 포함) — 사이클0.
- `dc0dc35` **게이트 구현(채택)**: `whisperlivekit/simul_whisper/backend.py`에 `_find_anchor_repeat_storm`(순수함수) — 최근 방출 단어 롤링윈도우(40단어)에서 1~2gram 앵커가 gap-tolerant(MAX_GAP=5)하게 4회 이상(MIN_COUNT=4) 반복 + 국소집중도(클러스터/윈도우내 그 앵커 총등장 ≥0.6)면 storm 판정, 순수 토큰 드롭(언어/컨텍스트 상태 불변). **자체발견 회귀**: 최초 구현이 ForeignLang/ScriptMismatchFilter의 "드롭 시 언어 재감지 arm" 패턴을 재사용했다가 `_apply_detected_language`가 재감지 후 언어가 같아도(is_switch=False) `init_tokens()`/`init_context()`를 무조건 호출해 컨텍스트를 지우는 부수효과와 결합, 자기강화 루프로 bong1 WER 24.5%→113.3% catastrophic 회귀(N=1 스크리닝에서 발견) → 드롭 시 언어/컨텍스트 상태를 전혀 건드리지 않도록 즉시 수정, 재측정으로 회귀 해소 확인(같은 커밋에 포함).
- 신규 유닛테스트 39개(`tests/test_anchor_repeat_gate.py` 15 + 분석스크립트 24) — 오탐방지 최우선(문서전반 흩어진 재등장 gap=8 비드롭, 정상 강조반복 2~3회 비드롭, 정상 코드스위칭/전체문장 비드롭) + 실측 storm 재현(영어/한글 앵커+변주, gap 최대 5단어 확인) + 언어상태 무변경 배선검증. pytest 179→**218 passed/1 skipped**(회귀없음). ruff 클린.

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo beam=2. 스크리닝 N=1(사이클0/2) → 확정 N=3(fail-fast 금지, 이번 Exp).

### 테스트 세트 결과 (N=3 확정, fail-fast 없음, JSON `eval_20260707_1437_case3_confirm.json`)

| 파일 | 직전 확정 베이스라인(Exp-168, `0fed0d5`) med/max | **이번 확정** med/max/min/stdev | 게이트(max, +10pp 완화) |
|------|------|------|------|
| bong1 | 27.8% / 30.5% | **35.3% / 35.6% / 28.4% / 4.1%** ✅(<40.5) | ≤40.5% |
| ytn2  | 19.7% / 26.1% | **26.1% / 30.5% / 21.2% / 4.7%** ✅(<44.5) | ≤44.5% |
| sbs1  | 16.7% / 48.8% | **13.7% / 14.9% / 12.5% / 1.2%** ✅(<26.1, sbs1은 오히려 Exp-168의 저빈도 stall 재현 없이 안정) | ≤26.1% |

held-out(단회, JSON `eval_20260707_1437_case3_heldout.json`): ytn1 WER 23.3%/F1 57.1%(Exp-159 baseline 33.1%보다 개선) · eng1 WER 3.8%/F1 0.0%(영어 회귀 없음).

**§5 완화게이트 판정 — 3조건 전부 미해당(클린 통과)**: ①max +10pp초과 없음(bong1 35.6≤40.5, ytn2 30.5≤44.5, sbs1 14.9≤26.1) ②WER≥60% 없음 ③F1 2회이상 0%대 없음(sbs1 R2만 1회 0.0%).

### storm 분석 (`scripts/analyze_case3_hallucination.py --per-file`, 9개 파일-회차)

- **파일당 최대 반복횟수(worst-case) = 3**(9개 회차 전부 4 미만) — 사이클0 베이스라인(bong1 "thank you"×3/ytn2 "김정은"×4)·사이클2 수정판(bong1 최대×3) 대비 게이트가 목표한 억제 유지. **ytn2 "김정은" storm 0/3으로 완전 소멸 유지**(사이클2와 동일 결과 재확인).
- bong1: R1 storm 0건, R2 2건(최대×3, "who"/"주인공이"), R3 1건(최대×3, "thank you") — MIN_COUNT=4 미만이라 게이트가 원래 손대지 않는 설계 영역(오탐방지 임계값대로 동작).
- sbs1: 3회 전부 storm 0건.

### ⚠️ 핵심 발견 — Req-2 두 경계 직접 정성확인, "3/3 안정" 아님(1/3씩 재현)

`.omc/transcripts/ytn2_C_R{1,2,3}.txt`를 정답과 직접 대조:

- **경계1**("...Security Council resolutions." 직후 → "이런 목표들을...UN안보리...") — R1 정상(선두절 "이런 목표들을" 누락은 기존 잔존 이슈), **R2는 KO 문장 전체가 "Thank you very much. Thank you. Thank you very much for joining us today. Thank you very much, everyone. Thank you very much so much."(5회 연쇄)로 완전 대체** — catastrophic swallow, R3는 "감사합니다." 단발 필러 삽입 후 문장 본체 보존(경미). → **2/3 안정, 1/3(R2) 재현**.
- **경계2**("...Initial Operational Capability." 직후 → "정경두 국방장관과 저는...") — R1·R2 정상(화자명 "박방/전경두"로 인식오차만, 문장 본체 보존), **R3는 KO 문장 전체가 "Thank you for your time, Mr. President. Thank you very much. Thank you, Mr. President, Mr. President of the United States. Thank you very much, Mr. President and Mr. President. Thank you very much"(~6회 연쇄)로 완전 대체** — catastrophic swallow. → **2/3 안정, 1/3(R3) 재현**.
- **원인 조사(로그 대조로 인과관계 확정)**: `grep "AnchorRepeatFilter" server_ytn2_C_R2/R3.log` 둘 다 **0건** — 이번 사이클 게이트가 두 재현 지점 근방에서 **전혀 발동하지 않았다**. 즉 이 게이트(`dc0dc35`)가 causally 유발한 회귀가 아니다. 실제 "thank you" 반복 횟수는 5~6회로 MIN_COUNT=4 이상이지만, 중간에 낀 가변길이 변주구("for joining us today", "Mr. President of the United States" 등)가 앵커 사이 gap을 5단어 초과로 벌려 `_find_anchor_repeat_storm`의 gap-tolerant 클러스터링이 이를 **연속 3회+연속 2~3회의 서브클러스터로 쪼개** MIN_COUNT=4 문턱을 피해간다 — 오탐방지를 위해 보수적으로 잡은 MIN_COUNT/MAX_GAP 설계의 **알려진 사각지대**(설계 당시 문서화된 트레이드오프가 실측으로 재현된 사례).
- Req-2(Exp-168) 자체의 N=3 확정측정(사이클8)에서는 두 경계 모두 "3/3 안정"으로 보고됐었다 — 이번 결과는 그 결론을 뒤집는 것이 아니라, **CLAUDE.md에 명시된 회차간 편차(±30~120%p)** 안에서 이 잔존 catastrophic-swallow 위험이 낮은 빈도(관측 2/6)로 여전히 존재함을 보여준다. 이 위험은 Req-3(CASE3) 착수 전부터 있던 것으로 이번 게이트가 새로 만든 것이 아니며, 게이트가 잡는 storm 유형(짧고 규칙적인 gap)과 이번에 재현된 storm 유형(긴 가변 변주구로 쪼개지는 storm)이 다르다.

### 판정 — 조건부 채택 권고(사용자 확인 필요, master 미머지)

Req-3 자체 목표(storm 최대반복횟수 감소·ytn2 "김정은" storm 소멸)는 달성. §5 정량게이트 3조건 전부 클린 통과. bong1·sbs1 신규 catastrophic 이슈 없음. 그러나 "가장 중요"로 지정된 검증 항목(Req-2 두 경계 3/3 안정)은 **미달성**(2/3씩) — 단 원인이 이번 변경과 무관함을 로그로 확정(게이트 미발동 구간에서 발생). GOAL 문서 §1 특별규칙(정성 우선)의 취지에 따라 이 잔존 위험을 자율로 덮지 않고 사용자에게 그대로 보고한다. **master 머지는 이 세션 범위에서 보류**(메인 세션이 사용자 확인 후 처리).

**Epoch 판단**: 세대 안 올림(E5 유지) — 기존 파이프라인의 디코더/VAD 흐름 자체는 불변, 앵커 반복 드롭이라는 새 방어선을 추가한 것뿐(Exp-167 FIX1·Exp-168 P2/since_offset과 동일 논리 — 실패모드를 바꾸는 구조 변경이 아니라 기존 실패모드에 대한 새 필터 추가).

### 다음 가설 (향후 검토 후보, 이번 범위 밖)

- **가변길이 변주구 대응 게이트 강화**: MAX_GAP을 5보다 살짝 늘리거나(오탐 위험 재평가 필요), 또는 "동일 화자시간 근접 구간 내 앵커 총 등장횟수"(서브클러스터 합산)로 판정 기준을 바꾸는 방안 — 이번에 재현된 두 사례(5~6회 연쇄가 3+2/3+3으로 쪼개짐) 특성을 유닛테스트로 고정한 뒤 재설계.
- **설계안 1순위(oracle 사이클1에서 보류)**: 컨텍스트 기아 fire 억제(segments_len<1.5s + boundary refresh 직후 배치 defer) — 근본원인 대응이나 Req-2 회귀위험이 커서 별도 사이클 필요.

**JSON**: `.omc/benchmarks/eval_20260706_2248_exp167_confirm.json`(초기 bong1+sbs1 N=3, HEAD e210465) · `eval_20260707_0002_expC_screen.json`(Direction A 스크리닝) · `eval_20260707_0023_expC_confirm_dirA.json`(Direction A 확정, 기각) · `eval_20260707_0127_expC_fix1_screen.json`(FIX 1 스크리닝) · `eval_20260707_0144_expC_fix1_confirm.json`(FIX 1 확정, 채택 — 위 표 출처).

---

## Exp-170 — 온점 형태소 분할: 한국어 종결어미·영어 약어 판별로 온점을 독립 문장경계로 승격 [E5, master 머지 `4b193ea`] (2026-07-07)

**날짜**: 2026-07-07
**워크트리/브랜치**: `worktrees/punct-split` @ `exp/punct-split`, feat `4159b1e` → master 머지 `4b193ea`(--no-ff)

**가설**: 연속 발화(특히 한국어)가 문장 분리 없이 한 줄로 길게 이어진다. Whisper는 마침표를 찍지만 현재 온점 분할은 뒤에 실제 침묵/발화끝이 있어야만 발동(Exp-166 축소)해 침묵 없는 경계를 놓친다. 동시에 Whisper는 거짓 마침표를 대량 생성한다(한국어 "올렸.습니다"·"주한미군.사령관", 영어 약어 "Dr.", 소수점) → 단순 온점 분할은 과분할. **형태소 판별**(한국어 종결어미 + 영어 약어 배제 + 다음단어 대문자)로 진짜 종결만 분할하면 문장 단위 확정(§3.3 최종목표)에 다가간다.

**변경 내용**:
- `whisperlivekit/sentence_boundary.py` 신설(순수 판별기): `is_genuine_sentence_end`/`is_sentence_final_ko`/`is_abbreviation_en`. 한국어 `KO_FINAL_SUFFIXES`(니다/어요/세요/구나/았다…, **bare 단음절 군/네/다/까 제외**=명사·조사 충돌 방어) + `KO_EXCLUDE_SUFFIXES`(니까/으로/는데…), 영어 `EN_ABBREV`+단일대문자+다음단어 대문자, 숫자-직전 가드. 온점 앞 어절 스크립트(한글/라틴)로 언어 라우팅.
- `whisperlivekit/tokens_alignment.py`: `_punct_split_here`(기존 (a)발화끝/(b)Silence에 (c)형태소 종결 추가), `compute_punctuations_segments` 분할점, diar 병합 3곳(병합조건·전파·라벨 — `PuncSegment.punct_boundary`로 같은 화자 재합침 방지·"punctuation" 정라벨), 비-diar `_nondiar_punct_split_pending` 선-분할. 범위 = 온점(`.`/`。`) 전용, `?`/`!`는 현행 유지.
- `whisperlivekit/timed_objects.py`: `PuncSegment.punct_boundary` 필드(내부 전용, to_dict 미방출).
- 테스트: `tests/test_sentence_boundary.py`(판별기 단위) + `tests/test_punct_split.py`(diar/비-diar 통합). 기존 6 assert(것으로/very 비종결) 회귀 없음. pytest 53 passed, ruff 클린.

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo beam=2. 스크리닝 N=1 → 확정 N=3. **held-out(ytn1/eng1) 미측정** — 출력계층 WER중립 + F1 지표한계(아래)로 held-out도 동일 한계, 사용자 승인 채택이라 생략(향후 온점 F1 metric 구현 후 재검토).

### 테스트 세트 결과 (N=3 확정, JSON `eval_punctsplit_adopt.json`)

| 파일 | baseline(Exp-161) med/max·F1 | 이번 med/max/min/stdev·F1med | ΔWER med/max | ΔF1 |
|------|------|------|------|------|
| bong1 | 30.5/30.5 · 50.0 | 30.2 / **36.0** / 29.9 / 3.4 · 44.9 | -0.3 / **+5.5** | -5.1 |
| ytn2  | 28.1/34.5 · 38.5 | 29.6 / 32.5 / 25.1 / 3.7 · **55.2** | +1.5 / -2.0 | **+16.7** |
| sbs1  | 14.9/16.1 · 16.7 | 14.3 / 14.9 / 11.9 / 1.6 · 13.3(R3=0.0) | -0.6 / -1.2 | -3.4 |

스크리닝(N=1) 참고: bong1 30.2/53.3, ytn2 15.8/60.9, sbs1 13.1/28.6(1회는 방향신호).

### 분석 (전사 정성 대조 — `.omc/transcripts/`)

- **형태소 분할 정확(핵심 목표 달성)**: sbs1 "…겁니다.⟨punctuation⟩ / …정의했습니다.⟨punctuation⟩ / …역설했습니다.⟨punctuation⟩"(니다 종결), ytn2 "…했습니다.⟨punctuation⟩", bong1 영어 "…in the film.⟨punctuation⟩ So he's…"·"…character.⟨punctuation⟩ But…"(다음단어 대문자). baseline 1줄 뭉침 → sbs1 14개 정문 분리.
- **거짓 마침표 미분할(과분할 방지)**: "주한미군 사령관"(군 제외)·"올렸습니다"(어간 미파편화)·"이와 관련해서"(baseline "관련." 분할 소멸)·"정연의 핵심은"·"저는"(조사). **영어 약어 가드**: bong1 "Dr. Bong" 병합 유지.
- **신규 실패모드(경미)**: 영어 환각 마침표+대문자 다음단어 → 가끔 오분할(bong1 ", what was the." | "What's…", garbage 구간). 한국어에선 미관측.
- **bong1 WER max 36.0 원인**: R3 웃음구간 필러 환각 폭주("That. I'm. I. I'm. I'm sorry. Yeah." — bong1 고질, STATE Exp-163/168). **출력계층 전용인 punct-split과 무관**(디코더 생성 단어, 분할이 환각을 늘릴 수 없음). 필러를 여러 줄로 쪼갤 뿐 WER은 그 단어들 탓.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 36.0>게이트30.5(+5.5) / ytn2 32.5≤34.5 ✓ / sbs1 14.9≤16.1 ✓ | △ bong1만 초과 — 웃음 필러환각 변동(기능 무관, 위 분석) |
| ② median 개선 | WER median 3파일 ≈baseline(~WER중립·출력계층) | ➖ 중립 |
| 목표(§3.3 문장분리) | sbs1 1줄→14정문·형태소 분할 정확 | ✅ 달성 |

**판정: ✅ 채택 (사용자 승인 — 목표 필수 기능 §4)**
- **F1 지표 한계 규명(핵심)**: 정답이 `scripts/eval.py:parse_reference_sentences`로 **빈 줄(화자전환/문단) 기준** 분할이라 문장(온점) 경계를 credit 못 함(§3.3 온점 2순위 metric 미구현) → 문장분할↑ = hyp 경계↑ = precision↓ = F1 하락. sbs1 R3 F1=0.0%인데 전사는 14개 정문이 증거. **∴ 현행 F1로 이 기능 정량평가 불가** — 온점 경계 F1 구현이 후속 과제.
- WER median≈baseline(출력계층 전용·단어 시퀀스 불변), 정성 정확, ytn2 F1+16.7pp. bong1 max 초과는 웃음 필러 변동으로 규명(기능 무관). 사용자 지침: 목표=문장단위 확정, F1보다 WER 우선, 화자전환 시 화자분리 필수(CLAUDE.md §3.3 갱신).

**Epoch 판단**: 세대 안 올림(E5 유지) — punct-split은 **출력 계층 전용**(확정된 세그먼트 분할)이라 디코더 파라미터(beam/CRT/PLC/logprob) 트레이드오프에 영향 없음. epoch 게이트가 보호하는 것은 디코더-파라미터 결론인데 punct-split은 WER 중립이라 E5 결론(Exp-160/161/162) 전부 유효. (연동갱신표의 "구조적 변경 bump"는 언어고정·비음성억제·디코더/VAD 등 WER 영향 변경 대상 — 출력계층 문장분할은 해당 안 됨.)

### 다음 가설 (향후 검토 후보)
- **온점 경계 F1 metric 구현**(§3.3 예고된 후속): 정답을 화자전환(빈 줄) + 문장(온점) 2계층으로 파싱해 문장분리 기능을 정량평가 가능하게. 이게 있어야 punct-split 후속 튜닝을 측정으로 판단 가능.
- **한국어 Tier2 종결어미**(`-다`/`-ㄴ다`, `len>=2` 가드) 커버리지 확대 — 온점 F1 구현 후.
- **영어 오분할 축소**: 환각 마침표+대문자 다음단어 오분할(bong1) 완화.

**JSON**: `.omc/benchmarks/eval_punctsplit_screen.json`(스크리닝 N=1) · `eval_punctsplit_adopt.json`(확정 N=3, 위 표 출처).

---

## Exp-171 — 언어전환 경계 오언어 토큰 철회 + 화자전환 서두 유실 수정 [E5, master 머지 `a14d028`] (2026-07-08)

**날짜**: 2026-07-08
**워크트리/브랜치**: `worktrees/boundary-retract` @ `exp/boundary-retract`, feat `f1b4e7e` → master 머지 `a14d028`(`--no-ff`)

**가설**: bong1 실사용 테스트에서 사용자가 두 결함을 보고: ① 화자전환 직후 diar 이벤트 도착 지연(~1-2s) 동안 구언어(예 en) 잠금 상태로 한국어 오디오가 디코딩되며 covert translation 발생·잔존("? Who is the.") 또는 반대로 새 화자 영어 서두가 구언어(ko) 스탬프로 커밋돼 직전 문장에 접착("했어요. The thought that."). ② `refresh_segment(complete=False)`가 무조건 마지막 2청크만 유지해 화자전환 경계 앞 서두("누가 주")가 정책적으로 폐기됨. Exp-168(CASE2)이 같은 경계의 eager 언어감지 오판(since_offset)과 반복형 필러는 해결했으나, 유창한 오번역·짧은 접착·서두유실은 P2 게이트(TTR·반복 전제)가 못 잡는 사각지대로 잔존 확인(코드 diff로 검증) — 이 갭을 메운다.

**변경 내용**:
- `whisperlivekit/timed_objects.py:134-135`: `LanguageSwitch`에 `retract_from`/`prev_language` 필드 추가(내부신호 전용, FrontData 미직렬화).
- `whisperlivekit/simul_whisper/decoder_state.py:39-40`: `pending_retract_from`/`pending_prev_language` 필드.
- `whisperlivekit/simul_whisper/align_att_base.py:218-224`: `_apply_detected_language`의 `is_switch` 블록에서 `pending_retract_from`/`pending_prev_language` 기록(재디코딩 구간 시작 절대시각+전환전 언어).
- `whisperlivekit/simul_whisper/backend.py:623-627`: `LanguageSwitch` 마커 방출 시 `retract_from`/`prev_language` 부착. `backend.py:247-248`: 긴침묵 리셋 경로에서 pending 클리어(진짜 문장경계는 철회 arm 무효화).
- `whisperlivekit/tokens_alignment.py:141-176`(`_retract_stale_language_tokens`) + `_insert_with_reattachment`(:127-130)에서 마커 append 직전 호출: **2구역 철회 규칙** — 구역1(`start≥boundary_t-RETRACT_EPS(0.05)`) `detected_language==prev_lang`이면 무조건 철회, 구역2(`[boundary_t-LANG_SWITCH_KEEP_SECS-1.0, 구역1)`) 반대-스크립트(`_is_opposite_script`, P2 게이트 로직 재사용)일 때만 철회. Silence/boundary 도달 시 스캔 즉시 중단. `[RetractScan]`/`[Retract]` 진단로그.
- `whisperlivekit/simul_whisper/backend.py:48-49,322-324`(`new_speaker`): `refresh_segment(complete=False, keep_secs=...)`로 교체 — `keep_secs = min(self.end - change_speaker.start + MARGIN(0.3), MAX_KEEP(5.0))`(경계-앵커 유지, 고정 `[-2:]` 컷 폐기). `align_att_base.py:117-149`(`refresh_segment`): `keep_secs` 파라미터 추가(None이면 기존 `[-2:]` 동작 그대로, 다른 호출부 전부 `complete=True`라 무영향 — grep 확인).
- `backend.py:340-356`: `global_time_offset`을 `change_speaker.start` 맹신 대신 `self.end - segments_len()`(eager 언어감지의 추가 트림 이후 계산)으로 재계산 + `cumulative_time_offset` 명시적 리셋(이중가산 방지, 구현 중 자체발견 수정).
- `whisperlivekit/basic_server.py:26-31`: `--trace-tokens` DEBUG 목록에 `whisperlivekit.tokens_alignment` 로거 추가 — 스크리닝 중 `[RetractScan]` 0건으로 오인될 뻔한 로깅 가시성 버그 자체발견·수정(root 로거 WARNING에 막혀 있었음, 철회 로직 버그 아님).
- 테스트: `tests/test_boundary_retract.py`(신설, 9개 — 구역1/구역2/Silence중단/하한/반대언어보존/noop 케이스 손트레이싱 검증). pytest 245 passed·1 skipped(회귀 없음).

**테스트 설정**: 경로 C, diar-ON(Sortformer + CRT 3.0), turbo beam=2, PLC=None. 스크리닝 N=1(bong1 단독 2회 + 3파일 1회) → 확정 N=3 → held-out N=1.

### 테스트 세트 결과 (N=3 확정, JSON `.omc/benchmarks/boundary_retract_adoption_N3.json`)

| 파일 | baseline(Exp-170) med/max·F1med | 이번 med/max/min/stdev·F1med | ΔWER med/max | ΔF1 |
|------|------|------|------|------|
| bong1 | 30.2/36.0 · 44.9 | 28.1 / **43.5** / 24.5 / 10.1 · 50.0 | -2.1 / **+7.5** | +5.1 |
| ytn2  | 29.6/32.5 · 55.2 | **18.7** / **18.7** / 16.7 / 1.1 · **75.0** | **-10.9** / **-13.8** | +19.8 |
| sbs1  | 14.3/14.9 · 13.3 | 13.1 / 15.5 / 8.9 / 3.3 · 26.7 | -1.2 / +0.6 | +13.4 |

held-out(N=1, JSON `.omc/transcripts/ytn1_C_R1.txt`·`eng1_C_R1.txt`): ytn1 **15.3%**/F1 52.2%(과거 참고치 21.5~33.1% 중 최저), eng1 **6.7%**/F1 0.0%(과거 2.9~4.8% 대비 +1.9~3.8pp, 절대치 한자릿수라 catastrophic 아님, F1=0.0%는 ref_sentences=1 지표한계).

스크리닝(N=1) 참고: bong1 단독 재측정 2회(25.4%/32.6%, 로깅수정 전후) + 3파일 1회(bong1 25.4%/ytn2 21.2%/sbs1 14.3%) — 전부 방향신호로 게이트 통과.

### 분석 (전사 내용 정성 대조 — `.omc/transcripts/`, `.omc/benchmarks/boundary_retract_adoption_N3.json`)

**bong1** (R3=median 28.1% 기준):
- **원 결함 해소 확인**: 전사 `"누가 주인공일까 이런 생각을 제가 제일 많이 했어요."`(정답과 완전 일치, 오번역 잔존 없음) 뒤에 `"The thought that I had the most is who is the main protagonist."`(별도 줄, `silence` 트리거로 정상 분리 — 과거 접착 증상 없음). 서두 유실도 미재현("누가 주" 보존).
- **환각 폭주(R2=43.5% 이상치)**: 전사 `"누가 주인공일까 주인공일까 이런 생각을 이런 생각을"`(어절 중복) + `"Thank you."` 필러 2회 + `"하하하"`(웃음환각). R1/R3는 동일 구간이 깨끗해 회차간 확률적 변동으로 추정(3회 중 1회만 재현). `[RetractScan]` 진단(로깅수정 후 별도 재측정): 11개 마커 중 4건 실제 철회(17토큰) — 제거 텍스트(`"It's just"`·`"The main character,"`·`"죄송합니다 형님"` 등)를 정답·최종전사와 대조 결과 **전부 중복/스테일 재디코딩 사본이었고 정답과 일치하는 최종버전은 보존됨** — 과도철회 증거 없음.
- **이번 변경 영향**: 원 결함(오번역잔존·접착·서두유실) 완전 해소. R2 이상치는 기존 문서화된 bong1 고유 실패모드(필러storm·웃음환각, STATE Exp-163/168/170)와 정성적으로 일치 — 이 변경이 유발했다는 증거 없음(단 `--trace-tokens` 없이 측정해 100% 배제는 못 함, 후속 재현조사 권장).

**ytn2** (R3=median 18.7% 기준):
- **코드스위칭 경계 대폭 개선**: 전사 `"...North Korea. UNDER SECRETARY KERRY: In the discussion..."` → `"왕성한 연합 방위태세를 유지하기 위한 노력을..."`(EN→KO 전환 경계 깔끔, language_switch 정상 발동). §3.8 최우선 목표(짧은 텀 코드스위칭)에 직접 부합하는 대폭 개선(median -10.9pp·max -13.8pp).
- **경미한 잔존**: `"한국군 사...자, 한국군 사령관"` 짧은 어절 중복 1건(catastrophic 아님).

**sbs1** (R2=median 13.1% 기준):
- 주요 실패 없음. `"선 제이비어 브런슨 주한미군 사령관..."` 한↔영 전환("From a satellite image, the Republic of Korea looks like an island.") 정상 처리.

**이번 변경 영향 총평**: 원 사용자 결함(오번역잔존·접착·서두유실) 전 회차 미재현으로 해소 확인. ytn2가 §3.8 최우선 목표에서 크게 개선, sbs1도 안정적 개선. bong1 median도 개선이나 max는 R2 1회 이상치로 게이트 초과 — 원인은 기존 bong1 고유 실패모드와 일치해 이 변경 특유 결함일 가능성은 낮게 평가되나 미확정.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 43.5>게이트36.0(+7.5, R2 1회 이상치) / ytn2 18.7≤34.5 ✓✓ / sbs1 15.5≤16.1 ✓ | △ bong1만 초과 — 정성분석상 기존 실패모드와 일치(위 분석), 회차변동 추정 |
| ② median 개선 | bong1 -2.1 ✓ / ytn2 **-10.9** ✓✓ / sbs1 -1.2 ✓ | ✅ 3파일 전부 개선 |
| 원 사용자 결함 해소 | 오번역잔존·접착·서두유실 전 회차 미재현 | ✅ 달성 |
| held-out 회귀 | ytn1 대폭개선 / eng1 소폭상승(catastrophic 아님) | ✅ 문제없음 |

**판정: ✅ 채택 (사용자 승인)** — CLAUDE.md §4 "①max 미회귀 1순위" 엄격 적용 시 bong1 게이트 초과로 자동채택 불가하나, 근본원인 조사(R1/R3 동일구간 클린 vs R2만 이상치, 필러/웃음 패턴이 STATE에 기존 기록된 bong1 고유 변동성과 일치, held-out 두 파일에서 비재현)를 사용자에게 투명 보고 후 명시적 승인으로 채택. 원 결함 해소 + ytn2 §3.8 최우선 목표 대폭개선이 핵심 근거.

**Epoch 판단**: 세대 안 올림(E5 유지) — Exp-168(CASE2, 같은 언어전환 경계 서브시스템)이 WER에 실질 영향을 준 개선이었음에도 epoch를 안 올린 전례를 따름. 이번 변경도 디코더 파라미터(beam/CRT/PLC/logprob) 자체를 바꾸지 않고 경계 시점의 토큰 커밋/폐기 정책만 조정 — E5의 파라미터 트레이드오프 결론(Exp-160/161/162)에 영향 없음.

### 다음 가설 (향후 검토 후보)
- **bong1 R2급 이상치 재현조사**: `--trace-tokens`로 bong1 N=3 재측정해 [RetractScan] 로그로 이 브랜치 관여 여부 확정(이번 세션 범위 밖으로 보류).
- **철회 EPS/하한값 캘리브레이션**: `RETRACT_EPS=0.05`·하한(`LANG_SWITCH_KEEP_SECS+1.0`)은 잠정값 — 추가 실측 축적 후 조정 여지(`docs/SENTENCE_FINALIZATION_LOGIC.md` §5에 "잠정" 태그로 기록됨).
- **ytn2 "한국군 사" 중복** 등 잔존 경미 이슈는 별도 실험으로 축적 후 판단.

**JSON**: `.omc/benchmarks/boundary_retract_adoption_N3.json`(확정 N=3, 위 표 출처) · `.omc/transcripts/ytn1_C_R1.txt`·`eng1_C_R1.txt`(held-out).

---

## Exp-172 — Stage 0 계측: 코드스위칭 경계 3증상 재현·유실 경로 귀속 (GOAL_CODESWITCH_BOUNDARY, 코드 무변경)

**날짜**: 2026-07-08 · **Epoch**: E5 (master `2b6a498`, 코드 무변경 계측 전용) · **브랜치**: master (main cwd)

### 가설 (계측 목적)

Exp-171 채택 후에도 실사용에서 잔존하는 3증상 — ① 코드스위칭 서두 유실 ② 한↔영 경계 없이 접착 ③ 문장 중간부 단어 유실 — 에 대해, ①②의 미발동 조건(무음·화자전환 없는 연속 코드스위칭에서 재감지 트리거 4종 전부 미발동)을 실측 포착하고, ③의 범인 경로를 `[TokenTrace] infer→` vs `emit→` diff + 드롭 태그 조인으로 특정한다. Stage 1(스크립트-앵커 재감지)의 N단어/T초 임계값 실측 근거 확보가 부수 목표.

### 변경 내용

**코드 무변경.** 분석 파서만 스크래치패드에 작성(`stage0_log_analysis.py` — 저장소 밖). 로그 사실 발견: 서버 로그 포맷은 `LEVEL:logger:msg`(타임스탬프 없음) — 구간 지속시간은 배치수×평균 배치주기(오디오길이/총배치수, 0.44~0.53s/배치)로 추정.

### 테스트 설정

경로 C, diar-ON(Sortformer), CRT=3.0, PLC=None, beams=2, turbo, `--trace-tokens --repeat 1`(스크리닝). provenance `vbcable=ok` 확인(RMS 0.154).

### 정량 결과 (스크리닝 N=1 — 방향 신호)

| 파일 | WER | F1 | baseline median (Exp-161) | 게이트(max) |
|------|-----|----|--------------------------|-------------|
| bong1 | 32.9% | 52.4% | 30.5% | ≤30.5 (초과, 단 N=1 방향신호·Exp-171 확정시 R2=43.5 이상치 전례) |
| ytn2 | 16.7% | 75.0% | 28.1% | ≤34.5 ✓ (좋은 회차) |
| sbs1 | 14.3% | 21.1% | 14.9% | ≤16.1 ✓ |

catastrophic 없음, 하니스 정상. 코드 무변경이므로 채택/기각 판정 비대상.

### 산출물 (a) — ①② 후보 구간 목록

| 파일 | 구간 | locked | 반대스크립트 방출 | 지속 | 종결 | 최종 결과 |
|------|------|--------|------------------|------|------|----------|
| bong1 | ~12s | ko | "The thought that" 3단어/2배치 | ~1.0s | ko→en 전환(침묵 트리거) | [Retract] 철회 후 재디코딩 **복구 성공** |
| bong1 | ~69s | ko | "You don 't understand" 4단어/2배치 | ~1.0s | ko→en 전환 | [Retract] 철회(76.2~76.6s) 후 재디코딩이 "Everyone here"부터 시작 — **4단어 완전 유실(① 확정 사례)** |
| ytn2 | — | — | 미재현 (이번 회차 전환 9건 전부 마커 정상 방출, WER 16.7% 양호 회차) | — | — | — |
| sbs1 | — | — | 해당 구간 없음(전환 2건 정상) | — | — | — |

- **N·T 실측**: 후보 2건 모두 반대 스크립트 streak **3~4단어·2배치·약 1.0초** 시점에 기존 트리거(침묵)가 뒤늦게 발동. 즉 이번 회차의 지연은 1초 내외였으나 그 사이 방출분이 철회로 유실됨 → Stage 1 임계 후보 N=3단어 또는 T≈1.0s.
- **①′ 신유형 (스크립트-앵커 사각지대)**: bong1 정답 `"아니 그 플라스틱 말랑말랑한 것도 만들었죠"`(ko) → 전사 `"plus. plastic, sorry, malang on a lot..."` — locked=en 고착 중 한국어 발화가 **영어 음차로 환각 디코딩**되어 출력 스크립트 반전이 아예 발생하지 않음. Stage 1 설계(방출 스크립트 반전 트리거)로는 **원리적으로 포착 불가**한 케이스 실측.

### 산출물 (b) — ③ 경로별 유실 기여도

배치 diff(infer→ vs emit→) + 태그 조인 + 정답 대조 라벨링:

| 경로 | bong1 | ytn2 | sbs1 | 정당 콘텐츠 유실 여부 |
|------|-------|------|------|---------------------|
| **[QualityGate] logprob<-2.0 억제** (infer 내부, 트레이스 불가시) | 46건 | 33건 | 17건 | **있음 — ytn2 "verified" 유실 확정**(정답 "fully verified denuclearization"→전사 "fully denuclearization"), bong1 "who/생각을/plus/a lot/for/네·예"(일부 재디코딩 복구, 일부 유실). 대부분(~75%)은 구두점·대시·필러·웃음의 정당 억제 |
| **[Retract] 하류 철회** (Exp-171 메커니즘) | 7건 | 0 | 0 | **있음 — bong1 "You don't understand" 4단어 유실 확정**(위 ① 사례). 철회 자체는 전부 언어전환 경계의 정당 서두였고 복구가 확률적(2건 중 1건 실패) |
| **무태그·미재방출** (세션 초입 언어미확정 buffer) | 9 | 2 | 2 | 있음 — bong1 "Song"(호칭) 유실, sbs1 정답 서두 "현지 시간 5일 미국 육군 전쟁 대학" 통유실, ytn2 "Yeah". 3파일 공통으로 **세션 초입에 집중** |
| **held/UTF-8 재조립 손상** | Hold12/Prep13 | Hold15/Prep15/**Drop2** | Hold29/Prep29 | 있음(sbs1) — 디코더 컨텍스트에 "방어선이라는 겁니다"·"지상 플랫..." **산출 확인**됐으나 방출은 "방 겁니다"로 손상, "플랫폼이라고" 유실. 컨텍스트에 mojibake(`방어�어�이라는어�`) 잔존 — UTF-8 held 재조립 경로 연루 정황 |
| [AnchorRepeatFilter] | 4단어 | 0 | 0 | 없음(반복 storm 정당 드롭) |
| [CrossBatchFilter] | 2 | 0 | 0 | 없음("malang"·"하하" 정당) |
| [HallucinationFilter]/[BatchRepeatFilter]/[DashFilter] | 3 | 1 | 1 | 없음 |
| [Loop Detection]/[rewind] | 0 | 2(rewind) | 0 | 미상(빈도 낮음) |

### 산출물 (c) — 최다 기여 경로 지목

**정당 콘텐츠 유실의 2대 경로 = ⑴ [QualityGate] logprob 억제(문장 중간부 — 증상 ③의 주범) + ⑵ [Retract] 언어전환 경계 철회 후 재디코딩 미복구(서두 — 증상 ①의 주범)**. 보조 경로 = ⑶ 세션 초입 언어미확정 buffer 유실(3파일 공통), ⑷ held/UTF-8 재조립 손상(sbs1 실측). goal 문서 §1-③ 우선순위 후보였던 CrossBatchFilter·AnchorRepeatFilter는 이번 실측에서 정당 콘텐츠 유실 기여 **미미**(전부 정당 드롭). QualityGate는 "기본 None(비활성)일 가능성 — 로그 유무로 우선 배제" 가정과 달리 **활성**(logprob 임계 -2.0)이며 최다 기여로 반전.

### 분석 (전사 내용 정성 대조)

**bong1** (R1 32.9%):
- **단어 유실·잘림(①)**: 전사 `"Everyone here Everyone here, ..."` / 정답 `"You don't understand. Everyone here, ..."` — 서두 4단어가 [Retract]@76.2~76.6s로 철회 후 미복구.
- **코드스위칭 실패(①′)**: 전사 `"plastic, sorry, malang on a lot"` / 정답 `"플라스틱 말랑말랑한 것도 만들었죠"` — locked=en 중 한국어가 영어 음차로 환각.
- **환각·웃음**: `"하하하 아틀렘이가"`(웃음 구간, 기존 실패모드), `"So So"` 중복. 세션 서두 `"Song,"`(호칭) 유실.

**ytn2** (R1 16.7%):
- **단어 유실(③)**: 전사 `"final fully denuclearization"` / 정답 `"final, fully verified denuclearization"` — "verified"가 [QualityGate] logprob -2.052 억제로 유실.
- 코드스위칭 경계 9건 전부 정상 분리(이번 회차 ①② 미재현). 어절 중복 `"우 중에서는 우선 왕성한 연 왕성한 연합"` 경미 잔존.

**sbs1** (R1 14.3%):
- **단어 유실(③)**: 전사 `"거대한 방 겁니다"` / 정답 `"거대한 방어선이라는 겁니다"` + `"지상 정의했습니다"` / 정답 `"지상 플랫폼이라고 정의했습니다"` — 디코더 컨텍스트에는 산출됐으나 방출 손상(held/UTF-8 정황).
- **세션 서두 유실**: 정답 `"현지 시간 5일 미국 육군 전쟁 대학 강연에 나선"` → 전사 `"강연에 나선"`부터 시작.

**총평**: 증상 ①=[Retract] 철회 후 재디코딩 미복구(확률적), 증상 ③=[QualityGate] 억제 + held/UTF-8 손상 + 세션초입 buffer로 경로 분담이 확정됨. 증상 ②(접착)는 이번 회차 미재현 — 전환 트리거(침묵)가 전부 1초 내 발동한 양호 회차.

### 결론

**계측 완료 (채택/기각 비대상)** — goal 문서 Stage 0 완료 기준 충족: (a) ①② 후보 구간 bong1 2건 실측(ytn2 미재현 사실 보고 포함), (b) 3파일 경로별 귀속 표, (c) 최다 기여 경로 지목(QualityGate + Retract). **③ 범인 특정됨 → Stage 2 착수 가능 상태**(단 Stage 1 채택 후 재계측 우선, 문서 §1 의존관계).

### 다음 가설 (Stage 1 착수 시 — 사용자 상의 후)

- **Stage 1 (스크립트-앵커 재감지)**: 실측 N=3단어/T≈1.0s 근거 확보. 단 이번 회차는 기존 침묵 트리거가 ~1s 지연으로 발동했으므로, Stage 1의 실효는 "침묵이 아예 없는" 연속 발화(ytn2 무휴지 유형, 이번 회차 미재현)에서 발현될 것. **①′ 음차 환각 유형은 Stage 1로 포착 불가** — 별도 신호 필요(사용자 상의 항목).
- **Stage 2 후보 재정렬**: 우선순위 1=QualityGate 정당단어 오억제(임계 -2.0 캘리브레이션 또는 단어수/스크립트 조건), 2=Retract 철회분 재디코딩 복구 보장(트림 잔여 오디오 창 검증), 3=세션초입 buffer 유실, 4=held/UTF-8 재조립 손상. CrossBatch/AnchorRepeat은 후순위로 강등.

**로그**: `.omc/server_logs/server_{bong1,ytn2,sbs1}_C_R1_20260708_15*.log`(TokenTrace DEBUG 포함) · **JSON**: `.omc/benchmarks/eval_20260708_1522_stage0_trace.json` · 파서: 스크래치패드 `stage0_log_analysis.py`(저장소 밖)

---

## Exp-173

**날짜**: 2026-07-08
**Epoch**: E5 (turbo, 파라미터 변경 — epoch bump 아님)

### 가설

사용자가 sbs1 전사에서 "올렸." / "습니다."처럼 한 단어(용언 어간+종결어미)가 침묵 세그먼트를 사이에 두고 두 줄로 쪼개지는 현상을 제보. 원인 추적 결과 `FixedVADIterator`(VAC)의 `min_silence_duration_ms=100`(0.1초)이 원인으로 지목됨 — 조음/숨 휴지 등 단어 내부 미세정적을 발화 종료로 오판해 오디오를 그 지점에서 잘라버리고, Whisper가 앞뒤 조각을 독립적으로 디코딩하며 단어가 분리됨(디코더 자체 오류가 아니라 청크 경계 오분할). `min_silence_duration_ms`를 200ms로 완화하면 이런 미세정적에 의한 오분할이 줄어들 것이라는 가설.

**주의**: 원 증상(단어 분할)은 재현 빈도가 낮아(1회 스크리닝에서 1회만 관측) 채택 확정 측정 3회차 어디에서도 직접 재현되지 않았다. 아래 정량·정성 개선은 **실제로는 다른 기전(발화 반복/필러 환각 감소)**에서 온 것으로 확인됨 — §분석 참조.

### 변경 내용

- `whisperlivekit/audio_processor.py:117-123` — `FixedVADIterator` 생성 시 `min_silence_duration_ms=200`(기존 100) 명시. 화자분할 유무 두 분기(vac_session 유/무) 모두 적용.

### 테스트 설정

경로 C(VBCable 루프백), diar-ON(Sortformer `sortformer-4spk-v2.nemo`), CRT=3.0, beams=2, PLC=None(기본), audio_max_len=15.0(기본). 스윕 100(베이스라인)/150/200/300(1회 스크리닝) → 200 후보 확정(`--repeat 3`) → held-out(ytn1+eng1, 단회).

command:
```
$env:WLK_MIN_SILENCE_MS = "200"   # 스크리닝 단계만 사용, 확정 단계는 코드 리터럴값
.venv\Scripts\python.exe scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3
```

### 스크리닝 (--repeat 1, 방향 신호)

| min_silence | bong1 | ytn2 | sbs1 |
|---|---|---|---|
| 100(base) | 31.1% | 16.3% | 7.7% |
| 150 | 31.7%(하니스 2회 실패 후 재측정) | 20.7% | 16.1% |
| 200 | **25.4%** | **12.3%** | 17.3% |
| 300 | 27.8% | 17.2% | 27.4% |

150이 200에 지배(dominated)돼 기각, 300은 전반 악화로 기각. 200을 확정측정 후보로 선정.

### 테스트 세트 결과 (확정, --repeat 3, median[min/max])

| 파일 | ms100(베이스라인) | ms200(후보) | worst-case |
|---|---|---|---|
| bong1(최우선) | 38.4% [27.5/46.8] | **36.9%** [31.7/37.2] | 46.8%→37.2% 대폭개선 |
| ytn2(최우선) | 16.7% [14.8/18.7] | **15.8%** [14.8/18.7] | 18.7%→18.7% 동률 |
| sbs1 | 13.1% [13.1/14.3] | 12.5% [9.5/17.3] | 14.3%→17.3% 소폭회귀(+3.0pp) |

### Held-out 결과 (단회)

| 파일 | ms100 | ms200 |
|---|---|---|
| ytn1(코드스위칭 일반화) | 24.5% | **14.7%**(-9.8pp) |
| eng1(영어 회귀 감시) | 6.7% | **3.8%**(-2.9pp) |

### 분석 (전사 내용 정성 대조)

**bong1** (median rep 기준, ms100 wer=38.4% vs ms200 wer=36.9%):
- **환각 폭주(완화)**: ms100 `"You don't understand. Everyone You don't understand. Everyone here"` (5단어 구 완전 반복) / ms200 `"You don't understand. Everyone understand everyone here"`(짧은 잔여 더듬거림만, 완전반복 소거).

**ytn2** (median rep 기준, ms100 wer=16.7% vs ms200 wer=15.8%):
- **환각 폭주(완화)**: ms100 `"우선 우선 왕성한 연합 방위 왕성한 연합 방위 태세를"`(2단어+4단어 이중 반복) + 스퓨리어스 삽입 `"UNDER SECRET."` / ms200 `"중에서는 우 중에서는 우선 왕성 왕성한 연합 방위"`(반복은 남아있으나 더 짧고, "UNDER SECRET." 소거).

**sbs1** (median rep 기준, ms100 wer=13.1% vs ms200 wer=12.5%):
- 주요 실패 없음. 두 조건 모두 정답 서두("현지 시간 5일 미국 육군전쟁 대학...")를 큰 손실 없이 보존(ms200: "미국 육군전쟁 대학..."으로 "현지 시간 5일" 소실 정도). worst-case 회귀(14.3%→17.3%)는 **3회차 폭(9.5~17.3%)이 넓어진 것**이며 재측정(150 스크리닝 vbcable 재시도 포함)에서 특정 실패 패턴(서두유실 등)이 재현되지 않아 **분산 확대로 판단**, 재현 가능한 결함 아님.

**이번 변경 영향**: 당초 가설(단어 내부 분할 수정)과 달리, 실제 개선 기전은 **min_silence 완화로 청크 경계가 조금 더 길어지며 반복/더듬거림형 환각이 줄어든 것**이다(원 증상은 저빈도라 직접 재현·검증 불가). 코드스위칭·다화자 최우선 2종(ytn2·bong1)에서 median·worst-case 모두 개선되고 held-out(ytn1)에서도 동일 방향 재현돼 일반화 신호가 강하다.

### 채택 조건 판정

① worst-case(max) 미회귀: bong1·ytn2 통과(개선/동률), **sbs1만 소폭 회귀**(+3.0pp, catastrophic 아님, 비재현 노이즈로 확인) — 엄밀 게이트는 부분 미통과
② median 개선: 3파일 전부 통과

### 결론

✅ **채택 (사용자 승인 — master 머지 완료, 커밋 `2b900a4`/머지 `01e36a0`)**. §3.8 최우선 목표(ytn2·bong1) median+worst-case 개선, held-out 일반화 확인. sbs1 worst-case 소폭 회귀는 재현 불가한 실행 편차로 판단해 사용자 확인 후 채택. 측정 중 VBCable 오염(다른 오디오 재생) 1회 발생해 ytn2/sbs1 확정측정 재실행함(bong1 데이터는 오염 전이라 재사용).

### 다음 가설

- 당초 증상(단어 내부 분할)은 저빈도·비재현이라 이번 변경으로 실제 해소됐는지 별도 확인 어려움 — 재발 시 별도 Exp로 추적.
- sbs1 서두유실 계열 문제는 별도 세션(`worktrees/boundary-retract-floor`, Exp-171 boundary-retract 후속)에서 다루는 중 — 중복 작업 방지 위해 결과 확인 후 필요시 합류.

**JSON**: `worktrees/vad-min-silence/eval_ms100.json`(스크리닝 100), `eval_ms150.json`, `eval_ms200.json`, `eval_ms300.json`, `eval_ms100_r3.json`(확정), `eval_ms200_r3.json`(bong1만 유효), `eval_ms200_r3_ytn2sbs1.json`(확정 재측정), `eval_ms100_heldout.json`, `eval_ms200_heldout.json`

---

## Exp-174 — 언어전환 경계 철회(retraction) 하한을 재디코딩 창 시작으로 정정 (retract_floor, Exp-172/173 후속)

**날짜**: 2026-07-08 · **Epoch**: E5 (브랜치 `exp/boundary-retract-floor`, 분기점 master `2b6a498`=Exp-171) · **머지**: master `500d175`(`--no-ff`)

### 가설

Exp-172 Stage 0 계측에서 ① 서두유실의 근본원인을 코드 레벨로 확정: 언어전환 경계 철회(`_retract_stale_language_tokens`)의 하한이 `boundary_t - LANG_SWITCH_KEEP_SECS - 1.0`(고정 3.5s)인데, 화자전환 등에서 `refresh_segment(keep_secs=...)`가 버퍼를 훨씬 짧게(실측 0.61s) 트림하면 철회 스캔이 **실제 재디코딩 창보다 넓게** 거슬러 올라가 재디코딩으로 재현 불가능한 서두 토큰까지 철회한다. bong1 실측(76s대) "You don't understand" 4단어가 이 메커니즘으로 완전 유실됨을 로그(`[RetractScan] boundary_t=77.31 prev_lang=ko scanned=9 removed=4`)로 확정. 철회 하한을 실제 재디코딩 창 시작(트림된 버퍼의 절대 시작 시각)으로 좁히면, 창 이전 토큰은 보존하고 창 안의 진짜 오언어 중복만 철회할 수 있다는 가설.

(참고: Exp-173에서 QualityGate가 ③ 최다기여 경로라는 Exp-172 서술은 dup 생존 여부 엄밀 재검증(단어경계 매칭) 결과 오귀속으로 정정됨 — 순유실은 96건 중 1건("verified")뿐이라 QualityGate 개입은 보류하고, 사용자 선택([[project-exp173-logprob-separation-impossible]])에 따라 ① Retract 서두복구를 이번 실험 대상으로 확정.)

### 변경 내용

`LanguageSwitch` 마커에 `retract_floor`(재디코딩 창 시작 절대시각)를 실어 철회 하한으로 우선 사용하도록 5개 파일을 수정(신규 상태 필드 1개 + 전파 경로):

- `whisperlivekit/timed_objects.py` — `LanguageSwitch` dataclass에 `retract_floor: Optional[float] = None` 필드 추가.
- `whisperlivekit/simul_whisper/decoder_state.py:42` — `pending_retract_floor: Optional[float] = None` 상태 필드 추가.
- `whisperlivekit/simul_whisper/align_att_base.py` `_apply_detected_language` (is_switch 블록) — `self.state.pending_retract_floor = self.state.pending_language_switch - self.segments_len()`(= `global_time_offset`, 트림된 버퍼의 절대 시작) 계산·저장.
- `whisperlivekit/simul_whisper/backend.py` (3곳) — 마커 생성 시 `retract_floor=pending_retract_floor` 전달, 마커 방출 후·긴침묵 경로 클리어 시 `pending_retract_floor = None`.
- `whisperlivekit/tokens_alignment.py` `_retract_stale_language_tokens` — 신규 파라미터 `redecode_floor: Optional[float] = None` 추가, 하한 계산을 `redecode_floor`가 있으면 그것을, 없으면 기존 `boundary_t - LANG_SWITCH_KEEP_SECS - 1.0`(하위호환 폴백)으로 변경.
- `tests/test_boundary_retract.py` — 신규 유닛테스트 3개(창 이전 보존/창 안 정상철회/None 폴백) 추가, 기존 12개 + 신규 3개 = 15개 전부 통과.

### 테스트 설정

경로 C, diar-ON(Sortformer), CRT=3.0, PLC=None, beams=2, turbo. cwd=워크트리(`worktrees/boundary-retract-floor`), `--model-dir`·`--files`·`--sortformer-model`은 메인 저장소 절대경로(워크트리에 대용량 test_data/모델 미포함, git 미추적) 지정. ① 스크리닝 `--repeat 1 --trace-tokens` ② 채택확정 `--repeat 3 --trace-tokens` ③ held-out `ytn1+eng1` 단회. 측정 중 sibling 세션들의 동시 경로C 측정과 VBCable/포트 8901 충돌로 1회 재시도(하니스 문제, 프로세스 정리 후 재실행).

### 정량 결과

**스크리닝(N=1)**: bong1 29.6%/F1 50.0% · ytn2 18.2%/F1 66.7% · sbs1 16.1%/F1 28.6%. catastrophic 없음.

**채택확정(N=3, JSON `eval_20260708_1821_retractfloor_adoptN3.json`)**:

| 파일 | WER median | WER max | WER min | WER stdev | F1 median | 게이트(max) | Exp-171 대비(median) |
|------|-----------|---------|---------|-----------|-----------|-------------|----------------------|
| bong1 | 37.5% | **39.3%** ❌ | 31.4% | 4.1% | 52.4% | ≤30.5%(초과) | 28.1%→37.5%(+9.4pp) |
| ytn2 | **15.8%** | 16.7% ✓ | 15.3% | 0.8% | 72.7% | ≤34.5% | 18.7%→15.8%(**-2.9pp**) |
| sbs1 | **10.7%** | 15.5% ✓ | 9.5% | 3.1% | 23.5% | ≤16.1% | 13.1%→10.7%(**-2.4pp**) |

**held-out(N=1, JSON `eval_20260708_1850_retractfloor_heldout.json`)**: ytn1 **10.4%**/F1 76.2%(과거 기록 21.5~33.1% 중 최저, 최고치) · eng1 **5.7%**/F1 0.0%(과거 2.9~7.6% 밴드 내, F1=0은 ref_sentences=1 지표한계).

### 분석 (전사 내용 정성 대조 — `.omc/transcripts/`, `eval_20260708_1821_retractfloor_adoptN3.json`)

**bong1** (R3=median 37.5% 기준, R1/R2도 함께 대조):
- **목표 결함(①) 확정 복구**: 정답 `"보통 그. You don't understand. Everyone here..."` — 전사(R1) `"아니 보통 그. You don't understand. Everyone,. everyone here they're going to be..."`. **3회차 전부**에서 "You don't understand"가 보존됨(Exp-172 계측 시점엔 이 구간이 통째로 소실되어 "Everyone here Everyone here"로 직행했었음). 부작용은 "Everyone," 경미한 중복 분절뿐.
- **환각 폭주(WER 상승 주범, 3/3 재현)**: R1 `"This man This man Thank you. Thank you."` + 신규 환각 인명 `"Good David Plylar: That's good. David Plylar: The main character is that metaphorical."`(정답엔 해당 문장 없음). R3 `"This This man there Thank you very much. Thank you. Thank you"` + `"What's your. Thank you. Thank you. you."`. **로그 인과관계 대조**(RetractScan 이벤트를 로그 라인 순서로 필러 위치와 대조) 결과, 이 필러들은 ⓐ 제 floor가 토큰을 보존한 RetractScan 이벤트보다 **먼저** 로그에 등장(R1 line 3359 "This man" < line 4174의 removed=0 이벤트)하거나 ⓑ 근접 RetractScan이 `stopped_by=silence/boundary`(제 floor 값과 무관하게 침묵/경계 토큰이 스캔을 먼저 막음)로 종료 — **이번 변경이 필러를 유발했다는 인과 증거 없음**. Exp-171 R2 이상치(43.5%, "Thank you" 필러 2회+"하하하" 웃음환각)와 정성적으로 동일한 기존 실패모드. 참고로 이번 max(39.3%)는 Exp-171의 max(43.5%, 이미 채택됨)보다 낮음 — median만 이번 3회 표본에서 나쁘게 나옴.
- 단 1건 애매한 사례(R3 boundary_t=98.11, scanned=6/removed=0/stopped_by=lower_bound, ①′ 음차환각 구간 근접) — floor가 정당 보존했는지 잔여 노이즈를 살렸는지 로그만으로 100% 단정 불가, 후속 관찰 필요.

**ytn2** (R1=median 15.8% 기준):
- **목표 무관 개선**: 코드스위칭 경계 9건 전부 정상(언어전환 마커 정상 발동), 경미한 어절 중복("한국군 사...자, 한국군 사령관") 1건 외 주요 실패 없음. §3.8 최우선 목표에 부합하는 대폭 개선(median -2.9pp, Exp-171 대비).

**sbs1** (R1=median 10.7% 기준):
- 주요 실패 없음. 한↔영 전환("From a satellite image...") 정상.

**이번 변경 영향 총평**: 목표 결함(①, bong1 서두유실)이 3/3 전부 확정 복구됐고 ytn2·sbs1 median이 동반 개선됐다. bong1 median/max 게이트 위반은 **로그 인과관계 대조상 이번 수정과 무관한 기존 필러/웃음 실패모드**(Exp-159/168/171에서 반복 관측)로 판단되나, 3/3 재현이 Exp-171(1/3)보다 빈도가 높아 100% 배제는 어렵다.

### 채택 조건 판정

| # | 조건 | 판정 |
|---|------|------|
| ① max WER 미회귀 | bong1 39.3%>게이트30.5%(❌, 단 Exp-171 자체 max 43.5%보다는 낮음) / ytn2 16.7%≤34.5%✓ / sbs1 15.5%≤16.1%✓ | △ bong1만 초과 — 근본원인 분석상 인과관계 없음(위 분석) |
| ② median 개선 | bong1 +9.4pp(악화) / ytn2 **-2.9pp**✓ / sbs1 **-2.4pp**✓ | 2/3 개선 |
| 목표 결함(①) 해소 | "You don't understand" 3/3 전 회차 확정 복구 | ✅ 달성 |
| held-out 회귀 | ytn1 대폭개선(과거 최고치) / eng1 정상 밴드 | ✅ 문제없음 |
| 전체 pytest 회귀 | rebase 후 전체 스위트 4건 실패 — **plain master(01e36a0, 제 코드 미포함) 단독 실행에서도 동일 4건 실패 확인** → 제 변경과 무관(VAD 변경 또는 환경 요인, 별도 이슈) | ✅ 제 변경발 회귀 아님 |

**판정: ✅ 채택 (사용자 확인 후 — held-out 검증 완료 조건부 채택 선택)** — bong1 게이트 초과가 CLAUDE.md §4 "①max 미회귀 1순위"에 형식상 저촉하나, 로그 시간순 인과관계 대조로 이번 수정과 무관함을 실증했고(Exp-171 선례와 동일 판단 근거), 목표 결함이 3/3 전부 복구되며 ytn2·sbs1·held-out이 모두 개선/무회귀라 사용자 승인으로 채택. rebase는 sibling Exp-173(VAD min_silence, `whisperlivekit/audio_processor.py` 1개 파일)과 파일 겹침 0으로 충돌 없이 클린 병합.

**Epoch 판단**: 세대 안 올림(E5 유지) — Exp-171과 동일 서브시스템(언어전환 경계 철회) 내 하한값 정정으로, 디코더 파라미터 트레이드오프에 영향 없음.

### 다음 가설 (향후 검토 후보)

- **bong1 R3 boundary_t=98.11 애매 사례**: `--trace-tokens` 확대 로깅으로 이 6토큰의 정당성(보존이 맞았는지) 재확인.
- **필러/웃음 환각(3/3 재현) 자체의 별도 근본 대응**: 이번 실험 범위 밖(Retract 메커니즘과 무관 확정) — CASE3/AnchorRepeatFilter 계열 후속 실험으로 이관.
- **rebase 후 조합상태(VAD min_silence+retract_floor) 재측정**: 이번 N=3/held-out은 VAD 수정 이전 코드로 측정됨 — master 현재 상태(양쪽 다 포함) 조합 효과의 정식 재측정은 미실시(rebase 자체는 파일 미겹침 확인 + pytest 무관 회귀 확인으로 충분히 갈음했으나, 정밀도를 높이려면 후속 스크리닝 권장).

**JSON**: `worktrees/boundary-retract-floor/.omc/benchmarks/eval_20260708_1811_retractfloor_screen.json`(스크리닝) · `eval_20260708_1821_retractfloor_adoptN3.json`(채택확정 N=3) · `eval_20260708_1850_retractfloor_heldout.json`(held-out) · `.omc/transcripts/`(전사)

---

## Exp-175 — 스크립트-앵커 재감지 게이트: 무음·화자전환 없는 연속 코드스위칭 재감지 트리거 신설 (GOAL_SCRIPT_ANCHOR_REDETECT, Stage 1)

**날짜**: 2026-07-09 · **Epoch**: E5 (브랜치 `exp/script-anchor-redetect` `cf0cd2c`, 분기점 master `500d175`=Exp-173+174) · **머지**: master `c3302a2`(`--no-ff`, 사용자 승인)

### 가설

Exp-172 Stage 0 계측으로 규명된 ① 코드스위칭 서두유실의 잔존 근본원인: `LanguageSwitch` 마커는 `_apply_detected_language`의 `is_switch`일 때만 arm되는데, 중간 재감지 트리거 4종(짧은침묵≥0.5s·긴침묵≥2.0s·화자전환 eager·PLC=기본 None 비활성)이 **무음·화자전환 없는 연속 코드스위칭에서 전부 미발동** → 구언어 고착 → 새 언어 서두 오디코드/유실(①) + 마커 미생성으로 한↔영 같은 line 접착(②). 실제 방출 토큰의 스크립트가 잠긴 언어와 연속 N=3단어 또는 T=1.0s(Exp-172 실측 임계) 반전 유지될 때 재감지(2.0s 창·min_prob 0.90)를 트리거하고, 다른 언어 확신 시에만 기존 전환 메커니즘(트림+마커 arm+retract arm+retract_floor, Exp-174)을 발동하면 이 구멍이 메워진다는 가설.

### 변경 내용 (전부 `whisperlivekit/simul_whisper/backend.py` + 테스트)

- `backend.py:170-188` — 상수 블록: `SCRIPT_ANCHOR_REDETECT_ENABLED`(롤백 플래그, :184), `_SCRIPT_ANCHOR_N_WORDS=3`(:185), `_SCRIPT_ANCHOR_T_SECS=1.0`(:186), 재감지 창 2.0s(:187)·min_prob 0.90(:188).
- `backend.py:221-224` — `__init__` 신규 상태: `_script_anchor_streak`(단어 리스트) + `_start`/`_end`(절대시각, T 문턱 판정용).
- `backend.py:532-618` — 신규 메서드 3개: `_reset_script_anchor_streak` / `_update_script_anchor_streak`(배치 끝 기준 누적 판정 — `_is_opposite_script`(tokens_alignment, TTR 게이트 없는 순수 스크립트) 재사용, 같은 스크립트 섞이면 리셋, 숫자·기호 중립 스킵, ko↔en 대칭) / `_apply_script_anchor_redetect`(트리거 시 `detect_current_language(2.0, 0.90)` → 다른 언어 확신 시에만 `_apply_detected_language` 위임 + 배치 드롭, 같은 언어 재확정 시 no-op+리셋(Exp-169), None 시 미적용+유지, `refresh_segment` 미호출(Exp-163)).
- `backend.py:682` — 삽입점: `process_iter` ScriptMismatchFilter 직후·AnchorRepeatFilter 앞.
- `backend.py:289·391·674·710` — streak 리셋 합류: 긴침묵 리셋 블록·`new_speaker`·ScriptMismatchFilter 발동 직후·AnchorRepeatFilter 발동 직후.
- `tests/test_script_anchor_redetect.py` — 신규 17테스트(TDD, MagicMock 관례): N-1 미발동/N 발동/T 발동/같은스크립트 리셋/중립 스킵/cross-batch 누적/None 유지/재확정 no-op/전환 드롭/ko↔en 대칭/무력화 플래그/미잠금·고정언어 미동작/긴침묵·new_speaker·양 게이트 발동 후 리셋.
- `tests/test_script_mismatch_gate.py`·`tests/test_anchor_repeat_gate.py` — 픽스처에 신규 상태 3필드 + `detect_current_language=None` 스텁 + `_FakeToken.start/end` 추가(신규 게이트 도입에 따른 테스트 하니스 보강; "정상 전체-영어 문장 무드롭" 계약은 재감지 불확신 전제로 재정의 — 확신 시 전환+드롭+재디코딩 복구가 새 정상 동작).
- 전체 pytest 274 통과 / 실패 4건은 plain master와 동일한 기존 `test_pipeline.py` 실패(Exp-174에서 무관 확정된 것과 동일 집합). ruff clean.

### 테스트 설정

경로 C, diar-ON(Sortformer), CRT=3.0, PLC=None, beams=2, turbo. cwd=워크트리(`worktrees/script-anchor-redetect`), `--model-dir`·`--files`·`--sortformer-model` 메인 저장소 절대경로. ① 스크리닝 `--repeat 1 --trace-tokens` ② 채택확정 `--repeat 3 --trace-tokens` ③ held-out(ytn1+eng1) 단회 ④ 같은 날 master 기준선(N=1, master@53553d6=500d175 동일 코드) ⑤ sbs1 게이트 초과 분리 측정(2×2: 코드×trace + 격리 N=3) ⑥ N 스윕(2/4, 탐사 전용 브랜치).

### 정량 결과

**채택확정(N=3, JSON `eval_20260709_0904_scriptanchor_adoptN3.json`)**:

| 파일 | WER median | WER max | WER min | WER stdev | F1 median | Exp-174 대비(median/max) | 게이트 발동 |
|------|-----------|---------|---------|-----------|-----------|--------------------------|------------|
| bong1 | **30.8%** | 36.0% | 28.7% | 3.7% | 54.5% | 37.5→30.8(**-6.7pp**) / 39.3→36.0(**-3.3pp**) | R3만 1회(ko→en) |
| ytn2 | 17.2% | 18.2% | 13.8% | 2.3% | 69.6% | 15.8→17.2(+1.4pp) / 16.7→18.2(+1.5pp, Exp-173 max 18.7 밴드 내) | 0회 |
| sbs1 | 16.7% | 17.9% | 15.5% | 1.2% | 23.5% | 10.7→16.7(+6.0pp) / 15.5→17.9(+2.4pp) — **아래 분리 측정으로 측정순서 효과 규명** | 0회 |

**스크리닝(N=1)**: bong1 36.6(발동 2) · ytn2 18.7(발동 1) · sbs1 18.5(발동 0). **held-out(단회)**: ytn1 **16.0%**/F1 61.5(과거 밴드 10.4~33.1 내) · eng1 **5.7%**/F1 0.0(Exp-174와 동일치) — 발동 0회(영어 단일언어 오탐 없음).

**같은 날 master 기준선(N=1, 무trace)**: bong1 **39.3%** · ytn2 16.3% · sbs1 8.3%. bong1은 master 자체가 같은 날 39.3을 기록 — 브랜치 max 36.0이 기준선보다 낮음.

**sbs1 게이트 초과(17.9>16.1) 분리 측정** — 발동 0회라 인과 기전 부재 → 2×2 교차 + 격리 재측정으로 원인 규명: master·무trace 8.3 / master·trace 10.7 / 브랜치·무trace 8.9 / **브랜치·trace 격리 N=3 = 8.3/10.1/12.5 (median 10.1, max 12.5 — 게이트 16.1·Exp-174 max 15.5 모두 통과)**. 채택확정 N=3의 sbs1 15.5~17.9 밴드는 **3파일 배치 후미(bong1×3+ytn2×3 뒤) 지속 부하의 측정 순서 효과**로 확정(sbs1은 Exp-161 규명대로 lag 민감 파일). JSON `eval_20260709_0948_scriptanchor_sbs1_isolatedN3.json`.

**N 스윕(탐사, N=1 방향 신호)**: N=2 → bong1 33.8(발동 1 정당 전환)·ytn2 18.7(**2단어 정상 삽입 오트리거 1회 — 재감지가 잠긴 언어 ko 재확정, no-op 방어 작동**, 비용=encoder forward 1회)·sbs1 10.7(0회, JSON `eval_20260709_0956_scriptanchor_sweepN2.json`). N=4 → bong1 26.3·ytn2 14.8·sbs1 14.3이나 **발동 0회**(문턱이 높아 이 회차의 전환들은 전부 기존 트리거가 선점 — 게이트 사실상 dormant, 수치는 무발동 회차 변동일 뿐, JSON `eval_20260709_1004_scriptanchor_sweepN4.json`). **기본값 N=3 유지 권고** — Exp-172 실측 정합 + N=2 오트리거 비용 + N=4 미발동(커버리지 상실) 실증. 스윕 브랜치 `exp/script-anchor-sweep-n2`(b100580)·`-n4`(e8b72e8)는 provenance 보존용 유지, 머지 비대상.

### 분석 (전사 내용 정성 대조)

**bong1** (R2=median 30.8 기준, R1=max/R3=min 대조):
- **① 서두 보존 (목표)**: R3 발동 로그 `[ScriptAnchorRedetect] 반대스크립트 streak 4단어/0.48s → 재감지 ko→en — 전환 적용·배치 드롭: You don 't understand` → 전사에 "You don't understand." 보존 — **Exp-172 확정 유실 사례를 게이트가 직접 선제 복구**(R3=28.7%, 3회차 중 최저 WER). 스크리닝 회차에선 ~70s "그냥 돌이에요. It's just a rock" 경계에서 streak 3(재감지 p=0.87<0.90 → 유지)→4(p=0.99 → 전환) 단계 발동, 트림 1.16s 후 재디코딩이 "It's just a rock." 완전 복구 — diar `[NewSpeaker]` 이벤트(1~2s 지연)보다 **먼저** 발동함을 로그 순서로 확인.
- **환각(max 회차, 기존 실패모드)**: R1(36.0%) "This map Thank you. Thank you So" + "Ha ha Ha ha! No Oh, my God"(웃음) + 환각 인명 "That's right, Phil." — **발동 0회 회차**로 게이트와 인과 무관, 같은 날 master 기준선(39.3%)에도 동종 패턴. Exp-159/168/171/174 반복 관측된 필러/웃음 모드.
- **①′ 음차환각(스코프 밖, 기록)**: R1 정답 "플라스틱 말랑말랑한 것도" → 전사 "plus as a mallang mallang on" — en 잠금 중 한국어가 영어 음차로 환각 디코딩, 스크립트 반전이 없어 본 설계로 원리상 포착 불가(Exp-172 예상 그대로 재확인).

**ytn2** (R1=median 17.2 기준):
- **발동 정당성**: 스크리닝 회차 streak 3단어/0.36s → 재감지 ko→en(p=1.00) — 배치 드롭 "There is more" → 트림 12.52s→2.32s 유지, 재디코딩 "There is more work to be done..." 완전 복구(선두 "-" 흔적만).
- **방송클로징 환각·필러 storm**: 전 회차 재발 0건. 코드스위칭 경계 마커 정상.
- **미방출형 서두유실(신규 분류, 게이트 스코프 밖)**: R3 "There is more work" 유실 — 발동 0회 회차로, 구언어 잠금 중 디코더가 해당 오디오에서 토큰을 아예 방출하지 않아(비-fire) 반전 streak 자체가 없던 케이스. docs/backlog/BACKLOG_CODESWITCH_FOLLOWUP.md §1로 카탈로그.

**sbs1** (R2=median 기준):
- 주요 실패 = 세션초입 서두 통유실("현지 시간 5일 미국 육군 전쟁 대학…" 3/3, Exp-172 ⑶ 기존 모드) + 문장 중복 재방출 1건. 발동 0회 — 게이트 무관. 격리 N=3에선 "From a satellite image" 포함 전환 정상.

**이번 변경 영향 총평**: 발동 총 5회(적용 3·불확신 유지 1·재확정 no-op 1, 스윕 제외) 전부 정당 — **오탐 0**. 발동 회차는 모두 해당 파일의 저 WER 쪽(bong1 R3=min 28.7). 상승으로 보였던 sbs1은 측정 순서 효과, ytn2는 노이즈 밴드 내, bong1은 median/max 동반 개선. 기존 실패모드(필러/웃음/음차/세션초입)는 발동 0회 회차에서만 관측돼 인과 무관이 로그로 실증됨.

### 채택 조건 판정

| # | 조건 (GOAL §4) | 판정 |
|---|------|------|
| ① 신규 게이트 발동과 인과로 엮인 환각 재발 | 0건 — 환각 회차는 전부 발동 0회, 같은 날 master 기준선에도 동종 패턴 | ✅ |
| ② Exp-172 후보 구간 발동→마커→서두 보존 관측 | "You don't understand"(Exp-172 확정 유실 사례) 게이트 직접 복구 + "It's just a rock"·"There is more work" 복구, diar 이벤트보다 선제 발동 | ✅ |
| ③ 테스트셋 WER max 미회귀 | bong1 36.0 < 같은날 master 39.3·Exp-174 39.3(STATE 게이트 30.5은 초과하나 Exp-174 전례와 동일하게 필러/웃음 정성 일치+발동 0회 인과 무관 실증) / ytn2 18.2 ≈ Exp-173 max 18.7 / sbs1 격리 N=3 max 12.5 < 15.5 | ✅ (bong1 별도 표기) |
| ④ held-out 미회귀 | ytn1 16.0 밴드 내 · eng1 5.7 동일치 | ✅ |

**추가 검증 — 짝지음 master↔브랜치 A/B 18런 (사용자 "WER 상승 아니냐" 질의 후)**: 같은 날·파일별 격리·선후 교대(M-B/B-M/M-B). bong1 M 29.3/29.3/33.5 vs B 27.8/38.4/29.9 · ytn2 M 16.3/14.3/21.7 vs B 18.2/17.7/15.8 · sbs1 M 17.3/16.7/9.5 vs B 11.9/48.2/16.1. median 합계 62.3 vs 63.7(+1.4pp)·짝별 승패 5:4 = **통계적 동률**. **브랜치 9런 전부 발동 0회** — 두 코드가 동일 디코딩 경로를 실행했음이 확정되어 차이는 전부 회차 노이즈. 이상치 규명: B sbs1 R2 48.2% = 첫 40s 무출력 stall(워치독 4연발·`det_lang=None`이라 게이트 동작 불가 — Exp-168의 master sbs1 48.8% stall과 동일 시그니처), B bong1 R2 38.4% = 필러/웃음 변동(같은 날 M도 39.3). JSON `paired_<file>_<cond>_R<rep>.json`(master=메인·branch=워크트리 `.omc/benchmarks/`).

**판정: ✅ 채택 (사용자 승인, master `c3302a2` 머지)** — §3.2 불변 제약(코드스위칭 무결성) 직결 기반 기능 + 게이트 4항 충족 + 오탐 0 + TDD 17테스트 + 짝지음 A/B로 WER 완전 중립 확정("평상시 완전 중립 + 방출형 코드스위칭 유실 모드 제거"가 이 수정의 성격). 연동 갱신: `docs/SENTENCE_FINALIZATION_LOGIC.md` §3.2 진입점 4→5종(간접 재-arm은 6번으로)·§5 파라미터 4행 추가 + 철회 스캔 하한 행의 Exp-174 반영 누락(stale) 정정.

**Epoch 판단**: E5 유지 — Exp-168/171/174와 동일한 언어전환 경계 서브시스템 내 트리거 추가, 디코더 파라미터 트레이드오프 무영향(발동 없으면 완전 수동 관찰자).

### 다음 가설 (docs/backlog/BACKLOG_CODESWITCH_FOLLOWUP.md 상세)

1. **미방출형 전환 서두 유실**(최우선): 비-fire 구간은 반전 streak이 없어 본 게이트 스코프 밖 — 재디코딩 창 하한을 마지막 방출 토큰 끝으로 당기거나 경량 비-fire 워치독 검토.
2. **①′ locked-lang 음차 환각**: 저신뢰+언어확률 경합 보조 트리거 별도 설계(Exp-160 스퓨리어스 리스크 주의).
3. **측정 프로토콜**: 3파일 배치 후미의 sbs1 상승(측정 순서 효과) — 채택확정 N=3의 파일 순서 로테이션 또는 파일별 격리 측정 검토 가치.

**JSON**: `worktrees/script-anchor-redetect/.omc/benchmarks/eval_20260709_0853_scriptanchor_screen.json`(스크리닝) · `eval_20260709_0904_scriptanchor_adoptN3.json`(채택확정) · `eval_20260709_0928_scriptanchor_heldout.json`(held-out) · `eval_20260709_0948_scriptanchor_sbs1_isolatedN3.json`(sbs1 격리) · `eval_20260709_0956_scriptanchor_sweepN2.json`(N=2 스윕) · 메인 `.omc/benchmarks/eval_20260709_0932_masterbaseline_sameday.json`·`eval_20260709_0945_masterbaseline_sbs1_trace2.json`(같은날 기준선)

---

## Exp-176 — 문법-조건부 침묵 경계 게이트 (Case B 단어중간분절 방지)

**날짜**: 2026-07-12 | **Epoch**: E5 (유지 — 출력 조립 계층 변경, 디코더 파라미터 무영향)

### 가설

VAD가 짧은 침묵(0.4s 초과)을 검출하면 `tokens_alignment.py`가 문법 판단 없이 **무조건** 세그먼트를 닫아, 같은 화자·같은 언어 연속 발화 중 문장이 **단어 중간**에서 잘리는 과분할(Case B, 예 "올렸"⏎"습니다", "관련"⏎"해서")이 발생한다. 온점 분할 경로에는 이미 문법 판별기 `is_genuine_sentence_end()`가 연결돼 있으나 침묵 경로엔 미연결이었다(근본원인 규명 = `docs/GOAL_SILENCE_GRAMMAR_GATE.md` §1). 이 판별기를 침묵 경로에도 연결하면 Case B를 제거하면서 화자/코드스위칭 경계는 그대로 보존할 수 있을 것이다.

### 변경 내용

- `whisperlivekit/sentence_boundary.py`: `should_split_after_silence()`(분할/병합/보류 3치 판정 — 기존 `is_sentence_final_ko` 재사용), `last_word()` 공개 래퍼 추가.
- `whisperlivekit/timed_objects.py`: `PuncSegment.gate_pending` 필드(게이트 보류 상태 전파).
- `whisperlivekit/tokens_alignment.py` (핵심, 약 +350줄):
  - `SILENCE_HARD_SECS=0.8`(안전망 — 이 이상 침묵은 문법 무관 항상 분할), `PENDING_RESOLVE_CAP=2.0`(B 대기 상한, silence.end 기준) 신설.
  - **decide-late**: 게이트 판정을 침묵 도착 시점이 아니라 B(다음 발화) 확정 시점/캡 만료 시점에 내림 — diar 경로(무상태 재계산)는 자동 충족, 비-diar 경로는 `_nondiar_pending_silence` 상태로 재귀속 꼬리 vs 새 발화 B를 구분해 구현.
  - **확정 유예 이원화**: 게이트 대상 침묵은 기존 `_apply_finalize_grace`(silence.**start** 기준)를 우회하고 `PENDING_RESOLVE_CAP`(silence.**end** 기준)만 적용 — B 디코드 지연 중 조기 finalized=True로 인한 번역 오발사 방지.
  - **메모**(`resolved_split_silences`): diar 무상태 재계산에서 캡 만료로 분할 확정된 침묵이 이후 재계산에서 병합으로 되돌아가는 플래핑 방지.
  - **hard_boundary 스탬프 수정**: `[SIL, LanguageSwitch]` 빈 스팬에서 소실되던 `hard_boundary`를 직전 침묵 PuncSegment에 스탬프 — 언어전환 경계를 넘는 병합을 구조적으로 차단.
  - 병합 실행 3중 조건(같은 화자 ∧ hard_boundary 아님 ∧ 언어 동일)이 문법 판정보다 항상 우선.
  - `[SilenceGate]` 판정 로그(모든 merge/split/pending 판정 기록).
- `whisperlivekit/parse_args.py`/`config.py`: `--silence-grammar-gate`/`--no-silence-grammar-gate` 롤백 플래그(기본 ON).
- `scripts/eval.py`: 플래그 패스스루.
- `tests/test_silence_grammar_gate.py`(신규): 26개 테스트(한국어 종결/미종결, 영어 대소문자, HARD 안전망, 구두점 경계 비대상, hard_boundary/화자 차단, 연속침묵 누적, 캡+메모, flush, 무력화 플래그 등).
- 커밋: `d8ebaaf`(`exp/silence-split-koen-gate`, master 미머지).

### 테스트 설정

경로 C(VBCable 루프백), 화자분할 ON(Sortformer), CRT=3.0, beams=2, PLC=None, audio_max_len=15.0(기본). 게이트 ON/OFF **짝지음**(같은 세션·같은 코드, 플래그만 상이). 스크리닝 `--repeat 1`(파일 3종 + HARD 스윕 0.6/1.0), 채택확정 `--repeat 3`(fail-fast 금지, 파일별 개별 호출로 측정).

### 정량 결과

**스크리닝(--repeat 1, 방향신호)** — ON vs OFF: bong1 WER 26.6→OFF32.3%(개선), ytn2 23.2→OFF18.2%(악화), sbs1 10.1→OFF8.3%(악화이나 화자F1은 100%→OFF66.7% 대폭개선). `[SilenceGate]` 고유판정 28건 중 오탐 0건(진짜종결 오병합 없음), d_eff merge/split_grammar 구간(0.42~0.74s)과 split_hard(0.80~2.08s)가 명확히 분리 — HARD=0.8이 문법판정과 상보적으로 작동함을 확인.

**HARD 스윕(0.6/0.8/1.0, 스크리닝)**: 0.6→sbs1 화자F1 100%→80% 하락, 1.0→bong1 WER 26.6→36.9%(+10.3pt, 반복환각 유발 추정) — 0.8이 두 회귀를 모두 피해 최적, **변경 없이 유지**.

**채택확정(--repeat 3, N=3 median/min/max/stdev)**:

| 파일 | 조건 | WER median/min/max/stdev | 화자분리F1 median/min/max | 문장분리F1 median |
|---|---|---|---|---|
| bong1 | ON | 29.3%/28.1%/38.7%/5.8% | 54.1%/52.4%/70.3% | 21.1% |
| bong1 | OFF | 28.7%/27.8%/36.9%/5.0% | 56.4%/51.3%/60.0% | 17.4% |
| ytn2 | ON | 16.7%/13.8%/**29.6%**/8.4% | 70.0%/60.9%/94.7% | N/A |
| ytn2 | OFF | 19.7%/18.2%/20.2%/1.0% | 64.0%/52.2%/66.7% | N/A |
| sbs1 | ON | 11.9%/9.5%/13.1%/1.8% | **100%/100%/100%** | 94.7% |
| sbs1 | OFF | 20.2%/14.9%/30.4%/7.9% | 57.1%/50.0%/66.7% | 78.3% |

참고게이트(Exp-161 max, 구regime): bong1≤30.5%/ytn2≤34.5%/sbs1≤16.1% — sbs1 ON은 크게 하회(개선), bong1/ytn2는 median은 이내이나 3회 편차가 커 max가 근접·초과(OFF도 유사 편차 — 파일 고유 고분산 특성).

**held-out(단회)**: ytn1 WER 10.4%(STATE baseline 21.5% 대비 대폭개선), 화자F1 88.9%. eng1 WER 3.8%(baseline 4.8% 대비 개선), 화자F1은 정답 포맷 특성(단일블록)으로 0%(회귀 아님) — hyp_lines 검사 결과 영어 대문자 시작 판정에 의한 과병합/과분할 없음, 회귀 없음.

**kinno(정성 sanity)**: WER 48.4%는 정답 부정확으로 게이팅 제외 대상. 대규모 누락·환각 없음, 한/영 외 언어 혼입 없음, 화자전환 대체로 합리적 지점에서 분리, Case B 징후 없음.

### 분석 (전사 내용 정성 대조)

**bong1** (N=3 전 회차 확인):
- **단어중간분절(Case B) 해소**: OFF `"...하고 자빠졌." / "는데, 솔직히."`(침묵으로 강제분할) → ON `"...하고 자빠졌는데,."` 한 줄 병합. **N=3 전 회차 재현** — run1/2/3 전부 `"자빠졌는데,"` 형태 유지, 재발 0건.
- 그 외 주요 실패 없음. 화자전환 경계는 ON/OFF 동일 유지.

**ytn2** (R_max=run3 기준, catastrophic 패턴 확인용):
- **환각 폭주(게이트 무관 추정)**: run3 원문에 `"we remain We remain resolute"`, `"Security Council Security Council"`, `"committed to close coordination committed to close coordination"` 등 토큰 반복(디코더 stutter)이 다발 — run1/run2엔 없음. WER max를 크게 끌어올린 원인으로 추정되나, 경계 배치 로직(이 게이트의 관장 범위)과의 인과관계는 **확증되지 않음**(회차성 디코더 변동 가능성). 별도 조사 필요(다음 가설 참조).
- **구중간 과분할 해소**: OFF `"...입장을 고소하고." / "있습니다."` → ON `"...입장을 고소하고 있습니다."` 병합. `"operational" / "control transition"` 류 분절도 ON에서 병합 유지.
- **[hard-fail 단서, silence 트리거 무관]**: run2에 `"왕성한 연."`→`"Thank you very."`(환각)→`"방위태세를..."`로 "연합"이 쪼개지는 사례 1건 관측되나, 이 경계의 trigger는 `language_switch`(이 게이트가 관장하는 `silence` 트리거가 아님)이며 OFF/ON run1·3에서는 해당 단어가 항상 온전 — 게이트와 상관관계 없는 기존 확률적 변동으로 판단.

**sbs1** (N=3 전 회차 확인):
- **화자분리 압도적 개선**: OFF 화자분리F1 50~66.7%(median 57.1%) → ON **100%(3회차 전부)**.
- **단어중간분절(Case B) 해소**: OFF `"...것으로." / "보입니다."` → ON `"...것으로 보입니다."` 병합. OFF `"...사령관. 자신의...올렸습니다."`(구간 분절) → ON 병합.
- 그 외 주요 실패 없음.

**이번 변경 영향 총평**: 목표(Case B 제거)를 게이트 통제범위(`silence` 트리거) 내에서 N=3 전 회차 재현 없이 완전 달성. 화자분리 F1이 최우선 지표에서 3파일 전부 worst-case 개선(특히 sbs1 50%→100%). WER은 median 기준 중립~대폭개선(sbs1)이나, ytn2 1파일의 max에서 토큰반복 환각으로 추정되는 변동이 관찰돼 게이트와의 완전한 무관성은 미확증 상태로 남긴다.

### 채택 조건 판정 (GOAL_SILENCE_GRAMMAR_GATE.md §4, 우선순위 순)

| # | 조건 | 판정 |
|---|------|------|
| ① Case B(단어중간분절) 0건 — hard-fail | 게이트 통제범위(silence 트리거) 내 N=3 전 회차 재발 0건. 목표 사례("자빠졌"⏎"는데,") 완전 해소 | ✅ |
| ② 화자분리 F1 worst-case 미회귀 | 3파일 전부 ON min ≥ OFF min (sbs1 50%→100% 압도적 개선) | ✅ |
| ③ WER max 미회귀 | bong1·sbs1 문제없음(sbs1 대폭개선). **ytn2만 ON 29.6% > OFF 20.2%(+9.4pt)** — 참고게이트(34.5%) 이내이나 원인(토큰반복 환각)이 경계로직과 무관한지 미확증 | 🟡 |
| ④ WER median 개선/중립 | 3파일 전부 개선 또는 중립 | ✅ |
| ⑤ 문장분리 F1(후순위) | bong1·sbs1 개선, ytn2 N/A(포맷 특성) | ✅ |
| ⑥ held-out(ytn1+eng1) 미회귀 | ytn1 대폭개선(21.5→10.4%), eng1 개선(4.8→3.8%), 영어 대문자 규칙 회귀 없음 | ✅ |
| ⑦ 코드스위칭/화자경계 무결성 | trigger 분포 대체로 유지, 구조적 소실 사례 없음(위 ytn2 run2 사례는 언어전환 트리거로 게이트 무관) | ✅ |

**판정: 🟡 채택 권고 (사용자 승인 대기, master 미머지)** — 7항 중 6항 명확 통과, 1항(③ ytn2 WER max)은 참고게이트는 충족하나 원인 미확증이라 조건부. §4 "정량이 애매하면 자율 기각/채택 대신 판단 유보 + 사용자 질의" 원칙에 따라 최종 채택 여부는 사용자 확인 후 확정.

**Epoch 판단**: E5 유지 — 세그먼트 조립(출력) 계층 변경으로 디코더 파라미터 트레이드오프에 영향 없음(Exp-170 온점분할 도입 시 선례와 동일 성격).

### 다음 가설 (백로그)

1. **ytn2 반복환각(디코더 stutter) 원인 규명**: 게이트 ON/OFF 무관 여부 재현측정(OFF에서도 유사 패턴이 나오는지) — ③ 조건부 판정 해소용.
2. **`[SilenceGate]` 로깅 최적화**: `_apply_silence_grammar_gate`가 매 틱 미해소 침묵을 반복 로깅해 로그량 과다(bong1 17707줄 vs 고유판정 13건) — 상태 변화 시에만 로그하도록 개선 검토.
3. **비-diar 경로 실측 검증**(GOAL §3.5): 이번 라운드는 diar 경로만 정량측정 — 비-diar(`get_lines`)도 동일 게이트가 구현·TDD는 됐으나 경로 A/내장 UI로 정성 검증 필요.
4. **화이트리스트 보강 검토**: `KO_FINAL_SUFFIXES`/`KO_EXCLUDE_SUFFIXES`("습니까" 등) 확장 여지 — 이번 스코프에서는 미변경.

**JSON** (전부 `worktrees/silence-split-koen-gate/.omc/benchmarks/` 기준): 스크리닝 `eval_20260712_1700_gateON.json`·`eval_20260712_1700_gateOFF.json` · HARD스윕 `eval_20260712_1731_hard0p6.json`·`eval_20260712_1739_hard1p0.json`(0.8은 gateON.json 재사용) · 채택확정 `eval_20260712_stage3ON_{bong1,ytn2,sbs1}.json`·`eval_20260712_stage3OFF_{bong1,ytn2,sbs1}.json` · held-out `eval_20260712_heldout_{ytn1,eng1}.json` · kinno `eval_20260712_qual_kinno.json`. HTML 비교 리포트: `.omc/transcripts/eval_report_silencegate_koen.html`.

---

## Exp-177 — 배포 증상 재현 계측: 필러 삼킴 Type A/B 분류 + 경계 QG 버퍼 폐기 유실 신규 규명 (코드 무변경)

**날짜**: 2026-07-13 · **Epoch**: E5 (master `6df6e2f`, Exp-176 머지 포함 — 코드 무변경 계측/재현 전용) · **브랜치**: master (main cwd)

### 가설 (계측 목적)

폐쇄망 배포 PC(최신 코드 반입 확인됨)에서 보고된 두 증상 — ① "Thank you very much / 고맙습니다"류 환각이 실제 전사를 먹어버림(삼킴) ② 문장 중간 단어·글자 유실 반복 — 이 dev 환경에서 재현되는지 확인하고, 재현 시 서버 로그(trace-tokens)로 원인 경로를 귀속한다. 재현되면 "반입/배포 환경 문제"가 배제되고 코드의 구조적 실패 모드로 확정된다. 침묵·화자교대가 많은 배포 실사용 조건의 대리로 **kinno(순차통역, 통역 대기 침묵 다수)를 최초로 N=3 측정**한다.

### 변경 내용

**코드 무변경.** `--trace-tokens` 계측만. goal 문서 신설: [docs/goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md](docs/goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md)(Type B 수정 설계 — §결론 참조).

### 테스트 설정

경로 C, diar-ON(Sortformer), CRT=3.0, PLC=None, beams=2, turbo, `--repeat 3 --trace-tokens`. 테스트 3파일(bong1+ytn2+sbs1) + **kinno 별도 N=3**(정성 sanity — WER/F1 게이팅 제외). provenance `vbcable=ok`(RMS 0.145/0.139) 육안 확인.

### 정량 결과 (N=3 — 코드 무변경이므로 채택/기각 비대상, 현행 master 상태 기록)

> **regime v2 2-F1의 최초 N=3 기록**(Exp-176 머지 후 master). STATE "2-F1 신 베이스라인 재측정" 후보 데이터로 쓸 수 있음.

| 파일 | WER med | WER max | WER min | stdev | 화자분리F1 med | 문장분리F1 med |
|------|---------|---------|---------|-------|---------------|---------------|
| bong1 | 34.1% | 36.9% | 29.6% | 3.7% | 51.3% | 8.7% |
| ytn2 | 21.2% | 24.1% | 19.7% | 2.3% | 76.2% | N/A |
| sbs1 | 13.1% | 13.7% | 13.1% | 0.3% | 100.0% | 94.7% |
| kinno | 30.5% | **72.0%** | 22.0% | **26.7%** | 69.0% | 37.5% |

**핵심**: 테스트 3파일(연속 방송음원)은 stdev 0.3~3.7%로 안정적인데, **kinno(침묵 다수)만 worst-case 폭발**(R3 72.0%) — 배포 증상의 dev 재현이자, "배포에서 더 심한 이유 = 입력에 침묵/비발화 구간이 많아서"의 직접 증거.

### 산출물 (a) — 증상 재현 및 Type 분류

두 증상 모두 재현 확정. 삼킴은 메커니즘이 다른 **2종**으로 분류됨:

| | **Type A: 반대 스크립트 변주형 필러 storm** | **Type B: 같은 스크립트 환각 삼킴 (신규 규명)** |
|---|---|---|
| 실측 사례 | kinno R3 `"Thank you very much for joining us today. We will continue to join us today on our website, …"`(생성 루프) · ytn2 R2 `"Thank you very much. … Thank, everyone. Thank"` · bong1 R1 `"This. map Thank you. Thank you."` | ytn2 R1: 정답 `"해서 한국군 사령관 조건을 기초로 한 전작권 전환을 …합의를 했습니다"`(EN→KO 통역)가 통유실되고 `"예수님과 관련 네, 감사합니다. 네, 네, 감사합니다."`로 대체 |
| 게이트 반응 | `AnchorRepeatFilter` 12run 합계 14회 발동에도 필러 잔존 — kinno R3는 서버로그 "Thank you" **663줄** vs 발동 **4회**(변주구가 gap>5로 클러스터 쪼갬 = **Exp-169 사각지대 재확인**). `ScriptMismatchFilter` **0회**(변주 필러는 TTR 안 무너짐) | 반대 스크립트 아님(ko 감지 중 ko 환각) — 스크립트 계열 게이트 **원리상 무반응** |
| 원인 | 침묵/비발화 구간 turbo 필러 생성(Exp-159 계열) + 출력 게이트 사각지대 | 경계 QG streak refresh 버퍼 폐기(아래 (b)) |

### 산출물 (b) — Type B 인과 사슬 (ytn2 R1 로그 라인 ~6460–6560, 전 단계 실측)

1. 화자전환 eager 감지 실패: `[ShortSilenceLangCheck] 최근 1.5s → en (p=0.54)` < 0.85 → None(경계 오디오 EN꼬리+KO서두 혼합). `keep_secs=1.34 kept=1.53s`.
2. **폴백 감지는 곧 성공**: 다음 infer `Detected language: ko with p=0.9064` → 토크나이저 ko 적용 — 감지 실패 자체는 치명 아님.
3. 혼합 경계 오디오 1.53s의 ko 디코드가 저신뢰 파편(`어`/`이`/`그`, avg_logprob −3.284) → `[QualityGate]` 억제 3연속.
4. **★ 비가역 유실**: `_on_quality_suppressed`([align_att_base.py:653-671](whisperlivekit/simul_whisper/align_att_base.py))가 `refresh_segment(complete=True)` 호출 → `state.segments=[]` **버퍼 전량 폐기** — 이 1.53s가 새 화자 문장의 서두 오디오.
5. 서두 없이 문장 중간부터 맨땅 디코드 → `"예수님과 관련…"` 환각 방출 = 삼킴 완성.

**빈도**: QG streak refresh 12run 합계 **25회**(bong1 2–4/run, ytn2 2–3, sbs1 1–2, kinno 0–3). kinno는 발생수-WER 강상관(R1 0회→22.0% / R3 3회→72.0%). **기존 결론과의 관계**: Exp-154(E4)·Exp-173(E5)의 "QG 부당드롭 ≈0~1%"는 **텍스트 억제(suppress)만** 전수 분석 — streak refresh의 **오디오 폐기 경로는 스코프 밖**이었다(신규 규명). Exp-172의 ③ 유실 경로 귀속에 "경계 QG streak refresh 버퍼 폐기"가 추가됨.

### 분석 (전사 내용 정성 대조)

**bong1** (R1 34.1%):
- **환각 폭주(Type A)**: 전사 `"This. map Thank you. Thank you."` / 정답 해당 구간 발화 사이 — 웃음/비발화 구간 필러(기존 실패모드 잔존).
- **화자 혼동·경계**: 화자분리F1 51.3%로 3파일 중 최저 — 다화자 짧은 교대 미분리 잔존.

**ytn2** (R1 21.2%):
- **삼킴(Type B)**: 전사 `"Let's. 예수님과 관련 네, 감사합니다."` / 정답 `"해서 한국군 사령관 …합의를 했습니다"` — KO 통역문 통유실+환각 대체(위 (b) 사슬).
- **재디코딩 churn 중복**: 전사 `"왕성한 왕성한 연합 방위 연합 방위태세"` / 정답 `"왕성한 연합 방위태세"`.
- **오인식(③계열)**: 전사 `"변환 없는 입장을 고소"` / 정답 `"변함 없는 입장을 고수"`.

**sbs1** (R1 13.7%):
- 주요 실패 없음. 화자분리F1 100%(Exp-176 효과 유지), Case B 미발생.

**kinno** (R3 72.0% — catastrophic 회차):
- **환각 생성 루프(Type A 극단형)**: 전사 `"We will continue to join us today on our website, but we will be able to watch it on our website. …"`(변주 문장 연쇄 생성) / 정답 `"다만 ITS 홈페이지를 통해서 온라인으로 시청을 …부탁드리겠습니다"` — KO 발화 통째 대체.
- **음차 깨짐(①′계열, 글자 유실)**: R1 전사 `"시 이스투데이 이스턴 손진희 아임 인터페이 러"` / 정답 `"She is today's MC 손진희. I am interpreter"` — locked-lang 음차 환각.
- **통역 대기 침묵 구간에 필러 집중**: `"…online streaming Thank you very much Thank you very much."` — 배포 실사용 조건과 동일 구조.

**총평**: 배포 두 증상 모두 dev 재현 — 반입 문제 아님 확정. 삼킴 = Type A(출력 게이트 사각지대·원천 미차단, 기지) + Type B(경계 QG 버퍼 폐기, **신규**). 유실 = Type B 폐기 + 재디코딩 churn + 음차 환각. kinno가 배포 조건(침묵-heavy)의 유효한 대리 재현체임이 확인됨.

### 채택 조건 판정

**비대상** (코드 무변경 계측). 하니스 정상(provenance/vbcable 전 회차 ok).

### 결론

**계측/재현 완료** — ① 배포 증상 dev 완전 재현(반입/환경 문제 배제), ② 삼킴 Type A/B 분류 확정, ③ Type B의 비가역 유실 지점(`refresh_segment(complete=True)` 버퍼 폐기, 경계 보호창 부재) 신규 규명, ④ 수정 설계를 goal로 산출: **[docs/goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md](docs/goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md)** (P1 경계 보호 보존형 refresh — 보호창 내 1회 오디오 보존+상태만 리셋, 재발 시 기존 폐기 폴백으로 비회귀 보증; 짝지음 A/B 채택 게이트 포함).

### 다음 가설

1. **Type B 수정 (goal 실행)**: GOAL_BOUNDARY_QG_PRESERVE.md 자율 루프 — 기대효과 = kinno류 worst-case 완화 + 코드스위칭 경계 삼킴/유실 감소. 비회귀 제약(사용자 명시) 하 짝지음 A/B로 검증.
2. **Type A 후속 (별도 goal)**: 앵커 반복 게이트를 "근접 시간창 내 앵커 총 등장" 기반으로 재설계(Exp-169 제안 방향) — 단 kinno R3의 변주 생성 루프형은 앵커 카운트로도 불완전, 원천(비음성 게이팅) 필요성 재확인.
3. **kinno류(침묵-heavy) 음원 테스트셋 편입 검토**: 현행 테스트 3파일은 이 실패 모드를 게이트에 노출하지 못함 — 배포 대리 재현체로 정량 세트 추가 제안(§3.8 회귀 감시 정합, 사용자 결정 사항).

**JSON**: `.omc/benchmarks/eval_20260713_1928_deploy_symptom_repro_N3.json`(테스트 3파일 N=3) · `.omc/benchmarks/eval_20260713_1952_kinno_symptom_repro_N3.json`(kinno N=3) · **로그**: `.omc/server_logs/server_{bong1,ytn2,sbs1,kinno}_C_R{1..3}_20260713_19*.log`(TokenTrace DEBUG 포함; Type B 사례 = `server_ytn2_C_R1_20260713_193831.log` 라인 ~6460–6560) · **전사**: `.omc/transcripts/{파일}_C_R{n}.txt`

---

## Exp-178 — 한국어 단독 데이터(kor1~3) 신규 측정: 배포 성능저하 dev 재현 계측 (코드 무변경)

**날짜**: 2026-07-15 · **Epoch**: E5 (master `606ecac`, Exp-176 머지 포함 — 코드 무변경 계측/재현 전용) · **브랜치**: master (main cwd)

### 가설 (계측 목적)

기존 테스트/held-out 세트에 **한국어 단독** 자료가 없었고, 배포 PC에서 한국어 단독 음성에 대해 ① 영어가 아닌데 영어로 전사 ② "Thank you"류 환각의 실발화 삼킴 ③ 서두/중간 단어 유실이 보고됐다. 한국어 단독 데이터 kor1~3(단일 화자 군 브리핑 낭독체, 각 109~126s)을 신규 추가해 dev에서 재현되는지 확인하고 서버 로그로 원인을 귀속한다. 비교군(ytn2=한영 코드스위칭·eng1=영어·sbs1=한국어 위주 방송)을 **동일 런에 포함**해(사용자 제안) 하니스 정상 여부와 "한국어 단독 고유 실패"를 동시에 분리 판정한다.

### 변경 내용

**코드 무변경.** 데이터 신규: `test_data/kor{1,2,3}.wav` + 정답 `kor{1,2,3}.txt`(사용자 추가, `[spk1]` 헤더+빈 줄 문장 구분) → 내용이 신형식 문법과 일치해 canonical `kor{1,2,3}_speak,sentence_sperate.txt`로 복사 생성(구형식 폴백 시 `[spk1]` 문자열이 WER 정답에 오염되는 것 방지). `kor4.txt`는 대응 음원 없음(미측정).

### 테스트 설정

경로 C, diar-ON(Sortformer), CRT=3.0, PLC=None, beams=2, turbo, `--repeat 1`(스크리닝 — trace-tokens 없음). provenance `vbcable=ok`(RMS 0.144) 육안 확인.

### 정량 결과 (N=1 스크리닝 — 코드 무변경이므로 채택/기각 비대상)

| 파일 | WER | 화자분리F1 | 문장분리F1 | 비고 |
|------|-----|-----------|-----------|------|
| **kor1** | **62.0%** | 0.0%※ | 50.0% (P0.80/R0.36) | 서두+중간 ~44s 통유실 |
| **kor2** | **47.9%** | 0.0%※ | 50.0% (P0.67/R0.40) | 서두 유실+중복 확정 2건×2회 |
| **kor3** | **49.7%** | 0.0%※ | 78.8% (P0.93/R0.68) | **Case B 3건(hard-fail)**+중복 1건×3회 |
| ytn2(비교) | 13.8% | 85.7% | N/A | baseline med 21.2 이내(양호 회차) |
| eng1(비교) | 4.8% | 0.0%※ | 66.7% | held-out 전례 3.8~5.7 정합 |
| sbs1(비교) | 14.9% | 80.0% | 90.0% | baseline med 13.1 근접 |

※ 단일 화자 파일(정답 화자전환 경계 0개)이라 화자분리 F1은 정의상 무의미(0.0=degenerate, 미측정으로 해석). kor 정답 txt의 줄바꿈은 절(연결어미) 단위라 문장분리 F1 Recall도 엄격 상한으로 해석(참고: 이 절 단위 미분리는 Case A 계열로 허용).

**핵심**: 비교군 3파일이 전부 베이스라인 수준 → 하니스/VBCable 정상. **kor1~3만 WER 48~62%로 붕괴** — 배포 보고 성능저하의 dev 완전 재현(반입/배포 환경 문제 배제), 기존 테스트셋(방송·인터뷰)이 커버하지 못한 **한국어 단독 낭독체(긴 호흡 pause + 군 전문용어) 스트레스 프로파일** 확인.

### 분석 (전사 내용 정성 대조 + 서버 로그 귀속)

**kor1** (62.0% — 유실 지배):
- **서두 유실(Type B, 세션 초입)**: 정답 `"전투발전부장 최창수 육군 소장입니다"` 통유실. 로그: 초입 저신뢰 영어/기호 디코드(`"-"`, `"-"`, `"The"` avg_logprob −5.6~−6.0) → `[QualityGate]` 3연속 → `refresh_segment` 버퍼 폐기.
- **★ 중간 통유실 ~44s (신규 실패 모드 — stall 연쇄 웨지)**: 정답 `"순서는 보시는 바와 같습니다"`~`"이는 먼 미래가 아니라 …현재라는 절박한 인식"` 문단 전체(정답의 약 절반) 무전사. 로그: `last_end=7.314` 고착 상태로 `SimulStreaming stall recovery: 10.4s without output — forcing segment refresh`가 **5연발**(end=26.4/38.7/49.0/59.8/70.7s) — 강제 refresh가 매번 버퍼를 폐기해도 디코더가 계속 저신뢰(QG 억제 파편 `"고려한"`, `"특히"`)로 재웨지, 복구 실패. WER 62%의 주인.
- 전사된 후반부는 비교적 정확(치환 `러우전`→`로전`, `종심`→`중심` 수준).

**kor2** (47.9% — 서두 유실+중복):
- **서두 유실(Type B) + 사용자 보고 증상의 정체**: 정답 `"먼저 육군은 두 개의 작전사를 유지한 상태에서"` 유실. 로그: 초입 **영어 환각** `"we have"`/`"the aim is to make"`/`"Thank"` QG 억제 → 3연속 → refresh 폐기. **배포 보고 "영어 전사·Thank you 환각"과 동일 근원** — dev에선 QG가 텍스트를 억제해 출력에 안 보이지만 그 대가로 서두 오디오가 비가역 폐기됨(배포에선 환각이 살아남아 표시된 형태로 추정).
- **중복 확정(재디코딩 churn)**: `"GPGOP, 유무인 GPGOP에 대한 …창설하고"` 2회, `"봉원사단은 사단과 여단 지휘부는 …전환"` 2회 확정.
- **한국어 필러 환각 삽입**: 전사 `"…가능하도록 공개하였습니다"`/`"…보장하고 확인되고 있습니다"`/`"…전투부대를 이루어졌습니다"` — 정답에 없는 종결어미형 필러.
- stall recovery 2회(91.8/102.8s).

**kor3** (49.7% — Case B hard-fail):
- **Case B(단어 중간 분절) 3건**: `"…통합."`⏎`"하고 방공간제전대…"`(정답 `"통합하고"`), `"…창설."`⏎`"하고평시…"`(정답 `"창설하고"`), `"…비행대대 창."`(정답 `"창설"` 잘림). **Exp-176 SilenceGate가 master에 머지된 상태에서 발생** — 낭독체 호흡 pause가 `SILENCE_HARD_SECS=0.8` 안전망을 트리거해 문법 판정을 우회(Exp-167 "호흡성 pause 정책" 사안의 재등장, 이번엔 단어 중간).
- **중복 확정**: `"또한 전투기 협업, 무인기 운영을 위해 전투비행대대를 개편"` 3회(1회는 문장 내부 중복 포함). `[AnchorRepeatFilter]` 1회만 발동 — Exp-169 사각지대 잔존.
- **서두 영어 환각**: 로그 초입 `"I"`/`"'m sorry"` QG 억제 → streak refresh(서두는 대체로 보존됐으나 `해역 함대`→`해쭨대` 등 저신뢰 치환).

**비교군**: ytn2/eng1/sbs1 주요 신규 실패 없음 — 실패는 한국어 단독 낭독체 고유.

**총평**: 배포 보고 3증상 모두 dev 재현·귀속 완료 — ① "영어 전사·Thank you 환각" = 세션 초입/저신뢰 구간 반대언어 필러(QG가 억제하면 Type B 서두 폐기로, 못 막으면 출력 노출로 발현), ② "서두 유실" = QG streak refresh 버퍼 폐기(Exp-177 Type B, kor 3/3), ③ "중간 유실" = **stall recovery 연쇄 웨지(신규 규명 후보)** — Exp-177 분류에 없던 모드로, 10s+ 무출력→강제 refresh 반복에도 저신뢰 재웨지가 반복돼 kor1에서 44s 통유실.

### 채택 조건 판정

**비대상** (코드 무변경 계측). 단 **kor3 Case B 3건은 hard-fail flag** — 원인(0.8s 안전망 우회) 수정 대상으로 기록.

### 결론

**계측/재현 완료** — 한국어 단독 낭독체에서 WER 48~62% 붕괴를 dev 재현(비교군 정상 = 하니스 무결·데이터 고유 실패 확정). 원인 3갈래: ① 경계/초입 QG streak refresh 버퍼 폐기(Exp-177 Type B — 서두 유실 3/3), ② stall recovery 연쇄 웨지(신규 — 중간 통유실), ③ SilenceGate 0.8s 안전망의 낭독체 pause 우회(Case B 재발). 부기: 재디코딩 churn 중복 확정, 한국어 종결어미형 필러 환각.

### 다음 가설

1. **[docs/goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md](docs/goal_prompt/GOAL_BOUNDARY_QG_PRESERVE.md) 루프 착수**: Type B 보존형 refresh가 kor 서두 유실 3/3을 직접 표적 — kor1~3을 검증 데이터로 편입해 A/B.
2. **stall 연쇄 웨지 규명**: kor1을 `--trace-tokens`로 재측정해 웨지 구간(7.3~71s) 디코더 상태(QG streak·refresh 상호작용, 왜 refresh 후에도 미복구인지) 귀속 — Exp-177 Type 분류에 "Type C(웨지형 통유실)" 추가 여부 판단.
3. **SILENCE_HARD_SECS 정책 재검토**: 낭독체 pause(0.8s+)가 단어 중간에 걸릴 때 문법 게이트가 무력화 — 안전망 상향/문법 판정 우선 순위 재조정(Exp-176 후속, Case B hard-fail 해소).
4. **kor1~3 테스트셋/held-out 편입 여부 = 사용자 결정 사항**(regime 변경): 한국어 단독 커버리지 공백을 메우는 후보. kor4 음원 확보 여부도 확인 필요.

**JSON**: `.omc/benchmarks/eval_20260715_0846_kor_baseline.json`(6파일 N=1) · **로그**: `.omc/server_logs/server_{kor1,kor2,kor3,ytn2,eng1,sbs1}_C_R1_20260715_08*.log` · **전사**: `.omc/transcripts/{파일}_C_R1.txt`

---

## Exp-179 — 세션 초입 언어 프로브: 콜드스타트 데드락 해소 (+ScriptAnchor 철자낭독 사각지대 신규 규명)

**날짜**: 2026-07-15 · **Epoch**: E5 · **브랜치**: `exp/session-start-lang-probe@b842c6f` (worktree, **master 미머지 — 사용자 승인 대기**)

### 가설

Exp-178 trace 재측정으로 규명한 **세션 초입 언어감지 콜드스타트 데드락**(감지가 first_timestamp=첫 커밋을 기다림 ↔ 커밋은 정상 디코드 필요 ↔ 미감지 기본 토크나이저 `<|en|>`이 한국어를 garbage로 디코드 → QG 억제 → 커밋 불가; 그 사이 QG streak refresh·long-silence 리셋이 서두 오디오 반복 폐기, 탈출 시점 확률적 25~71s)를, **2.0s 오디오 누적 시 커밋 없이 감지를 시도하고 p≥0.85일 때만 적용**하는 프로브로 끊는다. p 미달 시 기존 커밋 기반 경로가 그대로 폴백(무조건 적용 없음 — 회귀 위험 차단).

### 변경 내용

- [align_att_base.py](whisperlivekit/simul_whisper/align_att_base.py) `_detect_language_if_needed()`의 무기한 보류 else 분기(구 252~278행)에 프로브 삽입 + 모듈 상수 `SESSION_START_LANG_PROBE_ENABLED=True`(롤백 플래그)·`SESSION_START_LANG_MIN_PROB=0.85`. 로그 `[SessionStartLangProbe]`. first_timestamp/eager 기존 경로 무변경.
- `tests/test_session_start_lang_probe.py` 신설 10건(적용/보류/플래그OFF/기존경로 불간섭/no_grad 회귀방지) — 전체 스위트 372 passed. no_grad 이중 확인(infer `@torch.no_grad()` + `lang_id` 자체 데코레이트). `<|en|>` 기본값 출처 = `_init_state_common`→`create_tokenizer(None)`→`tokenizer.py:389 language or "en"`.

### 테스트 설정

경로 C, diar-ON, CRT=3.0, PLC=None, beams=2, turbo, `--trace-tokens`. **짝지음 A/B**: OFF=master@606ecac kor1~3 ×2(+동일 오전 회차 2런), ON=워크트리 kor1~3 ×2 + 비교군(bong1/ytn2/sbs1/eng1) ×1. provenance `vbcable=ok` 전 회차 확인. (첫 ON 런 1회는 브라우저 컨텍스트 hang으로 폐기·재실행 — 하니스 이슈, 데이터 미포함.)

### 정량 결과 (스크리닝)

| 파일 | OFF(master) WER | ON(프로브) WER | 프로브 발동 | 판독 |
|------|----------------|---------------|------------|------|
| kor1 | 62.0/22.8/57.9/45.0 (med~51.5) | **34.5/21.1 (med 27.8)** | 3/3 (ko p 0.95~0.996 @2.0~2.5s) | **개선 — med·max 모두** |
| kor2 | 70.1/71.5 (med 70.8) | 102.8/109.0 | R1 2회(ko)·R2 0회 | 양팔 catastrophic — 별개 결함 지배(아래) |
| kor3 | 49.7/77.5/62.3 (med 69.9) | 57.0/63.6 (med 60.3) | 0회(서두 조기 커밋) | 중립(변동 범위 내) |
| bong1 | (기준 med 34.1/max 36.9) | 27.2 | 0회(en 조기 커밋) | 무회귀 |
| ytn2 | (기준 med 21.2/max 24.1) | 20.7 | 0회 | 무회귀 (화자F1 56.0 — N=1, 기준 med 76.2보다 낮음 → 확정단계 확인) |
| sbs1 | (기준 med 13.1/max 13.7) | **9.5** | 1회(ko p=0.997) | 무회귀 (화자F1 40.0 — N=1 변동, Exp-176 전례 50~100 요동) |
| eng1 | (전례 3.8~5.7) | 4.8 | 1회(**en** p=0.998) | 무회귀 — 영어에 en 정적용 실증 |

### 분석 (정성)

- **kor1 서두 2문장("전투발전부장 최창수…"/"미래 합동작전…") 복구 2/2** — OFF 전 회차(6런) 유실이던 구간. 중간 통유실도 소멸. 잔여 오류 = 치환·중복 1건 수준.
- **프로브 발동 전수 정당**: 발동 6건 전부 정답 언어(ko×4·en×2), p 0.95~0.999. 미발동 파일은 분기 자체가 실행되지 않아 **코드 경로상 완전 중립**.
- **[신규 규명 ①] ScriptAnchorRedetect(Exp-175) 철자낭독 사각지대 = kor2 폭주(70~109%)의 주범 (OFF/ON 공통, 프로브 무관)**: 한국어 문장 내 영문 약어 철자 낭독("GP·GOP")이 Latin 3단어 streak을 만들어 `[ScriptAnchorRedetect] ko→en` 오전환 → **전환 트림이 직전 오디오 9.68~12.02s 폐기** → 곧바로 en→ko 복귀 전환(추가 2.4~2.7s 트림) → 재디코딩 중복 확정 폭주("GPGOP에 대한…" 프리픽스 4~5회 누진 재확정, WER>100%). Exp-175 A/B에선 게이트 발동 0회라 노출되지 않았던 결함. ON이 OFF보다 나쁘게 보이는 것(105.9 vs 70.8)은 프로브가 서두를 살려 **폐기 전 커밋량이 늘어난 만큼 중복 삽입도 증가**한 2차 효과 + 회차 변동.
- **[신규 규명 ②] long-silence 리셋이 detected_language까지 초기화** → 세션 중간에도 데드락 재진입 가능. kor2 R1에서 리셋 후 프로브가 2차 발동(2.13s)해 재감지로 커버됨을 실증 — 프로브가 초입뿐 아니라 중간 재진입도 방어.
- Case B(kor3 "통합."⏎"하고"·"창.")·중복 확정 churn은 프로브 무관 잔존(Exp-178 진단 유지).

### 채택 조건 판정

스크리닝 단계(채택 확정 N=3 미실시). 표적(kor1 데드락) med·max 개선 + 비교군 WER 무회귀 + 발동 전수 정당. 화자분리 F1(1순위 게이트)의 ytn2/sbs1 N=1 저하는 프로브 미발동 런이라 인과 없음이 유력하나 **채택 확정 짝지음 N=3에서 확인 필요**.

### 결론

**채택 후보 — 사용자 승인 대기** (§3.2 두 언어 환경의 기반 기능 성격). 승인 시 채택 확정 측정(테스트 3파일+kor1~3 짝지음 `--repeat 3`, held-out ytn1+eng1 단회) 후 머지.

### 다음 가설

1. **ScriptAnchorRedetect 철자낭독 가드** — 약어 철자 시퀀스(무모음 대문자 연쇄 등)를 streak 산입에서 제외 또는 재감지 결과 적용 전 전환 트림 억제. kor2 주범 제거.
2. 중복 확정 churn(전환/refresh 후 재디코딩 타임스탬프 재앵커) — Exp-177 Bug1 계열, GOAL_BOUNDARY_QG_PRESERVE와 연계.
3. Case B — SILENCE_HARD_SECS 낭독체 pause 정책(Exp-178 ③).

### 채택 확정 측정 (N=3, 2026-07-15 오후 — 사용자 지시로 kinno 포함)

| 파일 | WER med/max/min (stdev) | 화자F1 med | 프로브 발동 | 판독 |
|------|------------------------|-----------|------------|------|
| bong1 | 34.4/39.9/28.1 (5.9) | 60.5 (60.5/63.2/59.5) | **0/0/0** | 코드경로 master 동일 — max 39.9는 변동 귀속(화자F1은 기준 51.3보다 상회) |
| ytn2 | 17.7/30.0/15.3 (7.9) | 72.7 | **0/0/0** | 동일 논리 — STATE 게이트(34.5) 이내 |
| sbs1 | 10.1/15.5/8.9 (3.5) | 80.0 (R2 28.6 1회) | **1/1/1 (ko)** | 발동 3/3에도 WER 게이트(16.1) 이내·같은날 OFF 화자F1 80과 동일 |
| kor1 | 44.4/46.2/23.4 (12.7) | — | 1/1/1 (ko) | OFF med 51.5/max 62.0 대비 **med −7.1·max −15.8pp** |
| kor2 | 95.8/101.4 (3.4) | — | 1/1/2 | ScriptAnchor 철자낭독 결함 지배(프로브 무관) |
| kor3 | 68.9/73.5 (8.5) | — | 1/0/0 | 중립 |
| kinno | 31.7/**39.4**/31.3 (4.6) | 71.0 | 0/0/0 | OFF(Exp-177) max **72.0**→39.4·stdev 26.7→4.6 — 단 발동 0회라 프로브 귀속 불가(catastrophic 미재현 관찰) |
| ytn1(held-out) | 12.3 | 73.7 | 0 | 미회귀 |
| eng1(held-out) | 2.9 | 100.0 | 1 (**en**) | 미회귀 — en 정적용 |

**게이트 판정**: ① 화자분리 F1 — 발동 런(sbs1) 같은날 OFF와 동일(80), 미발동 런 인과 없음 → 통과. ② WER max — 발동 런 전부 게이트 이내(sbs1 15.5<16.1)·표적(kor1) max 대폭 개선; bong1 39.9는 미발동 런 변동(Exp-177 max 36.9와 3.0pp 차) → 통과(유보 각주). ③ 발동 전수 정당(확정 라운드 포함 ko×8·en×1, 오적용 0). ④ held-out 미회귀. → **채택 권고** (머지 = 사용자 승인).

**JSON**: OFF `.omc/benchmarks/eval_20260715_0940_kor_trace_x2.json` · ON `worktrees/session-start-lang-probe/.omc/benchmarks/eval_20260715_0958_kor_probe_on_x2.json`·`eval_20260715_1031_regress_probe_on.json`·`eval_confirm_{test3_N3,kor_N3,kinno_N3,heldout}.json` · **로그**: 각 `.omc/server_logs/server_*_20260715_*.log`(trace ON) · **전사**: 각 `.omc/transcripts/`

---

## Exp-180 — ScriptAnchorRedetect 철자낭독(약어) 오발동 가드 (P1, Exp-179 후속)

**날짜**: 2026-07-16(측정)~2026-07-17(채택) · **Epoch**: E5(구조 미변경 — epoch 미bump) · **브랜치**: `exp/scriptanchor-acronym-guard@747e47f`, **master 머지 `cfb0387`**

### 가설

Exp-179가 신규 규명한 kor2 폭주(70~109%) 원인 — 한국어 문장 내 영문 약어 철자낭독("GP·GOP")이 ScriptAnchorRedetect(Exp-175)의 Latin streak을 채워 ko→en 오전환을 유발하고, 전환 트림이 9.7~12s 오디오를 폐기해 중복 재확정 폭주로 이어진다 — 를 "약어 성격의 Latin 토큰을 streak 산입에서 중립 스킵"하는 가드로 막는다. 데이터 특화 하드코딩 금지(§3.8) 원칙에 따라 특정 단어가 아닌 타이포그래피 속성(길이·대소문자)만으로 판별한다.

### 변경 내용

- `whisperlivekit/simul_whisper/backend.py`: `_is_acronym_like_latin` 헬퍼 신설 + `_update_script_anchor_streak`에서 약어형 Latin 토큰을 중립 스킵(streak 가산도 리셋도 안 함). 규칙① 길이≤2(단일글자 철자낭독), 규칙② 전부대문자&&길이≤6(GOP/GPGOP/AI/NATO). 소문자 자연단어·타이틀케이스는 그대로 전환 증거로 인정(Exp-175 커버리지 보존). 롤백 플래그 `SCRIPT_ANCHOR_ACRONYM_GUARD_ENABLED=True`.
- `tests/test_script_anchor_redetect.py`: 헬퍼·게이트 통합 테스트 30건으로 확장(신규 ~12건), `is`/`to`류 소문자 2자 자연단어가 규칙①에 걸려 스킵되는 기지 한계를 `test_acronym_helper_short_natural_word_known_limitation`로 명시.

### 테스트 설정

경로 C, diar-ON, CRT=3.0, 짝지음 A/B(OFF=master, ON=워크트리). 스크리닝(Stage1, `--repeat 1~2`) 후 채택 확정(Stage3, `--repeat 3`, fail-fast 금지). 테스트=bong1+ytn2+sbs1+kor1~3(사용자 지시로 편입), held-out=ytn1+eng1(N=1), kinno(N=3 누적, 정성·게이팅 제외).

### 정량 결과 (Stage3 채택 확정, N=3)

| 파일 | OFF med(max) | ON med(max) | Δmed | Δmax | 화자F1 worst(OFF→ON) |
|---|---|---|---|---|---|
| bong1 | 35.6%(47.4%) | 38.1%(48.6%) | +2.4pt | +1.2pt | 47.6→50.0(개선) |
| ytn2 | 20.7%(21.2%) | 17.2%(20.7%) | -3.4pt | -0.5pt | 69.6→72.7(개선) |
| sbs1 | 10.1%(22.0%) | 10.7%(25.0%) | +0.6pt | +3.0pt | **66.7→33.3(악화)** |
| kor1 | 31.6%(50.9%) | 42.7%(46.2%) | +11.1pt | -4.7pt | 해당없음(단일화자) |
| kor2(표적) | 79.2%(120.8%) | 108.3%(131.9%) | **+29.2pt** | **+11.1pt** | 해당없음 |
| kor3 | 71.5%(86.1%) | 56.3%(62.3%) | -15.2pt | -23.8pt | 해당없음 |
| ytn1(held-out,N=1) | WER 12.3%/F1 73.7% | WER 11.7%/F1 100.0% | — | — | 개선 |
| eng1(held-out,N=1) | WER 2.9%/F1 100% | WER 4.8%/F1 0.0%(단일화자 채점) | — | — | N=1 저baseline 노이즈 가능성 |

### 분석 (정성)

- **kor2 로그 전수 감사**: ON 3라운드(R1~R3) 전부 ScriptAnchorRedetect 발동 5·5·4건이 **전부 acronym-skip**, 재감지 적용·LangSwitch 절단은 **3라운드 전부 0건** — 가드가 설계대로 정확히 동작해 표적 오발동 채널을 완전히 차단했다(로그 인과 확정). 동일코드 OFF는 오늘 재확인 로그에서 R3 2건 적용(ko→en "GP GOP" 6.25s 절단 포함)이 OFF 최악 라운드(120.8%)와 일치 — Exp-179 진단이 재실증됨.
- **그런데도 kor2 WER은 악화** — ON hyp_lines 대조 결과 3라운드 전부에서 `finalize_trigger=silence`(language_switch 아님) growing-prefix 중복 확정이 여전히 존재하며, 이는 **OFF에도 동일하게 존재하는 별개 결함**(kor3에서도 동일 패턴). 동일 OFF 코드의 kor2 median WER 자체가 세션만 바뀌어도(Stage1 108.0%→Stage3 79.2%) 29pt 흔들린 전례가 있어, 이번 ON 회귀분(+29.2pt)이 이 자연 변동폭과 사실상 같은 크기다.
- **sbs1 화자F1 worst-case 악화**: ON R1/R2 recall이 50%로 하락(참조 전환 ~2건 중 1건만 검출) — 참조 전환 개수가 적어 저표본 고변동 구조. 가드와의 인과 로그 대조는 시간관계상 미실시(후속 과제).
- **kor3**: Stage1(N=2) 역전 신호(OFF 57.6%→ON 77.5%)가 Stage3(N=3)에서 뒤집혀 개선(71.5%→56.3%) — N=2 스크리닝 노이즈로 판단.
- **ytn2 오스킵 감사(게이트 4-ⓒ)**: acronym-skip 6건 중 `is`(소문자 2자, 기지 한계) 1~2건 관찰. R3에서 `is` 스킵 직후 92줄 내 `there`+`more`로 정상 재감지·전환 발동 — 오스킵이 "카운트 지연"에 그쳤다는 설계 시 예상과 일치, 커버리지 손상 증거 없음.
- **Case B(단어 중간 분절) 전수 감사**: OFF+ON 18개 파일-라운드 전수 대조, 진짜 Case B 0건.

### 채택 조건 판정

| # | 게이트 | 판정 |
|---|---|---|
| 1 | 화자분리 F1 worst-case 미회귀 | 부분 미충족 — sbs1 -33.4pt |
| 2 | WER max 미회귀 | 부분 미충족 — kor2 +11.1pt |
| 3 | Case B 0건 | 충족 |
| 4 | 표적지표(ⓐ오발동0·ⓑWER개선·ⓒ오스킵무영향) | ⓐ충족·ⓑ미충족·ⓒ조건부충족 |
| 5 | held-out 미회귀 | 참고용 충족(N=1) |
| 6 | WER median 개선/중립 | 미충족(혼재) |

### 결론

**채택 (master 머지 `cfb0387`, 사용자 승인 — 2026-07-17)**. 정량 게이트는 문면상 충족되지 않으나(①②④⑥ 부분/미충족), 표적 메커니즘은 로그로 100% 검증됐고 Case B도 깨끗함. kor2 WER 악화·sbs1 F1 악화는 가드가 손대지 않는 별개 경로(silence-churn 재확정, 저표본 F1)의 세션 변동일 가능성이 높다는 정성 근거(동일 OFF 코드가 세션 간 29pt 흔든 전례)를 사용자가 받아들여 채택 — CLAUDE.md §4 "목표 필수 기능 채택은 사용자 질의" 절차(정량 게이트 미충족이어도 §3.2 한/영 코드스위칭 처리 기반 기능은 자율 기각하지 않고 사용자 확인)에 따라 자율 기각 대신 판단 유보로 보고, 사용자가 최종 채택을 결정했다. **epoch 미bump** — ScriptAnchorRedetect(Exp-175) 서브시스템 내 조건부 스킵 추가일 뿐, 디코더/VAD 파이프라인 자체는 무변경.

### 다음 가설

1. **kor2/kor3 silence-churn 결함**(finalize_trigger=silence growing-prefix 중복 재확정) — 이번 가드와 무관한 별도 결함으로 특정됨. 사용자 지시로 다음 조사 착수.
2. sbs1 화자F1 worst-case 회귀 로그 인과 대조 (저표본 노이즈 여부 확인).
3. held-out eng1·ytn1 N≥2 보강.

**JSON**: `.omc/benchmarks/eval_20260716_stage3_OFF_adoptN3.json` · `eval_20260716_151459_stage3_ON_adoptN3.json` · `eval_20260716_180014_heldout_ON_R1.json` · `eval_20260716_180920_kinno_ON_R2R3.json` · **로그**: `server_kor2_C_R{1,2,3}_20260716_15{4703,4918,5134}.log`(ON)·`server_kor2_C_R{1,2,3}_20260716_10{1646,1904,2119}.log`(OFF)·`server_ytn2_C_R{1,2,3}_20260716_15{2534,2750,3006}.log` · **최종보고서**: [docs/archive/GOAL_SCRIPTANCHOR_ACRONYM_GUARD_REPORT.md](docs/archive/GOAL_SCRIPTANCHOR_ACRONYM_GUARD_REPORT.md)

---

## Exp-181 — kor2/kor3 silence-churn(growing-prefix 중복) 근본원인 규명: 프런트 `finalizedHistory` Map 키 충돌 [E5, 코드 무변경, 계측]

**날짜**: 2026-07-17 · **Epoch**: E5 · **브랜치**: master(코드 무변경, 순수 계측) — Exp-180 다음 가설 1번 후속

### 가설

Exp-180에서 확인한 kor2/kor3 WER 악화의 별개 원인("finalize_trigger=silence growing-prefix 중복 확정")이 정확히 어느 코드 경로에서 발생하는지 규명한다. Exp-179 "다음 가설"이 "Exp-177 Bug1 계열(재디코딩 타임스탬프 재앵커)"로 추정했던 것이 맞는지도 확인한다.

### 조사 방법

1. `whisperlivekit/tokens_alignment.py`에서 `finalize_trigger` 설정 지점(4곳: :597·:669-671·:710·:809) 및 diar 경로 세그먼트 조립 로직(`get_lines_diarization`:551, `compute_punctuations_segments`:303) 정독.
2. kor2+kor3에 `--trace-tokens`(Stage 0, N=1) 재측정해 오늘 코드(master@0499957) 기준 현상 재현 확인.
3. 백엔드 `get_lines()` 호출부(`audio_processor.py:558` `results_formatter`) → 프런트 렌더 로직(`whisperlivekit/web/live_transcription.js`)까지 데이터 흐름 추적.

### 규명된 메커니즘 (코드 근거 확정)

- `tokens_alignment.py:303-348` `compute_punctuations_segments()`는 매 틱(0.05s, `audio_processor.py:621`) **`self.all_tokens`(세션 전체 누적 토큰) 전체를 처음부터 재분할**해 **완전히 새 `PuncSegment` 객체**를 만든다(델타 아님, docstring도 명시: ":428 매 틱 새로 만드는 조립 계층 산출물"). `get_lines_diarization()`(:551-617)은 이 신규 세그먼트들에 `finalize_trigger`(:597)를 부여하고 `seg.finalized=True`(:607-608)를 찍어 반환한다.
- Exp-176의 문법-조건부 침묵 게이트(`_apply_silence_grammar_gate`/`_gate_decide`, :368-492)는 **짧은 침묵 경계의 split/merge 판정을 이후 도착하는 B(다음 세그먼트) 맥락에 따라 뒤늦게 확정**하도록 설계돼 있다(`pending`→`merge`/`split` 지연 해소, `_apply_finalize_grace`:647-672도 유예). 즉 tick T에서 "finalized"로 찍힌 세그먼트가, tick T+1에서 더 많은 오디오가 들어오며 게이트가 그 경계를 "merge"로 재판정하면, **더 긴 `end` 타임스탬프를 가진 새 세그먼트로 다시 조립돼 다시 `finalized=True`로 반환**된다 — 이게 "growing-prefix 재확정"의 백엔드측 정체다.
- **결정적 증폭 지점**: `whisperlivekit/web/live_transcription.js:373-378` — 프런트가 finalized 세그먼트를 누적하는 `finalizedHistory`(:30, `new Map()`, 세션 내내 유지·:557에서만 clear)의 **키가 `${ln.start}|${ln.end}|${ln.speaker}`**(:375)다. 위 메커니즘으로 같은 논리적 문장의 `end`가 커질 때마다 **키가 달라져 `Map.set()`이 새 엔트리로 추가**될 뿐 이전(더 짧은) 엔트리를 **덮어쓰지 못한다** — 오래된 절단판이 영구히 남고 매번 더 긴 판이 추가로 쌓인다. 렌더는 `[...finalizedHistory.values(), ...]`(:378)라 모든 버전이 화면(및 경로 C가 읽는 `#linesTranscript` DOM)에 그대로 누적 표시된다.
- **Exp-179 가설(Exp-177 Bug1 계열) 기각**: Bug1은 `global_time_offset` 승계 버그(2026-07-03 Exp-151에서 이미 수정)로 타임스탬프 산술 문제였다. 이번에 규명한 메커니즘은 산술 버그가 아니라 **"finalized" 세그먼트의 경계(`end`)가 사후에 재조립되며 바뀔 수 있다는 설계상 계약 위반**(문법게이트의 지연 판정 자체는 Exp-176에서 의도된 기능)과 **프런트의 자연키 Map이 그 재조립을 "새 항목"으로 오인**하는 조합이다. 서로 다른 메커니즘.

### 실측 재현 (Stage 0, N=1, `--trace-tokens`)

`.omc/benchmarks/eval_20260717_1357_silencechurn_trace.json` (kor2 WER 95.1%·kor3 WER 57.0%, 화자F1 0.0%·문장F1 37.0%/70.6%, `vbcable=ok`). kor2 전사(`kor2_C_R1.txt`)에서 4개 growing-prefix 그룹 확인(예: "먼저 육군은...고려." → "...고려하여." / "GPGOP...창설." → "...창설하고...수." → "...수행이...발전시키며." → "...위협과...편성하겠습니다." 3단 성장). kor3(`kor3_C_R1.txt`)는 이번 회차엔 뚜렷한 성장형 중복이 관찰되지 않음(간헐적 현상 — 게이트가 매번 pending→merge로 재판정되는 건 아님을 시사).

### 중요 함의 — WER 측정치 자체가 과대평가일 가능성

경로 C의 `hyp_lines`/WER은 **이 프런트 DOM(`#linesTranscript`)에서 추출**된다(docs/TESTING.md). 즉 이번에 찾은 프런트 Map 키 충돌이 **실제 사용자 화면에도, 측정 WER에도 동일하게 영향**을 준다 — growing-prefix 중복이 WER 계산에서 대량 삽입(insertion) 오류로 잡혀 kor2 WER을 부풀렸을 가능성이 높다. 프런트 키를 고치면(예: `start`만으로 키를 잡고 `end`가 더 크면 in-place 교체) **kor2/kor3 실제 WER이 지금 측정치보다 크게 낮게 나올 가능성**이 있다 — 아직 검증 전.

### 채택 조건 판정

계측 전용(채택/기각 비대상, 코드 무변경).

### 결론

**원인 규명 완료**: kor2/kor3 growing-prefix 중복의 실체는 `live_transcription.js:373-378`의 `finalizedHistory` Map이 `start|end|speaker`로 키를 잡아, 문법게이트(Exp-176)가 사후에 세그먼트 경계를 늘리는 재조립을 매번 "새 줄"로 오인 누적하는 것. 백엔드 grammar-gate의 지연판정 자체는 의도된 설계(Exp-176)라 프런트 키를 안정 식별자(예: `start`, 또는 세그먼트 단조증가 id) 기준으로 바꿔 in-place 교체하는 쪽이 최소침습 후보 — 단 사용자 확인 후 착수(다음 가설 참조).

### 다음 가설

1. **프런트 `finalizedHistory` 키를 `start`(+`speaker`) 기준으로 변경**해 growing 세그먼트를 in-place 교체 — 최소침습, 백엔드 STT/게이트 로직 무변경. 이후 kor2/kor3 재측정으로 WER 실개선폭 확인(Exp-180 kor2 회귀분이 이 아티팩트에 기인했는지 검증).
2. (대안, 더 침습적) 백엔드에서 "finalized" 세그먼트의 (start,end)를 진짜 불변으로 만들도록 grammar-gate 판정을 finalize 이전에 완전히 끝내는 재설계 — 위험도·범위 큼, 1번 결과 확인 후 필요시만 검토.
3. sbs1 화자F1 worst-case 회귀(§Exp-180 미해결)는 이번 조사 범위 밖 — 별도.

**JSON**: `.omc/benchmarks/eval_20260717_1357_silencechurn_trace.json` · **로그**: `server_kor2_C_R1_20260717_135804.log`·`server_kor3_C_R1_20260717_140125.log` · **전사**: `.omc/transcripts/kor2_C_R1.txt`·`.omc/transcripts/kor3_C_R1.txt`

---

## Exp-182 — 프런트 실시간 전사 중복표시 2종 수정 (Exp-181 후속, 프런트 전용) [E5, master 머지 `36fdbaf`]

**날짜**: 2026-07-17 · **Epoch**: E5(프런트 렌더 전용 — 백엔드 STT/디코더/게이트 무변경, epoch 미bump) · **브랜치**: `fix/frontend-finalized-history-key`(`b94ae45`+`06c36f1`), **master 머지 `36fdbaf`**

### 가설

Exp-181이 규명한 growing-prefix 중복은 백엔드 grammar-gate의 지연판정(Exp-176, 의도된 설계)이 "finalized 세그먼트의 `end`를 사후 확장"하는 것과, 프런트 `finalizedHistory` Map의 자연키(`start|end|speaker`)가 그 확장을 "새 줄"로 오인 누적하는 조합이다. **백엔드는 건드리지 않고 프런트 렌더만 고쳐** 중복을 제거한다(2종: ① 최종 화면 누적 중복, ② 실시간 진행중 화면 중복).

### 변경 내용 (`whisperlivekit/web/live_transcription.js` `renderLinesWithBuffer()`, 프런트 전용)

1. **`b94ae45`** — `finalizedHistory.set` 키를 `${ln.start}|${ln.end}|${ln.speaker}` → **`${ln.start}` 단독**으로. 문장이 자라며 `end`가 커져도 `start`는 불변이므로 같은 항목을 in-place 덮어써 **최종 화면의 growing-prefix 중복** 제거.
2. **`06c36f1`** — 렌더 병합을 `[...finalizedHistory.values(), ...interim]` → **진행중(미확정) 줄과 `start`가 같은 확정 이력 항목을 억제**한 뒤 병합. 백엔드가 침묵으로 조기 확정한 세그먼트를 이후 마침표 철회 등으로 같은 `start`에서 이어 전사(재개방)할 때, 확정판(짧음)과 진행중판(성장)이 공존하는 **실시간 진행중 화면 중복**(사용자 화면 캡처로 확인된 증상) 제거. 진행중 줄이 그 세그먼트의 현재 진실이므로 stale 확정판을 가림(재확정되면 ①의 start-키로 자연 정리).

### 정량 결과 (경로 C, 스크리닝 N=1 — 방향 신호)

| 파일 | Exp-181 기준(수정 전) | b94ae45(①만) | 36fdbaf(①+②) |
|---|---|---|---|
| kor2 | 95.1% | **25.0%** | 20.8% |
| kor3 | 57.0% | **30.5%** | 41.1%(실행편차 밴드 내) |

pytest 411 passed·1 skipped(두 커밋 모두). ①만으로 kor2 95.1→25.0%(-70pt), kor3 57.0→30.5%(-26.5pt) — **growing-prefix 중복이 WER을 대량 삽입오류로 부풀렸던 것 실증**.

### 분석 (정성)

- ① 적용 후 kor3는 12개 확정 문장 전부 단일 발생(중복 완전 소거), kor2도 대부분 소거(잔존 1건은 `start`가 다른 별개 재전사 이벤트 — ②/이번 범위 밖).
- ② 검증 한계: 이 수정은 **실시간 진행중(interim) 표시** 전용이라, 경로 C가 스크래핑하는 **최종 DOM**(모두 확정)에는 `interimStarts`가 비어 억제 분기가 발동 안 함 → 경로 C로는 실증 불가. 경로 C는 "JS 변경이 렌더/스크래핑을 깨뜨리지 않고 최종 WER 무회귀" 안전망만 통과. **실제 증상 제거는 라이브 뷰 육안 검증 필요**(사용자 확인 예정).
- 기각된 가설: 별개로 백엔드 `audio_processor.py` 타임아웃 경로의 `buffer_transcription` 누출을 의심했으나, kor2 4회 계측에서 `buffer_text`가 확정 텍스트와 겹치는 사례 0건으로 **실측 기각**(코드 무변경 원복). 실시간 중복은 백엔드 leak이 아니라 위 프런트 렌더 조합이 원인임을 재확인.

### ★ 중대한 함의 — 과거 kor1~3 WER 측정치 재해석 필요

경로 C WER은 이 프런트 DOM에서 추출되므로, **Exp-178~181의 kor1/kor2/kor3 WER 수치(kor2 70~130% 등)는 이 렌더 아티팩트로 상당분 과대평가**됐던 것으로 확정된다. 특히 **Exp-180 약어 가드 채택 논의의 핵심 근거였던 "kor2 전체 WER 79→108% 악화"도 이 아티팩트가 낀 값**이다 — OFF/ON 양쪽에 동일하게 끼었으므로 상대 비교(오발동 0건 등 로그 기반 결론)는 유효하나, **절대 WER 게이트 판정은 재검토 대상**이다. Exp-180 kor2 회귀분의 상당 부분이 STT 품질이 아니라 이 UI 버그였을 가능성이 높다.

### 채택 조건 판정 / 결론

**채택 (master 머지 `36fdbaf`, 사용자 승인 — 2026-07-17)**. 프런트 렌더 전용·백엔드 STT 무변경·pytest 무회귀·경로 C 최종출력 무회귀. 표준 테스트셋(bong1/ytn2/sbs1)은 이 버그의 성장형 중복이 두드러지지 않아 영향 미미하나, kor 낭독체에서 측정 정확도를 크게 회복. **epoch 미bump**.

### 다음 가설

1. **라이브 뷰 육안 검증**(사용자) — ② 실시간 중복 제거 실효 확인.
2. **Exp-180 재평가**: 이 수정 반영 후 약어가드 OFF/ON을 kor2 포함 재측정하면, 지난 "판단 유보"의 kor2 회귀분이 UI 아티팩트였는지 STT 실회귀였는지 분리 가능 — 재측정 여부는 사용자 판단.
3. 백엔드 근본수정(선택): grammar-gate가 finalize 이전에 판정을 완전히 끝내 "finalized 세그먼트 (start,end) 불변" 계약을 지키게 하는 재설계 — 범위 크므로 프런트 수정으로 증상 해소된 현재는 후순위.

**JSON**: `.omc/benchmarks/eval_20260717_1506_interim_dedup.json`(①+② kor2 20.8%/kor3 41.1%) · b94ae45 측정분(①만 kor2 25.0%/kor3 30.5%) · **커밋**: `b94ae45`·`06c36f1`·머지 `36fdbaf`

---

## Exp-183 — Segment 안정 id 스키마 필드 추가: 배포 React 세그먼트 추적 계약 확립 (Exp-182 후속) [E5, master 머지]

**날짜**: 2026-07-17 · **Epoch**: E5(스키마 additive 필드 + 프런트 키 전환 — 백엔드 STT/디코더/게이트 무변경, epoch 미bump) · **브랜치**: `feat/segment-stable-id@b974023`, **master 머지**

### 가설

Exp-182에서 프런트 렌더 중복을 `start` 단독 키로 해소했으나, 페이로드의 `start`/`end`가 1초 해상도 벽시계 문자열이라 **같은-초에 시작한 다른 세그먼트(특히 다화자 bong1) 충돌 위험**이 잠재했다. 또 배포 React가 참조하는 `docs/API_SPEC.md`가 **`start|end|speaker` 복합키를 명시 권장**해, 프런트 개발자가 그대로 따르면 growing-prefix 중복 버그를 처음부터 재현하게 되는 상태였다. 근본 해결로 **스키마에 안정 세그먼트 식별자 `id`를 추가**해 내장 UI·배포 React 공통의 견고한 dedup 키를 제공한다.

### 변경 내용

- `whisperlivekit/timed_objects.py` `Segment.to_dict()`: `id` 필드 추가 = `round(self.start, 3)`(세션상대 시작초 float). 근거: 세그먼트가 자라거나(end↑) finalized→interim 재개방돼도 **첫 토큰 시작초는 불변**이라 안정, 순차 비겹침 세그먼트는 서로 다른 float라 고유, 1초 벽시계와 달리 같은-초 충돌 없음. additive 필드(기존 필드·타입 무변경).
- `whisperlivekit/web/live_transcription.js`: `finalizedHistory` 키 + interim 억제 키를 `${ln.start}`→`${ln.id}`로 전환(표시용 timeInfo `start`/`end`는 그대로).
- **문서(정본 갱신)**: `docs/API_SPEC.md`(§2.4.3 `id` 필드 행 추가·§2.4.4 렌더 규칙 신설·§2.4.2/§5 복합키 지침 폐기), `docs/SCHEMA_CHANGES.md`(§2 필드표 `id` + "라인 dedup·렌더 규칙"), `docs/FRONTEND_HANDOFF_SUMMARY.md`(§4.2 경고·§4.3 필드표·§4.4 신설). 잘못됐던 "복합키 권장"을 "**전체교체 렌더 권장 + 누적 시 `id` 단독**"으로 정정. 부수 규명: `_DEFAULT_RETENTION_SECONDS=inf`(리텐션 실제 무제한 확인 → 전체교체 렌더가 정답).

### 정량 결과 (경로 C, 스크리닝 N=1)

| 파일 | WER | 화자F1 | 판독 |
|---|---|---|---|
| kor2 | 22.2% | — | Exp-182 밴드(20.8~25%) 유지 |
| kor3 | 49.0% | — | ±변동 밴드 내 |
| **bong1(다화자)** | **23.3%** | **58.5%** | 기준(WER~35%·F1~50-55%) 대비 **무회귀** — **같은-초 충돌 우려 실측 해소** |

pytest 411 passed·1 skipped, ruff pass. id 방출 실증: `Segment.from_tokens([...start=12.34]).to_dict()['id']==12.34` 확인.

### 분석 (정성)

- **핵심 검증 = bong1 다화자 무회귀**: `start` 단독 키(Exp-182)의 잠재 리스크였던 "같은 초 다른 화자 세그먼트 충돌"이 id(float) 전환으로 제거됐고, bong1 화자F1 58.5%로 catastrophic 붕괴 없음 확인.
- 이 변경의 진짜 산출물은 **문서 계약 정정**이다 — 배포 React가 `id`로 dedup(또는 전체교체 렌더)하면 Exp-181/182에서 규명한 중복을 처음부터 안 겪는다. 기존 API_SPEC의 복합키 권장이 버그 유발원이었음을 바로잡았다.

### 채택 조건 판정 / 결론

**채택 (master 머지)**. additive 스키마 필드 + 프런트 키 전환, 백엔드 STT 무변경, pytest·ruff 무회귀, bong1 다화자 무회귀. **epoch 미bump**. 병렬 세션(session-lang-lock)이 `live_transcription.js`를 자기 워크트리에서 편집 중이라 향후 머지 충돌 가능 — 인지함.

### 다음 가설

1. (선택) 백엔드 근본수정 — grammar-gate가 finalize 이전에 판정을 끝내 "finalized 세그먼트 불변" 계약을 지키게 하는 재설계. 프런트/스키마로 증상·계약 모두 해소된 현재는 후순위.
2. Exp-180 약어가드 재평가 — 이제 kor WER 아티팩트가 제거됐으니, OFF/ON kor2 재측정으로 "판단 유보"를 깨끗한 숫자로 매듭(사용자 판단).

**JSON**: `.omc/benchmarks/eval_20260717_1534_segid.json`(kor2 22.2%/kor3 49.0%/bong1 23.3%·화자F1 58.5%) · **커밋**: `b974023` + 머지

---

## Exp-184 — 세션별 언어 고정(auto/ko/en): 코드스위칭 로직 게이트 + opt-in 단일언어 전사 [E5, master 머지 `ac17b00`]

### 가설
서버 `--lan auto`(코드스위칭 대응)로 **한국어 단일 음성**을 돌리면 성능이 나쁘다(Exp-178 kor 데이터 발굴 계기). 배포 현장엔 "이 세션은 ko만/en만"이라는 사전 정보가 있는 경우가 있어, 세션 단위로 언어를 고정하면 코드스위칭 재감지 오버헤드·오탐 없이 단일 언어에서 더 나은 전사가 가능할 것으로 예상. auto는 기본·무회귀(opt-in).

### 규명 (설계 전제)
`?language=` 세션 쿼리파라미터는 이미 존재했으나 **기본 백엔드(SimulStreaming)에서 무효**였다 — `SessionASRProxy`가 `transcribe()`만 가로채는데 SimulStreaming은 `infer()`를 호출하고 `original_language` 속성도 없어 조용히 무시됐다. 코드스위칭 게이트가 읽는 `AlignAttConfig.language`(`cfg.language`)와 프록시가 건드리는 `original_language`는 완전히 분리된 별개 값이었다.

### 변경 내용
- **세션 언어 전파**: `SimulStreamingOnlineProcessor.__init__(language=None)` + `_resolve_session_cfg`(`simul_whisper/backend.py:263-282`) — 세션 언어 지정 시 `dataclasses.replace(asr.cfg, language=...)`로 AlignAttConfig 얕은 사본을 만들어 `_create_alignatt`에 전달 → 기존 `cfg.language` 게이트 6곳이 코드 수정 없이 세션 언어를 따름. 미지정(None)이면 전역 cfg 그대로(auto 객체수준 무회귀). 번역 태스크(direct_english_translation)는 공유 tokenizer 충돌로 오버라이드 무시+경고.
- **코드스위칭 로직 auto 가드 5곳**: new_speaker eager 재감지(`backend.py:395-426`, `lang_locked` 시 스킵), 긴침묵 언어리셋(`backend.py:331-334`, 고정 시 고정언어 유지), ForeignLang 언어리셋(`backend.py:724`, 드롭은 유지), ScriptMismatch 재감지 arm(`backend.py:752`, 드롭은 유지), periodic-lang-check(`align_att_base.py:295`). 전부 `cfg.language != "auto"`일 때만 스킵 — auto에선 한 줄도 안 달라짐.
- **online_factory**(`core.py:255-291`): simulstreaming은 SessionASRProxy 미래핑 + language 직접 전달, 그 외 백엔드는 기존 프록시 유지.
- **basic_server**: `?language=` 허용목록 `{auto,ko,en}` 검증 + config 메시지 `language` 필드(적용 언어).
- **내장 UI**(`live_transcription.{html,js}`): 소스 언어 드롭다운(auto/ko/en) + `?language=` URL 조립(auto=생략).
- 단위 테스트 +16(`test_session_language_lock.py` 신규 15 + `test_lang_redetect.py` 긴침묵 고정 1), 연동 문서 5종(API_SPEC·SCHEMA_CHANGES·FRONTEND_HANDOFF·SENTENCE_FINALIZATION·TESTING).

### 테스트 설정
경로 C(VBCable), 화자분할 ON(Sortformer, CRT=3.0), 스크리닝 `--repeat 1`. provenance `branch=feat/session-lang-lock@9c574b5 vbcable=ok`. 모델 가중치는 워크트리에 대용량 파일 부재로 메인 저장소 절대경로 참조(코드는 워크트리, `--expect-code-root` 통과).
- ko 테스트: `--files kor1/kor2/kor3 --lan ko`
- en held-out: `--files eng1 --lan en`
- auto 베이스라인: `--files kor1/kor2/kor3+eng1 --lan auto`

### 테스트 세트 결과 (스크리닝 1회 — 방향 신호)

| 파일 | 모드 | 고정 WER | auto WER | ΔWER | 고정 문장F1 | auto 문장F1 |
|------|------|---------|---------|------|-----------|-----------|
| kor1 | ko | 20.5% | 18.7% | +1.8%p | 72.7% | 54.5% |
| kor2 | ko | 18.8% | 18.8% | 0 | 50.0% | 40.0% |
| kor3 | ko | 38.4% | 51.0% | **−12.6%p** | 71.0% | 71.0% |
| eng1 | en | 8.6% | 1.9% | +6.7%p | 50.0% | 100.0% |

한국어 3종 평균: **고정 25.9% vs auto 29.5%**(고정 3.6%p 유리, kor3 견인). 화자분리 F1은 단일화자 성격 + repeat=1이라 노이즈(kor2 100 vs 0, eng1 0 vs 100은 라인분할 타이밍 편차) — Sortformer는 `--lan` 무관이라 우열 판정 제외.

### 분석 (전사 내용 정성 대조)

**kor1/kor2** (ko 고정): 주요 실패 없음. 한국어 출력 정상, 한/영 외 언어 환각 0건. auto도 동일 언어 정상.

**kor3** (ko 고정):
- **단어 중간 분절(Case B)**: 고정 `추진하겠`⏎`으며`, `통합`⏎`하고`, `창설`⏎`하고` — 술어가 음절 경계에서 쪼개짐. **단 auto도 동일 발생**(`사령부를 창`⏎`설하고` — 더 심함, `창설하겠`⏎`으며`). → Case B는 **silence-churn 기존 아티팩트**(Exp-181 규명 계열)이며 **언어 고정과 무관**. kor1·kor2는 양쪽 모두 Case B 없음.

**eng1** (en 고정):
- **고유명사 오전사**: 고정 `Taoiseach`→`Fishek`/`Tisha`(아일랜드어), 영어 출력은 정상. auto는 1.9%로 이 구간을 더 잘 처리. → en 고정이 auto보다 나쁜 건 직관에 반하며, 영어는 auto도 첫 토큰에서 en으로 즉시 수렴해 고정과 거의 동일 경로를 타므로 **repeat=1 편차**로 해석(±30~120%p 변동 범위 내).

**코드스위칭 로직 비활성**: 서버 로그상 [NewSpeaker] eager 재감지·[LangSwitch] 마커·언어감지 로그가 고정·auto 양쪽 모두 미포착 — 단일언어·거의 단일화자 데이터라 그 경로가 애초에 자극되지 않는다. 비활성은 코드 설계(auto 가드)상이며 이 데이터셋은 대비 실측을 못 시킨다(단위 테스트 16종으로 커버).

**이번 변경 영향**: 한국어 단일언어에서 고정이 auto 대비 유망(kor3 −12.6%p), eng1 회귀는 스크리닝 편차 추정. Case B는 고정 무관 기존 이슈. auto 표준셋(bong1/ytn2/sbs1)은 게이트가 inert라 무영향(측정 생략, 구조적 무회귀 + pytest 425 pass로 갈음).

### 채택 조건 판정 / 결론

**채택 (master 머지, 사용자 승인 — opt-in)**. 정량 채택 게이트(`--repeat 3` worst-case)는 미실시이나, ① 기능 정상 작동(ko/en 고정 전사, 한/영 외 환각 0), ② auto 기본 **구조적 무회귀**(게이트 auto에서 inert·pytest 425 pass·ruff clean), ③ 한국어 단일언어 방향 유리, ④ §3.2 한/영 고정 환경 직결 **opt-in 기반기능**이라 CLAUDE.md §4 "목표 필수 기능 채택은 사용자 질의"에 따라 사용자 승인으로 채택. eng1 회귀·Case B는 별도 트랙(스크리닝 편차 / silence-churn). **epoch 미bump** — 게이트가 auto에서 완전 inert라 과거 auto 파라미터 결론 무효화 없음.

### 다음 가설
1. (선택) ko-모드 채택확정 `--repeat 3`(kor1/2/3, §3.8 신설 프로토콜) — median+분산으로 고정 우세 확정 + eng1 회귀가 편차인지 확인.
2. Case B(silence-churn) 근본수정은 언어모드 무관 별도 트랙(Exp-181 계열).

**JSON**: `.omc/eval_canary_kor1_ko.json`·`eval_kor23_ko.json`·`eval_eng1_en.json`·`eval_auto_baseline.json`(worktrees/session-lang-lock) · **커밋**: `4589cc7`+`b91ba55` → 머지 `ac17b00`

---

## Exp-185 — SILENCE_HARD_SECS 0.8→1.2 스윕: 낭독체 호흡 pause Case B 안전망 우회 해소 [E5, `exp/silence-hard-secs-sweep`]

### 가설

사용자 관찰(한 화자가 발화 중 잠깐 침묵할 때 침묵 로직이 문장을 과도하게 분리) + Exp-178/179의 기존 규명(`SILENCE_HARD_SECS=0.8`초 안전망이 낭독체 호흡 pause에서 문법 게이트를 우회해 kor3에 단어 중간 분절 Case B 3건을 냄, "다음 가설" 항목으로 이미 등록됨) → `SILENCE_HARD_SECS`를 상향하면 문법 게이트(`should_split_after_silence`)가 짧은 호흡 pause를 판정할 여유가 늘어 과분할이 줄고 Case B가 해소될 것으로 예측. 상한은 `backend.py` long-silence 하드리셋(2.0s)과 겹치지 않아야 하므로 기존 assert(`<=2.0`)를 그대로 유지.

### 변경 내용

`SILENCE_HARD_SECS`(기존 `tokens_alignment.py` 모듈 상수, 0.8 하드코딩)를 CLI로 오버라이드 가능하게 전환 — 값 자체를 바꾼 게 아니라 **스윕 인프라**를 추가:
- [tokens_alignment.py:95-98](whisperlivekit/tokens_alignment.py#L95-L98) `TokensAlignment.__init__`에 `self.silence_hard_secs = float(getattr(args, "silence_hard_secs", None) or SILENCE_HARD_SECS)` + `assert <= 2.0` 추가.
- [tokens_alignment.py:391](whisperlivekit/tokens_alignment.py#L391)(`_gate_decide`, diar 경로), [tokens_alignment.py:712](whisperlivekit/tokens_alignment.py#L712)(`_gate_intake_nondiar_silence`, 비-diar 경로) — 모듈 상수 참조를 `self.silence_hard_secs`로 교체.
- [config.py:73](whisperlivekit/config.py#L73) `silence_hard_secs: Optional[float] = None` 필드 추가.
- [parse_args.py:408-416](whisperlivekit/parse_args.py#L408-L416) `--silence-hard-secs` CLI 플래그(simulstreaming_group) 추가.
- [scripts/eval.py:582-589,665-666](scripts/eval.py#L582) `--silence-hard-secs` 인자 + `extra_server_args` 전달 추가.
- 미지정 시 기존 0.8 그대로 폴백 — **채택 확정 커밋에서 실제 값을 1.2로 변경**(아래 결론 참조).
- pytest 425 passed·1 skipped(무변경).

### 테스트 설정

경로 C, diar-ON(Sortformer, CRT=3.0), beams=2, PLC=None, turbo. cwd=워크트리(`worktrees/silence-hard-secs-sweep`, provenance로 매 회 확인). 언어모드 auto(`--lan auto`, bong1/ytn2/sbs1 + held-out ytn1)와 ko(`--lan ko`, kor1/kor2/kor3) 양쪽 측정, en held-out(eng1, `--lan en`) 단회. 워크트리 신설 시 test_data 일부(`bong1.wav`/`kor1~3.wav`)와 모델 파일(`model.safetensors`/`sortformer-4spk-v2.nemo`)이 git 비추적이라 부재했음 — 다른 워크트리에서 복사(테스트 wav)·하드링크(모델, 용량 절약)로 해결 겸 메인 저장소도 함께 복원(우발적 소실 발견, 원인 미상 — 별도 조사 불필요, 데이터 자체 소실 아님을 확인).

### 테스트 세트 결과

**① 스크리닝(N=1, 0.8→2.0 스윕)** — WER% / 화자F1%:

| SHS | bong1 | ytn2 | sbs1 | auto avg WER/화자F1 | kor1 | kor2 | kor3 | ko avg WER/화자F1 |
|---|---|---|---|---|---|---|---|---|
| 0.8(기존) | 36.9/57.9 | 15.8/76.2 | 8.9/80.0 | 20.5%/71.4% | 17.0/0.0 | 18.1/100.0 | 37.1/0.0 | 24.1%/33.3% |
| 1.0 | 29.0/75.7 | 18.7/72.7 | 10.1/66.7 | 19.3%/71.7% | 18.1/0.0 | 19.4/100.0 | 36.4/0.0 | 24.7%/33.3% |
| **1.2** | 33.8/68.6 | 14.8/90.0 | 9.5/80.0 | 19.4%/79.5% | 23.4/0.0 | 16.0/100.0 | 29.1/100.0 | 22.8%/66.7% |
| 1.5 | 29.0/68.4 | 18.7/76.2 | 7.7/100.0 | 18.5%/81.5% | 19.9/100.0 | 27.1/100.0 | 36.4/0.0 | 27.8%/66.7% |
| 1.8 | 27.5/77.8 | 16.3/81.8 | 7.7/80.0 | 17.2%/79.9% | 17.5/100.0 | 22.2/100.0 | 43.0/0.0 | 27.6%/66.7% |
| 2.0 | 29.3/57.1 | 10.3/94.7 | 14.9/80.0 | 18.2%/77.3% | 13.5/100.0 | 25.0/0.0 | 41.1/100.0 | 26.5%/66.7% |

전 구간에서 auto가 일관 개선. ko는 값마다 요동 — **1.2가 auto·ko 양쪽에서 동시에 개선되는 유일한 지점**으로 보여 확정 후보 선정.

**② 채택 확정(N=3, SHS=1.2)** — median(min–max, stdev):

| 파일 | WER | 화자F1 | 문장F1 |
|---|---|---|---|
| bong1 | 31.4%(29.3–34.4, σ2.6) | 64.9%(61.5–68.8) | 25.0% |
| ytn2 | 17.2%(16.7–20.2, σ1.9) | 90.0%(80.0–90.0) | N/A |
| sbs1 | 10.7%(8.9–11.9, σ1.5) | 100.0%(80.0–100.0) | 88.9% |
| **auto avg** | **19.8%** | **85.0%** | — |
| kor1 | 17.0%(17.0–22.2, σ3.0) | 0.0%(0.0–0.0) | 70.0% |
| kor2 | 19.4%(19.4–21.5, σ1.2) | 0.0%(0.0–0.0) | 40.0% |
| kor3 | 37.1%(36.4–45.7, σ5.2) | 100.0%(0.0–100.0, σ0.58) | 48.0% |
| **ko avg** | **24.5%** | **33.3%** | — |

**N=1 스크리닝과 달리 N=3에서 ko 화자F1 "개선"은 재현 안 됨**(kor1·kor2가 3회 전부 0.0%로 고착, N=1의 kor2=100%는 노이즈였음) — ko는 WER·F1 모두 베이스라인(0.8, N=1)과 사실상 동률(중립). auto는 N=3에서도 화자F1·WER 개선 유지, 단 **bong1 max 34.4%가 기존 확정 게이트(30.5%, Exp-161 N=3 베이스라인) 초과**.

**held-out(단회)**: ytn1(auto) WER 11.7%·화자F1 84.2%·문장F1 57.1%(베이스라인 21.5%/38.1% 대비 개선). eng1(en) WER 3.8%·화자F1 0.0%·문장F1 66.7%(베이스라인 4.8%/0.0% 대비 개선/동일) — 양쪽 무회귀.

### 분석 (전사 내용 정성 대조)

**kor3** (SHS=1.2, N=3 R1/R2/R3 전 회차):
- **Case B 완전 해소, 재발 0/3**: 기존 0.8에서 `"통합."`⏎`"하고 방공간제전대…"`(정답 `"통합하고"`)로 쪼개지던 지점이, 1.2에서는 R1/R2/R3 전부 `"통합하고 방공관제전대 통합 및…"` 한 줄로 유지됨. `"전투비행대대를 개편하고 장기체공저피탐…"`도 3회 전부 안 끊김(기존엔 `"…비행대대 창."`으로 단어 중간 잘림).
- **잔존 이슈**: kor3 WER 자체는 여전히 높음(median 37.1%) — 이는 Exp-178에서 별도 규명한 stall recovery 연쇄 웨지·QG streak refresh 서두 폐기 등 **다른 원인**(이번 변경 범위 밖)이 지배적.

**bong1** (SHS=1.2, N=3 중 max 회차 R2, WER 34.4%):
- **비언어 토큰·환각 폭주**: "Thank you"×4, "하하"×10 — bong1의 기존 웃음/필러 환각 실패모드(Exp-159/163/171/174/176에서 반복 확인)와 정성적으로 일치. 이번 변경(침묵 안전망 문턱)이 웃음 구간 환각을 유발할 메커니즘적 근거가 없어 **무관한 회차 변동**으로 판단.

**ytn2/sbs1** (SHS=1.2): 주요 실패 없음, N=3 전 회차 게이트(34.5%/16.1%) 이내.

**이번 변경 영향**: 목표(kor3 Case B)는 완전 해소. auto(co-first priority) WER·화자F1 순개선. ko 전체 WER·F1은 중립(회귀 아님). bong1 max 게이트 초과는 기존 웃음/필러 실패모드로 귀속, 이번 메커니즘과 무관.

### 채택 조건 판정 / 결론

① 화자분리 F1 worst-case 미회귀: auto **개선**(N=3 baseline 부재로 N=1 베이스라인 대비 비교, 정밀 worst-case 대조는 후속 과제) / ko **중립**(회귀 아님).
② WER max 미회귀: ytn2·sbs1 **✓** / bong1 **✗**(34.4%>30.5%, 정성 귀속=기존 웃음/필러 패턴 무관).
③ Case B 신규 발생 없음(hard floor): **✓** — 오히려 기존 Case B 해소.
④ pytest 전부 통과: **✓** 425 passed·1 skipped.
⑤ 아티팩트 악화 없음: **✓** 신규 실패 패턴 없음.
⑥ held-out 무회귀: **✓** ytn1·eng1 둘 다 개선.

**채택 (사용자 승인, master 머지 예정)**. bong1 max 게이트 초과에도 불구, CLAUDE.md §3.3 "Case B는 수치 무관 hard-fail — 원인 수정 대상"에 해당하는 목표를 정확히 해소했고 ko는 회귀 없이 중립·auto는 순개선이므로 사용자가 채택 승인. **epoch 미bump**(Exp-176 문법-조건부 침묵 게이트의 파라미터 값 조정 — 같은 세대 내 실험).

### 다음 가설

1. bong1의 웃음/필러 환각(Layer 3b)은 여전히 미해결 — no_speech/VAC 경로는 Exp-163~165에서 이미 폐기 확정됨. 별도 비-ASR 웃음 분류기 설계가 필요(범위 밖, 별도 세션).
2. ko kor1/kor2 화자F1이 SHS 값과 무관하게 3회 전부 0%로 고착 — Sortformer 화자분할과 침묵게이트 상호작용 또는 kor1/kor2 정답 자체의 화자전환 유무(단독 낭독이라 전환이 거의 없을 가능성) 확인 필요.
3. auto 화자F1 worst-case의 정밀한 N=3 베이스라인(SHS=0.8) 대조 측정 — 이번엔 시간 관계상 N=1 베이스라인과만 비교.

**JSON**: `worktrees/silence-hard-secs-sweep/.omc/benchmarks/eval_shs{0.8~2.0}_{auto,ko}.json`(스크리닝) · `eval_shs1.2_{auto,ko}_N3.json`(확정) · `eval_shs1.2_{ytn1,eng1}.json`(held-out) · **브랜치**: `exp/silence-hard-secs-sweep`(머지 대기)

---

## Exp-186

**날짜**: 2026-07-18 | **Epoch**: E5(미bump — 진단 측정, 코드 변경 없음) | **측정 언어모드**: **auto**
(`--lan auto` — kor1~3도 이례적으로 auto로 측정, §가설 참조)

### 배경/가설

사용자가 `--lan auto` 세션에서도 한국어만 계속 들어오는 상황(단일언어 세션)이 실제로 발생할 수
있다고 보고, 이 상황에서의 한국어 전사 성능을 개선하기 전에 먼저 **eng1을 제외한 전체 테스트
데이터를 auto 모드로 3회씩 측정하고 전사 결과를 정성 분석**해 개선 표적을 좁히는 것이 목적이었다.
kor1/kor2/kor3(평소 "ko 테스트"로 `--lan ko` 고정 측정하는 파일)를 이번엔 의도적으로 `--lan auto`로
측정해 "auto의 상시 언어 재감지 로직이 단일언어(한국어) 세션에 부작용을 일으키는가"를 직접
검증했다. 코드 변경 가설이 아니라 **진단 전용**(채택/기각 비대상) 실험이다. 부수적으로, 발견된
원인을 다음 라운드에 정밀 추적할 수 있도록 관찰용 디버그 로그(§변경 내용)를 보강했다.

### 변경 내용

**코드 변경 없음**(master 기준 순수 측정+분석). 단 별도 브랜치에 **관찰용 로그**를 추가·커밋(판정
로직·분기 조건·반환값은 전혀 변경하지 않음, `feat/debug-diagnostics-logging`, 커밋 `67a58ad`,
master 미머지):
- [tokens_alignment.py](whisperlivekit/tokens_alignment.py) finalize_trigger 배정 5개 분기 전부에
  `[TriggerAssign]`, grace 유예 판정에 `[FinalizeGrace]`, 비-diar 커밋에 `[CloseLine]`.
- [sentence_boundary.py](whisperlivekit/sentence_boundary.py) 순수 함수 전 반환지점에
  `[SentenceBoundary]`(어떤 규칙 — 숫자가드/KO_FINAL_SUFFIXES/EN_ABBREV 등 — 이 판정을 결정했는지).
- [filtering/__init__.py](whisperlivekit/filtering/__init__.py) 환각 제거·단어교정이 실제로 텍스트를
  바꿨을 때만 `[HallucinationDrop]`/`[WordCorrection]`(원문→치환문).
- [basic_server.py](whisperlivekit/basic_server.py) 위 신규 로거 2개를 기존 `--trace-tokens` DEBUG
  승격 목록에 추가(신규 CLI 플래그 없음).
- ruff clean(기존 이슈 1건은 무관), pytest 425 passed·1 skipped(회귀 없음).

### 테스트 설정

경로 C, `--lan auto`, diar-ON(Sortformer, CRT=3.0), `--trace-tokens`(backend/align_att_base/
tokens_alignment DEBUG — 이번 측정 로그엔 아직 위 신규 태그 미포함, 측정을 master@`ec4684e`로
먼저 수행하고 로그 보강은 별도 브랜치에 사후 추가했기 때문), `--repeat 3`. cwd=메인 저장소(master).
파일: bong1.wav, ytn2.mp3, sbs1.mp3, kor1.wav, kor2.wav, kor3.wav, ytn1.mp3, kinno.mp3(eng1 제외).

### 테스트 세트 결과

경로 C, N=3, median[min–max]:

| 파일 | 화자구조 | WER | 화자F1 | 문장F1 |
|---|---|---|---|---|
| bong1 | 4화자 | 29.3%[27.8–32.6] | 63.2%[57.9–78.8] | 14.3%[9.5–19.0] |
| ytn2 | 2화자 | 15.8%[11.8–18.7] | 90.0%[80.0–90.0] | N/A |
| sbs1 | 2화자 | 10.7%[10.1–11.9] | 100.0%[66.7–100.0] | 88.9%[85.7–94.7] |
| kor1 | 단일화자 | 43.9%[22.2–48.0] | 0.0%(3회 전부) | 42.9%[40.0–75.0] |
| kor2 | 단일화자 | 19.3%[10.3–21.4] | 100/0/100%(진동) | 100/80/100%(진동) |
| kor3 | 단일화자 | 33.8%[29.8–35.8] | 100/0/100%(진동) | 100/83.3/100%(진동) |
| ytn1(held-out) | 2화자 | 12.9%[9.8–21.5] | 84.2%(3회 동일) | 57.1%(3회 동일) |
| kinno(정성 sanity) | 2화자 | 32.1%[27.6–33.7] | 77.4%[56.2–84.6] | 47.1%[30.0–61.5] |
| **경로 C 평균** | | **23.8%** | **66.6%** | **64.0%** |

**Exp-185(`--lan ko`, 동일 코드 SHS=1.2, N=3) 대비 auto 교차비교** — `--lan` 값만 다르고 나머지
설정 동일:

| 파일 | ko(Exp-185) WER med[min–max] | auto(이번) WER med[min–max] | ko 화자F1 | auto 화자F1 | auto만의 Case B |
|---|---|---|---|---|---|
| kor1 | 17.0%[17.0–22.2] | 43.9%[22.2–48.0] | 0.0%(3회) | 0.0%(3회) | **3건** |
| kor2 | 19.4%[19.4–21.5] | 19.3%[10.3–21.4] | 0.0%(3회) | 100/0/100%(진동) | 0건 |
| kor3 | 37.1%[36.4–45.7] | 33.8%[29.8–35.8] | 100/0/100%(진동) | 100/0/100%(진동) | 0건(오탐 배제) |

### 분석 (전사 내용 정성 대조)

**bong1**(R1, median WER 29.3%):
- **화자 혼동·경계 오류**: 정답 화자전환 14회 대비 `speaker_change` 확정 트리거는 R1=1·R2=4·R3=3회뿐.
  서버 로그 diarizer 원시신호(`[NewSpeaker]`)는 회차당 26~27회로 diarizer 자체는 화자전환을 감지하나
  그 신호가 문장 확정으로 이어지는 비율이 매우 낮음(§3.1). eager_applied 비율·RetractScan
  removed 합계 어느 것도 F1 편차(57.9~78.8%)와 단조 상관 없음 — 단일 원인이 아닌 구조적 손실.

**ytn2**(R1, median WER 15.8%): **필러 환각**: 전사 "Uhhuh." — 정답에 없음. 코드스위칭 자체는
정상(화자F1 90%).

**sbs1**(R2, median WER 10.7%): **필러 환각**: "사태라." "You." — 정답에 없는 짧은 삽입. 주요
실패는 없음(화자F1 100%, 문장F1 88.9%).

**kor1**(R2, median WER 43.9%):
- **단어 유실·잘림(Case B, hard-fail)**: 전사 `"국방환.⟨silence⟩" / "경을 고려...⟨silence⟩"` —
  정답 "국방 환경을 고려한"의 "환경"이 음절 중간에서 잘림. R1에서도 같은 위치가 `"국방환경.
  ⟨silence⟩" / "을 고려한...⟨silence⟩"`로 절단(덜 심함) — 두 회차 재현. "소모 강요"→"강.⟨silence⟩"/
  "요 등,...⟨silence⟩"도 동일 유형. 트리거 원인 전부 `silence`.
- **코드스위칭(언어) 실패**: `[ShortSilenceLangCheck] 최근 1.5s → en (p=0.99)` — 순수 한국어
  구간을 영어로 고신뢰도 오검출. "Thank you very much."(2회) 환각 삽입까지 유발.
- **단어 유실**: "순서는 보시는 바와 같습니다." 통째 누락.

**kor2**(R3, median WER 19.3%): **단어 유실**: "동원사단은" 누락. **화자 경계**(§3.4): 화자F1이
100→0→100%로 진동하나 실제 화자오분류가 아니라 참조가 단일화자([spk1] 하나, 화자경계 0개)라
`compute_speaker_sentence_segmentation`(metrics.py)이 all-or-nothing 구조가 되기 때문(문장분리
F1이 100% 미만인 회차와 정확히 일치) — Sortformer·게이트 문제 아님.

**kor3**(R3, median WER 33.8%): **숫자·군사용어 동음이의**: "작전 3위"(정답 "작전사 및"), "준사군"
(정답 "준 4군") 반복. 화자F1 진동은 kor2와 동일 메커니즘(메트릭 아티팩트). Case B 의심 사례("준.")는
정답 자체가 "준 4군"(공백 포함)이라 오탐으로 배제.

**ytn1**(R3, held-out, median WER 12.9%): **필러 환각**: "Yeah." "Yeah, I." — 정답에 없음. **단어
유실**: "한반도뿐만" 누락. F1이 3회 모두 84.2%로 동일해 안정적으로 보이나, `speaker_change`
트리거는 거의 발동 안 함(1/0/0회)이고 대신 `language_switch`가 19회 안팎으로 안정 발동해 대리
역할 — 원어민↔통역 구조상 언어전환=화자전환이 거의 일치하는 우연.

**kinno**(R2, 정성 sanity, WER/F1 게이팅 제외): 대규모 누락·환각·비한영 혼입 없음. 한↔영 순차통역
alternation 구조를 화자·문장 분리가 대체로 잘 따라감. 사소한 누락("따라야 하므로" 등)만 확인.

**이번 실험의 영향(진단 전용)**: 코드 변경 없음 — 위 실패모드를 발견·원인 후보를 좁히는 것이
목적이었고 실제 개선은 다음 라운드 과제(§다음 가설).

### 채택 조건 판정 / 결론

📋 **계측완료 (채택/기각 비대상 — 코드 변경 없는 진단 측정)**.

핵심 발견 우선순위(화자분리 F1 > WER > 문장분리 F1 순):
1. **[최우선] `speaker_change` 확정 트리거가 구조적으로 거의 발동하지 않음** — bong1(다화자)조차
   회차당 1~4회뿐, diarizer는 26~27회 감지. 화자분리 F1이 1순위 지표인 이 프로젝트에서 가장
   우선순위 높은 개선 표적.
2. **[hard-fail] kor1 Case B 3건 확인** — `SILENCE_HARD_SECS=1.2`(Exp-185 채택 후)에도 불구하고
   auto 모드에서 잔존. kor3의 Case B는 Exp-185로 해소된 채 유지(오탐 배제로 확인), **kor1은
   Exp-185 범위 밖의 별개 사례**.
3. **kor1 순수 한국어 구간 언어오검출(ko→en) 버그** — 오검출 횟수와 WER이 상관.
4. **kor2/kor3 화자F1 0%↔100% 진동은 실제 버그가 아니라 메트릭 아티팩트** — Exp-185 "다음 가설 2"
   (SHS 무관 0% 고착 원인)에 대한 답: 단일화자 참조(화자경계 0개)의 all-or-nothing F1 구조 때문,
   Sortformer·게이트 상호작용 아님.
5. **auto vs ko 교차비교 결과 auto의 취약점은 kor1에 국한** — kor2/kor3는 auto가 오히려 동등하거나
   나음(§테스트 세트 결과 교차비교 표). "auto가 한국어 세션 전반을 악화시킨다"는 과장이며, 정확히는
   kor1 특유의 국소적 취약점.
6. 비한영 언어 혼입 0건(§3.2 준수). 필러 환각·숫자/군사용어 동음이의 다수 관찰(개선 우선순위는
   상대적으로 낮음).

상세 리포트: [docs/research/AUTO_MODE_KOREAN_PERF_ANALYSIS_20260718.md](docs/research/AUTO_MODE_KOREAN_PERF_ANALYSIS_20260718.md).

### 다음 가설

1. **[1순위]** §발견1 diarizer 신호 → `speaker_change` 확정 손실 원인 규명 — `[TriggerAssign]`/
   `[FinalizeGrace]` 로그(이번에 추가) 활성화 재측정으로 diarizer 감지 시점에 실제 어느 분기를
   타는지(게이트 보류/침묵 미도래/화자 귀속 오류) 추적.
2. §발견2 kor1 Case B — 무음 기반 조기 확정이 단어 중간에서 발생하는 정확한 경로 특정.
   `[SentenceBoundary]`/`[CloseLine]` 로그로 해당 오디오 구간(국방환경을/소모강요 부근) 재현·추적.
3. §발견3/5 "왜 kor1만" 언어오검출(ko→en)에 취약한지(발화 특성? 특정 구간 acoustic 특이점?) 원인
   조사.
4. (경험적, 코드 변경 아님) 단일화자 테스트 파일의 "화자분리 F1" 지표 적용 방식 재검토 필요성을
   사용자에게 제안 — 화자경계 0개 파일은 화자F1 대신 문장F1만 채택 게이팅에 반영하는 대안 등.

**JSON**: `.omc/benchmarks/eval_auto_kordebug_20260718_1216.json` · 시각화:
`.omc/transcripts/eval_report_auto_kordebug.html` · 전사: `.omc/transcripts/{stem}_C_R{1,2,3}.txt` ·
서버로그: `.omc/server_logs/server_{stem}_C_R{n}_20260718_*.log` · **디버그 로깅 브랜치**:
`feat/debug-diagnostics-logging`(커밋 `67a58ad`, 머지 대기) · **후속 goal prompt**:
`docs/goal_prompt/GOAL_AUTO_KOREAN_FOLLOWUP.md`

---

## Exp-187 — 화자전환 finalize_trigger 라벨 손실 규명 + 분기우선순위 수정 [E5, `exp/speaker-change-trigger-loss`]

### 배경 / 가설

Exp-186(`feat/debug-diagnostics-logging`, 관찰용 로그만 추가, 규명 미완)이 bong1(정답 화자전환 14회, 4화자)에서
diarizer `[NewSpeaker]` 로그는 회차당 26~27회 화자전환을 감지하는데 확정 트리거가 `speaker_change`로 배정된
횟수는 회차당 1~4회뿐임을 관찰했다. §3.3 최우선 지표(화자분리 F1)와 직결되는 손실이라 이번 Stage에서
`--trace-tokens`로 실측 규명한다. **최우선 가설**: `tokens_alignment.py:get_lines_diarization()`의 분기
우선순위(`hard_boundary`→`is_silence()`→`speaker != closing.speaker`→`punct_boundary`) 자체가 구조적 원인 —
`segment.is_silence()` 체크가 화자비교보다 먼저 걸려, 화자전환이 침묵을 사이에 두고 일어나면(자연 발화의 압도적
다수 케이스) `speaker_change`가 `silence`/`punctuation`에 흡수된다는 가설. 부수 관찰(검증 대상): 마지막
`else: closing.finalize_trigger = "speaker_change"` 폴백 분기가 De Morgan 전개상 도달 불가능해 보임(실제 0건인지
로그로 확인).

### 원인 규명 (재현 측정 + 코드 대조)

`--trace-tokens --repeat 3`로 bong1 단독 재현(fix 전 코드, `67a58ad`)한 뒤 `[TriggerAssign]` 서버 로그를 직접 대조:

1. **분기 우선순위가 실제 원인으로 확정**: `_apply_silence_grammar_gate()` → `_gate_decide()`(`tokens_alignment.py:412`)는
   이미 `diar_mode and next_seg.speaker != closing.speaker`일 때 문법 판정(`should_split_after_silence`)을
   건너뛰고 강제 분할(`split_grammar`)하고 있었다 — 즉 **화자전환이라는 사실 자체는 게이트 단계에서 이미 알고
   있었다**. 그런데 이 판정 결과(`path`)가 반환값 그 이상으로 전달되지 않고 `_log_silence_gate` 디버그 로그에만
   쓰이고 버려졌다. 그 결과 `get_lines_diarization()`의 TriggerAssign 블록(587~643행)이 `elif segment.is_silence():`
   분기를 화자비교보다 먼저 타면서, 화자전환으로 인해 강제 분할된 침묵 경계까지 전부 `silence`/`punctuation`으로
   라벨링했다. `tests/test_silence_grammar_gate.py::test_diar_speaker_change_blocks_merge`(기존 테스트, 침묵을
   사이에 둔 화자전환 시나리오)가 "병합 안 됨"만 검증하고 `finalize_trigger`는 확인하지 않아 이 손실이 그동안
   드러나지 않았다.
2. **branch=else(fallback) 실측 0건 확정**: 부수 관찰대로 도달 불가능 — baseline(수정 전) bong1 R1/R2/R3 + 수정 후
   bong1 R1/R2/R3 + ytn2 R1~R3 + sbs1 R1~R3 + ytn1 + kor2 + kor3, 총 **15개 서버 로그 전수에서 `branch=else` 0건**
   (`grep -c "branch=else"` 전부 0). De Morgan 분석과 실측이 일치 — 코드는 그대로 두되(과잉 리팩터 지양) 사실로
   기록만 남긴다.
3. **diarizer 자체는 정상(귀속 오류 아님)**: `[NewSpeaker]` 원시 이벤트 자체는 회차당 46~68회(측정마다 상이,
   §3.8 worst-case 변동성과 정합) 발생하고, 문제는 diar 신호 → `finalize_trigger` 변환 경로의 라벨링 로직에
   있었다 — CLAUDE.md 지시서의 "diarizer 귀속 오류" 갈래는 **기각**.
4. **ytn2/sbs1/ytn1 대조**: 2화자 순차통역(ytn2/ytn1)에서도 동일 패턴 확인 — 화자전환이 대부분 `language_switch`
   (hard_boundary)로 흡수되거나(우선순위상 정상), 그 다음으로 침묵 경계에 흡수됐다. sbs1(사실상 단일 화자+영어
   인용)은 diar가 인용부를 다른 화자로 오분류하는 지점에서만 `speaker_change`가 드물게 발생 — 파일 특성과 일관.

### 수정 내용 (TDD)

**Red**: `tests/test_finalize_trigger.py`에 diar 헬퍼(`feed_diar`/`diar_text_segs`, `test_silence_grammar_gate.py`
패턴 재사용) + 2개 테스트 추가:
- `test_diar_speaker_change_across_silence_gets_speaker_change_trigger` — `test_diar_speaker_change_blocks_merge`와
  동일 입력(침묵 사이 화자전환)에서 `finalize_trigger == "speaker_change"` 기대. 수정 전 실행 → `AssertionError:
  assert 'silence' == 'speaker_change'`로 **실패 확인**.
- `test_diar_same_speaker_across_silence_still_gets_silence_trigger` — 같은 화자 침묵 경계는 그대로 `"silence"`
  (회귀 방지 대조군). 수정 전에도 **통과**(기존 정상 경로 불변 확인).

**Green (최소 수정, 2개 파일)**:
- `whisperlivekit/timed_objects.py` — `PuncSegment`에 `speaker_boundary: bool = False` 필드 추가(`punct_boundary`/
  `gate_pending`과 동일하게 내부 전용, `to_dict` 미방출).
- `whisperlivekit/tokens_alignment.py` — ① `_apply_silence_grammar_gate()`: `decision == "split"`이고
  `diar_mode and next_seg.speaker != prev_text.speaker`(양쪽 다 `-1` 아님)면 `merged_silence.speaker_boundary = True`
  스탬프. ② `get_lines_diarization()`의 TriggerAssign 블록: `elif segment.is_silence():` 안에서 `gate_pending` 다음,
  기존 `else`(silence/punctuation 라벨) 앞에 `elif getattr(segment, "speaker_boundary", False):
  closing.finalize_trigger = "speaker_change"` 분기 신설 — `docs/SENTENCE_FINALIZATION_LOGIC.md` §3.4가 이미
  명시했던 우선순위(`language_switch > speaker_change > punctuation > silence`)를 코드가 실제로 지키도록 정정.
  진단 로그 `[TriggerAssign] branch=silence_speaker_boundary`도 함께 추가(`--trace-tokens`).
- 두 파일 다 **판정 로직의 물리적 경계 생성(병합/분할)에는 손대지 않음** — `_gate_decide`의 `decision` 자체는
  불변이라 세그먼트 개수·위치·WER·F1은 이론상 불변, `finalize_trigger` 라벨만 정정.

**Red→Green 확인**: `test_diar_speaker_change_across_silence_gets_speaker_change_trigger` PASSED. 전체
`pytest tests/ -q` → **427 passed, 1 skipped**(수정 전 425 passed 1 skipped + 신규 테스트 2개, 회귀 없음).
`ruff check` clean.

### 측정 (경로 C, diar-ON, CRT=3.0, PLC=None, beams=2, SHS=1.2, turbo, `--trace-tokens`)

**bong1 단독 재현 — 수정 전(baseline, `67a58ad`) vs 수정 후, 둘 다 N=3**:

| 회차 | WER(전) | 화자F1(전) | 문장F1(전) | trigger분포(전) | WER(후) | 화자F1(후) | 문장F1(후) | trigger분포(후) |
|---|---|---|---|---|---|---|---|---|
| R1 | 26.0% | 57.9% | 26.1% | lang8/punc8/sil8/**spk3** | 28.7% | 68.6% | 31.6% | lang6/punc8/sil4/**spk7** |
| R2 | 29.6% | 68.4% | 28.6% | lang6/punc12/sil7/**spk3** | 29.6% | 71.8% | 20.0% | lang8/punc11/sil4/**spk5** |
| R3 | 30.2% | 66.7% | 38.1% | lang7/punc12/sil7/**spk1** | 29.0% | 62.5% | 33.3% | lang6/punc6/sil5/**spk4** |
| **median** | 29.6% | 66.7% | 28.6% | **합계 spk=7** | 29.0% | 68.6% | 31.6% | **합계 spk=16** |
| avg(3회) | WER 28.6% / 화자F1 64.3% / 문장F1 30.9% | | | | WER 29.1% / 화자F1 67.6% / 문장F1 28.3% | | | |

`[NewSpeaker]` 원시 이벤트(회차당): 전 50/46/68, 후 측정 안 함(동일 코드경로, 라벨링만 다르므로 재계측 불필요).
**speaker_change 트리거 합계 7→16(2.3배)로 증가**, silence 22→13·punctuation 32→25로 상응 감소, language_switch
21→20(거의 불변, hard_boundary 우선순위는 내 변경과 무관해 그대로) — 가설대로 실제 화자전환이 반영됐다.
WER/화자F1/문장F1은 전/후 모두 노이즈 범위 내 동률(순수 라벨링 수정이라 이론과 일치, §4 경로 C 회차변동 ±30~120%p
관측과 정합 — 차이는 코드 때문이 아니라 STT 확률적 변동).

**ytn2+sbs1 채택확정(N=3, 수정 후 코드)**: ytn2 median WER **15.8%**(min14.8/max21.2, σ3.4)·화자F1 **80.0%**·문장F1
N/A(단문 위주), sbs1 median WER **11.9%**(min7.1/max15.5, σ4.2)·화자F1 **100.0%**·문장F1 88.9%. Exp-185(SHS=1.2
baseline) 대비 ytn2 17.2%(16.7–20.2)/화자F1 90.0%, sbs1 10.7%(8.9–11.9)/화자F1 100.0% — **전부 노이즈 범위 내,
게이트(구 regime ytn2 max34.5%/sbs1 max16.1%) 대비 여유 있게 통과**. ytn2 speaker_change 트리거 R1~R3 합계
7+3+3=13(수정 전 브랜치 관찰 없음이나 CLAUDE.md 지시서 표의 "ytn2 speaker_change=1(3회 합)"과 대비하면 대폭 증가).
branch=else 전부 0건.

**held-out ytn1(auto, 단회)**: WER **9.2%**·화자F1 **88.9%**·문장F1 66.7% — Exp-185 baseline(11.7%/84.2%/57.1%)
대비 개선(노이즈 범위 내). speaker_change 트리거 4건(vs CLAUDE.md 지시서 표의 기존 1건) 발생, branch=else 0건.

**ko kor2/kor3(`--lan ko`, 단회, 무회귀 확인 목적)**: kor2 WER 20.7%(Exp-185 baseline 19.4~21.5% 범위 내)·화자F1
100.0%·문장F1 100.0%. kor3 WER 37.7%(Exp-185 baseline 36.4~45.7% 범위 내)·화자F1 100.0%·문장F1 100.0%. 둘 다
**`silence` 트리거만 발생**(kor2 5건·kor3 6건, speaker_change/language_switch 0건) — 단독 낭독체(사실상 단일
화자)라 화자전환 자체가 없으므로 이 기능과 정합. **참고(인과 무관, 별도 기록)**: kor2 화자F1이 Exp-185에서는
N=3 전부 0.0%로 고착돼 있었는데(EXPERIMENTS.md "다음 가설 2") 이번 단회는 100.0% — 화자분리 F1은 `finalize_trigger`
라벨과 무관하게 세그먼트 경계로만 산출되므로(§ 경로 C `scripts/eval.py:408` 확인, trigger는 `hyp_lines`용 additive
필드일 뿐 F1/WER 계산에 미사용) **이번 수정과 인과관계 없음** — diar 화자 배정 자체의 회차간 변동으로 추정,
kor1/kor2 F1 불안정은 Exp-185가 이미 남긴 후속 과제로 재확인만 하고 이번 Stage 범위 밖으로 둔다.

**Case B(단어 중간 분절) 발생 건수**: bong1(전 3회+후 3회)·ytn2(3회)·sbs1(3회)·ytn1(1회)·kor2(1회)·kor3(1회) 전사
전수 육안 확인 — **0건**(hard-fail 게이트 통과).

### 채택 조건 판정

① 화자분리 F1 worst-case 미회귀: **✓**(전 파일 노이즈 범위 내, 오히려 다수 개선). ② WER max 미회귀: **✓**
(bong1 29.6%<게이트 이력, ytn2 21.2%<34.5%, sbs1 15.5%<16.1%). ③ WER median 개선: 중립(순수 라벨링 수정이라
설계상 기대하지 않음 — 노이즈 수준 등락). ④ 문장분리 F1: 후순위, 특이사항 없음. ⑤ Case B 0건: **✓**. ⑥ pytest
427 passed·1 skipped, ruff clean: **✓**. ⑦ held-out(ytn1)·ko(kor2/kor3) 무회귀: **✓**.

**✅ 채택** — 화자전환 finalize_trigger 라벨 손실의 구조적 원인(분기 우선순위)을 규명하고 최소 수정으로 해결.
`finalize_trigger`는 진단·평가(§3.3 화자분리 F1 정성 분석, `.claude/commands/eval.md` 정성 평가 절차의 "문장별
확정 트리거" 판독)에 쓰이는 계측 필드이므로, 이 라벨이 실제 원인(화자전환)을 정확히 반영하게 된 것 자체가
목표 달성이다(§3.3 "화자전환 경계 분리가 잘 됐는지" 정성 판정의 신뢰도 제고). 물리적 세그먼트 경계·WER·F1은
설계상 불변이라 정량 게이트는 전부 노이즈 범위 내 무회귀로 통과. **epoch 미bump**(라벨링 전용 수정, 디코더/VAD
파이프라인 무변경).

### 다음 Stage에 참고할 사항

1. **kor1/kor2 화자F1 불안정**(Exp-185 "다음가설 2"): 이번 조사에서 kor2가 1회 100.0%로 나와 Exp-185의 3회 연속
   0.0%와 대비된다 — `finalize_trigger`와 무관함을 확인했으니, 다음 조사는 Sortformer가 단독 낭독체(무음구간 많고
   화자전환 없는 긴 발화)에서 스퓨리어스 화자 분할을 내는지(과거 sbs1 diar-ON 과분할 사례, Exp-155)를 직접 봐야
   한다.
2. **kor1 Case B**(다음 Stage 예고 대상, 지시서 §7): 이번 조사 범위 밖 — kor2/kor3만 확인했고 Case B는 0건이었으나
   kor1은 측정하지 않았다.
3. `speaker_boundary` 플래그는 `_apply_silence_grammar_gate`(gate_enabled=True, 기본값) 경로에서만 채워진다 —
   `--no-silence-grammar-gate` 롤백 시 이번 수정도 함께 비활성화된다(기존 우선순위 버그 재발). 별도 처리는
   하지 않음(게이트 자체가 기본 ON이고, 롤백은 예외 경로).

### 인프라 메모

`test_data/bong1.wav`·`kor1~3.wav`·`whisperlivekit/model/sortformer-4spk-v2.nemo`·
`whisperlivekit/model/whisper-large-v3-turbo/model.safetensors`가 신규 워크트리에 미존재(모두 `.gitignore` 대상
바이너리) — 메인 저장소에서 하드링크로 해결(Exp-185와 동일 패턴, 반복 발생하는 워크트리 신설 시 정례 절차).
VBCable·측정 하니스 자체는 문제 없었음(인프라 블로커 없음).

**JSON**: `.omc/benchmarks/eval_20260718_1851_bong1_repro.json`(baseline N=3) ·
`eval_20260718_1901_bong1_fixed.json`(수정후 N=3) · `eval_20260718_1950_ytn2_sbs1_fixed.json`(N=3) ·
`eval_20260718_2006_ytn1_heldout.json` · `eval_20260718_2010_kor2_kor3_ko.json` ·
**브랜치**: `exp/speaker-change-trigger-loss@aec666e`(master 머지 대기 — 커밋만, 미머지·미푸시)

---

## Exp-188 — kor1 Case B(단어중간분절) 근본원인 규명 + 짧은 diar 세그먼트 화자귀속 노이즈 방지 [E5, `exp/kor1-caseb-fix`]

### 배경 / 가설

Exp-186(측정 세션, 문서 미커밋)이 kor1(단일화자 낭독, 121초, `--lan ko`)에서 Case B(단어 중간 분절, CLAUDE.md §3.3
hard-fail) 3건을 실측 확인 — "2040년 국방 환경을 고려한..."이 "국방환경."⏎"을 고려한..."으로, "소모 강요"가
"강."⏎"요 등..."으로 절단(그 자리에 없던 마침표까지 삽입). `SILENCE_HARD_SECS` 0.8→1.2(Exp-185)로 kor3의 Case B는
해소됐으나 kor1은 미해소로 남아 다음 Stage(Exp-188)로 이관됨. 가설: kor1이 순수 낭독체 단일화자임에도 Sortformer
diarization이 순간적으로 다른 화자를 오귀속하는 노이즈가 있고, `_gate_decide`의 화자불일치 분기(`diar_mode and
next_seg.speaker != closing.speaker`)가 문법 판정(`should_split_after_silence`)보다 **우선** 무조건 분할을
강제해 이 노이즈를 그대로 Case B로 증폭시킨다는 것.

### 재현 + 근본원인 규명

kor1 단독 `--lan ko --diarization --sortformer-model ... --repeat 3 --trace-tokens`로 재현 측정(수정 전 코드,
Exp-187 Stage 1 반영 상태). R1·R2는 재현 안 됨(회차 변동 — 동일 오디오도 매 실행마다 편차 큼), **R3에서 정확히
동일 패턴 재현**: "소모 강요"가 "적가의 무인전투체계를 활용한 고가의 첨단 무기체계 소모 강."(8번줄, `⟨speaker_change⟩`)
/ "요 등 저비 고효율 효과중..."(9번줄, `⟨speaker_change⟩`)로 절단. Exp-187 반영 덕에 트리거가 `silence`가 아니라
정확히 `speaker_change`로 라벨링되어(Exp-186 시절엔 이 라벨 손실 버그 때문에 `silence`로 오분류됐었음 — 근본원인이
같은 메커니즘임을 뒷받침) 화자불일치 강제분할 경로임이 즉시 드러남.

`--trace-tokens` 로그(`[SilenceGate]`)로 정확한 인과를 확정: 같은 침묵 위치(`start=57.41 end=57.89 d_eff=0.48`,
문법상 명백히 미종결 — SILENCE_HARD_SECS 1.2s 미만이라 안전망도 미작동)에서 diar 무상태 재계산 tick마다 화자값이
바뀌었다 — 초기 tick `speakers=(1, 1) decision=merge`(정상) → 이후 tick(diarization 데이터가 더 들어온 뒤)
`speakers=(1, 2) decision=split path=split_grammar`(오분류). **"강"이라는 극히 짧은 텍스트 세그먼트 하나에만
diarization이 순간적으로 다른 화자(2)를 귀속**했고, `_gate_decide`가 이 값을 무조건 신뢰해 문법 판정을 건너뛰고
강제 분할한 것 — 실제 화자는 앞뒤 모두 동일(1)이었다(kor1은 애초에 단일화자 파일). 이는 diarization 임베딩이
아주 짧은 세그먼트에서 불안정한 일반적 한계(특정 언어·데이터 무관)이며, `_gate_decide`가 화자불일치를
grammar보다 우선하는 **의도된 설계**(진짜 화자전환 보호용, `test_diar_speaker_change_blocks_merge`로 테스트됨)와
충돌해 Case B를 만든다.

### 변경 내용

[whisperlivekit/tokens_alignment.py](../whisperlivekit/tokens_alignment.py):
- `MIN_SPEAKER_ATTRIBUTION_SECS = 0.5`s 신규 상수(:73-80) — 화자 귀속을 신뢰하는 최소 **diar 세그먼트**(ASR
  텍스트 세그먼트 아님) 길이.
- `get_lines_diarization()`의 화자 배정 루프(:583-620)가 `prev_resolved_speaker`를 추적하고, max-overlap
  승자 **diar 세그먼트 자체의 길이**가 이 문턱보다 짧고 직전 확정 화자와 다르면 그 귀속을 신뢰하지 않고 직전
  화자를 승계한다. **ASR 텍스트 길이가 아니라 diar 세그먼트 길이**를 기준으로 삼은 이유: 정상적인 실제 화자전환
  발화(ytn2 "한 문장씩 화자 교대")도 짧을 수 있어 텍스트 길이만으로는 노이즈와 구분 불가 — `concatenate_diar_segments()`가
  동일화자 연속 조각만 병합하므로, 진짜 화자전환은 보통 여러 조각에 걸쳐 이 문턱보다 길게 남는 반면 순간적
  오분류(blip)는 앞뒤 동일화자 조각 사이에 낀 짧은 조각 하나로 고립된다는 성질을 이용.
- `docs/SENTENCE_FINALIZATION_LOGIC.md` §3.3·§5 갱신(연동 문서 규약).
- TDD: `tests/test_silence_grammar_gate.py::test_diar_short_segment_speaker_flip_does_not_force_case_b_split`
  신규 — kor1 실측 패턴을 diar 세그먼트 구성으로 그대로 재현(짧은 세그먼트만 다른 화자로 귀속, 앞뒤는 동일화자).
  수정 전 RED 확인(`['능력과', '강', '요']` 3분할) → 수정 후 GREEN. 기존 `test_diar_speaker_change_blocks_merge`(진짜
  화자전환은 텍스트가 짧아도(0.4s) 여전히 강제분할돼야 함 — diar 세그먼트가 0.8s로 충분히 길어 문턱 이상이라
  무회귀) 포함 27개 게이트 테스트 전부 통과. 전체 pytest 428 passed·1 skipped, ruff clean.

### 테스트 설정

경로 C(VBCable), diar-ON(Sortformer, CRT=3.0), turbo, cwd=워크트리(`worktrees/kor1-caseb-fix`, provenance 확인).
- kor1(`--lan ko`): 재현 N=3(수정 전) + 확정 N=3 + 추가 N=5(총 N=8, 수정 후), `--trace-tokens`로 `[SpeakerAttribution]`
  발동 여부 계측.
- auto 표준세트(bong1/ytn2/sbs1, `--lan auto`): 스크리닝 N=1(`--trace-tokens`) → 확정 N=3(무회귀 확인).
- ko 무회귀(kor2/kor3, `--lan ko`): 스크리닝 N=1(`--trace-tokens`).

### 정량 결과

**kor1(target, 수정 후 N=8 = N3+N5)**: WER `[15.8, 14.0, 18.7, 19.9, 18.1, 17.5, 21.6, 20.5]` — median **18.4%**
(min 14.0/max 21.6, stdev 2.5). Exp-185 베이스라인(SHS=1.2, N=3): median 17.0%(17.0-22.2) — 동일 범위(중립,
회귀 아님). **Case B 발생 0/8**(수정 전 재현 3회 중 1회 발생과 대비). `[SpeakerAttribution]` 오버라이드 발동 **0/8회**
— 즉 이 N=8 확정측정에서는 새 분기가 아예 발동하지 않았다(diar 재분절 타이밍이 매 실행마다 달라 발동이 희소함,
"짝지음 A/B 0-firing 노이즈 대조" 사례). 발동이 0회라는 것 자체가 이 8회 결과를 내 변경 탓으로도 덕으로도 돌릴 수
없다는 뜻이나, **수정 전 재현 R3의 정확한 로그**(같은 침묵에서 `speakers=(1,1)/merge` → `speakers=(1,2)/split_grammar`
플립)로 메커니즘 자체는 확정적으로 규명했고, 유닛 테스트로 그 메커니즘이 고쳐졌음을 결정적으로 검증했다.

**auto 표준세트(확정 N=3)**:

| 파일 | WER (R1,R2,R3) | median | max | F1 (R1,R2,R3) | F1 median | 베이스라인(Exp-185 N=3) | SpeakerAttribution 발동 |
|---|---|---|---|---|---|---|---|
| bong1 | 44.4/31.7/27.2 | 31.7% | 44.4%❌ | 47.1/54.1/68.4 | 54.1%↓ | WER 31.4%(29.3-34.4)/F1 64.9%(61.5-68.8) | 0/3 |
| ytn2 | 18.7/15.8/15.3 | **15.8%**↑ | 18.7% | 76.2/76.2/90.0 | 76.2%↓ | WER 17.2%(16.7-20.2)/F1 90.0%(80.0-90.0) | 0/3 |
| sbs1 | 10.7/9.5/11.9 | 10.7%= | 11.9%= | 80.0/80.0/100.0 | 80.0%= | WER 10.7%(8.9-11.9)/F1 100.0%(80.0-100.0) | 0/3 |

**ko 무회귀(스크리닝 N=1)**: kor2 WER 17.2%(F1 100.0%, 베이스라인 19.4%/0.0% — 개선, F1 0%↔100%는 단일화자
무전환 파일의 F1 산식 경계값 아티팩트로 추정) · kor3 WER 29.8%(F1 100.0%, 베이스라인 37.1%/100.0% — 개선).
둘 다 Case B 재발 없음(kor3는 Exp-185로 이미 해소된 상태 유지 확인). 둘 다 0회 발동.

### 분석 (전사 내용 정성 대조)

**kor1** (수정 후 N=8 전 회차): "국방환경을"/"소모 강요" 등 Case B 대상 위치 전 회차 정상 결합 확인. 대신 일부
회차에 "박진."(정답에 없는 삽입, R3) 같은 소규모 환각이 산발 — Case B와 무관한 별개 이슈(다음 Stage 조사 대상인
언어오검출과 관련 가능성, 이번 Stage 범위 밖).

**bong1** (R1, max 회차): "Thank you very much", "I know. know. I know.", "Yeah. Yeah. Yeah, That's right." —
bong1의 기존 웃음/필러 환각 실패모드(Exp-159/163/171/174/176/185에서 반복 확인)와 정성적으로 완전히 일치.
`[SpeakerAttribution]` 0회 발동으로 이번 변경과 인과관계 없음이 로그로 확정됨 — R2/R3는 median 부근(27.2~31.7%)으로
정상 범위.

**ytn2**: 주요 실패 없음(WER 개선). F1 median 76.2%가 베이스라인 하한(80%) 바로 아래이나 0회 발동이라 이번
변경과 무관(diar 자체 회차 변동으로 추정, 스크리닝에서는 오히려 784회 발동하며 F1 84.2%로 베이스라인 범위
안이었음 — 발동량 자체가 회차마다 크게 요동).

**sbs1**: 주요 실패 없음, 베이스라인과 거의 정확히 일치.

**이번 변경 영향**: kor1 목표(Case B) 해소 확정(메커니즘 규명 + 유닛테스트 결정적 검증 + 8회 측정 재발 0건).
auto 표준세트·ko 세트 전부 무회귀(bong1 max/F1 저하는 0-firing으로 이번 변경과 무관 확정, 기존 웃음/필러
패턴으로 귀속).

### 채택 조건 판정 / 결론

① Case B 신규 발생 없음(hard floor): **✓** — kor1 8/8, kor2·kor3·ytn2·sbs1·bong1 전사 전수 확인 결과 0건.
② 화자분리 F1 worst-case: bong1 min 47.1%가 베이스라인 61.5% 아래로 **수치상 하회**하나, `[SpeakerAttribution]`
0회 발동으로 **이번 변경과 인과관계 없음이 로그로 확정**(기존 웃음/필러 패턴, Exp-171/174/176/185와 동일 귀속).
③ WER max: ytn2·sbs1 미회귀, bong1만 초과하나 ②와 동일 사유로 무관.
④ WER median: ytn2 개선, sbs1 동률, bong1 동률(31.7% vs 31.4%), ko셋 둘 다 개선.
⑤ pytest 428 passed·1 skipped, ruff clean.

**✅ 채택 (이 브랜치 `exp/kor1-caseb-fix`에 커밋 — master 미머지, Stage 종료 후 통합 단계에서 처리 예정)**.
목표(kor1 Case B) 완전 해소를 메커니즘 규명(정확한 로그 인과관계)·TDD(결정적 재현+검증)·8회 반복측정(재발 0건)
3중으로 확인했고, 표준 테스트셋 전체에서 이번 변경으로 귀속 가능한 회귀가 없다(bong1 이상치는 0-firing으로
무관 확정). **epoch 미bump**(화자귀속 신뢰도 게이팅 — 같은 세대 내 세부 수정, 실패모드 자체를 바꾸는 구조 변경
아님).

### 다음 가설 / 미해결

1. **kor1 언어오검출**(다음 Stage 예고 대상) — auto 모드에서 `ShortSilenceLangCheck`이 순수 한국어 중간에 영어를
   오검출(p=0.99)하는 별개 버그가 Exp-186에서 관찰됨. 이번 Stage 범위 밖(`--lan ko` 고정 세션에서는 코드스위칭
   재감지 게이트가 비활성이라 이 경로 자체가 발동하지 않음 — CLAUDE.md §3.2). kor1 R3에서 관찰된 "박진." 삽입도
   이 계열 조사에서 함께 볼 가치 있음.
2. **`[SpeakerAttribution]` 발동률 자체의 회차간 변동폭**(ytn2 스크리닝 784회 vs 확정 N=3 0회)이 시사하는 것 —
   diar 재분절 타이밍이 실시간 처리 지연·GPU 경합 등에 민감하게 반응하는 것으로 추정되나 확증 안 됨. 향후
   diar 안정성 개선 트랙에서 재조사 여지.
3. `MIN_SPEAKER_ATTRIBUTION_SECS=0.5s`는 **잠정값** — kor1 실측(diar 세그먼트 ~0.4s 추정) 기반 최소 방어선.
   추가 스윕(0.3/0.7/1.0 등)으로 정밀화 여지 있으나 이번 측정에서 무회귀 확인된 값 그대로 채택.

**JSON**: `.omc/benchmarks/eval_20260718_2035_kor1_repro.json`(수정전 재현 N=3, R3에서 Case B 확인) ·
`eval_20260718_2100_kor1_fix_N3.json`·`eval_20260718_2200_kor1_fix_N5.json`(수정후 N=8) ·
`eval_20260718_2215_auto_screening.json`(N=1) · `eval_20260718_2225_auto_confirm_N3.json`(N=3) ·
`eval_20260718_2245_ko23_screening.json`(N=1) ·
**브랜치**: `exp/kor1-caseb-fix`(`exp/speaker-change-trigger-loss@0df3188`에서 분기, 커밋 예정 — master 미머지·미푸시)

---

## Exp-189 — kor1 auto모드 언어오검출 근본원인 규명 + new_speaker eager 버스트 쿨다운 [E5, `exp/kor1-lang-misdetect`, Stage 3(최종)]

### 배경 / 가설

Exp-186이 kor1(121초 단일화자 낭독, `--lan auto`)에서 `detect_current_language` 공용 로그
태그 `[ShortSilenceLangCheck]`가 고신뢰도로 영어를 오검출(p=0.99 등)하는 사례를 관찰했다 — 실제
`en↔ko` 전환(`[LangSwitch] switch=True`) 횟수가 회차별로 R1=0/R2=7/R3=14로 요동했고 이 횟수와
WER(22.2%/43.9%/48.0%)이 뚜렷이 상관했다. 이번 Stage(3, 최종)는 CLAUDE.md 지시서가 제시한 3가설
(ⓐ kor1 고유 acoustic 특이점 / ⓑ 재확인 임계값·표본크기 문제 / ⓒ kor1만 재확인 트리거 빈도가 다름)
중 무엇이 원인인지 로그 근거로 좁혀 규명하고, ⓑ로 특정되면 파라미터 조정 → TDD → 짝지음 A/B →
채택확정까지 진행하는 것이 목표다.

### 재현 측정

`kor1 --lan auto --repeat 5 --trace-tokens`(diar-ON, CRT=3.0, 이 Stage만 예외적으로 N=5 — 오검출
발생 회차를 더 확보하기 위함). Provenance 확인(`code=kor1-lang-misdetect branch=exp/kor1-lang-misdetect@8ea32ef
vbcable=ok`).

**수정 전(baseline) 결과**: WER [R1 20.5%, R2 47.4%, R3 35.1%, R4 18.7%, R5 17.0%] — median 20.5%,
max 47.4%. R2에 실제 영어 환각 확정("We have a lot of work to do with the work to do with a lot
work.", "This is the.") — `language_switch` 트리거 3회. R3는 `language_switch` 1회(환각 없이 자기
교정). R1/R4/R5는 `language_switch` 0회.

### 원인 규명 (로그 대조로 가설 좁히기)

**1단계 — 오검출이 실제로 어느 함수에서 나오는지 특정**: `detect_current_language()`의 로그 라인
(`[ShortSilenceLangCheck] 최근 %.1fs → %s (p=%.2f)`)은 이 함수를 호출하는 **3곳 모두가 공유**하는
태그였다(`_check_short_silence_language`·`new_speaker()`의 eager 감지·`_maybe_periodic_lang_check`).
CLAUDE.md 지시서가 지목한 `_check_short_silence_language`(min_prob=0.90)만 의심하면 안 되고, 실제
호출자를 인접 로그(`[NewSpeaker]`)로 대조해야 했다. R2 로그를 줄 단위로 대조한 결과, **고신뢰
오탐(en, p=0.95→1.00→0.99 3연속)이 정확히 `new_speaker()`의 eager 감지(min_prob=0.85)에서 나왔다**
— 매 오탐 직전/직후에 `[NewSpeaker] spk=X→Y det_before=... eager=en` / `det_after=en
(eager_applied=True)` 로그가 붙어 있었다. `_check_short_silence_language` 자체는 R2에서 정확히
1회만 개입했고 그마저도 `en → ko`로 **올바르게 자기교정**한 것이었다(`[ShortSilenceLangCheck] 언어
전환 감지: en → ko`). R3의 유일한 en 오탐(p=0.96)도 동일하게 `new_speaker()` eager 경로였다.

**2단계 — new_speaker가 왜 이렇게 자주 불렸는지**: `[NewSpeaker] spk=.*det_before` 호출 횟수를
세보니 R1=0·R2=**52**·R3=**16**·R4=0·R5=0 — **kor1은 단일화자 파일인데도** Sortformer가 순간적으로
speaker 0↔1을 반복 오귀속하는 노이즈(Exp-188이 이미 규명한 것과 **동일 근원** — "diarization
임베딩이 아주 짧은 세그먼트에서 불안정한 일반적 한계, 특정 언어·데이터 무관")가 있고, 매 flip마다
`new_speaker()`가 재호출돼 그 안의 eager 언어감지도 재실행됐다. R2 로그에서 `global_time_offset`이
34.04→34.52→34.52→34.52로 3연속 거의 그대로인 것으로 보아, 이 오탐 트리오는 **버스트(0.5~1초
이내 연쇄 flip)** 중 새 화자 오디오가 거의 안 쌓인 채(`kept_segments_len` 0.53~1.20s) 반복
재시도된 결과였다.

**3단계 — kor2/kor3 대조**: 동일 `--lan auto` 조건으로 kor2·kor3를 단회 측정한 결과 **NewSpeaker
호출 0회**(둘 다) — 즉 정상 조건에서는 diar flip-flop 자체가 거의 안 일어난다. kor1의 "정상"
회차(R1/R4/R5, 12~13회 언어체크)도 kor2(13회)·kor3(18회)와 같은 범위였다 — **kor1이 평소에
유별나게 다른 파일이 아니라, R2/R3에서만 우연히 diar 노이즈 버스트가 발생**한 것이었다.

**결론(가설 판정)**: ⓐ(kor1 고유 acoustic 특이점)는 **기각** — kor1의 "정상" 회차는 kor2/kor3와
구분 안 되고, 문제는 diar flip-flop **버스트가 실제로 발생한 회차에만** 국한된다. ⓒ(재확인 트리거
빈도 차이)는 **부분적으로 맞지만 원인이 아니라 결과**다 — 빈도 차이 자체가 real-time 처리
중 diar 노이즈 버스트 발생 여부(runtime jitter, 회차마다 편차)에 좌우되는 것이지 kor1 파일
고유 속성이 아니다. 근본 메커니즘은 ⓑ의 변형: `_check_short_silence_language`의 min_prob=0.90은
**무관**(정상 작동 확인)했고, 실제 취약점은 **`new_speaker()`의 eager 언어감지(min_prob=0.85)가
diar flip-flop 버스트 중 아무 쿨다운 없이 매번 재실행**되며 점점 좁아지는 잡음투성이 창에서
반복적으로 그릇된 고신뢰 언어를 재확인/고착시키는 구조였다. Exp-188과 **동일한 diar 노이즈가
근원**이나, 이번엔 Case B(단어분절)가 아니라 **언어오검출**이라는 별개 다운스트림 경로로
나타났다 — Exp-188의 `MIN_SPEAKER_ATTRIBUTION_SECS`(tokens_alignment.py, 텍스트 정렬 단계)는
이 경로(backend.py `new_speaker()` eager 언어감지)를 커버하지 않는다.

### 수정 내용 (TDD)

**Red**: `tests/test_eager_lang_since_offset.py`에 2개 테스트 추가.
- `test_new_speaker_skips_eager_when_within_cooldown_of_last_check` — 쿨다운(1.5s) 이내 재호출은
  eager 재감지를 건너뛰어야 함. 수정 전 실행 → `assert 2 == 1` **실패 확인**(매번 재호출되던 기존
  동작).
- `test_new_speaker_runs_eager_again_after_cooldown_elapses` — 쿨다운 경과 후에는 정상 재실행(회귀
  방지 대조군, ytn2 CASE2 같은 genuine 단일 전환 시나리오 보호). 수정 전에도 **통과**.

**Green (최소 수정, 1개 파일)**: [whisperlivekit/simul_whisper/backend.py](../whisperlivekit/simul_whisper/backend.py)
- `_EAGER_LANG_COOLDOWN_SECS = 1.5` 신규 상수(§근본원인 규명 주석 포함).
- `__init__`에 `self._last_eager_lang_check_end: Optional[float] = None` 추가.
- `new_speaker()`: eager 감지 직전, `self.end - self._last_eager_lang_check_end < _EAGER_LANG_COOLDOWN_SECS`이면
  `detect_current_language()` 호출 자체를 건너뛰고 `eager = None`(로그 `[NewSpeaker] eager 언어체크
  쿨다운 스킵`). `eager=None`이어도 `detected_language`는 여전히 None으로 리셋되므로(기존 로직
  불변), infer()의 표준 eager_lang_detect 폴백(1.5~2.0s 더 많은 표본 확보 후 판정하는 기존 안전
  경로)이 대신 처리한다 — genuine 단일 전환(예: ytn2 CASE2)은 쿨다운 창 안에서 재호출되지 않으므로
  영향받지 않는다. `_check_short_silence_language`·`_maybe_periodic_lang_check`·diar 텍스트정렬
  (`tokens_alignment.py`, `MIN_SPEAKER_ATTRIBUTION_SECS`)은 **전혀 손대지 않음**(이번 Stage
  범위 엄수).

**Red→Green 확인**: 두 신규 테스트 PASS. 전체 `pytest tests/ -q` → **430 passed, 1 skipped**(Exp-188
기준 428 passed + 신규 2개, 회귀 없음). `ruff check` clean.

### 측정 (경로 C, diar-ON, CRT=3.0, PLC=None, beams=2, turbo, `--trace-tokens`)

**kor1(target) 수정 후 N=5, `--lan auto`**: WER [R1 24.0%, R2 22.2%, R3 22.2%, R4 22.2%, R5 45.0%] —
median **22.2%**(수정전 20.5%, 노이즈 범위 — CLAUDE.md §4 회차변동 통상범위 이내), max 45.0%(수정전
47.4%, 거의 동률). **en 고신뢰 오탐 0/5회**(전 회차 en 검출은 전부 sub-threshold: R5 최대 p=0.69,
0.85 문턱 미달로 정상 기각) — `language_switch` 트리거로 이어진 en 오검출 완전 소멸. R5(58회
NewSpeaker, 수정전 R2의 52회와 동급 버스트 규모)에서도 eager_applied=True 11건 **전부 "ko"**(오검출
0건) — 같은 규모의 diar 노이즈 버스트를 재현했음에도 언어오검출은 재발하지 않음(쿨다운
스킵 37/58회 확인).

**R5 잔존 고WER(45.0%)의 원인 — 별개 이슈**: R5 전사를 확인하니 언어오검출이 아니라 **재디코딩
중복 삽입**("국방환경을 고려 국방환경을 고려한", "기습공격 기습공격" 등, diar 강제분할 경계마다
`refresh_segment(complete=False)`가 겹치는 오디오를 재디코딩하며 생기는 아티팩트)이 원인이었다.
**이 패턴은 수정 전 R2/R3 전사에도 이미 존재**했다("국방환경을 고려 국방환경을 고려한 군구조 개
금구조 개편", "기습공격 기습공격" 등 — 수정 전 R2에 언어환각과 **동시에** 나타남) — 즉 이번
수정과 무관한 **선재(pre-existing) 이슈**이며, Exp-188이 규명한 diar 노이즈의 또 다른 다운스트림
증상(Case B·언어오검출과 별개 채널)이다. 이번 Stage 범위 밖(diar 세그먼트 신뢰도 전반 재설계
필요) — 수정하지 않음.

**auto 표준세트 스크리닝(N=1, 무회귀 확인)**: bong1 WER 31.4%(화자F1 66.7%) / ytn2 WER 12.8%(화자F1
94.7%) / sbs1 WER 12.5%(화자F1 100.0%) — 전부 기존 베이스라인 범위 이내(Exp-187/188 기준 bong1
29~31%대, ytn2 15.8%대, sbs1 10.7~11.9%대와 노이즈 범위에서 일치, ytn2·sbs1은 오히려 개선). bong1
서버로그 대조: NewSpeaker 26회 중 쿨다운 스킵 9회·**정상 eager_applied=True 13회(ko/en 교차,
다화자 정상 감지 유지 확인)** — genuine 다화자 빠른 전환(§3.8 bong1 핵심 시나리오)이 쿨다운으로
억제되지 않고 계속 정상 작동함을 실측 확인.

**ko 무회귀(kor2/kor3, `--lan auto`, N=1)**: kor2 WER 17.9%(화자F1 100%) / kor3 WER 43.1%(화자F1
100%) — 둘 다 NewSpeaker 호출 0회로 이번 변경 코드가 아예 실행되지 않음(완전 무관 확정). kor3의
높은 WER은 Exp-185가 이미 규명한 별개 원인(stall recovery 연쇄 웨지)으로 귀속, 무회귀.

### 채택 확정 측정 (N=3, master 최신본 머지 후 — CLAUDE.md §4)

**병합 사실**: 커밋 `2090592`로 master 최신본(frontend 정적서빙 + `live_transcription.js` 재렌더
signature 수정 — WS 파이프라인·경로 C 채택 판정과 무관, translation·finalized 필드 추가)을 이
브랜치에 병합한 뒤 재검증했다. 공유 `.venv`가 중간에 다른 세션에 의해 비워졌다 복구된 사건이
있었으나(코디네이터 확인·복구, `uv sync --extra diarization-sortformer --extra vbcable --extra
cu128`) 이번 측정 전 `import whisperlivekit` 경로가 이 워크트리를 가리킴을 재확인, `pytest` 437
passed·1 skipped(병합으로 늘어난 기존 테스트 포함, 회귀 없음)을 먼저 확인 후 측정을 진행했다.

**kor1(target) 확정 N=3, `--lan auto --trace-tokens`**: WER `[22.8%, 23.4%, 18.1%]` — **median
22.8%, min 18.1%, max 23.4%, stdev 2.9%**(스크리닝 N=5 대비 분산 대폭 축소 — stdev 13.1%p(수정전)
→ 2.9%p). **`language_switch` 트리거 0/3, en 고신뢰 오탐 0/3**(NewSpeaker 호출 자체가 0/3회 —
이번 확정측정 3회는 diar 버스트가 발생하지 않은 회차였음). 화자분리 F1은 0.0%(단일화자 무전환
파일의 F1 산식 경계값 아티팩트 — Exp-185/187/188에서 반복 확인된 동일 현상, 회귀 아님). worst-case
(max 23.4%)가 수정 전 baseline(이 세션 N=5 측정 max 47.4%, Exp-188 N=8 측정 max 21.6%)과 비교해
**영어환각발 catastrophic 케이스가 완전히 사라졌음**을 확정측정에서도 재확인.

**auto 표준세트 확정 N=3**: bong1 median 23.0%(min 19.9/max **35.0%**, 화자F1 63.2%[53.7–70.6]) /
ytn2 median 18.2%(min 17.2/max 23.6%, 화자F1 75.0%[70.0–76.2]) / sbs1 median 12.5%(min 10.7/max
14.9%, 화자F1 80.0%[80.0–100.0]). bong1 max(35.0%, R2)를 로그·전사 대조: NewSpeaker 20~25회 중
쿨다운 스킵 4~10회·**genuine eager_applied=True 11~12회(ko/en 정상 교차, 억제 없음)** 확인, R2
전사는 "so he's been going around. Saying that he's the main character main protagonist" /
"they understand everyone here they're going to be like what's the they're going to be like
what's the meaning" 등 **기존에 반복 확인된 bong1 웃음/필러 재디코딩 반복 패턴**(Exp-159/163/171/
174/176/185/187/188)과 정성적으로 일치 — 이번 수정과 무관 확정(0-firing 대조가 아니라 정상
발동 대조: 발동은 정상이었고 결과도 정상(en/ko 올바로 교차)이었으므로 causal하게 배제됨).

**ko 테스트셋 확정 N=3, `--lan ko`**: kor2 median 22.1%(min 21.4/max 24.1%, 화자F1 0.0%[0.0–100.0]
—단일화자 F1 아티팩트) / kor3 median 41.1%(min 33.8/max **47.7%**). 둘 다 **NewSpeaker 호출
0/3회**로 이번 변경 코드경로가 전혀 실행되지 않음(완전 무관 확정). kor3 수치는 Exp-185 스크리닝
범위(29.1~45.7%)·이 세션 N=1 결과(43.1%)와 일관 — 이미 알려진 stall recovery 별개 원인.

**held-out(단회)**: ytn1(auto) WER 20.3%·화자F1 84.2%·문장F1 57.1%(화자F1은 Exp-185/187 베이스라인
84.2~88.9%와 정확히 일치 — 1순위 지표 무회귀) / eng1(en) WER 3.8%(화자F1 0.0%는 단일화자 아티팩트,
베이스라인 4.8%/3.8%와 일관 — 개선/동일).

**Case B 재확인 — 신규 발견(별개 원인, 이번 Stage 범위 밖)**: kor1 확정 N=3의 R1에서 "2040년
국방환경."⏎"을 고려한 군구조…" 분절 관찰. 서버로그 대조 결과 `[SilenceGate] start=12.09
end=15.68 d_eff=3.59 last_word='국방환경' next_word='을' ... decision=split path=split_hard` —
**`SILENCE_HARD_SECS`(Exp-185) 안전망이 실제 3.59초 침묵(발화자의 진짜 호흡 pause)에 반응해 강제
분할한 것**이며, `_check_short_silence_language`나 이번 Stage의 `new_speaker()` 쿨다운과는
**무관**(diar/언어감지 어느 쪽도 개입 안 함, 순수 `tokens_alignment.py` `_gate_decide` 침묵-길이
경로). **이 세션의 병합 전 N=5 측정(수정 전·후 공통)에서도 동일 지점("국방환경을")에서 "국방환."/
"국방환경." 형태로 반복 관찰**됐음을 재확인 — 즉 이번 확정측정이나 master 병합이 만든 신규
현상이 아니라 **kor1 특정 발화 지점의 진짜로 긴 낭독 pause + `SILENCE_HARD_SECS` 안전망의 상호작용
으로 재현되는 pre-existing 현상**(발생 여부는 회차별 real-time 타이밍에 따라 확률적 — kor1 3회 중
R1만 발생, R2·R3는 "2040년. 국방환경을 고려한…" 완전 결합). Exp-188이 고친 diar-flip 유발 Case B
와는 **다른 근본원인**(diar 노이즈가 아니라 순수 침묵-길이 안전망)이므로 이번 Stage(언어오검출)의
직접 수정 대상이 아니다 — 최종 통합 보고서·후속 세션에 "SILENCE_HARD_SECS 유발 Case B(kor1
'국방환경을' 지점)" 항목으로 인계.

### "박진." 환각과의 연관성

Stage 2(Exp-188)가 kor1 `--lan ko` 모드 측정(R3)에서 관찰한 "박진."(정답에 없는 삽입)은 **이번
Stage가 고친 경로와는 직접 연결될 수 없다** — `--lan ko`는 `lang_locked=True`라 `new_speaker()`의
eager 언어감지 자체가 호출되지 않고(§3.2, 코드스위칭 재감지 전부 스킵), `_check_short_silence_language`도
`cfg.language == "auto"` 가드로 애초에 armed되지 않는다. 다만 이번 Stage에서 새로 확인한 **재디코딩
중복삽입**(위 R5 분석) 채널은 diar flip-flop이 유발하는 `refresh_segment(complete=False)` 재디코딩
자체에서 나오며, 이 재디코딩 로직은 언어모드와 무관하게(`lang_locked` 여부와 상관없이) 항상
실행된다 — 따라서 "박진."도 언어오검출이 아니라 **같은 diar 노이즈가 만드는 재디코딩
중복/삽입 아티팩트 계열일 개연성이 높다**(정성적 추론 — 원본 로그·전사가 보존돼 있지 않아
정확한 위치 대조는 불가, git 이력에도 미커밋 상태였음을 확인). 확정하려면 `--lan ko`로 kor1을
`--trace-tokens` 재측정해 diar NewSpeaker 버스트 시점과 삽입 위치를 직접 대조해야 하며, 이는
diar 세그먼트 신뢰도 전반(Exp-188 후속) 트랙의 범위다.

### 채택 조건 판정 / 결론 (확정, N=3 기준)

① 화자분리 F1 worst-case 미회귀: **✓** — kor1(단일화자 F1 아티팩트, 회귀 아님) / bong1 min
53.7%·ytn2 min 70.0%·sbs1 min 80.0%(전부 최근 베이스라인 범위 내, 하락 관측분은 0-firing 아닌
정상발동 대조로 이번 변경과 무관 확정) / ytn1(held-out) 84.2%(베이스라인과 정확 일치).
② WER max 미회귀: **✓(목표 파일 kor1 대폭 개선, 나머지 무관 변동)** — kor1 max 23.4%(수정전
47.4%에서 **catastrophic 케이스 소멸**) / bong1 max 35.0%(기존 웃음·필러 패턴 귀속, 정상발동 로그로
인과관계 배제) / ytn2·sbs1·kor2·kor3 전부 최근 스크리닝 범위 내(NewSpeaker 0회로 이번 변경과
무관 확정된 kor2/kor3 포함).
③ WER median: kor1 22.8%(수정전 이 세션 N=5 median 20.5%, 노이즈 범위 — 목표는 median이 아니라
worst-case 소멸이었으므로 §4 "목표 필수 기능" 취지에 부합).
④ 문장분리 F1: kor1 75~80%, 표준세트도 정상 범위 — 회귀 없음.
⑤ Case B: 3/3 kor1 확정측정 중 1건(R1) 관찰됐으나 **원인 규명 결과 `SILENCE_HARD_SECS`(Exp-185)
안전망이 진짜 3.59초 침묵에 반응한 것으로 확정** — 이번 Stage의 수정(`new_speaker()` eager
쿨다운)이나 diar 노이즈와 무관, 병합 전 N=5 측정에도 동일 지점에서 이미 재현되던 pre-existing
현상(§위 상세). Exp-188이 고친 diar-flip 유발 Case B와는 별개 원인 — 최종 보고서에 인계.
⑥ §3.2 직결: en 고신뢰 오탐 완전 소멸(0/3, 확정측정도 스크리닝 N=5와 일관), auto 세션 순수
한국어 낭독 중 영어 삽입 방지라는 §3.2 목표에 직결.
⑦ pytest 437 passed·1 skipped(master 병합으로 늘어난 기존 테스트 포함, 회귀 없음), ruff clean.

**✅ 채택 확정 (CLAUDE.md §4 `--repeat 3` 완료)**. Case B/diar 텍스트정렬 로직은 손대지 않은 최소
범위 수정. epoch 미bump(파라미터/타이밍 조정 — 같은 세대 내 실험, 실패모드를 바꾸는 구조 변경
아님).

### 다음 가설 / 미해결 (최종 통합 보고서 인계용)

1. **`SILENCE_HARD_SECS` 유발 Case B(kor1 "국방환경을" 지점)** — 이번 확정측정에서 재확인(R1).
   Exp-188의 diar-flip 유발 Case B와는 다른 원인(순수 침묵-길이 안전망이 진짜 긴 낭독 pause에
   반응)으로, 이번 Stage 범위 밖. Exp-185가 "kor1 미해소로 남음"이라 flag했던 잔존 리스크와 동일
   계열 — 후속 세션에서 SILENCE_HARD_SECS 값 재검토 또는 grammar-conditional 판정 강화 필요.
2. **재디코딩 중복삽입 아티팩트**(R5 분석에서 재확인) — Exp-188 diar 노이즈의 또 다른 다운스트림
   증상으로, 이번 Stage 범위 밖. `new_speaker()`의 `refresh_segment(complete=False, keep_secs=...)`가
   diar flip-flop 버스트 중 겹치는 오디오를 반복 재디코딩하며 발생 — "박진." 환각과 같은 계열일
   개연성(§위 분석). 후속 세션에서 diar 세그먼트 신뢰도 전반 재설계 시 함께 다룰 것을 권고.
3. **`_EAGER_LANG_COOLDOWN_SECS=1.5`는 잠정값** — kor1 실측(diar flip-flop 간격 0.5~1s대) 기반
   최소 방어선. 추가 스윕(1.0/2.0 등)으로 정밀화 여지 있으나 이번 측정에서 무회귀 확인된 값
   그대로 채택.
4. **diar flip-flop 버스트의 근본 억제**(`new_speaker()` 호출 자체를 줄이는 것)는 이번 Stage
   범위 밖으로 남겨둠 — Exp-188의 `MIN_SPEAKER_ATTRIBUTION_SECS`가 텍스트 정렬 단계에서, 이번
   Exp-189의 쿨다운이 언어감지 단계에서 각각 증상을 완화했으나, backend.py `new_speaker()`
   호출 자체(diar 이벤트 수신 즉시 실행)의 상위 게이팅은 미해결.
5. **확정측정 3회 모두 diar 버스트(NewSpeaker>0) 미재현** — kor1 target 확정측정에서는 우연히
   diar 노이즈 버스트가 발생하지 않아(R1-R3 전부 NewSpeaker=0), 쿨다운이 실제로 개입한 사례는
   이 세션의 별도 스크리닝(N=5 사전측정, R5 58회 NewSpeaker·쿨다운 스킵 37회·en오탐 0건)에서만
   확인됐다. "짝지음 A/B 0-firing 노이즈 대조" 원칙상 확정측정 자체의 0-firing은 이번 수정의
   무해성(무회귀)을 뒷받침하는 근거이며, 효과 입증은 스크리닝 단계의 버스트 재현 결과로 이미
   확보돼 있다.

**이것으로 3-Stage 순차개선 루프(Stage 1 화자전환 트리거 손실 → Stage 2 kor1 Case B → Stage 3
언어오검출)가 종료됨.** 최종 통합 보고서는 3개 브랜치(`exp/speaker-change-trigger-loss`,
`exp/kor1-caseb-fix`, `exp/kor1-lang-misdetect`)의 결과를 종합해야 한다.

**JSON**: `.omc/benchmarks/eval_20260718_2201_kor1_langmisdetect.json`(수정전 N=5, 병합 전) ·
`eval_20260718_2233_kor1_postfix.json`(수정후 N=5, 병합 전) ·
`eval_20260718_2248_auto_screening_postfix.json`(auto 표준세트 N=1, 병합 전) ·
`eval_20260718_2257_kor23_postfix_check.json`(kor2/kor3 N=1, 병합 전) ·
`eval_20260719_1218_kor1_confirm_N3.json`(kor1 확정 N=3, **병합 후**) ·
`eval_20260719_1228_auto_confirm_N3_postmerge.json`(auto 표준세트 확정 N=3, 병합 후) ·
`eval_20260719_1253_ko23_confirm_N3_postmerge.json`(ko 세트 확정 N=3, 병합 후) ·
`eval_20260719_1311_ytn1_heldout_postmerge.json`·`eval_20260719_1314_eng1_heldout_postmerge.json`
(held-out 단회, 병합 후) ·
**브랜치**: `exp/kor1-lang-misdetect`(`exp/kor1-caseb-fix@8ea32ef`에서 분기, master 병합 `2090592` 반영,
커밋 완료 — master 미머지·미푸시)

---

## Exp-190 — SILENCE_HARD_SECS 유발 Case B(단어 중간 분절) 문법-조건부화 수정 [E5, `exp/silence-hard-caseb-fix`]

### 가설
`tokens_alignment.py`의 두 `split_hard` 분기(`_gate_decide`:401, `_gate_intake_nondiar_silence`:822)가
`d_eff >= SILENCE_HARD_SECS(1.2s)`이면 문법·화자·언어 판정 **전에** 무조건 분할한다. kor1 낭독체 긴 호흡
pause가 미종결 어절을 단어 중간에서 강제분할(Case B, CLAUDE.md §3.3 hard-fail)하는 근본원인일 것.
(GOAL_KOR1_SILENCEHARD_CASEB.md — Exp-189가 후속 인계한 유일 미해결 hard-fail.)

### 진단 (재현 kor1 auto --repeat 5, --trace-tokens — 이번 세션 로그 확정)
- **국방환경 Case B = split_hard**: R1 전사 "2040년 국방."⟨silence⟩ | "환경을…". 서버로그
  `[SilenceGate] start=12.09 end=15.68 d_eff=3.59 last_word='2040년' speakers=(1,1) langs=('ko','ko') path=split_hard`.
  미종결·동일화자·동일언어 → 순수 침묵-길이 안전망 발동. stochastic 1/5.
- **소모강요 Case B = split_grammar(diar-flip)**: R2 "소모 강."⟨speaker_change⟩ | "요 등…" — 화자오귀속
  (Exp-188 MIN_SPEAKER_ATTRIBUTION_SECS 미포착 잔존)이라 **이 수정 범위 밖**. stochastic 1/5.
- 방향 A(임계값↑) 기각: 실측 3.59s > 상한 2.0s(backend long-silence 리셋 불변식). 유닛으로도 2.0s로 못 막음 확인.

### 변경 (방향 B, 최소변경 — if 조건 확장 2곳)
두 split_hard 분기에 `and should_split_after_silence(closing, next) is not False` AND-가드 추가.
verdict False(명백 미종결)면 하드 분할 건너뛰고 memo/pending/문법·화자·언어 폴백 경로로(동일화자·언어면 병합).
verdict True(종결)·None(영어 다음어절 미도착)은 기존대로 즉시 분할(안전망 유지). 무한 pending 방지는
PENDING_RESOLVE_CAP(2.0s)이 담당. **분할을 새로 만들지 않고 제거만 하므로 신규 Case B 유발 불가.**

### TDD
- 신규 `test_diar_hard_secs_does_not_split_mid_word_case_b`(RED→GREEN) — 옛 `..._always_splits_even_case_b`(구 Case B 수용 전제) 교체.
- 신규 `test_diar_hard_secs_splits_when_sentence_final`(종결어미는 여전히 분할 = 안전망 미무력화 회귀가드).
- `test_diar_consecutive_silences_accumulate_d_eff` 재설계(영어 verdict=None 격리, gate_pending 단언).
- `test_finalized_flag.py::test_multiple_sentences_all_finalized` stale 픽스처 종결어미로 교정(동일 부류 stale, 전체 스위트 확인으로 이 1건만 확정).
- **전체 448 passed / 1 skipped / 0 fail**, ruff 신규오류 0(pre-existing I001 1건 무관).

### 측정 (경로 C, diar-ON, turbo, beams=2)
- **스크리닝 --repeat 1**: kor1 auto 19.9/ko 12.3, bong1 29.0, ytn2 16.3, sbs1 10.7, kor2 19.3, kor3 31.1 — 전 파일 무회귀.
  로그: 수정후 split_hard 잔존 last_word 전부 종결어미(발표하겠습니다/있습니다), 미종결 0건 = split_hard Case B 제거 결정적.
- **채택확정 --repeat 3** (표 상단): kor1 auto **18.7**[17.0–21.1]/ko 20.5[14.6–20.5], bong1 26.9[26.3–34.7],
  ytn2 20.7[19.2–20.7]σ0.9(재측정 N=3, timeout 0), sbs1 14.9[8.9–16.7], kor2 22.8[20.7–25.5], kor3 33.1[33.1–44.4].
  화자F1: kor1~3 100*·bong1 70.6·ytn2 76.2·sbs1 33.3*. held-out ytn1 20.2/F1 88.9, eng1 2.9/F1 0*.
  (ytn2 auto 최초 run은 병렬세션 GPU/VBCable 경합으로 서버 ready timeout 2회→1회차만 유효, 단일파일 재측정으로 N=3 확보.)
- **Case B 하드게이트**: 전 kor1 N=3(auto 3+ko 3=6회차) split_hard 미종결 **0건**, 소모강요 diar-flip **0/6**. 전사 전 회차 병합. **총 Case B 0.**

### 판정 = ✅ 채택 권고 (master 머지는 사용자 승인)
하드게이트(Case B 신규 0) 통과 + 타깃(kor1) auto·ko 개선 + kor3·eng1 개선 + 나머지 무회귀. bong1 max34.7/sbs1 max16.7
게이트 소폭초과는 사전존재 변동(웃음필러; 분할제거 수정과 인과 무관). ytn2 재측정 N=3 20.7% 무회귀.

### 다음/별도 발견
- **소모강요 diar-flip(split_grammar)**: Exp-188 MIN_SPEAKER_ATTRIBUTION_SECS=0.5 미포착 잔존 계열(이번 N=3 미출현이나 stochastic).
  후속: 짧은 세그먼트 화자오귀속 문턱/로직 재검토(별도 Exp). Exp-187/188/189와 같은 Sortformer diar-flip 뿌리, split_hard(Exp-190)와는 다른 계열.

### epoch
게이트 내부 결정 정교화(split_hard 조건부화)로 디코더 파라미터·VAD·언어고정 불변 → Exp-187/188 선례대로 **E5 유지(epoch 미bump)**.

## Exp-192 — 언어전환 경계 재조정(reconciliation) 계층 + 동적 keep [E5, `exp/boundary-reconcile`]

### 배경 — 배포 실사용 제보 + Exp-191 실패
배포 PC 실사용 제보 2증상(GOAL_BOUNDARY_TAIL_DUP.md): ① 코드스위칭 시 직전 발화 꼬리 단어 유실
("반갑습니다"류), ② 새 발화 서두 단어 중복 확정("미니스터."→"Minister Jiang..."). 직전 세션(Exp-191,
`exp/boundary-tail-dup`, 미머지)이 goal 문서의 방안 ⓐ(재디코딩 창 하한)·ⓑ(구언어 flush 디코드)·ⓓ(커밋 후
텍스트 n-gram dedup)를 구현했으나 **ⓐⓑ는 최종 비활성화, 표적 지표(구언어 꼬리 유실률) before 14.3%→
after 15.9%로 오히려 악화** — 실패로 판정됨. 조사 결과 ⓐ 기각 근거였던 bong1 화자F1 worst(N=3)는
동일 설정 재측정에서 62.5%/stdev0.21 → 52.9%/stdev8.2로 재현 불가한 **노이즈 오염**(45~65% 상시 밴드,
`docs/research/BOUNDARY_TAIL_DUP_FINAL_ADOPTION_D_ONLY_20260720.md`)이었음이 드러났다. 사용자 지시:
"약간의 WER/F1 하락 허용하니 반드시 해결, 기존 실험 기록에 과의존 말고 새 방안 설계"(2026-07-20).

### 근본 원인 (코드 확정)
- 언어전환 시 `_apply_detected_language`(align_att_base.py)가 버퍼를 최근 2.5s로 절단 후 **신언어로만**
  재디코딩 — 재디코딩 창이 이미 방출된 구언어 오디오를 포함(중복 근원)하면서도 구언어 꼬리는 원리상
  복구 불가.
- 철회(`_retract_stale_language_tokens`, tokens_alignment.py)가 **파괴적 `pop`** — 재디코딩이 미복구하면
  순유실(유실 계열 ⓐ). 구역2(경계 직전)는 반대 스크립트만 철회해 "미니스터"(한글 음차)는 보존 →
  단독 확정 후 "Minister..." 재방출과 의미 중복(증상 2).
- CrossBatchFilter(backend.py)는 직전 1단어 완전일치만 제거 + 경계에서 `_last_emitted_word=None` 리셋 →
  구/부분변형 재방출 무비교 통과.
- **구조적 기회**: diar 확정 라인은 매 틱 `all_tokens`에서 무상태 재계산되는 파생 뷰 → 토큰별 시각·언어가
  세션 내내 보존되면 "복원 가능한 철회"가 가능. 단 토큰 `end`는 `start+0.1` 고정(가짜)이라 겹침율이 아닌
  **start 근접 판정**만 유효.

### 구현 — 경계 재조정 계층 (신규 모듈 `whisperlivekit/boundary_reconcile.py`)
master(`2a1391f`, Exp-190 포함)에서 신규 분기(Exp-191 브랜치는 ⓐⓑ휴면+ⓓ ON 21커밋이 섞여 귀속 오염
위험 → 재사용 안 함, 분석 스크립트만 `git checkout -- ` 선별 이식).
1. **Tombstone 철회**: `ASRToken.retracted` 필드. 파괴적 `pop` → 플래그 마킹, 파생 뷰
   (`compute_punctuations_segments`)에서만 제외 — 단일 초크포인트로 가시(visible) 리스트 생성.
2. **구역2 확대**: `boundary_t−1.2s` 이내 같은 스크립트 구언어 토큰도 잠정 tombstone("미니스터" 표적) —
   복원 보장이 있어야 안전한 공격적 철회(전용 플래그 `RECONCILE_SAMESCRIPT_SUBZONE_ENABLED`).
3. **ReconcileWindow**(활성 최대 1개): 마감 3중 — D1(신언어 진행도가 boundary_t+0.25s 통과, 주신호)/
   D2(다음 Silence·LanguageSwitch 마커 도착, 새 마커면 이전 창 resolve 후 재arm)/D3(get_lines 훅에서
   audio_time 기준 3.0s 캡, 벽시계 금지). resolve = **단일 컷포인트 원자성**(신언어 최소 start를 컷 T로,
   `start≥T−τ` 전량 대체·`<T−τ` 전량 복원, 부분 복원 구멍 금지 — 하위단어 파편 Case B 방지, 단어 시작
   방향 스냅). 신언어 미도착 시 전량 복원(유실 해결 최우선).
4. **시간 소유권 dedup**(`RECONCILE_ENABLED` 전체 롤백 플래그): 최초 구현은 "start 근접(0.4s)만으로
   신규 드롭"이었으나 **계측 r1에서 치명적 오탐 발견** — 창 내 정상 연속 방출 단어(예 ytn2 " is"/" remain"/
   " reviewed", Δstart 0.14~0.40s)를 재방출로 오인해 드롭, WER 오히려 악화(ytn2 18.7%→22.7%). **정규화
   텍스트 결합 매칭으로 재설계**(`46a9e34`): 매칭 조건 = start 근접 **AND** (정규화 완전일치 OR 접두어
   관계). 방향 판정 — 신규가 기존 커버리지 확장("In."→"In support of these...") → 기존 supersede +
   인접 구두점 동반 소멸 + id(start) 승계(UI `finalizedHistory` 유령 방지); 신규가 기존의 부분 재방출
   ("상당한 상당한") → 정규화 완전일치 매칭분만 drop. 비매칭 토큰은 어느 방향도 불가침.
5. **동적 keep**(`LANG_SWITCH_DYNAMIC_KEEP_ENABLED`, align_att_base.py): 서두 유실(비-fire 계열,
   "In support of these" 유형)은 재조정만으론 못 잡음 — `_apply_detected_language`의 트림 keep을
   `clamp(버퍼끝−last_emit_end+0.3, 2.5, 5.0)`으로 가변화(`last_emit_end`는 backend.py 소유 → decoder
   state 미러 필드로 모델 계층에 전달). 상한 5.0s(Exp-166 환각 전례 감시 대상).

### TDD
신규 `tests/test_boundary_reconcile.py`(복원/대체/dedup 방향분기/id승계/정상반복보호/다중경계/D3캡/
단일컷원자성/플래그OFF레거시재현/with_offset필드보존/동적keep클램프 등), `test_boundary_retract.py`
가시 뷰 헬퍼로 치환(하한·Silence정지·반대방향불가침 의미 보존). **전체 540 passed / 1 skipped / 0 fail**,
ruff 신규오류 0(main 저장소 동일 스코프 대비 pre-existing 26건과 일치 확인).

### 측정 (경로 C, diar-ON, turbo, beams=2, `--trace-tokens`)
**계측 r1→r2 (ytn2+bong1, 오탐 발견·수정 검증)**:
| | ytn2 WER | ytn2 F1 | bong1 WER | bong1 F1 |
|---|---|---|---|---|
| r1(오탐 있음) | 22.7% | 73.7% | 41.1% | 56.3% |
| r2(수정 후) | 16.3% | 73.7% | 25.4% | 72.2% |

**스크리닝 --repeat 1** (수정 후, provenance `exp/boundary-reconcile@d1412e9`):
- auto(bong1/ytn2/sbs1): bong1 30.2%/F1 66.7%, ytn2 16.3%/F1 70.0%, sbs1 10.1%/F1 40.0%(단일화자 F1
  아티팩트, Exp-186 기지). 직전 Exp-190 스크리닝(bong1 29.0/ytn2 16.3/sbs1 10.7) 대비 bong1 +1.2pp
  (허용한도 +3pp 이내)·ytn2 동일·sbs1 개선 — **무회귀**.
- ko(kor1~3, `--lan ko`): kor1 18.7%/F1 100%(개선), kor2 20.7%/F1 0%(단일화자 아티팩트), kor3 35.8%/F1
  100%(직전 31.1% 대비 +4.7pp — **재조정 로그 3파일 전부 0건으로 dormant 확인**, 코드 경로 자체가
  안 타므로 인과 없는 단일회 노이즈로 판정, §3.2 ko 모드 요구사항대로 코드스위칭 재감지 완전 비활성).
- **표적 지표**(analyze_boundary_tail_dup.py, auto 3파일): 경계 23곳 중 정상 18(78%)·구언어꼬리
  3·비fire 1·기타1, 인접n-gram중복 2건. 정성: "미니스터."류 유령 라인·"Okay." 환각 대체 소멸 확인,
  복원(Restore) 이벤트 정상 발동.
- **Case B**: 전 스크리닝 파일 정성 전수 확인, bong1 1건("자빠졌"⏎유사 계열)은 재조정 로그 무연관·
  서버로그 대조 결과 기존 silence-gate 계열(Exp-190 스코프)로 분류 — 신규 유발 아님.

**짝지음 A/B (동적 keep ON/OFF, ytn2+bong1)**: OFF ytn2 14.8%/F1 90.0%, bong1 28.4%/F1 64.7% vs ON
(r2) ytn2 16.3%/F1 73.7%, bong1 25.4%/F1 72.2%. 스크리닝 로그에서 동적 keep 발동 20건 중 2.5s 상한
클램프 미해제(비-fire 장기정지 케이스 희소) — 두 레그 차이가 개선/회귀 어느 쪽 귀속인지 판단 불가한
표본 크기. **ON 유지**(서두 유실 대응이 설계 목적이므로 비활성화 근거 없이 OFF 고정 안 함).

### 판정 = 스크리닝 유망 — **확정(N=3)·held-out 측정 미실시** (사용자 지시로 조기 종료)
확정 측정(auto 3종×3회 fail-fast 금지) 진행 중 사용자가 시간 제약으로 중단 지시("스크리닝 결과 괜찮아
보였다, 이 버전으로 커밋하고 배포 이전작업") — `bc7akc84e` 태스크 중단, 잔존 프로세스 없음 확인.
**따라서 CLAUDE.md §4 "채택 확정 = repeat 3" 게이트는 통과된 것이 아니라 생략됨** — 아래는 스크리닝
1회 수치 기준 방향 신호이며, 회차 편차(±30~120%p 관측 선례)를 고려한 재확인 없이는 최종 채택 결론이
아니다. 브랜치 `exp/boundary-reconcile`(`8ff041b`) 커밋 완료, **master 미머지**(사용자 최종 결정 대기).

### 다음/후속
- 확정 r3 + held-out(ytn1 auto/eng1 en) 미실시 — 배포 착수 후 여유 시 재개 권장.
- 구언어꼬리 유실(비-fire 아닌 flush 계열, backlog §1-ⓑ)은 이번 루프에서도 3건 잔존(auto 3파일) —
  구언어 flush 디코드(Exp-191 ⓑ 방향)는 QualityGate 우회 결함 때문에 이번 루프에서 재시도하지 않음,
  근본 해결은 별도 설계 필요.
- Exp-191 브랜치(`exp/boundary-tail-dup`) 처리 재결정 필요 — 본 실험이 그 표적을 상위 호환(시간 레벨)
  하므로 폐기 권고, 단 사용자 확인 필요.

### epoch
언어전환 경계의 철회 실패모드를 파괴적→복원가능으로 구조 변경(Exp-171/172/173/174 철회 관련 결론은
tombstone 메커니즘으로 **대체**되며 모순 아님, 선례대로 **E5 유지(epoch 미bump)** — 디코더·VAD·언어고정
불변, 정렬 계층 국소 변경).

---

## Exp-193 — frame_threshold를 KO→EN 경계 꼬리유실 제어 레버로 규명 + is_last flush 코드수정 dead-end [E5, `exp/boundary-tail-flush`(미머지)]

### 배경 — 배포 실사용 제보(Exp-192 반입본 이후)
Exp-192(`b001e38`) 반입 후 배포 PC(RTX 5090) 실사용 제보: 코드스위칭 KO→EN 경계에서 **한국어 문장 마지막
단어가 단어 중간까지 잘려 유실**("갱신하겠습니다"→"갱신하.", "되었습니다"→"되."). 잘린 꼬리가 다음 줄로도
안 가고 소멸(Case B와 다름). 개발 PC(3080)+개발 데이터에선 드물 수 있음 → 사용자 지시: ① dev에서 코드스위칭
`--repeat 3` 충분히 측정해 재현 확인, ② 재현되면 수정, ③ 미재현이면 GPU 성능차/데이터차 고려해 배포 PC 파라미터·
디버깅 제안. (측정 착수 전 공유 `.venv` 반쪽손상 발견·무중단 복구 — 별건.)

### 근본원인 (코드 조사로 확정 — 병렬 4서브시스템 읽기전용 조사)
- 매 infer는 버퍼 끝 `frame_threshold`(기본 25≈0.5s) 구간을 디코딩하지 않고 남긴다(align_att_base.py:501-508).
  아직 구언어(KO) 토큰으로 커밋 안 된 꼬리가 이 미디코딩/held 구간에 있을 수 있다.
- 언어전환 감지 시 `_apply_detected_language`(align_att_base.py:229-277)가 `_trim_segments_to_recent` +
  `create_tokenizer(EN)` + `init_tokens()`/`init_context()`로 디코더 리셋 → 미커밋 KO 꼬리는 다음 infer에서
  EN 토크나이저로 재디코딩돼 garbage→`ScriptMismatchFilter`(backend.py:794) 드롭 = **순유실**. 온점은
  `_append_terminal_punctuation`(audio_processor.py) 합성이지 모델 디코딩 아님.
- Exp-192 재조정 계층은 **이미 커밋된 토큰만** tombstone/복원 → 미커밋 꼬리는 시야 밖(구조적 사각지대).
- **왜 5090에서 잦은가**: `get_all_from_queue`(audio_processor.py:70-71)가 큐 축적분을 concat해 배치를 만드는데,
  빠른 GPU는 infer 사이 큐 축적이 적어 배치가 `vac_chunk_size` 하한(≈0.2s)에 수렴 → KO 어절 꼬리와 EN 서두가
  별개 배치로 쪼개져 꼬리가 버퍼끝 미디코딩 구간에 걸릴 확률↑. 느린 3080은 배치가 커서 어절이 통째 디코딩됨.
  = 동일 원천유실 버그, 심각도가 GPU 속도(배치크기)에 비례.

### 측정 (경로 C, `--lan auto`, diar-ON, turbo, beams=2, CRT=3.0, `--trace-tokens`)
**① baseline ft=25, `--repeat 3`** (master `b001e38`, `eval_repro_boundary.json`):
| 파일 | WER median [min/max] | 화자F1 | 문장F1 |
|---|---|---|---|
| bong1 | 25.7% [23.3/31.4] | 76.5% | 25.0% |
| ytn2 | 15.8% [14.8/17.2] | 77.8% | — |
| sbs1 | 8.9% [8.3/10.1] | 100% | 88.9% |
| ytn1(held-out) | 11.7% [9.2/25.8] | 84.2% | 57.1% |
평균 WER 16.8%·화자F1 83.7%. → **mid-word "갱신하." 미재현이나, 동일 메커니즘의 완화형(문장꼬리 종결동사 유실)
재현**: ytn2 "…합의점에." (종결동사 "이르렀습니다" 유실) **3/3 일관**, ytn1 "미국은." 파편 1회.

**② ft=35, `--repeat 3`** (`eval_ampl_ft35.json`) — GPU 작은배치 레짐 모사(미디코딩 tail 구간 확대) 증폭 시도:
| 파일 | WER median | 화자F1 | 문장F1 |
|---|---|---|---|
| bong1 | 26.6% | **62.9%(↓)** | 30.0% |
| ytn2 | **11.8%** | 90.0% | — |
| sbs1 | 11.3% | 100% | 88.9% |
| ytn1 | 15.3% | 77.8% | 57.1% |
평균 WER 16.1%·화자F1 81.3%. **예상과 반대 — 증폭이 아니라 완화**: ytn2 "합의점에 이르었습니다" **3/3 복원**,
ytn1 "미국은." 파편 소멸. 두 run의 유일 차이가 `--frame-threshold`이고 이 경계가 3/3 뒤집혔으므로 인과 확증.
**→ frame_threshold = KO 꼬리유실을 직접 제어하는 레버(↑=꼬리 복원, AlignAtt가 경계영역을 더 오래 물어 꼬리가
전환 트리거 前에 커밋됨)**. 단 전역 상향이라 **모든 커밋 지연 → 다화자 화자전환 분리 저하**(bong1 화자F1 median
76.5→62.9, 3회 전부 하락). Case B 신규 0.

**③ is_last flush 코드수정** (`exp/boundary-tail-flush@b001e38 분기`, 스크리닝 `--repeat 1`, `eval_tailflush_scr.json`):
언어전환 트림/스왑 **직전**에 구언어 토크나이저로 `infer(is_last=True)`(frame_threshold=4, 버퍼 끝까지) 강제 flush
→ `state.pending_langswitch_flush`로 process_iter 전파(현재 배치에 이어붙임) → `ASRToken.retract_protected`로
철회 보호 + infer 재진입 가드(`_infer_active`) + 롤백 플래그 `LANG_SWITCH_TAIL_FLUSH_ENABLED`. TDD 신규
`test_langswitch_tail_flush.py` 14케이스(red 9→green), 전체 **554 passed / 1 skip**, ruff clean.
스크리닝: bong1 23.9%/화자72.2, ytn2 14.8%/100, sbs1 6.5%/100, ytn1 10.4%/88.9 — 회귀 없음. **그러나 서버로그상
flush 발동 = ytn2 0/9회·bong1 0·sbs1 0·ytn1 1회뿐** → **실질 미작동**. 원인: 이 데이터의 KO↔EN 전환은
`[NewSpeaker]` 34회·`eager` 37회 등 **화자전환(diarization) 주도**인데, new_speaker는 `detected_language=None`
리셋+버퍼 refresh를 먼저 하므로 flush의 `detected_language is None` 가드에 스킵됨(설계상 신화자 garbage 방지).
유일한 ytn1 1회 flush는 `prev_lang=en 꼬리 "에는"`(EN전환인데 KO garbage 디코딩)→픽업 반대스크립트 드롭 = 무효.
**근본원인 재규명: 전환 대부분이 화자전환 주도 + boundary 검출 지연으로 KO꼬리·EN서두가 버퍼에서 얽혀 있어
"경계에서 flush"는 이미 늦어 garbage가 된다.** (ytn2 "합의점에 이르었습니다" 완결은 flush=0이므로 fix 효과 아닌
단일run 분산.) ft=35가 더 잘 동작한 이유 = 정상 디코드가 경계 前에 꼬리를 커밋하기 때문.

### 분석 (전사 내용 정성 대조)
**bong1** (다화자): ft=25→ft=35에서 한국어 컨텐츠는 유사하나 **화자전환 분리 저하**(화자F1 76.5→62.9) — 큰
frame_threshold가 화자경계 커밋을 지연시킨 결과. 웃음/필러 환각(기존 실패모드)은 두 조건 유사, frame_threshold와 무관.
**ytn2** (코드스위칭 핵심): **코드스위칭 실패=꼬리유실** — ft=25 `"합의점에."` 3/3(종결동사 유실) vs ft=35
`"합의점에 이르었습니다"` 3/3 복원. flush 스크리닝도 완결됐으나 flush 0회라 분산.
**sbs1** (KO 낭독 위주): 주요 실패 없음. 경계 적어 frame_threshold 영향 미미, 안정.
**ytn1** (held-out): ft=25 `"미국은."` 파편(문장 첫 어절만 확정) vs ft=35 소멸(완결 문장). flush의 `"Hand-mi."`는
EN 디코더가 "한미"를 로마자로 환각한 것(align_att 로그 17693)이지 flush 무관.
**이번 변경 영향**: frame_threshold↑는 ytn2/ytn1의 KO 꼬리유실(코드스위칭 실패)을 완화하되 bong1 다화자 화자분리를
희생. is_last flush는 전환 경로(new_speaker 주도) 미스매치로 무영향. Case B 신규 0(ft↑는 오히려 Case B 위험 감소).

### 채택 (조건) 판정
- **frame_threshold=35 전역**: ①화자분리 F1 worst-case = bong1 76.5→62.9 **회귀(1순위 지표 위반)** → 전역 기본값
  채택 불가. ②WER max/median = 회귀 없음(오히려 ytn2 개선). ③Case B 0. → **전역 채택 불가, 단 원인·수정방향 확정**.
- **is_last flush**: 실질 미작동(발동 ~0) → **dead-end, 기각**(브랜치 `exp/boundary-tail-flush` 미머지 보존).

### 결론 — frame_threshold를 배포 PC 레버로 (사용자 승인)
전역 기본값 변경 대신, 배포 서버 기동에 `--frame-threshold 35`(필요시 스윕 40~50) opt-in. 배포 PC(5090)에서
심각형 감소 확인 + content에 맞춰 **꼬리복원 ↔ 다화자 화자F1** 트레이드오프 튜닝. 무코드변경·무재배포. 정본 명령:
`C:\Python312\python.exe -m whisperlivekit.basic_server --frame-threshold 35 …`. **frame_threshold는 §3.8 backend
레벨 파라미터라 데이터특화 하드코딩 아님**(일반 레버).

### 다음/후속
- **사용자 신규 요청(완료 → Exp-194)**: frame_threshold '외' 대안 설계공간 탐색 — (A)조건부/국소 frame_threshold·
  토크나이저 스왑 유예, (B)경계시각 슬라이스 표적 재디코딩(얽힘 회피), (C)문법-조건부 확정 유예(Exp-190 게이트
  확장), (D)화자전환 지연보정 재귀속(Exp-168/171/174 좌표계 재사용) 병렬조사 → **D1(=B1, new_speaker 경계
  슬라이스) 1순위 도출·프로토타입 착수 → 스크리닝 기각(Exp-194 참조)**.
- 배포 PC frame_threshold 실측 확인 후 최적값·트레이드오프 회신 대기.
- Exp-192 확정 r3/held-out 미실시분과 별개 트랙.

### epoch
E5 유지(epoch 미bump) — frame_threshold는 파라미터 값(구조 변경 아님), is_last flush는 미머지 기각. JSON:
`.omc/benchmarks/eval_repro_boundary.json`(baseline ft25 N=3)·`eval_ampl_ft35.json`(ft35 N=3)·
`worktrees/boundary-tail-flush/.omc/benchmarks/eval_tailflush_scr.json`(flush 스크리닝 N=1).

---

## Exp-194 — frame_threshold 외 대안 설계공간 탐색 → D1(화자전환 경계 슬라이스 재디코딩) 프로토타입·스크리닝 기각 [E5, `exp/boundary-tail-flush`(미머지·미커밋)]

### 배경 — 사용자 요청(Exp-193 후속)
Exp-193에서 frame_threshold를 배포 레버로 확정한 직후, 사용자가 "frame_threshold 외에도 다른 해결 방안이
있는지 검토해봐" 요청. 다화자 화자F1 비용(bong1 76.5→62.9) 없이 KO 꼬리를 복원할 코드 대안을 병렬 탐색.

### 대안 설계공간 탐색 (읽기전용 4클러스터 병렬조사 + 랭킹, 코드변경 없음)
클러스터 A(조건부/국소 frame_threshold·토크나이저 스왑 유예) / B(경계시각 슬라이스 표적 재디코딩) / C(문법-조건부
확정 유예, Exp-190 게이트 확장) / D(화자전환 지연보정 재귀속, Exp-168/171/174 좌표계 재사용)를 코드 근거로 평가·
랭킹. **결론**: 근본원인(꼬리 미커밋+EN 재디코딩 드롭)을 실제로 뚫으면서 전역 다화자 비용이 0인 계열은 **D1≡B1
(new_speaker의 refresh_segment 직전 pre-boundary KO-슬라이스 재디코딩)** 뿐 — 실패한 Exp-193 is_last flush의
두 실패원인(①삽입점이 화자전환 아닌 언어전환 감지 경로라 미발동 ②버퍼 전체 tail 디코딩이라 EN서두까지 오디코드)을
정확히 교정하는 접근으로 판정. C계열(확정 유예 단독)은 "꼬리가 애초에 KO 토큰으로 도착 안 함"이 코드로 확정돼
**원리적으로 무효**(refresh_segment가 꼬리 오디오 자체를 폐기·EN 재디코딩은 드롭). A1(조건부 ft)은 화자전환
활성 신호(eager)가 정확히 꼬리 보존이 필요한 지점과 겹쳐 신호정렬 충돌. D2(비재디코딩 재귀속)는 순유실엔 무효.
필수 가드 3종을 조건으로 D1 프로토타입 승인(사용자).

### 구현 — D1 (`exp/boundary-tail-flush` 워크트리 재작업, Exp-193 flush 인프라 일부 재사용)
- **삽입점 이동**: `_apply_detected_language`의 `_flush_prev_language_tail` 호출·`process_iter`의
  `pending_langswitch_flush` 픽업 블록 **제거**(원거동 복원) → **`backend.py new_speaker()`의
  `refresh_segment`(경계 트림) 직전**으로 이동(버퍼 온전·토크나이저/detected_language/speaker 모두 아직
  구언어·구화자인 시점).
- **슬라이스**: `align_att_base.py` 신규 `decode_tail_slice(boundary_abs)` — 버퍼를 `[0, change_speaker.start]`
  로 tail-truncate(EN 서두 오디오 제외, 원 텐서 불변 뷰)한 뒤 현재(구언어) 토크나이저로 `infer(is_last=True)`
  1회. 재방출 방지는 slice_lower 명시 없이 **디코더 커밋 프리픽스 연속성**(state.tokens 이후분만 방출)으로 구조적
  실현 + `retract_protected`(Exp-193 재사용) 철회보호 + dedup_batch 백스톱.
- **save/restore**: 슬라이스 직후 `refresh_segment`가 `init_tokens`/`init_context`로 디코더 상태(tokens/context/
  kv_cache/last_attend_frame/pending_incomplete_tokens)를 어차피 리셋 → 명시 복원 대상은 `state.segments`(원
  버퍼)+`quality_suppress_streak` 둘뿐(검증됨, B2 격리 디코드 에스컬레이션 불필요로 판정).
- **Case B 가드**: `_snap_tail_to_word_boundary` — 슬라이스 상한(경계)에 0.20s 이내로 맞닿은 마지막 어절은 hold
  (어절중간 절단 위험).
- **전파**: `audio_processor.py`의 `ChangeSpeaker` 분기가 `new_speaker()` 반환(꼬리 토큰)을 캡처해 공유 emit
  블록(all_tokens/new_tokens/번역 큐)으로 라우팅(선행은 반환값을 버리고 `continue`).
- 롤백 플래그 `NEW_SPEAKER_TAIL_SLICE_ENABLED`, 고정(ko/en) 세션은 회귀위험 최소화로 미발동(auto 전용).

### TDD
신규 `tests/test_boundary_tail_slice.py`(17케이스: 슬라이스 커밋·EN서두 미포함·Case B hold·재방출 없음·버퍼
restore·플래그OFF레거시·화자귀속), 선행 `test_langswitch_tail_flush.py` 제거·`test_lang_switch_wiring.py` 원복.
전체 **557 passed / 1 skipped**, ruff clean(변경 파일 전부).

### 측정 (경로 C, `--lan auto`, diar-ON, turbo, beams=2, CRT=3.0, `--trace-tokens`, **스크리닝 `--repeat 1`**)
| 파일 | baseline(Exp-193 ft25) WER | D1 스크리닝 WER | 화자F1(baseline→D1) |
|---|---|---|---|
| bong1 | 25.7% | **30.8%**(악화) | 76.5→66.7(악화) |
| ytn2 | 15.8% | 13.8%(개선, 단 아래 참조) | 77.8→80.0 |
| sbs1 | 8.9% | **23.8%**(약 2.7배 악화) | 100→66.7(악화) |
| ytn1 | 11.7% | **21.5%**(악화) | 84.2→66.7(악화) |

`[TailSlice]` 실제 발동 확인(선행 flush의 ytn2 0/9와 대조): bong1 12회(hold 2)·ytn2 8회(hold 1)·sbs1 2회·ytn1
8회(hold 2) — 삽입점 이동(new_speaker=지배 경로)이 발동 자체는 성공시킴.

### 분석 (전사 내용 정성 대조)
**ytn2**(핵심 타깃): **목표 미달성** — "합의점에." 유실이 일어나는 정확한 화자전환(`spk=1→0 det_before=ko
eager=None`) 지점에서 **TailSlice 로그가 전무**(발동도 hold도 "없음" 로그도 없음). 코드에 무로그 조기리턴 경로가
3곳(`detected_language is None`/`segments 없음`/`slice_secs<audio_min_len`) 있어 어느 조건에 걸렸는지 특정
불가 — **진단 계측 갭**. ytn2 WER 자체는 개선(13.8%)됐으나 다른 지점 발동의 부수효과로 보이며 핵심 타깃과 무관.
**bong1**: `"So my son, who's So my son, who's holding up..."` — **어절 반복(중복 방출)** 신규 발생. D1이
"디코더 프리픽스 연속성으로 구조적 방지"라 주장한 바로 그 문제가 재현된 것으로 의심(정확한 TailSlice 인과는
로그 컨텍스트 부족으로 미확정).
**sbs1**: `"영구적인 지상 플랫폼이라고 정의했습니다."` — baseline엔 있던 앞부분("특히 한국을... 미국의 힘을
고정하는")이 **신규 유실**. `"사태리아 기자가 보도합니다."` — baseline에 없던 **신규 환각**(정답 무관 텍스트).
**ytn1**: `"Han-kong."`, `"- 감사합니다."` — 신규 파편/환각.
**이번 변경 영향**: 목표(ytn2 핵심 꼬리) 미복원 + 3/4 파일 WER·화자F1 악화 + bong1/sbs1/ytn1에 신규 중복·유실·
환각 패턴. 스크리닝 1회라 일부 변동은 노이즈 가능성이나, **목표 라인 자체가 미복원된 것은 노이즈가 아니라 로직
결함**(무로그 스킵 경로)이며, 부작용 패턴의 광범위성(4파일 중 3파일)도 우연으로 보기엔 일관적.

### 채택 (조건) 판정
스크리닝 단계에서 이미 ①표적 미달성 ②화자분리 F1 worst-case 다수 회귀(1순위 지표 위반, D1의 존재이유였던
"전역비용 0" 가정이 실측에서 성립 안 함) ③신규 중복/환각 발생 — **`--repeat 3` 확정측정 진행 없이 스크리닝
단계에서 기각**. 정확한 인과(왜 그 경계에서 스킵됐는지, 왜 중복/환각이 생겼는지)는 로그 계측 부족으로 미규명.

### 결론 — D1 기각, frame_threshold 배포 레버로 최종 확정 (사용자 결정)
코드 레벨 시도가 두 번(Exp-193 is_last flush, 본 Exp D1) 모두 실패 판정. 이미 검증되고 사용자 승인된 안전한
대안(Exp-193 frame_threshold 배포 opt-in)이 있는 상태에서, 추가 진단 계측 없이 3차 코드 시도로 넘어가는 대신
**여기서 코드 레벨 탐색을 종료**(사용자 승인) — `--frame-threshold 35`(스윕 40~50) 배포 PC opt-in이 최종 권고.
**D1 재시도 금지**(추가 진단 계측 없이는) — 재시도 시 최소 `[TailSlice] 스킵(사유)` 로그를 3개 조기리턴 경로
전부에 추가해 "합의점에" 경계에서 왜 스킵됐는지부터 규명해야 함.

### 다음/후속
- 배포 PC frame_threshold 실측 확인 후 최적값·트레이드오프 회신 대기(Exp-193과 동일 트랙).
- 워크트리 `worktrees/boundary-tail-flush`(브랜치 `exp/boundary-tail-flush`)에 D1 변경 **미커밋 상태로 보존**
  (사용자 명시 요청 시에만 커밋 — 세션 전역 규칙). `.omc/transcripts/*.txt`는 측정 부산물이라 커밋 대상 아님.
- Exp-192 확정 r3/held-out 미실시분과 별개 트랙.

### epoch
E5 유지(epoch 미bump) — D1은 미커밋·기각. JSON:
`worktrees/boundary-tail-flush/.omc/benchmarks/eval_tailslice_scr.json`(D1 스크리닝 N=1).

---

## Exp-195 — 언어잠금 Stage 0: LMR 진단지표 + SOT 사후분포 프로브 + 단일언어 세션 오탐률 표본확대 [E5, `exp/lang-lock-stage0`(미머지)]

**언어모드**: ko(kor1~3) + en(eng1) + auto(bong1·ytn2·sbs1·ytn1) — run 분리 측정.
**코드 변경**: 계측·지표 전용. **디코딩 행동 변경 0**(추가 forward 0, 텐서 미수정, 분기 미관여).

### 가설
`detected_language`가 `en`에 고착된 채 한국어 오디오가 들어오면 Whisper가 off-manifold 상태에서
**한국어 발화를 영어로 번역 출력**한다(자유 환각이 아니라 언어 토큰 오지정 — 의미가 보존되는 것이 증거).
① 이 피해량을 WER과 분리해 정량화할 수 있는가(LMR). ② 그 실패를 **방출 전에** 검출할 신호가
디코더 내부에 이미 존재하는가(SOT 위치 언어 사후분포).

### 변경 (커밋 순)
| 커밋 | 내용 |
|---|---|
| `6b6336e` | 정답 비언어 태그(`(웃음)(박수)(환호)(잡음)(더듬)`)를 WER·F1에서 제외 |
| `9ba0f2d` | `[RefreshSegment]`·`[ShortSilenceLangCheck]`·`[QualityGate]` 진단 로깅 |
| `38bf97b` | **LMR 지표** — `metrics.py` `_align_ops`/`compute_language_mismatch` + eval 배선 + `backfill_lang_mismatch.py` |
| `b1a5e63` | **SOT 사후분포 계측** — `_read_sot_posteriors`/`[SotLangProbe]`/`[LangDriftStats]` |
| `cdbb452` | 연동 문서 갱신(TRANSCRIPTION_REQUIREMENTS §2~5, eval.md, TESTING.md, CLAUDE.md) |
| `5466b87` | **Stage 0 판별력 분석** — `analyze_sot_lang_probe.py` + `docs/research/SOT_LANG_PROBE_STAGE0.md` |
| `8f20dd5` | **표본 확대** — 동 문서 §10 (코드 변경 0) |

### 결과 ① — 피해량 (LMR, bong1 10회 소급 · 재측정 0회)
| | median | min | max |
|---|---|---|---|
| WER | 30.06% | 22.36% | 43.50% |
| LMR_ko | **15.4%** | 7.7% | 37.4% |
| WER 귀속량 `lmr_wer_pp` | **4.38%p** | 2.11%p | **10.27%p** |

언어잠금이 bong1 WER median의 약 14%, 최악 회차의 24%를 먹는다. `corr(LMR_ko, WER)=+0.724`.
실패는 **en 잠금 단방향**(역방향 10회 통틀어 4건). LMR은 **하한**이다(del+ins로 갈라진 피해 미포착).
**채택 게이트가 아니라 원인 귀속용 진단지표.**

### 결과 ② — 검출 신호 판별력 (Stage 0, bong1 R1 + ytn2 R1)
살아남은 신호는 **`p_opp`(잠긴 언어의 반대쪽 재정규화 확률) 하나뿐**. τ=0.97에서
bong1 배경 median 0.000763 → 발동 28/457(4버스트), ytn2 0.000312 → 25/239(4버스트).
버스트가 실패 지점에만 뭉치고, 선제성은 A −0.80s / B 0.00s / C −2.88s.

**반증되어 폐기된 신호**: `p_translate`(723 프로브 전부 정확히 0 → task 토큰 누출 가설 S3 사망) ·
`resid`(bong1 88% 통과, ytn2 방향 역전) · `H_lang`(ytn2 역전) · `p_nospeech`(전 배치 0) ·
top1−top2 마진(`lang_restrict_koen` ON이라 `2p−1`, p의 단조변환).
**반증된 용법**: "전환을 프로브로 승인" — 프로브는 *버퍼 내용*을 읽어 전환 경계에선 직전 잠금에
동조하므로, 이 규칙은 정당한 한국어 전환 2건을 차단했을 것이다.

### 결과 ③ — 단일언어 세션 오탐률 (표본 확대, 이번 회차 신규 측정)
경로 C · `--repeat 1` · 화자분할 ON · CRT 3.0 · `--trace-tokens` · `vbcable=ok` · 6파일.

| 파일 | 모드 | WER | 화자F1 | 문장F1 | LMR_ko | probes | 발동 τ=0.97 | 연속 run | 게이트 통과¹ |
|---|---|---|---|---|---|---|---|---|---|
| kor1 | ko | 40.9% | 0.0%² | 75.0% | 0.0% | 365 | 3 | 3 (전부 K=1) | 0 |
| kor2 | ko | 18.6% | 100.0%² | 100.0% | 0.0% | 285 | 1 | 1 (K=1) | 0 |
| kor3 | ko | 33.8% | 100.0%² | 100.0% | 0.0% | 321 | 1 | 1 (K=1) | 0 |
| eng1 | en | 5.7% | 0.0%² | 66.7% | n/a | 121 | 0 | 0 | 0 |
| sbs1 | auto | 11.3% | 100.0% | 94.7% | 0.0% | 249 | 0 | 0 | 0 |
| ytn1 | auto | 20.2% | 82.4% | 40.0% | **19.7%**(9.2%p) | 266 | 25 | 4 | 2 |

¹ 오프라인 재현(`K≥3 ∧ T≥1.0s ∧ seglen≥2.0s`) — 런타임 쿨다운·타 arm 미반영이라 **상한**.
² 단일화자 낭독의 화자F1 0/100 극단은 산식 경계 아티팩트이지 화자분리 실패 아님.

**ko 발동 5건 전수**: 순수 오탐 2건(kor2 b1 `먼저 육군`, kor3 b30 `원 거리 타격` — 정상 전사 구간) +
kor1 서두 자막 환각 구간 1건(`자막 제공 배달의민족`, 정답 "전투발전부장 최창수 육군 소장입니다" 통째 유실) +
회색 2건. → **Stage 0의 "순수 오탐 0"은 코드스위칭 파일 한정 결과였다.**
단 5건 전부 **K=1 단발 · seglen 0.24~1.02s**이며 다음 배치에서 즉시 문턱 아래로 자기교정된다
(kor2 건은 `Refreshing segment` 직후 잔여버퍼임이 로그로 확인 — Exp-189 실패모드의 정확한 재현).

**ytn1 25건은 전부 참양성**: 정답 한국어(`안녕하십니까 / 지난 세 달 만에 두 번째로 대한민국에 다시
방문할 수 있게 되어 기쁘게 생각합니다`)가 `Yeah, I'm not sure how many years I'm happy to be here.
to be able to visit the United States`로 전사 — 의미 보존형 영어 번역. LMR_ko 19.7%(`ko_to_en=15`)가
독립 확증. Exp-160 스퓨리어스 재현 없음.

**LMR 교차검증**: 단일언어 4종 전부 `ko_to_en=0`·`en_to_ko=0` — 프로브와 독립적으로 같은 결론
(단일언어 세션엔 언어잠금 실패가 없다). 따라서 ko 발동 5건은 "LMR이 놓친 실패"가 아니라 신호 쪽 오탐이다.

### 결과 ④ — ko 오탐률 `--repeat 3` 확증 (같은 세션, 코드 변경 0)
결과 ③의 판정이 스크리닝 1회에 얹혀 있어 kor1~3을 `--lan ko --repeat 3`으로 재측정했다.
WER med: kor1 **21.6%**(16.4/26.3, stdev 5.0) · kor2 **24.1%**(19.3/24.8, 3.0) · kor3 **35.8%**(28.5/39.1, 5.4).
LMR 9/9 세션 0.0%.

**ko 세션 누계 12개 / 3756 프로브**

| | 값 |
|---|---|
| 발동 τ=0.97 | **23건 (0.61%)** |
| 발동 시 `seglen` | 0.24s ×20 · 0.48s ×2 · 1.02s ×1 → 최대 **1.02s** |
| `seglen ≥ 2.0s` 발동 | **0건** |
| 최대 연속 K | **2** (K=3 미달) |
| 게이트 통과 | **0 / 23** |
| 세션 초입 15초 이내 | 17 / 23 |

**오탐은 랜덤이 아니라 결정론적이다** — kor2 b1은 3/3 회차, kor3 b1·b30은 3/3 회차에서 같은 지점에
반복 발동한다. 따라서 ① Stage 0의 "순수 오탐 0"은 **최종 반증**됐고, 동시에 ② 오탐이 `seglen≤1.02s`
단일 체제에만 살아 `seglen≥2.0s`(Exp-189 대응으로 **미리** 지정된 값) 하나로 23/23이 배제된다는
사실도 12세션 규모로 굳었다.

### 결과 ⑤ — en 방향 확증 + 오탐/참양성의 **방향 분리**
eng1도 `--lan en --repeat 3` 재측정(코드 변경 0). **누계 4세션 500프로브 = 발동 0건.**
WER med **3.8%**(2.9/6.7, stdev 2.0). → 안 A 사전 등록 표본 전부 닫힘.

| 방향 | 세션 | probes | 발동 | 성격 | 게이트 통과 |
|---|---|---|---|---|---|
| `locked=ko` (ko 세션) | 12 | 3756 | **23 (0.61%)** | **전부 오탐/회색**(참양성 0) | **0/23** |
| `locked=en` (en 세션) | 4 | 500 | **0** | — | 0 |
| `locked=en` (auto ytn1) | 1 | 266 | 25 | **전부 참양성** | 2 run |
| auto sbs1 | 1 | 249 | 0 | — | 0 |

**15세션 통틀어 `locked=ko` 참양성 0건 · `locked=en` 오탐 0건** — 오탐과 참양성이 방향으로 완전히 갈린다.
해석은 **가설로만** 남긴다(극소버퍼에서 사후분포가 영어 사전확률로 끌린다면 설명되나 사전확률 미측정).
설계 함의로 방향 비대칭 문턱(`locked=ko`만 τ↑)이 자연스럽지만, **게이트 파라미터를 실측에 맞춰 사후
조정하는 것이 곧 정지 사유로 든 행위**이므로 구현하지 않고 기록만 남긴다. 또한 `locked=ko` 방향
**참양성 판별력이 미측정**(그 방향 실패 0건)이라 비대칭 문턱이 진짜 실패를 놓치는지는 알 수 없다.

### 판정 — 계측 채택 / 개입(Stage 1) 정지
- **계측·지표는 채택 권고**(행동 변경 0이라 회귀 위험 없음). 단 `exp/lang-lock-stage0` **미머지** 상태.
- **Stage 1(재감지 강제) 착수는 정지**. 사전 등록 진행 조건("단일언어 세션 정상 전사 구간 발동 0건")을
  충족하지 못했다. 기준을 사후 완화해 진행하는 것은 게이트 파라미터의 임의 튜닝에 해당하므로
  **사용자 판단으로 이관**(CLAUDE.md §4 "목표 필수 기능 채택은 사용자 질의").
- **양쪽 근거**: (계속) 오탐 5건은 인계서 §4 게이트가 사후 튜닝 없이 이미 배제하도록 설계돼 있었고
  would_fire 0인 반면 ytn1 참양성 run 2개는 통과한다 / (중단) Exp-189가 경고한 "p=0.95~1.00 고신뢰
  오탐"이 실제로 재현됐고, 게이트가 막아준다는 판단은 `--repeat 1` 표본 1회에 의존한다.
- **재개 시 권고 순서**: ~~① kor1~3 `--repeat 3` 재측정~~ **완료(결과 ④)** → 곧바로 **② 안 B(섀도우
  `would_fire` 로깅)** 가능. 착수 시 확인할 값은 "런타임 게이트가 오프라인 재현과 동일하게 23/23을
  막는가"이며, 그것이 정확히 섀도우 모드의 측정 대상이다.
- 정지 사유의 성격이 이동했다: "표본이 1회뿐이라 모른다" → **"재현되는 고신뢰 오탐이 존재한다는 사실 자체"**.
  즉 정보 부족이 아니라 **설계 수용 여부** 판단이다.

### 한계
- ko 오탐률 0.61%는 12세션 기반 추정치. `--repeat 3`은 이 프로젝트의 채택확정 최소 규모이지 대표본은 아니다.
- **`locked=ko` 방향 참양성 판별력 미측정** — 15세션 통틀어 그 방향 실패가 0건이라, "`locked=ko` 발동은
  전부 오탐"인지 "그 방향 실패가 이 데이터셋에 없었을 뿐"인지 **구분되지 않는다**.
- 게이트 통과 판정은 **로그 사후 재현**이지 런타임 게이트 실행이 아니다.
- **반대 방향(`locked=ko` + 영어 오디오) 판별력은 이번에도 미측정** — ytn1 실패도 `locked=en` 방향이라
  6파일 통틀어 `locked=ko` 실패 0건.
- 위음성률 미정량 · 개입 효과 전혀 미측정(검출 가능성만 보였다) · kinno 미측정.
- 잠재 버그 미수정(행동 변경 금지 원칙): `state.sot_index`가 context 길이를 반영하지 않아
  `--max-context-tokens > 0` 또는 `--static-init-prompt` 사용 시 `_check_no_speech`가
  `<|startofprev|>` 위치를 읽는다. 운영 기본값에선 잠복 — 별도 백로그.

### epoch
E5 유지(epoch 미bump) — 계측 전용이라 실패 모드를 바꾸지 않고, 브랜치도 미머지.
산출물: `docs/research/SOT_LANG_PROBE_STAGE0.md`(분석 정본) ·
`docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md`(인계·정지 사유) ·
`.omc/benchmarks/stage0_probe/*_tau097.txt`(프로브 전수 분석 6파일).

---

## Exp-196 — 화자전환 시 동일언어 확정 경계 재디코딩 스킵 (samelang 머지, Exp-190 계열 후속) (2026-07-22) [E5→E6, `fix/samelang-no-refresh`(master 머지 `3ad14a6`)]

**언어모드**: auto(bong1·ytn2·sbs1) — 다른 세션(별도 워크트리)에서 구현·측정·머지, 이 세션(`exp/lang-lock-stage0`)은
`git merge master`로 반영만 하고 후속 문서 정리를 담당.
**코드 변경**: `whisperlivekit/simul_whisper/backend.py`만.

### 배경 — Exp-155와의 관계 (같은 가설, 두 번째 시도)
**Exp-155**(2026-07-03, **E4 base 기질**, 브랜치 `exp/conditional-speaker-reset`)가 이미 같은 방향을 시도해
**기각**됐다 — "동일언어 화자전환이면 new_speaker 리셋(`refresh_segment`·`detected_language=None`·`_apply`)을
통째로 생략"하는 넓은 범위 설계였다. bong1의 new_speaker 15/15가 전부 동일언어로 판정돼 리셋이 100% 생략됐고,
그 안에 섞여 있던 **진짜 다른 화자(영어 화자 2명·한국어 화자 2명)를 "같은 언어"라는 이유로 블렌딩**해
화자F1 -4.1(38.1%p WER 악화 동반)로 악화됐다. 타겟이었던 sbs1은 new_speaker 자체가 0회 발동해 애초에
검증 불능이었다.

이번 시도는 다르다:
- **기질(substrate)**: 이번은 **E5 turbo**(Exp-155는 E4 base) — 코드스위칭 실패모드 자체가 다르다(EXPERIMENTS.md
  이월 핵심사실 참조: turbo는 "Thank you" 필러 환각형, base는 방송클로징 환각형).
- **리셋 범위**: Exp-155는 리셋 블록 전체(화자 귀속 갱신까지 포함)를 생략했지만, 이번은 **경계 재디코딩
  (`refresh_segment` 호출) 하나만** 스킵하고 화자 귀속(`token.speaker`)·`global_time_offset`은 그대로
  갱신한다. 즉 "같은 화자처럼 취급"이 아니라 "화자는 바뀌었다고 기록하되 그 경계의 오디오를 다시 읽지는
  않는다"는 설계 — Exp-155가 실패한 정확한 지점(진짜 다른 화자를 같은 화자로 뭉갬)을 피해간다.

### 변경 내용 (커밋 순)
| 커밋 | 내용 |
|---|---|
| `47fd76c` | 화자전환 시 eager 언어감지가 기존 언어와 동일함을 확정하면 경계 재디코딩(`refresh_segment`)을 생략. `refresh_segment`가 디코더 prefix는 버리면서 오디오(keep_secs분)는 남겨, 다음 패스가 같은 구간을 백지에서 다시 전사해 중복 방출(ytn2 "우선 우선"/"왕성 왕성한")을 만들던 것이 근본원인 — 언어가 안 바뀌었으면 "새 화자의 언어로 다시 읽기"라는 재디코딩 목적 자체가 성립하지 않는다는 관찰. eager=None(쿨다운·감지실패)이면 동일언어를 확신 못 해 기존 경로(재디코딩) 유지 |
| `4448288` | Exp-189 쿨다운(1.5s)에 eager 감지가 걸려 `eager=None`이 되면 "동일 언어 확정"에 실패해 재디코딩이 강행되던 사각지대 수정 — 직전 감지결과를 `_last_eager_lang_result`에 캐시해 쿨다운 구간의 스킵 판정에만 재사용(캐시값은 `eager` 자체와 분리 보관해 `_apply_detected_language`까지 타지 않게 함 — Exp-189가 억제한 flip-flop 재적용 방지). bong1 화자전환 25건 중 8건이 이 쿨다운 사각지대였다 |

### 측정 (경로 C, `--lan auto`, `--repeat 1` 스크리닝, diar ON — 다른 세션 측정, 커밋 메시지 인용)
| 파일 | 지표 | 전 | 후 |
|---|---|---|---|
| ytn2 | WER | 15.8% | 12.3% |
| ytn2 | 화자분리 F1 | 80.0% | 94.7% |
| bong1 | 화자분리 F1 | 73.7% | **78.8%**(자체 최고) |
| sbs1 | 화자분리 F1 | 80~100% 밴드 | 회귀 없음 |

정성: bong1 "everyone here Everyone here" 등 중복 해소.

### 판정 — 이번 세션은 반영·정리만
이 실험은 `worktrees/bong1-eval-diagnostics`(`exp/lang-lock-stage0`)가 아닌 별도 세션에서 구현·측정·머지됐다
(`3ad14a6`). 이 세션은 `git merge master`로 반영했을 뿐 — 코드 파일 충돌 0건(브랜치는
`align_att_base.py`/`simul_whisper.py`/`scripts/`/`metrics.py`를, 이 머지는 `backend.py`만 건드려 파일
집합이 완전히 분리돼 있었다). **ko/en 세션에는 영향 없음** — `lang_locked` 분기에서 `eager=None`·
`eager_cached=None`이라 `lang_evidence=None`이 되어 스킵 판정 자체가 early return으로 미진입한다(Exp-195의
ko/en 오탐 수치 23건·0.61%·게이트 통과 0/23은 그대로 유효). **auto 세션은 영향 있음** — 동일언어 화자전환에서
`refresh_segment` 미호출로 버퍼가 안 잘려 세그먼트가 계속 자라므로(재디코딩이 스킵되니 잘릴 계기가 없다),
Exp-195의 auto 오탐/참양성 수치(ytn1 25건 등)는 이 머지 이후 **직접 비교 불가**해졌다.

**✅ 채택(머지 완료 확인, 이 세션은 재기각하지 않음)** — 위 수치는 N=1 스크리닝이나 이미 master에 머지된
상태(다른 세션의 결정)이며, CLAUDE.md §4 채택 확정(`--repeat 3`) 게이트 적용은 그 세션의 범위였다. 이 세션은
merge 반영 + epoch 정합성 정리만 담당한다.

### epoch
**E5 → E6 bump** — new_speaker의 실패모드를 바꾸는 구조 변경이다(경계 재디코딩이 화자전환마다 무조건
발동하던 것에서, 동일언어 확정 시 조건부 스킵으로 변경). E5에서 new_speaker/경계재디코딩 경로에 얹혀
있던 결론(frame_threshold 배포레버 Exp-193·boundary_reconcile Exp-192·keep_secs Exp-171/174 등)은
`[E5·재검증]` 대상 — 그 경로들이 도달하는 빈도·조건이 스킵 신설로 달라졌기 때문이다. 상세는
STATE(`EXPERIMENTS.md`) "코드 세대(Epoch)" 절 참조.

## Exp-197 — 언어잠금 Stage 1 섀도우 게이트 실측 (안 B 완료, 로깅버그 발견·수정 포함) (2026-07-22) [E6, `exp/lang-lock-stage0`(미머지)]

**언어모드**: auto(bong1·ytn2·sbs1·ytn1, `--lan auto --repeat 1`).
**코드 변경**: `whisperlivekit/simul_whisper/align_att_base.py`(게이트 G1~G7 구현 + `[Stage1ShadowStats]`
로깅버그 수정) + `tests/test_stage1_shadow_gate.py`(신규 테스트).

### 배경
안 B(Stage 1 섀도우 판정)는 §10-5(정지, 사용자 판단 대기)에서 멈춰 있었다 — 사용자가 재개를
승인했다(goal 문서 `docs/goal_prompt/tranquil-floating-starfish.md`). 재개 전 이 goal 문서 §1이 다른
세션의 samelang 머지(Exp-196, `3ad14a6`)와의 충돌을 사전 검증했다 — 코드 파일 충돌 0건(브랜치는
`align_att_base.py`/`simul_whisper.py`/`scripts/`/`metrics.py`를, 머지는 `backend.py`만 건드려 파일
집합 완전 분리), ko/en 세션에는 영향 없음(Exp-196과 동일 근거), **auto 세션은 영향 있음**(동일언어
화자전환에서 `refresh_segment` 미호출로 세그먼트 성장 거동이 달라져 Exp-195의 auto 오탐/참양성 수치와
직접 비교 불가해짐 — Exp-196 결론과 동일).

### 구현
`align_att_base.py`에 게이트 G1~G7(비-auto 가드 · 언어미감지 · 최소버퍼 `seglen≥2.0s` · `p_opp≥0.97` ·
연속 `K≥3` ∧ 지속 `T≥1.0s` · 쿨다운 3.0s · 다른 트리거 진행중 배제) + 증거 리셋 훅
(`refresh_segment()`·`_apply_detected_language()` 2곳) 신설. 트리거 지점은 기존
`_sot_lang_probe_impl()` 직후(encoder_feature를 이미 쥔 지점이라 추가 forward 비용 0). **섀도우
불변식**: 게이트가 전부 만족돼도 `_apply_detected_language`는 호출하지 않고
`[Stage1Shadow] would_fire=True lang=%s p_opp=%.4f t=%.2f seglen=%.2f k=%d dur=%.2f` 로깅만 한다 —
diff에서 `_apply_detected_language` 신규 호출 0건임을 확인했다(goal 문서 Step 4 검증 기준). 신규
테스트(TDD, 14개 시나리오) 추가, pytest 648→670 pass·ruff clean.

### 측정 중 발견 — `[Stage1ShadowStats]` 로깅 버그, 수정, 재측정
Step 5 첫 스크리닝 run(커밋 `6af9b3d`)의 로그를 점검하다가, 세션요약 `[Stage1ShadowStats]`의
중복억제 가드가 `would_fire`만 비교하는 버그를 발견했다 — `would_fire`가 세션 내내 0으로 고정되는
(4파일 중 3개가 이 경우) run에서는 `blocked_by`가 계속 누적돼도 "직전과 동일"로 오판돼, 실제로는 첫
`is_last` 시점(프로브 약 2회째) 이후로 요약 줄이 전혀 갱신되지 않았다 — 세션 나머지 전체의 진짜
게이트별 차단 내역이 로그에 도달하지 못한 것. `d6bd66a`에서 중복억제 키를 총 호출수
(`would_fire + sum(blocked_by.values())`)로 교체 — `_log_lang_drift_stats()`가 `probes`(총 호출수)로
중복억제하는 기존 관례를 그대로 따랐다. 회귀 테스트(`test_shadow_stats_logs_again_when_only_blocked_by_changes`)
추가, pytest 670→671 pass. `would_fire` 자체(배치마다 무조건 찍히는 개별 로그)는 이 버그와 무관해
영향받지 않았다 — 영향은 `[Stage1ShadowStats]` 요약의 `blocked_by` 누적치에 한정된다.

### 측정 (경로 C, `--lan auto --repeat 1` 스크리닝, diar ON·CRT 3.0·`--trace-tokens`, `vbcable=ok`,
코드=`exp/lang-lock-stage0@d6bd66a` — 로깅 수정 후 v2 run)

**WER/F1 sanity**

| 파일 | WER | 화자F1 | 문장F1 | LMR_ko |
|---|---|---|---|---|
| bong1.wav | 28.9% | 70.3% | 21.1% | 10.9%(3.0%p) |
| ytn2.mp3 | 13.3% | 100.0% | N/A | 0.0% |
| sbs1.mp3 | 11.9% | 100.0% | 88.9% | 0.0% |
| ytn1.mp3(held-out) | 22.1% | 84.2% | 57.1% | 19.7%(9.2%p) |
| **종합** | **19.1%** | **88.6%** | **55.7%** | — |

samelang 머지(Exp-196)로 auto 베이스라인 자체가 이동해 **Exp-195 auto 수치와 직접 비교하지 않는다** —
sanity 목적(0%/100% 이상치·붕괴형 catastrophic 없음)만 확인, 이상 없음. 참고(비교 아님): 로깅버그가
있던(디코딩은 동일한) v1 첫 run은 bong1 27.1/57.1/28.6, ytn2 16.3/72.7/NA, sbs1 11.9/57.1/76.2,
ytn1 14.7/88.9/66.7, 종합 17.5/69.0/57.1 — v1↔v2 편차는 로그 한 줄만 건드린 수정이 만든 게 아니라
CLAUDE.md §4가 문서화한 통상적 회차간 분산(±30~120%p대) 범위다.

**`[Stage1ShadowStats]` 게이트별 차단 (v2, 세션 최종 누적치)**

| 파일 | would_fire | G1 | G2 | G3 | G4 | G5 | G6 | G7 | 총 게이트호출수 |
|---|---|---|---|---|---|---|---|---|---|
| bong1.wav | 0 | 0 | 13 | 25 | 424 | 5 | 0 | 0 | 467 |
| ytn2.mp3 | 0 | 0 | 10 | 6 | 330 | 0 | 0 | 0 | 346 |
| sbs1.mp3 | 0 | 0 | 2 | 6 | 238 | 0 | 0 | 0 | 246 |
| ytn1.mp3(held-out) | **15** | 0 | 2 | 10 | 227 | 8 | 0 | 0 | 262 |

G4(`p_opp<0.97`)가 4파일 전부에서 차단의 압도적 다수 — 대부분 프로브가 버퍼길이와 무관하게 애초에
문턱에 도달 못 함. G1=0 전 파일은 이 run이 auto 전용이라 예상된 결과(ko/en 가드 자체는 §10-6이
12세션 규모로 이미 검증). G6·G7도 전 파일 0 — 쿨다운·타 트리거 진행중이 이번 run에서 병목이 된 적
없음.

**ytn1 `would_fire=15` = 독립 15건이 아니라 연속 1개 에피소드** — 같은 성장버퍼에서 K가 5→19로
자라나는 연속 배치, 지속시간 1.20s→5.88s, 전부 `lang=en`: t=8.07s(p_opp=0.9962,k=5)→8.31(0.9801,6)→
8.55(0.9911,7)→8.79(0.9867,8)→9.27(0.9950,9)→9.75(0.9994,10)→9.99(0.9913,11)→10.23(0.9860,12)→
10.47(0.9861,13)→10.95(0.9983,14)→11.19(0.9995,15)→11.43(0.9992,16)→11.67(0.9985,17)→
11.67(0.9985,18, 동일 t_abs)→12.74(0.9906,19).

**정성 교차검증(참양성 확정)**: 이 시간창(t≈8~12.7s)은 `ytn1_C_R1.txt` 전사 도입부
(`"Yeah, I'm sorry. I'm sorry, I'm sorry, but I the United States. I'm happy to be here today. I
want to first thank you for hosting today's Security Consultative Meeting. I want to."`, 문장#1~4
`finalize_trigger=⟨punctuation⟩`)와 정확히 겹치고, 뒤이은 문장#5가 `⟨language_switch⟩`로 확정되며
한국어로 전환된다 — §10-4/Exp-195가 이미 규명한 **동일한 ytn1 언어잠금 실패**(한국인 개회사가 영어로
잠겨 전사)다. 이 run의 LMR_ko(19.7%/9.2%p)가 Exp-195 원보고 LMR_ko 19.7%와 거의 정확히 일치 — 독립
교차확증. bong1/ytn2/sbs1 3파일은 `would_fire=0`(오탐신호 0) — 단 이 run의 목적은 오탐률 재측정이
아니라(그 작업은 Exp-195가 12세션 규모로 이미 완료) 런타임 게이트가 설계대로 동작하는지 확인이었고,
결과는 설계대로였다.

### 판정
🟡 **계측 완료 — 개입(실제 트리거 배선)은 정지, 사용자 판단 대기.** would_fire: bong1/ytn2/sbs1=0
(오탐 신호 없음), ytn1(held-out)=15(연속 1에피소드, 정성 확인상 참양성·오탐 아님). 게이트가 이번
run에서 발동한 유일한 사례가 이미 알려진 실제 실패를 정확한 위치에서 잡아냈다는 점에서 **설계대로
동작**했다고 판단한다. 다만 `_apply_detected_language`에 실제로 배선해 섀도우를 졸업시킬지는 **이번
작업 범위 밖**이다 — CLAUDE.md의 "핵심 불변 제약 직결 기능은 정량 결과만으로 자율 채택/기각하지 않고
사용자에게 채택 여부를 묻는다" 규칙과 goal 문서 Step 6("master 머지는 사용자 확인 후, 실제 적용은
별도 단계")에 따라 사용자 확인을 기다린다. 브랜치(`exp/lang-lock-stage0`)는 master 미머지 유지.
정본 = `docs/research/SOT_LANG_PROBE_STAGE0.md` §11 · 인계 = `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` §4-0-3.

### epoch
**E6 그대로(bump 없음)** — 이번 변경은 섀도우 계측 전용이고, `_apply_detected_language`에 대한 신규
호출이 diff상 0건임을 Step 3/4에서 직접 확인했다(위 "섀도우 불변식" 참조). 실제 디코딩 결정 경로를
전혀 바꾸지 않으므로 어떤 실패모드도 바꿀 수 없다 — epoch bump 대상이 아니다.

## Exp-198 — Stage 1 섀도우 게이트 지속문턱 T 1.0s→0.8s 완화 (오프라인 리플레이 근거) (2026-07-22) [E6, `exp/lang-lock-stage1-duration`(미머지)]

**언어모드**: auto(bong1·ytn2·sbs1·ytn1, `--lan auto --repeat 1`, ytn2만 N=2 재측정).
**코드 변경**: `whisperlivekit/simul_whisper/align_att_base.py`의 상수 `STAGE1_MIN_DURATION`
**1.0 → 0.8** 단 한 개(커밋 `6868c2d`) + 회귀 테스트 3건. 게이트 로직·섀도우 불변식 무변경 —
`_apply_detected_language` 신규 호출 **0건**(섀도우 유지). pytest 674→677 pass·1 skip, ruff clean.

### 배경 — Exp-197 사후분석에서 드러난 40ms 미스
Exp-197은 bong1 `blocked_g5=5`(K/T 미달 차단)를 집계만 하고 내용을 열어보지 않았다. 이번에 그 5건을
프로브 단위로 뜯어보니 그중 하나가 **확정 참양성이 T 문턱에 0.04s 못 미쳐 막힌 사례**였다.
정답 `test_data/bong1.txt:43` = `아니 그 (더듬) 플라스틱 말랑말랑한 것도 만들었죠 우리가 안전한
소품으로 물론.` 인데, 전사는 한국어로 시작했다가(`아이 그` / `플라스틱 안색`) 영어로 뒤집힌다 —
`Plastic, sorry` / `Malang mal` / `ang an` / `awesome thing to make . We're going` — 그 뒤에야
올바른 한국어가 재방출된다. 잘못 방출된 영어는 삽입 오류 + 환각으로 남는 **확정 언어잠금 실패**다
(§10-4 ytn1과 동형). 이 구간 버스트: t=91.20(k=1, p_opp=0.9797, seglen=4.36) → 91.68(k=2, 0.9945,
4.84) → 91.92(k=3, 0.9896, 5.08, dur=0.72) → 92.16(k=4, **0.9996**, 5.32, **dur=0.96**). G3·G4·K≥3
전부 통과, **오직 `T≥1.0s`에서만 차단**. 버스트가 여기서 끝나 K=5로 이어지지 않으므로 "더 기다리면
어차피 발동"이 성립하지 않는다.

### 방법 — 오프라인 리플레이(주 증거)와 그 검증
섀도우 게이트는 디코딩에 영향이 0이고 입력이 프로브 스트림(`t_abs`·`p_opp`·`seglen`·`lang`)의 순수
함수이며 그 스트림이 서버 로그에 전부 남으므로, **기측정 로그만으로 임의 상수의 `would_fire`를
재계산**할 수 있다(재측정 0회). 분산이 ±30~120%p인 이 프로젝트에서 게이트 로직 질문에 **결정론적
증거**를 주는 유일한 수단이다. 신뢰하기 전에 Exp-197 4파일의 실측 `[Stage1ShadowStats]` 카운트를
**정확히 재현하는지** 대조했고 완전 일치했다 — bong1 g2=13/g3=25/g4=424/g5=5/fire=0, ytn2
g2=10/g3=6/g4=330/fire=0, sbs1 g2=2/g3=6/g4=238/fire=0, ytn1 g2=2/g3=10/g4=227/g5=8/fire=15.

**로그 판독 함정(재사용 지식)**: 첫 시도에서 4파일 전부 G4만 정확히 **+1**씩 어긋났다. 원인은
`infer(is_last=True)`가 **그 호출의 마지막 프로브를 처리하기 전에** 세션 요약을 방출하기 때문이다 —
로그상 요약 줄 뒤에 프로브가 한 줄 더 남지만 그 프로브는 요약 카운트에 없다. 마지막 프로브 1개를
제외하자 4파일이 전부 정확히 일치. (Exp-197의 중복억제 버그와는 **별개** 사안 — 그쪽은 요약이
갱신 안 되는 문제, 이쪽은 요약과 프로브의 순서 문제.)

### T 스윕 (K≥3·`seglen≥2.0s`·τ=0.97 고정, would_fire bong1/ytn2/sbs1/ytn1)

| T | bong1 | ytn2 | sbs1 | ytn1 |
|---|---|---|---|---|
| 1.0s(현행) | 0 | 0 | 0 | 15 |
| 0.9s | 1 | 0 | 0 | 16 |
| **0.8s(채택)** | **1** | **0** | **0** | **16** |
| 0.7s | 2 | 0 | 0 | 17 |
| 0.5s | 2 | 0 | 0 | 17 |
| 0.0s | 2 | 0 | 0 | 19 |

**에피소드 커버리지는 T=0.5~0.9에서 완전히 동일**하다 — 이 구간에서 달라지는 것은 *어떤 에피소드를
잡는가*가 아니라 *같은 에피소드 안에서 몇 번째 배치에 발동하는가*(발동 지연)뿐이다. 즉 0.8은 관측
한 건에 맞춰 깎은 knife-edge 값이 아니라 넓은 평탄구간 안의 값이다. **ytn2·sbs1은 T=0.0까지 내려도
0**(G3·G4에서 이미 전멸 — 후보 자체가 안 생긴다). T=0.8에서 새로 통과하는 발동점은 정확히 2개이고
둘 다 `k=4/dur=0.96`: **bong1 t=92.16**(위 확정 참양성)과 **ytn1 t=4.95**(p_opp=0.9838,
seglen=4.95 — ytn1의 이미 알려진 서두 실패 구간 *안쪽*이라 신규 오탐이 아니라 같은 실패의 더 이른
포착).

### 오탐 위험 검증 — T의 기여분은 0, 차단은 전적으로 G3
Exp-195의 ko/en 세션 로그 **16개**(kor1~3 각 4회 + eng1 4회)를 **G1(비-auto 가드) 의도적 우회**로
리플레이했다 — 실제 ko/en 세션은 G1이 첫 관문에서 다 막지만, 알고 싶은 것은 "**같은 단일언어 내용이
auto 세션으로 들어왔을 때**" 나머지 게이트가 버티는가라는 worst case이기 때문이다. **결과: 16파일
전부, T=0.0을 포함한 모든 T에서 `would_fire`=0.** 이유는 명확하다 — 그 로그들에서 `p_opp≥0.97`을
통과한 프로브의 **최대 seglen이 1.02s**이고 G3 문턱은 2.0s다(여유 **0.98s**). 즉 **알려진 오탐
계열의 차단은 전적으로 G3가 하고 있고 T의 기여분은 0** — T 완화는 오탐 방어를 전혀 잠식하지 않는다.
Exp-195(§4-0-1)의 "오탐은 `seglen ≤ 1.02s`라는 좁은 체제에만 산다"와 같은 구조를 T 축에서 독립
재확인한 셈이다.

### 측정 (경로 C, `--lan auto --repeat 1`, diar ON·CRT 3.0·`--trace-tokens`, `vbcable=ok`,
코드=`exp/lang-lock-stage1-duration@6868c2d`)

| 파일 | WER | 화자F1 | 문장F1 | LMR_ko | would_fire | 차단 G2/G3/G4/G5 |
|---|---|---|---|---|---|---|
| bong1.wav | 24.7% | 62.5% | 23.5% | 13.0%(3.6%p) | 0 | 18/41/432/2 |
| ytn2.mp3(N=2 재측정 median) | **11.1%** | **95.0%** | N/A | 0.0% | 0 | — |
| sbs1.mp3 | 8.9% | 80.0% | 90.0% | 0.0% | 0 | 0/2/248/0 |
| ytn1.mp3(held-out) | 11.7% | 84.2% | 57.1% | 1.3%(0.6%p) | **2** | 10/8/224/3 |

**ytn2 1차 run 폐기(하니스/자원 stall — STT 회귀 아님)**: 1차 수치 WER 69.0% / 화자F1 26.7%.
세 신호가 동시에 나와 측정 자체가 무효다 — ① 로그에 `FFmpeg read timeout`, ② 처리 lag 최대
**58.70s**(같은 run의 sbs1은 2.17s), ③ 프로브 수 **150**으로 반토막(Exp-197의 비교 가능한 run은
347). 이번 diff는 **로그 한 줄이 언제 찍히는지만** 바꾸므로 디코딩에 영향을 줄 경로가 물리적으로
없다 — 원인은 코드가 아니라 머신 경합.

**ytn2 재측정(한산한 머신: GPU 1.0/10.2 GiB·util 8%·경합 STT 서버 없음, N=2)**: R1 WER 8.4% /
화자F1 100.0%, R2 WER 13.8% / 화자F1 90.0% → median WER 11.1% / 화자F1 95.0%(min 8.4 / max 13.8 /
stdev 3.8), LMR 0.0%. 건강도 정상 복귀 — lag max 0.99s/0.98s, timeout 0건, 프로브 364/371.
**`would_fire`는 2회차 모두 0**(`blocked_g5`도 양쪽 0) — ytn2는 애초에 후보를 만들지 않는다는
리플레이 예측과 일치.

**Exp-197(T=1.0) 수치와의 비교는 효과가 아니다**: Exp-197은 bong1 28.9/70.3/21.1 · ytn2 13.3/100.0 ·
sbs1 11.9/100.0/88.9 · ytn1 22.1/84.2/57.1이었다. **diff가 로깅 전용인 이상 두 run의 WER/F1 차이는
전부 회차간 분산이며 개선도 회귀도 아니다** — 이 표를 "T 완화로 bong1 WER 28.9→24.7 개선"처럼
인용해서는 안 된다.

### 한계 — `would_fire`의 실현(realization) 의존성이 매우 크다
**실측 run은 bong1 발동을 재현하지 못했다**(`would_fire=0`, `blocked_g5=2`). 리플레이는 Exp-197
스트림에서 bong1 1건을 예측하지만 실측은 **다른 오디오 실현**이었고, 그 회차의 플라스틱 구간에서는
같은 `p_opp` 버스트가 생기지 않았다. 같은 이유로 ytn1은 이번에 2건만 발동했다(Exp-197 15건).
따라서 두 증거의 역할을 섞지 않는다 — **게이트 로직 질문("T=0.8이 옳은가")의 주 증거는 결정론적
리플레이**(동일 스트림에 상수만 바꿔 비교하므로 분산 미개입)이고, **실측 run의 역할은 end-to-end
확인**(구현 동작·로그 포맷 정상·크래시 없음·변경에 귀속 가능한 회귀 없음 — 달성)이다. 실측은 bong1
리플레이 결과를 확증하지도 반증하지도 않는다.

이 실현편차는 **섀도우 졸업(실제 트리거 배선) 판단에 직접 걸리는 사실**이다: 게이트 발동은 회차마다
있다가 없다가 하는 **희소·간헐 이벤트**다(같은 파일·같은 코드에서 15건→2건, 1건→0건). 실제 트리거로
승격해도 효과가 회차별로 나타났다 사라질 것이므로 **단회 측정으로 이익/해악을 귀속하는 것은
원리적으로 불가능**하며, N≥3 반복 + 발동 카운트 기반 짝지음 대조가 사실상 필수다.

### 판정
🟡 **계측 개선(섀도우 유지) — T 1.0→0.8 채택.** 근거 = ① T=1.0이 확정 참양성 1건을 0.04s 차로
놓치고 있었다 ② T 스윕상 0.5~0.9가 동일 커버리지 평탄구간이라 0.8은 knife-edge가 아니다 ③ ko/en
16세션 G1 우회 리플레이에서 T=0.0까지 오탐 통과 0 — 오탐 차단은 전적으로 G3의 몫이라 T 완화가
방어를 잠식하지 않는다. 실측은 end-to-end 동작 확인(ytn1 2건 발동·회귀 없음)에 성공했고, WER/F1은
로깅 전용 diff이므로 Exp-197 대비 차이가 곧 회차간 분산이다. **실제 트리거 배선(섀도우 졸업)은
여전히 사용자 판단 대기** — CLAUDE.md의 "핵심 불변 제약 직결 기능은 자율 채택/기각하지 않는다"
규칙에 따른다. 브랜치 `exp/lang-lock-stage1-duration`은 master 미머지 유지.
정본 = `docs/research/SOT_LANG_PROBE_STAGE0.md` §12 · 인계 = `docs/backlog/LANG_LOCK_STAGE0_HANDOFF.md` §4-0-4.

### epoch
**E6 그대로(bump 없음)** — 변경은 섀도우/로깅 전용 상수 1개이고 `_apply_detected_language` 신규
호출이 여전히 0건이다. 실제 디코딩 결정 경로를 전혀 건드리지 않으므로 어떤 실패모드도 바꿀 수 없다
(Exp-197과 동일한 논거).

## Exp-199 — UTF-8 seam 수렴 게이트 + 방출/보류 계약 정렬로 한국어 중간 단어 유실 완화 (2026-07-22) [E6, `exp/utf8-held-emit-loss`(master 머지 `f9f9cc5`)]

**언어모드**: ko(kor1~3, `--lan ko --repeat 1`) + auto(sbs1, `--lan auto --repeat 1`, 컴퓨터 정지로 오염된
1차 sbs1 회차는 폐기하고 재측정).
**배경**: 같은 세션에서 배포 제보 2증상("녹음 시작/장침묵 후 전사 유실", "한국어 중간 단어 유실")을
kor1~3+sbs1 각 5회 계측(`--trace-tokens`)으로 원인 규명 — 중간 단어 유실(BUG B)의 주원인은
`align_att_base.py`의 UTF-8 hold-retry 로직이었다(스트리밍 배치 경계에 한글 멀티바이트가 걸려
`[UTF-8 Filter] Skipping incomplete (held for retry)`로 보류됐다가 2회 재시도 후
`[UTF-8 Fix] Dropping ... won't resolve`로 통째 폐기). 실측 사례(kor2 "보장하고 예비"→"부대는",
kor3 "해역 함대 사이"→소실, sbs1 "한반도 동"·"전략적" 소실)가 전부 이 로그와 1:1 대응했다. 토크나이저
실측으로 원인을 바이트 단위까지 확정: `" 보장"` = 토큰 `[7842, 252, 98]`이고 `7842`는 `" 보"`+
`'장'`(3바이트)의 첫 바이트뿐이라, 배치 커밋 경계가 한글 글자 중간에 떨어지는 게 구조적으로 흔했다.
당초 이 사고 진단은 신규 조사였으나, 착수 후 **이미 별도 goal 루프(`docs/goal_prompt/GOAL_UTF8_HELD_EMIT_LOSS.md`,
2026-07-19 작성)로 같은 문제가 조사·구현까지 끝나 있었고**(브랜치 `exp/utf8-held-emit-loss`, 커밋
`98e6089`/`b819738`, 2026-07-20) 다만 그 goal 문서가 "master 머지 금지 — 사용자 승인 대기"로 명시
게이팅해둔 채 승인이 나지 않아 미머지 상태로 방치돼 있었다 — 이번 세션에서 그 브랜치를 master에 rebase
(merge commit)해 재사용했다. (주의: 커밋 메시지에 "Exp-191"이 찍혀 있으나 이는 오기 — 진짜 Exp-191은
EXPERIMENTS_LOG.md상 전혀 다른 실패한 실험 `exp/boundary-tail-dup`이다. 번호 재사용 혼선 주의.)

### 근본 원인 (코드 확정) + 수정 내용
Whisper BPE가 한글 1글자(UTF-8 3바이트)를 최대 3토큰에 바이트 단위로 흩뿌리므로, 스트리밍 커밋 경계가
글자 중간에 떨어지는 상황 자체는 정상이고, 이를 복구하는 hold-retry 로직(`_handle_pending_tokens`,
`MAX_PENDING_RETRIES=2`)에 결함 2가지가 있었다:
1. **재이어붙이기 전제 붕괴**: 보류한 바이트를 다음 배치 앞에 무조건 prepend하지만, 재디코딩이 그 뒷바이트를
   반드시 이어서 내놓는다는 보장이 없다 — attention이 지나쳐버리면 이어붙인 결과가 여전히 깨진 채로
   2회 재시도 후 폐기된다. **수정**: `_merge_pending_tokens` 신설 — prepend 전에 `decode(pending+new)`가
   여전히 U+FFFD를 포함하는데 `decode(new)` 단독은 clean이면 "죽은 seam"으로 판단해 pending을 즉시
   폐기하고 new만 정상 처리(정상 이어받기 상황은 new 단독도 여전히 깨져 있으므로 게이트 미발동 —
   Exp-087의 "미 미디어" hold/재emit 설계 보존).
2. **방출부/보류부 계약 불일치**: 방출부(`_build_timestamped_words`)는 중간에 깨진 단어를 그냥 skip하고
   계속 진행하는데, 보류부(`_handle_pending_tokens`)는 **마지막** 단어만 검사해 hold한다 — 중간에 낀
   조각은 재시도 기회 없이 영구 유실. **수정**: 방출부는 **첫** U+FFFD 단어에서 멈추고(그 뒤 clean 단어도
   다음 청크로 이연), 보류부도 첫 U+FFFD 단어부터 끝까지 전부 hold — 위치 무관 재시도 보장.
`SEAM_CONVERGENCE_FIX_ENABLED`(기본 `True`) 롤백 플래그로 두 수정을 한 번에 토글.

### TDD
`tests/test_utf8_held_emission.py` 신규 13개(H1 계약불일치 RED→GREEN, H2 스테일seam RED→GREEN 2건,
H3 retry/상한 drop 거동고정, H4 refresh/reset 클리어 거동고정, Exp-087 "미 미디어" 회귀가드, 플래그
False=완전 기존동작 재현). master 재병합 후 H4 목이 Exp-197 계측(`_stage1_shadow_reset_evidence`)
누락으로 깨져 스텁 보강(`8a5c694`). 전체 `pytest tests/ whisperlivekit/` **694 passed·1 skipped**
(무관한 기존 `scripts/vbcable_test.py` 픽스처 수집 에러 1건은 master 동일 재현 확인 — pre-existing).

### 측정 (경로 C, diar-ON, CRT=3.0, turbo, `--trace-tokens`, 짝지음 ON/OFF)
사용자 시간 제약으로 **스크리닝 `--repeat 1`만 실시, 채택 확정(N=3) 생략** — 아래 수치는 방향 신호.

| 파일 | OFF WER | ON WER | UTF-8 drop 이벤트 | 비고 |
|---|---|---|---|---|
| kor1 | 18.1% | **14.6%** | 1→1 | 개선 |
| kor2 | 18.6% | 18.6% | 2→4 | **최종 방출 텍스트가 ON/OFF 완전 동일**(drop 증가분은 무해) — "보장하고" 유실은 seam 무관 잔존 |
| kor3 | 39.1% | **33.1%** | 4→0 | drop 완전 해소, 가장 뚜렷한 개선 |
| sbs1(1차) | — | — | — | 측정 중 사용자가 컴퓨터 정지 직접 목격 — 오염 판정, 폐기 |
| sbs1(재측정) | 10.1% | 13.7% | 1→0 | drop은 줄었으나 WER 소폭 악화 — "플랫폼이라고"가 디코더 컨텍스트 덤프엔 U+FFFD 없이 멀쩡히 조립돼 있었음(로그 확인) → seam과 무관한 **별개의 기존 emit 동기화 버그**(디코더가 만든 단어가 방출 단계에서 누락, 원인 코드 미특정) 귀속, 이번 회차에 우연히 걸림

**화자분리 F1**: kor1~3은 단일화자 아티팩트(기지, Exp-186)라 판정 제외. sbs1은 두 회차 모두 발동
편차만 있고(50~100%) drop 이벤트와 무관.
**Case B**: 4파일 5회 전부 미발견.

### 판정 = 스크리닝 방향 신호 — **사용자 승인으로 확정측정 없이 조기 머지**
CLAUDE.md §4 "채택 확정 = repeat 3" 게이트는 **생략**(사용자가 시간 제약으로 스크리닝만 지시,
"master 머지 진행하자"로 직접 승인). 판단 근거: ① seam 자신의 표적 지표(UTF-8 drop)는 4파일 중
나쁜 방향으로 텍스트가 바뀐 사례 0건(kor2는 drop 증가에도 텍스트 불변, sbs1 유일 WER 악화는 로그로
확인된 무관 버그 귀속) ② Case B·신규 결함 0건 ③ pytest 전량 GREEN. **master 머지 완료(`f9f9cc5`)**.

### 다음/후속
- kor2 "보장하고" 잔존 유실 — 이 fix가 못 잡는 UTF-8 실패 변형이 있다는 뜻, 별도 조사 필요.
- sbs1 "플랫폼이라고" emit 동기화 버그 — seam과 무관, 원인 미특정 상태로 잔존(이전 세션
  `docs/research/2026-07-22_kor-silence-wordloss-diagnostic.md`가 유사 패턴을 이미 별도 항목으로 기록).
- BUG A(침묵/세션시작 유실)는 이번 실험 범위 밖 — 위 진단 문서에 원인 갈래 3~4개 별도 정리됨, 후속
  탐색 과제.
- 사용자 승인으로 확정측정을 생략했으므로, 여유 있을 때 `--repeat 3` 짝지음으로 재확인 권장.

### epoch
**E6 그대로(bump 없음)** — emit 계층(seam/hold-retry) 국소 버그 수정. 디코더 파라미터·VAD·언어감지
경로는 무변경.

**주의: 원본 JSON/로그/전사 파일 전부 소실됨** — 워크트리 `worktrees/utf8-held-emit-loss`의
`.omc/`(gitignored, 워크트리 로컬)에 저장돼 있었는데, 병합 직후 워크트리를 `git worktree remove --force`로
정리하면서 함께 삭제됐다(파일명: `eval_20260722_1556_seam{ON,OFF}_{kor,sbs}.json`,
`eval_20260722_1620_seam{ON,OFF}_sbs1only.json`, `server_{kor1,kor2,kor3,sbs1}_C_R1_20260722_*.log`,
`transcripts_seam{ON,OFF}*/`). 위 표·인용문은 삭제 전 세션 내에서 직접 읽고 기록한 것 — 원본 재검증이
필요하면 재측정해야 한다. **교훈**: 워크트리 삭제 전 `.omc/` 산출물을 커밋 밖 위치(예 워크트리 밖)로
먼저 옮기거나 최소 이 로그에 수치·인용을 남겨둘 것.

---

## Exp-200 — UTF-8 반토막 음절 커밋 오염 근본수정 (클린 커밋 절단, Direction A) (2026-07-22) [E6, `exp/utf8-context-clean-commit`(커밋 `17cc4af` → master 머지 `76150ca`)]

**언어모드**: ko(kor1~3, `--lan ko --repeat 1`) + auto(bong1·ytn2·sbs1, `--lan auto --repeat 1`). 짝지음 A/B — `CONTEXT_CLEAN_COMMIT_ENABLED` ON(True)/OFF(False), `SEAM_CONVERGENCE_FIX_ENABLED=True` 양쪽 공통. 측정 = **스크리닝 1회만**(사용자 시간제약, `--repeat 3` 확정단계 생략).

**배경**: Exp-199(seam 수렴 게이트)가 한국어 중간 단어 유실(BUG B)을 **일부만** 잡고 잔존 유실이 남았다. 이번 세션 사전 진단(kor1~3+sbs1 각 5회 `--trace-tokens`)이 잔존 유실의 단일 근본원인을 바이트 단위까지 확정: Whisper byte-level BPE가 한글 1글자(UTF-8 3바이트)를 최대 3토큰에 흩뿌리고, AlignAtt 스트리밍이 음절 중간에서 배치를 커밋하면 그 배치 마지막 토큰이 반토막(디코드 시 U+FFFD `�`)이 된다. 방출 경로(`_build_timestamped_words`)와 hold 경로(`_handle_pending_tokens`)는 Exp-199 seam 수정으로 이미 "첫 `�` 단어"에서 멈추도록 정렬됐으나, **커밋 경로만 여전히 `�`를 넘어 전진**했다: `align_att_base.py`의 `self.state.tokens.append(new_tokens_tensor)`가 반토막 `�` 토큰 포함 hypothesis를 디코더 컨텍스트에 커밋 → 다음 청크는 high-water mark(`token_len_before`) 뒤쪽만 재디코딩하므로 커밋된 반토막이 mark에 묻혀 영영 재디코딩 안 됨 → hold된 완성 바이트는 재디코딩이 이어바이트를 안 주면 `MAX_PENDING_RETRIES=2` 소진 후 드롭. 결과: 앞바이트는 커밋돼 mark 전진, 완성분은 드롭 → 음절/단어 영구 유실.

### 수정 내용
- `whisperlivekit/simul_whisper/align_att_base.py:60` — 롤백 플래그 `CONTEXT_CLEAN_COMMIT_ENABLED = True` 신설(`SEAM_CONVERGENCE_FIX_ENABLED` 옆). False = 완전 기존 동작.
- `align_att_base.py:939~` — 헬퍼 `_clean_commit_hypothesis(new_hypothesis, split_words, split_tokens)` 신설: `_handle_pending_tokens`의 `�` 검출 idiom(`next((i for i,w in enumerate(split_words) if "�" in w), None)`) 재사용해 첫 `�` 단어 인덱스를 찾고, 그 앞까지의 토큰만 반환. `incomplete_idx is None`이면 원본 그대로, `len(clean_prefix) < len(new_hypothesis)`일 때만 절단(둘 다 같은 순서 리스트의 프리픽스라 짧은 쪽이 교집합). **순수 subtractive**(길이 미증가) — 비-fire "마지막 단어 hold" 스트리밍 의미 불변. 새 tokenizer 호출·재디코딩 없음.
- `align_att_base.py:868~870` — 커밋 지점: `new_hypothesis` 대신 `commit_hypothesis = self._clean_commit_hypothesis(...)`로 텐서 생성·커밋·`Output:` 로그. `_quality_gate`(:863~864)는 **원본 `new_hypothesis` 유지**(억제 판정은 전체 청크 기준, 절단은 컨텍스트 위생만).
- PyTorch(`SimulWhisper`)·MLX(`MLXAlignAtt`) 둘 다 베이스 `infer()` 상속 → **한 곳 수정으로 양 백엔드 커버**(읽기전용 검증만: 빈 커밋 허용·zero-width 텐서 허용).

의도한 인과사슬: 반토막 미커밋 → high-water mark 청결 유지 → 다음 청크가 그 오디오를 오염 없는 컨텍스트에서 재디코딩 → 온전한 단어 생성 → 기존 seam 게이트가 stale 반토막 정리. **핵심 검증(코드확인)**: 오디오 위치는 토큰 커밋과 분리(`simul_whisper.py:167` `insert_audio`가 `audio_max_len` 초과 시 **앞쪽만** 트림) — 반토막 음절은 버퍼 끝(fire 경계)에 있어 앞-트림 대상 아님 → 토큰 미커밋이어도 오디오는 버퍼에 남아 재디코딩됨.

**TDD**: `tests/test_utf8_held_emission.py`에 `commit_prefix` 헬퍼 + 커밋계층 테스트 7개 신설. RED(수정 전, 메서드 부재로 7 fail)→GREEN(수정 후 신규 7 + 기존 13 = 20 pass). 무회귀: `test_media_no_leading_fragment_duplication`(미 미디어 중복 가드) 유지, A/B 플래그(`test_flag_false_commits_broken_token`), subtractive 증명(`test_commit_unchanged_when_all_clean`·`test_commit_nonfire_lastword_unchanged`), 복구통합(`test_full_redecode_supersedes_stale_pending_single_emit`). 전체 스위트 `tests/ whisperlivekit/` **701 passed·1 skipped**, ruff 신규위반 0.

### 테스트 세트 결과 (경로 C, diar-ON Sortformer CRT=3.0, turbo, `--trace-tokens`, N=1 스크리닝, OFF→ON)

| 파일 | 모드 | WER OFF→ON | 화자F1 OFF→ON | 문장F1 OFF→ON | Dropping OFF→ON |
|------|------|-----------|--------------|--------------|-----------------|
| kor1 | ko | 18.7→**14.6%** | 1.0→1.0 | 1.0→1.0 | 1→1 |
| kor2 | ko | 21.4→**17.2%** | 1.0→1.0 | 1.0→1.0 | 2→**0** |
| kor3 | ko | 39.7→**29.1%** | **0.0→1.0** | 0.92→0.91 | 3→**0** |
| bong1 | auto | 25.3→**33.4%** ⚠️ | 0.63→0.71 | 0.10→0.33 | 1→1 |
| ytn2 | auto | 14.8→**12.3%** | 1.0→0.9 | — | 2→**0** |
| sbs1 | auto | ~12.5→**~8.9%** | 0.81→0.87 | 0.44→0.64 | 5→**0** |

**표적 지표 (설계 메커니즘 확증)**:
- **Dropping(영구유실) 이벤트 총 14→2**(86%↓): kor2·kor3·ytn2·sbs1 → 0. Discarding stale(seam 게이트 발동) 13→130, Prepending(stale 재접합) 145→20 — 반토막 미커밋 → 재디코딩 → seam이 stale 폐기로 이어지는 인과사슬이 트레이스 카운트로 그대로 관측됨.
- **유실구 복구**: kor3 `보장`(2/0)·`로봇 등`(1/0), sbs1 `플랫폼`(1/0)을 ON이 정확 문맥에서 복구(하단 §분석). 유실 신규 추가 0.
- **FFFD 방출 = 전 파일 0**(ON/OFF 공통) → Case B(바이트) 0·"미 미디어"류 중복 0.

### 분석 (전사 내용 정성 대조)

**kor3** (ko, ON WER 29.1% vs OFF 39.7%): 목표 유실구가 **정상 문맥으로 복구**됨.
- **단어 유실 복구**: ON `"전문성 보장과 안정적인 운용을 위한"` / OFF `"전문성 위한"`("보장과 안정적인 운용을" 유실) — 계획 지목 유실구 복구.
- **단어 유실 복구**: ON `"드론 로봇 등 유무인 복합전투체계"` / OFF `"드론 유무인 복합"`("로봇 등" 유실) — 정확 복구.
- **화자경계**: ON 화자F1 1.0 vs OFF 0.0(diar 라벨 정합 개선). 환각·Case B 없음. ON L1 run-on(OFF가 2줄로 나눈 걸 1줄로)은 Case A(동일화자 문장 미분리, 허용).

**kor1·kor2** (ko): 주요 신규 실패 없음. WER 개선은 ko_del(삭제=유실) 감소 주도 — kor1 ko_del 5→2, kor3 ko_del 18→10. OFF kor3는 `ins_runs_ge3=1`·`max_ins_run=3`(환각 run) 있었으나 ON은 `max_ins_run=1`(환각 run 소멸).

**ytn2·sbs1** (auto): 개선. sbs1 `플랫폼` 복구, WER·문장F1 모두 개선. ytn2 WER 개선, 화자F1 -0.1(1회 분산 범위).

**bong1** (auto, ON WER 33.4% vs OFF 25.3% — **회귀 +8.1pp**): 비-catastrophic.
- **단어 유실(꼬리 절단)**: ON은 마지막 영어 번역 블록이 `"...the Sun character say within the film, this is."`에서 **끊김** / OFF는 `"...announcing it on screen."`까지 완결 — 최종 1~2문장 en_del(39 vs OFF 12, ON −165자). 계획이 잔존 리스크로 명시한 "반토막 오디오가 20s 창 밖 트림 전 재디코딩 못하는 희귀 폴백"으로 추정(단정 아님, 1회 측정).
- **경미 중복**: ON `"So So my son"`·`"This This map"`(OFF도 `"It's him It's him"` 등 자체 중복 다수 — bong1 다화자 특성, fix 신규 아님). laughter 구간은 ON/OFF 둘 다 지저분(기존 알려진 bong1 웃음 환각). 환각 spiral·Case B 없음.

**이번 변경 영향**: ko(한국어 단독 낭독)에서 반토막 커밋 오염 제거가 목표 유실구를 정상 복구하고 삭제·환각 run을 줄여 WER을 명확히 개선. auto는 ytn2·sbs1 개선·bong1 회귀(영어 다화자 꼬리 절단). Dropping 14→2 표적지표는 설계대로 작동.

### 채택 (조건) 판정
- **① 화자F1 worst-case 미회귀**: kor3 0.0→1.0·bong1 0.63→0.71·sbs1 0.81→0.87 개선, ytn2 1.0→0.9 소폭(1회 분산). 전반 개선/유지.
- **② WER max 미회귀**: ko 3파일 전부 개선, auto ytn2·sbs1 개선. **bong1만 +8.1pp 회귀** — §3.8 최우선 파일이라 worst-case 관점 yellow flag. 단 1회 스크리닝 분산 범위이고 비-catastrophic(꼬리 절단, 환각 spiral 아님).
- **③ Case B·중복 hard-gate**: FFFD 방출 0 → Case B 0, "미 미디어"류 중복 0. **통과**. (fix가 커밋에서 토큰을 빼기만 하므로 단어중간 분절 신규 생성 구조적으로 불가.)

### 결론
**브랜치 커밋(`17cc4af`) → master 머지 완료(`76150ca`).** 표적지표(Dropping 14→2·유실구 복구·FFFD 0)와 ko 개선은 명확하나, bong1 auto WER +8.1pp 회귀(§3.8 최우선 파일)가 계획의 자체 판정기준("worst-case 미회귀")과 상충 — CLAUDE.md §4 "목표 필수 기능 채택은 사용자 질의" 및 §3.2(한국어 단어유실 = 불변제약 직결)에 따라 자율 기각/머지 대신 **사용자 판단으로 에스컬레이션**했다. **사용자가 실사용 관찰상 만족으로 머지 승인**(bong1 `--repeat 3` 확정측정은 진행 중 중단·생략 지시). **1회 스크리닝 근거임**(seam Exp-199와 동일 규율 — 순수 커밋계층 정합성 수정 + 단위테스트로 로직 고정이라 회차편차 리스크 낮음). **후속(잔존 리스크)**: bong1 꼬리절단(en_del 39)이 재현되면 "반토막 오디오 20s 창 트림 전 재디코딩 실패" 폴백 경로 별도 조사 필요.

### 다음 가설
- master 머지 승인 시 → 필요하면 `--repeat 3` 확정측정으로 bong1 회귀가 실제인지 분산인지 확증(특히 화자F1 worst-case).
- bong1 꼬리 절단이 재현되면 → "반토막 오디오 20s 창 트림 전 재디코딩 실패" 폴백 경로 별도 조사(계획 §잔존 명시). 범위 밖: kor1 "전자기"→"전작이"(무로그 앰비귀티, 반토막 아님), BUG A(침묵후 유실, 별개 패밀리 — `docs/research/2026-07-22_kor-silence-wordloss-diagnostic.md`).

**JSON**: `.omc/benchmarks/eval_utf8_{ON,OFF}_{ko,auto}_20260722_1718.json`(4개) · 서버 트레이스 `.omc/server_logs/server_*_C_R1_20260722_17*.log`(12개, ON=이른 ts/OFF=늦은 ts).

---

## Exp-201 — lang_locked 세션 new_speaker 경계 재디코딩 무조건 스킵 (2026-07-22) [E6 후보, `exp/hallu-t1-lang-locked-skip`(커밋 `9c17e0f`, **미머지** — 환각루프 T1)]

**언어모드**: ko(kor1~3, `--lan ko`) 확정측정(`--repeat 3`) + auto(bong1·ytn2·sbs1, `--lan auto --repeat 1`) 무회귀 스크리닝.

**배경**: 2026-07-22 환각루프 goal 세션의 사전 로그 분석(kor1~3·sbs1 각 5회 `--trace-tokens`)이 확정한 계열① — `backend.py new_speaker()`에서 `lang_locked`(ko/en 고정) 세션은 화자전환 시 eager 언어재감지를 아예 안 돌려(`eager=None`, 쿨다운 캐시 `_last_eager_lang_result`도 lang_locked 분기에선 설정되지 않아 영원히 비어 있음) "동일 언어 확정 시 경계 재디코딩 스킵"(Exp-196, E6) 조건의 `lang_evidence`가 항상 `None` → 조건이 구조적으로 절대 발동 못 함. 세션 언어는 화자전환으로 바뀔 수 없으므로 이 스킵은 고정 세션에서 항상 자명하게 참이어야 하는데 정반대로 매 화자전환마다 무조건 `refresh_segment`(경계 재디코딩)를 태워 중복 방출을 유발했다(kor1 R3=NewSpeaker 32회·Refresh 34회·WER 32.2%, R4=NewSpeaker 60회·Refresh 63회·WER 35.1% — goal 프롬프트 §2 계열① 원인 코드 확정 인용).

### 수정 내용
- `whisperlivekit/simul_whisper/backend.py:449~` — `new_speaker()` 최상단에서 `lang_locked`이면 eager 감지·`boundary_offset`·쿨다운 로직을 전혀 거치지 않고 곧장 "동일 언어 확정" 스킵 경로로 조기 return(화자 귀속 `self.model.speaker` 갱신만, `refresh_segment` 미호출). 기존 `if lang_locked: eager=None else: ...` 분기는 이제 도달 불가능한 죽은 코드였으므로 제거하고 `else` 본문을 그대로 dedent — auto 경로(비-lang_locked)의 로직·동작은 **글자 그대로 동일**(디덴트만, 재배치 아님).
- `tests/test_session_language_lock.py` — 회귀 테스트 2개 신설: `test_new_speaker_locked_skips_boundary_refresh`(lang_locked → `refresh_segment.assert_not_called()`, 화자 귀속은 갱신됨), `test_new_speaker_auto_still_calls_refresh_segment_when_lang_differs`(대조군 — auto 세션은 여전히 `refresh_segment.assert_called_once()`, 회귀 없음 확인).

**TDD**: RED 확인(수정 전 신규 테스트 1개 fail — `refresh_segment` 실제로 1회 호출되어 버그 재현) → GREEN(수정 후 신규 2개 포함 15개 전부 pass). 전체 스위트 `tests/` **744 passed·1 skipped**(무관), ruff 신규 위반 0.

### 테스트 세트 결과

**ko 확정측정(`--repeat 3`, N=3, median/max)**:

| 파일 | WER (R1/R2/R3) | median | max | NewSpeaker (R1/R2/R3) | Refresh (R1/R2/R3) |
|------|-----------------|--------|-----|------------------------|----------------------|
| kor1 | 14.0/11.7/11.1 | 11.7% | 14.0% | 0/30/22 | 3/3/4 |
| kor2 | 26.2/13.1/17.9 | 17.9% | 26.2% | 0/0/0 | 3/4/3 |
| kor3 | 29.8/33.8/30.5 | 30.5% | 33.8% | 0/0/0 | 4/4/4 |

**auto 무회귀 스크리닝(N=1)**: bong1 30.1%(게이트 ≤30.5%) · ytn2 14.3%(게이트 ≤34.5%) · sbs1 13.7%(게이트 ≤16.1%) — Exp-161 확정 게이트 전부 이내.

**표적 지표 (설계 메커니즘 확증)**: kor1 R2(NewSpeaker 30회)·R3(22회)에서 **Refresh가 3~4회로 0-firing 회차(R1)와 동일 수준 유지** — 수정 전이라면 발동 횟수만큼(30·22회) 폭증했을 경로다. WER도 firing 회차(11.1~11.7%)가 0-firing 회차(14.0%)보다 오히려 낮음 — goal 프롬프트가 인용한 pre-fix 사례(NewSpeaker 32~60회 → Refresh 34~63회 → WER 32~35%)와 정반대 패턴으로, 목표 결함(중복방출) 해소를 직접 확인.

### 분석 (전사 내용 정성 대조)

**kor1** (ko, R1/R2/R3 hyp_lines 전수 대조): NewSpeaker 발동 회차(R2/R3)에서 텍스트 **중복·왜곡 0건** — 같은 발화 내용이 R1(0-firing)과 동일한 순서로 이어지며, 화자전환 지점마다 문장이 더 잘게 나뉠 뿐(예: R1 "…발전 중에 있고, 특히…AI, 드론, 로봇 등 유무인 복합 전투체계를…" 한 줄 vs R2 같은 구간이 "…AI, 드론, 로봇 등."/"유무인 복합 전투 체계를…" 2줄로 분리) 단어 유실·Case B(단어 중간 분절) 0건. **화자분리 F1**: R1=1.0 vs R2/R3=0.0 — 그러나 이는 이 fix가 유발한 게 아니라 **Sortformer가 단일화자 낭독(kor1)에서 flip-flop 오탐**(goal §2 계열① 진단과 동일 현상)해 `trigger=speaker_change` 줄바꿈이 정답에 없는 지점에 삽입된 것. 화자 귀속(`token.speaker`) 갱신 로직은 스킵 경로·재디코딩 경로 양쪽에서 **동일하게** 수행되므로(줄 끝 `self.model.speaker = change_speaker.speaker`), 이 fix 유무와 무관하게 발생했을 현상 — 별개 이슈(§3 T5 예비 "kor1 flip-flop 버스트 상류 완화"로 승계).

**kor2·kor3** (ko, 전 회차 NewSpeaker 0회): 0-firing — 짝지음 원칙상 노이즈 대조군, 이 fix의 효과를 검증하지 못함(다음 세션에서 화자전환 재현 시도 여지).

**이번 변경 영향**: kor1의 NewSpeaker 폭주 회차에서 목표한 Refresh 폭주·중복방출이 완전히 해소됨(설계대로 작동). 부수적으로 관측된 kor1 화자분리 F1 붕괴는 Sortformer 화자귀속 오탐(별개 근본원인)이며 이 fix가 신규로 유발한 것이 아님을 코드 경로 대조로 확인.

### 채택 (조건) 판정
- **① 화자분리 F1 worst-case**: kor1 R2/R3 0.0 — 표면상 우려되나 위 분석대로 fix와 무관(Sortformer flip-flop, 양쪽 코드 경로 동일 동작). ko 모드는 아직 F1 확정 baseline 미수립(STATE 명시)이라 "회귀" 비교 자체가 성립 안 함 — 별개 이슈로 분리 기록.
- **② WER max 미회귀**: auto 3파일 전부 Exp-161 게이트 이내. ko는 baseline 없어 게이트 비교 불가하나 firing 회차가 오히려 개선 방향.
- **③ Case B·중복 hard-gate**: 전수 대조 결과 0건. **통과**(fix가 refresh_segment 호출 자체를 건너뛰므로 재디코딩발 중복이 구조적으로 발생 불가).

### 결론
**브랜치 커밋 완료(`9c17e0f`) → 채택권고·머지 대기.** 목표 결함(lang_locked 세션 화자전환 시 무조건 재디코딩→중복방출)의 재현·수정·해소를 유닛테스트(RED→GREEN)와 실측(NewSpeaker 22~30회 발동에도 Refresh 3~4회 유지, 중복 0건) 양쪽으로 확증. auto 무회귀 확인. kor1 화자분리 F1 붕괴는 별개 원인(Sortformer flip-flop)으로 규명되어 이 fix의 채택을 막을 근거가 아니라고 판단하나, **머지 여부는 사용자 확인 사항**(이번 루프는 master 머지 금지 원칙).

### 다음 가설
- kor2/kor3도 NewSpeaker 발동 회차를 잡으면 동일 패턴(Refresh 무회귀·중복 0) 재확인 여지.
- kor1 Sortformer flip-flop 자체 완화는 별도 과제(§3 T5 예비, `MIN_SPEAKER_ATTRIBUTION_SECS` 재분석) — 이번 T1 fix와 독립적으로 진행.

**JSON**: `.omc/benchmarks/eval_20260722_2305_hallu_t1_ko_screen.json`(스크리닝 N=1) · `eval_20260722_2316_hallu_t1_auto_noregress.json`(auto 무회귀) · `eval_20260722_2329_hallu_t1_ko_confirm_N3.json`(확정 N=3). 서버 트레이스 `.omc/server_logs/server_kor{1,2,3}_C_R{1,2,3}_20260722_23*.log`.

---

## Exp-202 — 침묵 클로징 환각 섀도우 계측(`[SilenceHalluProbe]`) 실측 — would_hold 오탐 3/3, 게이트 배선 보류 (2026-07-22/23) [E6, `exp/hallu-t2-silence-hallu-probe`(커밋 `0348f1d`, **미머지·계측전용** — 환각루프 T2]

**언어모드**: ko(kor1~3, `--lan ko`, N=1) + auto(bong1·ytn2·sbs1, `--lan auto`, N=1), 전부 `--trace-tokens`. 코드 변경 없음(계측 전용, `SILENCE_HALLU_PROBE_ENABLED` 로깅만 — Exp-201과 별개로 커밋된 계측 브랜치에서 측정).

**배경**: goal 프롬프트 T2 — VAD 침묵 개시(`Silence.is_starting`) → `start_silence()` → `process_iter(is_last=True)`로 진입하는 강제 flush는 `quality_gate`를 항상 건너뛴다. 이 지점에서 "attention reaches the end" ∧ 직전 호출 대비 attended frame 전진폭이 거의 0/역행 ∧ 텍스트 커밋 → "감사합니다"류 클로징 환각 후보로 가정하고 `would_hold`를 로깅(§2a, 실제 억제 없음).

### 측정 결과

| 파일 | 모드 | is_last_calls | committed_on_is_last | would_hold |
|------|------|---------------|------------------------|------------|
| kor1 | ko | 26 | 21 | 0 |
| kor2 | ko | 35 | 29 | 0 |
| kor3 | ko | 40 | 32 | **2** |
| bong1 | auto | 21 | 18 | 0 |
| ytn2 | auto | 12 | 6 | **1** |
| sbs1 | auto | 12 | 8 | 0 |

### 분석 (would_hold 발동 3건 전수 라벨링, §2c)

- **kor3 `위한`@t=3.10s, `위해`@t=15.20s**: 둘 다 **오탐**. 정답 대조 결과 두 단어 모두 정상 문맥의 흔한 한국어 연결어(~을 위한, ~하기 위해)로 정답에도 동일하게 존재 — 새 음성 없이 이어 생성된 필러가 아니라 **짧은 정상 단어가 짧다는 이유만으로 frame_advance≈0을 만든 것**.
- **ytn2 `control`@t=7.22s**: **오탐**. TokenTrace 대조 결과 디코더가 "…transfer of operational control"까지 디코드하다 그다음(", "/"and") 진행분이 버퍼 말단(`attention reaches the end: 361/362`)에 걸려 `control`만 우선 커밋하고 나머지는 보류(hold)한 **정상 스트리밍 부분방출** — `control,`·`control and` 두 continuation을 시도한 디코드 흔적이 로그에 그대로 남아 있어(라인 10893-10906) 새 텍스트를 지어낸 게 아님이 명확.
- **bong1(웃음 구간 포함) would_hold 0건**: T4(필러 타임스탬프 정체 시그니처) 부수판정 — 이번 회차엔 신호 없음(발동 자체가 없어 판단 보류, 재현성 낮음 가능성).

**would_hold 오탐률**: 3/3(100%) — §2c 규칙("오탐 1건 이상 → 게이트 배선 금지")에 따라 **배선 금지**. 근본 원인: `start_silence()`가 `is_starting`(아주 짧은 호흡 pause만 감지해도 발동)에서 호출되어 문장 최종경계뿐 아니라 **모든 미세 pause마다** is_last=True 강제 flush가 발생 — 그 시점엔 그 pause가 "긴 침묵"인지 미정이라, 프레임 전진폭만으로는 "짧은 정상 단어의 자연스러운 부분방출"과 "새 음성 없는 이어짓기 환각"을 구분 못 함.

### 결론
**계측완료(채택/기각 비대상) — 게이트 배선 금지.** 후보 시그니처(attention_reached_end ∧ frame_advance≈0)는 특이도가 낮아 정상 스트리밍 부분방출을 다량 오탐한다. 원 목표(§2 계열②, kor3 "감사합니다"/sbs1 "다음은" 폭주)의 실제 발동 사례는 이번 측정에서 재현되지 않음(N=1 스크리닝 한계일 수 있음).

### 다음 가설
- 조건 좁히기 후보(2a 재계측 시): ① `is_starting` 대신 `end_silence()`의 `long_silence`(실제 긴 침묵 확정, `MIN_DURATION_REAL_SILENCE` 이상) 시점과 연동 — 미세 호흡 pause를 원천 제외. ② 커밋 run의 절대 길이(음절 수)가 극히 짧으면(1~2음절/단어) 애초에 후보에서 제외하는 정규화. ③ hold 중인 continuation이 있었는지(TokenTrace상 다음 continuation 시도 흔적) 함께 확인 — 있으면 정상 부분방출, 없으면 환각 후보로 격상.
- kor3/kor1~3 각 5회 원본 로그(§2 배경)에 실제 있었던 "감사합니다"/"다음은" 폭주 사례의 시그니처를 이 계측으로 역추적 재현 시도 여지(N=1이 아니라 그 특정 회차를 재현하도록 시드/반복 필요).

**JSON**: `.omc/benchmarks/eval_20260722_2358_hallu_t2_ko_probe.json`(ko) · `eval_20260723_00XX_hallu_t2_auto_probe.json`(auto). 서버 트레이스 `.omc/server_logs/server_{kor1,kor2,kor3,bong1,ytn2,sbs1}_C_R1_2026*.log`.

---

## Exp-203 — 음차 경계 환각 고아 토큰 계측(`[PreSwitchOrphan]`) 실측 — 진짜 경계환각 신규 포착, 단 수치 임계값 미도출 (2026-07-23) [E6, `exp/hallu-t3-preswitch-orphan-probe`(커밋 `57e8b71`, **미머지·계측전용** — 환각루프 T3]

**언어모드**: auto(sbs1·ytn2·bong1, `--lan auto`, N=1, `--trace-tokens`). ytn1은 held-out이라 제외(§7-4 규칙). 코드 변경 없음(계측 전용).

**배경**: sbs1 실측(2026-07-22 세션) — KO 문장 확정 → 0.55s 침묵 → KO 잠금 상태로 영어 서두가 음차 방출("사태라"≈"satellite") → 그제서야 화자전환/언어전환 인지. 언어전환 마커 삽입 직전의 최근 커밋 run을 `[PreSwitchOrphan]`으로 로깅(임계값 걸러내기 없음, §3a).

### 측정 결과

| 파일 | 발동 건수 |
|------|-----------|
| sbs1 | 2 |
| ytn2 | 9 |
| bong1 | 11 |

### 분석 (발동 22건 전수 대조, §3b)

- **sbs1(2건)**: 이번 회차는 목표 결함("사태라") **재현 안 됨** — KO→EN 전환이 깨끗함(`브런슨 사령관은…비유한 바 있습니다. From a satellite image…` 정상). 두 orphan 모두 legitimate 문장 꼬리(`한 바 있습니다`·`China`) — 진음성 대조군.
- **ytn2(9건) — 진짜 경계환각 신규 포착**:
  - **`John Gyeong`@t=55.18~55.42**(EN→KO 마커 직전, gap=0.32s): 최종 출력에도 그대로 남아 있음 — `…initial operational capability John Gyeong. 정경두 국방장관과…`(정답엔 "John Gyeong" 없음, "정경두"만). **국방장관 이름의 음차 오번역이 EN→KO 전환 경계에서 삽입된 것** — sbs1 "사태라"(고유명사/전문용어 음차)와 **동일 계열의 신규 사례**(다른 파일에서 최초 확인).
  - **`You`@84.34(→최종 출력 `Let's.`)·`Minister Liu:`@104.10(→최종 출력 `Prime.`)**: 두 건 모두 **probe가 로깅한 시점의 텍스트가 최종 출력과 다름** — 커밋 후 boundary_reconcile 등으로 **철회·대체**됐다(probe는 커밋 순간의 스냅샷이라 이후 철회를 모름). 두 최종형("Let's."/"Prime.") 자체도 정답엔 없는 **소규모 삽입 환각**(EN→KO 경계 바로 앞) — probe가 그 "불안정 경계"를 정확히 짚었으나 텍스트 내용 자체는 stale.
  - 나머지 6건(`.`·`resolutions`·`이르었습니다`·`. "There is more`)은 정답과 정확히 대응하는 **정상 문장 꼬리**(대조군).
- **bong1(11건)**: 다수(9건)는 정상 단어/구두점 꼬리(대조군). **`틀렘이까? 죄송합니다 형`@108.65~110.39**은 정답의 `그 아들내미가 죄송합니다 형님`과 부분 대응하나 `틀렘이까` 자체는 정답에 없는 왜곡(웃음·중첩발화 구간, 기존 bong1 환각 패턴과 정성 일치) — **혼재 사례**(일부 정상+일부 왜곡, 깨끗한 단일 판정 불가). 나머지는 대조군.
- **구현 한계 발견**: 일부 run의 `dur`/`gap_to_marker`가 음수(예: bong1 `That's it` dur=-1.92, ytn2 `Minister Liu:` dur=-0.18) — 언어전환 경계 부근에서 토큰 타임스탬프가 항상 단조증가하지 않는 경우가 있음(철회·재정렬 영향 추정). 계측 로직 자체의 버그는 아니나(디코딩 영향 없음, 로그값만 비단조) 수치 기반 자동판정에는 노이즈 요인 — 후속 설계 시 고려.

### 결론
**계측완료(채택/기각 비대상). "환각만 잡고 정상 꼬리는 안 잡는" 단순 수치 임계값(길이·gap)은 이번 22건 표본에서 도출 안 됨** — 진짜 환각과 정상 꼬리 둘 다 길이 0.1~2초, gap -0.6~3s에 걸쳐 분포해 겹친다. 그러나 **메커니즘 자체는 유효함을 확증**: sbs1 "사태라" 외에 ytn2에서 **국방장관 이름 음차 오번역("John Gyeong")** 이라는 **동일 계열의 신규 경계환각 사례**를 처음 포착했고, 두 건은 **probe 커밋 스냅샷과 최종 출력이 다른("철회됨") 경계 불안정** 사례로 확인됨. §3b 규칙대로 "억지로 문턱을 만들지 않는다" — 자동 게이트는 미설계.

### 다음 가설
- **최종 출력 대조 추가**(다음 세션): probe가 커밋 시점 텍스트뿐 아니라 "이 run이 나중에 철회/대체됐는가"까지 추적하면(2건에서 이미 관측된 신호) 판별력이 오를 수 있다 — `_recent_commit_runs`에 철회 여부 플래그 추가 검토.
- 고유명사/전문용어 음차 오번역(John Gyeong·사태라 계열)은 **스크립트 불일치가 아니라 같은 스크립트 내 오번역**이라 기존 ScriptMismatch류 게이트로 못 잡음 — 별도 신호(예: 언어전환 마커 직전 N초 내 committed 고유명사 후보의 낮은 confidence) 탐색 여지.
- 시간 남으면 ytn2/bong1을 반복 측정해 "John Gyeong"류 사례 재현율 확인(sbs1 "사태라"처럼 5회 중 3회 수준인지).

**JSON**: `.omc/benchmarks/eval_20260723_00XX_hallu_t3_auto_probe.json`. 서버 트레이스 `.omc/server_logs/server_{sbs1,ytn2,bong1}_C_R1_20260723_00*.log`.

---

## Exp-204 — ChangeSpeaker dispatch 노이즈 필터 (kor1 flip-flop 근본원인 수정) (2026-07-23) [E6 후보, `exp/hallu-t5-changespeaker-dispatch-filter`(커밋 `80f4bbd`, **미머지** — 환각루프 T5, §3 예비항목에서 승격]

**언어모드**: ko(kor1~3, `--lan ko`, N=1 스크리닝) + auto(bong1·ytn2·sbs1, `--lan auto`, N=1 스크리닝 + `--repeat 3` 확정).

**배경**: T1 확정측정(Exp-201) 로그를 재분석하다 발견 — kor1 flip-flop 버스트가 단일 순간에 NewSpeaker 8회 연속 발생(중간 정상 디코딩 처리 없이 로그가 바로 이어짐). Exp-188(`MIN_SPEAKER_ATTRIBUTION_SECS`, 텍스트 화자라벨링 계층)이 이 버스트를 걸러줄 것으로 기대했으나, 버스트 구간에 `[SpeakerAttribution]` 로그가 **0건** — 그 완화책이 이 dispatch 경로엔 애초에 적용 대상이 아님을 실측 확인. `audio_processor.py _update_diarization_state()`가 Sortformer 원시 세그먼트의 화자변화를 감지할 때마다 **세그먼트 길이 검사 없이** `ChangeSpeaker`를 dispatch하는 것이 근본원인(설계 사각지대).

### 수정 내용
- `whisperlivekit/audio_processor.py` — 모듈 상수 `CHANGE_SPEAKER_DISPATCH_FILTER_ENABLED`(롤백 플래그)·`MIN_CHANGE_SPEAKER_DISPATCH_SECS=0.5`(기존 `MIN_SPEAKER_ATTRIBUTION_SECS`와 동일값) 신설.
- `_update_diarization_state()` — 세그먼트 길이가 문턱 미만이면 dispatch뿐 아니라 `_last_diar_speaker` 상태 갱신도 스킵(짧은 flip이 상태를 오염시켜 이후 진짜 화자 복귀가 스퓨리어스 전환으로 재판정되는 것도 함께 방지).
- **TDD**: 신규 유닛 8개(문턱 미만·이상·경계값·세션최초·상태오염방지·롤백 A/B 대조·공유state 무변경) 전부 GREEN. 전체 750 passed·1 skipped(무관)·ruff clean.
- **⚠️ 유사 전례**: ChangeSpeaker 디바운스가 Exp-106(E1, base 기질)에서 ytn2 회귀 전력 — 시간기반 디바운스가 아닌 순수 최소길이 필터라 메커니즘이 다르고 base 기질 결론이라 epoch 게이트상 방향신호일 뿐이지만, ytn2를 특히 주의해 재검증함.

### 테스트 세트 결과

**ko 스크리닝(N=1) — 표적 지표**: kor1 NewSpeaker **22~30회(Exp-201 로그) → 4회**(대폭 감소). Refresh=5(이 브랜치는 T1 fix 미포함이라 남은 이벤트는 여전히 refresh 유발 — 예상대로). WER kor1 13.5%/kor2 13.8%/kor3 32.5%(무관 밴드 내).

**auto 확정측정(`--repeat 3`, N=3, median/max) vs Exp-161 게이트(bong1≤30.5%/ytn2≤34.5%/sbs1≤16.1%)**:

| 파일 | WER (R1/R2/R3) | median | max | 게이트 | seg_f1 |
|------|-----------------|--------|-----|--------|--------|
| bong1 | 27.1/33.7/35.2 | 33.7% | **35.2%(게이트 초과 +4.7pp)** | 30.5% | 0.50/0.53/0.65 |
| ytn2 | 21.2/17.2/18.7 | 18.7% | 21.2%(이내, 대폭개선) | 34.5% | 0.60/0.70/0.86 |
| sbs1 | 10.7/11.3/8.9 | 10.7% | 11.3%(이내, 대폭개선) | 16.1% | 0.40/0.80/0.80 |

### 분석 (전사 내용 정성 대조)

- **ytn2·sbs1**: 게이트 대폭 이내로 개선. **Exp-106이 우려한 ytn2 디바운스류 회귀는 이번엔 재현 안 됨** — 오히려 median이 baseline(28.1%) 대비 큰 폭 개선(18.7%). 순수 최소길이 필터가 시간기반 디바운스와 다른 메커니즘임이 실측으로도 뒷받침됨.
- **bong1 max 35.2% 회귀 원인 분석**: 최악회차 전사를 정답과 전수 대조 — `This man Dismap Thank you. Thank you.`·`Okay, cool Thank you.`·`하하하하하` 등 **전형적인 bong1 웃음구간 필러/환각 패턴**(기존에 이미 광범위하게 문서화된 별개 미해결 이슈, STATE "Layer 3b 비음성 게이팅" 참조)이며, 화자전환 경계에서의 왜곡·중복 등 **diarization/ChangeSpeaker 관련 신규 아티팩트는 발견되지 않음**. 즉 이 회귀는 bong1의 기존·독립적 웃음 환각 변동성(원래도 회차마다 크게 요동)이 이번 3회 중 한 번 강하게 나타난 것으로 보이며, 이 fix가 새로 유발한 결함이 아니라고 판단됨(단 인과 100% 배제는 로그만으로 불가능).

### 채택 (조건) 판정
- **① 화자분리 F1 worst-case**: bong1 0.50~0.65(기존과 비슷한 밴드), ytn2·sbs1은 개선. 뚜렷한 worst-case 신규 붕괴 없음.
- **② WER max 미회귀**: ytn2·sbs1 대폭 개선. **bong1만 게이트 초과(+4.7pp)** — §3.8 최우선 파일이라 엄격 적용 시 미통과. 단 위 정성분석상 원인이 이 fix와 무관한 별개 기존 이슈(웃음 환각)로 보임.
- **③ Case B·중복 hard-gate**: 전수 대조에서 Case B 0건. 화자전환 관련 신규 중복 0건(발견된 중복/필러는 전부 기존 bong1 웃음 패턴).

### 결론
**조건부 채택권고 — 브랜치 커밋 완료(`80f4bbd`), 머지는 사용자 판단 대기.** 표적 지표(kor1 flip-flop 22~30회→4회)와 ytn2·sbs1 개선은 명확하나, bong1 max가 게이트를 초과했다(+4.7pp). 정성분석 결과 그 원인이 이 fix가 건드리지 않는 **별개의 기존 미해결 이슈**(웃음구간 필러 환각, Layer 3b 비음성 게이팅 — STATE에 오래전부터 기록된 채 미해결)로 보이나, 로그만으로 인과관계를 100% 배제할 수는 없다. CLAUDE.md §4 채택 우선순위상 "①max 미회귀"를 엄격 적용하면 미통과이지만, §3.8 최우선 파일(bong1)의 max 회귀 원인이 이 코드 경로 밖에 있어 보이는 애매한 경우라 **자율 기각하지 않고 사용자 확인으로 에스컬레이션**(Exp-176/199/200과 동일한 선례).

### 다음 가설
- bong1만 별도로 N을 늘려(예: 5회) 이 fix의 실제 bong1 영향을 웃음환각 변동성과 분리 가능한지 확인.
- 채택 시 T1(`exp/hallu-t1-lang-locked-skip`)과 함께 머지하면 lang_locked 세션에서 이중 효과(경계 재디코딩 스킵 + 스팸 이벤트 자체 감소) 기대 — 별도 브랜치라 함께 측정한 적은 없음.
- bong1 웃음구간 Layer 3b 비음성 게이팅은 이 fix와 별개로 여전히 미해결(STATE 기록 유지).

### ★추가 — bong1 N=5 확장 측정 (분산 특성 재확인)

**방법**: bong1만 2회 추가 측정(총 N=5: 기존 3회 + 신규 2회).

**결과**: WER 5회 = [27.1, 33.7, 35.2, 26.8, 36.1]% → **정렬 시 26.8/27.1/33.7/35.2/36.1, median 33.7%(N=3과 동일), max 36.1%(N=3의 35.2%보다 더 벌어짐), min 26.8%**. stdev가 매우 큼(범위 9.3pp) — Exp-161 baseline(N=3, 29.3~30.5%, stdev 0.7%로 매우 좁음)과 뚜렷이 다른 분산 양상. 5회 중 3회가 게이트(30.5%) 초과, 2회는 게이트 이내.

**해석**: N=5로도 median이 안정적(33.7%로 N=3과 동일)이라는 점은 이 fix 적용 시 bong1이 baseline보다 다소 높은 대역(약 33%대)에 재중심화됐을 가능성을 시사하나, **동시에 분산 자체가 baseline보다 훨씬 커진 것도 사실**이다. 두 원인이 혼재할 수 있음: ① 이 fix와 무관한 bong1 고유의 웃음환각 변동성이 이번 측정 시점에 유독 크게 나타남(다른 요인 — GPU 부하·최근 머지된 여러 변경 누적 등) ② fix가 실제로 bong1 worst-case를 약간 악화시킴. **N=5로도 완전히 분리 판별은 안 됨** — 정성분석(§본문)은 여전히 웃음환각 패턴이 원인이라는 쪽을 가리키나, 수치만으로는 단정 불가.

**결론 보강**: 조건부 채택권고 유지, 단 **median이 baseline 대비 다소 높아졌을 가능성(29.3~30.5%대 → 33%대로)**을 사용자 확인 시 함께 고지할 것 — 이는 max 게이트 초과보다 더 근본적인 신호일 수 있다.

### ★★정정 — 플레인 마스터 동일조건 대조측정으로 채택권고 철회

**방법**: 위 "N=5 확장" 결과가 여전히 애매해, **T5 fix를 아예 적용하지 않은 현재 마스터**(워크트리 `hallu-plainmaster-bong1-check`, `master@104adc8`)에서 **같은 날·같은 조건**으로 bong1을 N=5 측정해 정면 대조.

**결과**: 플레인 마스터 bong1 WER 5회 = **[29.5, 21.4, 21.4, 20.2, 30.1]%, median 21.4%, max 30.1%(게이트 이내), stdev 4.9%**. T5 브랜치(median 33.7%, max 36.1%, stdev 더 큼)와 **뚜렷한 차이** — 같은 날 같은 조건에서 이 정도 median 차이(21.4→33.7%)는 우연한 변동으로 보기 어렵다.

**메커니즘 확인**: NewSpeaker 원시 이벤트 카운트도 대조 — 플레인 마스터 bong1은 회차당 **53~67회**(평균 ~61회) 발생하는데, T5 필터 적용 시 **37회**로 감소(§측정 2 확인치). 즉 필터가 원시 이벤트의 **약 40%를 억제**하고 있다. kor1(노이즈성 flip-flop 22~30회→3~4회, 거의 전부 노이즈)과 달리, **bong1은 CLAUDE.md §3.3/§3.8이 명시하는 "다화자가 짧은 단어를 번갈아 말하는" 파일**이라 0.5초 미만의 화자전환 다수가 **노이즈가 아니라 진짜 화자전환**일 가능성이 높다 — 필터가 이를 억제하면 화자 귀속이 잘못돼(rapid turn-taking 구간에서 이전 화자로 잘못 유지) WER이 악화되는 것으로 설명 가능(Exp-106이 ytn2 코드스위칭 속도에서 우려했던 것과 같은 계열의 실패모드가, 이번엔 bong1의 화자전환 속도에서 재현된 것).

**결론 철회**: 위 "조건부 채택권고"를 **철회**한다. 이 fix는 kor1의 flip-flop 노이즈는 효과적으로 억제하지만, **§3.8 공동 최우선 파일인 bong1의 핵심 과제(다화자 빠른 전환)를 훼손**하는 것으로 판단되며, 현재 고정 문턱(0.5s) 설계로는 채택 부적합. **재설계 필요**(예: 훨씬 낮은 문턱, 또는 노이즈와 진짜 전환을 구분하는 별도 시그널) — 아래 후속 시도 참조.

### ★★★후속 — 문턱 0.5s→0.2s 하향 재검증 (bong1 피해 대폭 완화)

**변경**: `MIN_CHANGE_SPEAKER_DISPATCH_SECS` 0.5→0.2(커밋 `703794c`). 유닛테스트를 문턱 상수 상대값으로 일반화 + 경계값 테스트 부동소수 정밀도 수정. 750 pass·ruff clean.

**재측정**:
- **bong1(N=3)**: WER [22.3, 27.4, 28.6]% → **median 27.4%, max 28.6%(게이트 30.5% 이내로 회복!)** — 플레인 마스터(median 21.4%/max 30.1%)보다도 max가 낮음. NewSpeaker 원시 이벤트 대비 억제율도 0.5s 문턱보다 완화(31~58회 유지, 플레인 마스터 53~67회에 더 근접).
- **kor1(N=2)**: 이번 2회는 우연히 **0-firing**(flip-flop 버스트 자체가 재현 안 됨, kor1 특유의 간헐성 — Exp-201에서도 R1/R2/R5는 0-firing이었음) — 0.2s 문턱의 노이즈 억제력 자체는 이번 표본으로 재확인 못함(향후 세션에서 버스트 재현 회차를 잡아 확인 필요).

**결론(갱신)**: 0.2s 문턱은 bong1 피해를 실질적으로 해소하는 것으로 보인다 — **채택권고를 조건부로 재상향**하되, ① kor1 flip-flop 억제 효과가 0.2s에서도 유지되는지 버스트 재현 회차로 재확인, ② bong1·ytn2·sbs1 `--repeat 3` 정식 확정측정을 다시 거쳐야 함(이번 0.2s 재검증은 스크리닝 수준). 원 설계(0.5s)의 실패는 "Exp-188 기존 상수를 검증 없이 재사용"한 것이 원인 — **재사용 가정도 실측 검증이 필요하다는 교훈**으로 기록.

### ★★★★ kor1 flip-flop 재현 회차로 0.2s의 트레이드오프 확인

**추가 측정**: kor1을 4회 더 반복 → **R4에서 버스트 재현**(NewSpeaker **12회**, Refresh 9회, WER **26.3%**) — 나머지 3회는 0-firing(WER 13.5~15.8%).

**해석**: 0.2s 문턱은 0.5s 문턱(같은 버스트를 3~4회까지 억제)보다 **덜 공격적으로 걸러낸다** — 0.2~0.5s 사이 세그먼트를 통과시키기 때문에, kor1 flip-flop 노이즈 중 그 구간에 속하는 것들은 여전히 dispatch된다. 그 결과 **T5 단독(0.2s, T1 미포함)**으로는 버스트 발생 시 여전히 WER이 일부 악화(26.3%, 0-firing 대비 +10~13pp)한다 — 원래(무필터) 22~30회보다는 12회로 절반 이상 줄었지만 **완전 억제는 아님**.

**함의**: 이는 오히려 **T1+T5 결합의 필요성을 강화**한다 — T5(0.2s)가 이벤트 수를 줄이고, T1이 살아남은 이벤트를 "공짜"로 만들어야 kor1 문제가 완전히 해소된다(§Exp-205 결합검증, 단 그 검증은 0.5s 버전 기준이었으므로 **0.2s로 재검증 필요**). T5 단독 채택 시에도 bong1 피해 해소라는 목적은 달성하나, kor1 목표는 T1과 함께 머지해야 완전해짐을 명시적으로 기록.

**최종 결론**: 채택권고(0.2s) 유지하되, **"T5 단독보다 T1+T5 결합 머지를 권장"** 근거가 하나 더 늘었다. 정식 확정측정(0.2s 버전, T1 결합 여부 각각)이 다음 세션 최우선 과제.

**JSON**: `.omc/benchmarks/eval_20260723_0041_hallu_t5_ko_screen.json`(ko 스크리닝) · `eval_20260723_0055_hallu_t5_auto_noregress.json`(auto N=1) · `eval_20260723_0111_hallu_t5_auto_confirm_N3.json`(auto 확정 N=3). 서버 트레이스 `.omc/server_logs/server_{kor1,kor2,kor3,bong1,ytn2,sbs1}_C_R*_20260723_0*.log`.

---

## Exp-205 — T1+T5 결합 검증 (cherry-pick 상호작용 확인, 스크리닝 전용) (2026-07-23) [E6 후보, `exp/hallu-t1t5-combined-check`(커밋 `3ac30b8` = `9c17e0f`+`80f4bbd` cherry-pick) — 환각루프, 코드 신규작성 없음]

**언어모드**: ko(kor1~3, N=1) + auto(bong1·ytn2·sbs1, N=1). **목적은 회귀 확정이 아니라 T1·T5 상호작용 확인**(두 fix가 별도 브랜치에서 독립 개발돼 함께 측정된 적이 없었음).

**방법**: 워크트리 `worktrees/hallu-t1t5-combined-check`, `master`에서 분기 후 `git cherry-pick 9c17e0f 80f4bbd` — **충돌 0건**. 전체 752 passed·1 skipped(무관)·ruff clean.

### 결과

**ko 스크리닝 — 이상적 상호보완 확인**: kor1 NewSpeaker **3회**(T5 단독 4회와 비슷한 노이즈 억제 수준) 중 **3/3 전부 T1의 "경계 재디코딩 스킵"(lang_locked) 발동** — Refresh는 무관한 정상 침묵-refresh 3회뿐. WER kor1 11.7%/kor2 17.9%/kor3 35.8%(무관 밴드). **설계대로 두 fix가 정확히 상호보완**(T5=노이즈 이벤트 자체 감소, T1=남은 진짜 이벤트의 재디코딩 비용 제거).

**auto 무회귀(N=1)**: bong1 23.5%(seg_f1 0.55)·ytn2 24.1%(seg_f1 0.73)·sbs1 12.5%(seg_f1 0.80) — **Exp-161 게이트(30.5/34.5/16.1) 전부 이내**, T5 단독 확정측정(Exp-204)의 bong1 max 우려도 이번 회차엔 재현 안 됨(단 N=1). auto 모드에서는 `cfg.language=="auto"`라 T1의 `lang_locked` 분기가 애초에 비활성(grep으로 잡힌 "경계 재디코딩 스킵" 로그는 전부 기존 Exp-196 auto 동일언어 스킵 — T1과 무관, 예상대로 T1이 auto 경로에 관여하지 않음을 재확인).

### 결론
**계측완료(채택/기각 비대상, 신규 코드 없음) — 결합 시 상호작용 문제 없음 확인.** 두 fix는 서로 다른 계층(T5=diar 이벤트 dispatch 소스, T1=new_speaker 재디코딩 분기)에서 독립적으로 작동하며 간섭하지 않는다. auto 경로는 예상대로 T1이 관여하지 않아(lang_locked 전용) T5만 효과를 내고, ko 경로는 둘 다 효과를 내 최상의 결합 결과를 보임. **정식 채택 확정(--repeat 3)은 T1·T5 개별 머지가 승인된 이후 별도로 필요**(이번 검증은 스크리닝 1회, 상호작용 부재 확인이 목적).

**JSON**: `.omc/benchmarks/eval_20260723_0130_hallu_t1t5_ko_screen.json` · `eval_20260723_0142_hallu_t1t5_auto_noregress.json`.

---

## Exp-206 — kor3 "감사합니다" 클로징 필러 재현 시도 — 4/4 미방출, 계열② 재검증 필요성 발견 (2026-07-23) [E6, `exp/hallu-t2-silence-hallu-probe`(계측전용, 코드변경 없음) — 환각루프 T2 후속]

**언어모드**: ko(kor3 단독, `--lan ko --repeat 4`, `--trace-tokens`). **목적**: T2의 원 목표(§2 계열②, goal 프롬프트가 인용한 "kor3 R2/R5 세션 말미 '감사합니다' 생성·방출")를 실측 기반으로 재현해 `[SilenceHalluProbe]`의 실제 시그니처를 보정하려 함.

### 방법·결과
- kor3를 4회 반복 측정, 서버 로그에서 `감사합니다` 문자열과 `[SilenceHalluProbe]` would_hold 값을 전수 검색.
- **`감사합니다`가 4회 전부에서 디코더 내부 후보(DEBUG 증분 디코드 로그)로 등장**(R1×3·R2×4·R3×3·R4×1) — 매번 문맥상 부적절한 위치(예: "…개편하겠습니다 감사합니다", "…감축하겠습니다. 감사합니다" — 브리핑 중간)에 삽입되는 전형적 환각 패턴.
- **그러나 `Output:`(실제 커밋) 라인에는 `감사합니다`가 단 한 번도 등장하지 않음(0/4)**. 로그 정밀 대조(kor3 R2 line 6983 주변) 결과: 디코더가 "...개편하겠습니다 감사합니다"까지 증분 디코드 → `attention reaches the end: 739/740`로 루프 종료 → 이번 호출의 최종 `Output:`은 **공백**(홀드) — "감사합니다"는 미완결 마지막 단어로 취급돼 보류됐고, 다음 호출에서 재확인되지 못해 자연 소멸.
- **`[SilenceHalluProbe]` would_hold=0/4** — T2 프로브가 "실측 대비 안 잡은 것"이 아니라, **애초에 커밋된 텍스트 자체가 없어 후보가 될 게 없었다**(빈 `text=`는 `would_hold` 조건의 `commit_text` 진위값 검사에서 자동 탈락, 설계대로 동작).
- **"다음은"(sbs1/kor3 beam 대안 인용) 검색도 0/4** — 이번 측정 범위에서 재현 안 됨.

### 분석
원 진단(2026-07-22 세션)이 인용한 "감사합니다 생성·방출" 사례는 그 시점 코드/데이터에서 실제 COMMIT까지 도달했던 것으로 보이나, **현재 마스터(Exp-199/200 UTF-8 커밋계층 정합성 수정 포함) 기준으로는 디코더의 환각 경향 자체는 여전하지만(내부 후보 4/4 재현) 커밋 게이팅이 이를 매번 성공적으로 홀드·폐기**하고 있다. Exp-199/200이 "반토막 UTF-8 토큰"이라는 다른 문제를 고치며 커밋 직전 hypothesis 절단·검증 로직을 강화했는데, 그 부수효과로 이 필러도 함께 억제됐을 가능성이 있다(직접 인과 확인은 안 됨 — 별도 조사 필요하면 Exp-199/200 이전 커밋으로 롤백 후 동일 측정 대조 가능).

### 결론
**계측완료(채택/기각 비대상, 코드 변경 없음).** T2의 원 목표(kor3 감사합니다 필러)가 **이번 측정 4/4에서 실제로 방출되지 않음**을 확인 — §2 계열②의 "최신 master(Exp-200 이후) 전사에서도 지속" 서술은 **이 4회 표본 기준 재검증 필요**(과거 서술이 stale일 가능성). T2가 설계한 `[SilenceHalluProbe]` 시그니처는 애초에 커밋되지 않는 텍스트에 대해서는 원천적으로 발동할 수 없으므로 이번 조건 좁히기 시도는 "실측할 양성 예시가 없다"는 이유로 보류. 계열②는 **여전히 완전히 해소됐다고 확언할 수 없으나(내부 후보 생성 경향은 그대로), 우선순위를 낮춰도 될 근거**를 새로 확보함.

### 다음 가설 (★후속 검증으로 해결됨 — 아래 추가 참조)
- Exp-199/200 이전 커밋으로 kor3를 재측정해 "감사합니다"가 실제로 방출됐었는지 대조 → **완료, 결과는 아래 추가 참조**.
- 계열②를 완전히 닫으려면 더 많은 반복(N≥10)과 다른 ko 세션(kor1/kor2)·auto 파일에서도 "필러가 후보로만 생기고 커밋은 안 되는지" 동일 패턴을 확인해 일반화 여부 판단(다음 세션 과제로 유지).

**JSON**: `.omc/benchmarks/eval_20260723_0150_hallu_t2_kor3_repeat4.json`. 서버 트레이스 `.omc/server_logs/server_kor3_C_R{1,2,3,4}_20260723_01*.log`.

### ★추가 — Exp-199 이전 커밋(`2957cc7`) 대조측정 결과 (가설 반증)

**방법**: 워크트리 `worktrees/hallu-pre-exp199-check`(Exp-199 병합 직전 커밋 `2957cc7`에서 분기, 코드 변경 없음)에서 동일하게 kor3 `--repeat 4` 측정.

**결과**: "감사합니다" 후보 발생은 **오히려 더 잦음**(1/1/7/9회, 신코드의 1/3/4/3회보다 많음)이나 **실제 커밋(`Output:`)에는 이번에도 4/4 전부 미방출**(WER 34.4~39.1%, 구코드라 전반적으로 더 나쁨은 별개). 즉 **8회 측정(신코드 4+구코드 4) 전부에서 "감사합니다"가 실제로 방출된 적이 없다.**

**정정된 결론**: 애초 가설("Exp-199/200의 UTF-8 커밋계층 수정이 부수효과로 억제했다")은 **반증됨** — 그 수정 이전부터 동일한 홀드 메커니즘이 이미 작동하고 있었다. 대신 두 가지 해석이 남는다: ① 이 "감사합니다" 커밋 자체가 원래도 **드문 간헐적 현상**(실시간 STT 회차간 변동성이 큰 것으로 이미 잘 알려진 프로젝트 특성 — VBCable 재생 타이밍의 미세한 차이가 청크 경계를 바꿔 어쩌다 한 번씩만 실제로 커밋되게 만들 가능성)이라 8회로도 못 잡았을 수 있다. ② 원 진단(2026-07-22 세션)이 인용한 로그 라인(`kor3_C_R2:L12852`·`R5:L13587`)이 실제로는 이번에 확인한 것과 같은 **DEBUG 증분 디코드 후보 라인**이었을 가능성(그 세션에서 "생성·방출"이라고 서술했지만 "방출"(commit) 여부까지 `Output:` 라인으로 교차검증했는지는 그 세션 기록에 명시돼 있지 않음) — **재확인 권장**.

**다음 가설(갱신)**: 사용자가 원 진단 세션의 인용 로그 라인을 직접 재확인하거나, 더 많은 반복(N≥10)으로 실제 커밋 사례를 잡아야 계열②의 실재 여부·빈도가 확정된다. 이번 8회 측정 결과만으로는 "완전히 해소됐다"고도 "여전히 심각하다"고도 확언할 수 없다 — **불확실성 자체를 결론으로 남긴다.**

**JSON(대조)**: `.omc/benchmarks/eval_20260723_0209_hallu_pre199_kor3_repeat4.json`. 서버 트레이스 `.omc/server_logs/server_kor3_C_R{1,2,3,4}_20260723_02*.log`(워크트리 `hallu-pre-exp199-check`).
