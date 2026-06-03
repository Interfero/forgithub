# Reorganize Jarvis_free: project in subfolders, repo entry points at project root.
param(
    [string]$ProjectRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) "Jarvis_free")
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $ProjectRoot).Path

$dirs = @("scripts\launch", "scripts\windows", "assets\images", "packaging", "var")
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root $d) | Out-Null
}

$moves = @(
    @{ From = "run-start.vbs"; To = "scripts\launch\run-start.vbs" },
    @{ From = "run-restart.vbs"; To = "scripts\launch\run-restart.vbs" },
    @{ From = "run-serve.vbs"; To = "scripts\launch\run-serve.vbs" },
    @{ From = "run-jarvis.vbs"; To = "scripts\launch\run-jarvis.vbs" },
    @{ From = "install-browsers.bat"; To = "scripts\windows\install-browsers.bat" },
    @{ From = "install-chromium.bat"; To = "scripts\windows\install-chromium.bat" },
    @{ From = "install-google-chrome.bat"; To = "scripts\windows\install-google-chrome.bat" },
    @{ From = "install-qwen.bat"; To = "scripts\windows\install-qwen.bat" },
    @{ From = "install-voice.bat"; To = "scripts\windows\install-voice.bat" },
    @{ From = "serve.bat"; To = "scripts\windows\serve.bat" },
    @{ From = "serve-window.bat"; To = "scripts\windows\serve-window.bat" },
    @{ From = "show-log.bat"; To = "scripts\windows\show-log.bat" },
    @{ From = "start-background.bat"; To = "scripts\windows\start-background.bat" },
    @{ From = "start-quick.bat"; To = "scripts\windows\start-quick.bat" },
    @{ From = "stop-ports.bat"; To = "scripts\windows\stop-ports.bat" },
    @{ From = "wait-server.bat"; To = "scripts\windows\wait-server.bat" },
    @{ From = "recreate_venv_py311.bat"; To = "scripts\windows\recreate_venv_py311.bat" },
    @{ From = "restart-full.bat"; To = "scripts\windows\restart-full.bat" },
    @{ From = "build-exe.bat"; To = "packaging\build-exe.bat" },
    @{ From = "jarvis.spec"; To = "packaging\jarvis.spec" },
    @{ From = "jarvis.png"; To = "assets\images\jarvis.png" },
    @{ From = "e5a5eabd-e0ea-4a7c-9f02-3bf71aa68e42_b7fdfd41-d45c-4ba2-b8c6-f0cc7d01303c.png"; To = "assets\images\e5a5eabd-e0ea-4a7c-9f02-3bf71aa68e42_b7fdfd41-d45c-4ba2-b8c6-f0cc7d01303c.png" },
    @{ From = "ollama_reg.txt"; To = "var\ollama_reg.txt" },
    @{ From = "qwen_now.json"; To = "var\qwen_now.json" },
    @{ From = "qwen_status.txt"; To = "var\qwen_status.txt" },
    @{ From = "_png_check.txt"; To = "var\_png_check.txt" },
    @{ From = "restart.ps1"; To = "scripts\restart.ps1" }
)

foreach ($m in $moves) {
    $src = Join-Path $Root $m.From
    $dst = Join-Path $Root $m.To
    if (Test-Path $src) {
        if (Test-Path $dst) { Remove-Item -LiteralPath $dst -Force }
        Move-Item -LiteralPath $src -Destination $dst -Force
    }
}

Get-ChildItem -LiteralPath $Root -Filter "*.txt" -File | Where-Object { $_.Name -match "ЗАПУСК" } | ForEach-Object {
    $dst = Join-Path $Root "docs\$($_.Name)"
    if (-not (Test-Path $dst)) { Move-Item $_.FullName $dst -Force }
}

Write-Host "Jarvis_free layout OK: $Root" -ForegroundColor Green
