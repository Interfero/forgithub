param(
    [string]$RepoRoot = "",
    [switch]$Deep,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\disk-budget.ps1")

$root = Get-RepoRoot -Start $RepoRoot
$removed = 0
$freed = [int64]0

function Remove-TreeSafe {
    param([string]$Path, [string]$Label)

    if (-not (Test-Path -LiteralPath $Path)) { return }

    $bytes = Get-DirBytes -Path $Path
    if ($DryRun) {
        Write-Host "[dry-run] would remove $Label ($((Format-Bytes $bytes)))" -ForegroundColor Yellow
        return
    }

    Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Removed $Label — freed $(Format-Bytes $bytes)" -ForegroundColor Green
    script:removed++
    script:freed += $bytes
}

Write-Host "Cleanup workspace under $root" -ForegroundColor Cyan
if ($DryRun) { Write-Host "(dry run — nothing deleted)" -ForegroundColor DarkGray }

$patterns = @(
    @{ Path = Join-Path $root "jarvis\frontend\dist"; Label = "Jarvis frontend dist" },
    @{ Path = Join-Path $root "jarvis\backend\data\models\*.gguf.part"; Label = "partial GGUF downloads"; Glob = $true }
)

foreach ($p in $patterns) {
    if ($p.Glob) {
        Get-ChildItem -Path (Split-Path $p.Path -Parent) -Filter (Split-Path $p.Path -Leaf) -ErrorAction SilentlyContinue |
            ForEach-Object { Remove-TreeSafe -Path $_.FullName -Label $p.Label }
    } else {
        Remove-TreeSafe -Path $p.Path -Label $p.Label
    }
}

Get-ChildItem -Path $root -Recurse -Directory -Filter "__pycache__" -Force -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-TreeSafe -Path $_.FullName -Label "__pycache__" }

Get-ChildItem -Path $root -Recurse -Directory -Filter ".pytest_cache" -Force -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-TreeSafe -Path $_.FullName -Label ".pytest_cache" }

if ($Deep) {
    Remove-TreeSafe -Path (Join-Path $root "jarvis\frontend\node_modules") -Label "Jarvis node_modules"
    Remove-TreeSafe -Path (Join-Path $root "jarvis\backend\venv") -Label "Jarvis venv"
}

Write-Host ""
Write-Host "Cleanup done: $removed items, freed $(Format-Bytes $freed)" -ForegroundColor Cyan
& (Join-Path $PSScriptRoot "disk-status.ps1") -RepoRoot $root
