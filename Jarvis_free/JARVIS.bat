@echo off
cd /d "%~dp0"
call "%~dp0scripts\windows\start-quick.bat"
exit /b %ERRORLEVEL%
