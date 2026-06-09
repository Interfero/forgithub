# Jarvis uvicorn: stable start (Python process, not cmd wrapper).
param(
    [switch]$Visible,
    [string]$HostAddr = "127.0.0.1",
    [int]$Port = 8000
)

. "$PSScriptRoot\jarvis-process.ps1"
$Root = Get-JarvisRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend "venv\Scripts\python.exe"
$LogDir = Get-JarvisLogDir
$LogFile = Join-Path $LogDir "server.log"
$PidFile = Join-Path $LogDir "server.pid"

if (-not $env:JARVIS_PORT) { $env:JARVIS_PORT = "$Port" }

if (-not (Test-Path $Python)) {
    Write-Host "[ERROR] No backend\venv. Run start.bat first." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Add-Content -Path $LogFile -Value "`n=== start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -Encoding UTF8

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
        "`"$Python`" -m uvicorn main:app --host $HostAddr --port $Port",
        "pause"
    ) | Set-Content -Path $launcher -Encoding ASCII
    Start-Process cmd.exe -ArgumentList @("/k", $launcher)
    Write-Host "Server window opened. Keep it open."
    exit 0
}

$p = Start-Process `
    -FilePath $Python `
    -ArgumentList $uvicornArgs `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -PassThru

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
