@echo off
cd /d "%~dp0"
if /i "%~1"=="full" (
  wscript //nologo "%~dp0scripts\launch\run-restart.vbs" full
) else (
  wscript //nologo "%~dp0scripts\launch\run-restart.vbs"
)
exit /b %ERRORLEVEL%
