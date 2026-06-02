# Jarvis uvicorn: stable start (Python process, not cmd wrapper).
param(
    [switch]$Visible,
    [string]$HostAddr = "127.0.0.1",
    [int]$Port = 8001
)

. "$PSScriptRoot\jarvis-process.ps1"
$Root = Get-JarvisRoot
$Backend = Join-Path $Root "backend"
$Python = Get-JarvisPython
$LogDir = Get-JarvisLogDir
$LogFile = Join-Path $LogDir "server.log"
$PidFile = Join-Path $LogDir "server.pid"

Set-JarvisFreeEnv
if (-not $env:JARVIS_PORT) { $env:JARVIS_PORT = "$Port" }

if (-not (Test-Path $Python)) {
    Write-Host "[ERROR] No Python venv (local or shared jarvis Pro). Run start.bat first." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$pyNote = if ($Python -like "*\jarvis\backend\venv\*") { " (shared jarvis Pro)" } else { "" }
Add-Content -Path $LogFile -Value "`n=== start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') python=$Python$pyNote ===" -Encoding UTF8

function Stop-OldServer {
    if (Test-Path $PidFile) {
        try {
            $oldPid = [int](Get-Content $PidFile -Raw).Trim()
            if ($oldPid -gt 0) {
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
            }
        } catch { }
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
    try {
        Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    } catch { }
    Start-Sleep -Seconds 2
}

Stop-OldServer

$uvicornArgs = @("-m", "uvicorn", "main:app", "--host", $HostAddr, "--port", "$Port")

if ($Visible) {
    $launcher = Join-Path $env:TEMP "jarvis-uvicorn.cmd"
    @(
        "@echo off",
        "cd /d `"$Backend`"",
        "title Jarvis-SERVER",
        "set JARVIS_EDITION=$($env:JARVIS_EDITION)",
        "set JARVIS_PORT=$Port",
        "set JARVIS_SHARED_ROOT=$($env:JARVIS_SHARED_ROOT)",
        "`"$Python`" -m uvicorn main:app --host $HostAddr --port $Port",
        "pause"
    ) | Set-Content -Path $launcher -Encoding ASCII
    Start-Process cmd.exe -ArgumentList @("/k", $launcher)
    Write-Host "Server window opened. Keep it open."
    exit 0
}

# Windows PowerShell 5.1 не поддерживает Start-Process -Environment (только PS 7+).
$serverEnv = @{
    JARVIS_EDITION           = $env:JARVIS_EDITION
    JARVIS_PORT              = "$Port"
    JARVIS_SHARED_ROOT       = $env:JARVIS_SHARED_ROOT
    PLAYWRIGHT_BROWSERS_PATH = $env:PLAYWRIGHT_BROWSERS_PATH
}
foreach ($key in $serverEnv.Keys) {
    $val = $serverEnv[$key]
    if ($null -ne $val -and "$val".Length -gt 0) {
        Set-Item -Path "env:$key" -Value ([string]$val)
    }
}
$startParams = @{
    FilePath         = $Python
    ArgumentList     = $uvicornArgs
    WorkingDirectory = $Backend
    WindowStyle      = 'Hidden'
    PassThru         = $true
}
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $startParams['Environment'] = $serverEnv
}
$p = Start-Process @startParams

if (-not $p) {
    Write-Host "[ERROR] Failed to start Python." -ForegroundColor Red
    exit 1
}

$p.Id | Set-Content -Path $PidFile -Encoding ASCII

$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    if ($p.HasExited) {
        Add-Content -Path $LogFile -Value "Process exited code $($p.ExitCode)" -Encoding UTF8
        Write-Host "[ERROR] Server process exited (code $($p.ExitCode))." -ForegroundColor Red
        Write-Host "Check: $LogFile and import errors in backend\main.py"
        exit 1
    }
    try {
        $r = Invoke-WebRequest -Uri "http://${HostAddr}:${Port}/api/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch { }
}

if (-not $ok) {
    Add-Content -Path $LogFile -Value "Health check failed on port $Port (PID $($p.Id))" -Encoding UTF8
    Write-Host "[ERROR] Server not responding on port $Port." -ForegroundColor Red
    exit 1
}

Write-Host "Jarvis OK  PID $($p.Id)  http://${HostAddr}:${Port}/"
exit 0
