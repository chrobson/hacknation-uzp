@echo off
REM Windows: runs start.sh inside WSL (Ubuntu). Arguments are passed through, e.g. start.bat --input input --output output
cd /d "%~dp0"
wsl bash ./start.sh %*
