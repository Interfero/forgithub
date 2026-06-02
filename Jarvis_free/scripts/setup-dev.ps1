param(
    [string]$RepoRoot = "",
    [switch]$SkipNpm,
    [switch]$SkipVenv
)

$ErrorActionPreference = "Stop"
$jarvisRoot = $PSScriptRoot | Split-Path -Parent
if ($RepoRoot) {
    $forgithubRoot = (Resolve-Path $RepoRoot).Path
} else {
    $forgithubRoot = (Resolve-Path (Join-Path $jarvisRoot "..")).Path
}

$guard = Join-Path $forgithubRoot "scripts\guard-disk.ps1"
$diskStatus = Join-Path $forgithubRoot "scripts\disk-status.ps1"

Write-Host "Jarvis Free — dev setup" -ForegroundColor Cyan
Write-Host "Jarvis: $jarvisRoot"

if (Test-Path $guard) {
    & $guard -RepoRoot $forgithubRoot -RequiredBytes 800000000
    if ($LASTEXITCODE -ne 0) {
        throw "Not enough disk budget (~800 MB needed for venv+npm). Run cleanup or see DISK.md"
    }
}

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

if (-not $SkipVenv) {
    $venvPy = Join-Path $jarvisRoot "backend\venv\Scripts\python.exe"
    if (-not (Test-Path $venvPy)) {
        if (-not (Test-Command "py")) {
            throw "Python not found. Install Python 3.11+ and retry."
        }
        Write-Host "Creating Python venv..." -ForegroundColor Yellow
        Push-Location (Join-Path $jarvisRoot "backend")
        try {
            py -3.11 -m venv venv 2>$null
            if (-not (Test-Path "venv\Scripts\python.exe")) {
                py -3 -m venv venv
            }
            & ".\venv\Scripts\python.exe" -m pip install --upgrade pip wheel
            & ".\venv\Scripts\pip.exe" install -r requirements.txt
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "Python venv OK" -ForegroundColor Green
    }
}

if (-not $SkipNpm) {
    $nodeModules = Join-Path $jarvisRoot "frontend\node_modules"
    if (-not (Test-Path $nodeModules)) {
        if (-not (Test-Command "npm")) {
            Write-Warning "npm not found — skip frontend deps. Install Node.js LTS."
        } else {
            Write-Host "npm install (frontend)..." -ForegroundColor Yellow
            Push-Location (Join-Path $jarvisRoot "frontend")
            try {
                npm ci 2>$null
                if ($LASTEXITCODE -ne 0) { npm install }
            } finally {
                Pop-Location
            }
        }
    } else {
        Write-Host "frontend node_modules OK" -ForegroundColor Green
    }
}

$keyExample = Join-Path $jarvisRoot "backend\config\deepseek_free.key.example"
$keyReal = Join-Path $jarvisRoot "backend\config\deepseek_free.key"
if ((Test-Path $keyExample) -and -not (Test-Path $keyReal)) {
    Copy-Item $keyExample $keyReal
    Write-Host "Created deepseek_free.key from example — paste your sk- key before run." -ForegroundColor Yellow
}

if (Test-Path $diskStatus) {
    & $diskStatus -RepoRoot $forgithubRoot
}

Write-Host "Jarvis dev setup done." -ForegroundColor Green
