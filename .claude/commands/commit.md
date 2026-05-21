# Commit

staged 변경사항을 분석해 Conventional Commits 형식의 한국어 커밋 메시지를 생성하고 커밋한다.

<allowed-tools>
Bash(git status*)
Bash(git diff*)
Bash(git add*)
Bash(git log*)
Bash(git commit*)
</allowed-tools>

## 실행 순서

1. `git status`와 `git diff --cached`로 staged 상태 확인
2. staged 파일이 없으면 → unstaged 변경사항 전체를 보여주고 스테이징 여부를 사용자에게 확인
3. staged diff 전체 분석 → 변경 성격 파악
4. 관련 없는 변경사항이 섞여 있으면 분리 커밋 제안
5. Conventional Commit 메시지 초안 작성 후 사용자에게 제시
6. 확인 후 `git commit -m "..."` 실행

## 커밋 메시지 형식

```
<타입>: <한 줄 요약, 명령형, 72자 미만>

[선택적 본문 — 변경 이유나 중요 맥락이 있을 때만]
```

**타입 목록:**
- `feat`: 새로운 기능
- `fix`: 버그 수정
- `docs`: 문서만 변경
- `refactor`: 동작 변경 없는 코드 구조 변경
- `test`: 테스트 추가/수정
- `chore`: 빌드, 설정, 의존성 변경
- `style`: 포맷, 들여쓰기 등 코드 의미 변경 없음
- `perf`: 성능 개선

## 규칙

- 커밋 메시지는 **한국어** (CLAUDE.md §4)
- subject는 명령형, 72자 미만
- Co-Authored-By 서명 추가 안 함
- `git add -A` 또는 `git add .` 사용 금지 — 파일명을 명시적으로 지정
