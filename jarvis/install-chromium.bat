@echo off
chcp 65001 >nul
title Jarvis — встроенный Chromium (Playwright)
cd /d "%~dp0"

echo ========================================
echo   Встроенный браузер Jarvis (Chromium)
echo   Playwright headless — бесплатно
echo   Папка: %%LOCALAPPDATA%%\Jarvis\browsers
echo   Обычно Jarvis ставит браузеры сам при старте.
echo   Этот bat — если автоустановка не сработала.
echo ========================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat — нужен Python venv.
  pause
  exit /b 1
)

call backend\venv\Scripts\activate.bat

echo [pip] playwright...
pip install playwright>=1.49.0 -q
if errorlevel 1 (
  echo [ОШИБКА] pip install playwright
  pause
  exit /b 1
)

set PLAYWRIGHT_BROWSERS_PATH=%LOCALAPPDATA%\Jarvis\browsers
if not exist "%PLAYWRIGHT_BROWSERS_PATH%" mkdir "%PLAYWRIGHT_BROWSERS_PATH%"

echo [playwright] chromium (headless, внутри Jarvis)...
python -m playwright install chromium
if errorlevel 1 (
  echo [ОШИБКА] playwright install chromium
  pause
  exit /b 1
)
python -m playwright install-deps chromium 2>nul

echo.
echo Готово. Перезапустите Jarvis (restart.bat).
pause
