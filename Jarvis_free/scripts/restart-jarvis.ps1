# Перезапуск Jarvis без окон консоли (вызывается из run-restart.vbs).
param([switch]$Full)

. "$PSScriptRoot\jarvis-process.ps1"
$Root = Get-JarvisRoot
Set-Location $Root

$env:JARVIS_EDITION = 'free'
$env:JARVIS_PORT = '8001'
$proRoot = Join-Path (Split-Path $Root -Parent) 'jarvis'
if (Test-Path $proRoot) {
    $env:JARVIS_SHARED_ROOT = $proRoot
}

$logDir = Get-JarvisLogDir
$logFile = Join-Path $logDir 'restart.log'
Write-JarvisLog $logFile '=== restart ==='

try {
    Stop-JarvisPorts

    $frontend = Join-Path $Root 'frontend'
    if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
        Write-JarvisLog $logFile 'npm install...'
        $code = Invoke-Npm -NpmArgs @('install') -WorkingDirectory $frontend -LogFile (Join-Path $logDir 'frontend-install.log')
        if ($code -ne 0) {
            throw "npm install failed (code $code). See logs\frontend-install.log"
        }
    }

    $buildLog = Join-Path $logDir 'frontend-build.log'
    Write-JarvisLog $logFile 'npm run build...'
    $code = Invoke-Npm -NpmArgs @('run', 'build') -WorkingDirectory $frontend -LogFile $buildLog
    if ($code -ne 0) {
        throw "npm run build failed (code $code). See logs\frontend-build.log"
    }

    & "$PSScriptRoot\start-server.ps1"
    if ($LASTEXITCODE -ne 0) {
        throw 'Server did not start. See logs\server.log'
    }

    Write-JarvisLog $logFile 'OK (браузер не открывается; JARVIS_OPEN_BROWSER=1 — открыть)'
    exit 0
} catch {
    Write-JarvisLog $logFile "ERROR: $($_.Exception.Message)"
    Show-JarvisError $_.Exception.Message
    exit 1
}
