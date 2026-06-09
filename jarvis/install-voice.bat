@echo off
chcp 65001 >nul
title Jarvis — Silero TTS
cd /d "%~dp0"
echo.
echo   Silero TTS v5_ru — локальная озвучка (Настройки -^> Голос)
echo   Старый XTTS/Coqui удаляется автоматически при старте Jarvis.
echo.
backend\venv\Scripts\python.exe -c "from modules import silero_tts; print(silero_tts.start_install())"
pause
