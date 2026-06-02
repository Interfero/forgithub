@echo off
chcp 65001 >nul
cd /d "%~dp0"
call "%~dp0stop-ports.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-server.ps1" -Visible
call "%~dp0wait-server.bat"
if errorlevel 1 pause & exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\open-jarvis-ui.ps1"
pause
