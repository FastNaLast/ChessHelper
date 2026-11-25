# Собирает zip для переноса проекта на другой компьютер.
# Не включает .venv и engine — на новом ПК их пересоздаст setup.bat.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stamp = Get-Date -Format "yyyy-MM-dd-HHmm"
$desktop = [Environment]::GetFolderPath("Desktop")
$zip = Join-Path $desktop ("chess-assistant-" + $stamp + ".zip")
$tmp = Join-Path $env:TEMP ("chess-assistant-backup-" + $stamp)

Write-Host "Копирую файлы во временную папку..."
robocopy $root $tmp /E /XD ".venv" "engine" "__pycache__" /XF "*.pyc" /NFL /NDL /NJH /NJS | Out-Null

Write-Host "Упаковываю..."
Compress-Archive -Path (Join-Path $tmp "*") -DestinationPath $zip -Force
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host ("Готово: " + $zip) -ForegroundColor Green
Write-Host "На новом компьютере: распаковать -> setup.bat -> run.bat"
