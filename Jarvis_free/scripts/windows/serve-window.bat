@echo off
chcp 65001 >nul
call "%~dp0_root.bat"
call "%~dp0stop-ports.bat"
powershell -NoProfile -ExecutionPolicy Bypass -File "%JARVIS_ROOT%\scripts\start-server.ps1" -Visible
call "%~dp0wait-server.bat"
if errorlevel 1 pause & exit /b 1
powershell -NoProfile -ExecutionPolicy Bypass -File "%JARVIS_ROOT%\scripts\open-jarvis-ui.ps1"
pause
