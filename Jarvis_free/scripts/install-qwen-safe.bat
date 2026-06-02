@echo off
chcp 65001 >nul
title Jarvis — Qwen download (disk budget 10 GB)
cd /d "%~dp0.."

echo ========================================
echo   Qwen 14B ~9 GB — проверка лимита 10 GB
echo   При нехватке места используйте DeepSeek API
echo   (backend\config\deepseek_free.key)
echo ========================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\..\scripts\guard-disk.ps1" -RequiredBytes 9663676416
if errorlevel 1 (
  echo.
  echo [СТОП] Qwen 14B не влезет в бюджет 10 GB.
  echo См. docs\DISK.md — профиль apiOnly или cleanup-workspace.ps1
  pause
  exit /b 1
)

call "%~dp0..\install-qwen.bat"
