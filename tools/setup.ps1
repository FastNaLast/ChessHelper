# Установка зависимостей и движка. Запускается через setup.bat
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "=== 1/3 Проверка Python ===" -ForegroundColor Cyan
$python = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $python) {
    Write-Host "Python не найден в PATH. Установи Python 3.10+ и запусти снова." -ForegroundColor Red
    exit 1
}
Write-Host ("Python: " + $python.Source)

Write-Host "=== 2/3 Виртуальное окружение и пакеты ===" -ForegroundColor Cyan
if (-not (Test-Path "$root\.venv\Scripts\python.exe")) {
    python -m venv "$root\.venv"
}
$py = "$root\.venv\Scripts\python.exe"

$mirrors = @(
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple"
)
$installed = $false
foreach ($mirror in $mirrors) {
    Write-Host ("Пробую индекс: " + $mirror)
    & $py -m pip install --index-url $mirror --timeout 120 --retries 2 -r requirements.txt
    if ($LASTEXITCODE -eq 0) { $installed = $true; break }
}
if (-not $installed) {
    Write-Host "Не удалось поставить пакеты ни с одного индекса. Проверь интернет/VPN." -ForegroundColor Red
    exit 1
}

Write-Host "=== 3/3 Stockfish ===" -ForegroundColor Cyan
if (Test-Path "$root\engine\stockfish.exe") {
    Write-Host "Stockfish уже на месте."
} else {
    $url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip"
    $zip = "$root\engine\stockfish.zip"
    New-Item -ItemType Directory -Force -Path "$root\engine" | Out-Null
    $ProgressPreference = "SilentlyContinue"
    Write-Host "Скачиваю Stockfish (~81 МБ)..."
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath "$root\engine\tmp" -Force
    $exe = Get-ChildItem "$root\engine\tmp" -Recurse -Filter "stockfish*.exe" | Select-Object -First 1
    Copy-Item $exe.FullName "$root\engine\stockfish.exe" -Force
    Remove-Item "$root\engine\tmp" -Recurse -Force
    Remove-Item $zip -Force
    Write-Host "Stockfish установлен."
}

Write-Host ""
Write-Host "Готово. Запускай run.bat" -ForegroundColor Green
