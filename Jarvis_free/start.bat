@echo off
REM Запуск Jarvis Free (без окон консоли). Логи: logs\start.log
cd /d "%~dp0"
wscript //nologo "%~dp0scripts\launch\run-start.vbs"
exit /b %ERRORLEVEL%
