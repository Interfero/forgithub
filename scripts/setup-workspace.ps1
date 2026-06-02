param(
    [string]$RepoRoot = "",
    [switch]$SkipSecurity,
    [switch]$SkipJarvisDeps
)

$ErrorActionPreference = "Stop"
$root = if ($RepoRoot) { (Resolve-Path $RepoRoot).Path } else { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path }

Write-Host "=== forgithub workspace setup ===" -ForegroundColor Cyan
Write-Host "Root: $root"
Write-Host ""

if (-not $SkipSecurity) {
    & (Join-Path $PSScriptRoot "setup-security.ps1")
}

& (Join-Path $PSScriptRoot "disk-status.ps1") -RepoRoot $root

if (-not $SkipJarvisDeps) {
    $jarvisSetup = Join-Path $root "Jarvis_free\scripts\setup-dev.ps1"
    if (Test-Path $jarvisSetup) {
        Write-Host ""
        Write-Host "=== Jarvis Free dev setup ===" -ForegroundColor Cyan
        & $jarvisSetup -RepoRoot $root
    }
}

Write-Host ""
Write-Host "Ready. Next:" -ForegroundColor Green
Write-Host "  cd Jarvis_free"
Write-Host "  copy backend\config\deepseek_free.key.example backend\config\deepseek_free.key"
Write-Host "  .\start.bat"
Write-Host ""
Write-Host "Disk limit: 10 GB — see DISK.md before install-qwen.bat (14B ~9 GB)."
