@echo off
call "%~dp0_root.bat"
wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-restart.vbs" full
exit /b %ERRORLEVEL%
