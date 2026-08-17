# 백로그 — 영어 문장분할 오탐 (`en_next_capitalized`)

> 상태: **미착수**(분석 완료·실측 근거 있음). 2026-08-17 ytn1 유령 stub 조사(Exp-209 예정) 중
> **별개 결함**으로 분리 발견. 사용자 판단으로 유령 stub 수정과 분리해 별도 과제화했다 —
> 계층이 다르고(재조정 계층 vs 문장경계 계층), 한 번에 머지하면 측정에서 효과 귀속이 불가능하기 때문.

## 1. 증상

정상 전사된 단어가 **문장 중간에서 잘려 독립 줄**이 된다. 화면상 유령 stub과 구별되지 않지만
텍스트 자체는 정확하다 — 즉 **드롭 대상이 아니라 병합 대상**이다.

ytn1 실측(경로 C, `--lan auto`, 화자분할 ON, N=20):

```
9.  The United States remains fully committed to the defense of the Republic of.  ⟨silence⟩
10. Korea.                                                                        ⟨language_switch⟩
11. 미국은 대한민국 방위에 여전히 확고한 의지를 갖고 있습니다.                          ⟨punctuation⟩
```

정답은 `The United States remains fully committed to the defense of the Republic of korea.`
한 문장이다. `Korea`는 **정확한 전사**인데 줄만 잘못 쪼개졌다.

## 2. 근본 원인

[whisperlivekit/sentence_boundary.py](../../whisperlivekit/sentence_boundary.py)
`should_split_after_silence()`의 영어 경로가 **"다음 어절이 대문자인가"만** 보고 분할을 결정한다.

```python
nxt = next_text.strip()
verdict = nxt[0].isupper()      # ← 닫히는 어절이 문장을 끝낼 수 있는지 보지 않는다
```

실측 로그:

```
[SentenceBoundary] should_split_after_silence rule=en_next_capitalized verdict=True
                   word='of' next_text=' Korea'
[SilenceGate] start=48.73 end=49.15 d_eff=0.42 last_word='of' next_word='Korea'
              speakers=(2, 2) langs=('en', 'en') decision=split path=split_grammar
```

`of`는 전치사라 문장을 끝낼 수 없는데, 뒤에 **고유명사**가 와서 대문자라는 이유만으로 분할됐다.
한국어 경로는 종결어미(`is_sentence_final_ko`)로 **닫히는 쪽**을 검사하는 반면, 영어 경로는
**여는 쪽**만 본다 — 비대칭이 결함의 본질이다.

## 3. 실측 빈도

ytn1 20회에서 플래그된 경계 stub 37건을 정답 대비 위치 인식으로 분류한 결과:

| 판정 | 건수 | 비중 |
|---|---|---|
| DUP(중복 유령) | 12 | 32% |
| HALLUC(교차언어 환각) | 17 | 46% |
| **LEGIT(정상 단어·오분할)** | **8** | **22%** |

LEGIT 8건 중 **6건이 `of`\|`Korea` 단일 패턴**, 나머지는 `Meeting.`·`있습니다.` 각 1건.
즉 이 결함 하나가 경계 stub의 약 1/6을 만든다.

## 4. 개선 방향 (제안 — 미검증)

영어 경로에도 **닫히는 어절 검사**를 추가해 한국어 경로와 대칭을 맞춘다:

> 다음 어절이 대문자라도, **닫히는 어절이 문장을 끝낼 수 없는 기능어**(전치사·관사·접속사·
> 한정사·조동사 등)면 분할하지 않는다.

- 판정은 품사 사전이 아니라 **닫힌 소형 기능어 집합**으로 충분하다(실측 사례가 전부 전치사/한정사).
  특정 데이터 단어를 외우는 것이 아니라 영어 문법 일반 규칙이므로 §3.8 "데이터 특화 하드코딩 금지"에
  저촉되지 않는다.
- 롤백 플래그 필수(`EN_SPLIT_FUNCWORD_GUARD_ENABLED` 등).

## 5. 위험 / 측정 주의

- **영어 문장분할 전반에 영향**한다 — held-out **eng1** 회귀 감시가 필수다.
- 반대 방향 위험 = **과소분할**: 진짜 문장이 기능어로 끝나는 경우(예: 인용·생략)에는 분할이
  억제돼 문장분리 F1이 떨어질 수 있다. 단 §4상 **문장분리 F1 하락 단독은 기각 근거가 아니다**.
- 채택 게이트는 표준(§4): 화자분리 F1 worst-case 미회귀 → WER max 미회귀 → WER median.
- 유령 stub 수정(Exp-209)과 **같은 회차에 머지하지 않는다** — 분산이 큰 환경이라 두 변경을
  묶으면 효과 귀속이 불가능하다.

## 6. 참고

- 조사 원본: 2026-08-17 세션(ytn1 20회 `--trace-tokens` 계측), 유령 stub 3분류 발견.
- 관련 정본: [docs/SENTENCE_FINALIZATION_LOGIC.md](../SENTENCE_FINALIZATION_LOGIC.md)
- 유령 stub 계열(별개 결함): Exp-208(부분해) → Exp-209(병합 + DUP 드롭) 예정.
