# Задача Планировщика: ежедневная проверка цен на роботы-газонокосилки.
# Запускается из scheduler\run.ps1 -Name prices, результат идёт в logs\prices.log.
$ErrorActionPreference = "Stop"

# UTF-8, чтобы русский вывод python не портился
try {
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
  $OutputEncoding = New-Object System.Text.UTF8Encoding $false
} catch { }

$here     = Split-Path -Parent $MyInvocation.MyCommand.Path          # ...\scheduler\tasks
$schedDir = Split-Path -Parent $here                                 # ...\scheduler
$root     = Split-Path -Parent $schedDir                             # ...\sluxach
$script   = Join-Path $root "prices\check_prices.py"

if (-not (Test-Path $script)) { throw "Не найден скрипт: $script" }

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = "C:\Users\vodev\AppData\Local\Programs\Python\Python312\python.exe" }

& $py -X utf8 $script
exit $LASTEXITCODE
