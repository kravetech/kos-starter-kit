[CmdletBinding()]
param(
    [string]$Answers = ".\installer\answers.example.json",
    [string]$Target,
    [ValidateSet("lean","standard","business","developer","creator","custom","migration")]
    [string]$Mode,
    [switch]$DryRun,
    [switch]$Resume,
    [switch]$Migration,
    [switch]$AllowOverwrite
)

$ErrorActionPreference = "Stop"
$script:StarterRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$script:InstallerVersion = "1.1.0"

function Set-DefaultProperty {
    param([object]$Object, [string]$Name, $Value)
    if (-not $Object.PSObject.Properties[$Name]) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Stop-InputError {
    param([string]$Message)
    throw [System.ArgumentException]::new($Message)
}

function Convert-ToTemplateValues {
    param([object]$AnswersObject)
    $values = @{}
    foreach ($section in @("user","system","privacy","rhythm")) {
        foreach ($property in $AnswersObject.$section.PSObject.Properties) {
            if ($property.Value -is [bool]) { $values[$property.Name] = $property.Value.ToString().ToLowerInvariant() }
            elseif ($property.Value -is [array]) { $values[$property.Name] = $property.Value -join ", " }
            else { $values[$property.Name] = [string]$property.Value }
        }
    }
    $values["system_name"] = [string]$AnswersObject.system.name
    $values["system_short_name"] = [string]$AnswersObject.system.short_name
    $values["system_description"] = [string]$AnswersObject.system.description
    return $values
}

function Expand-Template {
    param([string]$Content, [hashtable]$Values)
    return [regex]::Replace($Content, '\{\{([a-z0-9_]+)\}\}', {
        param($match)
        $key = $match.Groups[1].Value
        if ($Values.ContainsKey($key)) { return $Values[$key] }
        return $match.Value
    })
}

function Write-SafeFile {
    param([string]$Path, [string]$Content, [bool]$Overwrite, [object]$State)
    $resolvedTarget = [System.IO.Path]::GetFullPath([string]$State.target_path).TrimEnd('\')
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not ($resolvedPath.Equals($resolvedTarget, [System.StringComparison]::OrdinalIgnoreCase) -or
        $resolvedPath.StartsWith($resolvedTarget + '\', [System.StringComparison]::OrdinalIgnoreCase))) {
        Stop-InputError "Destination resolves outside installation target: $resolvedPath"
    }
    $parent = Split-Path -Parent $Path
    if ($parent) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Set-Content -LiteralPath $Path -Value $Content -Encoding utf8
        $State.created_files += $Path
        return
    }
    $current = Get-Content -LiteralPath $Path -Raw
    if ($current.TrimEnd("`r","`n") -eq $Content.TrimEnd("`r","`n")) {
        $State.skipped_files += $Path
        return
    }
    if ($Overwrite) {
        Set-Content -LiteralPath $Path -Value $Content -Encoding utf8
        $State.created_files += $Path
        return
    }
    $extension = [System.IO.Path]::GetExtension($Path)
    $proposal = if ($extension) {
        Join-Path (Split-Path -Parent $Path) ("{0}.new{1}" -f [System.IO.Path]::GetFileNameWithoutExtension($Path), $extension)
    } else { "$Path.new" }
    Set-Content -LiteralPath $proposal -Value $Content -Encoding utf8
    $State.conflicts += [pscustomobject]@{ existing = $Path; proposed = $proposal }
}

try {
    $answerCandidate = if ([System.IO.Path]::IsPathRooted($Answers)) { $Answers } else { Join-Path $script:StarterRoot $Answers }
    $answerPath = [System.IO.Path]::GetFullPath($answerCandidate)
    if (-not (Test-Path -LiteralPath $answerPath -PathType Leaf)) { Stop-InputError "Answer file not found: $answerPath" }
    $answerObject = Get-Content -LiteralPath $answerPath -Raw | ConvertFrom-Json
    foreach ($section in @("user","system","privacy","rhythm","installation")) {
        if (-not $answerObject.PSObject.Properties[$section]) {
            $answerObject | Add-Member -NotePropertyName $section -NotePropertyValue ([pscustomobject]@{})
        }
    }
    if (-not [string]$answerObject.user.preferred_name) { Stop-InputError "user.preferred_name is required." }
    $preferred = [string]$answerObject.user.preferred_name
    Set-DefaultProperty $answerObject.user "full_name" ""
    Set-DefaultProperty $answerObject.user "author_name" $preferred
    Set-DefaultProperty $answerObject.user "technical_username" (($preferred -replace '[^A-Za-z0-9._-]+','-').Trim('-').ToLowerInvariant())
    Set-DefaultProperty $answerObject.user "role" "Knowledge worker"
    Set-DefaultProperty $answerObject.user "timezone" "UTC"
    Set-DefaultProperty $answerObject.user "locale" "en"
    Set-DefaultProperty $answerObject.user "language" "English"
    Set-DefaultProperty $answerObject.user "communication_style" "Direct, concise, practical"
    Set-DefaultProperty $answerObject.system "name" "Knowledge OS"
    Set-DefaultProperty $answerObject.system "short_name" "KOS"
    Set-DefaultProperty $answerObject.system "root_folder_name" ([string]$answerObject.system.name)
    Set-DefaultProperty $answerObject.system "description" "A portable operating system for durable knowledge and active work."
    Set-DefaultProperty $answerObject.system "motto" ""
    Set-DefaultProperty $answerObject.system "installation_date" (Get-Date -Format "yyyy-MM-dd")
    Set-DefaultProperty $answerObject.privacy "default_ai_access" "internal"
    Set-DefaultProperty $answerObject.privacy "restricted_folders" @("03 - Personal","09 - Attachments")
    Set-DefaultProperty $answerObject.privacy "business_ai_access" "internal"
    Set-DefaultProperty $answerObject.privacy "personal_ai_access" "restricted"
    Set-DefaultProperty $answerObject.privacy "linked_source_ai_access" "restricted"
    Set-DefaultProperty $answerObject.privacy "exclude_sensitive_automatically" $true
    Set-DefaultProperty $answerObject.rhythm "daily_review_time" "17:00"
    Set-DefaultProperty $answerObject.rhythm "weekly_review_day" "Friday"
    Set-DefaultProperty $answerObject.rhythm "monthly_review" $true
    Set-DefaultProperty $answerObject.rhythm "daily_note_generation" $true
    Set-DefaultProperty $answerObject.rhythm "inbox_processing" $true
    Set-DefaultProperty $answerObject.rhythm "memory_maintenance" $true
    Set-DefaultProperty $answerObject.rhythm "handoff_maintenance" $true
    Set-DefaultProperty $answerObject.rhythm "git_review" $false
    Set-DefaultProperty $answerObject.rhythm "project_health_checks" $true
    Set-DefaultProperty $answerObject.installation "mode" "standard"
    Set-DefaultProperty $answerObject.installation "target_directory" ([string]$answerObject.system.root_folder_name)
    Set-DefaultProperty $answerObject.installation "initialize_git" $false
    Set-DefaultProperty $answerObject.installation "create_initial_commit" $false
    Set-DefaultProperty $answerObject.installation "include_samples" $false
    Set-DefaultProperty $answerObject.installation "include_gitkeep" $true
    Set-DefaultProperty $answerObject.installation "enable_windows_scripts" $true
    Set-DefaultProperty $answerObject.installation "enable_unix_scripts" $true
    Set-DefaultProperty $answerObject.installation "configure_external_integrations" $false
    Set-DefaultProperty $answerObject.installation "allow_overwrite" $false
    Set-DefaultProperty $answerObject.installation "backup_before_migration" $true
    Set-DefaultProperty $answerObject.installation "custom_modules" @()
    if ($Mode) { $answerObject.installation.mode = $Mode }
    if ($Migration) { $answerObject.installation.mode = "migration" }
    if ($Target) { $answerObject.installation.target_directory = $Target }
    if ([string]$answerObject.privacy.default_ai_access -notin @("public","internal","restricted")) { Stop-InputError "Invalid default AI access." }
    if ([string]$answerObject.installation.mode -notin @("lean","standard","business","developer","creator","custom","migration")) { Stop-InputError "Invalid installation mode." }
    if ([string]$answerObject.rhythm.daily_review_time -notmatch '^([01][0-9]|2[0-3]):[0-5][0-9]$') { Stop-InputError "daily_review_time must use HH:mm." }
    $rawTarget = [string]$answerObject.installation.target_directory
    $targetCandidate = if ([System.IO.Path]::IsPathRooted($rawTarget)) { $rawTarget } else { Join-Path $script:StarterRoot $rawTarget }
    $targetRoot = [System.IO.Path]::GetFullPath($targetCandidate)
    $targetNormalized = $targetRoot.TrimEnd('\')
    $starterNormalized = $script:StarterRoot.TrimEnd('\')
    $volumeRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetPathRoot($targetRoot)).TrimEnd('\')
    $userProfile = if ($env:USERPROFILE) { [System.IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\') } else { "" }
    if ($targetNormalized.Equals($volumeRoot, [System.StringComparison]::OrdinalIgnoreCase)) { Stop-InputError "Target cannot be a filesystem root." }
    if ($userProfile -and $targetNormalized.Equals($userProfile, [System.StringComparison]::OrdinalIgnoreCase)) { Stop-InputError "Target cannot be the user profile directory." }
    if ($targetNormalized.Equals($starterNormalized, [System.StringComparison]::OrdinalIgnoreCase)) { Stop-InputError "Target cannot equal the starter-kit root." }
    if ($starterNormalized.StartsWith($targetNormalized + '\', [System.StringComparison]::OrdinalIgnoreCase)) { Stop-InputError "Target cannot contain the starter-kit root." }
    $existingAncestor = $targetRoot
    while ($existingAncestor -and -not (Test-Path -LiteralPath $existingAncestor)) {
        $parent = Split-Path -Parent $existingAncestor
        if ($parent -eq $existingAncestor) { break }
        $existingAncestor = $parent
    }
    while ($existingAncestor -and (Test-Path -LiteralPath $existingAncestor)) {
        $item = Get-Item -LiteralPath $existingAncestor -Force
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            Stop-InputError "Target ancestry contains a link or reparse point: $existingAncestor"
        }
        $parent = Split-Path -Parent $existingAncestor
        if (-not $parent -or $parent -eq $existingAncestor) { break }
        $existingAncestor = $parent
    }
    if (Test-Path -LiteralPath $targetRoot -PathType Container) {
        $reparsePoint = Get-ChildItem -LiteralPath $targetRoot -Recurse -Force | Where-Object {
            ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
        } | Select-Object -First 1
        if ($reparsePoint) { Stop-InputError "Target contains a link or reparse point: $($reparsePoint.FullName)" }
        $hasContent = Get-ChildItem -LiteralPath $targetRoot -Force | Select-Object -First 1
        if (-not $DryRun -and -not $Resume -and $answerObject.installation.mode -ne "migration" -and $hasContent) {
            Stop-InputError "Target is not empty. Use -Migration for an existing vault or -Resume for an interrupted installation."
        }
    }
    $localConfigPath = Join-Path $script:StarterRoot "installer\local-config.json"
    if (Test-Path -LiteralPath $localConfigPath -PathType Leaf) {
        $localConfig = Get-Content -LiteralPath $localConfigPath -Raw | ConvertFrom-Json
        foreach ($protectedValue in @($localConfig.reference_paths) + @($localConfig.protected_paths)) {
            if (-not $protectedValue) { continue }
            $protected = [System.IO.Path]::GetFullPath([string]$protectedValue).TrimEnd('\')
            if ($targetRoot.Equals($protected, [System.StringComparison]::OrdinalIgnoreCase) -or $targetRoot.StartsWith($protected + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
                Stop-InputError "Target resolves inside protected path: $targetRoot"
            }
        }
    }
    $modules = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    @("system","projects","inbox","daily","templates","attachments","archive") | ForEach-Object { [void]$modules.Add($_) }
    if ($answerObject.installation.mode -eq "custom") {
        @($answerObject.installation.custom_modules) | ForEach-Object { [void]$modules.Add([string]$_) }
    } elseif ($answerObject.installation.mode -ne "lean") {
        @("business","personal","hobbies","knowledge") | ForEach-Object { [void]$modules.Add($_) }
    }
    $manifest = Get-Content -LiteralPath (Join-Path $script:StarterRoot "installer\structure.manifest.json") -Raw | ConvertFrom-Json
    $prefixMap = @{
        system="00 - System"; business="01 - Business"; projects="02 - Projects"; personal="03 - Personal";
        hobbies="04 - Hobbies"; knowledge="05 - Knowledge"; inbox="06 - Inbox"; daily="07 - Daily";
        templates="08 - Templates"; attachments="09 - Attachments"; archive="99 - Archive"
    }
    $allowedPrefixes = @($modules | ForEach-Object { $prefixMap[$_] })
    $directories = @($manifest.standard_directories | Where-Object {
        $candidate = [string]$_
        @($allowedPrefixes | Where-Object { $candidate.StartsWith($_, [System.StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
    })
    $plan = [System.Collections.Generic.List[object]]::new()
    Get-ChildItem -LiteralPath (Join-Path $script:StarterRoot "templates\root") -File | Sort-Object Name | ForEach-Object {
        $plan.Add([pscustomobject]@{ Source=$_.FullName; Relative=$_.Name })
    }
    $mapping = @{
        system=@("system","00 - System"); business=@("business","01 - Business"); projects=@("projects","02 - Projects");
        personal=@("personal","03 - Personal"); hobbies=@("hobbies","04 - Hobbies"); knowledge=@("knowledge","05 - Knowledge");
        inbox=@("inbox","06 - Inbox"); daily=@("daily","07 - Daily"); attachments=@("attachments","09 - Attachments");
        archive=@("archive","99 - Archive"); automations=@("automations","00 - System\Automations")
    }
    $templateModules = @($modules) + "automations"
    foreach ($module in $templateModules) {
        if (-not $mapping.ContainsKey($module)) { continue }
        $sourceRoot = Join-Path $script:StarterRoot ("templates\" + $mapping[$module][0])
        $destinationRoot = $mapping[$module][1]
        Get-ChildItem -LiteralPath $sourceRoot -Recurse -File | Sort-Object FullName | ForEach-Object {
            $relativeFromSource = $_.FullName.Substring($sourceRoot.Length).TrimStart('\')
            $relativeTarget = Join-Path $destinationRoot $relativeFromSource
            if ($module -eq "system" -and $_.Name -eq "ai-context-manifest.yaml") { $relativeTarget = "00 - System\Config\ai-context-manifest.yaml" }
            $plan.Add([pscustomobject]@{ Source=$_.FullName; Relative=$relativeTarget })
        }
    }
    if ($modules.Contains("projects")) {
        Get-ChildItem -LiteralPath (Join-Path $script:StarterRoot "templates\projects") -File | Where-Object Name -ne "Projects-MOC.md" | ForEach-Object {
            $plan.Add([pscustomobject]@{ Source=$_.FullName; Relative=(Join-Path "08 - Templates\Project\Project-Folder-Template" $_.Name) })
        }
    }
    if ($modules.Contains("daily")) {
        Get-ChildItem -LiteralPath (Join-Path $script:StarterRoot "templates\daily") -File | ForEach-Object {
            $plan.Add([pscustomobject]@{ Source=$_.FullName; Relative=(Join-Path "08 - Templates\Reviews" $_.Name) })
        }
    }
    $dryManifest = [ordered]@{
        installer_version=$script:InstallerVersion; generated_at=[DateTimeOffset]::Now.ToString("o"); target=$targetRoot;
        mode=[string]$answerObject.installation.mode; directories=$directories; files=@($plan.Relative)
    }
    if ($DryRun) {
        $dryPath = Join-Path $script:StarterRoot "build\dry-run-manifest.json"
        $dryManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $dryPath -Encoding utf8
        Write-Output "Dry run complete: $dryPath"
        exit 0
    }
    $statePath = Join-Path $targetRoot "00 - System\Installation\installer-state.json"
    if ($Resume -and -not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        Stop-InputError "Resume requested but installer state was not found: $statePath"
    }
    if ($Resume -and (Test-Path -LiteralPath $statePath -PathType Leaf)) {
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
        if (-not ([System.IO.Path]::GetFullPath([string]$state.target_path).Equals($targetRoot, [System.StringComparison]::OrdinalIgnoreCase))) { Stop-InputError "Resume target mismatch." }
    } else {
        $state = [pscustomobject]@{
            installer_version=$script:InstallerVersion; start_time=[DateTimeOffset]::Now.ToString("o"); last_completed_phase=0;
            selected_mode=[string]$answerObject.installation.mode; target_path=$targetRoot; answer_file=$answerPath;
            created_files=@(); skipped_files=@(); conflicts=@(); errors=@(); validation_results=[pscustomobject]@{}; completion_status="in-progress"
        }
    }
    New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
    if ($answerObject.installation.mode -eq "migration" -and $answerObject.installation.backup_before_migration) {
        $existing = @(Get-ChildItem -LiteralPath $targetRoot -Recurse -File -Force | Where-Object { $_.FullName -notlike "*\00 - System\Installation\backups\*" })
        if ($existing.Count -gt 0) {
            $backupRoot = Join-Path $targetRoot ("00 - System\Installation\backups\" + (Get-Date -Format "yyyyMMdd-HHmmss"))
            foreach ($file in $existing) {
                $relative = $file.FullName.Substring($targetRoot.Length).TrimStart('\')
                $destination = Join-Path $backupRoot $relative
                New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
                Copy-Item -LiteralPath $file.FullName -Destination $destination
            }
            $state | Add-Member -NotePropertyName backup_path -NotePropertyValue $backupRoot -Force
        }
    }
    foreach ($relative in $directories) {
        $directory = Join-Path $targetRoot $relative
        $resolvedDirectory = [System.IO.Path]::GetFullPath($directory)
        if (-not $resolvedDirectory.StartsWith($targetNormalized + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            Stop-InputError "Directory resolves outside installation target: $resolvedDirectory"
        }
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
        if ($answerObject.installation.include_gitkeep) {
            $keep = Join-Path $directory ".gitkeep"
            if (-not (Test-Path -LiteralPath $keep -PathType Leaf)) { Set-Content -LiteralPath $keep -Value "" -Encoding utf8; $state.created_files += $keep }
        }
    }
    $state.last_completed_phase = 1
    $values = Convert-ToTemplateValues $answerObject
    $overwrite = [bool]($AllowOverwrite -or $answerObject.installation.allow_overwrite)
    foreach ($item in $plan) {
        $content = Expand-Template (Get-Content -LiteralPath $item.Source -Raw) $values
        Write-SafeFile -Path (Join-Path $targetRoot $item.Relative) -Content $content -Overwrite $overwrite -State $state
    }
    $state.last_completed_phase = 2
    if ($answerObject.installation.include_samples) {
        $samplePairs = @(
            @((Join-Path $script:StarterRoot "examples\sample-project"), (Join-Path $targetRoot "02 - Projects\Incubating\Sample Project")),
            @((Join-Path $script:StarterRoot "examples\sample-company"), (Join-Path $targetRoot "01 - Business\Companies\Example Company"))
        )
        foreach ($pair in $samplePairs) {
            if ($pair[1] -like "*\01 - Business\*" -and -not $modules.Contains("business")) { continue }
            Get-ChildItem -LiteralPath $pair[0] -Recurse -File | ForEach-Object {
                $relative = $_.FullName.Substring($pair[0].Length).TrimStart('\')
                Write-SafeFile -Path (Join-Path $pair[1] $relative) -Content (Get-Content -LiteralPath $_.FullName -Raw) -Overwrite $overwrite -State $state
            }
        }
        Write-SafeFile -Path (Join-Path $targetRoot "07 - Daily\sample-daily-workflow.md") -Content (Get-Content -LiteralPath (Join-Path $script:StarterRoot "examples\sample-daily-workflow.md") -Raw) -Overwrite $overwrite -State $state
    }
    $state.last_completed_phase = 3
    if ($answerObject.installation.initialize_git -and -not (Test-Path -LiteralPath (Join-Path $targetRoot ".git"))) {
        & git -C $targetRoot init -b main
        if ($LASTEXITCODE -ne 0) { throw "git init failed." }
    }
    if ($answerObject.installation.create_initial_commit -and -not (Test-Path -LiteralPath (Join-Path $targetRoot ".git"))) {
        Stop-InputError "create_initial_commit requires initialize_git or an existing Git repository."
    }
    $state.last_completed_phase = 4
    $validationErrors = @()
    foreach ($required in @("README.md","AGENTS.md","CLAUDE.md","CODEX.md","memory.md","handoff.md","CONTEXT-POLICY.md","TOKEN-OPTIMIZATION.md")) {
        if (-not (Test-Path -LiteralPath (Join-Path $targetRoot $required) -PathType Leaf)) { $validationErrors += "Missing file: $required" }
    }
    foreach ($required in @("00 - System","02 - Projects","06 - Inbox","07 - Daily","08 - Templates","09 - Attachments","99 - Archive")) {
        if (-not (Test-Path -LiteralPath (Join-Path $targetRoot $required) -PathType Container)) { $validationErrors += "Missing directory: $required" }
    }
    $textFiles = Get-ChildItem -LiteralPath $targetRoot -Recurse -File | Where-Object { $_.Extension -in @(".md",".json",".yaml",".yml") }
    foreach ($file in $textFiles) {
        if ((Get-Content -LiteralPath $file.FullName -Raw) -match '\{\{[a-z0-9_]+\}\}') { $validationErrors += "Unresolved template token: $($file.FullName)" }
    }
    foreach ($adapter in @("CLAUDE.md","CODEX.md")) {
        if ((Get-Content -LiteralPath (Join-Path $targetRoot $adapter)).Count -gt 40) { $validationErrors += "Adapter is not thin: $adapter" }
    }
    $registryPath = Join-Path $targetRoot "00 - System\Automations\AUTOMATION-REGISTRY.md"
    if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) { $validationErrors += "Automation registry missing." }
    elseif ((Get-Content -LiteralPath $registryPath -Raw) -notmatch 'Status: Not configured') { $validationErrors += "External automations are not explicitly unconfigured." }
    $privacyFindings = @()
    foreach ($file in $textFiles) {
        $text = Get-Content -LiteralPath $file.FullName -Raw
        if ($text -match '(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*[''"]?[A-Za-z0-9+/=_-]{12,}' -or $text -match '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----') {
            $privacyFindings += "Potential secret-like value: $($file.FullName)"
        }
    }
    $validation = [pscustomobject]@{ status=if ($validationErrors.Count -eq 0) {"PASS"} else {"FAIL"}; errors=$validationErrors }
    $privacy = [pscustomobject]@{ status=if ($privacyFindings.Count -eq 0) {"PASS"} else {"FAIL"}; findings=$privacyFindings }
    $state.validation_results = [pscustomobject]@{ validation=$validation; privacy=$privacy }
    $state.last_completed_phase = 5
    $state.completion_status = if ($validation.status -eq "PASS" -and $privacy.status -eq "PASS") { "complete" } else { "failed" }
    $reportPath = Join-Path $targetRoot "00 - System\Installation\INSTALLATION-REPORT.md"
    $conflictJson = $state.conflicts | ConvertTo-Json -Depth 6
    $validationJson = $validation.errors | ConvertTo-Json -Depth 4
    $report = @"
# Installation Report

## Result

- Installer version: $script:InstallerVersion
- Mode: $($answerObject.installation.mode)
- Target: $targetRoot
- Created: $($state.created_files.Count)
- Skipped: $($state.skipped_files.Count)
- Conflicts: $($state.conflicts.Count)
- Validation: $($validation.status)
- Privacy scan: $($privacy.status)

## First-Day Checklist

- [ ] Review ``me.md`` and remove unwanted profile fields.
- [ ] Review and approve or revise privacy classifications.
- [ ] Review ``memory.md`` and ``handoff.md``; both start as drafts.
- [ ] Open ``00 - System/Home.md`` in Obsidian.
- [ ] Process one synthetic or real Inbox item.
- [ ] Review automation definitions; external integrations remain unconfigured.
- [ ] Initialize or commit Git only after reviewing generated content.
- [ ] Keep any remote private unless every personal, business, project, daily, and attachment file is approved for publication.

## Conflicts

``````json
$conflictJson
``````

## Validation Findings

``````json
$validationJson
``````

## Exact Next Action

Review the first-day checklist, then change generated context from draft only after human approval.
"@
    New-Item -ItemType Directory -Path (Split-Path -Parent $reportPath) -Force | Out-Null
    Set-Content -LiteralPath $reportPath -Value $report -Encoding utf8
    $state | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $statePath -Encoding utf8
    if ($answerObject.installation.create_initial_commit) {
        & git -C $targetRoot add --all
        if ($LASTEXITCODE -ne 0) { throw "git add failed." }
        & git -C $targetRoot commit -m "Initialize Knowledge OS"
        if ($LASTEXITCODE -ne 0) { throw "git commit failed." }
    }
    Write-Output "Installation $($state.completion_status): $targetRoot"
    if ($state.completion_status -eq "complete") { exit 0 }
    exit 2
}
catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    if ($_.Exception -is [System.ArgumentException]) { exit 2 }
    exit 3
}
