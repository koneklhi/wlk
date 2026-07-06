# block-uv-mutate.ps1 — PreToolUse hook (Bash|PowerShell)
# 공유 .venv(워크트리 Junction 공유) 오염 방지. subagent가 `uv run ruff` 폴백으로
# 암묵적 auto-sync를 트리거하면 diarization-sortformer extra가 떨어져 tokenizers가
# 0.21.4 -> 0.22.2로 강등되고 transformers/sortformer import가 깨져 서버가 죽으며
# 진행 중이던 측정이 전멸한다. 환경-변형 uv 명령을 하드 차단한다.
#
# 검사 방식: 명령 문자열을 줄 단위로 훑어 "명령 위치"(줄 시작 또는 구분자 ; | & ( 백틱 뒤)의
# uv 를 잡는다. 과거엔 전체 문자열에 대해 개행(\n)을 제외해, 여러 uv 줄을 개행으로 이어붙인
# 명령의 2번째+ 줄이 샜다(예: DEPLOYMENT_OFFLINE §2.2 wheelhouse 빌드 블록). 이제 줄 단위로
# 검사하되 heredoc / PowerShell here-string 본문(커밋메시지 등)만 스킵해 오탐을 막는다.
$ErrorActionPreference = 'SilentlyContinue'
$payload = [Console]::In.ReadToEnd()
if (-not $payload) { exit 0 }
$j = $payload | ConvertFrom-Json
$cmd = $j.tool_input.command
if (-not $cmd) { exit 0 }

# 한 줄 안에서 uv 가 "명령 위치"에 있을 때만 매칭. 줄 단위 검사이므로 ^ 가 각 줄 시작을 가리킨다.
$uvAt = '(?:^|[;|&(`])\s*uv(?:\.exe)?\s+'

$deny = $false
$reason = ''
$hereEnd = $null   # non-null 이면 heredoc/here-string 본문 스킵 중 (종료 토큰 저장)

foreach ($ln in ($cmd -split "`n")) {
  $line = $ln.TrimEnd("`r")

  # heredoc/here-string 본문 스킵 중이면 종료 토큰만 확인하고 넘어간다
  if ($null -ne $hereEnd) {
    if ($line.Trim() -eq $hereEnd) { $hereEnd = $null }
    continue
  }

  # 1) 이 줄의 uv 변형 명령 검사 (heredoc 시작 감지보다 먼저 — 오프너 줄 자체도 검사)
  if ($line -match $uvAt) {
    # 환경-변형 서브커맨드 전면 차단
    if ($line -match ($uvAt + '(run|pip|add|remove|lock)(\s|$)')) {
      $sub = $Matches[1]
      $deny = $true
      $reason = "uv $sub 차단 — 공유 .venv(워크트리 Junction 공유) 재동기화/오염 방지. uv run 등은 암묵적 auto-sync로 tokenizers 0.21.4->0.22.2 강등을 유발해 서버(sortformer/transformers)를 죽이고 진행 중 측정을 파괴한다. lint는 .venv\Scripts\ruff.exe (또는 .venv\Scripts\python.exe -m ruff)를 직접 호출하라. 배포/wheelhouse 등 uv가 정말 필요한 작업은 Junction 해제(rmdir .venv) 후 전용 워크트리의 독립 .venv에서 수행하라. 의존성 변경이 정말 필요하면 사용자 확인 후: uv sync --extra diarization-sortformer --extra vbcable --extra cu128"
      break
    }
    # uv venv (--clear 포함): 공유 .venv 재생성/재빌드 — 반쪽 손상의 직접 원인
    elseif ($line -match ($uvAt + 'venv(\s|$)')) {
      $deny = $true
      $reason = "uv venv 차단 — 공유 .venv 재생성/재빌드 금지. venv 재생성 중 IDE(antigravity Jedi 언어서버)가 .venv\Scripts\python.exe를 잠그면 Scripts 제거가 '액세스 거부(os error 5)'로 실패해 Lib·pyvenv.cfg만 소실되는 반쪽 손상(python.exe exit 106 'No pyvenv.cfg file')이 발생, 측정·pytest가 전면 차단된다. 배포/wheelhouse 등 uv가 필요한 작업은 반드시 Junction 해제(rmdir .venv) 후 전용 워크트리의 독립 .venv에서 수행하라 — 공유 venv에는 절대 금지."
      break
    }
    # uv sync 는 필수 extra(diarization-sortformer)를 포함할 때만 허용.
    # 백틱 줄이음으로 --extra 가 다음 줄에 올 수 있으므로 extra 존재 여부는 전체 명령($cmd)에서 확인한다.
    elseif ($line -match ($uvAt + 'sync(\s|$)')) {
      if ($cmd -notmatch '--extra\s+diarization-sortformer') {
        $deny = $true
        $reason = "uv sync 차단 — --extra diarization-sortformer 누락. extras 없는 sync는 tokenizers를 0.22.2로 강등해 transformers/sortformer import를 깨뜨린다. 올바른 형태: uv sync --extra diarization-sortformer --extra vbcable --extra cu128"
        break
      }
    }
    # uv export/tree/--version/python 등 읽기전용과 올바른 uv sync 는 통과
  }

  # 2) heredoc / here-string 시작 감지 → 다음 줄부터 본문 스킵 (커밋메시지 안의 uv 오탐 방지)
  if ($line -match "@'\s*$")      { $hereEnd = "'@" }
  elseif ($line -match '@"\s*$')  { $hereEnd = '"@' }
  elseif ($line -match '<<-?\s*["'']?([A-Za-z_][A-Za-z0-9_]*)["'']?\s*$') { $hereEnd = $Matches[1] }
}

if (-not $deny) { exit 0 }

$obj = @{ hookSpecificOutput = @{ hookEventName = 'PreToolUse'; permissionDecision = 'deny'; permissionDecisionReason = $reason } }
$obj | ConvertTo-Json -Compress -Depth 5
exit 0
