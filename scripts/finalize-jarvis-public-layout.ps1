# Post-copy layout for public Jarvis_free: launchers, paths, README, gitignore.
param(
    [string]$ProjectRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) "Jarvis_free")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $ProjectRoot).Path

function Set-Utf8File {
    param([string]$Path, [string]$Content)
    $dir = Split-Path $Path -Parent
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    Set-Content -LiteralPath $Path -Value $Content -Encoding UTF8
}

# VBS: project root is two levels up from scripts/launch/
$vbsFiles = @(
    "scripts\launch\run-start.vbs",
    "scripts\launch\run-restart.vbs",
    "scripts\launch\run-serve.vbs"
)
foreach ($rel in $vbsFiles) {
    $path = Join-Path $Root $rel
    if (-not (Test-Path $path)) { continue }
    $c = Get-Content $path -Raw
    if ($c -notmatch 'GetParentFolderName\(fso\.GetParentFolderName') {
        $c = $c -replace 'root = fso\.GetParentFolderName\(WScript\.ScriptFullName\)',
            'root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))'
        Set-Content $path $c -NoNewline
    }
}

$runJarvis = Join-Path $Root "scripts\launch\run-jarvis.vbs"
if (Test-Path $runJarvis) {
    $c = Get-Content $runJarvis -Raw
    $c = $c -replace 'root = fso\.GetParentFolderName\(WScript\.ScriptFullName\)',
        'root = fso.GetParentFolderName(fso.GetParentFolderName(WScript.ScriptFullName))'
    $c = $c -replace '\\run-serve\.vbs', '\scripts\launch\run-serve.vbs'
    Set-Content $runJarvis $c -NoNewline
}

Set-Utf8File (Join-Path $Root "scripts\windows\_root.bat") @'
@echo off
set "JARVIS_ROOT=%~dp0..\.."
cd /d "%JARVIS_ROOT%"
'@

Get-ChildItem (Join-Path $Root "scripts\windows\*.bat") | Where-Object { $_.Name -ne "_root.bat" } | ForEach-Object {
    $c = Get-Content $_.FullName -Raw
    if ($c -match 'cd /d "%~dp0"') {
        $c = $c -replace 'cd /d "%~dp0"', 'call "%~dp0_root.bat"'
        Set-Content $_.FullName $c -NoNewline
    }
}

$replacements = @{
    "scripts\windows\start-quick.bat" = @{
        Old = 'wscript //nologo "%~dp0run-serve.vbs"'
        New = 'wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-serve.vbs"'
    }
    "scripts\windows\start-background.bat" = @{
        Old = 'wscript //nologo "%~dp0run-serve.vbs"'
        New = 'wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-serve.vbs"'
    }
    "scripts\windows\serve.bat" = @{
        Old = 'wscript //nologo "%~dp0run-serve.vbs"'
        New = 'wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-serve.vbs"'
    }
    "scripts\windows\restart-full.bat" = @{
        Old = 'wscript //nologo "%~dp0run-restart.vbs" full'
        New = 'wscript //nologo "%JARVIS_ROOT%\scripts\launch\run-restart.vbs" full'
    }
    "scripts\windows\serve-window.bat" = @{
        Old = 'powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-server.ps1" -Visible'
        New = 'powershell -NoProfile -ExecutionPolicy Bypass -File "%JARVIS_ROOT%\scripts\start-server.ps1" -Visible'
    }
}
foreach ($rel in $replacements.Keys) {
    $path = Join-Path $Root $rel
    if (-not (Test-Path $path)) { continue }
    $c = Get-Content $path -Raw
    $r = $replacements[$rel]
    if ($c -match [regex]::Escape($r.Old)) {
        $c = $c -replace [regex]::Escape($r.Old), $r.New
        Set-Content $path $c -NoNewline
    }
}
$serveWindow = Join-Path $Root "scripts\windows\serve-window.bat"
if (Test-Path $serveWindow) {
    $c = Get-Content $serveWindow -Raw
    $c = $c -replace 'File "%~dp0scripts\\open-jarvis-ui\.ps1"', 'File "%JARVIS_ROOT%\scripts\open-jarvis-ui.ps1"'
    Set-Content $serveWindow $c -NoNewline
}

Set-Utf8File (Join-Path $Root "start.bat") @'
@echo off
REM Запуск Jarvis Free (без окон консоли). Логи: logs\start.log
cd /d "%~dp0"
wscript //nologo "%~dp0scripts\launch\run-start.vbs"
exit /b %ERRORLEVEL%
'@

Set-Utf8File (Join-Path $Root "start.ps1") @'
Set-Location $PSScriptRoot
& wscript.exe //nologo (Join-Path $PSScriptRoot 'scripts\launch\run-start.vbs')
exit $LASTEXITCODE
'@

Set-Utf8File (Join-Path $Root "restart.bat") @'
@echo off
cd /d "%~dp0"
if /i "%~1"=="full" (
  wscript //nologo "%~dp0scripts\launch\run-restart.vbs" full
) else (
  wscript //nologo "%~dp0scripts\launch\run-restart.vbs"
)
exit /b %ERRORLEVEL%
'@

Set-Utf8File (Join-Path $Root "start-dev.bat") @'
@echo off
cd /d "%~dp0"
call "%~dp0scripts\windows\start-dev.bat"
exit /b %ERRORLEVEL%
'@

Set-Utf8File (Join-Path $Root "JARVIS.bat") @'
@echo off
cd /d "%~dp0"
call "%~dp0scripts\windows\start-quick.bat"
exit /b %ERRORLEVEL%
'@

Set-Utf8File (Join-Path $Root "scripts\restart.ps1") @'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
& wscript.exe //nologo (Join-Path $Root 'scripts\launch\run-restart.vbs')
exit $LASTEXITCODE
'@

Set-Utf8File (Join-Path $Root "scripts\windows\start-dev.bat") @'
@echo off
chcp 65001 >nul
title Jarvis Free — режим разработки
call "%~dp0_root.bat"

echo Режим разработки: Backend :8001 + Vite :5173
echo Для обычного использования: start.bat в корне Jarvis_free
echo.

call "%~dp0stop-ports.bat"

if not exist "frontend\node_modules" (
  cd frontend
  call npm install
  cd ..\
)

call backend\venv\Scripts\activate.bat 2>nul

start "Jarvis Backend" cmd /k "cd /d %JARVIS_ROOT%backend && call venv\Scripts\activate.bat && set JARVIS_EDITION=free&& set JARVIS_PORT=8001&& uvicorn main:app --reload --host 127.0.0.1 --port 8001"
ping 127.0.0.1 -n 4 >nul
start "Jarvis Frontend" cmd /k "cd /d %JARVIS_ROOT%frontend && npm run dev"

set /a N=0
:wait5173
ping 127.0.0.1 -n 2 >nul
netstat -ano | findstr "LISTENING" | findstr ":5173 " >nul 2>&1
if not errorlevel 1 goto ok
set /a N+=1
if %N% LSS 20 goto wait5173
echo Frontend не запустился
pause
exit /b 1
:ok
start "" "http://127.0.0.1:5173/"
pause
'@

Set-Utf8File (Join-Path $Root "scripts\windows\install-qwen-safe.bat") @'
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
'@

$oldSafe = Join-Path $Root "scripts\install-qwen-safe.bat"
if (Test-Path $oldSafe) { Remove-Item $oldSafe -Force }

Set-Utf8File (Join-Path $Root "packaging\build-exe.bat") @'
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
cd ..\

cd backend
call venv\Scripts\python.exe -c "from modules.memory_store import _ensure_dirs; _ensure_dirs()"
cd ..\

call backend\venv\Scripts\pip.exe install pyinstaller -q
call backend\venv\Scripts\pyinstaller.exe packaging\jarvis.spec --noconfirm
if errorlevel 1 ( pause & exit /b 1 )

echo Готово: dist\Jarvis.exe
pause
'@

$spec = Join-Path $Root "packaging\jarvis.spec"
if (Test-Path $spec) {
    $c = Get-Content $spec -Raw
    if ($c -match 'root = Path\(SPECPATH\)\s*\nbackend') {
        $c = $c -replace 'root = Path\(SPECPATH\)\r?\nbackend', 'root = Path(SPECPATH).parent`r`nbackend'
        Set-Content $spec $c -NoNewline
    }
    if ($c -match 'root = Path\(SPECPATH\)\s*\r?\nbackend' -and $c -notmatch 'Path\(SPECPATH\)\.parent') {
        $c = $c -replace 'root = Path\(SPECPATH\)', 'root = Path(SPECPATH).parent'
        Set-Content $spec $c -NoNewline
    }
}

$vite = Join-Path $Root "frontend\vite.config.ts"
if (Test-Path $vite) {
    $c = Get-Content $vite -Raw
    $c = $c -replace "../../jarvis/jarvis\.png", "../assets/images/jarvis.png"
    $c = $c -replace '\.\./jarvis\.png', '../assets/images/jarvis.png'
    Set-Content $vite $c -NoNewline
}

$tsconfig = Join-Path $Root "frontend\tsconfig.app.json"
if (Test-Path $tsconfig) {
    $c = Get-Content $tsconfig -Raw
    $c = $c -replace '"@jarvis-base": \["\.\./jarvis\.png"\]', '"@jarvis-base": ["../assets/images/jarvis.png"]'
    Set-Content $tsconfig $c -NoNewline
}

$fixPng = Join-Path $Root "frontend\scripts\fix-jarvis-png.mjs"
if (Test-Path $fixPng) {
    $c = Get-Content $fixPng -Raw
    $c = $c -replace "path\.join\(root, 'jarvis\.png'\)", "path.join(root, 'assets/images/jarvis.png')"
    Set-Content $fixPng $c -NoNewline
}

Set-Utf8File (Join-Path $Root "README.md") @'
# Jarvis Free

Бесплатная редакция Jarvis. Публичная копия в репозитории [forgithub](https://github.com/Interfero/forgithub).

> Не коммитьте ключи API и личные чаты. См. [SECURITY.md](../docs/SECURITY.md) и [DISK.md](../docs/DISK.md).

## Структура (внутри Jarvis_free)

```
Jarvis_free/
├── README.md, .gitignore, Dockerfile, docker-compose.yml
├── start.bat, restart.bat, start-dev.bat   ← запуск
├── backend/
├── frontend/
├── scripts/launch/      ← VBS
├── scripts/windows/     ← install-*, serve, …
├── packaging/           ← build-exe.bat
├── assets/images/
├── docs/
└── var/                 ← временные файлы (не в git)
```

## Запуск

1. Ключ: `backend\config\deepseek_free.key.example` → `deepseek_free.key`
2. `start.bat` → http://127.0.0.1:8001/

## Утилиты

| Задача | Путь |
|--------|------|
| Qwen 14B (проверка 10 GB) | `scripts\windows\install-qwen-safe.bat` |
| Сборка EXE | `packaging\build-exe.bat` |
| Dev-режим | `start-dev.bat` |

Данные пользователя: `%LOCALAPPDATA%\Jarvis_free\data`
'@

Set-Utf8File (Join-Path $Root ".gitignore") @'
backend/venv/
backend/config/deepseek_free.key
backend/data/settings.json
backend/data/chats.json
backend/data/server_runtime.json
backend/data/*.db
backend/data/models/*.gguf
backend/data/models/*.gguf.part
backend/data/telegram/config.json
backend/data/avito/config.json
backend/data/uploads/
backend/data/generated/
backend/data/_tmp_*/
backend/data/memory/conscious/Память_сессий.md
frontend/node_modules/
frontend/dist/
logs/
var/
__pycache__/
*.pyc
.env
.env.*
!.env.example
dist/
build/
*.exe
'@

Write-Host "Public layout finalized: $Root" -ForegroundColor Green
