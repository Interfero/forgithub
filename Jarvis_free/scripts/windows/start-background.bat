@echo off
call "%~dp0_root.bat"
wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-serve.vbs"
exit /b %ERRORLEVEL%
