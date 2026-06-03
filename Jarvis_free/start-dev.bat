@echo off
cd /d "%~dp0"
call "%~dp0scripts\windows\start-dev.bat"
exit /b %ERRORLEVEL%
