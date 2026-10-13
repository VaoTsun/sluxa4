# Manage OpenCode scheduled tasks via Windows Task Scheduler.
# Usage:
#   schedule.ps1 -Action add    -Name prices -Time 09:00     # daily at 09:00
#   schedule.ps1 -Action add    -Name test   -Minutes 5      # every 5 minutes
#   schedule.ps1 -Action list
#   schedule.ps1 -Action run    -Name prices
#   schedule.ps1 -Action remove -Name prices
param(
  [Parameter(Mandatory=$true)][ValidateSet('add','remove','list','run')][string]$Action,
  [string]$Name,
  [string]$Time = "09:00",
  [int]$Minutes = 0
)

$root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$runScript = Join-Path $root "run.ps1"
$prefix    = "OpenCode-"
$ErrorActionPreference = "Stop"

function Full-Name([string]$n) { return $prefix + $n }

switch ($Action) {
  'list' {
    $items = Get-ScheduledTask | Where-Object { $_.TaskName -like "$prefix*" }
    if (-not $items) { "No scheduled tasks yet." }
    else { $items | Select-Object TaskName, State | Format-Table -AutoSize | Out-String | Write-Output }
  }
  'run' {
    if (-not $Name) { throw "-Name required" }
    Start-ScheduledTask -TaskName (Full-Name $Name)
    "Triggered: $(Full-Name $Name)"
  }
  'remove' {
    if (-not $Name) { throw "-Name required" }
    Unregister-ScheduledTask -TaskName (Full-Name $Name) -Confirm:$false
    "Removed: $(Full-Name $Name)"
  }
  'add' {
    if (-not $Name) { throw "-Name required" }
    $arg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runScript`" -Name `"$Name`""
    $taskAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
    if ($Minutes -gt 0) {
      $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $Minutes) `
        -RepetitionDuration (New-TimeSpan -Days 3650)
    } else {
      $trigger = New-ScheduledTaskTrigger -Daily -At $Time
    }
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
      -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
      -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName (Full-Name $Name) -Action $taskAction `
      -Trigger $trigger -Settings $settings `
      -Description "OpenCode scheduled task '$Name'" -Force | Out-Null
    "Registered: $(Full-Name $Name)"
  }
}
