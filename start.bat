@echo off
REM Uruchomienie na Windows: przez WSL (zalecane) albo lokalny Python 3.13+
cd /d "%~dp0"
where wsl >nul 2>nul && (wsl ./start.sh %*) || (python main.py %*)
