param(
    [string]$RepoRoot = "",
    [int64]$RequiredBytes = 0,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\disk-budget.ps1")

$root = Get-RepoRoot -Start $RepoRoot
$ok = Test-DiskBudget -Root $root -RequiredBytes $RequiredBytes -Strict:$Strict
if (-not $ok) {
    Write-Host "Run: .\scripts\cleanup-workspace.ps1" -ForegroundColor Cyan
    Write-Host "Docs: DISK.md" -ForegroundColor Cyan
    exit 1
}
Write-Host "Disk budget OK." -ForegroundColor Green
exit 0
