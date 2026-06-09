param(
    [string]$SourcePath = "C:\Users\420\Documents\develop\jarvis",
    [string]$TargetPath = ""
)

$ErrorActionPreference = "Stop"
$source = Resolve-Path $SourcePath
$repoRoot = Split-Path $PSScriptRoot -Parent
if (-not $TargetPath) {
    $TargetPath = Join-Path $repoRoot "jarvis"
}

$excludeDirs = @(
    "node_modules", "venv", ".git", "dist", "build", "__pycache__",
    ".venv", "coverage", ".idea", ".vscode", "logs",
    "uploads", "generated", "files", "mail", "voice_samples",
    "_tmp_rbw", "_tmp_tg", "models", "cache", "silero"
)

$excludeFiles = @(
    "settings.json", "chats.json", "server_runtime.json",
    "jarvis_free_updates.json", "jarvis_component_updates.json",
    "accountant.db", "jarvis.db", "inbox.db",
    "deepseek_free.key", "huggingface.key", "user_base.ogg", "xtts_state.json",
    "ollama_reg.txt", "qwen_now.json", "qwen_status.txt", "_png_check.txt",
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
    "backend\data\memory\conscious\Память_сессий.md",
    "backend\data\memory\unconscious\Стереотипы.txt"
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

Write-Host "Copying Jarvis (public-safe): $source" -ForegroundColor Cyan

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
  "deepseek_active": false,
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

Run `start.bat` once — Jarvis checks and downloads missing components.
Or use `install-qwen.bat` for local Qwen (needs disk space; see repo docs/DISK.md).
'@
    }
) | ForEach-Object {
    $full = Join-Path $TargetPath $_.Path
    $dir = Split-Path $full -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Set-Content -LiteralPath $full -Value $_.Content -Encoding UTF8
}

Write-Host ""
Write-Host "Done: $TargetPath" -ForegroundColor Green
Write-Host "Next:" -ForegroundColor Cyan
Write-Host "  .\scripts\check-secrets.ps1 -Path jarvis"
Write-Host "  git add jarvis; git commit; git push"
