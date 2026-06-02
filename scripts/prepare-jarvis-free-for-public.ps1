param(
    [string]$SourcePath = "C:\Users\420\Documents\develop\Jarvis_free",
    [string]$TargetPath = "C:\Users\420\Documents\develop\forgithub\Jarvis_free"
)

$ErrorActionPreference = "Stop"
$source = Resolve-Path $SourcePath

$excludeDirs = @(
    "node_modules", "venv", ".git", "dist", "build", "__pycache__",
    ".venv", "coverage", ".idea", ".vscode", "logs",
    "uploads", "generated", "files", "mail", "voice_samples",
    "_tmp_rbw", "_tmp_tg", "models", "cache"
)

$excludeFiles = @(
    "settings.json", "chats.json", "server_runtime.json", "jarvis_free_updates.json",
    "accountant.db", "jarvis.db", "inbox.db",
    "deepseek_free.key", "user_base.ogg", "xtts_state.json",
    ".env", ".env.local", ".env.production"
)

$excludeExtensions = @(
    ".gguf", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx",
    ".zip", ".rar", ".7z", ".exe"
)

$excludeRelativePaths = @(
    "backend\data\telegram\config.json",
    "backend\data\avito\config.json",
    "backend\data\telegram_analyst\config.json",
    "backend\data\memory\conscious\Память_сессий.md"
)

function Should-SkipItem {
    param([string]$RelativePath, [bool]$IsDirectory)

    $norm = $RelativePath -replace '/', '\'
    $parts = $norm -split '\\'

    foreach ($part in $parts) {
        if ($excludeDirs -contains $part) { return $true }
    }

    foreach ($blocked in $excludeRelativePaths) {
        if ($norm -ieq $blocked) { return $true }
    }

    if ($IsDirectory) { return $false }

    $leaf = Split-Path $norm -Leaf
    if ($excludeFiles -contains $leaf) { return $true }
    if ($leaf -like ".env.*" -and $leaf -notlike "*.example") { return $true }

    $ext = [System.IO.Path]::GetExtension($leaf).ToLowerInvariant()
    if ($excludeExtensions -contains $ext) { return $true }
    if ($ext -eq ".key" -and $leaf -notlike "*.example") { return $true }

    return $false
}

if (Test-Path $TargetPath) {
    Remove-Item -LiteralPath $TargetPath -Recurse -Force
}

Write-Host "Copying Jarvis Free (public-safe): $source" -ForegroundColor Cyan

Get-ChildItem -Path $source -Recurse -Force | ForEach-Object {
    $rel = $_.FullName.Substring($source.Path.Length).TrimStart('\', '/')
    if ([string]::IsNullOrWhiteSpace($rel)) { return }

    if (Should-SkipItem -RelativePath $rel -IsDirectory:$_.PSIsContainer) {
        return
    }

    $dest = Join-Path $TargetPath $rel
    if ($_.PSIsContainer) {
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
    } else {
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -LiteralPath $_.FullName -Destination $dest -Force
    }
}

# Example configs (no secrets)
@(
    @{
        Path = "backend\data\settings.json.example"
        Content = @'
{
  "provider": "deepseek",
  "default_model": "DeepSeek-V4-Flash",
  "openai_key": "",
  "openai_model": "gpt-5.5-instant",
  "anthropic_key": "",
  "deepseek_key": "",
  "perplexity_key": "",
  "perplexity_model": "sonar",
  "xai_key": "",
  "xai_model": "grok-4.20",
  "nanobanana_key": "",
  "qwen_ram_enabled": true,
  "deepseek_active": true,
  "openai_active": false,
  "perplexity_active": false,
  "xai_active": false,
  "nanobanana_active": false,
  "xtts_active": true
}
'@
    },
    @{
        Path = "backend\data\chats.json.example"
        Content = '{"chats":[]}'
    },
    @{
        Path = "backend\data\telegram\config.example.json"
        Content = @'
{
  "bot_token": "",
  "blocklist_ids": [],
  "telegram_proxy": "direct",
  "mother_core_enabled": false
}
'@
    },
    @{
        Path = "backend\data\avito\config.example.json"
        Content = @'
{
  "client_id": "",
  "client_secret": "",
  "user_id": "",
  "sync_enabled": false,
  "last_sync_date": ""
}
'@
    },
    @{
        Path = "backend\data\models\README.md"
        Content = @'
# Models (not in git)

Large GGUF files are not stored in this public repository.

Download Qwen models separately or reuse models from a local Jarvis Pro install:
`../jarvis/backend/data/models` (see root README).
'@
    }
) | ForEach-Object {
    $full = Join-Path $TargetPath $_.Path
    $dir = Split-Path $full -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Set-Content -LiteralPath $full -Value $_.Content -Encoding UTF8
}

$publicReadme = @'
# Jarvis Free

Бесплатная редакция Jarvis: весь функционал в одном чате, без экрана-аватара и 2D-игры.

> **Публичный репозиторий.** Не коммитьте `.env`, ключи API, токены Telegram/Avito и личные чаты.
> Перед сборкой EXE см. [SECURITY.md](../docs/SECURITY.md) в корне репозитория.

## Первый запуск

1. Python 3.11+ и Node.js для фронта.
2. Ключ DeepSeek: скопируйте `backend/config/deepseek_free.key.example` → `backend/config/deepseek_free.key` и вставьте ключ (`sk-…`).
3. Установите зависимости backend и frontend (см. `backend/requirements.txt`, `frontend/package.json`).
4. Запустите `start.bat` или `start.ps1`.
5. Откройте http://127.0.0.1:8001/

## Данные пользователя

Free хранит чаты и настройки в `%LOCALAPPDATA%\Jarvis_free\data` (не в git).

Шаблоны: `backend/data/*.example` и `backend/data/*/config.example.json`.

## Модели Qwen (~9 ГБ)

Не включены в git. Положите GGUF в `backend/data/models/` или используйте общую папку Jarvis Pro (см. `backend/modules/app_paths.py`).

## Сборка EXE

Только после `..\scripts\check-secrets.ps1`. Арtefacts (`dist/`, `*.exe`) не публикуются в GitHub.

## Порт

Jarvis Free: **8001** (полная версия Pro обычно **8000**).
'@

Set-Content -LiteralPath (Join-Path $TargetPath "README.md") -Value $publicReadme -Encoding UTF8

$jarvisGitignore = @'
backend/venv/
backend/config/deepseek_free.key
backend/data/deepseek_free.key
backend/data/settings.json
backend/data/chats.json
backend/data/server_runtime.json
backend/data/*.db
backend/data/models/*.gguf
backend/data/models/*.bin
backend/data/telegram/config.json
backend/data/avito/config.json
backend/data/telegram_analyst/
backend/data/uploads/
backend/data/generated/
backend/data/_tmp_*/
backend/data/memory/conscious/Память_сессий.md
frontend/node_modules/
frontend/dist/
logs/
__pycache__/
*.pyc
.env
.env.*
!.env.example
'@

Set-Content -LiteralPath (Join-Path $TargetPath ".gitignore") -Value $jarvisGitignore -Encoding UTF8

Write-Host "Done: $TargetPath" -ForegroundColor Green
