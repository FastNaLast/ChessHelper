@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo [ОШИБКА] Виртуальное окружение не найдено.
    echo Запусти setup.bat — он всё поставит.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" main.py
