param([string]$In, [string]$OutDir, [string]$Prefix = "slide", [int]$SlideH = 1200, [int]$Quality = 92)
Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Image]::FromFile($In)
$w = $src.Width; $h = $src.Height
$n = [math]::Floor($h / $SlideH)
$codec = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object { $_.MimeType -eq 'image/jpeg' }
$ep = New-Object System.Drawing.Imaging.EncoderParameters(1)
$ep.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality, [long]$Quality)
if ($SlideH -gt 0 -and $n -gt 1) {
  for ($i = 0; $i -lt $n; $i++) {
    $bmp = New-Object System.Drawing.Bitmap($w, $SlideH)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $dst = New-Object System.Drawing.Rectangle(0, 0, $w, $SlideH)
    $rc = New-Object System.Drawing.Rectangle(0, ($i * $SlideH), $w, $SlideH)
    $g.DrawImage($src, $dst, $rc, [System.Drawing.GraphicsUnit]::Pixel)
    $g.Dispose()
    $bmp.Save((Join-Path $OutDir ($Prefix + "-" + ($i + 1) + ".jpg")), $codec, $ep)
    $bmp.Dispose()
  }
}
$all = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($all)
$g.DrawImage($src, 0, 0, $w, $h)
$g.Dispose()
$all.Save((Join-Path $OutDir ($Prefix + "-all.jpg")), $codec, $ep)
$all.Dispose()
$src.Dispose()
"$n slices, $w x $h"
