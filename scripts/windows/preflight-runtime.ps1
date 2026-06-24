param(
  [Parameter(Mandatory=$true)]
  [string]$RepoRoot,

  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repo = (Resolve-Path $RepoRoot).Path

function Normalize-PathString([string]$value) {
  if ([string]::IsNullOrWhiteSpace($value)) {
    return ""
  }

  return $value.Replace("/", "\").TrimEnd("\").ToLowerInvariant()
}

$repoNorm = Normalize-PathString $repo
$tauriConfigPath = Join-Path $repo "desktop\src-tauri\tauri.conf.json"

if (!(Test-Path $tauriConfigPath)) {
  Write-Error "[preflight] tauri.conf.json not found: $tauriConfigPath"
  exit 1
}

$rawConfig = Get-Content $tauriConfigPath -Raw -Encoding UTF8
if ($rawConfig -match '"devUrl"\s*:\s*"([^"]+)"') {
  $devUrl = $matches[1]
} else {
  Write-Error "[preflight] devUrl not found in tauri.conf.json"
  exit 1
}
$uri = [Uri]$devUrl
$port = [int]$uri.Port

Write-Host "[preflight] repo=$repo"
Write-Host "[preflight] repoNorm=$repoNorm"
Write-Host "[preflight] devUrl=$devUrl port=$port"

# 1. Kill stale dev server only if it belongs to this repo.
$listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)

foreach ($conn in $listeners) {
  $pidValue = [int]$conn.OwningProcess
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue

  $cmd = ""
  $exe = ""
  if ($proc) {
    $cmd = [string]$proc.CommandLine
    $exe = [string]$proc.ExecutablePath
  }

  Write-Host "[preflight] port $port occupied by PID=$pidValue EXE=$exe CMD=$cmd"

  $cmdNorm = Normalize-PathString $cmd
  $exeNorm = Normalize-PathString $exe

  $belongsToRepo =
    ($cmdNorm -like "*$repoNorm*") -or
    ($exeNorm -like "*$repoNorm*")

  if ($belongsToRepo) {
    if ($DryRun) {
      Write-Host "[preflight] DRY RUN would kill PID=$pidValue"
    } else {
      Write-Host "[preflight] killing stale repo-owned dev server PID=$pidValue"
      Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    }
  } else {
    Write-Error "[preflight] port $port is occupied by a process not owned by this repo. Refuse to start to avoid loading wrong frontend."
    exit 1
  }
}

# 2. Kill stale Tauri binary only if executable path is under this repo target dir.
$tauriProcs = @(Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -like "*有声书翻译工坊*") -or
  ($_.CommandLine -like "*youshengshu*")
})

foreach ($proc in $tauriProcs) {
  $pidValue = [int]$proc.ProcessId
  $cmd = [string]$proc.CommandLine
  $exe = [string]$proc.ExecutablePath

  $cmdNorm = Normalize-PathString $cmd
  $exeNorm = Normalize-PathString $exe

  $belongsToRepo =
    ($cmdNorm -like "*$repoNorm*") -or
    ($exeNorm -like "*$repoNorm*")

  if ($belongsToRepo) {
    if ($DryRun) {
      Write-Host "[preflight] DRY RUN would kill stale Tauri PID=$pidValue"
    } else {
      Write-Host "[preflight] killing stale repo-owned Tauri PID=$pidValue"
      Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
    }
  }
}

# 3. Remove Vite cache under this repo only.
$cachePaths = @(
  (Join-Path $repo "desktop\node_modules\.vite"),
  (Join-Path $repo "desktop\.vite")
)

foreach ($path in $cachePaths) {
  if (Test-Path $path) {
    if ($DryRun) {
      Write-Host "[preflight] DRY RUN would remove cache $path"
    } else {
      Write-Host "[preflight] removing cache $path"
      Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
    }
  }
}

Write-Host "[preflight] OK"
exit 0
