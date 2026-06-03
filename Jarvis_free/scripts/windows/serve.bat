@echo off
REM Сервер на :8000 без окон консоли. Окно для отладки: serve-window.bat
call "%~dp0_root.bat"
wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-serve.vbs"
exit /b %ERRORLEVEL%
