# Claude ↔ antigravity(Gemini) 협업 규약

메인 개발은 **Claude Code**, 제3자 검토는 **antigravity CLI(`agy`)**가 맡는다. 두 도구가 같은 git 저장소를
읽으므로, 기존 "docs/ = 공유 SoT" 문화를 그대로 협업 채널로 쓴다 — **파일 매개 핸드오프**. 수동 복붙 없이
요청/회신을 git 파일로 주고받는다.

antigravity 쪽 역할·금지사항의 정본은 [../AGENTS.md](../AGENTS.md) §0이다. 핵심: **antigravity는 검토자이지
실행자가 아니다** (코드 편집·커밋·측정 금지, 산출물은 `docs/reviews/`의 마크다운뿐).

---

## 1. 디렉터리 / 파일 명명

- 핸드오프 파일은 모두 `docs/reviews/`에 쌓는다.
- **요청 파일** (Claude 작성): `docs/reviews/<YYYY-MM-DD>-<topic>-request.md`
- **회신 파일** (antigravity 작성): `docs/reviews/<YYYY-MM-DD>-<topic>-gemini.md`
- (선택) diff 덤프: `docs/reviews/<YYYY-MM-DD>-<topic>-diff.patch`

`<topic>`은 kebab-case 한 단어~두 단어 (예: `exp090-vad`, `phase4-baseline`).

## 2. 요청 파일 형식 (Claude → antigravity)

```markdown
# 검토 요청: <제목>

## 검토 대상
- (파일/diff/plan 경로, 또는 인라인 내용)

## 범위
- (어디까지 보고 어디는 보지 말 것)

## 질문 목록
1. ...
2. ...

## 판정 기준 (해당 시)
- (이 변경이 통과해야 할 조건. 측정 수치가 관련되면 §4 분산 규약을 상기)
```

## 3. 회신 파일 형식 (antigravity → Claude)

```markdown
# 검토 회신: <제목>

## 질문별 답변
1. ...
2. ...

## 발견 이슈
- [심각] ...
- [보통] ...
- [경미] ...

## 대안 제안
- ...

## 불확실/추가 정보 필요
- ...
```

심각도 태그: `[심각]` = 채택 시 회귀/위반 위험, `[보통]` = 개선 권고, `[경미]` = 사소·스타일.

## 4. Claude의 수용 절차

받은 회신은 **맹종하지 않는다.** `superpowers:receiving-code-review` 규율을 적용한다:

- 각 지적을 **근거와 함께 검증**한 뒤 채택/기각한다. 기술적으로 틀린 지적은 이유를 달아 기각한다.
- 채택한 지적은 실제 작업(plan 수정·코드 변경)에 반영한다.
- 갈리는 판단(아래 레시피 B의 교차 검증)에서 결론이 안 나면 **사람에게 올린다.**

---

## 5. 레시피 A — 방향성/계획 검토

실행 *전* 방향을 독립 점검할 때.

1. **Claude**: plan/실험 가설을 `docs/`에 쓰고, 요청 파일에 구체적 질문을 담는다.
   예: "이 방향이 §3.8 과적합(sbs1/ytn1 특화) 아닌가? 후처리 말고 더 단순한 백엔드(디코더 파라미터) 대안은?
   ytn2 일반화에 악영향 가능성은?"
2. **antigravity(`agy`)**: AGENTS.md 자동 로드 → `ROADMAP.md`·`PHASE2_EXPERIMENTS.md`·요청 파일을 읽고,
   필요 시 읽기 전용(`research`) 서브에이전트로 독립 비판 → 회신 파일 작성.
3. **Claude**: 회신을 읽고 plan에 반영하거나 근거 있는 기각.

## 6. 레시피 B — 코드/diff 리뷰

구현 *후* 머지 전 독립 리뷰.

1. **Claude**: `git diff <base>..<branch>`를 `docs/reviews/<...>-diff.patch`로 덤프(또는 브랜치명만 전달)
   하고 요청 파일 작성.
2. **antigravity**: 독립 리뷰 → 회신 파일.
3. **Claude**: 자신의 `/code-review` 결과와 **교차 검증**.
   - 두 리뷰가 **겹치는** 지적 → 신뢰도↑, 우선 처리.
   - **갈리는** 지적 → 사람이 판단.

---

## 7. 가드레일

- **측정 채택 결정은 antigravity 권한 밖.** 경로 C 분산(§4)은 미묘하다 — antigravity는 *가설 비판*과 *코드
  리뷰*만 한다. "이 수치가 채택 기준 통과인가"의 최종 판정은 **N≥3 median 규칙 + 사람**이 한다.
  antigravity는 회신에서 채택/기각을 단정하지 않고, "이런 점을 보라"는 관찰·질문으로 남긴다.
- **antigravity는 저장소에 코드·커밋을 만들지 않는다** (AGENTS.md §0 재확인). 코드 제안은 회신 파일 안의
  예시/패치 스니펫으로만 제시하고, 적용은 Claude가 한다.
