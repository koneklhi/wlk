# 전사 성능 요구사항 + 2‑지표(화자분리·문장분리) 측정 방법론

이 문서는 **실시간 STT 전사가 달성해야 할 요구사항을 우선순위 순으로 명세**하고, 그것을 정량·정성으로
측정하는 방법론과 metric 구현 계획을 담는다. **성능 개선·결과 분석 세션은 이 문서 §1을 최적화 대상으로 읽는다.**

> 배경: 과거 테스트 결과가 좋지 않았던 원인 중 하나가 "전사 요구사항이 명확히 명시되지 않음"이었다.
> 이 문서는 그 요구사항을 단일 SoT로 고정해, 개선 방향이 요구사항 달성에 정렬되도록 한다.
> 상위 설계 제약은 [../CLAUDE.md](../CLAUDE.md) §3(핵심 설계 제약)·§4(운영 규칙)를 따른다.

---

## 1. 전사 성능 요구사항 (우선순위 순 — SoT)

개선 초점·채택 판정 **모두** 아래 순서를 따른다. 상위 요구사항이 하위보다 우선한다.

### 1순위 [최우선] — 화자 전환 = 반드시 문장(줄) 분리 · 측정: **화자분리 F1**

- 정답 스크립트에서 `[spkN]` 화자 라벨이 **바뀌는 지점**에서는, STT 전사가 **반드시** 그 지점에서
  문장/줄을 **분리·확정**해야 한다. (한 줄에 두 화자의 발화가 섞이면 실패.)
- **화자분리 F1** = 정답의 화자전환 경계가 전사 줄분리로 **실현된 정도**(경계 위치 정렬 F1).
- **수단 불문**: 화자분할(Sortformer 등)·언어 감지·침묵(VAD)·구두점 등 **무엇으로든** 이 경계에서 분리가
  일어나면 된다. → 목표는 특정 diarization 기법의 정확도가 **아니라**, **화자전환 지점에서의 분리 실현**이다.
  개선 아이디어를 낼 때 "어떤 신호를 쓰든 화자전환 경계에서 줄이 갈라지게 하라"가 기준.

### 2순위 — 전사 정확도 · 측정: **WER**

- 단어 누락(deletion)·환각(insertion)·치환(substitution) 최소화.
- **대규모 누락/환각 절대 금지** (문장·구절 단위 유실, 반복 환각 폭주 등).
- worst‑case(max WER) 미회귀를 median 개선보다 우선 (상용화 worst‑case 우선, CLAUDE.md §3.8).

### 3순위 [nice‑to‑have] — 동일 화자 문장 분리 · 측정: **문장분리 F1**

- 같은 화자가 여러 문장을 이어 말할 때, **온점(문장 종결)마다** 줄을 분리하면 좋다.
- **Case A 허용**: 동일 화자의 인접 두 문장이 분리되지 않고 **붙여서 전사돼도 무방**하다.
  - 예(bong1 spk3): `So my son who is holding up the rock over there has a little bit more screen
    time than I do in the film. So he's been going around saying that he's the main character,
    main protagonist.` — 이 둘이 한 줄로 붙어 나와도 OK(문장분리 F1 recall 손실일 뿐, **기각 근거 아님**).

### 절대 금지 (모든 우선순위 위의 hard floor)

- **Case B — 단어 중간 over‑split 금지**: 한 단어/문장이 **단어 중간에서 쪼개져** 확정 전사되면 안 된다.
  - 예: `…한반도 동쪽이 위를 향하게 뒤집어 놓은 지도를 올렸` ⟶(줄바꿈)⟶ `습니다.`
    ("올렸습니다"가 "올렸"+"습니다"로 분절) — WER이 괜찮아 보여도 **critical 실패**. 발견 시 **flag하고
    원인을 수정**한다(관련: [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) §3.5, Exp‑173 계열).
  - 원칙: **under‑split(미분리)은 허용, 단어 중간 over‑split은 금지.**
- **한/영 두 언어 고정**(CLAUDE.md §3.2): 한국어·영어 외 언어(일본어·중국어 등) 환각 금지.
  code‑switching(한 발화 내 한·영 혼용)에서 단어 유실·환각·문장 조기 확정 방지.
- **폐쇄망 오프라인**(CLAUDE.md §3.1): 런타임 네트워크 호출 금지.

> **우선순위 개정 이력**: 이 순서(화자분리 F1 > WER > 문장분리 F1)는 프로젝트 기존 도그마
> "WER > F1"([../CLAUDE.md](../CLAUDE.md) §3.3·§4의 옛 표현)를 **개정**한다. 화자분리 F1이 WER보다 위다.

---

## 2. 정답 스크립트 형식 (신형식 canonical)

성능 개선의 정답 스크립트는 **`test_data/<name>_speak,sentence_sperate.txt`** (신형식)을 canonical로 쓴다.
구 `test_data/<name>.txt`(라벨 없는 빈 줄 형식)는 **deprecated** — metric 코드가 신형식 파서로 전환되면 정답
용도 폐기(그 전까지 과도기 병존).

신형식 구조(예 `sbs1_speak,sentence_sperate.txt`):

```
[spk1]
<문장1>

<문장2>

[spk2]
<문장1>
```

- `[spkN]` = 화자 턴 헤더(자기 줄 단독). 화자는 사람 단위(같은 화자는 한·영 code‑switch 가능; bong1은 4화자
  `spk1`~`spk4`). 화자가 바뀌면 새 `[spkN]` 헤더.
- 헤더 아래, 빈 줄로 구분된 각 줄 = 그 화자의 **한 문장**(온점 기준 분리).
- **두 경계 종류**를 동시에 라벨링한다:
  - `[spkN]` **전환** = **화자전환 경계**(1순위 요구, 깨끗·명확).
  - 화자 블록 **내부 줄바꿈** = **문장(온점) 경계**(3순위, 사람이 수기 라벨 → judgment 노이즈 있음 → 후순위 정당화).
- **WER 정답 텍스트** = 신형식에서 `[spkN]` 헤더 줄을 제거하고 문장을 이어붙인 것(라벨은 단어로 세지 않는다).

파일 목록·역할은 [TESTING.md](TESTING.md) `test_data 디렉토리 구조` 참조.

---

## 3. 측정 방법론 — 2지표 분리

신형식이 두 경계를 라벨링하므로, **화자분리 F1과 문장분리 F1을 따로 산출·기록**한다.

| 지표 | 정답 경계 | 가설(hyp) 경계 | 의미 | 우선순위 |
|---|---|---|---|---|
| **화자분리 F1** | `[spkN]` 전환 위치 | STT 확정 줄분리 위치 | 화자전환에서 줄이 갈라지는가 | **1순위** |
| **문장분리 F1** | 화자 블록 내 줄바꿈(온점) 위치 | STT 확정 줄분리 위치 | 동일 화자 문장을 분리하는가 | 3순위 |
| WER | (신형식 라벨 제거 텍스트) | STT 전사 텍스트 | 전사 정확도 | 2순위 |

- 두 F1 모두 **경계 위치 정렬 F1**(단어 정렬 후 경계 위치 매칭)이라, 기존 `whisperlivekit/metrics.py`의
  `compute_segmentation`(경계 정렬 F1) 로직을 **정답 경계 집합만 바꿔** 두 번 호출하면 된다.
- 화자분리 F1은 **경계 실현 여부**만 보므로 경로 C hyp가 화자 id를 잃어도(§5 참조) 계산 가능하다.
  "어느 화자인지"(귀속) 정확도까지 보려면 §5의 화자 id 배선이 필요(선택 확장).

### kinno — 정성 sanity held‑out (정량 게이팅 제외)

- `kinno`(2화자, 순차통역)는 **정답 텍스트의 단어·철자가 부정확할 수 있다**. 따라서 kinno에서는
  **WER/F1 수치를 채택 게이트로 쓰지 않는다.**
- 용도: **전반적 화자분리·문장분리가 대충 되는지 + 대규모 누락/환각이 없는지**만 정성 확인.

---

## 4. 결과 분석·채택 기준

채택 게이트 순서(worst‑case 우선, CLAUDE.md §4와 정합):

1. **화자분리 F1 worst‑case 미회귀** (최우선). 화자전환 경계 분리가 무너지면 median이 좋아도 기각.
2. **WER max 미회귀** → **WER median 개선**.
3. **문장분리 F1** — 변동은 후순위. 하락만으로 기각하지 않는다(Case A 허용). 단 **Case B(단어중간 분리)가
   보이면** F1 수치와 무관하게 원인 수정.

정성 분석(전사 txt 정독) 시 반드시 확인:

- **화자전환 경계**마다 줄이 갈라졌는가(1순위). 안 갈라진 지점 = 최우선 개선 대상.
- **Case B** 발생 여부(단어 중간 분절) — 발견 시 hard‑fail로 flag.
- **대규모 누락/환각·한영 외 언어 환각** 여부.
- 동일 화자 문장 분리(Case A는 허용 — 감점 아님).
- kinno는 위 항목의 **거친 sanity**만(수치 신뢰 금지).

정량·정성 통합 판정표는 [.claude/commands/eval.md](../.claude/commands/eval.md) `정성 평가 절차` 참조.

---

## 5. metric 구현 계획 (다음 세션 — 코드 과제)

현재 신형식 파일 6종은 **orphaned**(어떤 코드도 로드 안 함). eval은 `audio_path.with_suffix(".txt")`로 구
파일만 읽는다. 구현 순서:

1. **[1순위] 신형식 canonical 파서**: `scripts/eval.py`가 `<name>_speak,sentence_sperate.txt`를 정답으로
   읽도록 전환. `parse_reference_sentences`(현 `scripts/eval.py`, 빈 줄 분할)를 대체/확장해 `[spkN]` 헤더를
   해석하고 **(a) 화자전환 경계 집합** + **(b) 문장 경계 집합** + **(c) 라벨 제거 WER 텍스트**를 산출.
   신형식 부재 시 구 파일로 폴백(과도기).
2. **2지표 산출**: `whisperlivekit/metrics.py`에 `compute_segmentation`을 화자경계·문장경계 각각으로 호출하는
   경로 추가. `FileResult` 데이터클래스(현 `scripts/eval.py`)에 `speaker_f1/precision/recall` +
   `sentence_f1/…` 필드 추가, `_build_result`에서 채움.
3. **집계·출력**: `_aggregate_runs`(repeat 집계)·`print_summary`(stdout)·`output_data`(JSON)에 두 F1을
   `seg_f1`과 병렬로 확장. `--repeat` median/min/max/stdev도 두 F1 각각.
4. **[선택] 경로 C 화자 id 배선**: 귀속 정확도까지 보려면 `whisperlivekit/web/live_transcription.js`의
   `.textcontent` div에 `data-speaker`를 부여하고 `scripts/vbcable_test.py` DOM scrape가 이를 수집하게 한다
   (현재 화자 id는 `.speaker-badge` span에만 있어 scrape에서 유실). 화자분리 F1(경계 실현)만 볼 거면 불필요.
5. **kinno 정성‑only 처리**: kinno는 수치 산출은 하되 채택 게이트에서 제외(리포트에 "sanity only" 표기).

> 라인 번호는 드리프트할 수 있으니 **함수/식별자 이름**으로 찾는다(위 이름은 현재 코드 기준).
> 코드 변경 시 [../CLAUDE.md](../CLAUDE.md) "코드 변경 시 연동 갱신 문서" 표대로 관련 문서를 lockstep 갱신.

---

## 6. 실험 기록 regime 구분

지표 세분화(2‑F1) + 정답 신형식 전환으로 **측정 regime v2** 경계가 생겼다.

- **구 regime**: 단일 문장분리 F1(빈 줄=화자전환 경계, 구 정답). 이 F1은 신 화자분리 F1과 **직접 비교 불가**.
- **신 regime v2**: 화자분리 F1 + 문장분리 F1 분리, 정답 신형식. 신 Exp는 **두 F1을 따로** 기록.
- [../EXPERIMENTS.md](../EXPERIMENTS.md)(STATE)에 regime v2 경계를 표기하고, 신 Exp 기록 시 두 F1을 남긴다.
  2‑F1 신 베이스라인은 §5 metric 코드 착지 후 재측정한다.
