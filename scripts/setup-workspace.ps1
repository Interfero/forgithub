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

Write-Host ""
Write-Host "Ready. Next:" -ForegroundColor Green
Write-Host "  cd jarvis"
Write-Host "  .\start.bat          # first run: installs deps, builds UI, opens browser"
Write-Host "  .\start-quick.bat    # daily use"
Write-Host ""
Write-Host "Disk limit: 10 GB — see docs/DISK.md before install-qwen.bat (14B ~9 GB)."
