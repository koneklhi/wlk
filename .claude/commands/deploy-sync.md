---
description: master 변경사항을 배포 반입 산출물(deploy/, wlk_in/)에 동기화한다
---

배포 PC로 가져갈 반입 산출물을 현재 master 기준으로 최신화해줘. 매번 절차를 처음부터 재구성하지 말고,
아래 순서를 따른다. (배경: 이 스킬은 절차 뼈대만 맡는다 — "지난번에 뭘 했는지"는 `wlk_in\SYNC_STATE.txt`가
1차 소스로, memorize가 best-effort 보조로 담당하고, "빌드 중 뭔가 터졌을 때"는 systematic-debugging
스킬이 담당한다.)

1. **직전 동기화 지점 확인 (SYNC_STATE.txt 우선, memorize는 보조)**
   - `wlk_in\SYNC_STATE.txt`(반입 스테이징 디렉터리 — 저장소 기준 `../wlk_in`, 절대경로는 개인
     `CLAUDE.md` §"폐쇄망 반입(wlk_in) 규약" 참조) 상단 "현재 상태" 블록에서 `last_synced_commit`을
     읽는다. 이것이 1차 진실 소스다.
   - 파일이 없거나 읽을 수 없으면 `memorize search "deploy-sync"`로 폴백한다. 그래도 못 찾으면
     사용자에게 기준 커밋을 묻는다.
   - `SYNC_STATE.txt` 하단 이력 로그에서 직전 동기화 때 남은 트랩·미해결 이슈를 함께 확인한다 —
     이번에도 재발했는지 먼저 점검한다.

2. **변경 범위 파악**
   - `git log <직전 커밋>..master --oneline`, `git diff <직전 커밋>..master --stat`으로 무엇이 바뀌었는지 확인한다.
   - 변경이 없으면 "이미 최신"으로 보고하고 종료한다.

3. **변경 범위별 대응 결정 — 2축으로 분리해서 판단한다**

   "휠/wheelhouse를 재빌드해야 하는가"와 "`wlk_in`의 raw 소스 사본을 갱신해야 하는가"는 다른 질문이다.
   배포 PC는 `python -m whisperlivekit.basic_server`를 **cwd의 소스 폴더에서 직접** 실행하므로(cwd가
   항상 site-packages보다 import 우선순위가 높다 — §8 트랩 참조), 휠 재빌드 여부와 무관하게 아래 경로
   변경은 **항상** `wlk_in` 원본 사본 갱신 대상이다.

   | 바뀐 것 | 휠/wheelhouse 조치 | `wlk_in` 원본 미러 조치 |
   |---|---|---|
   | `pyproject.toml` / `uv.lock` | wheelhouse 전체 재구성 필요(`docs/DEPLOYMENT_OFFLINE.md` §2.2) — 무거운 작업이니 진행 전 사용자 확인 | 파일 자체도 복사(배포 PC 참고용) |
   | `whisperlivekit/**` (패키지 코드) | 프로젝트 wheel만 재빌드(§2.2 step 5) + 내용 검증 | **변경 파일 복사 필수** — cwd 섀도잉으로 실제 실행되는 게 이 사본이다 |
   | `scripts/**` | 불필요 — wheel엔 안 들어감 | 변경 파일 복사(배포 PC에서 소스 그대로 직접 실행) |
   | `docs/**` | 불필요 | 변경 파일 복사(배포 PC 운영자 참고용 — "배포 산출물 없음"과 "wlk_in 사본 갱신 불필요"는 다른 얘기다) |
   | `test_data/**`, 루트 메타파일(`README.md` 등) | 불필요 | 변경 파일 복사 |
   | `whisperlivekit/model/**` | 해당 없음 | `.gitignore` 비추적이라 git diff로 안 잡힘 — 새 모델 파일 추가 여부를 사용자에게 별도 확인 |
   | `.claude/`, `.memorize/`, `.omc/` | 불필요 | **범위 밖** — 배포 PC는 Claude Code를 쓰지 않는다. `wlk_in`에 이미 있는 구버전은 방치해도 무방(정리 불필요) |

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
   - 휠이 바뀌었으면 새 wheel을 `deploy/` · `wlk_in/deploy/`에 복사하고, `git archive
     master --output=deploy\deploy_source.zip`을 재생성해 `wlk_in`에도 동일 반영한다.
   - **`wlk_in` 원본 미러는 파일 단위로 갱신한다** — 전체 트리 재추출(`git archive` 통짜 압축 해제)이나
     `robocopy /MIR`는 쓰지 않는다. 두 방식 모두 "git 추적 파일 전체"를 기준으로 움직이는데, gitignore된
     모델 가중치(`model.safetensors`, `.nemo`, silero onnx/jit 등)가 그 기준에 없어 실수로 지워질 위험이
     있다. 대신:
     1. 2단계에서 이미 구한 `git diff <직전 커밋>..master --name-status`(대상 경로: `whisperlivekit`,
        `scripts`, `docs`, `test_data`, 루트 메타파일, `pyproject.toml`, `uv.lock` — `.claude`/`.memorize`/
        `.omc`는 제외)를 그대로 파일 목록으로 쓴다.
     2. `A`/`M` 상태 경로는 `git show master:<path>`를 `wlk_in\<path>`에 덮어쓴다.
     3. `D` 상태 경로는 `wlk_in\<path>`를 명시적으로 삭제한다(그 파일만 — 디렉터리 통째 삭제 금지).
     4. `R`(rename) 상태는 삭제(구 경로)+추가(신 경로)로 처리한다.
     5. 변경된 각 파일을 `diff -q`로 동기화 확인한다.
   - 임시 워크트리를 만들었으면 정리한다 — `git worktree remove`가 실패하면 `.venv` junction 여부를
     `Get-ChildItem -Attributes ReparsePoint`로 먼저 확인하고, 있으면 `[System.IO.Directory]::Delete(path, $false)`로
     junction만 제거(대상 디렉터리를 따라 들어가지 않음)한 뒤 재시도한다 — 그 직후 공유 `.venv`가
     멀쩡한지 반드시 재확인한다.
   - 최초 1회 전체 셋업(처음부터 `wlk_in`을 통째로 새로 까는 경우)은 이 파일 단위 절차 대신 기존
     `docs/DEPLOYMENT_OFFLINE.md` §1.1의 `git archive` 방식을 쓴다 — 상황이 다르다(최초/전체=archive,
     이후 증분=파일 단위).

7. **오류 발생 시**
   - 추측성 재시도나 임시방편으로 넘어가지 않는다. `systematic-debugging` 스킬 절차(Phase 1 근본원인
     조사부터)로 전환한다.
   - 원인이 규명되면, 다음 단계로 넘어가기 전에 `memorize project decision add`로 기록해 다음 번에
     바로 참조되게 한다.

8. **기록 + 보고**
   - **`wlk_in\SYNC_STATE.txt`를 갱신한다(1차 진실 소스, 필수)**: 상단 "현재 상태" 블록을 새 커밋
     해시·시각·범위로 교체하고, 하단 이력 로그에 새 항목을 append한다(덮어쓰지 않는다). 형식:
     ```
     last_synced_commit: <커밋 7자리>
     last_synced_at: <ISO 8601>
     last_scope: full|incremental
     wheel_version: <바뀌었으면 새 버전, 아니면 이전 값 유지>
     deploy_pc_confirmed_applied: unknown

     === HISTORY (append newest at bottom) ===
     --- <ISO 8601> ---
     commit: <커밋 7자리>
     scope: full|incremental
     wheel_rebuilt: yes|no
     files:
       <path> (A|M|D)
       ...
     notes: <트랩·이슈·특이사항>
     ```
     `deploy_pc_confirmed_applied`는 새 동기화 때마다 `unknown`으로 리셋한다 — "dev PC의 `wlk_in`이
     최신"과 "배포 PC가 실제로 반영했는지"는 별개이며 후자는 여기서 검증 불가하다(폐쇄망). 사용자가
     USB 반입·적용을 확인해줄 때만 `yes`로 갱신한다.
   - memorize에도 `memorize project decision add`로 best-effort 기록을 시도한다 — 실패해도 위
     SYNC_STATE.txt 갱신이 이미 끝났으므로 동기화 자체를 막지 않는다.
   - 새 트랩을 발견했다면 `docs/DEPLOYMENT_OFFLINE.md` §8 표에도 추가한다.
   - master에 코드가 새로 병합됐다면 `docs/MASTER_CHANGES.md` 갱신이 필요한지 확인한다
     (필요하면 `/update-master-changes` 별도 실행을 제안).
   - 아래 형식으로 사용자에게 보고한다:
     ```
     ## 반입 동기화 완료 (master @ <커밋 7자리>, <날짜>)
     **바뀐 파일**
     - <path> — <이유> [wlk_in 반영 완료]
     ...
     **wheel/wheelhouse**: 재빌드 불필요 / 재빌드함(사유: ...)
     **배포 PC(C:\whist\wlk)에서 적용할 명령**
       copy <path> C:\whist\wlk\<path>
       ...
     **주의**: 여기까지는 dev PC `wlk_in` 스테이징 갱신입니다. 배포 PC는 폐쇄망이라 자동 반영이
     안 됩니다 — 위 파일을 USB로 옮기고 배포 PC에서 직접 덮어써야 실제 적용됩니다. 적용을
     확인해주시면 SYNC_STATE.txt의 deploy_pc_confirmed_applied를 갱신하겠습니다.
     ```

**주의**:
- 배포 PC 파일 vs site-packages(wheel) 구분을 항상 먼저 확인한다 — `scripts/`는 소스트리 실행이라
  파일 자체 복사가 필요하고, `whisperlivekit/`는 **wheel 재설치와 무관하게 cwd의 raw 소스 사본이
  항상 우선 로드된다**(`python -m pkg`는 cwd를 sys.path 최우선에 둔다). 배포 PC에서
  `python -c "import whisperlivekit; print(whisperlivekit.__file__)"`로 실제 로드 경로를 확인하는 게
  가장 확실하다 — wheel만 재설치하고 raw 사본을 안 갱신하면 동작이 안 바뀐다(§8 트랩 참조).
- **"`wlk_in`이 최신"과 "배포 PC가 실제로 반영했음"은 다른 사실이다.** 이 스킬은 dev PC 스테이징
  (`wlk_in`)까지만 책임진다 — 폐쇄망이라 배포 PC 상태를 여기서 검증할 수 없다. 매 동기화 후
  `SYNC_STATE.txt`의 `deploy_pc_confirmed_applied`가 `unknown`이면 사용자에게 USB 반입·적용 여부를
  확인한다.
- `uv run` / `uv sync` / `uv venv` / `uv pip` / `uv add` / `uv remove` / `uv lock`을 공유 `.venv`에
  실행하는 모든 행위는 금지한다.
- 이 스킬은 배포 산출물 동기화까지가 범위다 — STT 성능 회귀 검증(`/eval`)이나 실험 기록
  (`/log-experiment`)은 별개 스킬 소관이다.
