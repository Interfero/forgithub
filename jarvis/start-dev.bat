@echo off
chcp 65001 >nul
title Jarvis — режим разработки
cd /d "%~dp0"

echo Режим разработки: Backend :8000 + Vite :5173
echo Для обычного использования запускайте start.bat
echo.

call "%~dp0stop-ports.bat"

if not exist "frontend\node_modules" (
  cd frontend
  call npm install
  cd ..
)

call backend\venv\Scripts\activate.bat 2>nul

start "Jarvis Backend" cmd /k "cd /d %~dp0backend && call venv\Scripts\activate.bat && uvicorn main:app --reload --host 127.0.0.1 --port 8000"
ping 127.0.0.1 -n 4 >nul
start "Jarvis Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

set /a N=0
:wait5173
ping 127.0.0.1 -n 2 >nul
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>&1
if not errorlevel 1 goto ok
set /a N+=1
if %N% LSS 20 goto wait5173
echo Frontend не запустился — смотрите окно Jarvis Frontend
pause
exit /b 1
:ok
start "" "http://127.0.0.1:5173/"
pause
