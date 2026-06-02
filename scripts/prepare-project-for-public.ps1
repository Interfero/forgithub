param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$TargetName
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
$source = Resolve-Path $SourcePath
$target = Join-Path $repoRoot $TargetName

$excludeDirs = @(
    "node_modules", ".git", "dist", "build", ".venv", "venv",
    "__pycache__", ".idea", ".vscode", "coverage", ".turbo"
)

$excludeFiles = @(
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
    "credentials.json", "service-account.json", "google-services.json",
    "secrets.json", "Thumbs.db", ".DS_Store"
)

$excludeExtensions = @(".pem", ".key", ".p12", ".pfx", ".zip", ".rar", ".7z", ".exe")

if (Test-Path $target) {
    throw "Папка уже существует: $target. Выберите другое имя или удалите её вручную."
}

Write-Host "Копирование: $source -> $target" -ForegroundColor Cyan

function Should-Skip {
    param([string]$RelativePath, [bool]$IsDirectory)

    $parts = $RelativePath -split '[\\/]'
    foreach ($part in $parts) {
        if ($excludeDirs -contains $part) { return $true }
    }

    if ($IsDirectory) { return $false }

    $leaf = Split-Path $RelativePath -Leaf
    if ($excludeFiles -contains $leaf) { return $true }
    if ($leaf -like ".env.*" -and $leaf -notlike "*.example") { return $true }

    $ext = [System.IO.Path]::GetExtension($leaf).ToLowerInvariant()
    if ($excludeExtensions -contains $ext) { return $true }

    return $false
}

New-Item -ItemType Directory -Path $target | Out-Null

Get-ChildItem -Path $source -Recurse -Force | ForEach-Object {
    $rel = $_.FullName.Substring($source.Path.Length).TrimStart('\', '/')
    if ([string]::IsNullOrWhiteSpace($rel)) { return }

    if (Should-Skip -RelativePath $rel -IsDirectory:$_.PSIsContainer) {
        Write-Host "  skip: $rel" -ForegroundColor DarkGray
        return
    }

    $dest = Join-Path $target $rel
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

Write-Host ""
Write-Host "Копирование завершено." -ForegroundColor Green
Write-Host "Дальше:" -ForegroundColor Cyan
Write-Host "  1. Проверьте .env.example — только плейсхолдеры, без реальных значений."
Write-Host "  2. Запустите: .\scripts\check-secrets.ps1 -Path `"$TargetName`""
Write-Host "  3. Только после OK — git add / commit / push."
