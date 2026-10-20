@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    pause
    exit /b 1
)

if not exist "%~dp0logs" mkdir "%~dp0logs"

echo Starting camera backend...
start "Pik-Cha Camera" /D "%~dp0camera" cmd /k python "%~dp0tools\tee_run.py" camera -- python -u app.py
timeout /t 2 /nobreak >nul

echo Starting print worker...
start "Pik-Cha Printer" /D "%~dp0printer" cmd /k python "%~dp0tools\tee_run.py" printer -- python -u print_worker.py

echo Starting frontend server...
start "Pik-Cha Frontend" /D "%~dp0frontend\frontend" cmd /k python "%~dp0tools\tee_run.py" frontend -- python -u -m http.server 5500
timeout /t 2 /nobreak >nul

start "" http://localhost:5500/01_landing_main/index.html
endlocal
