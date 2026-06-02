@echo off
REM Перезапуск без окон консоли. Логи: logs\restart.log, logs\frontend-build.log
cd /d "%~dp0"
if /i "%~1"=="full" (
  wscript //nologo "%~dp0run-restart.vbs" full
) else (
  wscript //nologo "%~dp0run-restart.vbs"
)
exit /b %ERRORLEVEL%
