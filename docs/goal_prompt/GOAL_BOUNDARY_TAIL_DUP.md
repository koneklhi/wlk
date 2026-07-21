# Goal Prompt — 언어전환 경계 단어 유실(꼬리/서두) + 경계 중복 확정 공동 수정 루프

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: 배포 PC 실사용 제보 2증상을 **한 루프에서** 수정한다 —
> **증상 1**: 코드스위칭 시 직전 발화 마지막 단어들이 유실
> (`"안녕하세요 반갑습니다" + "nice to meet you"` → `"안녕하세요" + "nice to meet you"`).
> **증상 2**: 코드스위칭 시 새 발화 첫 단어가 중복 확정
> (`"안녕하세요" / "nice" / "nice to meet you"`).
> 둘을 묶는 이유: **유실 수정(재디코딩 창 확대)과 중복은 서로 트레이드오프**다 — 창을 넓히면 재방출
> 중복이 늘고(Exp-166 keep 스윕: 4.5s에서 방송환각), 중복 필터만 넣으면 유실을 못 고친다. 같은 측정
> 셋에서 동시 판정해야 한쪽 개선이 다른 쪽 회귀로 상쇄되는 것을 잡는다.
>
> ⚠️ **진행 규율 — 완전 자율 (사용자 장시간 부재 가정)**:
> - 모든 중간 판단(방향 조합·임계값·재측정·스크리닝 기각)은 자율 결정하고 근거를 기록.
> - **유일한 사용자 질문 = 마지막 채택(머지) 여부.** master 머지는 절대 하지 않는다 — 브랜치 커밋까지만.
> - CLAUDE.md §3.8(범용 개선만, 데이터 특화 하드코딩 금지)·§3.3(Case B hard-fail)·§3.2(개선 대상
>   언어모드 = **auto** 선언, ko/en 무회귀 확인) 우선.

---

## 0. 출발 지점 (2026-07-19 작성 — 반드시 먼저 확인)

- **master 상태 재확인**: 작성 시점 master = `8a9a8bd`(코드 최신분 = `03de591`). **주의 — 병렬 루프
  Exp-190**(SILENCE_HARD Case B 수정, 워크트리 `silence-hard-caseb-fix`, 채택권고 상태)이
  `tokens_alignment.py` `_gate_decide` 부근을 수정했고 머지 여부는 사용자 결정 대기다. 이 루프도
  `tokens_alignment.py`를 만지므로 **Exp-190의 머지 결론이 난 뒤 최신 master에서 분기**하는 것이
  원칙(사용자에게 시작 시점 확인). 부득이 먼저 시작하면 이후 rebase 충돌을 감수하고 명시 기록.
- **Exp 번호**: [EXPERIMENTS.md](../../EXPERIMENTS.md) 빠른참조 최신 번호 확인 후 +1(Exp-190은 사용됨).
- **배포 실사용 제보 원문 (2026-07-19, 배포 PC = master `03de591` 적용 확인 상태에서 발생)**: 상단 인용부.
- **dev 재현 확인 (2026-07-19 스크리닝, master `80e3127`+ 경로 C `--lan auto --repeat 1`)**:
  - `.omc/transcripts/ytn2_C_R1.txt` — **증상 1**: 정답 `"In support of these ends, we remain..."` →
    전사 `"ends, we remain..."`부터(전환 직후 서두 유실). 정답 `"이런 목표들을 달성하기 위해서 우리는"`
    → 전사 `"위해서 우리는"`부터. **증상 2**: `"미니스터."` 단독 확정(⟨language_switch⟩) 직후
    `"Minister Jiang and I reviewed..."` 재시작 — 제보 "nice"/"nice to meet you"와 동일 패턴.
    라인 내 중복 `"논의한 사안 중에서는 우 사안 중에서는 우선"`·`"상당한 상당한"` 다수.
  - `.omc/benchmarks/eval_allauto_20260719_1408.json` 원본. 단 이 run은 `--trace-tokens` 없이 돌아
    경계 로그가 없다 — **판단 근거는 이 세션에서 새로 뜨는 `--trace-tokens` 측정**으로 삼는다.
- **기존 규명 (재조사 불필요 — 원문은 `EXPERIMENTS_LOG.md` grep + backlog 문서)**:
  - **유실 계열 ⓐ — [Retract] 철회 후 재디코딩 미복구**: Exp-172 증상① 확정(bong1 "You don't
    understand" 4단어, 복구 확률 2건 중 1건 실패). Exp-174가 `retract_floor` 하한을 정정했으나
    확률적 미복구 잔존. 철회 코드 = [tokens_alignment.py](../../whisperlivekit/tokens_alignment.py)
    `_retract_stale_language_tokens`(`:176`, 호출 `:166`, `RETRACT_EPS` `:52`).
  - **유실 계열 ⓑ — 미방출형(non-fire) 서두 유실**: [docs/backlog/BACKLOG_CODESWITCH_FOLLOWUP.md](../backlog/BACKLOG_CODESWITCH_FOLLOWUP.md)
    §1(최우선 지정). 구언어 잠금 중 반대 언어 음향에서 AlignAtt 방출 정지 → 늦은 트리거의 재디코딩
    창(keep_secs)이 미방출 구간을 못 덮음. 실측: ytn2 "There is more work" 유실, sbs1 diar 도착 시
    버퍼 0.48s(keep 1.53s 요청에도). keep 계산 =
    [backend.py](../../whisperlivekit/simul_whisper/backend.py) `new_speaker` `:445-447`
    (`_NEW_SPEAKER_KEEP_MARGIN`/`_NEW_SPEAKER_MAX_KEEP`).
  - **증상 1의 "구언어 꼬리" 하위유형 주의**: 배포 제보(`"반갑습니다"` 유실)는 **경계 이전 구언어
    오디오**가 대상 — 현행 프로토콜은 전환 시 경계 기준 절단 후 **신언어로만** 재디코딩하므로, 창을
    아무리 넓혀도 구언어 꼬리는 신언어 재디코딩으로 복구되지 않을 수 있다(음차·유실). 이 하위유형이
    실측되면 "전환 적용 직전 구언어로 [마지막 방출 토큰 끝, 경계] 구간 1회 마감(flush) 디코드" 같은
    별도 설계가 필요하다(§4-ⓑ). **매 사례를 로그로 계열 구분**(ⓐ철회/ⓑ미방출/구언어꼬리)할 것 —
    겉보기 패턴이 같아도 원인이 다르다(Exp-188/189의 계열 구분 규율 준용).
  - **중복 계열 — 재디코딩 창 겹침 이중 방출**: backlog §5. CrossBatchFilter는 "완전 동일 인접
    단어"만 제거([filtering/__init__.py](../../whisperlivekit/filtering/__init__.py)) — 구/문장 단위
    중복은 통과. Exp-173: QG 억제 96건 중 46건이 dup(= QG가 우연히 걸러주는 게 상당수, 통과분이
    최종 전사에 남음 — 즉 dup 억제를 QG에 의존하는 건 설계가 아니라 요행).
- **스코프 격리 (이 루프에서 다루지 않는 것)**:
  - QG streak refresh 버퍼 폐기(Type B 삼킴) → [GOAL_BOUNDARY_QG_PRESERVE.md](GOAL_BOUNDARY_QG_PRESERVE.md).
  - held/UTF-8 방출 손상(연속 발화 단어 유실) → [GOAL_UTF8_HELD_EMIT_LOSS.md](GOAL_UTF8_HELD_EMIT_LOSS.md).
  - locked-lang 음차 환각(backlog §2)·필러 storm(Type A, backlog §4) → 별도 설계 세션.
  - Case B 단어 중간 분절 → Exp-190(완료, 채택권고)이 다룸 — 재작업 금지, 재발 시 계열 구분 보고만.
- **공용 워크트리·venv 규약(반드시 준수)**: `.venv` Junction 공유(`mklink /J .venv ..\..\.venv`),
  `uv run`/`uv sync`/`uv pip`/`uv add`/`uv lock` **절대 금지**([[shared-venv-uv-run-concurrency-hazard]]),
  lint `.venv\Scripts\ruff.exe`·테스트 `.venv\Scripts\python.exe -m pytest` 직접 호출, **측정은
  cwd=워크트리**([[worktree-eval-import-resolution]] — import 경로 검증 후 진행). main 워크트리 코드 편집 금지.
- **측정 정본**: 경로 C만, provenance(`branch=…@… vbcable=ok`) 육안 확인. 스크리닝=`--repeat 1`,
  채택확정=`--repeat 3`(fail-fast 금지, median+min/max/stdev). diar-ON(Sortformer, CRT=3.0), turbo.
  **⚠️ 다른 세션과 경로 C 동시 측정 금지**(VBCable 단일 물리 장치 + 고정 포트 — 병렬 측정 상호 전멸).

---

## 1. 목표

언어전환 경계에서 ① 단어 보존율을 올리고(꼬리·서두 유실 감소) ② 경계 중복 확정을 줄인다 —
**두 표적 지표를 같은 측정에서 동시 판정**하며, 한쪽 개선이 다른 쪽을 회귀시키면 채택 불가.
Case B 신규 발생 0건(hard-fail)·화자분리 F1 worst-case 미회귀는 전제 게이트.

## 2. 준비

- master 최신(§0 — 가급적 Exp-190 결론 이후)에서 분기 → 브랜치 `exp/boundary-tail-dup`,
  워크트리 `worktrees/boundary-tail-dup`, `.venv` Junction 공유.
- 먼저 읽을 것: [docs/SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md)(경계 처리
  ·철회 서술), `EXPERIMENTS_LOG.md`에서 Exp-171/172/174 블록(철회 메커니즘·유실 실측),
  backlog §1·§5(수정 방향 초안), Exp-166 블록(keep 스윕 — 창 확대의 실패 전례).

## 3. 재현 + 정밀 진단

### 3-1. 재현 측정

- ytn2(경계 최다·§3.8 최우선) + bong1, `--lan auto --diarization --sortformer-model
  whisperlivekit/model/sortformer-4spk-v2.nemo --compression-ratio-threshold 3.0 --trace-tokens
  --repeat 3`(경계 이벤트가 회차마다 다르므로 3회 이상). cwd=워크트리, provenance 확인.

### 3-2. 경계 전수 분류 + 자동 카운터

1. 모든 언어전환 경계(ytn2 정답 기준 9곳 내외)에 대해 회차별로: **유실**(정답 대비 경계 전후 누락
   단어 수, 계열: ⓐ철회 미복구 / ⓑ미방출 / 구언어꼬리 / 기타) · **중복**(경계 후 n-gram 재방출) ·
   정상 여부를 로그(`[Retract]`/`[NewSpeaker]`/`[LangSwitch]`/keep_secs/방출 시각)로 귀속한다.
2. **자동 카운터 스크립트 신설** `scripts/analyze_boundary_tail_dup.py`(오프라인 전용): 전사 내
   인접 n-gram(2~4) 중복 자동 검출 + 정답 대조 경계 누락 단어 수 산출 — 이 두 수치가 이 루프의
   **표적 지표**다(WER보다 민감·직접적). 이후 스크리닝/확정 측정마다 함께 산출한다.
3. 계열별 빈도 분포로 §4 방향 조합의 우선순위를 정한다(예: 미방출형이 지배적이면 ⓐ 창 하한 수정
   우선, 구언어꼬리가 실재하면 ⓑ flush 설계 착수, 철회 미복구가 지배적이면 복구 보장 우선).

## 4. 수정 방향 (자율 판단 — §3-2 분포 근거로 조합 선택, 최소 변경)

**유실 쪽**:
- **ⓐ 재디코딩 창 하한 = 마지막 방출 토큰 끝 시각**(backlog §1-ⓐ): `refresh_segment(keep_secs=...)`
  계산부([backend.py](../../whisperlivekit/simul_whisper/backend.py) `:445-447`)가 diar 경계·고정
  keep 대신 미방출 구간 전체를 덮도록. `_NEW_SPEAKER_MAX_KEEP`(5.0s) 상한 유지 필수.
- **ⓑ 구언어 마감(flush) 디코드**(신규 설계 — 배포 제보 "반갑습니다" 직접 대응): 전환 적용 직전
  [마지막 방출 토큰 끝, 경계] 구간을 **구언어 토크나이저로 1회 최종 디코드**해 꼬리를 방출한 뒤
  절단·전환. 비용 = 전환당 추가 디코드 1회(RTX 3080에서 실시간 lag 확인 필수). 철회(Exp-171)와의
  순서·중복 상호작용 유닛으로 고정.
- **ⓒ 비-fire 경량 워치독**(backlog §1-ⓑ): "오디오 전진 vs 방출 정지" 1~2s급 감지로 언어 재감지
  선제 트리거 — ⓐ/ⓑ로 부족할 때만(정상 침묵 오탐 리스크).

**중복 쪽**:
- **ⓓ 커밋 전 겹침 dedup**: 커밋(확정 라인 추가) 직전, 직전 확정 꼬리와의 n-gram(2~4) 겹침 검사로
  재방출 중복을 제거 — Exp-171 철회 구역 규칙의 "재디코딩 일반"으로의 확장(backlog §5 제안).
  위치 = [tokens_alignment.py](../../whisperlivekit/tokens_alignment.py) 커밋 경로. **시간창 제한**
  (재디코딩 창 겹침 구간에서만 발동)으로 정상 반복 발화("네, 네"·강조 반복) 보호. 기존
  Exp-002/028/057 필터와 중복 설계 금지 — 그 필터들이 못 잡는 "겹침 재방출"만 표적.

공통: 새 상수 남발 금지, 롤백 플래그 1개(모듈 상수)로 짝지음 A/B 가능하게. ⓐ+ⓓ가 기본 조합 후보
(ⓐ가 중복을 늘리는 만큼 ⓓ가 상쇄하는 구조 — 그래서 한 루프다).

## 5. TDD (필수)

- 신규 `tests/test_boundary_tail_dup.py`:
  - ⓓ dedup 유닛: 겹침 재방출 제거 / 정상 반복("네, 네") 보존 / 시간창 밖 미적용 / 한·영 혼합 경계.
  - ⓐ/ⓑ 유닛: 미방출 구간 커버 창 계산, flush 디코드 경로(도입 시)의 철회 상호작용·중복 비방출.
  - 회귀 유지: `tests/test_boundary_retract.py`(Exp-171/174)·`tests/test_silence_grammar_gate.py`
    (Exp-176/188/190) 전부 통과 — 특히 **진짜 경계의 정상 분할·철회 동작을 훼손하지 않음**을 고정.
- `.venv\Scripts\python.exe -m pytest tests/ -q` 전체 통과, `.venv\Scripts\ruff.exe check .` clean.

## 6. 측정 계획

1. **스크리닝(`--repeat 1`)**: auto 세트(bong1/ytn2/sbs1) — WER + **표적 지표(경계 유실 단어 수·
   중복 n-gram 수, §3-2 스크립트)**. ko 세트(kor1~3, `--lan ko`)로 무회귀 확인(특히 ⓓ dedup이 낭독
   반복 표현을 오삭제하지 않는지 — 진행 중 Exp-190과 같은 파일군이므로 결과 비교 시 코드 세대 주의).
2. 유망하면 **채택확정(`--repeat 3`, fail-fast 금지)**: auto 세트 + held-out 단회(**ytn1 `--lan auto`
   — 코드스위칭 경계 다수라 이 루프에서 특히 중요**, eng1 `--lan en`). 판정 = 화자분리 F1 worst-case
   미회귀 → WER max 미회귀 → WER median → 문장분리 F1. **Case B 0건 hard 게이트.**
3. **정성 필수**: 경계별 before/after 전사 대조 표(ytn2 전 경계) — 유실 복구·중복 소멸을 사례로
   입증. 부작용 감시: 재방출 중복 증가(ⓐ 단독 시), 방송클로징 환각 재발(Exp-166 전례), 실시간 lag
   (ⓑ 도입 시), 정상 반복 오삭제(ⓓ).

## 7. 산출물

- `/log-experiment`로 Exp-N 기록(언어모드 auto 명시, ko 무회귀 부기).
- [docs/SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md) 갱신(경계 철회/재디코딩
  서술 변경 시 — 연동 문서 규약).
- 브랜치 `exp/boundary-tail-dup` 커밋까지만. **master 머지 금지** — 사용자 승인 대기.

## 8. 완료 보고 (사용자에게 제시)

1. 한 줄 결론: 채택 권고 / 기각 권고 / 판단 유보.
2. §3-2 계열 분류표(유실 ⓐ/ⓑ/구언어꼬리/기타 빈도) + 채택한 방향 조합과 근거.
3. 정량 표(WER + 표적 지표 before/after, N=3 + held-out) + 게이트 판정.
4. 정성: 배포 제보 2증상 대응 사례 인용(경계 꼬리 보존·"미니스터."류 중복 소멸 여부).
5. 미해결·후속(예: 구언어꼬리 flush 미도입 시 잔존 규모, 음차 환각 연계).
6. **사용자 질문**: `exp/boundary-tail-dup`를 master에 머지할지.

## 9. 회귀 교훈 (반드시 준수)

- **Exp-166**: keep 창 4.5s 확대가 방송클로징 환각을 유발한 전례 — 창 확대는 반드시 중복/환각
  감시와 짝으로. `MAX_KEEP` 5.0s 상한 유지.
- **Exp-163**: 디코더가 재생성하는 환각은 출력 필터로 못 막는다 — ⓓ dedup은 "정당 재방출 겹침"
  전용이며 환각 반복 대응은 스코프 밖(기존 필터 유지).
- **Exp-171/174**: 철회 상태(`retract_from/floor`)와 새 창 계산·flush의 상호작용을 유닛으로 고정 —
  철회가 정당 꼬리를 지우는 회귀 재발 금지.
- 단일화자 파일 화자분리 F1 0%/100%는 지표 아티팩트(Exp-186) — 판정 근거로 쓰지 않는다.
- auto 표적 수정이 ko/en 모드를 회귀시키지 않는지 확인(§3.2 언어모드 축) — 특히 ⓓ는 모드 무관
  커밋 경로라 ko 세트 무회귀 확인 필수.
- 공유 `.venv` 가드레일·경로 C 동시 측정 금지(§0) 준수.
