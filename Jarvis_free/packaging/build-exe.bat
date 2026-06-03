@echo off
chcp 65001 >nul
title Jarvis — сборка exe
cd /d "%~dp0\.."

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat
  pause
  exit /b 1
)

cd frontend
call npm run build
if errorlevel 1 ( cd .. & pause & exit /b 1 )
cd ..

cd backend
call venv\Scripts\python.exe -c "from modules.memory_store import _ensure_dirs; _ensure_dirs()"
cd ..

call backend\venv\Scripts\pip.exe install pyinstaller -q
call backend\venv\Scripts\pyinstaller.exe packaging\jarvis.spec --noconfirm
if errorlevel 1 ( pause & exit /b 1 )

echo Готово: dist\Jarvis.exe
pause
