# Общие функции запуска без окон консоли (Windows).
$script:JarvisRoot = Split-Path $PSScriptRoot -Parent

function Get-JarvisRoot {
    return $script:JarvisRoot
}

function Get-JarvisLogDir {
    $d = Join-Path $script:JarvisRoot 'logs'
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    return $d
}

function Get-JarvisPython {
    # Локальный backend\venv или общий venv из jarvis (Pro).
    $local = Join-Path $script:JarvisRoot 'backend\venv\Scripts\python.exe'
    if (Test-Path $local) { return $local }
    $proRoot = Join-Path (Split-Path $script:JarvisRoot -Parent) 'jarvis'
    $shared = Join-Path $proRoot 'backend\venv\Scripts\python.exe'
    if (Test-Path $shared) { return $shared }
    return $local
}

function Set-JarvisFreeEnv {
    if (-not $env:JARVIS_EDITION) { $env:JARVIS_EDITION = 'free' }
    if (-not $env:JARVIS_PORT) { $env:JARVIS_PORT = '8001' }
    $proRoot = Join-Path (Split-Path $script:JarvisRoot -Parent) 'jarvis'
    if ((Test-Path $proRoot) -and -not $env:JARVIS_SHARED_ROOT) {
        $env:JARVIS_SHARED_ROOT = $proRoot
    }
    $pwBrowsers = Join-Path $env:LOCALAPPDATA 'Jarvis\browsers'
    if (-not $env:PLAYWRIGHT_BROWSERS_PATH) {
        $env:PLAYWRIGHT_BROWSERS_PATH = $pwBrowsers
    }
}

function Write-JarvisLog {
    param(
        [string]$LogFile,
        [string]$Message
    )
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $Message"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Show-JarvisError {
    param([string]$Text)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show(
            $Text,
            'Jarvis',
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
    } catch {
        Write-Host $Text
    }
}

function Invoke-HiddenCommand {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $script:JarvisRoot,
        [string]$StdOutFile = $null,
        [string]$StdErrFile = $null
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    if ($ArgumentList.Count -gt 0) {
        $psi.Arguments = ($ArgumentList | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '""') + '"' } else { $_ }
        }) -join ' '
    }
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false

    if ($StdOutFile) {
        $psi.RedirectStandardOutput = $true
    }
    if ($StdErrFile) {
        $psi.RedirectStandardError = $true
    }

    $p = [System.Diagnostics.Process]::Start($psi)
    if ($StdOutFile) {
        $out = $p.StandardOutput.ReadToEnd()
        Set-Content -Path $StdOutFile -Value $out -Encoding UTF8
    }
    if ($StdErrFile) {
        $err = $p.StandardError.ReadToEnd()
        Set-Content -Path $StdErrFile -Value $err -Encoding UTF8
    }
    $p.WaitForExit()
    return $p.ExitCode
}

function Invoke-Npm {
    param(
        [string[]]$NpmArgs,
        [string]$WorkingDirectory,
        [string]$LogFile = $null
    )

    $npm = (Get-Command npm.cmd -ErrorAction Stop).Source
    if ($LogFile) {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $npm
        $psi.Arguments = ($NpmArgs | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '""') + '"' } else { $_ }
        }) -join ' '
        $psi.WorkingDirectory = $WorkingDirectory
        $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
        $psi.CreateNoWindow = $true
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $p = [System.Diagnostics.Process]::Start($psi)
        $out = $p.StandardOutput.ReadToEnd()
        $err = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        Set-Content -Path $LogFile -Value ($out + $err) -Encoding UTF8
        return $p.ExitCode
    }
    return Invoke-HiddenCommand -FilePath $npm -ArgumentList $NpmArgs -WorkingDirectory $WorkingDirectory
}

function Stop-JarvisPorts {
    $logDir = Get-JarvisLogDir
    $pidFile = Join-Path $logDir 'server.pid'
    if (Test-Path $pidFile) {
        try {
            $oldPid = [int](Get-Content $pidFile -Raw).Trim()
            if ($oldPid -gt 0) {
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
            }
        } catch { }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    foreach ($port in @(8000, 8001, 5173, 5174)) {
        try {
            Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue |
                ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
        } catch { }
    }
    Start-Sleep -Seconds 2
}

function Start-JarvisBrowser {
    # По умолчанию браузер не открываем. Явно: set JARVIS_OPEN_BROWSER=1
    if ($env:JARVIS_OPEN_BROWSER -ne '1') { return }
    $port = if ($env:JARVIS_PORT) { $env:JARVIS_PORT } else { '8001' }
    Start-Process "http://127.0.0.1:$port/" | Out-Null
}
