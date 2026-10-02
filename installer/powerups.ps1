# Shared KOS Power-Up domain logic (dot-sourced, not executed directly).
#
# Provides a constrained YAML-lite reader plus registry/manifest validation
# and read-only discovery, mirroring installer/powerups.py so both engines
# stay dependency-free. Supports block mappings, block sequences (including
# sequences of mappings), flow lists (`[a, b]`/`[]`), quoted or bare scalars,
# and `#` comments. Anchors, tags, multi-line scalars, and flow mappings are
# not supported -- that scope is sufficient for registry.yaml, settings.yaml,
# and Power-Up manifest.yaml files.

$script:KosSemverPattern = '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$'
$script:KosIdPattern = '^[a-z][a-z0-9-]*$'

class KosYamlCursor {
    [System.Collections.Generic.List[object]]$Items
    [int]$Pos = 0
    KosYamlCursor([System.Collections.Generic.List[object]]$items) { $this.Items = $items }
    [object] PeekItem() {
        if ($this.Pos -lt $this.Items.Count) { return $this.Items[$this.Pos] }
        return $null
    }
    [object] NextItem() {
        $item = $this.Items[$this.Pos]
        $this.Pos++
        return $item
    }
}

function Remove-KosYamlComment {
    param([string]$Line)
    $sb = New-Object System.Text.StringBuilder
    $quote = $null
    foreach ($ch in $Line.ToCharArray()) {
        if ($quote) {
            [void]$sb.Append($ch)
            if ($ch -eq $quote) { $quote = $null }
            continue
        }
        if ($ch -eq '"' -or $ch -eq "'") { $quote = $ch; [void]$sb.Append($ch); continue }
        if ($ch -eq '#') { break }
        [void]$sb.Append($ch)
    }
    return $sb.ToString().TrimEnd()
}

function Split-KosYamlFlow {
    param([string]$Inner)
    $parts = New-Object System.Collections.Generic.List[string]
    $depth = 0
    $current = New-Object System.Text.StringBuilder
    $quote = $null
    foreach ($ch in $Inner.ToCharArray()) {
        if ($quote) {
            [void]$current.Append($ch)
            if ($ch -eq $quote) { $quote = $null }
            continue
        }
        if ($ch -eq '"' -or $ch -eq "'") { $quote = $ch; [void]$current.Append($ch); continue }
        if ($ch -eq '[' -or $ch -eq '{') { $depth++; [void]$current.Append($ch); continue }
        if ($ch -eq ']' -or $ch -eq '}') { $depth--; [void]$current.Append($ch); continue }
        if ($ch -eq ',' -and $depth -eq 0) { [void]$parts.Add($current.ToString().Trim()); [void]$current.Clear(); continue }
        [void]$current.Append($ch)
    }
    if ($current.ToString().Trim() -ne "") { [void]$parts.Add($current.ToString().Trim()) }
    return $parts
}

function ConvertTo-KosYamlScalar {
    param([string]$Token)
    $t = $Token.Trim()
    if ($t -eq "" -or $t -eq "~" -or $t.ToLowerInvariant() -eq "null") { return $null }
    if ($t.ToLowerInvariant() -eq "true") { return $true }
    if ($t.ToLowerInvariant() -eq "false") { return $false }
    if ($t.Length -ge 2 -and $t.Substring(0, 1) -eq $t.Substring($t.Length - 1, 1) -and ($t.StartsWith('"') -or $t.StartsWith("'"))) {
        return $t.Substring(1, $t.Length - 2)
    }
    if ($t -eq "[]") { return , @() }
    if ($t -eq "{}") { return [ordered]@{} }
    if ($t.StartsWith("[") -and $t.EndsWith("]")) {
        $inner = $t.Substring(1, $t.Length - 2).Trim()
        if ($inner -eq "") { return , @() }
        return , @(Split-KosYamlFlow $inner | ForEach-Object { ConvertTo-KosYamlScalar $_ })
    }
    if ($t -match '^-?\d+$') { return [int]$t }
    if ($t -match '^-?\d+\.\d+$') { return [double]$t }
    return $t
}

function Read-KosYamlNodes {
    param([KosYamlCursor]$Cursor, [int]$MinIndent)
    $peek = $Cursor.PeekItem()
    if ($null -eq $peek -or $peek.Indent -lt $MinIndent) { return $null }
    if ($peek.Content -eq "-" -or $peek.Content.StartsWith("- ")) {
        return Read-KosYamlSeq -Cursor $Cursor -Indent $peek.Indent
    }
    return Read-KosYamlMap -Cursor $Cursor -Indent $peek.Indent
}

function Read-KosYamlMap {
    param([KosYamlCursor]$Cursor, [int]$Indent, [string]$FirstKey, [object]$FirstValue, [bool]$HasFirst = $false)
    $result = [ordered]@{}
    if ($HasFirst) { $result[$FirstKey] = $FirstValue }
    while ($true) {
        $peek = $Cursor.PeekItem()
        if ($null -eq $peek -or $peek.Indent -ne $Indent) { break }
        $content = $peek.Content
        if ($content -eq "-" -or $content.StartsWith("- ")) { break }
        $colonIndex = $content.IndexOf(":")
        if ($colonIndex -lt 0) { break }
        $key = $content.Substring(0, $colonIndex).Trim().Trim('"', "'")
        if ($key -notmatch '^[A-Za-z0-9_.-]+$') { break }
        [void]$Cursor.NextItem()
        $rest = $content.Substring($colonIndex + 1).Trim()
        if ($rest -eq "") {
            $value = Read-KosYamlNodes -Cursor $Cursor -MinIndent ($Indent + 1)
            if ($null -eq $value) { $result[$key] = [ordered]@{} } else { $result[$key] = $value }
        } else {
            $result[$key] = ConvertTo-KosYamlScalar $rest
        }
    }
    return $result
}

function Read-KosYamlSeq {
    param([KosYamlCursor]$Cursor, [int]$Indent)
    $result = New-Object System.Collections.Generic.List[object]
    while ($true) {
        $peek = $Cursor.PeekItem()
        if ($null -eq $peek -or $peek.Indent -ne $Indent) { break }
        if (-not ($peek.Content -eq "-" -or $peek.Content.StartsWith("- "))) { break }
        $item = $Cursor.NextItem()
        $content = $item.Content
        $rest = if ($content -eq "-") { "" } else { $content.Substring(2) }
        if ($rest -eq "") {
            [void]$result.Add((Read-KosYamlNodes -Cursor $Cursor -MinIndent ($Indent + 1)))
            continue
        }
        $colonIndex = $rest.IndexOf(":")
        $handled = $false
        if ($colonIndex -ge 0) {
            $candidateKey = $rest.Substring(0, $colonIndex).Trim().Trim('"', "'")
            if ($candidateKey -match '^[A-Za-z0-9_.-]+$') {
                $valuePart = $rest.Substring($colonIndex + 1).Trim()
                if ($valuePart -ne "") {
                    $firstValue = ConvertTo-KosYamlScalar $valuePart
                } else {
                    $firstValue = Read-KosYamlNodes -Cursor $Cursor -MinIndent ($Indent + 3)
                }
                $entry = Read-KosYamlMap -Cursor $Cursor -Indent ($Indent + 2) -FirstKey $candidateKey -FirstValue $firstValue -HasFirst $true
                [void]$result.Add($entry)
                $handled = $true
            }
        }
        if (-not $handled) { [void]$result.Add((ConvertTo-KosYamlScalar $rest)) }
    }
    # The unary comma prevents PowerShell's pipeline from enumerating (and thus
    # unwrapping) a single-item or empty List[object] when this is captured by
    # a caller such as `$value = Read-KosYamlNodes ...`.
    return , $result
}

function ConvertFrom-KosYaml {
    param([string]$Text)
    $items = New-Object System.Collections.Generic.List[object]
    foreach ($rawLine in ($Text -split "`r?`n")) {
        $stripped = Remove-KosYamlComment $rawLine
        $trimmed = $stripped.Trim()
        if ($trimmed -eq "" -or $trimmed -eq "---") { continue }
        $indent = $stripped.Length - $stripped.TrimStart(' ').Length
        [void]$items.Add([pscustomobject]@{ Indent = $indent; Content = $trimmed })
    }
    $cursor = [KosYamlCursor]::new($items)
    $first = $cursor.PeekItem()
    if ($null -eq $first) { return [ordered]@{} }
    return Read-KosYamlNodes -Cursor $cursor -MinIndent $first.Indent
}

function ConvertTo-KosSemverTuple {
    param([string]$Value)
    $core = ($Value -split '-')[0]
    $core = ($core -split '\+')[0]
    $parts = $core -split '\.'
    return [pscustomobject]@{ Major = [int]$parts[0]; Minor = [int]$parts[1]; Patch = [int]$parts[2] }
}

function Compare-KosSemver {
    param([string]$VersionA, [string]$VersionB)
    $ta = ConvertTo-KosSemverTuple $VersionA
    $tb = ConvertTo-KosSemverTuple $VersionB
    if ($ta.Major -ne $tb.Major) { return $ta.Major.CompareTo($tb.Major) }
    if ($ta.Minor -ne $tb.Minor) { return $ta.Minor.CompareTo($tb.Minor) }
    return $ta.Patch.CompareTo($tb.Patch)
}

function Test-KosPowerUpRegistry {
    param([object]$Registry)
    $errors = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]
    if ($null -eq $Registry -or -not ($Registry -is [System.Collections.IDictionary])) {
        [void]$errors.Add("registry.yaml did not parse to a mapping")
        return [pscustomobject]@{ Errors = $errors; Warnings = $warnings }
    }
    if (-not $Registry["schema_version"]) { [void]$errors.Add("registry.schema_version is required") }
    $entries = $Registry["power_ups"]
    if ($null -eq $entries) {
        [void]$errors.Add("registry.power_ups must be present (use [] when empty)")
        $entries = @()
    }
    $seenIds = New-Object System.Collections.Generic.HashSet[string]
    # Do not wrap $entries in @(...): PowerShell 5.1 throws "Argument types do
    # not match" re-wrapping a List[object] whose elements are [ordered]@{}
    # maps. Plain `foreach` over the List[object] directly is safe.
    foreach ($entry in $entries) {
        if (-not ($entry -is [System.Collections.IDictionary])) {
            [void]$errors.Add("registry entry is not a mapping")
            continue
        }
        $entryId = [string]$entry["id"]
        if (-not $entryId -or $entryId -notmatch $script:KosIdPattern) {
            [void]$errors.Add("registry entry has an invalid id: '$entryId'")
        } elseif ($seenIds.Contains($entryId)) {
            [void]$errors.Add("duplicate Power-Up id in registry: $entryId")
        } else {
            [void]$seenIds.Add($entryId)
        }
        $version = [string]$entry["version"]
        if (-not $version -or $version -notmatch $script:KosSemverPattern) {
            [void]$errors.Add("registry entry '$entryId' has an invalid version: '$version'")
        }
        $status = [string]$entry["status"]
        if ($status -notin @("enabled", "disabled")) {
            [void]$errors.Add("registry entry '$entryId' has an invalid status: '$status'")
        }
        $mode = [string]$entry["installation_mode"]
        if ($mode -notin @("external", "embedded")) {
            [void]$errors.Add("registry entry '$entryId' has an invalid installation_mode: '$mode'")
        }
        if (-not $entry["manifest"]) { [void]$errors.Add("registry entry '$entryId' is missing a manifest path") }
        if (-not $entry["install_path"]) { [void]$warnings.Add("registry entry '$entryId' has no install_path recorded") }
    }
    return [pscustomobject]@{ Errors = $errors; Warnings = $warnings }
}

function Test-KosPowerUpManifest {
    param([object]$Manifest, [string]$KosVersion)
    $errors = New-Object System.Collections.Generic.List[string]
    $warnings = New-Object System.Collections.Generic.List[string]
    if ($null -eq $Manifest -or -not ($Manifest -is [System.Collections.IDictionary])) {
        [void]$errors.Add("manifest.yaml did not parse to a mapping")
        return [pscustomobject]@{ Errors = $errors; Warnings = $warnings }
    }
    if (-not $Manifest["schema_version"]) { [void]$errors.Add("manifest.schema_version is required") }
    $manifestId = [string]$Manifest["id"]
    if (-not $manifestId -or $manifestId -notmatch $script:KosIdPattern) {
        [void]$errors.Add("manifest.id must be a lowercase, hyphenated identifier")
    }
    $version = [string]$Manifest["version"]
    if (-not $version -or $version -notmatch $script:KosSemverPattern) {
        [void]$errors.Add("manifest.version must be a semantic version (MAJOR.MINOR.PATCH)")
    }
    $compat = $Manifest["kos_compatibility"]
    if ($null -eq $compat) { $compat = [ordered]@{} }
    $minimum = [string]$compat["minimum_version"]
    if (-not $minimum -or $minimum -notmatch $script:KosSemverPattern) {
        [void]$errors.Add("manifest.kos_compatibility.minimum_version must be a semantic version")
    }
    $maximum = $compat["maximum_version"]
    $maximumText = if ($null -eq $maximum) { "" } else { [string]$maximum }
    if ($maximumText -ne "" -and $maximumText -notmatch $script:KosSemverPattern) {
        [void]$errors.Add("manifest.kos_compatibility.maximum_version must be null or a semantic version")
    }
    if ($KosVersion -and $KosVersion -match $script:KosSemverPattern -and $minimum -match $script:KosSemverPattern) {
        if ((Compare-KosSemver $KosVersion $minimum) -lt 0) {
            [void]$errors.Add("installed KOS $KosVersion is older than the Power-Up's minimum $minimum")
        }
        if ($maximumText -match $script:KosSemverPattern -and (Compare-KosSemver $KosVersion $maximumText) -gt 0) {
            [void]$errors.Add("installed KOS $KosVersion is newer than the Power-Up's maximum $maximumText")
        }
    }
    $installation = $Manifest["installation"]
    if ($null -eq $installation) { $installation = [ordered]@{} }
    # Do not wrap a parsed List[object] in @(...) -- see the note above Test-KosPowerUpRegistry's foreach.
    $supportedModes = $installation["supported_modes"]
    if ($null -eq $supportedModes -or $supportedModes.Count -eq 0) {
        [void]$errors.Add("manifest.installation.supported_modes must declare at least one mode")
        $supportedModes = New-Object System.Collections.Generic.List[object]
    }
    foreach ($mode in $supportedModes) {
        if ($mode -notin @("external", "embedded")) {
            [void]$errors.Add("manifest.installation.supported_modes has an unsupported mode: $mode")
        }
    }
    $defaultMode = $installation["default_mode"]
    if ($defaultMode -and $supportedModes.Count -gt 0 -and ($defaultMode -notin $supportedModes)) {
        [void]$errors.Add("manifest.installation.default_mode must be one of supported_modes")
    }
    $agents = $Manifest["agents"]
    if ($null -eq $agents) { $agents = [ordered]@{} }
    if (-not $agents["canonical_skill"]) { [void]$warnings.Add("manifest.agents.canonical_skill is not declared") }
    $permissions = $Manifest["permissions"]
    if (-not ($permissions -is [System.Collections.IDictionary]) -or -not $permissions.Contains("read") -or -not $permissions.Contains("write")) {
        [void]$errors.Add("manifest.permissions must declare read and write locations")
    } else {
        $canonicalWrites = $permissions["canonical_kos_writes"]
        if ($null -eq $canonicalWrites) { $canonicalWrites = [ordered]@{} }
        $allowed = [bool]$canonicalWrites["allowed"]
        $requiresApproval = $canonicalWrites["requires_explicit_approval"]
        $requiresApprovalValue = if ($null -eq $requiresApproval) { $true } else { [bool]$requiresApproval }
        if ($allowed -and -not $requiresApprovalValue) {
            [void]$errors.Add("manifest.permissions.canonical_kos_writes.allowed requires requires_explicit_approval: true")
        }
    }
    $lifecycle = $Manifest["lifecycle"]
    if ($null -eq $lifecycle) { $lifecycle = [ordered]@{} }
    foreach ($command in @("install_command", "initialize_command", "upgrade_command", "uninstall_command")) {
        if (-not $lifecycle[$command]) { [void]$warnings.Add("manifest.lifecycle.$command is not declared") }
    }
    return [pscustomobject]@{ Errors = $errors; Warnings = $warnings }
}

function ConvertTo-KosYamlScalarText {
    param([object]$Value)
    if ($Value -is [bool]) { return $(if ($Value) { "true" } else { "false" }) }
    if ($null -eq $Value) { return "null" }
    if ($Value -is [int] -or $Value -is [double]) { return [string]$Value }
    $text = [string]$Value
    if ($text -eq "" -or $text -eq "true" -or $text -eq "false" -or $text -eq "null" -or ($text -match '[:#\[\]{}]') -or ($text -match '^\s') -or ($text -match '\s$')) {
        $escaped = $text.Replace('\', '\\').Replace('"', '\"')
        return '"' + $escaped + '"'
    }
    return $text
}

function Format-KosPowerUpRegistryEntry {
    param([System.Collections.Specialized.OrderedDictionary]$Entry)
    $order = @("id", "name", "version", "status", "installation_mode", "install_path", "manifest", "initialized_targets", "installed_at", "updated_at")
    $lines = New-Object System.Collections.Generic.List[string]
    $first = $true
    foreach ($key in $order) {
        if (-not $Entry.Contains($key)) { continue }
        $prefix = if ($first) { "  - " } else { "    " }
        $first = $false
        $value = $Entry[$key]
        if ($key -eq "initialized_targets") {
            $items = @($value)
            if ($items.Count -eq 0) {
                [void]$lines.Add("$prefix$key`: []")
            } else {
                [void]$lines.Add("$prefix$key`:")
                foreach ($item in $items) { [void]$lines.Add("      - $(ConvertTo-KosYamlScalarText $item)") }
            }
        } else {
            [void]$lines.Add("$prefix$key`: $(ConvertTo-KosYamlScalarText $value)")
        }
    }
    return ($lines -join "`n") + "`n"
}

function Register-KosPowerUp {
    param([string]$RegistryPath, [System.Collections.Specialized.OrderedDictionary]$Entry)
    $text = Get-Content -LiteralPath $RegistryPath -Raw
    $registry = ConvertFrom-KosYaml $text
    $existingIds = @()
    $existingEntries = $registry["power_ups"]
    if ($null -ne $existingEntries) {
        foreach ($item in $existingEntries) {
            if ($item -is [System.Collections.IDictionary]) { $existingIds += [string]$item["id"] }
        }
    }
    if ($existingIds -contains $Entry["id"]) {
        throw "Power-Up '$($Entry["id"])' is already registered; registration does not overwrite entries"
    }
    $block = Format-KosPowerUpRegistryEntry $Entry
    $match = [regex]::Match($text, '(?m)^power_ups:\s*\[\]\s*$')
    if ($match.Success) {
        $newText = $text.Substring(0, $match.Index) + "power_ups:`n" + $block.TrimEnd("`n") + $text.Substring($match.Index + $match.Length)
    } else {
        $newText = $text.TrimEnd("`r", "`n") + "`n" + $block
    }
    Set-Content -LiteralPath $RegistryPath -Value $newText -Encoding utf8 -NoNewline
}

function Find-KosPowerUps {
    param([string]$HomeDirectory, [string[]]$RegisteredIds, [string]$KosVersion)
    $candidates = New-Object System.Collections.Generic.List[object]
    if (-not $HomeDirectory -or -not (Test-Path -LiteralPath $HomeDirectory -PathType Container)) {
        return , $candidates
    }
    $seenIds = @{}
    Get-ChildItem -LiteralPath $HomeDirectory -Directory | Sort-Object Name | ForEach-Object {
        $entryDir = $_
        $manifestPath = Join-Path $entryDir.FullName "manifest.yaml"
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return }
        $report = [ordered]@{ Path = $entryDir.FullName; ManifestPath = $manifestPath }
        try {
            $manifest = ConvertFrom-KosYaml (Get-Content -LiteralPath $manifestPath -Raw)
        } catch {
            $report.Status = "ERROR"
            $report.Errors = @("manifest.yaml failed to parse: $($_.Exception.Message)")
            $report.Warnings = @()
            $report.Manifest = $null
            $report.Id = $null
            $report.Version = $null
            [void]$candidates.Add([pscustomobject]$report)
            return
        }
        $result = Test-KosPowerUpManifest -Manifest $manifest -KosVersion $KosVersion
        # $result.Errors/.Warnings are already List[string]; do not re-wrap in
        # @(...) -- AddRange then fails to bind to IEnumerable[string].
        $errors = New-Object System.Collections.Generic.List[string]
        $errors.AddRange($result.Errors)
        $warnings = New-Object System.Collections.Generic.List[string]
        $warnings.AddRange($result.Warnings)
        $powerUpId = [string]$manifest["id"]
        $lifecycle = $manifest["lifecycle"]
        if ($lifecycle -is [System.Collections.IDictionary]) {
            foreach ($key in $lifecycle.Keys) {
                $commandPath = $lifecycle[$key]
                if ($commandPath -and -not (Test-Path -LiteralPath (Join-Path $entryDir.FullName $commandPath) -PathType Leaf)) {
                    [void]$warnings.Add("lifecycle.$key points to a missing file: $commandPath")
                }
            }
        }
        if ($powerUpId -and $seenIds.ContainsKey($powerUpId)) {
            [void]$errors.Add("duplicate Power-Up id discovered at '$($entryDir.FullName)' and '$($seenIds[$powerUpId])'")
        } elseif ($powerUpId) {
            $seenIds[$powerUpId] = $entryDir.FullName
        }
        if ($powerUpId -and $RegisteredIds -contains $powerUpId) {
            [void]$warnings.Add("'$powerUpId' is already registered; discovery will not overwrite it")
        }
        $report.Manifest = $manifest
        $report.Id = $powerUpId
        $report.Version = [string]$manifest["version"]
        $report.Permissions = $manifest["permissions"]
        $report.Errors = $errors
        $report.Warnings = $warnings
        $report.Status = if ($errors.Count -gt 0) { "ERROR" } elseif ($warnings.Count -gt 0) { "WARNING" } else { "PASS" }
        [void]$candidates.Add([pscustomobject]$report)
    }
    # Unary comma: see the note in Read-KosYamlSeq -- without it, a single
    # discovered candidate collapses from a 1-item list to the bare item.
    return , $candidates
}
