[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$Report,
    [switch]$IncludeGenerated
)
$ErrorActionPreference = "Stop"
try {
    $scanRoot = [System.IO.Path]::GetFullPath($Root)
    if (-not $Report) { $Report = Join-Path $scanRoot "PRIVACY-SCAN.md" }
    $findings = @()
    $denylistPath = Join-Path $scanRoot "installer\private-terms.txt"
    $privateTerms = if (Test-Path -LiteralPath $denylistPath -PathType Leaf) {
        @(Get-Content -LiteralPath $denylistPath | Where-Object { $_.Trim() -and -not $_.TrimStart().StartsWith("#") } | ForEach-Object { $_.Trim() })
    } else { @() }
    if ($privateTerms.Count -eq 0) {
        $findings += "WARN no local private-term denylist configured; copy ``installer/private-terms.example.txt`` to ignored ``installer/private-terms.txt``"
    }
    Get-ChildItem -LiteralPath $scanRoot -Recurse -File | Where-Object {
        $_.FullName -ne $denylistPath -and
        $_.FullName -notmatch '[\\/]\.git[\\/]' -and
        $_.FullName -notmatch '[\\/]\.claude[\\/]' -and
        ($IncludeGenerated -or $_.FullName -notmatch '[\\/](logs|build|test-output)[\\/]') -and
        ($_.Extension -in @(".md",".json",".yaml",".yml",".ps1",".sh",".py",".txt") -or $_.Name -eq ".gitignore")
    } | ForEach-Object {
        $relative = $_.FullName.Substring($scanRoot.Length).TrimStart('\')
        $content = Get-Content -LiteralPath $_.FullName -Raw
        foreach ($term in $privateTerms) { if ($content -match [regex]::Escape($term)) { $findings += "ERROR private reference term ``$term`` in ``$relative``" } }
        if ($content -match '(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[''"]?[A-Za-z0-9+/=_-]{12,}' -or $content -match '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----') { $findings += "ERROR potential secret-like value in ``$relative``" }
        if ($content -match '(?i)(?:[A-Z]:\\[A-Za-z0-9][A-Za-z0-9 _.-]+(?:\\[A-Za-z0-9][A-Za-z0-9 _.-]*)*|/(?:Users|home)/[^/\s]+/)') { $findings += "ERROR absolute machine path in ``$relative``" }
    }
    $status = if (@($findings | Where-Object { $_ -like "ERROR*" }).Count -eq 0) { "PASS" } else { "FAIL" }
    $body = @("# Privacy Scan","","Generated: $([DateTimeOffset]::Now.ToString('o'))","Status: **$status**","","## Findings","")
    $body += if ($findings.Count) { $findings | ForEach-Object { "- $_" } } else { "- None." }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Report) -Force | Out-Null
    Set-Content -LiteralPath $Report -Value $body -Encoding utf8
    Write-Output "Privacy scan: $status"
    if ($status -eq "PASS") { exit 0 } else { exit 2 }
} catch { [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)"); exit 3 }
