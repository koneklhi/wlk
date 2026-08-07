---
description: master에 채택 실험이 머지된 직후 docs/MASTER_CHANGES.md를 최신 상태로 갱신한다
---

<allowed-tools>
Bash(git log*)
Bash(git diff*)
Bash(git show*)
Bash(git merge-base*)
</allowed-tools>

master에 채택 실험이 머지된 직후 `docs/MASTER_CHANGES.md`를 갱신해줘.

1. **현재 상태 파악**
   - `docs/MASTER_CHANGES.md`를 읽는다.
   - `git log --oneline -10 --first-parent master`로 최근 머지 내역을 확인한다.
   - 가장 최근 머지 커밋(merge(phaseN): Exp-NNN 채택 형식)과 해당 브랜치 diff를 확인한다.
   - `EXPERIMENTS_LOG.md`(Exp-131+, `grep "Exp-NNN"`으로 해당 블록만) 또는 `PHASE2_EXPERIMENTS.md`(Exp-001~130 아카이브)에서 해당 Exp-N 섹션을 읽어 가설·변경·수치·결론을 파악한다.

2. **§2 베이스라인 수치 갱신**
   - 최신 path C N≥3 측정 결과(median/max/stdev/F1)로 표를 교체한다.
   - 기존 베이스라인 수치는 삭제하고 새 수치로 덮어쓴다 (역사는 EXPERIMENTS.md/PHASE2_EXPERIMENTS.md 소관).
   - `.omc/benchmarks/` 디렉토리에 최신 JSON 결과 파일이 있으면 그 수치를 정확히 옮긴다.

3. **해당 도메인 섹션 갱신/추가 (§3~§7)**
   - 채택된 변경이 속하는 섹션(STT 품질·필터링·번역·스키마·eval)을 찾아 내용을 추가하거나 업데이트한다.
   - 형식 유지: `upstream 동작 → 우리 변경 → 성능/이유 → 핵심 파일(링크) → 도입 Exp-N`
   - 기각된 내용, 중간 과정, 시행착오는 절대 추가하지 않는다 (EXPERIMENTS.md 소관).
   - 새로운 섹션이 필요하면 기존 섹션 번호 체계를 이어서 추가한다.

4. **§8 향후 개선점(TODO) 갱신**
   - 이번 채택으로 해결된 TODO 항목이 있으면 제거한다.
   - 해당 Exp의 "다음 가설" 내용을 TODO에 추가한다.
   - 우선순위(단기/중기/장기)를 유지한다.

5. **§9 갱신 규약** — 내용은 건드리지 않는다.

6. **검증**
   - 수정 결과를 출력해 보여준다.
   - 커밋 메시지 초안을 제안한다: `docs: MASTER_CHANGES.md — Exp-NNN 채택 반영`
   - 수정할 부분이 있는지 사용자에게 확인을 구한다.

**주의**:
- 시행착오·기각 실험은 이 문서에 추가하지 않는다.
- 수치는 코드나 JSON에서 직접 확인한 것만 기재한다. 추측하지 않는다.
- 파일 링크는 `docs/` 기준 상대 경로(`../whisperlivekit/...`)로 작성한다.
