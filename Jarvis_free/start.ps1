# Запуск без окон консоли: .\start.ps1
Set-Location $PSScriptRoot
& wscript.exe //nologo (Join-Path $PSScriptRoot 'run-start.vbs')
exit $LASTEXITCODE
