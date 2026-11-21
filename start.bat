@echo off
REM Windows: runs start.sh inside WSL (Ubuntu). Arguments are passed through, e.g. start.bat --input input --output output
REM OCR of scans needs tesseract with Polish in WSL; start.sh installs it if it can (root or passwordless sudo), otherwise prints the command.
cd /d "%~dp0"
wsl bash ./start.sh %*
