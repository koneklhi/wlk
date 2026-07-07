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

> ⚠️ **기질(substrate) 전환 — 2026-07-05 소급 확인 (Exp-158)**: **E1~E4는 전부 의도한 `whisper-large-v3-turbo`가 아니라 `base`(74M)** whisper 위에서 측정된 것이었다 — `SimulStreamingASR.__init__`이 `model_dir`을 무시하고 `model_path`만 확인하던 배선 버그(파라미터 차원 검증으로 확정: base=71.8M/512차원, turbo=807.0M/1280차원). 폐쇄망 배포는 인터넷이 없어 base 자동다운로드도 실패하는 **배포 블로커**였다. 아래 **E1~E4 항목의 파라미터 값·WER 수치는 전부 무효**(재검증 대상)이나, **구조적 코드 결정**(SimulStreaming·Sortformer 채택, 언어전환 프로토콜 Exp-150~153, 필터 Exp-139/152, 반복필터 Exp-002/028/057)은 코드에 그대로 남아있어 유효하다. **Epoch 5(E5) = turbo 기질, 최초로 의도한 모델 위 측정.**

- **현재 master = Epoch 5 (E5, turbo 기질) — 2026-07-05**: 두 버그 수정 머지(Exp-158, 커밋 9e3217e/d11f8b0/415ac39) — ① `model_dir` 배선 버그 수정(SimulStreamingASR가 실제로 turbo 로드) ② `detect_current_language()`가 `@torch.no_grad()` 밖에서 실행돼 turbo 인코더(807M·32층) forward가 autograd 그래프 보존, 0.2s→31.96s(~160배)로 폭주해 실시간 stall(FFmpeg read timeout)을 일으키던 버그 수정. **E1~E4의 모든 파라미터 결론(beam·CRT·PLC·logprob·frame_threshold 등)이 base 기질 위에서 나온 것이므로 turbo 기질에서 전면 재검증 필요.** 1차 turbo N=3: bong1 28.1%(base 대비 개선)/ytn2 41.9%(base 대비 대폭회귀)/sbs1 16.1%(개선이나 실시간 lag 최대 41s, RTX 3080). held-out 미측정.
- **Epoch 4 (E4, base 기질 — 이력, 수치 무효)**: E3 + **diar-ON 언어전환 경로 배선 활성화**(`prev_lang fallback`로 마커/2.5s 트림 실발동 + `PuncSegment.hard_boundary`로 diar 병합 경계보존). **Exp-153 머지 (dc312bb, 2026-07-03).** E3에서 **dormant**였던 전환 메커니즘이 측정경로(diar-ON)에서 처음 실동작 → 실패모드 변화: 전환경계 단어보존(§3.2/Q4) 획득 + **신규 재디코딩 filler 환각**("You know, in Bukhpil"류)·**마커 과분할**(F1 precision↓). E2 파라미터 결론(PLC·beam·CRT·nonspeech; Exp-131~149)은 전환 활성화로 거동이 또 달라지므로 **[E2·재검증]** 유지. **PLC는 Exp-154서 재평가 완료 → 기본값 4.0 채택**(전환세금 제거·배선 후 E1/E2 3회기각이 채택으로 전환; ytn2 무휴지 코드스위칭 유일경로). 단, **이 전체가 base 기질 위 측정 — 구조 결정만 유효, 파라미터 값은 재검증 대상.**
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

## 현재 베이스라인 (Epoch 5 — turbo, 확정)

> **turbo 기질 baseline (2026-07-06, Exp-161 최신)** — PLC 기본값 None 전환(Exp-160) + `audio_max_len` 30.0→15.0 전환(Exp-161) 이후 수치가 **현재 master 기본 설정 기준**. diar-ON, CRT=3.0, **PLC=None**, **audio_max_len=15.0(기본)**, beams=2.
> **확정 게이트(max)**: bong1≤30.5% / ytn2≤34.5% / sbs1≤16.1% (Exp-161 N=3로 갱신 — 3파일 모두 개선).
> JSON: `.omc/benchmarks/eval_20260705_2338_audiomax15_N3.json`(테스트 N=3) · `eval_20260706_0002_audiomax15_heldout.json`(held-out)

| 파일 | WER median | WER max | WER min | WER stdev | F1 median | 측정 N |
|------|-----------|---------|---------|-----------|-----------|--------|
| bong1 | 30.5% | 30.5% | 29.3% | 0.7% | 50.0% | 3 |
| ytn2  | **28.1%** | 34.5% | 24.6% | 5.0% | 38.5% | 3 |
| sbs1  | **14.9%** | 16.1% | 13.1% | 1.5% | 16.7% | 3 |
| ytn1(held-out) | 21.5% | — | — | — | 38.1% | 1 |
| eng1(held-out) | 4.8% | — | — | — | 0.0% | 1 |

**테스트 평균(median)**: WER 24.5% (Exp-160 직후 27.9%에서 대폭 개선, sbs1이 주도) · **분산 대폭 감소**(전 파일 stdev 1~5%대 — worst-case 안정성 확보, §3.8 최우선 원칙과 정합). **sbs1 실시간 lag**: 41s → **2s대**로 안정화(Exp-161).

**참고(audio_max_len=30.0 시절, PLC=None만 적용 — Exp-160, `audio_max_len` 변경으로 대체됨)**: bong1 30.5%/max33.5%/stdev3.0 · ytn2 30.0%/max38.4%/stdev7.2 · sbs1 23.2%/max30.4%/stdev10.6 · ytn1(held-out) 22.7% · eng1(held-out) 7.6%.

**참고(PLC=4.0 시절 E5 baseline, Exp-158/159 — PLC 기본값 변경으로 대체됨)**: bong1 28.1%/max34.7% · ytn2 41.9%/max47.3% · sbs1 16.1%/max31.0% · ytn1(held-out) 33.1% · eng1(held-out) 3.8%. PLC=None 대비 bong1·sbs1은 median이 더 좋았으나(단 sbs1은 고분산 파일), **ytn2는 PLC=4.0의 스퓨리어스 전환이 방송클로징 환각을 유발**해 크게 나빴다(Exp-160 규명).

**참고(base 기질 E4 baseline, 무효화됨 — Exp-153 N=3)**: bong1 36.3%/max37.5 · ytn2 25.6%/max26.1 · sbs1 20.2%/max26.8. turbo 대비 bong1·sbs1은 개선, **ytn2는 대폭 회귀**(코드스위칭 스캐폴딩이 base 거동에 맞춰 튜닝됐던 게 원인 추정 — 재조사 필요).

**✅ 실시간 lag 해결(Exp-161)**: sbs1 lag 41s(Exp-158, RTX 3080) → `audio_max_len` 30.0→15.0 전환으로 **2s대 안정화**(3회 재현: 2.04/2.03/2.17s). 배포(RTX 5090)는 더 여유 있을 것으로 예상되나 재확인 권장.

## 이월 핵심사실 (distilled — 상세는 LOG / [PHASE2_EXPERIMENTS.md])

> 태그: **[불변]** = 측정방법론·데이터특성·구조 → 모든 epoch에서 유효. **[E1·재검증]** = E1에서 측정한 파라미터 트레이드오프 → E2 코드에선 재검증 대상.
> **substrate 태그(2026-07-05 추가)**: **[모델무관·유지]** = base/turbo 어느 기질에서도 유효(구조 결정·측정방법론). **[base전용·재검증]** = base 기질(E1~E4) 위에서 나온 파라미터 결론 → turbo에서 전면 재검증 대상. **[base진단·재확인필요]** = base 기질의 실패모드 진단 → turbo에서 같은 현상인지 미확인.

- **[불변][측정][모델무관·유지]** 경로 C(VBCable)만 채택 판정 기준. 경로 A(PCM 주입)는 실사용과 무관 → 폐기.
- **[불변][측정][모델무관·유지]** Exp-106~129 전체 기각 — silent code-version trap(잘못된 cwd로 변경 미반영 측정) + VBCable 간헐 불안정 + provenance 미기록. provenance 하니스(Exp-130) master 머지 완료가 새 기준점.
- **[불변][디코더][모델무관·유지]** SimulStreaming 채택(Exp-001) — LocalAgreement는 영어 코드스위칭을 통째 누락하고 발화 후반 커버리지를 잃음. AlignAtt 실출력 토큰엔 **구두점이 없어** 구두점 기반 확정이 미발동 → 확정 신호는 VAD silence·세그먼트 경계·언어 전환에서 찾는다.
- **[E5·재검증완료][디코더][모델무관·유지]** `beam=2`(기본값)가 turbo에서도 최적으로 재확인(Exp-162) — beam=1(greedy)·beam=3 스크리닝 모두 3파일 중 2~3개가 게이트 초과(beam=3은 전부 초과). base 기질(Exp-125: beam2 28.1%→beam3 29.6%→beam4 40.4% 단조증가)과 동일 방향 — [base전용·재검증]에서 [모델무관·유지]로 격상. CRT=3.0도 재확인(2.5는 게이트 초과, 2.8은 baseline과 구분 안 됨) — 변경 불필요.
- **[E5·재검증완료][언어][모델무관·유지]** `periodic_lang_check`(PLC) 기본값 4.0(Exp-154, base 기질) → **turbo에서 N=3 재검증 결과 None(비활성)으로 전환(Exp-160)**: PLC=4.0의 주기적 재확인이 ytn2에서 스퓨리어스 언어전환을 오탐 → 트림+재디코딩 발동 → 방송클로징 환각("김정은 기자입니다" 반복)을 유발함을 정성 확인. PLC=None으로 해당 환각 완전 소멸, ytn2 median -11.9pp·max -8.9pp 개선. base 기질에서 "PLC=None이면 언어 고착 후 환각 급증"이었던 Exp-131/143/145 결론은 **turbo에서 재현되지 않음**(모델별 상이 — [base전용] 태그였던 근거가 뒤집힘). PLC=2.0(강화 방향)은 N=1에서 유사 개선 신호를 보였으나 **N=3에서 재현 실패**(ytn2 median 46.8%로 오히려 baseline보다 나쁨) — N=1 스크리닝 한계 사례로 기록.
- **[불변][diar][모델무관·유지]** Sortformer 과분할로 단일화자(sbs1) 문장분리 F1 급락(diar-ON 36.4% vs diar-OFF 76.2%, ref=3 vs hyp=9–11). **[E4·규명][base진단·재확인필요]** 이 과분할 근원은 **화자전환 이벤트가 아니라 문장경계 과분할**(`tokens_alignment` 온점분할) — Exp-155서 sbs1의 `new_speaker`(ChangeSpeaker) 발동이 **0회**로 확인(화자전환 조건부 리셋으론 sbs1 F1 개선 불가). **[E1][base전용·재검증]** ChangeSpeaker 2.0s 디바운스는 ytn2 회귀(Exp-106); nonspeech_prob=0.35는 bong1 환각↓이나 ytn2 부작용(Exp-107). **[E5·Exp-167 규명·모델무관·유지]** 이 문장경계 과분할의 근본원인 4갈래(Silence마커 순서경쟁·flush 0토큰·QG streak→refresh·구두점갭기반 (c)분기)를 실증 규명, 3갈래는 코드수정 완료(`tokens_alignment.py`)이고 나머지 하나("것으로/보입니다"류 잔존)는 버그가 아니라 **Silence 토큰 생성 문턱(`MIN_DURATION_REAL_SILENCE=0.4`) 부근의 VAD 측정 민감도** 때문임을 3/3 케이스로 실증(0.39s→병합, 0.45s→분할). 남은 sbs1 과분할은 문장확정 신호조합 정책(호흡성 pause를 하드경계로 볼지) 재검토가 필요한 **별개 사안**으로 재분류.
- **[불변][환각][모델무관·유지]** bong1 웃음 구간에서 Whisper 환각 다발(JSON 분석 확인) — 현상 자체는 Whisper 계열 공통 특성으로 추정되나 구체적 양상은 turbo에서 재확인 필요.
- **[불변][환각·E2규명][base진단·재확인필요]** **bong1 worst-case 근본 원인 = 비음성(웃음·박수) 구간 언어 오감지** → 중국어/일본어 환각 캐스케이드(Exp-138 코드 규명). E2(lang_restrict_koen)가 CJK 언어토큰을 막아도 환각은 **사라지지 않고 라틴/한글 쓰레기로 형태만 바뀜**(Exp-139). → 비음성 구간 자체를 전사에서 배제(VAD/no_speech)하는 **Layer 3b가 미해결 1순위 과제**. turbo N=3(Exp-158) 정성분석에서도 bong1에 필러/반복 환각("Thank you" 연쇄) 확인 — 양상은 다르나 문제 자체는 잔존. **[E5·Exp-163 실측강화]** turbo 'thank you' 필러를 backend 후처리 반복필터(v1 연속 n-gram·v2 윈도우-앵커)로 억제 시도 **실패·기각** — 필터가 스톰을 올바로 탐지·refresh해도 ①디코더가 refresh 후 필러를 **재생성**해 출력 드롭으로 못 막고 ②storm-refresh가 ytn2 정렬을 교란해 max 34.5→46.8 catastrophic 회귀. **→ 필러는 출력 후처리가 아니라 반드시 원천(Layer 3b 비음성 게이팅)에서 차단해야 함이 실측 확인됨.** **[E5·Exp-164 실측강화·모델무관·유지]** Layer 3b 원천 차단을 기존 두 메커니즘으로 시도 **실패·기각**: ① no_speech SOT 게이트는 **구조적으로 무효** — `_concat_segments()`가 롤링버퍼 전체(최대 audio_max_len=15s, 이전 실제 발화 포함)를 판정해 tail에 웃음/필러가 있어도 확률이 절대 안 오름(3파일 1221샘플 전부 정확히 0.000, 어떤 임계값도 무의미). ② VAC(Silero) 임계값 상향(0.4)은 신호 자체는 살아있으나(mean0.715·min0·max0.996) **개념적으로 부적합** — 웃음·필러는 실제 음성에너지(성대진동)를 동반해 "speech"로 통과되므로 임계값을 올려도 억제 안 되고(전사에 필러 그대로 잔존) bong1 게이트만 초과(34.4>30.5). **→ Layer 3b는 세그먼트 tail만 판정하는 구조 변경 또는 별도 비-ASR 웃음 분류기가 필요 — 기존 no_speech/VAC 확장으로는 도달 불가함이 확정.** **[E5·Exp-165 실측강화·모델무관·유지] no_speech tail 판정도 실패 → 폐기 확정**: Exp-164의 다음가설(tail만 판정하면 오르나?)을 `detect_current_language` tail-slice + `lang_id` SOT forward 재조합으로 구현·계측(진단전용, 게이팅 미연결). bong1(웃음)+ytn2(필러) tail(2.0s) 513샘플 + bong1 고정밀 290샘플 **전부 no_speech=0.000000**. 고정밀 진단에서 `ns_logit`이 -10.1~-10.5로 변동(forward 정상)·top_id=50360 top_p≈0.52(SOT 분포 정상)임에도 no_speech 토큰만 logit ~-10 고착 → **turbo no_speech 헤드가 tail 내용 무관 degenerate**임이 확정. **Exp-164의 "롤링버퍼 오염" 진단을 정정**(tail만 봐도 0 → 원인은 버퍼가 아니라 헤드). **Layer 3b no_speech 계열(전체버퍼·tail 모두) 폐기 확정 — 남은 경로는 웃음 전용 비-ASR 분류기 뿐(별도 설계 세션).**
- **[E4·규명][필터][base진단·재확인필요]** **QualityGate(avg_logprob<-2.0) 부당드롭 = 0%**(Q1 규명, Exp-154 하니스). 억제 텍스트 전수 분류(bong1 46·ytn2 33·sbs1 14) 결과 전부 ① 비음성 마커(laughter/applause/speaking/AUDIO) ② 문장부호·단일문자 ③ **최종 전사에 이미 존재하는 중복 재디코딩 조각** ④ 환각조각뿐 — 정상 한국어 유실 없음. → **언어별 logprob 임계·드롭→재디코딩 수정 불필요**(사용자 확인). ytn2 회차분산은 QualityGate가 아닌 다른 원인(ForeignLang 혼란/재디코딩 churn/실오인식). logprob 분포 자체가 모델마다 다르므로 turbo에서 재확인 필요.
- **[불변][필터/반복][모델무관·유지]** master 유지 베이스라인 필터 = **Exp-002**(cross-batch stateful 반복)/**Exp-028**(단일음절 연속반복 억제+context 리셋)/**Exp-057**(배치 내 4-word 반복 드롭). 신규 언어특화 하드코딩보다 backend 대안 우선. `_filter_repetitions()`는 단일 `update()` 배치 내부만 동작 → cross-batch 반복은 stateful 필터 필요.
- **[불변][측정·레벨][모델무관·유지]** 입력 볼륨은 정상 범위(±12dB)에서 WER에 유의미한 영향 없음(Exp-157) — Whisper log-mel 창별 자기정규화(audio.py:155)로 절대 레벨 둔감, 회차 변동성(10~14pp) ≫ 레벨 효과(~3pp). ytn2를 −37.9 LUFS까지 낮춰도 VAD 미검출 없이 유지. bong1(핫/소스클립)만 감쇠 미세개선. **서버측 볼륨 정규화(AGC)는 미적용**(측정상 WER 이득 없음; 잔여가치는 배포 마이크 극단 오설정 로버스트니스뿐 — 이번 스윕 미측정). 게인 스윕(`eval.py --gain-db`)·`verify_loopback` 유니티 게인 검증(−20dBFS±1dB)은 진단 인프라로 상비 — 이 인프라 자체는 모델 무관.
- **[E5·신규][모델무관·유지]** `SimulStreamingASR.__init__`의 `model_dir` 배선 버그(Exp-158) 수정 후, 다른 백엔드(qwen3/voxtral)와 동일하게 `model_dir or model_path` 폴백 패턴 적용됨 — 향후 SimulStreaming 관련 모델 경로 변경 시 이 패턴 유지.
- **[E5·규명][base전용·재검증]** turbo 전환으로 코드스위칭 실패모드 자체가 변함: ytn2에서 방송 클로징류(Exp-157서 "MBC 뉴스…") 대신 **"Thank you" 연쇄 필러 환각**이 우세하게 관측(Exp-158) — turbo가 불확실 구간에서 "더 그럴듯하게" 필러를 생성하는 경향으로 추정. base용으로 튜닝된 코드스위칭 스캐폴딩(언어전환 프로토콜·PLC)이 이 신규 실패모드에 적절한지 재검증 필요.
- **[E5·규명][모델무관·유지]** "Thank you" 필러 폭주가 **bong1·ytn2에 이어 ytn1(held-out)에서도 재현**(Exp-159) — turbo 전반의 일반적 실패모드로 확정(3개 파일 공통). 단 ytn2의 **catastrophic 콘텐츠 대체(방송클로징 환각)는 쌍둥이 ytn1에서 재현되지 않음** — 코드스위칭 일반의 문제가 아니라 ytn2 파일 고유의 음향/정렬 난이도(`audio-feature-analysis` 미머지 도구의 앵커율 46% 발견과 정합)가 만든 최악 사례로 추정.
- **[E5·채택][성능][모델무관·유지]** `audio_max_len` 기본값 **30.0→15.0 채택(Exp-161)** — sbs1 lag 41s(Exp-158)의 원인은 매 infer() 호출마다 버퍼 전체를 재인코딩하는 비용 누적으로 규명. 15.0으로 낮춰 lag 2s대 안정화 + 3파일 모두 WER median·max·stdev 개선(특히 sbs1 23.2%→14.9%, stdev 10.6→1.5). 원인이 "인코딩 비용 대 버퍼 크기"라는 압축가능한 계산량 문제이므로 모델(base/turbo) 무관하게 유효할 가능성 높음(단 base에선 미검증).
- **[E5·Exp-168 규명·모델무관·유지]** Exp-90의 "Thank you" 필러 재검증 완료(부분): ytn2에서 EN↔KO 전환 경계 직후 필러가 실제 발화를 통째로 삼키는 메커니즘 확정 — ① 기존 4개 필터(QualityGate·BatchRepeatFilter·CrossBatchFilter·DRY)는 전부 "완전동일반복" 또는 "한국어 전용"을 전제해 "영어+변주" 필러에 원리상 무력(`BatchRepeatFilter`의 `[가-힣]` 조건이 결정적 사각지대). ② `new_speaker()`의 eager 언어감지가 화자전환 경계시각과 무관하게 버퍼 끝 "마지막 1.5초"를 무조건 잘라, 새 화자 발화 직후엔 직전화자 오디오로 오판하는 별개 메커니즘도 확정. 두 방어선(언어-스크립트 불일치 게이트 + since_offset 시각보정)으로 ytn2의 두 관측 경계 모두 해결(WER 43.8%→26.1% max). **단, bong1·held-out 등 다른 파일의 필러 발생 여부는 이번 조사 범위 밖**(§ Req-3/CASE3에서 재검증 필요) — "Thank you 필러가 turbo 전반의 일반적 실패모드"라는 Exp-159 결론 자체를 뒤집는 것은 아님.
- **[E5·Exp-169 규명·모델무관·유지]** CASE3 script-agnostic 앵커 반복게이트(gap-tolerant 클러스터링, MIN_COUNT=4·MAX_GAP=5·MIN_CONCENTRATION=0.6)는 짧고 규칙적인 storm(ytn2 "김정은"×4류)은 완전 억제하나, **가변 길이 변주구가 낀 storm(예: "Thank you [긴 변주구] Thank you" 반복)은 앵커 사이 gap이 5단어를 넘어 서브클러스터(예 3+2)로 쪼개져 MIN_COUNT 문턱을 피해가는 사각지대가 실측(N=3)으로 확인됨** — Req-2가 해결했던 ytn2 두 경계(안보리결의 직후·정경두 국방장관 직전)에서 이 사각지대형 storm이 각 1/3 빈도로 재현, 목표 문장 전체를 완전 대체(catastrophic swallow). 게이트 로그(`AnchorRepeatFilter`)가 두 재현 지점에서 전혀 발동하지 않아 게이트 자체가 원인이 아님은 확정(원래도 존재하던 잔존 위험). 향후 이 사각지대(가변 변주구 storm) 대응 시 MAX_GAP 단순 확대보다 "근접 시간창 내 앵커 총 등장" 같은 재설계 고려.

## 빠른 참조

> **Exp-001~157 = base 기질 시대(2026-07-05 이전)** — 전체 표는 [EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md) 상단으로 이관됨(STATE 예산 절약). 구조 변경(Exp-139·143·150·151·152·153)만 유효, 파라미터 결론은 전부 재검증 대상 — 위 "코드 세대(Epoch)" 절 참조.
> **Epoch 열**: E5 = turbo 기질(2026-07-05~). E1~E4 = base 기질(무효, 이력).

| Exp | Epoch | 날짜 | 변경 | bong1 WER med | ytn2 WER med | sbs1 WER med | 판정 |
|-----|-------|------|------|--------------|-------------|-------------|------|
| Exp-169 | **E5** | 2026-07-07 | CASE3 환각폭주 — script-agnostic 앵커 반복(필러storm) 게이트 신설(`_find_anchor_repeat_storm`, `dc0dc35`), master 미머지·사용자확인대기 | 35.3% | 26.1% | 13.7% | 🟡 조건부채택권고 (§5 3조건 클린통과 + storm 최대반복 4→3·ytn2"김정은"storm 소멸 달성; 단 Req-2 두경계 재검증 결과 3/3 아닌 2/3씩(각 1회 catastrophic swallow 재현) — 게이트 미발동 구간에서 발생해 이번 변경과 인과무관 확정, 가변변주구가 gap-tolerant 클러스터링을 3+2로 쪼개는 사각지대 잔존; 사용자 확인 후 머지여부 결정) |
| Exp-168 | **E5** | 2026-07-07 | CASE2 코드스위칭 서두유실 — 전환경계 필러환각 해소(언어-스크립트 불일치 게이트 `8aeb5a2` + eager 언어감지 since_offset `0fed0d5`), master 머지 | 27.8% | **19.7%**(43.8%→대폭개선) | 16.7%(max48.8%❌) | ✅ 채택 (ytn2 두 경계 필러폭주 3/3·3/3 해소; sbs1 max초과는 화자전환0회라 이번 코드경로 미호출 확인 + 기존 저빈도 stall현상(Exp-167서도 0/3)임을 실증, 사용자 확인 후 채택; ytn1 held-out도 개선) |
| Exp-167 | **E5** | 2026-07-07 | CASE1 문장꼬리분리 4대경로 완료 — 온점분할 갭기반 (c)분기 완전제거(FIX1, `e6ae496`; Direction A `dd33fe7`는 갭측정 혼동으로 기각), master 머지 | 28.7% | 36.0%(별개이슈) | 14.3% | ✅ 채택 (bong1 타겟패턴 "자빠졌/는데" 3/3 확정해결; sbs1 "것으로/보입니다" 잔존 1/3은 CASE1 버그 아닌 Silence 0.4s 문턱 경계 정책 이슈로 재분류 실증; ytn2 WER악화는 기존 "Thank you" 필러환각(CASE3 대상)과 무관 확인) |
| Exp-166 | **E5** | 2026-07-06 | LANG_SWITCH_KEEP_SECS 스윕(3.5/4.5) `--lang-switch-keep-secs` CLI, master 미머지 | 31.1/28.4% | **40.9/34.5%** | 15.5/**18.5%** | ❌ 기각 (N=1: ytn2 두 값 모두 baseline median 위·서두 유실 미완화(정성 잔존/악화), sbs1 4.5 게이트 초과; ytn2 지배오류=필러스톰·방송환각으로 keep_secs 무관) |
| Exp-165 | **E5** | 2026-07-06 | tail-only no_speech shadow probe(tail-slice 재조합 계측), master 미머지 | — (probe 로깅전용·WER 해석불가) | — | — | ❌ 기각·폐기확정 ((b)분리불가: tail 513샘플+고정밀 290샘플 전부 no_speech=0.000000, ns_logit≈-10 고착 = turbo no_speech 헤드 degenerate; Exp-164 "버퍼오염" 진단 정정 = tail도 0; Layer 3b no_speech 계열 폐기, P3 스킵) |
| Exp-164 | **E5** | 2026-07-06 | 비음성 게이팅(no_speech 계측+VAC 임계값 스윕 0.4), master 미머지 | **34.4% (max초과 ❌)** | 30.0% | 11.9% | ❌ 기각 (no_speech는 롤링버퍼 전체판정이라 구조적 무효(1221샘플 전부 0.000) — 스윕 스킵; VAC=0.4는 게이트 초과 + 웃음/필러 전사 그대로 잔존, VAC가 음성에너지만 판정해 개념적으로 부적합) |
| Exp-163 | **E5** | 2026-07-06 | cross-batch 필러 반복 필터(v1 연속 n-gram→v2 윈도우-앵커), master 미머지 | 26.3% (필터0회·분산) | **34.0% (max46.8 ❌)** | 16.1% | ❌ 기각 (ytn2 max catastrophic; 후처리 필터가 디코더 필러 재생성 못 막고 storm-refresh가 ytn2 정렬 교란해 악화; 원천 비음성게이팅으로 피벗) |
| Exp-162 | **E5** | 2026-07-06 | P3 재검증(beam 1/3, CRT 2.5/2.8), 코드변경 없음 — 스크리닝만 | — | — | — | ➖ 변경없음 채택 (beam=2·CRT=3.0 재확인, beam=1/3·CRT=2.5는 게이트 초과로 스크리닝 단계 기각, CRT=2.8은 baseline과 무구분) |
| Exp-161 | **E5** | 2026-07-06 | audio_max_len 기본값 30.0→15.0 — sbs1 실시간 lag(41s) 해결 | 30.5% (동일, stdev 3.0→0.7 안정화) | **28.1%** (30.0%에서 추가개선) | **14.9%** (23.2%에서 대폭개선) | ✅ 채택 (3파일 모두 max·median·stdev 전부 개선 — 가장 명확한 채택; lag 41s→2s대) |
| Exp-160 | **E5** | 2026-07-05 | PLC 기본값 4.0→None(비활성) — ytn2 스퓨리어스 전환→방송클로징 환각 근본원인 규명 | 30.5% (28.1%에서 소폭악화) | **30.0%** (41.9%에서 -11.9pp 개선) | 23.2% (16.1%에서 악화, max는 개선) | ✅ 채택 (①max 3파일 모두 미회귀 ②ytn2 median·max 확실개선; PLC=2.0은 N=3서 재현실패해 기각) |
| Exp-159 | **E5** | 2026-07-05 | held-out(ytn1/eng1) 확정 측정, 코드변경 없음 — P0 완료 | — | — | — | ℹ️ baseline 확정 (ytn1 33.1%로 ytn2보다 8.8pp 양호 → ytn2 회귀는 파일고유 난이도 쪽; eng1 3.8%로 영어 회귀 없음; 게이트 max 변경 없음) |
| Exp-158 | **E5** | 2026-07-05 | model_dir 배선버그 수정 + no_grad stall 수정 — turbo 기질 전환 [E4→E5] | 28.1% (base 대비 -8.2) | 41.9% (base 대비 +16.3 ❌) | 16.1% (base 대비 -4.1) | ✅ 채택 (correctness 버그 — WER 게이트 무관 필수, 폐쇄망 배포 블로커였음; ytn2 회귀는 코드스위칭 스캐폴딩 base종속 추정, 별도 재조사 필요; held-out 미측정) |

---

> **신규 실험 기록 위치**: Exp-159+ 전체 서술은 **[EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md)** 에 추가하고(작성 형식·전사 정성분석 가이드는 LOG 상단 + `/log-experiment`), **이 STATE 파일에는 위 빠른참조 표에 1행만** 추가한다(Epoch 열 포함). 확정 결론이 바뀌면 "이월 핵심사실"도 갱신. 구조 변경이 master에 머지되면 **epoch 마커를 올리고** 이전 epoch 파라미터 결론에 `[E?·재검증]` 부여.
