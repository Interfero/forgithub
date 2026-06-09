@echo off
cd /d "%~dp0"
wscript //nologo "%~dp0run-serve.vbs"
exit /b %ERRORLEVEL%
