@echo off
chcp 65001 >nul
title Jarvis — Qwen download (disk budget 10 GB)
call "%~dp0_root.bat"

echo ========================================
echo   Qwen 14B ~9 GB — проверка лимита 10 GB
echo ========================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%JARVIS_ROOT%\..\..\scripts\guard-disk.ps1" -RequiredBytes 9663676416
if errorlevel 1 (
  echo.
  echo [STOP] Qwen 14B does not fit 10 GB budget.
  echo See docs\DISK.md in forgithub repo root.
  pause
  exit /b 1
)

call "%~dp0install-qwen.bat"
