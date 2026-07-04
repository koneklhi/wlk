# 실험 로그 (STT WER/F1 개선) — STATE (요약·현행상태)

이 파일은 **항상 읽는 요약본**이다. 현행 측정 regime · 베이스라인 · 이월 핵심사실 · 빠른참조 · **코드 세대(epoch) 게이트**만 담는다.
개별 실험의 전체 서술은 [EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md)에, Exp-001~130은 [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md)에 있다.
측정·채택 규율은 [CLAUDE.md](CLAUDE.md) §4·§3.8을 따른다. 기록은 `/log-experiment`로 수행한다.

> **3계층 구조**
> - **이 파일 (STATE)** — 항상 읽음. 요약·regime·baseline·이월핵심·빠른참조·epoch 게이트. (~150줄 상한)
> - [EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md) **(LOG)** — Exp-131~ 전체 서술. **온디맨드**: 특정 Exp 상세는 `grep "Exp-NNN"`으로 해당 블록만.
> - [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md) **(ARCHIVE)** — Exp-001~130, 동결. 아주 오래된 결론 추적 시에만.

---

## 읽기 규약 (Claude — 매 개선 세션)

1. 세션 시작 시 **이 STATE 파일만** 읽는다(짧음). LOG/ARCHIVE를 통째로 읽지 않는다.
2. 특정 과거 실험 상세가 필요하면 → [EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md)에서 `grep "Exp-NNN"`으로 해당 블록만.
3. 과거 결론을 현재 작업의 채택/기각 근거로 인용하기 전 **아래 epoch 게이트**를 반드시 적용한다.

## 코드 세대 (Epoch) — stale 결론 차단 게이트

> **왜**: 실패 모드를 바꾸는 구조적 코드 변경 전후로 디코더 파라미터의 트레이드오프가 달라진다.
> 다른 세대에서 나온 결론을 현재 코드의 **확정 근거**로 쓰면 오판한다(예: 초기 파라미터 튜닝 ↔ 언어고정·비음성억제 도입 후).

- **현재 master = Epoch 4 (E4)**: E3 + **diar-ON 언어전환 경로 배선 활성화**(`prev_lang fallback`로 마커/2.5s 트림 실발동 + `PuncSegment.hard_boundary`로 diar 병합 경계보존). **Exp-153 머지 (dc312bb, 2026-07-03).** E3에서 **dormant**였던 전환 메커니즘이 측정경로(diar-ON)에서 처음 실동작 → 실패모드 변화: 전환경계 단어보존(§3.2/Q4) 획득 + **신규 재디코딩 filler 환각**("You know, in Bukhpil"류)·**마커 과분할**(F1 precision↓). E2 파라미터 결론(PLC·beam·CRT·nonspeech; Exp-131~149)은 전환 활성화로 거동이 또 달라지므로 **[E2·재검증]** 유지. **PLC는 Exp-154서 재평가 완료 → 기본값 4.0 채택**(전환세금 제거·배선 후 E1/E2 3회기각이 채택으로 전환; ytn2 무휴지 코드스위칭 유일경로).
- **Epoch 3 (E3, 이력)**: E2 + **언어 전환 프로토콜 재설계**(전환 시 오디오 절단으로 재디코딩 세금 제거 · `_check_short_silence_language` SOT 배선버그 수정 · LanguageSwitch 문장경계 마커). 단계1 머지 (6db5ea1, 2026-07-02) — **단 diar-ON(측정 기본)에서 dormant**였음(Exp-153이 배선으로 활성화).
- **Epoch 2 (E2, 이력)**: SimulStreaming + diar-ON + `lang_restrict_koen=True`(후처리 CJK/주석 필터). Exp-139 머지(2026-07-01), Exp-142에서 logprob=-2.0 N=3 베이스라인 확정(bong1 37.5 / ytn2 31.5 / sbs1 19.6).
- **세대 경계 규칙**: 파라미터 값 변경(PLC·beam·frame_threshold·CRT 등)은 epoch를 **올리지 않는다**(같은 세대 내 실험). 언어고정·비음성억제·디코더 교체·VAD 파이프라인 변경 등 **실패 모드를 바꾸는 구조 변경**만 세대를 올린다.

**▶ epoch 게이트 (필수)**: 과거 Exp 결론(특히 파라미터)을 현재 작업의 채택/기각 근거로 인용하기 전, 그 Exp의 epoch가 *지금 측정 대상 코드*의 epoch와 같은지 확인한다. **다르면 확정 사실이 아니라 '방향 신호'로만** 쓰고 재검증한다.
예: Exp-131~137(E1)의 PLC·beam·frame_threshold 기각은 E2 코드(언어고정+비음성억제)에선 **재검증 대상** — 그 기각 사유인 "bong1 max 폭주(웃음→CJK 환각)"를 E2가 직접 손대기 때문.

---

## 현행 측정 regime (2026-06-30 갱신 — 2계층 스크리닝/확정)

- **테스트 세트(채택/기각)**: `bong1` + `ytn2` + `sbs1`
  - **① 스크리닝(평소)**: `eval.py --repeat 1` — 빠른 방향 탐색·catastrophic 회귀 감지. 1회 수치는 방향 신호로만 해석한다.
  - **② 채택 확정(머지 직전)**: `eval.py --repeat 3` — N≥3회 **median + min/max/stdev** 함께 본다. 이 단계에서만 **fail-fast 금지**(분산 자체가 데이터).
- **held-out(일반화 검증)**: `ytn1` + `eng1` — 채택 후보에 한해 회귀 감시, **단회** 검증. (ytn1 = ytn2 동일 이벤트 쌍둥이 코드스위칭, eng1 = 영어 회귀 감시)
- **측정 경로**: 경로 C(VBCable 루프백)만. provenance 게이트 필수 — 매 측정 첫 줄 `[provenance] code=wlk branch=master@… vbcable=ok …` 육안 확인.
- **측정 기본 설정**: 화자분할 ON (Sortformer + `--compression-ratio-threshold 3.0`).
- **채택 우선순위(② 단계 기준)**: ① 최악 케이스(max WER) 미회귀 ② median 개선. max가 catastrophic하면 median이 좋아도 기각.
- **개선 1순위**: `ytn2`(짧은 텀 코드스위칭) + `bong1`(다화자 장시간) 공동 최우선. **데이터 특화 하드코딩 금지 — 개선은 일반화돼야 한다.**

## 현재 베이스라인 (Epoch 1 — master default)

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

## 이월 핵심사실 (distilled — 상세는 LOG / [PHASE2_EXPERIMENTS.md])

> 태그: **[불변]** = 측정방법론·데이터특성·구조 → 모든 epoch에서 유효. **[E1·재검증]** = E1에서 측정한 파라미터 트레이드오프 → E2 코드에선 재검증 대상.

- **[불변][측정]** 경로 C(VBCable)만 채택 판정 기준. 경로 A(PCM 주입)는 실사용과 무관 → 폐기.
- **[불변][측정]** Exp-106~129 전체 기각 — silent code-version trap(잘못된 cwd로 변경 미반영 측정) + VBCable 간헐 불안정 + provenance 미기록. provenance 하니스(Exp-130) master 머지 완료가 새 기준점.
- **[불변][디코더]** SimulStreaming 채택(Exp-001) — LocalAgreement는 영어 코드스위칭을 통째 누락하고 발화 후반 커버리지를 잃음. AlignAtt 실출력 토큰엔 **구두점이 없어** 구두점 기반 확정이 미발동 → 확정 신호는 VAD silence·세그먼트 경계·언어 전환에서 찾는다.
- **[E1·재검증][디코더]** `beam=4`는 ytn2 catastrophic(Exp-125: beam2 28.1%→beam3 29.6%→beam4 40.4% 단조증가). bong1은 beam=4로 안정화되나 ytn2 손해가 압도. **beam=3은 재검증 대상.**
- **[E4·채택][언어]** `periodic_lang_check`(PLC) **기본값 4.0 채택(Exp-154)** — 전환세금 제거·배선 완료(Exp-151/153) 후 재평가에서 ytn2 무휴지 en→ko 전환을 잡아 median 개선·filler 소멸. E1/E2 3회기각(Exp-131/143/145)은 전환세금 미제거 상태의 결론이라 무효화. PLC=None이면 언어 고착 후 환각 급증.
- **[불변][diar]** Sortformer 과분할로 단일화자(sbs1) 문장분리 F1 급락(diar-ON 36.4% vs diar-OFF 76.2%, ref=3 vs hyp=9–11). **[E4·규명]** 이 과분할 근원은 **화자전환 이벤트가 아니라 문장경계 과분할**(`tokens_alignment` 온점분할) — Exp-155서 sbs1의 `new_speaker`(ChangeSpeaker) 발동이 **0회**로 확인(화자전환 조건부 리셋으론 sbs1 F1 개선 불가). **[E1]** ChangeSpeaker 2.0s 디바운스는 ytn2 회귀(Exp-106); nonspeech_prob=0.35는 bong1 환각↓이나 ytn2 부작용(Exp-107).
- **[불변][환각]** bong1 웃음 구간에서 Whisper 환각 다발(JSON 분석 확인).
- **[불변][환각·E2규명]** **bong1 worst-case 근본 원인 = 비음성(웃음·박수) 구간 언어 오감지** → 중국어/일본어 환각 캐스케이드(Exp-138 코드 규명). E2(lang_restrict_koen)가 CJK 언어토큰을 막아도 환각은 **사라지지 않고 라틴/한글 쓰레기로 형태만 바뀜**(Exp-139). → 비음성 구간 자체를 전사에서 배제(VAD/no_speech)하는 **Layer 3b가 미해결 1순위 과제**.
- **[E4·규명][필터]** **QualityGate(avg_logprob<-2.0) 부당드롭 = 0%**(Q1 규명, Exp-154 하니스). 억제 텍스트 전수 분류(bong1 46·ytn2 33·sbs1 14) 결과 전부 ① 비음성 마커(laughter/applause/speaking/AUDIO) ② 문장부호·단일문자 ③ **최종 전사에 이미 존재하는 중복 재디코딩 조각** ④ 환각조각뿐 — 정상 한국어 유실 없음. → **언어별 logprob 임계·드롭→재디코딩 수정 불필요**(사용자 확인). ytn2 회차분산은 QualityGate가 아닌 다른 원인(ForeignLang 혼란/재디코딩 churn/실오인식).
- **[불변][필터/반복]** master 유지 베이스라인 필터 = **Exp-002**(cross-batch stateful 반복)/**Exp-028**(단일음절 연속반복 억제+context 리셋)/**Exp-057**(배치 내 4-word 반복 드롭). 신규 언어특화 하드코딩보다 backend 대안 우선. `_filter_repetitions()`는 단일 `update()` 배치 내부만 동작 → cross-batch 반복은 stateful 필터 필요.
- **[불변][측정·레벨]** 입력 볼륨은 정상 범위(±12dB)에서 WER에 유의미한 영향 없음(Exp-157) — Whisper log-mel 창별 자기정규화(audio.py:155)로 절대 레벨 둔감, 회차 변동성(10~14pp) ≫ 레벨 효과(~3pp). ytn2를 −37.9 LUFS까지 낮춰도 VAD 미검출 없이 유지. bong1(핫/소스클립)만 감쇠 미세개선. **서버측 볼륨 정규화(AGC)는 미적용**(측정상 WER 이득 없음; 잔여가치는 배포 마이크 극단 오설정 로버스트니스뿐 — 이번 스윕 미측정). 게인 스윕(`eval.py --gain-db`)·`verify_loopback` 유니티 게인 검증(−20dBFS±1dB)은 진단 인프라로 상비.

## 빠른 참조

> **Epoch 열**: E1 = 언어고정 없음(master 이전) / E2 = `lang_restrict_koen=True` + 후처리 CJK/주석 필터 포함(현재 master, 2026-07-01 머지). suppress_nonspeech(Exp-138)는 E2에 **미포함** — 기각.
> **E1 파라미터 기각(131·132·133·137)은 E2 코드에서 재검증 대상** — 위 epoch 게이트 적용.

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

> **신규 실험 기록 위치**: Exp-140+ 전체 서술은 **[EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md)** 에 추가하고(작성 형식·전사 정성분석 가이드는 LOG 상단 + `/log-experiment`), **이 STATE 파일에는 위 빠른참조 표에 1행만** 추가한다(Epoch 열 포함). 확정 결론이 바뀌면 "이월 핵심사실"도 갱신. 구조 변경이 master에 머지되면 **epoch 마커를 올리고** 이전 epoch 파라미터 결론에 `[E?·재검증]` 부여.
