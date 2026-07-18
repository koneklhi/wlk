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
  - 이 항목은 **출력 언어 집합 제한**이며, 아래 세션 언어모드(입력 소스 지정)와는 별개 개념이다.
- **폐쇄망 오프라인**(CLAUDE.md §3.1): 런타임 네트워크 호출 금지.
- **세션 언어모드(auto/ko/en) 준수**(CLAUDE.md §3.2): 세션이 ko 또는 en으로 고정된 경우 해당 언어 전사에
  집중하되, code‑switching 재감지 로직만 비활성화될 뿐 전사 품질(WER·Case B 금지 등) 요구사항은 동일하게
  적용된다. auto 세션은 위 code‑switching 요구사항이 그대로 적용된다.

> **우선순위 개정 이력**: 이 순서(화자분리 F1 > WER > 문장분리 F1)는 프로젝트 기존 도그마
> "WER > F1"([../CLAUDE.md](../CLAUDE.md) §3.3·§4의 옛 표현)를 **개정**한다. 화자분리 F1이 WER보다 위다.

---

## 2. 정답 스크립트 형식 (canonical)

성능 개선의 정답 스크립트는 **`test_data/<name>.txt`**를 canonical로 쓴다(2026-07-18부로 단일 규약 —
과거 `_speak,sentence_sperate.txt` 접미사로 별도 관리되던 신형식 파일을 `<name>.txt`로 이전·통합했다).
`[spkN]` 헤더가 있으면 아래 신형식으로 파싱해 화자분리 F1+문장분리 F1을 산출하고, 헤더가 없으면(라벨
없는 빈 줄 형식) 구형식으로 폴백 파싱한다(문장분리 F1 미산출).

신형식 구조(예 `sbs1.txt`):

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

파일 목록·역할은 [TESTING.md](TESTING.md) `test_data 디렉토리 구조` 참조. 각 파일은 세션 언어모드(CLAUDE.md §3.2: auto/ko/en) 중 하나로 측정된다 — bong1·ytn2·sbs1·ytn1·kinno = auto(코드스위칭), eng1 = en, kor1~3 = ko. 정답 스크립트 형식 자체는 언어모드와 무관하게 동일하다.

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
- **언어모드 축**: 서버가 `--lan auto/ko/en` 중 무엇으로 기동됐는지에 따라 측정 대상 파일군이 갈린다(CLAUDE.md §3.8). 2지표 산출 로직 자체는 언어모드와 무관하게 동일 — `--lan`이 다른 파일을 같은 eval.py 실행에 섞지 않는다는 실행 절차상의 제약만 있다(CLAUDE.md §4, [TESTING.md](TESTING.md) 경로 C).

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

## 5. metric 구현 현황

Part 1~3(파서·2지표 산출·집계/출력)은 **구현 완료**되었다(`feat/eval-speaker-sentence-f1`, TDD로 작성,
`tests/test_eval_reference_parser.py`·`tests/test_metrics_segmentation.py`·`tests/test_eval_build_result.py`).
Part 4(경로 C 화자 id 배선)는 **선택 확장으로 아직 미구현**이다.

1. **[완료] 신형식 canonical 파서**: `scripts/eval.py`의 `parse_speaker_sentence_reference()`가
   `<name>.txt`를 읽어 `[spkN]` 헤더를 해석하고 **(a) 화자경계 집합** +
   **(b) 문장 경계 집합** + **(c) 라벨 제거 WER 텍스트**(`plain_text`)를 산출한다(`[spkN]` 헤더가 없으면
   `None`을 반환). `_build_result()`가 동일한 `<name>.txt`에 대해 신형식 파싱을 우선 시도하고, 파싱
   실패 시(`None`) 같은 파일을 구 `parse_reference_sentences()`로 폴백한다(2026-07-18부로 별도
   `_speak,sentence_sperate.txt` 접미사 파일명 규약은 폐지·`<name>.txt`로 통합).
2. **[완료] 2지표 산출**: `whisperlivekit/metrics.py`의 `compute_speaker_sentence_segmentation()`이
   `compute_segmentation()`과 동일한 Levenshtein 정렬·경계 매칭 로직(내부 공용 헬퍼로 추출:
   `_flatten_sentences`/`_flatten_blocks`/`_match_boundaries`/`_boundary_prf`)을 화자경계·문장경계 두
   집합에 각각 적용해 hyp 단어 정렬을 1회만 공유 계산한다. `FileResult`(현 `scripts/eval.py`)에는 계획과
   달리 새 `speaker_f1` 필드를 만들지 않고 **기존 `seg_f1/seg_precision/seg_recall` 필드를 화자분리 F1이
   그대로 이어받는 방식**으로 구현했다(§1 "화자분리 F1이 옛 단일 F1의 직접 후속"과 정합, JSON 하위호환
   목적) — `sentence_f1/sentence_precision/sentence_recall` + `ref_format`(`"new"`/`"old"`/`None`) 필드가
   신규 추가됐다. 모든 블록이 단일 문장이면(예 ytn2) 블록 내부 경계가 0개이므로 `sentence_f1`은 `None`
   (해당 없음)이지 `0.0`이 아니다.
3. **[완료] 집계·출력**: `_aggregate_runs`·`print_summary`·`output_data`(JSON)가 `seg_f1`(화자분리)과
   `sentence_f1`(문장분리)을 나란히 median/min/max/stdev까지 산출한다. `_save_transcript`가 저장하는
   전사 txt 헤더에도 두 F1 + `ref_format`(신형식/구형식)이 표기된다.
4. **[미구현·선택] 경로 C 화자 id 배선**: 귀속 정확도까지 보려면 `whisperlivekit/web/live_transcription.js`의
   `.textcontent` div에 `data-speaker`를 부여하고 `scripts/vbcable_test.py` DOM scrape가 이를 수집하게 한다
   (현재 화자 id는 `.speaker-badge` span에만 있어 scrape에서 유실). 화자분리 F1(경계 실현)만 볼 거면
   불필요 — Part 1~3이 다루는 것은 항상 "경계 위치"뿐이고, "이 줄이 몇 번 화자 발화인가"(귀속)는 여전히
   미측정이다.
5. **kinno 정성-only 처리**: 코드 과제가 아니라 리포팅 관례다 — kinno도 다른 파일과 동일하게 수치가
   산출되지만(코드에 kinno 특례 없음, CLAUDE.md §3.8 및 이 저장소 규약대로), 채택 게이트에서는 제외하고
   정성 확인 용도로만 쓴다. 이미 CLAUDE.md §3.8·§4와 `.claude/commands/eval.md` §정성 평가 절차에 반영돼 있다.

> **다음 실행 단계**: 코드는 착지했지만 **regime v2 베이스라인 경로 C 실측은 아직 하지 않았다**(이번
> 작업 범위는 코드+테스트, 라이브 서버/오디오 측정은 미포함). 다음 성능 개선 세션에서
> [EXPERIMENTS.md](../EXPERIMENTS.md)(STATE) 안내대로 신 베이스라인을 측정한다.
> 라인 번호는 드리프트할 수 있으니 **함수/식별자 이름**으로 찾는다(위 이름은 현재 코드 기준).
> 코드 변경 시 [../CLAUDE.md](../CLAUDE.md) "코드 변경 시 연동 갱신 문서" 표대로 관련 문서를 lockstep 갱신.

---

## 6. 실험 기록 regime 구분

지표 세분화(2‑F1) + 정답 신형식 전환으로 **측정 regime v2** 경계가 생겼다.

- **구 regime**: 단일 문장분리 F1(빈 줄=화자전환 경계, 구 정답). 이 F1은 신 화자분리 F1과 **직접 비교 불가**.
- **신 regime v2**: 화자분리 F1 + 문장분리 F1 분리, 정답 신형식. 신 Exp는 **두 F1을 따로** 기록.
- [../EXPERIMENTS.md](../EXPERIMENTS.md)(STATE)에 regime v2 경계를 표기하고, 신 Exp 기록 시 두 F1을 남긴다.
  2‑F1 신 베이스라인은 §5 metric 코드 착지 후 재측정한다.
