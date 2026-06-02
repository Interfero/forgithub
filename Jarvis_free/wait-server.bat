@echo off
setlocal
set /a N=0
:wait
ping 127.0.0.1 -n 2 >nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a N+=1
if %N% LSS 45 goto wait
exit /b 1
