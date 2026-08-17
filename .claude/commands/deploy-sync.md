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
   - `git log <직전 커밋>..master --oneline`, `git diff <직전 커밋>..master --name-status`로 무엇이
     바뀌었는지 확인한다(이 `--name-status` 출력을 6단계 파일 단위 복사의 목록으로 그대로 재사용한다).
   - 변경이 없으면 "이미 최신"으로 보고하고 종료한다.

3. **변경 범위별 대응 결정 — 2축으로 분리해서 판단한다**

   "의존성 wheelhouse를 재빌드해야 하는가"와 "`wlk_in`의 raw 소스 사본을 갱신해야 하는가"는 서로 다른
   축이다. **whisperlivekit 프로젝트 자체는 wheel로 빌드·설치하지 않는다** — 배포 PC는 항상 `python -m
   whisperlivekit.basic_server`(모듈 실행, `docs/DEPLOYMENT_OFFLINE.md` §0·§4가 권장하는 유일한 기동법)로
   켜고, 이 방식은 cwd(raw 사본)를 sys.path 최우선에 둔다. 즉 `whisperlivekit/**` 변경은 **raw 사본
   갱신만으로 충분**하며 재설치할 프로젝트 wheel 자체가 없다. wheelhouse 재빌드가 필요한 건 **서드파티
   의존성**(`pyproject.toml`/`uv.lock`)이 바뀔 때뿐이다.

   | 바뀐 것 | 의존성 wheelhouse 조치 | `wlk_in` 원본 미러 조치 |
   |---|---|---|
   | `pyproject.toml` / `uv.lock` | wheelhouse 전체 재구성 필요(`docs/DEPLOYMENT_OFFLINE.md` §2.2) — 무거운 작업이니 진행 전 사용자 확인 | 파일 자체도 복사(배포 PC 참고용) |
   | `whisperlivekit/**` (패키지 코드) | **불필요** — 프로젝트는 wheel로 설치하지 않는다 | **변경 파일 복사 필수 — 이게 whisperlivekit 코드 반영의 유일한 경로다.** `python -m` 실행 시 이 사본이 그대로 우선 로드된다 |
   | `scripts/**` | 불필요 — wheel엔 안 들어감 | 변경 파일 복사(배포 PC에서 소스 그대로 직접 실행) |
   | `docs/**` | 불필요 | 변경 파일 복사(배포 PC 운영자 참고용 — "배포 산출물 없음"과 "wlk_in 사본 갱신 불필요"는 다른 얘기다) |
   | `test_data/**`, `tests/**`, 루트 메타파일(`README.md`·`EXPERIMENTS*.md` 등) | 불필요 | 변경 파일 복사 |
   | `frontend/app/**` (React 소스) | 불필요 | 변경 파일 복사(배포 PC는 빌드하지 않는다 — 참고·재빌드 대비용) |
   | **`frontend/static/**` (빌드 dist)** | 해당 없음 | **`.gitignore` 비추적이라 git diff·`git archive`로 절대 안 잡힌다 — 아래 4-B 참조. 배포 PC가 실제로 서빙하는 유일한 UI 산출물이므로 누락하면 화면이 구버전에 머문다** |
   | `whisperlivekit/model/**` | 해당 없음 | `.gitignore` 비추적이라 git diff로 안 잡힘 — 새 모델 파일 추가 여부를 사용자에게 별도 확인 |
   | `whisperlivekit/llm_translation/local_stt_shot/**`, `whisperlivekit/llm_translation/Embedding_model/**` (번역 RAG 자산) | 해당 없음 | `.gitignore` 비추적이라 git diff로 안 잡힘 — **복사도 삭제도 하지 않는다**. 배포 PC 기보유 자산이며 이게 있어야 RAG가 켜진다(`docs/DEPLOYMENT_OFFLINE.md` §6.3). 6단계 파일 단위 갱신에서 이 두 디렉터리를 건드리지 않았는지, 배포 PC에 여전히 존재하는지만 확인 |
   | `.claude/`, `.memorize/`, `.omc/` | 불필요 | **범위 밖** — 배포 PC는 Claude Code를 쓰지 않는다. `wlk_in`에 이미 있는 구버전은 방치해도 무방(정리 불필요) |

4. **서드파티 의존성 wheelhouse 재빌드가 필요한 경우(`pyproject.toml`/`uv.lock` 변경 시) — 공유 `.venv` 절대 접촉 금지**
   - `uv export` / `uv sync` / `uv venv` / `uv run`을 공유(Junction) `.venv`에 실행하지 않는다(CLAUDE.md uv
     가드레일 — 위반 시 IDE 언어서버 잠금과 겹쳐 `.venv`가 반쪽 손상되는 실사고가 있었다,
     `docs/DEPLOYMENT_OFFLINE.md` §8 트랩 표 참조).
   - 전용 워크트리 + 독립 `.venv`(`docs/DEPLOYMENT_OFFLINE.md` §2.2 공식 레시피)에서 `uv export` →
     `pip download`로 wheelhouse를 재구성한다. whisperlivekit 프로젝트 자체는 wheel로 빌드하지 않으므로
     `uv build --wheel`/`python -m build --wheel` 단계는 필요 없다.
   - 무거운 작업(전체 wheelhouse 재구성 등)이면 서브에이전트에 위임해 메인 세션 컨텍스트를 아낀다 —
     워크트리 절대경로를 프롬프트에 명시(CLAUDE.md 워크트리 규약).
   - 패키징 버그 등 **코드 자체를 고쳐야 하는 문제가 발견되면 여기서 직접 고치지 않는다** — 별도
     브랜치+워크트리로 분리하고, 병합은 사용자 승인 후 진행한다(main 브랜치 편집 규약).

4-B. **프론트엔드 dist 갱신이 필요한 경우(`frontend/app/**` 변경 시)**

   `frontend/static/`은 `.gitignore` 대상이라 2단계의 `git diff --name-status`에도, 6단계의
   `git archive`에도 **나타나지 않는다**. 그런데 배포 PC(`--frontend-dir` 기본값 `frontend/static`,
   cwd 상대)가 실제로 서빙하는 것은 이 dist뿐이다. 소스만 복사하고 끝내면 배포 PC UI는 구버전에
   머문 채 "반입했는데 안 바뀐다"가 된다. 따라서 프론트 소스가 바뀌었으면 반드시 여기를 거친다.

   1. **빌드**: `frontend/app`에서 `pnpm install && pnpm typecheck && pnpm test && pnpm build`.
      산출물은 `vite.config.ts`의 `outDir: '../static'` 설정대로 `frontend/static/`에 떨어진다.
      (`pnpm lint`는 반입 이전부터 있던 기존 위반으로 exit 1이 될 수 있다 — 신규 위반 유무만 본다.)
   2. **출처 확인**: 빌드한 트리의 HEAD가 동기화 대상 커밋과 같은지 `git rev-parse`로 대조한다.
      워크트리에서 빌드했다면 그 워크트리 HEAD가 master(또는 master의 머지 부모)여야 한다 —
      다른 커밋으로 빌드한 dist를 반입하면 소스와 화면이 어긋난다.
   3. **복사**: `wlk_in\frontend\static\`을 **통째로 지우고 새로 복사**한다. 여기는 빌드 산출물만
      들어 있는 leaf 디렉터리라 6단계의 "전체 트리 재추출 금지" 경고(모델 가중치 유실 위험)가
      적용되지 않는다. 오히려 지우지 않으면 Vite의 해시 파일명(`index-<hash>.js`) 탓에 구버전
      asset이 무한히 쌓인다.
   4. **검증**: `diff -rq <소스 dist> <wlk_in dist>`로 바이트 단위 동일 확인.

   배포 PC 적용도 같은 이유로 **디렉터리 교체**다 — `C:\whist\wlk\frontend\static\`을 지우고
   새로 덮어쓴다. 파일 단위 복사만 하면 구 asset이 남는다(동작은 하지만 계속 누적된다).

5. **반영 산출물 검증**
   - `frontend/app/**`가 바뀌었으면: `wlk_in\frontend\static\index.html`이 참조하는 asset 해시가
     방금 빌드한 것과 같은지 확인한다 — 소스만 갱신되고 dist가 구버전인 상태가 가장 흔한 실수다.
   - `whisperlivekit/**`가 바뀌었으면: 이번에 바뀐 설정값(`parse_args.py` 기본값 등)과 신규/변경
     서브패키지(예: `whisperlivekit.filtering`·`whisperlivekit.llm_translation`)가 `wlk_in\whisperlivekit\`에
     실제로 반영됐는지 `diff -q`로 확인한다 — 프로젝트가 wheel로 설치되지 않으므로 이 raw 사본 확인이
     유일한 검증 수단이다(`docs/DEPLOYMENT_OFFLINE.md` §8 "raw 소스 파일 복사 누락" 참조).
   - 의존성 wheelhouse를 재구성했으면: `deploy\wheelhouse\`에 신규/변경 의존성이 빠짐없이 받아졌는지
     `pip download` 로그의 `Successfully downloaded` 목록으로 확인한다(`docs/DEPLOYMENT_OFFLINE.md` §2.2).

6. **동기화 반영**
   - `git archive master --output=deploy\deploy_source.zip`을 재생성해 `wlk_in`에도 동일 반영한다.
     의존성 wheelhouse를 재구성했으면 `deploy\wheelhouse\`(신규/갱신분)도 `wlk_in\deploy\wheelhouse\`에
     복사한다 — whisperlivekit 프로젝트는 wheel로 빌드하지 않으므로 복사할 project wheel은 없다.
   - **`wlk_in` 원본 미러는 파일 단위로 갱신한다** — 전체 트리 재추출(`git archive` 통짜 압축 해제)이나
     `robocopy /MIR`는 쓰지 않는다. 두 방식 모두 "git 추적 파일 전체"를 기준으로 움직이는데, gitignore된
     모델 가중치(`model.safetensors`, `.nemo`, silero onnx/jit 등)가 그 기준에 없어 실수로 지워질 위험이
     있다. **whisperlivekit 코드 변경 반영은 이 파일 단위 갱신이 유일한 경로다** — wheel이라는 백스톱이
     없으므로 아래 단계를 빠짐없이 수행한다:
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
     deps_wheelhouse_version: <서드파티 의존성 wheelhouse를 재빌드했으면 새 시각/버전, 아니면 이전 값 유지 — whisperlivekit 프로젝트 자체는 wheel로 배포하지 않으므로 이 필드는 wheelhouse에만 해당>
     deploy_pc_confirmed_applied: unknown

     === HISTORY (append newest at bottom) ===
     --- <ISO 8601> ---
     commit: <커밋 7자리>
     scope: full|incremental
     deps_wheelhouse_rebuilt: yes|no
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
     **의존성 wheelhouse**: 재빌드 불필요 / 재빌드함(사유: ...) — whisperlivekit 프로젝트 자체는 wheel로
     빌드하지 않으므로 이 항목은 서드파티 의존성(`pyproject.toml`/`uv.lock`)이 바뀐 경우에만 해당
     **배포 PC(C:\whist\wlk)에서 적용할 명령**
       copy <path> C:\whist\wlk\<path>
       ...
       (의존성 wheelhouse를 재빌드했을 때만 추가)
       C:\Python312\python.exe -m pip install --no-index --find-links C:\whist\wlk\deploy\wheelhouse -r C:\whist\wlk\deploy\requirements-deploy.txt
     **검증(권장)**: 배포 PC에서 `C:\Python312\python.exe -c "import whisperlivekit; print(whisperlivekit.__file__)"`로
     실제 로드 경로가 `C:\whist\wlk\whisperlivekit\...`인지 확인한다 — `python -m whisperlivekit.basic_server`는
     항상 저장소 루트(cwd)를 우선 로드하므로, 이 경로가 아니라면 저장소 루트 밖에서 실행했는지 의심한다.
     **주의**: 여기까지는 dev PC `wlk_in` 스테이징 갱신입니다. 배포 PC는 폐쇄망이라 자동 반영이
     안 됩니다 — 위 파일을 USB로 옮기고 배포 PC에서 직접 덮어써야 실제 적용됩니다. whisperlivekit 코드
     변경은 **raw 파일 복사만으로 충분**합니다(더 이상 wheel 재설치 단계가 없습니다) — 단, 파일 복사
     자체가 빠짐없이 됐는지는 여전히 확인이 필요합니다(`diff -q`). 적용을 확인해주시면 SYNC_STATE.txt의
     deploy_pc_confirmed_applied를 갱신하겠습니다.
     ```

**주의**:
- `whisperlivekit`는 wheel로 설치하지 않는다 — 배포 PC는 항상 `C:\Python312\python.exe -m
  whisperlivekit.basic_server`(모듈 실행)로 켜고, 이 방식은 cwd(저장소 루트의 raw 사본)를 sys.path
  최우선에 둔다. `scripts/`도 마찬가지로 소스트리 그대로 직접 실행되므로, **두 경로 모두 파일 단위
  복사만 정확하면 반영은 보장된다** — wheel 재설치 같은 별도 단계는 없다. 배포 PC는 venv가 없으므로
  (`docs/DEPLOYMENT_OFFLINE.md` §3) `C:\Python312\python.exe -c "import whisperlivekit;
  print(whisperlivekit.__file__)"`로 실제 로드 경로가 `C:\whist\wlk\whisperlivekit\...`인지 확인하면
  가장 확실하다(같은 문서 §8 트랩 "raw 소스 파일 복사 누락" 참조) — wheel 백스톱이 없으므로 파일
  복사 누락 자체를 잡아낼 유일한 수단은 이 확인과 `diff -q`뿐이다.
- **"`wlk_in`이 최신"과 "배포 PC가 실제로 반영했음"은 다른 사실이다.** 이 스킬은 dev PC 스테이징
  (`wlk_in`)까지만 책임진다 — 폐쇄망이라 배포 PC 상태를 여기서 검증할 수 없다. 매 동기화 후
  `SYNC_STATE.txt`의 `deploy_pc_confirmed_applied`가 `unknown`이면 사용자에게 USB 반입·적용 여부를
  확인한다.
- `uv run` / `uv sync` / `uv venv` / `uv pip` / `uv add` / `uv remove` / `uv lock`을 공유 `.venv`에
  실행하는 모든 행위는 금지한다.
- 이 스킬은 배포 산출물 동기화까지가 범위다 — STT 성능 회귀 검증(`/eval`)이나 실험 기록
  (`/log-experiment`)은 별개 스킬 소관이다.
