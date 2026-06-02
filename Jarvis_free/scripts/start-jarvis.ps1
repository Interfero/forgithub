# Первый/полный запуск Jarvis Free без окон консоли (run-start.vbs).
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
$logFile = Join-Path $logDir 'start.log'
Write-JarvisLog $logFile '=== start ==='

function Resolve-PythonCmd {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($ver in @('-3.11', '-3.10')) {
            $code = Invoke-HiddenCommand -FilePath 'py' -ArgumentList @($ver, '-c', 'import sys')
            if ($code -eq 0) { return @('py', $ver) }
        }
    }
    return @('python')
}

try {
    Stop-JarvisPorts

    $frontend = Join-Path $Root 'frontend'
    if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
        Write-JarvisLog $logFile 'npm install (frontend)...'
        $code = Invoke-Npm -NpmArgs @('install') -WorkingDirectory $frontend -LogFile (Join-Path $logDir 'frontend-install.log')
        if ($code -ne 0) { throw "npm install failed. See logs\frontend-install.log" }
    }

    $distIndex = Join-Path $frontend 'dist\index.html'
    $needBuild = -not (Test-Path $distIndex)
    if (-not $needBuild) {
        $srcVer = Get-Item (Join-Path $frontend 'src\version.ts')
        $distIdx = Get-Item $distIndex
        if ($srcVer.LastWriteTime -gt $distIdx.LastWriteTime) { $needBuild = $true }
    }
    if ($needBuild) {
        Write-JarvisLog $logFile 'npm run build...'
        $code = Invoke-Npm -NpmArgs @('run', 'build') -WorkingDirectory $frontend -LogFile (Join-Path $logDir 'frontend-build.log')
        if ($code -ne 0) { throw "npm run build failed. See logs\frontend-build.log" }
    }

    $venvPy = Join-Path $Root 'backend\venv\Scripts\python.exe'
    $proVenv = Join-Path $proRoot 'backend\venv\Scripts\python.exe'
    if (Test-Path $proVenv) {
        $venvPy = $proVenv
        Write-JarvisLog $logFile "Using shared venv from jarvis (Pro)"
    }
    if (-not (Test-Path $venvPy)) {
        Write-JarvisLog $logFile 'Creating venv...'
        $py = Resolve-PythonCmd
        $pyArgs = if ($py.Length -gt 1) { $py[1..($py.Length - 1)] } else { @() }
        $code = Invoke-HiddenCommand -FilePath $py[0] -ArgumentList ($pyArgs + @('-m', 'venv', 'backend\venv')) -WorkingDirectory $Root
        if ($code -ne 0) { throw 'Failed to create backend\venv' }
    }

    $pip = Join-Path $Root 'backend\venv\Scripts\pip.exe'
    if (-not (Test-Path (Join-Path $Root 'backend\venv\Lib\site-packages\fastapi'))) {
        Write-JarvisLog $logFile 'pip install -r requirements.txt...'
        $req = Join-Path $Root 'backend\requirements.txt'
        $pipLog = Join-Path $logDir 'pip-install.log'
        $code = Invoke-HiddenCommand -FilePath 'cmd.exe' -ArgumentList @(
            '/c', "`"$pip`" install -r `"$req`" >> `"$pipLog`" 2>&1"
        ) -WorkingDirectory $Root
        if ($code -ne 0) { throw 'pip install failed. See logs\pip-install.log' }
    } else {
        Invoke-HiddenCommand -FilePath $pip -ArgumentList @('install', 'socksio', '-q') | Out-Null
    }

    $pwPkg = Join-Path $Root 'backend\venv\Lib\site-packages\playwright'
    if (-not (Test-Path $pwPkg)) {
        Write-JarvisLog $logFile 'pip install playwright (встроенный Chromium)...'
        $code = Invoke-HiddenCommand -FilePath $pip -ArgumentList @(
            'install', 'playwright>=1.49.0', '-q'
        )
        if ($code -ne 0) {
            Write-JarvisLog $logFile 'WARN: pip install playwright failed — install-chromium.bat'
        }
    }

    $pwBrowsers = Join-Path $env:LOCALAPPDATA 'Jarvis\browsers'
    New-Item -ItemType Directory -Force -Path $pwBrowsers | Out-Null
    $env:PLAYWRIGHT_BROWSERS_PATH = $pwBrowsers

    function Test-JarvisBrowserPrefix {
        param([string]$Prefix)
        if (-not (Test-Path $pwBrowsers)) { return $false }
        foreach ($d in Get-ChildItem -Path $pwBrowsers -Filter "$Prefix-*" -Directory -ErrorAction SilentlyContinue) {
            if (Test-Path (Join-Path $d.FullName 'chrome-win\chrome.exe')) { return $true }
            if (Test-Path (Join-Path $d.FullName 'chrome-win64\chrome.exe')) { return $true }
        }
        return $false
    }

    if (-not (Test-JarvisBrowserPrefix 'chromium')) {
        if (Test-Path $proRoot) {
            Write-JarvisLog $logFile 'WARN: Chromium not in shared Jarvis/browsers — run start.bat in jarvis (Pro) once'
        } else {
            Write-JarvisLog $logFile 'playwright install chromium (внутри Jarvis)...'
            $chLog = Join-Path $logDir 'chromium-install.log'
            $code = Invoke-HiddenCommand -FilePath $venvPy -ArgumentList @(
                '-m', 'playwright', 'install', 'chromium'
            ) -LogFile $chLog -WorkingDirectory $Root
            if ($code -ne 0) {
                Write-JarvisLog $logFile 'WARN: chromium — install-chromium.bat'
            }
        }
    }

    if (-not (Test-JarvisBrowserPrefix 'chromium')) {
        Write-JarvisLog $logFile 'WARN: chromium missing — install-browsers.bat'
    } else {
        Write-JarvisLog $logFile 'playwright install chromium-headless-shell (Jarvis)...'
        $hsLog = Join-Path $logDir 'chromium-headless-install.log'
        Invoke-HiddenCommand -FilePath $venvPy -ArgumentList @(
            '-m', 'playwright', 'install', 'chromium-headless-shell'
        ) -LogFile $hsLog -WorkingDirectory $Root | Out-Null
    }

    Write-JarvisLog $logFile 'pip llama-cpp-python (optional)...'
    Invoke-HiddenCommand -FilePath $pip -ArgumentList @(
        'install', 'llama-cpp-python', '--prefer-binary',
        '--extra-index-url', 'https://abetlen.github.io/llama-cpp-python/whl/cpu', '-q'
    ) | Out-Null

    Write-JarvisLog $logFile 'Qwen model check...'
    $dlScript = Join-Path $script:JarvisRoot 'backend\scripts\download_qwen_model.py'
    Invoke-HiddenCommand -FilePath $venvPy -ArgumentList @($dlScript) -LogFile (Join-Path $logDir 'qwen-download.log') | Out-Null

    & "$PSScriptRoot\start-server.ps1"
    if ($LASTEXITCODE -ne 0) { throw 'Server did not start. See logs\server.log' }

    if ($env:JARVIS_OPEN_BROWSER -ne '0') {
        Start-Sleep -Seconds 1
        & "$PSScriptRoot\open-jarvis-ui.ps1" | Out-Null
        Write-JarvisLog $logFile 'UI opened in Jarvis Chrome (not default Windows browser)'
    } else {
        Write-JarvisLog $logFile 'OK — UI: scripts\open-jarvis-ui.ps1 (JARVIS_OPEN_BROWSER=0)'
    }
    exit 0
} catch {
    Write-JarvisLog $logFile "ERROR: $($_.Exception.Message)"
    Show-JarvisError $_.Exception.Message
    exit 1
}
