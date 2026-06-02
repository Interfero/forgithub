@echo off
chcp 65001 >nul
title Jarvis — браузеры внутри приложения
cd /d "%~dp0"

echo ========================================
echo   Браузеры Jarvis (внутри приложения)
echo   %LOCALAPPDATA%\Jarvis\browsers
echo   - Chromium headless (фон)
echo   - Chromium окно (UI + 2GIS)
echo ========================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat
  pause
  exit /b 1
)

call backend\venv\Scripts\activate.bat
set PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\Jarvis\browsers
if not exist "%PLAYWRIGHT_BROWSERS_PATH%" mkdir "%PLAYWRIGHT_BROWSERS_PATH%"

pip install -U playwright>=1.49.0 -q

echo [1/2] playwright install chromium --force
python -m playwright install --force chromium
echo [2/2] playwright install chromium-headless-shell --force
python -m playwright install --force chromium-headless-shell

echo.
echo Проверка chrome.exe...
cd backend
python -c "from modules.jarvis_browsers import find_windowed_chrome_exe,find_headless_chromium_exe; print('windowed:', find_windowed_chrome_exe()); print('headless:', find_headless_chromium_exe())"
cd ..

echo.
echo Готово. Перезапустите Jarvis (restart.bat).
pause
