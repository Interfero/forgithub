param(
    [string]$Path = ".",
    [switch]$StagedOnly
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path $Path

$blockedNames = @(
    ".env", ".env.local", ".env.development", ".env.production", ".env.test",
    "credentials.json", "service-account.json", "google-services.json",
    "secrets.json", "secrets.yaml", "secrets.yml"
)

$blockedExtensions = @(".pem", ".key", ".p12", ".pfx", ".kdbx")

$secretPatterns = @(
    @{ Name = "AWS Access Key"; Pattern = "AKIA[0-9A-Z]{16}" },
    @{ Name = "GitHub PAT"; Pattern = "gh[pousr]_[A-Za-z0-9_]{20,}" },
    @{ Name = "OpenAI-style key"; Pattern = "sk-[A-Za-z0-9]{20,}" },
    @{ Name = "Private key block"; Pattern = "BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY" },
    @{
        Name = "Generic secret assignment"
        Pattern = '(?i)(api[_-]?key|client[_-]?secret|access[_-]?token|password)\s*[:=]\s*["''](?!your_|insert|replace|example|changeme|xxx|TODO)[^"''\s]{8,}["'']'
    }
)

function Get-ScanFiles {
    param([string]$ScanRoot)

    if ($StagedOnly) {
        Push-Location $ScanRoot
        try {
            $staged = git diff --cached --name-only --diff-filter=ACMR 2>$null
            if (-not $staged) { return @() }
            return $staged | ForEach-Object {
                $full = Join-Path $ScanRoot $_
                if (Test-Path $full -PathType Leaf) { Get-Item $full }
            }
        } finally {
            Pop-Location
        }
    }

    return Get-ChildItem -Path $ScanRoot -Recurse -File -Force |
        Where-Object {
            $rel = $_.FullName.Substring($ScanRoot.Length).TrimStart('\', '/')
            -not ($rel -match '(^|[\\/])\.git([\\/]|$)') -and
            -not ($rel -match '(^|[\\/])node_modules([\\/]|$)') -and
            -not ($rel -match '(^|[\\/])\.venv([\\/]|$)') -and
            -not ($rel -match '(^|[\\/])dist([\\/]|$)') -and
            -not ($rel -match '(^|[\\/])build([\\/]|$)')
        }
}

$issues = @()
$files = @(Get-ScanFiles -ScanRoot $root)

foreach ($file in $files) {
    $name = $file.Name.ToLowerInvariant()

    if ($blockedNames -contains $name) {
        $issues += "[blocked file] $($file.FullName)"
        continue
    }

    if ($name -like ".env.*" -and $name -notlike "*.example") {
        $issues += "[env without example] $($file.FullName)"
        continue
    }

    $ext = $file.Extension.ToLowerInvariant()
    if ($blockedExtensions -contains $ext) {
        $issues += "[blocked extension $ext] $($file.FullName)"
        continue
    }

    try {
        $content = Get-Content -LiteralPath $file.FullName -Raw -ErrorAction Stop
    } catch {
        continue
    }

    if ([string]::IsNullOrWhiteSpace($content)) { continue }

    foreach ($rule in $secretPatterns) {
        if ($content -match $rule.Pattern) {
            $issues += "[$($rule.Name)] $($file.FullName)"
        }
    }
}

if ($issues.Count -gt 0) {
    Write-Host ""
    Write-Host "SECURITY CHECK FAILED" -ForegroundColor Red
    Write-Host "Issues found: $($issues.Count)" -ForegroundColor Red
    $issues | Select-Object -Unique | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    Write-Host ""
    Write-Host "Fix issues before commit. See SECURITY.md" -ForegroundColor Red
    exit 1
}

$scope = if ($StagedOnly) { "staged files" } else { "tree $root" }
Write-Host "OK: no secrets detected ($scope)." -ForegroundColor Green
exit 0
