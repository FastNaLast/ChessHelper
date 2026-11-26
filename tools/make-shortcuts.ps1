# Создаёт ярлыки на рабочем столе с иконками проекта.
# Запуск: powershell -ExecutionPolicy Bypass -File tools\make-shortcuts.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
$main = Join-Path $root "main.py"
$phone = Join-Path $root "run-phone.bat"
$icons = Join-Path $root "assets\icons"

if (-not (Test-Path $pythonw)) {
    Write-Host "Нет .venv — сначала запусти setup.bat" -ForegroundColor Red
    exit 1
}

$ws = New-Object -ComObject WScript.Shell

function New-Shortcut {
    param(
        [string]$Name,
        [string]$Target,
        [string]$Arguments,
        [string]$Icon,
        [string]$Description
    )
    $path = Join-Path $desktop $Name
    $shortcut = $ws.CreateShortcut($path)
    $shortcut.TargetPath = $Target
    $shortcut.Arguments = $Arguments
    $shortcut.WorkingDirectory = $root
    $shortcut.Description = $Description
    $shortcut.WindowStyle = 1
    if (Test-Path $Icon) {
        $shortcut.IconLocation = "$Icon,0"
    }
    $shortcut.Save()
    Write-Host "OK  $Name" -ForegroundColor Green
}

New-Shortcut -Name "Шахматный помощник.lnk" `
    -Target $pythonw `
    -Arguments "`"$main`"" `
    -Icon (Join-Path $icons "assistant.ico") `
    -Description "Шахматный помощник: анализ позиции, разбор PGN, дебюты"

New-Shortcut -Name "Шахматы на телефоне.lnk" `
    -Target $phone `
    -Arguments "" `
    -Icon (Join-Path $icons "phone.ico") `
    -Description "Локальный сервер шахмат для телефона"

# обновить иконки в копиях, если они лежат в Desktop\chess
$copyDir = Join-Path $desktop "chess"
if (Test-Path $copyDir) {
    foreach ($name in "Шахматный помощник.lnk", "Шахматы на телефоне.lnk") {
        $source = Join-Path $desktop $name
        if (Test-Path $source) {
            Copy-Item $source (Join-Path $copyDir $name) -Force
        }
    }
}

# сбросить кэш иконок, чтобы обновились сразу
try {
    & ie4uinit.exe -show
} catch {
}
Write-Host "Готово." -ForegroundColor Green
