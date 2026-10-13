# read_deepseek_window.ps1
# Снимает окно DeepSeek Harness (через PrintWindow, работает даже если окно за другими)
# и распознаёт текст встроенным OCR Windows (ru). Результат пишет в UTF-8 файл.
param(
  [string]$OutTxt = "ds_ocr.txt",
  [int]$CropLeft = 0,
  [int]$CropTop = 0,
  [int]$CropRight = 0,
  [int]$CropBottom = 0
)

Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class NativeShot {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
[NativeShot]::SetProcessDPIAware() | Out-Null

function Write-Out([string]$t) {
  [IO.File]::WriteAllText($OutTxt, $t, (New-Object Text.UTF8Encoding($false)))
}

$proc = Get-Process | Where-Object { $_.ProcessName -like '*DeepSeek*' -and $_.MainWindowHandle -ne 0 } | Select-Object -First 1
if (-not $proc) { Write-Out ""; exit 0 }

$hwnd = $proc.MainWindowHandle
$rect = New-Object NativeShot+RECT
[NativeShot]::GetWindowRect($hwnd, [ref]$rect) | Out-Null
$w = $rect.Right - $rect.Left
$h = $rect.Bottom - $rect.Top
if ($w -le 0 -or $h -le 0) { Write-Out ""; exit 0 }

$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
[NativeShot]::PrintWindow($hwnd, $hdc, 2) | Out-Null
$g.ReleaseHdc($hdc)
$g.Dispose()

if ($CropLeft -or $CropTop -or $CropRight -or $CropBottom) {
  $cw = $w - $CropLeft - $CropRight
  $ch = $h - $CropTop - $CropBottom
  if ($cw -gt 0 -and $ch -gt 0) {
    $crop = New-Object System.Drawing.Bitmap($cw, $ch)
    $cg = [System.Drawing.Graphics]::FromImage($crop)
    $srcRect = New-Object System.Drawing.Rectangle($CropLeft, $CropTop, $cw, $ch)
    $dstRect = New-Object System.Drawing.Rectangle(0, 0, $cw, $ch)
    $cg.DrawImage($bmp, $dstRect, $srcRect, [System.Drawing.GraphicsUnit]::Pixel)
    $cg.Dispose()
    $bmp.Dispose()
    $bmp = $crop
  }
}

$png = [IO.Path]::ChangeExtension($OutTxt, ".png")
$bmp.Save($png, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($op, $type) {
  $t = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
  $t.Wait(-1) | Out-Null
  $t.Result
}

[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($png)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$lang = New-Object Windows.Globalization.Language("ru")
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
$text = ""
if ($engine) {
  $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $text = $result.Text
}
Write-Out $text
