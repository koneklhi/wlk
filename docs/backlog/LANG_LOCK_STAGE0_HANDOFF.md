# 언어잠금 환각 대응 — Stage 0 완료 인계 (2026-07-21, 표본 확대분 반영)

> **한 줄**: 한국어 발화가 영어로 번역/음차되는 "언어잠금" 실패를 정량화하는 지표(LMR)와 검출 계측(SOT 프로브)을
> 구현·측정 완료했고, **Stage 0 판정은 GO**(용법 한정)다. 이어서 **안 A(표본 확대)를 실행 완료**했고,
> 그 결과 **Stage 1(안 B)은 착수하지 않고 정지**했다 — 사용자 판단 대기.
>
> **⛔ 정지 사유 (먼저 읽을 것)**: 단일언어 ko 세션에서 `p_opp≥0.97` 발동이 관측돼, 안 A 착수 시
> 사전 등록한 진행 조건("단일언어 세션 정상 전사 구간 발동 0건")을 충족하지 못했다.
> `--repeat 3` 확증까지 마친 누계는 **ko 12세션 3756 프로브 / 발동 23건(0.61%) / 순수 오탐 확정**이며,
> 동일 지점이 3/3 회차 반복되는 **결정론적** 패턴이다.
> 단 발동 23건 전부 `seglen ≤ 1.02s` · 최대 연속 K=2라 **Stage 1 게이트에 23/23 전부 걸린다**(would_fire 0).
> 즉 판단은 정보 부족이 아니라 **설계 수용 여부**의 문제다.
> 수치·전수 분류·양쪽 근거 = **§4-0 / §4-0-1**. 상세 정본 = `docs/research/SOT_LANG_PROBE_STAGE0.md` §10.

---

## 0. 지금 어디에 있나

| 항목 | 값 |
|---|---|
| 브랜치 | `exp/lang-lock-stage0` |
| 워크트리 | `worktrees/bong1-eval-diagnostics/` (`.venv` junction·모델·wav 하드링크 셋업 완료) |
| 분기점 | `d4b7556` 시점 master. **이후 master가 `6b6effa`(feat/deploy-ui 머지)로 전진했다** — 채택 단계에서 재베이스 필요 |
| 상태 | 전부 커밋됨. 테스트 648 pass, ruff clean |

### 커밋 (오래된 것부터)

| 커밋 | 내용 |
|---|---|
| `6b6336e` | 정답 비언어 태그(`(웃음)(박수)(환호)(잡음)(더듬)`)를 WER·F1 계산에서 제외 |
| `9ba0f2d` | `[RefreshSegment]`·`[ShortSilenceLangCheck]`·`[QualityGate]` 진단 로깅 |
| `38bf97b` | **LMR 진단 지표** — `metrics.py` `_align_ops`/`compute_language_mismatch` + eval 배선 + backfill CLI |
| `b1a5e63` | **SOT 사후분포 계측** — `_read_sot_posteriors`, 추가 forward 0·행동 변경 0 |
| `cdbb452` | 연동 문서 갱신 (TRANSCRIPTION_REQUIREMENTS §2~5, eval.md, TESTING.md, CLAUDE.md) |
| `5466b87` | **Stage 0 판별력 분석** — `analyze_sot_lang_probe.py` + `docs/research/SOT_LANG_PROBE_STAGE0.md` |
| `8f20dd5` | **표본 확대(Exp-195)** — `SOT_LANG_PROBE_STAGE0.md` §10 + 6파일 전사·프로브 분석 산출물. **코드 변경 0** |

메인 저장소 `EXPERIMENTS.md`의 stale 정정 2건(Exp-190/192 "미머지"→머지 완료, 음차 해소 오기록 정정)은
master `e4284cf`에 **커밋 완료**됐다 — 재작업 불필요.

---

## 1. 무슨 문제를 푸는가

`detected_language`가 `en`에 고착된 상태로 한국어 오디오가 들어오면 Whisper가 off-manifold 상태
(학습에 `<|en|><|transcribe|>`+한국어 조합이 없음)에서 **한국어 발화를 영어로 번역·음차 출력**한다.

```
정답  누가 주인공일까 이런 생각을 제가 제일 많이 했어요
전사  is the one who is the main I think that's what I've done

정답  죄송합니다 형님. 들고서 메타포리칼하다고 하잖아요.
전사  Sorry, my name metaphorical as a metaphorical thing, so.
```

의미가 보존된 번역이라는 점이 진단의 핵심 증거다(자유 환각이 아니라 언어 토큰 오지정).

**왜 기존 방어선이 전부 무력한지** (전부 코드로 확인됨):

| 방어선 | 무력한 이유 |
|---|---|
| `suppress_tokens` (`simul_whisper.py:105-112`) | `<\|translate\|>`·모든 언어 토큰이 **이미** 생성 금지. translate는 토큰 스위치가 아니라 가중치에 학습된 행동이라 억제로 못 막는다 |
| QualityGate (`align_att_base.py:697`) | 유창한 영어 번역은 **logprob이 높고 compression ratio가 낮다**. 확신에 차서 틀린 경우 |
| ScriptAnchorRedetect (`backend.py:203-206`) | 방출 텍스트의 스크립트 반전을 본다. en 잠금 중엔 방출이 계속 Latin이라 **반전이 안 일어난다** — 자기충족적 맹점 |
| `_detect_language_if_needed` (`align_att_base.py:284-288`) | `detected_language is None`일 때만 진입 → 세션 최초 1회 |
| `refresh_segment` (`align_att_base.py:153-192`) | 언어 재확인 없이 기존 언어 재확정. 회당 24~40회 발동, 오디오 99~133초 폐기 |

---

## 2. 확정된 사실 (수치)

### 2-1. 피해량 — LMR 지표, bong1 10회 소급 (재측정 0회)

| | median | min | max |
|---|---|---|---|
| WER | 30.06% | 22.36% | 43.50% |
| LMR_ko (한국어 정답 중 영어로 뒤집힌 비율) | **15.4%** | 7.7% | 37.4% |
| **WER 귀속량** (`lmr_wer_pp`) | **4.38%p** | 2.11%p | **10.27%p** |
| LMR_en (역방향) | 0.0% | 0.0% | 0.84% |

- 언어잠금이 bong1 WER median의 **약 14%**, 최악 회차의 **24%**를 먹는다. `corr(LMR_ko, WER) = +0.724`.
- 실패는 **en 잠금 단방향**(역방향은 10회 통틀어 4건).
- **LMR은 하한**이다 — 정렬이 `del`+`ins`로 갈라진 피해는 미포착(`ko_del` median 8.5단어).
- **채택 게이트가 아니다.** 게이트 순서(화자F1 worst → WER max → WER median → 문장F1)는 불변, LMR은 원인 귀속용.

### 2-2. 제2 실패 축 (별개, 미착수)

같은 분해에서 나온 것:
- **영어 단어 삽입** median 22단어(≈WER 6.6%p) — 언어잠금(4.38%p)보다 큰 버킷. 필러 환각 + 재디코딩 이음매 중복이 섞여 있다.
- **영어 누락** worst 회차 폭증 — R1 36단어·R10 34단어 vs 평시 6~16단어(`en_del`).
- 계측 함정: `(더듬)`은 **실제로 발화된** "이 그 저"를 지운 것이라 STT가 정확히 전사하면 삽입 페널티를 받는다. `(웃음)(박수)`와 성격이 다르니 삽입 축을 다룰 때 분리할 것.

사용자 판단으로 **언어잠금을 우선**하고 삽입 축은 보류했다.

### 2-3. Stage 0 — 검출 신호 판별력 (bong1 R1 + ytn2 R1, 각 1회)

**살아남은 신호는 `p_opp`(잠긴 언어의 반대쪽 재정규화 확률) 하나뿐.**

| | 배경 median | 발동(τ=0.97) | 정상 전사 구간 발동 |
|---|---|---|---|
| bong1 R1 | 0.000763 | 28/457 (4개 버스트) | **0건** |
| ytn2 R1 | 0.000312 | 25/239 (4개 버스트) | **0건** |

버스트가 실패 지점에만 뭉친다:

```
bong1 버스트1  t=14.34-16.26s  locked=en  p_opp med=0.9994
   직전 방출 ', what|did you|think'  →  버스트 내 'is the one|who is the main'
bong1 버스트3  t=112.23-113.67s locked=en p_opp med=0.9831
   직전 방출 '죄송|합니다|형'        →  버스트 내 '- Sorry|, my name'
ytn2  버스트2  t=37.15-43.70s  locked=en  p_opp med=0.9993  (22배치)
   정답 한국어 문장이 통째 소실 → 'Thank you very much' 필러 환각으로 대체
```

**오탐 전수 분류**: bong1 33건 = 참양성 32 + 정당전환 선행 1 + **순수 오탐 0**.
ytn2 26건 = 참양성 22 + 정당전환 선행 4 + **순수 오탐 0**. Exp-160 스퓨리어스 재현 없음.

**선제성**: 이벤트 A −0.80s(잘못된 잠금 적용 *전*), B 0.00s(동시), C −2.88s(9배치 연속).

---

## 3. 반증된 것 — 되살리지 말 것

이 절이 이 문서에서 가장 중요하다. 아래는 전부 **데이터로 죽었다**.

| 아이디어 | 반증 근거 |
|---|---|
| **S3 — task 위치에서 translate 신호 검출** | `p_translate`가 두 파일 **723개 프로브 전부 정확히 0.000000**, `p_transcribe` 0.99995+ 고정. 이 실패는 task 토큰 누출이 아니라 **언어 토큰 오지정**이다 |
| **S2 — resid(비정규화 잔여 질량)** | bong1 88%(420/479) 배치가 문턱을 넘어 무의미하고 대체 문턱도 없다. ytn2에선 **방향 역전**(표적 0/24 vs 대조 7/201) |
| **S2 — H_lang(엔트로피)** | ytn2에서 역전 |
| **p_nospeech** | 전 배치 0. (turbo no_speech 헤드 degenerate — Exp-164/165 기존 결론과 일치) |
| **top1−top2 마진을 독립 게이트로** | `lang_restrict_koen`(기본 ON)으로 후보가 2개뿐이라 `margin = 2p−1`. p의 단조변환일 뿐 |
| **ko/en 제한 정규화를 "새 레버"로** | 이미 기본 ON (`config.py:28`, `parse_args.py:426`). 기존 로그의 `en p=0.99`는 **이미 재정규화된 값** |
| **refresh_segment 직전에 감지** | 그 지점엔 `encoder_feature`가 없다(호출부가 전부 `infer()` 밖) → 인코더 재실행 0.2s 필요. 게다가 음차는 고logprob이라 QG를 안 건드려 refresh 시점과 겹치지 않는다 |
| **"전환을 프로브로 승인"하는 용법** | 프로브는 *오디오 버퍼 내용*을 읽는다. 전환 경계에선 버퍼가 아직 이전 언어라 **직전 잠금에 동조**한다(bong1 3회 `p_en` 0.995~0.9997). 이 규칙을 넣었으면 정당한 한국어 전환 2건을 차단했을 것이다 |
| **인코더 독립 LID(VoxLingua107)** | 선행 PoC에서 NO-GO — 음차 창을 Khmer 0.90/English 1.00으로 오판 |
| **Exp-190/192가 음차를 해소했다** | **오기록.** Exp-190은 침묵 게이트(언어 무관), Exp-192는 감지가 이미 옳다는 전제의 경계 정리. bong1 N=10에서 음차 5/10 재현 |

**지지되는 용법은 하나뿐**: "잠금 유지 중 **지속** 불일치가 관측되면 재감지를 강제한다."

### 과거 실험이 준 설계 제약

재감지 자체는 무해하다(Exp-101/102/104/175/179/189 전부 채택). **재감지에 딸려오는 버퍼 파괴가 catastrophic을 만든다**:

| Exp | 시도 | 결과 |
|---|---|---|
| Exp-095 | 주기 재감지 + `refresh_segment(complete=True)` | sbs1 **70.8%** |
| Exp-096 | 짧은침묵 후 재감지 + full reset | ytn1 max **101.2%** |
| Exp-097 | `create_tokenizer(None)`로 언어 강제 제거 | sbs1 **138.7%** |
| Exp-160 | periodic_lang_check 활성 | 스퓨리어스 오탐 → 환각. **PLC=None이 현행 채택값** |
| Exp-101 | 재감지 + **버퍼 유지** | ✅ 채택 |
| Exp-189 | eager 쿨다운 | ✅ 채택. **p=0.95~1.00 고신뢰 오탐이 실측됨 — 문턱만 높여선 못 막는다** |

`_apply_detected_language`(`align_att_base.py:234-282`) 주의:
`skip_trim=True`는 **철회 arm을 막지 않는다**(`:269`의 `if is_switch:`가 가드 밖). 그리고 `:279`의
`pending_retract_floor`가 전체 버퍼 길이(최대 15s)만큼 내려가 **트림보다 blast radius가 커진다**.
Exp-192의 동적 keep(`clamp(버퍼끝−last_emit_end+0.3, 2.5, 5.0)`)이 이미 "이미 방출된 오디오만 폐기"를
구현하므로, 적용은 **`_apply_detected_language(new_lang)` 기본 경로를 그대로 재사용**할 것.
`create_tokenizer`를 직접 부르면 Exp-150이 고친 SOT 미갱신 버그가 재발한다.

---

## 4. 다음 단계 — 안 A·안 B 완료(계측), 실제 게이트 적용(트리거 배선) 여부가 다음 결정

| 안 | 내용 | 상태 |
|---|---|---|
| **A. 표본 확대** | **코드 변경 0.** 현 계측 그대로 sbs1·kor1~3(`--lan ko`)·eng1(`--lan en`)·ytn1을 돌려 **단일언어 세션 오탐률**(최대 미지수)을 메운다 | ✅ **완료 (2026-07-21, Exp-195)** — 결과는 §4-0. kinno만 미측정 |
| **B. Stage 1 섀도우 판정** | 게이트 G1~G7(최소 버퍼길이·연속 K배치·쿨다운·다른 트리거 중복방지·auto 가드) 구현하되 **적용 안 함**, `would_fire`만 로깅. auto 4파일(bong1/ytn2/sbs1/ytn1) 측정 | ✅ **완료 (2026-07-22, Exp-197)** — 결과는 §4-0-3. would_fire: bong1/ytn2/sbs1=0, ytn1(held-out)=15(연속 1에피소드·정성 확인상 참양성). **실제 게이트 적용(트리거 배선) 여부는 사용자 판단 대기** |
| **C. 종료** | `/log-experiment`로 Exp 번호 부여·기록하고 닫는다. 계측·지표는 브랜치에 남아 언제든 재개 가능 | Exp-195·Exp-197 부여·기록 완료. 종료 여부는 미결정 |

### 4-0. 안 A 결과 — “가장 큰 미지수”의 답 (Exp-195)

> 정본 = `docs/research/SOT_LANG_PROBE_STAGE0.md` §10. 아래는 판단에 필요한 요지만.

**§7 “단일언어 세션 오탐률 전혀 모름”은 해소됐고, 답은 “0이 아니다”.**

| 파일 | 모드 | WER | LMR_ko | 발동 τ=0.97 | 연속 run | 게이트 통과¹ |
|---|---|---|---|---|---|---|
| kor1 | ko | 40.9% | 0.0% | **3** | 3 (전부 K=1) | **0** |
| kor2 | ko | 18.6% | 0.0% | **1** | 1 (K=1) | **0** |
| kor3 | ko | 33.8% | 0.0% | **1** | 1 (K=1) | **0** |
| eng1 | en | 5.7% | n/a | **0** | 0 | **0** |
| sbs1 | auto | 11.3% | 0.0% | **0** | 0 | **0** |
| ytn1 | auto | 20.2% | **19.7%**(9.2%p) | **25** | 4 | **2** (전부 참양성) |

¹ 오프라인 재현(`K≥3 ∧ T≥1.0s ∧ seglen≥2.0s`). 런타임 쿨다운·타 arm 미반영이라 **상한**이다.

- ko 발동 5건 중 **순수 오탐 2건 확정**(kor2 b1 `먼저 육군`, kor3 b30 `원 거리 타격` — 둘 다 정상 전사 구간).
  나머지는 kor1 서두 자막 환각 구간 1건 + 회색 2건. → §2-3의 “순수 오탐 0”은 **코드스위칭 파일 한정**이었다.
- 그러나 **5건 전부 K=1 단발 · seglen 0.24~1.02s**이고, 다음 배치에서 즉시 문턱 아래로 자기교정된다
  (kor2 건은 `Refreshing segment` 직후 잔여버퍼임이 로그로 확인 — §4 게이트가 `seglen≥2.0s`를
  “가장 중요”하다고 지목하며 막으려던 Exp-189 실패모드 그 자체).
- ytn1은 정답 한국어가 `Yeah, I'm not sure how many years I'm happy to be here`로 전사된 **교과서적
  언어잠금 실패**이고, 프로브 버스트가 그 구간에 정확히 뭉친다. LMR_ko 19.7%(`ko_to_en=15`)가 독립 확증.
- 단일언어 4종 LMR은 `ko_to_en=0`·`en_to_ko=0` — 프로브와 **독립적으로 같은 결론**(단일언어 세션에
  언어잠금 실패는 없다). 즉 ko 발동 5건은 “LMR이 놓친 실패”가 아니라 신호 쪽 오탐이다.

**왜 정지했나**: 안 A 착수 시 사전 등록한 분기 기준은 “ko/en 단일언어 세션에서 정상 전사 구간 발동
0건, 또는 전부 정당전환 선행으로 설명됨”이었다. 실측은 **둘 다 아니다**(kor1~3은 설계상 단일언어
낭독이라 정당전환이 존재할 수 없다). 기준을 사후에 완화해 진행하는 것은 “게이트 파라미터를 임의로
보수적으로 튜닝해 계속 진행”에 해당하므로, 약속대로 멈추고 판단을 넘긴다.

**사용자 결정을 위한 양쪽 근거**

- *계속*: 오탐 5건은 게이트가 **사후 튜닝 없이 이미** 배제하도록 설계돼 있었고(would_fire 0),
  ytn1 참양성 run 2개는 통과한다 — 게이트 뒤에서 신호/잡음이 깨끗이 갈린다.
- *중단*: Exp-189가 경고한 “p=0.95~1.00 고신뢰 오탐”이 **실제로 재현됐다**. 게이트가 막아준다는 판단은
  `--repeat 1` 표본 1회에 의존하며, `seglen≥2.0s`를 넘는 오탐이 다른 회차에 없다는 보장은 없다
  (이 프로젝트는 stdev 6.1%p가 5/10 빈도 현상을 가린 전례가 있다 — §6-7).

### 4-0-1. `--repeat 3` 확증 — ①은 이 세션에서 이미 수행됨

위 권고 ①(kor1~3 N=3 재측정)을 같은 세션에서 실행했다(코드 변경 0, 동일 설정). **ko 세션 누계 12개.**

| | 값 |
|---|---|
| probes | 3756 |
| 발동 τ=0.97 | **23건 (0.61%)** — 재현성 있음 |
| 발동 시 `seglen` | 0.24s ×20 · 0.48s ×2 · 1.02s ×1 → **최대 1.02s** |
| `seglen ≥ 2.0s` 발동 | **0건** |
| 최대 연속 K | **2** (K=3 미달) |
| **게이트 통과** | **0 / 23** |

WER median(N=3): kor1 21.6%(16.4/26.3, stdev 5.0) · kor2 24.1%(19.3/24.8, 3.0) · kor3 35.8%(28.5/39.1, 5.4).
LMR은 9/9 세션 전부 0.0%.

**두 결론이 동시에 굳었다.**
1. 오탐은 실재하고 **결정론적으로 재현**된다 — kor2 b1, kor3 b1·b30은 3/3 회차에서 같은 지점에 발동.
   랜덤 노이즈가 아니므로 §2-3의 “순수 오탐 0”은 최종 반증됐다.
2. 그러나 오탐은 **`seglen ≤ 1.02s`라는 좁은 체제에만 산다.** `segments_len() ≥ 2.0s` 조건
   하나만으로 23/23이 배제되며, 이는 사후에 맞춘 문턱이 아니라 §4가 Exp-189 대응으로 **미리** 지정한 값이다.

→ **판정(Stage 1 정지)은 유지한다.** 다만 정지 사유가 “표본이 1회뿐이라 모른다”에서
**“재현되는 고신뢰 오탐이 존재한다는 사실 자체”**로 바뀌었다 — 판단의 성격이 정보 부족이 아니라
설계 수용 여부로 이동했다.

**재개한다면 남은 순서**: ①은 완료됐으므로 곧바로 **② 안 B(섀도우 `would_fire` 로깅)**로 갈 수 있다.
착수 전 확인할 것은 “런타임 게이트가 오프라인 재현과 동일하게 23/23을 막는가”이며, 그것이 바로
섀도우 모드가 측정하려는 값이다.

### 4-0-2. en 방향도 N=3까지 닫음 + **오탐/참양성의 방향 분리**

eng1도 `--lan en --repeat 3`으로 재측정했다(코드 변경 0). **eng1 누계 4세션 500프로브 = 발동 0건.**
WER median 3.8%(min 2.9 / max 6.7 / stdev 2.0). → **안 A의 사전 등록 표본이 전부 닫혔다.**

| 방향 | 세션 | probes | 발동 | 성격 | 게이트 통과 |
|---|---|---|---|---|---|
| `locked=ko` (ko 세션) | 12 | 3756 | **23 (0.61%)** | **전부 오탐/회색** — 참양성 0 | **0 / 23** |
| `locked=en` (en 세션) | 4 | 500 | **0** | — | 0 |
| `locked=en` (auto ytn1) | 1 | 266 | 25 | **전부 참양성** | 2 run |
| auto sbs1 | 1 | 249 | 0 | — | 0 |

**15세션을 통틀어 `locked=ko` 참양성 0건, `locked=en` 오탐 0건** — 오탐과 참양성이 방향으로 완전히 갈린다.

- **해석은 가설로만 남긴다**: 극소 버퍼에서 사후분포가 영어 사전확률로 끌린다면 `locked=ko`에서만
  `p_opp`가 튀는 것이 설명되지만, 사전확률을 직접 측정하지는 않았다.
- **설계 함의(미구현)**: 방향 비대칭 문턱(`locked=ko`일 때만 τ↑ 또는 최소버퍼↑)이 자연스러운 레버다.
  단 게이트 파라미터를 실측에 맞춰 사후 조정하는 것은 §4-0이 정지 사유로 든 행위 그 자체이므로
  **이번 세션에서 구현하지 않았다.** 채택 여부는 사용자 판단.
- **주의**: `locked=ko` 방향의 **참양성 판별력은 여전히 미측정**(그 방향 실패 사례가 0건)이라,
  “`locked=ko` 발동은 전부 오탐”인지 “단지 그 방향 실패가 이 데이터셋에 없었을 뿐”인지 구분되지 않는다.
  비대칭 문턱을 도입하면 진짜 실패를 놓칠 수 있다.

### 4-0-3. 안 B 완료 — Stage 1 섀도우 계측 결과 (Exp-197)

> 정본 = `docs/research/SOT_LANG_PROBE_STAGE0.md` §11. 아래는 판단에 필요한 요지만.

**§4-0-1이 예고한 순서(① 표본확대 → ② 섀도우 로깅)의 ②를 완료했다.** 게이트 G1~G7 + 증거 리셋 훅을
`align_att_base.py`에 구현(`would_fire`만 로깅, `_apply_detected_language` 미호출 — 섀도우 불변식은
diff 검토로 신규 호출 0건 확인), auto 4파일(bong1/ytn2/sbs1/ytn1)을 `--lan auto --repeat 1`로
재측정했다.

**측정 중 로깅 버그 발견·수정**: 첫 스크리닝 run(`6af9b3d`)에서 `[Stage1ShadowStats]` 세션요약의
중복억제 가드가 `would_fire`만 비교해, `would_fire=0`으로 고정된(4파일 중 3개) 세션에서 `blocked_by`
누적치가 첫 `is_last` 시점(프로브 2회째) 이후로 전혀 갱신되지 않는 버그가 있었다.
`_log_lang_drift_stats()`의 기존 관례(총 호출수로 중복억제)에 맞춰 `d6bd66a`에서 수정, 회귀 테스트
1건 추가. `would_fire` 자체(개별 로그)는 영향 없었다 — **아래는 수정 후 v2 재측정**.

| | bong1 | ytn2 | sbs1 | ytn1(held-out) |
|---|---|---|---|---|
| WER | 28.9% | 13.3% | 11.9% | 22.1% |
| would_fire | **0** | **0** | **0** | **15** |
| 총 게이트호출수 | 467 | 346 | 246 | 262 |
| 최다 차단 게이트 | G4(424) | G4(330) | G4(238) | G4(227) |

WER/F1은 samelang 머지(Exp-196) 이후 auto 베이스라인 자체가 이동해 Exp-195 수치와 **직접 비교
대상이 아니다** — sanity(catastrophic 붕괴 없음)만 확인, 붕괴 없음.

**ytn1의 15건 = 독립 15건이 아니라 연속 1개 에피소드**(같은 성장버퍼에서 K=5→19, t=8.07~12.74s,
전부 `lang=en`). 이 시간창은 `ytn1_C_R1.txt` 전사 도입부(`"Yeah, I'm sorry... I'm happy to be
here... I want to."`)와 정확히 겹치고, 그 뒤 문장 #5가 `⟨language_switch⟩`로 확정되며 한국어로
전환된다 — §4-0/§10-4가 이미 규명한 **동일한 ytn1 언어잠금 실패**(한국어 개회사가 영어로 잠겨
전사됨)이며, 이번 run의 LMR_ko(19.7%/9.2%p)가 Exp-195가 원래 보고한 같은 파일 LMR_ko 19.7%와 거의
정확히 일치해 **독립 교차확증**된다. **참양성 확정, 오탐 아님.**

bong1/ytn2/sbs1 3파일은 이번 run에서 `would_fire=0` — 오탐 신호 없음(단 이 run은 오탐률을 다시 재는
목적이 아니었다 — 그 작업은 §4-0-1이 이미 12세션 규모로 닫았다. 이번 run의 목적은 런타임 게이트가
설계대로 동작하는지 확인하는 것이었고, 결과는 설계대로였다).

**지금 남은 결정**: 섀도우 게이트를 실제 트리거(`_apply_detected_language` 배선)에 연결해 졸업시킬지
여부다. 이는 CLAUDE.md의 "핵심 불변 제약 직결 기능은 정량 결과만으로 자율 채택/기각하지 않고
사용자에게 묻는다" 규칙과 goal 문서(`tranquil-floating-starfish.md`) Step 6가 명시한 "master 머지는
사용자 확인 후, 실제 적용은 별도 단계" 순서에 따라 **사용자 판단 대기**다. 브랜치
(`exp/lang-lock-stage0`)는 master 미머지 상태로 유지.

### Stage 1을 하게 될 경우 설계 요지 (이미 검토됨)

- **트리거 지점**: `infer()` 첫 forward 직후(`align_att_base.py:449-460` 근처). 여기가 **encoder_feature를 이미 손에 쥔 유일한 지점**이고 비용 0이다.
- **게이트(전부 AND)**: `cfg.language=="auto"` / `detected_language is not None` / **`segments_len() >= 2.0s`**(가장 중요 — refresh 직후 좁은 버퍼에서 Exp-189 고신뢰 오탐 재현 방지) / `p_opp >= τ`(0.97 근처, 스윕) / **연속 K배치 AND T초 지속**(K=3, T=1.0s — 10Hz라 K만으론 0.3s에 불과) / 쿨다운 3.0s(`last_lang_switch_time` 재사용) / 다른 트리거 arm 중 진입 금지(`pending_language_switch`·`eager_lang_detect`) / refresh·new_speaker·긴침묵 시 증거 리셋
- **적용**: `_apply_detected_language(new_lang)` 단일 호출. `refresh_segment` **절대 호출 금지**. 같은 언어 재확정이면 no-op(Exp-169: `init_context()`가 자기강화 재환각 루프를 만든다)
- **기각 조건**: 어떤 회차든 WER > 60% / ytn2에 정당화 안 되는 발동 / kor1 발동(Exp-189 재현) / `--lan ko,en`에서 발동(가드 위반) / Case B 신규 발생 / 화자F1 worst 회귀

---

## 5. 재현 명령

**모두 워크트리 cwd에서 실행** (editable 설치 함정 — 메인에서 돌리면 다른 코드를 잰다).

```bash
cd worktrees/bong1-eval-diagnostics

# 테스트 · lint
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\ruff.exe check whisperlivekit/metrics.py scripts/eval.py scripts/analyze_sot_lang_probe.py

# LMR 소급 계산 (재측정 0회)
.venv\Scripts\python.exe scripts/backfill_lang_mismatch.py \
  .omc/benchmarks/eval_bong1x10_20260721_172727.json --ref-file test_data/bong1.txt

# Stage 0 프로브 분석
.venv\Scripts\python.exe scripts/analyze_sot_lang_probe.py \
  --log .omc/server_logs/server_bong1_C_R1_20260721_212212.log --tau 0.97

# 경로 C 측정 (auto)
.venv\Scripts\python.exe scripts/eval.py \
  --model-dir whisperlivekit/model/whisper-large-v3-turbo \
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 \
  --lan auto --repeat 1 \
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo \
  --compression-ratio-threshold 3.0 --trace-tokens \
  --output .omc/benchmarks/eval_<name>.json
# ko 세션은 --files test_data/kor1.wav --lan ko 로 run 분리 (--lan은 실행당 전역 1값)
```

### 이번 측정에서 남은 산출물

| | |
|---|---|
| bong1 R1 | `.omc/transcripts/bong1_C_R1.txt`, `.omc/server_logs/server_bong1_C_R1_20260721_212212.log` (12MB, 프로브 479) |
| ytn2 R1 | `.omc/transcripts/ytn2_C_R1.txt`, `.omc/server_logs/server_ytn2_C_R1_20260721_212532.log` (2.3MB, 프로브 244) |
| sbs1·kor1 | **미실행** (사용자 지시로 중단). eval이 JSON 쓰기 전에 종료돼 `eval_stage0_*.json` 없음 — 전사 txt와 서버 로그만 존재 |

bong1 R1 = WER 38.4% / 화자F1 64.5% / 문장F1 13.3% / LMR_ko 20.9%(6.3%p) — 10회 베이스라인 밴드 내(**무회귀 확인**).
ytn2 R1 = WER 26.6% / 화자F1 72.7% / LMR_ko 12.5%(5.4%p) — 최근 밴드(15.8~20.7%) 상단. 초과분 상당수가 위 `Thank you very much` 환각 구간.

---

## 6. 함정 (실제로 겪은 것들)

1. **`uv` 금지.** 워크트리들이 메인 `.venv`를 Junction 공유한다. `uv run`·`uv pip`·`uv add/remove/lock/venv`·extras 없는 `uv sync`가 진행 중인 병렬 측정을 전멸시킨다. 파이썬은 `.venv\Scripts\python.exe`, lint는 `.venv\Scripts\ruff.exe` **직접 호출**.
2. **정답 판본 불일치.** 워크트리 `test_data/bong1.txt` ≠ 메인 판본(`분량이 조금 많은데` vs `조금 더 많은데`). 벤치 JSON은 **워크트리 판본**과 일치한다. `backfill_lang_mismatch.py`가 assert로 막는다.
3. **오디오·모델은 gitignore.** 새 워크트리엔 `test_data/*.wav`, `model.safetensors`, `sortformer-4spk-v2.nemo`가 없다 — 하드링크 필요. 이번에 `kor1~3.wav`를 그렇게 채웠다.
4. **포트 8901 공유.** `eval.py`의 `SERVER_PORT`가 8901인데 배포 UI 세션도 8901을 쓴다. 측정 전 점유 프로세스를 확인할 것.
5. **VBCable 겹침.** 다른 세션이 브라우저로 CABLE Output을 캡처 중이면 양쪽 측정이 오염된다. 측정 전 확인 필수.
6. **`[vbcable_test] 녹음 중지(일시중단)`은 정상 단계다.** 재생 완료 후 서버 처리 대기 구간이라 브라우저가 멈춘 것처럼 보이지만 무음이 아니다. 무음이면 WER이 100% 근처로 튄다.
7. **N≤3 표본으로 "해소됐다"고 판정하지 말 것.** 실행 분산 stdev 6.1%p가 5/10 빈도 현상을 가린다 — 실제로 이 프로젝트에서 한 번 오판했다.

---

## 7. 미해결 / 미확인

- ~~**단일언어 세션(kor1~3, eng1) 오탐률 전혀 모름**~~ → **해소(Exp-195, §4-0)**. 답: ko 세션에서
  τ=0.97 발동 5건(순수 오탐 2건 확정), eng1 0건. 전부 K=1·seglen<2.0s라 게이트 통과 0.
  **`--repeat 3` 확증까지 완료(§4-0-1)** — ko 12세션 누계 0.61%(23/3756), 게이트 통과 0/23.
  **en 방향은 여전히 N=1**(eng1 1세션·발동 0)이라 그쪽만 표본이 얕다.
- 관측된 실패가 **전부 `locked=en` + 한국어 오디오** — 반대 방향(`locked=ko` + 영어) 판별력 미확인.
  **Exp-195에서도 미해소**: ytn1 실패 역시 `locked=en` 방향이라 6파일 통틀어 `locked=ko` 실패 0건.
- **위음성률 미정량** — bong1 LMR_ko 20.9%가 이벤트 A·B로 전부 설명되는지 미확인.
- **개입 효과 전혀 미측정** — 검출 가능성만 보였다. 버퍼가 낡았으면 재감지도 틀릴 수 있다.
- 이벤트 B의 선제성이 정확히 0.00s 경계 — 첫 오방출 자체는 못 막는다.
- 필러 환각(`Thank you very much`)이 언어잠금과 **같은 뿌리인지** — ytn2 1건뿐인 가설. 사실이면 삽입 축(WER 6.6%p)도 함께 잡히는 셈이라 payoff가 커진다.
- sbs1·ytn1·kinno 미측정.
- **`state.sot_index`가 context 길이를 반영하지 않는 잠재 버그** — `--max-context-tokens > 0`이나 `--static-init-prompt` 사용 시 `_check_no_speech`가 `<|startofprev|>` 위치를 읽는다. 운영 기본값에선 잠복이라 이번엔 고치지 않았다(행동 변경 금지). 별도 백로그.
- **`fix/samelang-no-refresh`(`47fd76c`,`4448288`, master 미머지)가 Exp-155와 사실상 같은 가설**인데 실험 기록이 없다. Exp-155 기각 사유(bong1 new_speaker 15/15가 동일언어 → 100% 스킵 → 진짜 다른 화자 블렌딩, 화자F1 −4.1 / ytn2 −14.5) 재발 여부 미검증. 머지 전 확인 권고.
- ~~**Exp 번호 미부여**~~ → **해소**: Stage 0 본편 + 표본 확대를 **Exp-195**로 통합 기록
  (`EXPERIMENTS_LOG.md` / `EXPERIMENTS.md` 빠른참조).

---

## 8. 참조

- `docs/research/SOT_LANG_PROBE_STAGE0.md` — Stage 0 분석 전문(신호별 표·선제성·오탐 전수)
- `docs/research/TRANSLIT_LANGID_PROBE.md` (커밋 `d9e3101`) — 선행 NO-GO. §6이 남긴 "매 배치 연속 프로브" 미해결 꼬리를 이번에 닫았다
- `docs/TRANSCRIPTION_REQUIREMENTS.md` §2~§5 — LMR 정의·게이트 위치·구현
- `EXPERIMENTS_LOG.md:2920` — "①′ locked-lang 음차 환각: 저신뢰+언어확률 경합 보조 트리거 별도 설계" 후속과제 원문
