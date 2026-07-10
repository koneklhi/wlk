# 전사 결과 4개 이슈 원인 분석 (ytn2 코드스위칭·한국어 저하·온점·문장분리)

## Context

다른 세션에서 진행 중인 성능 개선(단계1, E3) 테스트 전사에서 관찰된 4개 현상의 원인 분석 요청.
분석 대상 코드 = master@E3 (단계1 머지 완료, 커밋 6db5ea1). 근거는 코드 직접 확인 + EXPERIMENTS_LOG(Exp-139~150) + exam.md(단계1 보고서, switch=True 0회 dormant 발견).

**이 작업의 산출물은 원인 분석 보고이며, 코드 수정은 포함하지 않는다** (수정 후보는 각 절 말미에 제안만).

---

## Q1. 한국어 전사가 이전 버전보다 나빠 보이는 원인

코드스위칭/언어고정 기능을 넣으면서 **한국어에 구조적으로 불리한 억제 장치 4개**가 쌓였다. 각각은 환각 억제 목적으로 채택됐지만, 부작용이 전부 "정상 한국어를 통째로 버리는" 방향이다.

### 1-1. logprob quality gate = 드롭 방식 (가장 유력)
- `align_att_base.py:543-564` `_quality_gate()` — avg_logprob < **-2.0**(Exp-142 기본값)이면 `return []` 로 **배치 전체 폐기**.
- Whisper는 한국어 avg_logprob가 영어보다 체계적으로 낮음 → 동일 품질이어도 한국어가 게이트에 더 자주 걸림. **실측 증거**: Exp-140(-1.0)에서 sbs1 한국어 앵커 정상 발화가 잘려 +11.3pp catastrophic, Exp-141 기록에 "EN-after-KR 세그먼트의 낮은 logprob" 명시 — 코드스위칭 경계·한국어 구간이 저logprob 영역.
- **구 whisperlive와의 결정적 차이**: 구 코드(faster-whisper 계열)의 `log_prob_threshold=-1.0`은 **temperature fallback(재시도) 트리거**였지 출력 폐기가 아님. 신 코드는 재시도 없이 그냥 버림 → 단어 유실로 직결.

### 1-2. CJK 세그먼트 통드롭 필터 (Exp-139)
- `filtering/__init__.py:97-139` — 한자·가나가 **한 글자라도** 있으면 세그먼트 **통째 드롭**. 한글(U+AC00~)은 안전하지만, 정상 한국어 문장 안에 환각 한자 1개가 섞이면 그 문장 전체가 사라짐.
- **실측 증거**: Exp-139 채택 시 bong1(한국어 화자 2명 포함) median **+8.8pp 회귀** — 이후 Exp-142로 일부 상쇄됐을 뿐 메커니즘은 그대로.

### 1-3. 한국어 특화 반복 필터 (베이스라인 필터의 편향)
- `backend.py:188-204` BatchRepeatFilter — **한글 단어만** 대상으로 배치 내 4회 반복 시 **배치 전체 드롭 + context 리셋**. "네 네 네 네" 같은 정상 맞장구도 걸림. 영어에는 없는 필터.
- `backend.py:226` char-run 필터 — 문자 단위 연속 반복 감지라 한글 음절 반복("하하하하"=4자)이 영어("llll" 필요)보다 낮은 문턱에서 걸림.

### 1-4. 오언어 lock 구간의 형태 변화 (E2 이후)
- `lang_restrict_koen`은 **감지 단계만** {ko,en} 제한(`simul_whisper.py:213-228`) — 디코딩엔 관여 안 함. 비음성(웃음 등) 구간에서 오감지가 나면 CJK 환각 대신 **한글/라틴 쓰레기**로 형태만 바뀜(Exp-139 정성 분석 확인). 이 쓰레기 한글은 CJK 필터에 안 걸리고 WER의 한국어 쪽 오류로 계상 → "한국어가 더 나빠 보이는" 체감 요인.

### 검증 방법 (원인별 기여도 분리)
서버 로그에서 `[QualityGate]` / `[BatchRepeatFilter]` / `[HallucinationFilter]` / CJK 드롭 발생 횟수를 회차별로 집계하고, 드롭된 텍스트를 정답과 대조해 "정상 한국어였는데 버려진" 비율을 측정. (필터별 억제 카운터는 이미 로그에 있으므로 grep만으로 가능.)

### 수정 후보 (분석 후 별도 실험으로)
① quality gate를 드롭 대신 재디코딩(temperature fallback)으로, 또는 언어별 임계 분리(ko는 -2.5 등) ② CJK 필터를 통드롭 → 해당 스팬만 strip ③ BatchRepeatFilter에 최소 길이·간격 조건 추가.

---

## Q2. 온점이 문장 맨 앞에 나오는 원인

Whisper 토크나이저가 문장 끝 온점을 **다음 디코드 배치에 별도 토큰으로** 내보내는 경우가 있는데, 이 "지각 도착한 온점"이 앞 문장에 못 붙고 다음 줄 머리에 남는다. 두 단계 결함의 조합:

1. **선두 온점 필터의 의도적 보존 + 리셋 구멍** — `backend.py:208-215`: 직전 방출 단어가 이미 구두점으로 끝났을 때만 선두 온점을 제거(중복 제거 목적)하고, 아니면 "직전 단어의 문장끝 온점"으로 보고 **보존**한다. 그런데:
   - 보존된 온점은 토큰 스트림상 **다음 배치의 첫 토큰**이라, 그 사이에 줄 경계(침묵·화자전환·finalize)가 끼면 앞 문장이 이미 닫혀버려 온점이 새 줄 머리로 밀림.
   - `new_speaker()`가 `_last_emitted_word=None` 리셋(`backend.py:158`) → 화자전환 직후엔 중복 온점도 필터가 못 잡음.
2. **조립 시 재부착 로직 부재** — diar-ON 병합(`tokens_alignment.py:221-227`)은 `segments[-1].text += segment.text` 단순 연결이라, 선두 온점을 앞 세그먼트 끝으로 옮기는 처리가 없음.

실제 전사 증거: `bong1_C_R1.txt`에 `It's him. .This man.` / `. What was the.` 패턴 다수.

**수정 후보**: 줄 조립 단계에서 "새 줄 첫 토큰이 문장종결 구두점이면 직전 finalized 줄 끝으로 이전(없으면 드롭)" 규칙 추가 — timed_objects/tokens_alignment 한 곳 처리로 전 경로 해결.

---

## Q3. ytn2 en→ko 전환에서 문장 구분이 안 된 원인

**두 겹의 원인** — 마커가 생성되지 않았고, 생성됐어도 diar-ON 경로가 소비하지 않는다.

1. **LanguageSwitch 마커가 diar-ON에서 아예 생성 안 됨 (dormant)** — exam.md 계측으로 확정: switch=True 0회.
   - 경로: 화자전환 시 `new_speaker()`(`backend.py:150`)가 `detected_language=None` 리셋 → 다음 감지에서 `_apply_detected_language()`(`align_att_base.py:165-190`)의 `is_switch = prev_lang is not None and …` 가 **항상 False**("최초 감지") → `pending_language_switch` 마커 arm 자체가 안 됨.
   - 화자전환 이벤트가 없는 en→ko 전환(예시처럼 통역 음성이 한 화자로 붙는 경우)은 짧은침묵 재감지(≥0.5s pause 필요)나 PLC(기본값 None=꺼짐)만이 전환을 잡을 수 있는데, 예시 구간에선 발동 조건이 안 맞아 미발동.
2. **생성돼도 diar-ON 병합이 경계를 지움** — `compute_punctuations_segments()`(`tokens_alignment.py:119-126`)는 마커에서 세그먼트를 나누지만, `get_lines_diarization()`의 병합 루프(`tokens_alignment.py:221-227`)가 **화자만 보고** 같은 화자면 무조건 `+=` 재병합 → 언어 경계 정보 소실. (diar-OFF 경로 `tokens_alignment.py:274-281`는 `is_boundary()`를 정상 처리 — diar-ON만 결함.)
3. **예시에서 27초가 한 줄인 부가 요인**: ytn2는 원어(영어) 위에 통역(한국어)이 겹치는 오디오라 Sortformer가 화자전환을 안 냈을 가능성 — 화자 경계도, 언어 경계도 없으니 한 줄로 누적.

**수정 후보**: ① `new_speaker()`에서 prev_lang을 별도 보관해 다음 감지 시 is_switch 판정 복원 ② `get_lines_diarization()` 병합 루프에 boundary 세그먼트 경계 보존(PuncSegment에 boundary 플래그 전파) — 단계1 마커 설계를 diar-ON에서 실제로 작동시키는 배선 작업.

---

## Q4. 코드스위칭 구간 단어 누락 — 기존에 보완 기법이 있었나?

**결론: 구 whisperlive에는 코드스위칭 보완 기법 자체가 없었고**(세그먼트당 언어 감지 1회, 중간 전환 미지원 — `whisperlive_code/transcriber.py:1766-1856`), **신 시스템에는 보완 장치가 새로 만들어졌지만 diar-ON에서 핵심 경로가 잠들어 있다(dormant).**

### 신 시스템의 단어 누락 메커니즘 (활성 상태별)

| 메커니즘 | 위치 | 상태 |
|---|---|---|
| ① 감지 게이트 지연: 전환 감지까지 1.5~2.0s 동안 경계 오디오가 **구 언어 SOT로 디코딩** → 쓰레기 → quality gate가 폐기 | `align_att_base.py:191-217` + `543-564` | **활성 — 주범 후보** |
| ② AlignAtt 단조 attention: 구 언어로 이미 attend한 프레임은 전환 후 재디코딩 안 됨 (되감기 없음) | `align_att_base.py` infer 루프 | **활성** |
| ③ `new_speaker()`의 미확정 음역 폐기: `refresh_segment(complete=False)` + `buffer=[]` — 화자전환 직전 미확정 단어 유실 | `backend.py:147-149` | **활성** |
| ④ logprob 게이트가 EN↔KR 경계 세그먼트(저logprob)를 선별적으로 드롭 | Exp-140/141 실측 | **활성** |
| ⑤ 단계1 보완: 전환 시 2.5s만 남기고 트림 → 경계 오디오 재디코딩 (`_trim_segments_to_recent`) | `align_att_base.py:144-163` | **dormant** — diar-ON에서 switch=True 0회 (Q3-1과 동일 원인) |

즉 "보완 기법이 있는데 제 기능을 못 하는" 상황이 정확하다: 단계1이 만든 경계 재디코딩(⑤)은 is_switch=False 문제(Q3-1) 때문에 diar-ON에서 한 번도 발동하지 않았고, 그 사이 ①~④가 경계 단어를 깎는다. 구 버전은 애초에 중간 전환을 안 했기 때문에 "전환 경계 누락"이란 실패 모드 자체가 드물었다(대신 언어 고착으로 통째 오전사).

**해결 방향(우선순위)**: (a) Q3 수정으로 switch 경로 활성화 → ⑤가 ②를 상쇄하는지 계측 (b) quality gate 드롭 → 재디코딩 전환으로 ①·④ 완화 (c) `new_speaker()` 미확정 음역을 폐기 대신 재디코딩 대상에 포함.

---

## 후속 작업 제안 (사용자 결정 사항)

이 분석은 보고가 산출물이며, 이어서 진행한다면:
1. **계측 먼저**: 서버 로그의 `[QualityGate]`/`[BatchRepeatFilter]`/CJK 드롭 카운트를 테스트 3종 회차별 집계 → Q1 원인별 기여도 정량화 (코드 변경 없음, 로그 grep)
2. **단계2 후보**: Q3 수정(new_speaker prev_lang 보존 + diar-ON boundary 소비) — 단계1 dormant 문제의 직접 후속이며 exam.md의 "진행 방향 결정" 질문과 합류
3. Q2 온점 재부착은 저위험 독립 수정으로 별도 브랜치 가능

## 검증 방법

- Q1: 로그 카운터 집계 스크립트로 드롭된 텍스트 vs 정답 대조 (읽기 전용)
- Q2/Q3: 수정 채택 시 경로 C 스크리닝(--repeat 1) → F1(경계) 변화 + 전사 정성 확인, 채택 확정은 --repeat 3 (CLAUDE.md §4 규율)
