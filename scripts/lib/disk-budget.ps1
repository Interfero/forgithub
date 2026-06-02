param(
    [string]$RepoRoot = "",
    [switch]$Json,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    param([string]$Start)
    if ($Start) { return (Resolve-Path $Start).Path }
    $here = $PSScriptRoot
    while ($here) {
        if (Test-Path (Join-Path $here "config\workspace.json")) {
            return $here
        }
        $parent = Split-Path $here -Parent
        if (-not $parent -or $parent -eq $here) { break }
        $here = $parent
    }
    throw "Cannot find config/workspace.json from $PSScriptRoot"
}

function Get-DirBytes {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return [int64]0 }
    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        $sum = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        if ($null -eq $sum) { return [int64]0 }
        return [int64]$sum
    }
    return [int64]$item.Length
}

function Format-Bytes {
    param([int64]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N1} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N0} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Resolve-TrackedPath {
    param($Entry, [string]$Root)

    if ($Entry.path -eq ".") { return $Root }

    if ($Entry.path) {
        $p = Join-Path $Root $Entry.path
        if (Test-Path -LiteralPath $p) { return (Resolve-Path -LiteralPath $p).Path }
        return $p
    }

    if ($Entry.env -and $Entry.suffix) {
        $base = [Environment]::GetEnvironmentVariable($Entry.env)
        if (-not $base) { return $null }
        $p = Join-Path $base $Entry.suffix
        if (Test-Path -LiteralPath $p) { return (Resolve-Path -LiteralPath $p).Path }
        return $p
    }

    return $null
}

function Get-DiskBudgetReport {
    param(
        [string]$Root,
        [double]$LimitGb = 10,
        [int]$WarnAtPercent = 85
    )

    $configPath = Join-Path $Root "config\workspace.json"
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    if ($LimitGb -le 0) { $LimitGb = [double]$config.diskLimitGb }
    if ($WarnAtPercent -le 0) { $WarnAtPercent = [int]$config.warnAtPercent }

    $limitBytes = [int64]($LimitGb * 1GB)
    $rows = @()
    $total = [int64]0

    foreach ($entry in $config.trackedPaths) {
        $resolved = Resolve-TrackedPath -Entry $entry -Root $Root
        $bytes = if ($resolved) { [int64](Get-DirBytes -Path $resolved) } else { [int64]0 }
        if ($bytes -gt 0 -or -not $entry.optional) {
            $total += $bytes
        }
        $rows += [pscustomobject]@{
            Id = $entry.id
            Label = $entry.label
            Path = if ($resolved) { $resolved } else { "(missing)" }
            Bytes = $bytes
            Human = Format-Bytes $bytes
            Optional = [bool]$entry.optional
        }
    }

    $percent = if ($limitBytes -gt 0) { [math]::Round(100.0 * $total / $limitBytes, 1) } else { 0 }
    $status = "ok"
    if ($percent -ge 100) { $status = "over" }
    elseif ($percent -ge $WarnAtPercent) { $status = "warn" }

    return [pscustomobject]@{
        Root = $Root
        LimitGb = $LimitGb
        LimitBytes = $limitBytes
        UsedBytes = $total
        UsedHuman = Format-Bytes $total
        FreeBytes = [int64][math]::Max([int64]0, $limitBytes - $total)
        FreeHuman = Format-Bytes ([int64][math]::Max([int64]0, $limitBytes - $total))
        UsedPercent = $percent
        Status = $status
        DefaultProfile = $config.defaultProfile
        Rows = $rows
    }
}

function Test-DiskBudget {
    param(
        [string]$Root = "",
        [int64]$RequiredBytes = 0,
        [switch]$Strict
    )

    $rootPath = Get-RepoRoot -Start $Root
    $report = Get-DiskBudgetReport -Root $rootPath

    if ($RequiredBytes -gt 0 -and ($report.UsedBytes + $RequiredBytes) -gt $report.LimitBytes) {
        $need = Format-Bytes $RequiredBytes
        Write-Host "DISK BUDGET: need $need more, only $($report.FreeHuman) free (limit $($report.LimitGb) GB)." -ForegroundColor Red
        return $false
    }

    if ($report.Status -eq "over") {
        Write-Host "DISK BUDGET EXCEEDED: $($report.UsedHuman) / $($report.LimitGb) GB ($($report.UsedPercent)%)" -ForegroundColor Red
        return $false
    }

    if ($Strict -and $report.Status -eq "warn") {
        Write-Host "DISK BUDGET WARNING: $($report.UsedHuman) / $($report.LimitGb) GB ($($report.UsedPercent)%)" -ForegroundColor Yellow
        return $false
    }

    return $true
}

function Write-DiskBudgetReport {
    param($Report)

    Write-Host ""
    Write-Host "Disk budget: $($Report.UsedHuman) / $($Report.LimitGb) GB ($($Report.UsedPercent)%) - $($Report.Status)" -ForegroundColor $(switch ($Report.Status) { "over" { "Red" } "warn" { "Yellow" } default { "Green" } })
    Write-Host "Free: $($Report.FreeHuman) | Default profile: $($Report.DefaultProfile) (see docs/DISK.md)"
    Write-Host ""
    $Report.Rows | Format-Table Label, Human, Path -AutoSize
}
