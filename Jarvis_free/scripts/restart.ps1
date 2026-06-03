$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
& wscript.exe //nologo (Join-Path $Root 'scripts\launch\run-restart.vbs')
exit $LASTEXITCODE
