@echo off
chcp 65001 >nul
call "%~dp0_root.bat"
if not exist "logs\server.log" (
  echo Log poka pust. Zapustite serve.bat
  pause
  exit /b 0
)
powershell -NoProfile -Command "Get-Content -Path 'logs\server.log' -Tail 40 -Encoding UTF8"
echo.
if exist "logs\server.err.log" (
  echo --- stderr ---
  powershell -NoProfile -Command "Get-Content -Path 'logs\server.err.log' -Tail 20 -Encoding UTF8"
)
pause
