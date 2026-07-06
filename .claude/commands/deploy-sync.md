---
description: master 변경사항을 배포 반입 산출물(deploy/, wlk_in/)에 동기화한다
---

배포 PC로 가져갈 반입 산출물을 현재 master 기준으로 최신화해줘. 매번 절차를 처음부터 재구성하지 말고,
아래 순서 + memorize 기록을 따른다. (배경: 이 스킬은 절차 뼈대만 맡는다 — "지난번에 뭘 했는지"는
memorize가, "빌드 중 뭔가 터졌을 때"는 systematic-debugging 스킬이 담당한다.)

1. **직전 동기화 지점 확인 (memorize)**
   - `memorize search "deploy-sync"`로 가장 최근 deploy-sync 기록을 찾아 그때 동기화된 master 커밋 해시를 확인한다.
     기록이 없으면(최초 실행) 사용자에게 기준 커밋을 묻는다.
   - 그 기록에 남은 트랩·미해결 이슈도 함께 확인한다 — 이번에도 재발했는지 먼저 점검한다.

2. **변경 범위 파악**
   - `git log <직전 커밋>..master --oneline`, `git diff <직전 커밋>..master --stat`으로 무엇이 바뀌었는지 확인한다.
   - 변경이 없으면 "이미 최신"으로 보고하고 종료한다.

3. **변경 범위별 대응 결정**

   | 바뀐 것 | 필요한 조치 |
   |---|---|
   | `pyproject.toml` / `uv.lock` | wheelhouse 전체 재구성 필요(`docs/DEPLOYMENT_OFFLINE.md` §2.2) — 무거운 작업이니 진행 전 사용자 확인 |
   | `whisperlivekit/**` (패키지 코드) | 프로젝트 wheel만 재빌드(§2.2 step 5) + 내용 검증 |
   | `scripts/**` | wheel 재빌드 불필요 — **wheel엔 안 들어가고 배포 PC에서 소스 그대로 직접 실행**되므로 파일만 복사 |
   | `whisperlivekit/model/**` | `.gitignore` 비추적이라 git diff로 안 잡힘 — 새 모델 파일 추가 여부를 사용자에게 별도 확인 |
   | `docs/**`만 | 배포 산출물 변경 없음, 스킵 |

4. **wheel 재빌드가 필요한 경우 — 공유 `.venv` 절대 접촉 금지**
   - `uv build` / `uv sync` / `uv venv` / `uv run`을 공유(Junction) `.venv`에 실행하지 않는다(CLAUDE.md uv
     가드레일 — 위반 시 IDE 언어서버 잠금과 겹쳐 `.venv`가 반쪽 손상되는 실사고가 있었다, §8 트랩 표 참조).
   - 방법: (a) 전용 워크트리 + 독립 `.venv`(§2.2 공식 레시피 — 의존성 자체가 바뀌었을 때) 또는
     (b) 별도 시스템 Python으로 `python -m build --wheel`(의존성 변경 없이 패키지 코드만 바뀌었을 때, 더 가볍다).
   - 무거운 작업(전체 wheelhouse 재구성 등)이면 서브에이전트에 위임해 메인 세션 컨텍스트를 아낀다 —
     워크트리 절대경로를 프롬프트에 명시(CLAUDE.md 워크트리 규약).
   - 패키징 버그 등 **코드 자체를 고쳐야 하는 문제가 발견되면 여기서 직접 고치지 않는다** — 별도
     브랜치+워크트리로 분리하고, 병합은 사용자 승인 후 진행한다(main 브랜치 편집 규약).

5. **빌드 산출물 검증**
   - `zipfile`로 wheel 내부에 예상 서브패키지(`whisperlivekit.filtering` · `whisperlivekit.llm_translation` 등)가
     빠짐없이 포함됐는지 확인한다 — 과거 `pyproject.toml` packages 목록 누락으로 이 문제가 실제 발생한 적 있다(§8 트랩).
   - 이번에 바뀐 설정값(`parse_args.py` 기본값 등)이 wheel 안 소스에 실제로 반영됐는지 확인한다.

6. **동기화 반영**
   - 새 wheel을 `deploy/` · `wlk_in/deploy/`에 복사한다.
   - `git archive master --output=deploy\deploy_source.zip`을 재생성하고 `wlk_in`에도 동일 반영한다.
   - `scripts/closed_test.py` · `scripts/eval.py` 등 **wheel에 안 들어가고 배포 PC에서 소스로 직접 실행되는
     파일**은 `wlk_in`에 파일 자체를 복사한다(복사 후 `diff -q`로 동기화 확인).
   - 임시 워크트리를 만들었으면 정리한다 — `git worktree remove`가 실패하면 `.venv` junction 여부를
     `Get-ChildItem -Attributes ReparsePoint`로 먼저 확인하고, 있으면 `[System.IO.Directory]::Delete(path, $false)`로
     junction만 제거(대상 디렉터리를 따라 들어가지 않음)한 뒤 재시도한다 — 그 직후 공유 `.venv`가
     멀쩡한지 반드시 재확인한다.

7. **오류 발생 시**
   - 추측성 재시도나 임시방편으로 넘어가지 않는다. `systematic-debugging` 스킬 절차(Phase 1 근본원인
     조사부터)로 전환한다.
   - 원인이 규명되면, 다음 단계로 넘어가기 전에 `memorize project decision add`로 기록해 다음 번에
     바로 참조되게 한다.

8. **기록 + 보고**
   - 성공하면 아래처럼 memorize에 기록한다:
     ```
     memorize project decision add --title "deploy-sync: master <커밋 7자리> (<날짜>)" \
       --decision "<동기화 범위, wheel 버전, 새로 발견된 트랩/이슈, 다음 동기화 시 참고할 것>"
     ```
   - 새 트랩을 발견했다면 `docs/DEPLOYMENT_OFFLINE.md` §8 표에도 추가한다(memorize는 세션 간 연속성용,
     §8 표는 배포 PC에서 사람이 직접 펼쳐보는 문서 — 역할이 달라 둘 다 필요하다).
   - master에 코드가 새로 병합됐다면 `docs/MASTER_CHANGES.md` 갱신이 필요한지 확인한다
     (필요하면 `/update-master-changes` 별도 실행을 제안).
   - 배포 PC에서 실행할 명령(wheel 강제 재설치 등)을 정리해 사용자에게 제시하고, 수정할 부분이
     있는지 확인을 구한다.

**주의**:
- 배포 PC 파일 vs site-packages(wheel) 구분을 항상 먼저 확인한다 — `scripts/`는 소스트리 실행이라
  파일 자체 복사가 필요하고, `whisperlivekit/`는 wheel 재설치로만 반영된다(이 둘을 혼동해 실제로
  헷갈렸던 이력이 있다).
- `uv run` / `uv sync` / `uv venv` / `uv pip` / `uv add` / `uv remove` / `uv lock`을 공유 `.venv`에
  실행하는 모든 행위는 금지한다.
- 이 스킬은 배포 산출물 동기화까지가 범위다 — STT 성능 회귀 검증(`/eval`)이나 실험 기록
  (`/log-experiment`)은 별개 스킬 소관이다.
