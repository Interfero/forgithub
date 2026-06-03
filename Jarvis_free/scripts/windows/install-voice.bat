@echo off
chcp 65001 >nul
title Jarvis — голос XTTS в приложение
call "%~dp0_root.bat"

echo ========================================
echo   XTTS-v2 — внутри Jarvis
echo   backend\data\tts  +  assets\voice
echo ========================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat
  pause
  exit /b 1
)

call backend\venv\Scripts\activate.bat
python backend\scripts\install_xtts_voice.py
pause
