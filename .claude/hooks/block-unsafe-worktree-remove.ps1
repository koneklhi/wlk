# block-unsafe-worktree-remove.ps1 — PreToolUse hook (Bash|PowerShell)
#
# `git worktree remove` 는 워크트리 안의 Windows Directory Junction 을 **따라 들어가
# 대상 디렉터리의 내용을 삭제**한다. 이 저장소는 워크트리들이 메인 `.venv` 를 Junction 으로
# 공유하므로(CLAUDE.md 워크트리 규약), 워크트리를 그냥 제거하면 공유 `.venv` 가 통째로
# 비워지고 진행 중인 모든 측정·pytest 가 즉시 죽는다.
#
# 실측 확인 (2026-08-18):
#   - junction 을 둔 채 `git worktree remove --force` → 대상 디렉터리는 남고 **내용 전멸**
#   - PowerShell `Remove-Item -Recurse` 는 관통하지 않음 (git 만 관통)
#   - junction 을 먼저 `rd` 로 끊은 뒤 remove → 대상 무사
# 같은 날 이 사고가 두 번 재현돼 공유 .venv 가 두 번 파괴됐다(08:55, 14:23). 당시
# UV_NO_SYNC·block-uv-mutate hook 은 무력했다 — uv 는 애초에 원인이 아니었기 때문이다.
#
# 이 hook 은 `git worktree remove` 를 가로채, 대상 워크트리에 재분석 지점(Junction/
# SymbolicLink)이 남아 있으면 차단한다. 링크가 없으면 통과시킨다.
$ErrorActionPreference = 'SilentlyContinue'
$payload = [Console]::In.ReadToEnd()
if (-not $payload) { exit 0 }
$j = $payload | ConvertFrom-Json
$cmd = $j.tool_input.command
if (-not $cmd) { exit 0 }

# `git worktree remove` (옵션 순서 무관) 탐지. prune/list/add 는 대상 아님.
if ($cmd -notmatch '(?:^|[;|&(`])\s*git(?:\.exe)?\s+(?:-[^\s]+\s+)*worktree\s+remove\b') { exit 0 }

# 명령에서 경로 후보를 뽑는다 — `git worktree remove [--force] <path>` 형태.
$paths = @()
foreach ($m in [regex]::Matches($cmd, '(?:^|[;|&(`])\s*git(?:\.exe)?\s+(?:-[^\s]+\s+)*worktree\s+remove\s+(.+)')) {
    $tail = $m.Groups[1].Value
    # 첫 줄만, 그리고 이어지는 다른 명령은 잘라낸다
    $tail = ($tail -split "`n")[0]
    $tail = ($tail -split '[;|&]')[0]
    foreach ($tok in ($tail -split '\s+')) {
        $t = $tok.Trim().Trim('"').Trim("'")
        if (-not $t) { continue }
        if ($t.StartsWith('-')) { continue }   # --force 등 옵션 스킵
        $paths += $t
    }
}
if (-not $paths) { exit 0 }

$repo = $env:CLAUDE_PROJECT_DIR
if (-not $repo) { $repo = 'c:/Users/A040-000-0001/Desktop/260605wlk/wlk' }

$found = @()
foreach ($p in $paths) {
    $cand = $p
    if (-not [System.IO.Path]::IsPathRooted($cand)) {
        $cand = Join-Path $repo $p
        if (-not (Test-Path -LiteralPath $cand)) { $cand = Join-Path $repo "worktrees\$p" }
    }
    if (-not (Test-Path -LiteralPath $cand)) { continue }
    $links = Get-ChildItem -LiteralPath $cand -Recurse -Force -Directory -ErrorAction SilentlyContinue |
             Where-Object { $_.LinkType -in @('Junction', 'SymbolicLink') }
    foreach ($l in $links) { $found += "$($l.FullName) -> $($l.Target)" }
}

if (-not $found) { exit 0 }

$list = ($found | Select-Object -First 5) -join ' | '
$reason = @"
git worktree remove 차단 — 이 워크트리에 Junction 이 남아 있어 **대상(공유 .venv) 내용이 전멸**한다.
git 은 재분석 지점을 따라 들어가 대상 파일을 지운다(2026-08-18 실측 확인, 같은 날 공유 .venv 2회 파괴).
발견된 링크: $list

안전한 제거 절차 — 링크를 먼저 끊고(대상은 보존됨) 그 다음 제거하라:
  cmd /c rd "<워크트리>\.venv"          # 재귀 플래그 없이. 링크만 사라지고 대상은 그대로다
  git worktree remove [--force] <워크트리>

여러 링크가 있거나 자동화하려면:
  Get-ChildItem <워크트리> -Recurse -Force -Directory |
    Where-Object LinkType -in Junction,SymbolicLink |
    ForEach-Object { [System.IO.Directory]::Delete(`$_.FullName, `$false) }
"@

$obj = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } }
$obj | ConvertTo-Json -Compress -Depth 5
exit 0
