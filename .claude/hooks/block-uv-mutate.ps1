# block-uv-mutate.ps1 — PreToolUse hook (Bash|PowerShell)
# 공유 .venv(워크트리 Junction 공유) 오염 방지. subagent가 `uv run ruff` 폴백으로
# 암묵적 auto-sync를 트리거하면 diarization-sortformer extra가 떨어져 tokenizers가
# 0.21.4 -> 0.22.2로 강등되고 transformers/sortformer import가 깨져 서버가 죽으며
# 진행 중이던 측정이 전멸한다. 환경-변형 uv 명령을 하드 차단한다.
$ErrorActionPreference = 'SilentlyContinue'
$payload = [Console]::In.ReadToEnd()
if (-not $payload) { exit 0 }
$j = $payload | ConvertFrom-Json
$cmd = $j.tool_input.command
if (-not $cmd) { exit 0 }

# uv 가 "명령 위치"(줄 시작 또는 구분자 ; & | ( 백틱 개행 뒤)에 있을 때만 검사한다.
# 이렇게 해야 커밋 메시지/echo 안의 따옴표 문자열 "uv run ..." 오탐을 피한다(공백/따옴표 뒤는 제외).
$uvAt = '(?:^|[;|&(`\n])\s*uv(?:\.exe)?\s+'
if ($cmd -notmatch $uvAt) { exit 0 }

$deny = $false
$reason = ''

# 1) 환경-변형 서브커맨드는 전면 차단
if ($cmd -match ($uvAt + '(run|pip|add|remove|lock|venv)(\s|$)')) {
  $sub = $Matches[1]
  $deny = $true
  $reason = "uv $sub 차단 — 공유 .venv(워크트리 Junction 공유) 재동기화/오염 방지. uv run 등은 암묵적 auto-sync로 tokenizers 0.21.4->0.22.2 강등을 유발해 서버(sortformer/transformers)를 죽이고 진행 중 측정을 파괴한다. lint는 .venv\Scripts\ruff.exe (또는 .venv\Scripts\python.exe -m ruff)를 직접 호출하라. 의존성 변경이 정말 필요하면 사용자 확인 후: uv sync --extra diarization-sortformer --extra vbcable --extra cu128"
}
# 2) uv sync 는 필수 extra(diarization-sortformer)를 포함할 때만 허용
elseif ($cmd -match ($uvAt + 'sync(\s|$)')) {
  if ($cmd -notmatch '--extra\s+diarization-sortformer') {
    $deny = $true
    $reason = "uv sync 차단 — --extra diarization-sortformer 누락. extras 없는 sync는 tokenizers를 0.22.2로 강등해 transformers/sortformer import를 깨뜨린다. 올바른 형태: uv sync --extra diarization-sortformer --extra vbcable --extra cu128"
  }
}
# uv export/tree/--version/python 등 읽기전용과 올바른 uv sync 는 통과

if (-not $deny) { exit 0 }

$obj = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } }
$obj | ConvertTo-Json -Compress -Depth 5
exit 0
