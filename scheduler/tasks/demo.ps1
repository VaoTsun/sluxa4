# Demo scheduled task: writes a timestamped line to the task log.
Write-Output "Demo task ran. Now: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "User: $env:USERNAME   Computer: $env:COMPUTERNAME"
