param(
    [string]$RepoRoot = "",
    [switch]$Json,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib\disk-budget.ps1")

$root = Get-RepoRoot -Start $RepoRoot
$report = Get-DiskBudgetReport -Root $root

if ($Json) {
    $report | ConvertTo-Json -Depth 5
    if ($report.Status -eq "over") { exit 2 }
    if ($Strict -and $report.Status -eq "warn") { exit 1 }
    exit 0
}

Write-DiskBudgetReport $report

if ($report.Status -eq "over") { exit 2 }
if ($Strict -and $report.Status -eq "warn") { exit 1 }
exit 0
