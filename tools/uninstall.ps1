# Удаляет всё, что было скачано и установлено для проекта.
# Код, data\ и reports\ остаются на месте.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Get-SizeMb($path) {
    if (-not (Test-Path $path)) { return 0 }
    $bytes = (Get-ChildItem $path -Recurse -Force -ErrorAction SilentlyContinue |
              Measure-Object -Property Length -Sum).Sum
    if (-not $bytes) { return 0 }
    return [Math]::Round($bytes / 1MB, 1)
}

$removed = 0.0

foreach ($target in @("$root\.venv", "$root\engine")) {
    if (Test-Path $target) {
        $size = Get-SizeMb $target
        Write-Host ("Удаляю " + $target + " (" + $size + " МБ)")
        Remove-Item $target -Recurse -Force
        $removed += $size
    }
}

Get-ChildItem $root -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Remove-Item "$root\reports\capture.png" -Force -ErrorAction SilentlyContinue
$desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item (Join-Path $desktop "Шахматный помощник.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $desktop "Шахматы на телефоне.lnk") -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host ("Освобождено примерно " + [Math]::Round($removed, 1) + " МБ.") -ForegroundColor Green
Write-Host "Осталось (твой код и данные): app\, main.py, data\, reports\, tools\, README.md, settings.json"
Write-Host "Чтобы вернуть всё обратно — запусти setup.bat"
