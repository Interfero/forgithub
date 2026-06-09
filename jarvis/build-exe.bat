@echo off
chcp 65001 >nul
title Jarvis — сборка exe
cd /d "%~dp0"

echo ========================================
echo   Jarvis — сборка Jarvis.exe
echo ========================================

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat — нужен venv в backend\venv
  pause
  exit /b 1
)

echo [1/3] Сборка интерфейса...
cd frontend
call npm run build
if errorlevel 1 (
  cd ..
  pause
  exit /b 1
)
cd ..

echo [2/3] Подготовка data\memory...
if not exist "backend\data\memory" mkdir "backend\data\memory"
cd backend
call venv\Scripts\python.exe -c "from modules.memory_store import _ensure_dirs; _ensure_dirs(); print('memory dirs ok')"
cd ..
if errorlevel 1 (
  echo Ошибка подготовки memory
  pause
  exit /b 1
)

echo [3/3] PyInstaller...
call backend\venv\Scripts\pip.exe install pyinstaller -q
call backend\venv\Scripts\pyinstaller.exe jarvis.spec --noconfirm
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo Готово: dist\Jarvis.exe
echo Данные пользователя: %%LOCALAPPDATA%%\Jarvis\data
echo Файлы предобучения из exe копируются туда только если ещё нет.
echo.
pause
