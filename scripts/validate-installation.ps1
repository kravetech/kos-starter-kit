[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallationRoot, [string]$Report)
$ErrorActionPreference = "Stop"
try {
    $root = [System.IO.Path]::GetFullPath($InstallationRoot)
    if (-not $Report) { $Report = Join-Path $root "VALIDATION-REPORT.md" }
    $findings = @()
    foreach ($relative in @("README.md","AGENTS.md","CLAUDE.md","CODEX.md","ARCHITECTURE.md","CONTEXT-POLICY.md","TOKEN-OPTIMIZATION.md","memory.md","handoff.md","00 - System\Installation\installer-state.json","00 - System\Installation\INSTALLATION-REPORT.md","00 - System\Automations\AUTOMATION-REGISTRY.md")) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) { $findings += "ERROR missing installation file: ``$relative``" }
    }
    foreach ($relative in @("00 - System","01 - Business","02 - Projects","03 - Personal","04 - Hobbies","05 - Knowledge","06 - Inbox","07 - Daily","08 - Templates","09 - Attachments","99 - Archive")) {
        if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Container)) { $findings += "ERROR missing installation directory: ``$relative``" }
    }
    Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.Extension -in @(".md",".json",".yaml",".yml") } | ForEach-Object {
        if ((Get-Content -LiteralPath $_.FullName -Raw) -match '\{\{[a-z0-9_]+\}\}') { $findings += "ERROR unresolved template token: ``$($_.FullName.Substring($root.Length).TrimStart('\'))``" }
    }
    foreach ($adapter in @("CLAUDE.md","CODEX.md")) { if ((Get-Content -LiteralPath (Join-Path $root $adapter)).Count -gt 40) { $findings += "ERROR adapter is not thin: ``$adapter``" } }
    $registry = Join-Path $root "00 - System\Automations\AUTOMATION-REGISTRY.md"
    if ((Test-Path -LiteralPath $registry) -and (Get-Content -LiteralPath $registry -Raw) -notmatch 'Status: Not configured') { $findings += "ERROR external automations are not explicitly unconfigured" }
    $status = if (@($findings | Where-Object { $_ -like "ERROR*" }).Count -eq 0) { "PASS" } else { "FAIL" }
    $body = @("# Installation Validation Report","","Generated: $([DateTimeOffset]::Now.ToString('o'))","Status: **$status**","","## Findings","")
    $body += if ($findings.Count) { $findings | ForEach-Object { "- $_" } } else { "- None." }
    Set-Content -LiteralPath $Report -Value $body -Encoding utf8
    Write-Output "Installation validation: $status"
    if ($status -eq "PASS") { exit 0 } else { exit 2 }
} catch { [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)"); exit 3 }
