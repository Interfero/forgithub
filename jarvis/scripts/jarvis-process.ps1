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
    foreach ($port in @(8000, 5173)) {
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
    Start-Process 'http://127.0.0.1:8000/' | Out-Null
}
