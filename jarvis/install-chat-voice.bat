@echo off

chcp 65001 >nul

title Jarvis — голосовой диалог (STT + TTS)

cd /d "%~dp0"

echo ========================================
echo   Голосовой диалог Jarvis
echo   STT: GigaAM-v3 e2e_rnnt (русская речь)
echo   TTS: Silero v5_ru (локально, Настройки -^> Голос)
echo ========================================
echo.

if not exist "backend\venv\Scripts\python.exe" (
  echo Сначала запустите start.bat
  pause
  exit /b 1
)

echo [1/3] Базовые пакеты (TTS, ffmpeg, whisper-резерв)...
backend\venv\Scripts\python.exe -m pip install edge-tts httpx num2words faster-whisper imageio-ffmpeg hydra-core omegaconf -q
if errorlevel 1 (
  echo [ОШИБКА] pip install базовых пакетов
  pause
  exit /b 1
)

echo [2/3] GigaAM-v3 с GitHub (salute-developers)...
backend\venv\Scripts\python.exe -m pip install --force-reinstall --no-deps "git+https://github.com/salute-developers/GigaAM.git" -q
if errorlevel 1 (
  echo [ОШИБКА] pip install GigaAM
  pause
  exit /b 1
)

echo [3/4] ffmpeg для GigaAM (копия в data/stt/bin)...
cd backend
venv\Scripts\python.exe -c "from modules.voice_stt import _ensure_ffmpeg_shim, _ffmpeg_path; p=_ensure_ffmpeg_shim(); print('ffmpeg:', p); assert p, 'ffmpeg missing'"
if errorlevel 1 (
  echo [ОШИБКА] ffmpeg shim
  cd ..
  pause
  exit /b 1
)

echo [4/4] Проверка STT + TTS...
venv\Scripts\python.exe -c "from modules.voice import get_chat_voice_readiness; from modules.voice_stt import get_stt_status, _load_gigaam; _load_gigaam(); import json; print(json.dumps({'tts': get_chat_voice_readiness(), 'stt': get_stt_status()}, ensure_ascii=False, indent=2))"
cd ..

echo.
echo Готово. В чате включите микрофон и говорите по-русски — wake-word не обязателен.
echo При первом распознавании скачается GigaAM-v3 (~430 МБ).
pause
