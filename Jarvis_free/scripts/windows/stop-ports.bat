@echo off
call "%~dp0_root.bat"
if exist "logs\server.pid" (
  for /f %%p in (logs\server.pid) do taskkill /F /PID %%p >nul 2>&1
  del /f /q "logs\server.pid" >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":5173 "') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000 "') do taskkill /F /PID %%a >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1
ping 127.0.0.1 -n 3 >nul
