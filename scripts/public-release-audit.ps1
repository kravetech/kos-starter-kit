[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$Report
)

$ErrorActionPreference = "Stop"

try {
    $scanRoot = [System.IO.Path]::GetFullPath($Root)
    if (-not $Report) { $Report = Join-Path $scanRoot "reports\RELEASE-AUDIT.md" }
    & git -C $scanRoot rev-parse --git-dir *> $null
    if ($LASTEXITCODE -ne 0) { throw "Release audit requires an initialized Git repository." }
    $tracked = @(& git -C $scanRoot ls-files)
    if ($LASTEXITCODE -ne 0) { throw "Unable to enumerate tracked Git files." }
    $findings = @()
    if ($tracked.Count -eq 0) { $findings += "ERROR Git index contains no tracked files; stage the intended release first." }
    $forbiddenFiles = @(
        "installer/answers.json",
        "installer/local-config.json",
        "installer/private-terms.txt"
    )
    $allowedKeepFiles = @("logs/.gitkeep","build/.gitkeep","test-output/.gitkeep")
    foreach ($relative in $tracked) {
        $normalized = $relative.Replace("\", "/")
        if ($normalized -in $forbiddenFiles -or
            ($normalized -match '^(logs|build|test-output)/' -and $normalized -notin $allowedKeepFiles)) {
            $findings += "ERROR forbidden release path is tracked: ``$normalized``"
        }
    }
    $stagedModes = @{}
    & git -C $scanRoot ls-files --stage | ForEach-Object {
        if ($_ -match '^(\d{6})\s+[0-9a-f]+\s+\d+\s+(.+)$') {
            $stagedModes[$Matches[2].Replace("\", "/")] = $Matches[1]
        }
    }
    foreach ($relative in @($tracked | Where-Object { $_ -like "*.sh" } | ForEach-Object { $_.Replace("\", "/") })) {
        if ($stagedModes[$relative] -ne "100755") {
            $findings += "ERROR ``$relative`` is not staged as executable; run ``git update-index --chmod=+x $relative``"
        }
    }
    $denylistPath = Join-Path $scanRoot "installer\private-terms.txt"
    $privateTerms = if (Test-Path -LiteralPath $denylistPath -PathType Leaf) {
        @(Get-Content -LiteralPath $denylistPath | Where-Object { $_.Trim() -and -not $_.TrimStart().StartsWith("#") } | ForEach-Object { $_.Trim() })
    } else { @() }
    if ($privateTerms.Count -eq 0) {
        $findings += "WARN no local private-term denylist configured."
    }
    foreach ($relative in $tracked) {
        $path = Join-Path $scanRoot $relative
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $item = Get-Item -LiteralPath $path
        if ($item.Extension -notin @(".md",".json",".yaml",".yml",".ps1",".sh",".py",".txt") -and $item.Name -ne ".gitignore") { continue }
        $content = Get-Content -LiteralPath $path -Raw
        foreach ($term in $privateTerms) {
            if ($content.IndexOf($term, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $findings += "ERROR private denylist term ``$term`` in ``$relative``"
            }
        }
        if ($content -match '(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[''"]?[A-Za-z0-9+/=_-]{12,}' -or
            $content -match '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----') {
            $findings += "ERROR potential secret-like value in ``$relative``"
        }
        if ($content -match '(?i)(?:[A-Z]:\\[A-Za-z0-9][A-Za-z0-9 _.-]+(?:\\[A-Za-z0-9][A-Za-z0-9 _.-]*)*|/(?:Users|home)/[^/\s]+/)') {
            $findings += "ERROR absolute machine path in ``$relative``"
        }
        if ($relative.Replace("\", "/") -like ".github/workflows/*") {
            foreach ($match in [regex]::Matches($content, '(?m)^\s*-\s+uses:\s*[^@\s]+@([^\s#]+)')) {
                if ($match.Groups[1].Value -notmatch '^[0-9a-fA-F]{40}$') {
                    $findings += "ERROR GitHub Action is not pinned to a full commit SHA in ``$relative``: ``$($match.Value.Trim())``"
                }
            }
        }
    }
    if (-not (Test-Path -LiteralPath (Join-Path $scanRoot "LICENSE") -PathType Leaf)) {
        $findings += "ERROR LICENSE is missing."
    }
    $architecture = Get-Content -LiteralPath (Join-Path $scanRoot "ARCHITECTURE.md") -Raw
    $pythonInstaller = Get-Content -LiteralPath (Join-Path $scanRoot "installer\install.py") -Raw
    $powerShellInstaller = Get-Content -LiteralPath (Join-Path $scanRoot "install.ps1") -Raw
    $architectureVersion = [regex]::Match($architecture, '(?m)^version:\s*([0-9]+\.[0-9]+\.[0-9]+)').Groups[1].Value
    $pythonVersion = [regex]::Match($pythonInstaller, '(?m)^VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"').Groups[1].Value
    $powerShellVersion = [regex]::Match($powerShellInstaller, '(?m)^\$script:InstallerVersion\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"').Groups[1].Value
    if (-not $architectureVersion -or $architectureVersion -ne $pythonVersion -or $architectureVersion -ne $powerShellVersion) {
        $findings += "ERROR release versions are inconsistent: architecture=$architectureVersion, python=$pythonVersion, powershell=$powerShellVersion"
    }
    $status = if (@($findings | Where-Object { $_ -like "ERROR*" }).Count -eq 0) { "PASS" } else { "FAIL" }
    if ($findings.Count -eq 0) { $findings += "Tracked release content passed path, privacy, license, and version checks." }
    $body = @("# Public Release Audit","","Generated: $([DateTimeOffset]::Now.ToString('o'))","Status: **$status**","","## Findings","")
    $body += $findings | ForEach-Object { "- $_" }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Report) -Force | Out-Null
    Set-Content -LiteralPath $Report -Value $body -Encoding utf8
    Write-Output "Public release audit: $status"
    if ($status -eq "PASS") { exit 0 } else { exit 2 }
} catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 3
}
