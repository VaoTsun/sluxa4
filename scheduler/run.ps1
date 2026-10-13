# Generic task runner for OpenCode scheduled tasks.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1 -Name <task>
# Looks for tasks\<name>.ps1 | tasks\<name>.py | tasks\<name>.cmd and logs to logs\<name>.log
param(
  [Parameter(Mandatory=$true)][string]$Name
)

# Корректная работа с UTF-8 (иначе русский текст из дочерних процессов превращается в кракозябры)
try {
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
  $OutputEncoding = New-Object System.Text.UTF8Encoding $false
} catch { }

$root    = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskDir = Join-Path $root "tasks"
$logDir  = Join-Path $root "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$log = Join-Path $logDir "$Name.log"

function Write-Log([string]$m) {
  "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Add-Content -Path $log -Encoding UTF8
}

Write-Log "=== START '$Name' ==="

$file = @(
  (Join-Path $taskDir "$Name.ps1"),
  (Join-Path $taskDir "$Name.py"),
  (Join-Path $taskDir "$Name.cmd")
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $file) {
  Write-Log "ERROR: task file not found (tasks\$Name.ps1|.py|.cmd)"
  exit 2
}

Write-Log "Script: $file"

try {
  if ($file -like "*.py") {
    $out = & python -X utf8 $file 2>&1 | Out-String
  } elseif ($file -like "*.cmd") {
    $out = & cmd /c $file 2>&1 | Out-String
  } else {
    $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $file 2>&1 | Out-String
  }
  if ($out.Trim()) { $out.TrimEnd() | Add-Content -Path $log -Encoding UTF8 }
  Write-Log "=== OK (exit=$LASTEXITCODE) ==="
} catch {
  Write-Log "ERROR: $($_.Exception.Message)"
  exit 1
}
