# status_window.ps1 — окно прогресса загрузки "подружки".
# Пока статус BUSY — показывает загрузку. Когда стало DONE — зелёное
# "готова" на ~2 секунды и ЗАКРЫВАЕТСЯ САМО (крестик жать не нужно).
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$statusPath = Join-Path $PSScriptRoot "status.txt"
$utf8 = New-Object System.Text.UTF8Encoding($false)

$form = New-Object System.Windows.Forms.Form
$form.Text = "Подружка — загрузка"
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedToolWindow"
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.ClientSize = New-Object System.Drawing.Size(490, 92)
$form.BackColor = [System.Drawing.Color]::LightYellow

$label = New-Object System.Windows.Forms.Label
$label.Location = New-Object System.Drawing.Point(14, 12)
$label.Size = New-Object System.Drawing.Size(462, 44)
$label.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$label.ForeColor = [System.Drawing.Color]::DarkSlateGray
$label.Text = "Проверяю статус…"

$bar = New-Object System.Windows.Forms.ProgressBar
$bar.Location = New-Object System.Drawing.Point(14, 62)
$bar.Size = New-Object System.Drawing.Size(462, 16)
$bar.Style = "Marquee"
$bar.MarqueeAnimationSpeed = 20

$form.Controls.Add($label)
$form.Controls.Add($bar)

$script:closed = $false

# Одноразовый таймер: через 2 секунды после "готова" закрыть окно сами.
$closeTimer = New-Object System.Windows.Forms.Timer
$closeTimer.Interval = 2000
$closeTimer.Add_Tick({
    $closeTimer.Stop()
    $script:closed = $true
    $form.Close()
})

$refresh = New-Object System.Windows.Forms.Timer
$refresh.Interval = 700
$refresh.Add_Tick({
    if ($script:closed) { return }
    if (Test-Path $statusPath) {
        try {
            $lines = [System.IO.File]::ReadAllLines($statusPath, $utf8)
            $state = if ($lines.Count -gt 0) { $lines[0].Trim() } else { "" }
            $msg = if ($lines.Count -gt 1) { ($lines[1..($lines.Count - 1)] -join " ") } else { "" }
            $age = (New-TimeSpan -Start (Get-Item $statusPath).LastWriteTime -End (Get-Date)).TotalSeconds
        } catch {
            $state = "ERR"; $msg = ""; $age = 0
        }
        if ($state -eq "DONE") {
            $form.BackColor = [System.Drawing.Color]::PaleGreen
            $label.ForeColor = [System.Drawing.Color]::DarkGreen
            $label.Text = "Подружка готова — слушаю.`nГоворите: «подружка»"
            $bar.Style = "Blocks"; $bar.Value = 100
            if (-not $closeTimer.Enabled) { $closeTimer.Start() }
        } elseif ($state -eq "BUSY") {
            $form.BackColor = [System.Drawing.Color]::LightYellow
            $label.ForeColor = [System.Drawing.Color]::DarkSlateGray
            $label.Text = "Загрузка: $msg"
            if ($age -gt 25) { $label.Text += "`n(похоже, процесс остановлен)" }
            $bar.Style = "Marquee"; $bar.MarqueeAnimationSpeed = 20
        } else {
            $form.BackColor = [System.Drawing.Color]::LightGray
            $label.Text = "Неизвестный статус подружки"
        }
    } else {
        $form.BackColor = [System.Drawing.Color]::LightGray
        $label.Text = "Файл статуса не найден.`nПодружка ещё не запускалась."
    }
    $form.Refresh()
})

$refresh.Start()
[System.Windows.Forms.Application]::Run($form)