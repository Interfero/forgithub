# Перезапуск без окон консоли: .\restart.ps1
Set-Location $PSScriptRoot
& wscript.exe //nologo (Join-Path $PSScriptRoot 'run-restart.vbs')
exit $LASTEXITCODE
