@echo off
REM Первый/полный запуск без окон консоли. Логи: logs\start.log
REM Режим с окнами (разработка): start-dev.bat
cd /d "%~dp0"
wscript //nologo "%~dp0run-start.vbs"
exit /b %ERRORLEVEL%
