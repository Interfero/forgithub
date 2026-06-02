$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent

Push-Location $repoRoot
try {
    git config core.hooksPath .githooks
    Write-Host "Git hooks включены: .githooks" -ForegroundColor Green
    Write-Host "Pre-commit будет запускать scripts\check-secrets.ps1" -ForegroundColor Green
} finally {
    Pop-Location
}
