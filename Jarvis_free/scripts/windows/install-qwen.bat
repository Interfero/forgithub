@echo off
chcp 65001 >nul
title Jarvis — загрузка Qwen 2.5 14B в приложение
call "%~dp0_root.bat"

echo ========================================
echo   Qwen 2.5 14B — ВНУТРЬ приложения Jarvis
echo   Папка: %~dp0backend\data\models
echo   Это часть Jarvis, НЕ отдельная установка на ПК
echo   (не общий каталог Ollama / не «просто на компьютер»)
echo   ~9 ГБ, нужно время и место на диске
echo ========================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat — нужен Python venv.
  pause
  exit /b 1
)

call backend\venv\Scripts\activate.bat

echo [pip] Движок llama-cpp...
pip install llama-cpp-python --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu -q
if errorlevel 1 (
  echo [ОШИБКА] Не удалось установить llama-cpp-python
  pause
  exit /b 1
)

echo.
python backend\scripts\download_qwen_model.py
if errorlevel 1 (
  pause
  exit /b 1
)

echo.
echo Перезапустите Jarvis: restart.bat
pause
