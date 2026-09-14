@echo off
:: Pik-Cha! 전체 실행기.
:: 카메라 백엔드(camera/app.py, 8000번) + 인쇄 워커(printer/print_worker.py)
:: + 프론트(frontend, 5500번)를 각각 별도 창으로 띄우고 브라우저를 연다.
:: 로그를 봐야 하니 각 창은 끝나도 자동으로 안 닫히게(cmd /k) 열어둔다.

cd /d "%~dp0"

echo [1/3] 카메라 백엔드 시작 (camera/app.py, http://localhost:8000)
start "Pik-Cha - Camera Backend" cmd /k "cd /d "%~dp0camera" && python app.py"

:: 백엔드가 8000번 포트를 먼저 잡을 시간을 준다.
timeout /t 2 /nobreak >nul

echo [2/3] 인쇄 워커 시작 (printer/print_worker.py)
start "Pik-Cha - Print Worker" cmd /k "cd /d "%~dp0printer" && python print_worker.py"

echo [3/3] 프론트 정적서버 시작 (frontend, http://localhost:5500)
start "Pik-Cha - Frontend" cmd /k "cd /d "%~dp0frontend" && python -m http.server 5500"

:: 프론트 서버가 뜰 시간을 준다.
timeout /t 2 /nobreak >nul

start "" http://localhost:5500/Main/index.html
