@echo off
:: Pik-Cha! 실행기.
:: 이 파일을 더블클릭하면:
::   1) 이 폴더를 로컬 웹서버(python -m http.server 8000)로 띄우고
::   2) 잠시 기다린 뒤 브라우저로 Main/index.html을 연다.
:: index.html을 직접 더블클릭(file://)하면 카메라 접근이 막히므로
:: 반드시 이 실행기를 통해 열어야 한다.

cd /d "%~dp0"

:: "PikCha Server"라는 이름의 별도(최소화된) 콘솔 창에서 서버를 백그라운드로 실행한다.
:: 다 쓴 후에는 이 창을 닫으면 서버가 종료된다.
start "PikCha Server" /min cmd /c "python -m http.server 8000"

:: 서버가 완전히 뜰 시간을 1초 준다.
timeout /t 1 /nobreak >nul

:: 기본 브라우저로 앱의 진입점을 연다.
start "" http://localhost:8000/Main/index.html
