@echo off
REM Сервер на :8000 без окон консоли. Окно для отладки: serve-window.bat
cd /d "%~dp0"
wscript //nologo "%~dp0run-serve.vbs"
exit /b %ERRORLEVEL%
