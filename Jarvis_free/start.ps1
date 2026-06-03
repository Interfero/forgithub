Set-Location $PSScriptRoot
& wscript.exe //nologo (Join-Path $PSScriptRoot 'scripts\launch\run-start.vbs')
exit $LASTEXITCODE
