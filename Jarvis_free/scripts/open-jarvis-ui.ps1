# Открыть UI Jarvis во встроенном Chrome (не браузер Windows по умолчанию).
param(
    [string]$Url = "http://127.0.0.1:8001/"
)

. "$PSScriptRoot\jarvis-process.ps1"
$Root = Get-JarvisRoot
$venvPy = Get-JarvisPython
if (-not (Test-Path $venvPy)) {
    Write-Host '[ERROR] Нет Python venv — сначала start.bat' -ForegroundColor Red
    exit 1
}

$backend = Join-Path $Root 'backend'
Push-Location $backend
try {
    $code = & $venvPy -c @"
from modules.jarvis_browsers import open_jarvis_ui_in_chrome
ok, msg = open_jarvis_ui_in_chrome('$($Url -replace "'","''")')
print(msg)
raise SystemExit(0 if ok else 1)
"@ 2>&1
} finally {
    Pop-Location
}
if ($LASTEXITCODE -ne 0) {
    Write-Host $code -ForegroundColor Yellow
    exit 1
}
Write-Host "Jarvis UI: $code"
exit 0
