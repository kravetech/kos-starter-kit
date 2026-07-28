[CmdletBinding()]
param([string]$StarterRoot = (Split-Path -Parent $PSScriptRoot), [string]$Report)
$ErrorActionPreference = "Stop"
try {
    $root = [System.IO.Path]::GetFullPath($StarterRoot)
    if (-not $Report) { $Report = Join-Path $root "reports\VALIDATION-REPORT.md" }
    $requiredFiles = @(
        "README.md","INSTALL.md","INITIALIZE.md","KOS-INSTALLER.md","QUESTIONNAIRE.md","MANIFEST.md","PRIVACY.md",
        "LICENSE","LICENSE-NOTICE.md","SECURITY.md","PUBLICATION.md","CHANGELOG.md","install.ps1","install.sh","initialize.ps1","initialize.sh",".gitignore",".gitattributes",
        "installer\answers.example.json","installer\private-terms.example.txt","installer\questionnaire.schema.json","installer\structure.manifest.json",
        "installer\installer-state.template.json","scripts\validate-starter-kit.ps1","scripts\validate-starter-kit.sh",
        "scripts\validate-installation.ps1","scripts\validate-installation.sh","scripts\privacy-scan.ps1",
        "scripts\privacy-scan.sh","scripts\public-release-audit.ps1","scripts\generate-manifest.ps1","scripts\generate-manifest.sh",
        ".github\workflows\ci.yml"
    )
    $requiredDirectories = @(
        "installer","templates\root","templates\system","templates\business","templates\projects","templates\personal",
        "templates\hobbies","templates\knowledge","templates\inbox","templates\daily","templates\attachments",
        "templates\archive","templates\automations","scripts","reports","examples","logs","build","test-output"
    )
    $findings = @()
    foreach ($relative in $requiredFiles) { if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) { $findings += "ERROR missing required file: ``$relative``" } }
    foreach ($relative in $requiredDirectories) { if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Container)) { $findings += "ERROR missing required directory: ``$relative``" } }
    foreach ($relative in @("installer\answers.example.json","installer\questionnaire.schema.json","installer\structure.manifest.json","installer\installer-state.template.json")) {
        try { $null = Get-Content -LiteralPath (Join-Path $root $relative) -Raw | ConvertFrom-Json }
        catch { $findings += "ERROR invalid JSON ``$relative``: $($_.Exception.Message)" }
    }
    $installer = Get-Content -LiteralPath (Join-Path $root "KOS-INSTALLER.md") -Raw
    foreach ($heading in @("Role","Objective","Inputs","Constraints","Privacy Rules","Questionnaire","Installation Modes","Dry Run","File Generation","Template Processing","Context Bootstrap","Automation Setup","Git Initialization","Validation","Conflict Handling","Resume Behavior","Rollback","Installation Report")) {
        if ($installer -notmatch "(?m)^## $([regex]::Escape($heading))\s*$") { $findings += "ERROR installer heading missing: ``$heading``" }
    }
    foreach ($adapter in @("templates\root\CLAUDE.md","templates\root\CODEX.md")) {
        if ((Get-Content -LiteralPath (Join-Path $root $adapter)).Count -gt 40) { $findings += "ERROR adapter is not thin: ``$adapter``" }
    }
    $example = Get-Content -LiteralPath (Join-Path $root "installer\answers.example.json") -Raw | ConvertFrom-Json
    $available = [System.Collections.Generic.HashSet[string]]::new()
    foreach ($section in @("user","system","privacy","rhythm")) { foreach ($property in $example.$section.PSObject.Properties) { [void]$available.Add($property.Name) } }
    @("system_name","system_short_name","system_description") | ForEach-Object { [void]$available.Add($_) }
    $tokens = [System.Collections.Generic.HashSet[string]]::new()
    Get-ChildItem -LiteralPath (Join-Path $root "templates") -Recurse -File | ForEach-Object {
        [regex]::Matches((Get-Content -LiteralPath $_.FullName -Raw), '\{\{([a-z0-9_]+)\}\}') | ForEach-Object { [void]$tokens.Add($_.Groups[1].Value) }
    }
    foreach ($token in $tokens) { if (-not $available.Contains($token)) { $findings += "ERROR template token has no answer mapping: ``{{$token}}``" } }
    foreach ($script in @("install.ps1","initialize.ps1")) {
        $content = Get-Content -LiteralPath (Join-Path $root $script) -Raw
        if ($content -notmatch '\$ErrorActionPreference' -or $content -notmatch '\bexit\b') { $findings += "ERROR unsafe PowerShell error handling: ``$script``" }
    }
    $status = if (@($findings | Where-Object { $_ -like "ERROR*" }).Count -eq 0) { "PASS" } else { "FAIL" }
    $body = @("# Starter-Kit Validation Report","","Generated: $([DateTimeOffset]::Now.ToString('o'))","Status: **$status**","","## Findings","")
    $body += if ($findings.Count) { $findings | ForEach-Object { "- $_" } } else { "- None." }
    New-Item -ItemType Directory -Path (Split-Path -Parent $Report) -Force | Out-Null
    Set-Content -LiteralPath $Report -Value $body -Encoding utf8
    Write-Output "Starter-kit validation: $status"
    if ($status -eq "PASS") { exit 0 } else { exit 2 }
} catch { [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)"); exit 3 }
