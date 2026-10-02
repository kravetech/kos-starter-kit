# Native PowerShell 5.1/7 engine. Shared assets, schemas and version contract.
Set-StrictMode -Version 2
$script:KosRoot = Split-Path -Parent $PSScriptRoot
$script:KosState = '00 - System/Installation/kos-installation.json'
$script:KosRuns = '00 - System/Installation/Runs'
$script:KosCaps = '00 - System/Config/capabilities.json'
$script:Utf8 = New-Object System.Text.UTF8Encoding($false)

function Convert-KosObject($Value) {
    if ($null -eq $Value) { return $null }
    if ($Value -is [string] -or $Value -is [ValueType]) { return $Value }
    if ($Value -is [System.Collections.IDictionary]) { return $Value }
    if ($Value -is [array]) { return ,@($Value | ForEach-Object { Convert-KosObject $_ }) }
    if ($Value -is [pscustomobject]) {
        $map = @{}
        foreach ($p in $Value.PSObject.Properties) { $map[$p.Name] = Convert-KosObject $p.Value }
        return $map
    }
    return $Value
}
function Convert-KosJson([string]$Text) {
    # Validate syntax first, then reject duplicate/case-colliding object keys.
    $parsed=$Text | ConvertFrom-Json
    $stack=New-Object System.Collections.Generic.Stack[object]
    $tokens=[regex]::Matches($Text,'"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+')
    for($i=0;$i -lt $tokens.Count;$i++){
        $token=$tokens[$i].Value
        if($token -eq '{'){$stack.Push(@{kind='object';keys=@{}})}
        elseif($token -eq '['){$stack.Push(@{kind='array'})}
        elseif($token -in @('}',']')){$null=$stack.Pop()}
        elseif($token.StartsWith('"') -and $i+1 -lt $tokens.Count -and $tokens[$i+1].Value -eq ':'){
            $key=($token | ConvertFrom-Json);$object=$stack.Peek()
            if($object.keys.Contains($key)){throw 'JSON_DUPLICATE_KEY'};$object.keys[$key]=$true
        }
    }
    return Convert-KosObject $parsed
}
function Read-KosJson([string]$Path) { return Convert-KosJson ([IO.File]::ReadAllText($Path, $script:Utf8)) }
function Get-KosJson($Value, [int]$Depth = 0) {
    if ($null -eq $Value) { return 'null' }
    if ($Value -is [bool]) { return $Value.ToString().ToLowerInvariant() }
    if ($Value -is [string]) {
        $escaped = [regex]::Replace($Value, '[\x00-\x1f"\\]', {
            param($m)
            switch ([int][char]$m.Value) {
                34 { '\"'; break } 92 { '\\'; break } 8 { '\b'; break }
                9 { '\t'; break } 10 { '\n'; break } 12 { '\f'; break } 13 { '\r'; break }
                default { '\u{0:x4}' -f [int][char]$m.Value }
            }
        })
        return '"' + $escaped + '"'
    }
    $pad = '  ' * $Depth; $inner = '  ' * ($Depth + 1)
    if ($Value -is [System.Collections.IDictionary]) {
        if ($Value.psbase.Count -eq 0) { return '{}' }
        $keys = [string[]]@($Value.psbase.Keys); [Array]::Sort($keys, [StringComparer]::Ordinal)
        $lines = @($keys | ForEach-Object { $inner + (Get-KosJson ([string]$_)) + ': ' + (Get-KosJson $Value[$_] ($Depth + 1)) })
        return "{`n" + ($lines -join ",`n") + "`n$pad}"
    }
    if ($Value -is [array] -or $Value -is [System.Collections.IList]) {
        if ($Value.Count -eq 0) { return '[]' }
        $lines = @($Value | ForEach-Object { $inner + (Get-KosJson $_ ($Depth + 1)) })
        return "[`n" + ($lines -join ",`n") + "`n$pad]"
    }
    return [Convert]::ToString($Value, [Globalization.CultureInfo]::InvariantCulture)
}
function Get-KosBytes($Value) { return ,$script:Utf8.GetBytes((Get-KosJson $Value) + "`n") }
function Get-KosHash([byte[]]$Bytes) {
    $hash = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($Bytes))).Replace('-','').ToLowerInvariant() } finally { $hash.Dispose() }
}
function Get-KosTextHashes([string]$Text) {
    $hashes=@()
    foreach($ending in @("`n","`r`n")){foreach($extra in @('',"`n","`r`n")){
        $raw=$script:Utf8.GetBytes($Text.Replace("`r`n","`n").Replace("`n",$ending)+$extra)
        $hashes+=@(Get-KosHash $raw);$hashes+=@(Get-KosHash ([byte[]](@(239,187,191)+$raw)))
    }}
    return ,$hashes
}
function Test-KosLink([string]$Path) {
    try { return ([IO.File]::GetAttributes($Path) -band [IO.FileAttributes]::ReparsePoint) -ne 0 }
    catch [IO.FileNotFoundException] { return $false }
    catch [IO.DirectoryNotFoundException] { return $false }
}
function Test-KosRelative([string]$Relative) {
    if (-not $Relative -or $Relative.Contains('\') -or $Relative.StartsWith('/')) { throw 'PATH_INVALID' }
    foreach ($part in $Relative.Split('/')) {
        if (-not $part -or $part -in @('.','..') -or $part -match '[ .]$|[\x00-\x1f:<>"|?*]' -or $part -match '^(?i:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\.|$)') { throw 'PATH_RESERVED' }
    }
}
function Get-KosSafe([string]$Root, [string]$Relative = '') {
    if ($Relative) { Test-KosRelative $Relative }
    $path = if ($Relative) { [IO.Path]::GetFullPath((Join-Path $Root $Relative)) } else { [IO.Path]::GetFullPath($Root) }
    $node = $path
    while ($node) {
        if (Test-KosLink $node) { throw 'PATH_LINK' }
        if ($node -ne $path -and (Test-Path -LiteralPath $node) -and -not (Test-Path -LiteralPath $node -PathType Container)) { throw 'PATH_PARENT_FILE' }
        $parent = Split-Path -Parent $node
        if ($parent -eq $node) { break }; $node = $parent
    }
    return $path
}
function Get-KosTarget([string]$Root) {
    $path = Get-KosSafe $Root
    $source = [IO.Path]::GetFullPath($script:KosRoot).TrimEnd('\','/')
    $normalized = $path.TrimEnd('\','/')
    if ($normalized -eq [IO.Path]::GetPathRoot($path).TrimEnd('\','/') -or $normalized -eq $env:USERPROFILE -or $normalized -eq $source -or $source.StartsWith($normalized + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'TARGET_UNSAFE_OR_SOURCE' }
    if ((Test-Path -LiteralPath $path) -and -not (Test-Path -LiteralPath $path -PathType Container)) { throw 'TARGET_NOT_DIRECTORY' }
    $local = Join-Path $script:KosRoot 'installer/local-config.json'
    if (Test-Path -LiteralPath $local) {
        $config = Read-KosJson $local
        foreach ($item in @($config['protected_paths']) + @($config['reference_paths'])) {
            if (-not $item) { continue }
            $protected = [IO.Path]::GetFullPath($item).TrimEnd('\','/')
            if ($normalized -eq $protected -or $normalized.StartsWith($protected + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or $protected.StartsWith($normalized + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'TARGET_PROTECTED' }
        }
    }
    return $path
}
function Get-KosInventory([string]$Root, [string[]]$Excluded=@()) {
    $null = Get-KosSafe $Root
    $result = New-Object System.Collections.Generic.List[object]
    if (-not (Test-Path -LiteralPath $Root)) { return ,@() }
    $pending = New-Object System.Collections.Generic.Stack[string]; $pending.Push($Root)
    while ($pending.Count) {
        $parent = $pending.Pop(); $null = Get-KosSafe $parent
        foreach ($file in Get-ChildItem -LiteralPath $parent -Force) {
            if($file.Name -in $Excluded){continue}
            $rel = $file.FullName.Substring($Root.TrimEnd('\','/').Length + 1).Replace('\','/')
            if (Test-KosLink $file.FullName) { $result.Add(@{path=$rel;kind='link';ownership='user-owned'}) }
            elseif ($file.PSIsContainer) {
                $result.Add(@{path=$rel;kind='directory'})
                if ($rel -notin @('.git',$script:KosRuns)) { $pending.Push($file.FullName) }
            } else { $result.Add(@{path=$rel;kind='file';hash=(Get-KosHash ([IO.File]::ReadAllBytes((Get-KosSafe $Root $rel))))}) }
        }
    }
    return ,@($result | Sort-Object { $_.path })
}
function New-KosLinkIndex($Paths) {
    $byPath=@{};$byName=@{}
    foreach($rel in @($Paths | Sort-Object -CaseSensitive)) {
        $pathKey=$rel.ToLowerInvariant()
        if(-not $byPath.ContainsKey($pathKey)){$byPath[$pathKey]=New-Object System.Collections.Generic.List[string]}
        $byPath[$pathKey].Add($rel)
        $name=if([IO.Path]::GetExtension($rel).ToLowerInvariant() -eq '.md'){[IO.Path]::GetFileNameWithoutExtension($rel)}else{[IO.Path]::GetFileName($rel)}
        $nameKey=$name.ToLowerInvariant()
        if(-not $byName.ContainsKey($nameKey)){$byName[$nameKey]=New-Object System.Collections.Generic.List[string]}
        $byName[$nameKey].Add($rel)
    }
    return @{path=$byPath;name=$byName}
}
function Get-KosNormalizedLink([string]$Value) {
    $parts=New-Object System.Collections.Generic.List[string]
    foreach($part in $Value.Split('/')){
        if($part -in @('','.')){continue}
        if($part -eq '..'){
            if($parts.Count -eq 0){return $null}
            $parts.RemoveAt($parts.Count-1)
        }else{$parts.Add($part)}
    }
    return ($parts -join '/')
}
function Get-KosLinkCandidates($Index,[string]$Source,[string]$Raw,[string]$Kind) {
    $target=($Raw -split '\|',2)[0];$target=($target -split '#',2)[0].Trim()
    if($Kind -eq 'markdown'){
        $target=$target.Trim('<','>');$target=($target -split '\?',2)[0]
        $target=[Uri]::UnescapeDataString($target)
    }
    if(-not $target -or $target.Contains('\') -or $target -match '^[A-Za-z][A-Za-z0-9+.-]*:|^//'){return ,@()}
    $explicit=$target.Contains('/')
    $suffix=if([IO.Path]::GetExtension($target)){''}else{'.md'}
    if($Kind -eq 'wiki' -and -not $explicit){
        $name=if($target.EndsWith('.md',[StringComparison]::OrdinalIgnoreCase)){$target.Substring(0,$target.Length-3)}else{$target}
        $key=$name.ToLowerInvariant()
        return ,@(if($Index.name.ContainsKey($key)){$Index.name[$key].ToArray()})
    }
    $sourceDir=($Source -split '/') | Select-Object -SkipLast 1
    $sourceDir=$sourceDir -join '/'
    if($Kind -eq 'wiki' -or $target.StartsWith('/')){$candidates=@($target.TrimStart('/'))}
    elseif($explicit -and -not $target.StartsWith('./') -and -not $target.StartsWith('../')){$candidates=@($target,($sourceDir+'/'+$target))}
    else{$candidates=@(($sourceDir+'/'+$target),$target)}
    foreach($candidate in $candidates){
        $normalized=Get-KosNormalizedLink ($candidate+$suffix)
        if($null -ne $normalized -and $Index.path.ContainsKey($normalized.ToLowerInvariant())){
            return ,@($Index.path[$normalized.ToLowerInvariant()].ToArray() | Sort-Object -CaseSensitive)
        }
    }
    return ,@()
}
function Get-KosLinkAudit([string]$Root,$Files,$Items) {
    $existing=@($Files | Where-Object {$_.kind -eq 'file'} | ForEach-Object {$_.path})
    if($existing.Count -gt 20000){throw 'LINK_SCAN_LIMIT'}
    $known=@{};foreach($rel in $existing){$known[$rel]=$true}
    $added=@($Items | Where-Object {$_.action -eq 'CREATE' -and -not $known.ContainsKey($_.path)} | ForEach-Object {$_.path})
    $before=New-KosLinkIndex $existing;$after=New-KosLinkIndex @($existing+$added)
    $rewritten=@{};foreach($item in $Items){if($item.action -in @('UPDATE_SAFE','UPDATE_APPROVED','MERGE')){$rewritten[$item.path]=$true}}
    $notes=@($existing | Where-Object {$_.EndsWith('.md',[StringComparison]::OrdinalIgnoreCase) -and -not $rewritten.ContainsKey($_)} | Sort-Object -CaseSensitive)
    if($notes.Count -gt 10000){throw 'LINK_SCAN_LIMIT'}
    $collisions=@($after.name.psbase.Keys | Where-Object {$after.name[$_].Count -gt 1 -and (-not $before.name.ContainsKey($_) -or $before.name[$_].Count -le 1)} | Sort-Object -CaseSensitive)
    $audit=@{scannedMarkdownFiles=$notes.Count;references=0;preexistingUnresolved=0;preexistingAmbiguous=0;newBasenameCollisions=$collisions;regressions=@()}
    $regressions=New-Object System.Collections.Generic.List[object];$seen=@{}
    foreach($rel in $notes){
        $path=Get-KosSafe $Root $rel
        if((Get-Item -LiteralPath $path).Length -gt 1048576){throw 'LINK_SCAN_LIMIT'}
        $content=[IO.File]::ReadAllText($path,$script:Utf8)
        $content=[regex]::Replace($content,'(?ms)^```.*?^```[^\r\n]*','')
        $content=[regex]::Replace($content,'`+[^`\r\n]*`+','')
        foreach($match in [regex]::Matches($content,'!?\[\[([^\]\r\n]+)\]\]|!?\[[^\]\r\n]*\]\((<[^>\r\n]*>|[^)\r\n]+)\)')){
            $kind=if($match.Groups[1].Success){'wiki'}else{'markdown'}
            $target=if($kind -eq 'wiki'){$match.Groups[1].Value}else{$match.Groups[2].Value}
            $old=Get-KosLinkCandidates $before $rel $target $kind;$new=Get-KosLinkCandidates $after $rel $target $kind
            $audit.references++
            if($audit.references -gt 50000){throw 'LINK_SCAN_LIMIT'}
            if($old.Count -eq 0){$audit.preexistingUnresolved++}
            elseif($old.Count -gt 1){$audit.preexistingAmbiguous++}
            elseif(($old -join "`n") -cne ($new -join "`n")){
                $key=$rel+"`n"+$kind+"`n"+$target
                if(-not $seen.ContainsKey($key)){$regressions.Add(@{source=$rel;kind=$kind;target=$target});$seen[$key]=$true}
            }
        }
    }
    $audit.regressions=@($regressions | Sort-Object @{Expression={$_.source}},@{Expression={$_.kind}},@{Expression={$_.target}})
    return $audit
}
function Get-KosCurrent([string]$Root, [string]$Relative) {
    $path = Get-KosSafe $Root $Relative
    if (Test-Path -LiteralPath $path -PathType Container) { throw 'PATH_NOT_FILE' }
    if (Test-Path -LiteralPath $path -PathType Leaf) { return Get-KosHash ([IO.File]::ReadAllBytes($path)) }
    return $null
}
function Merge-KosExisting($Defaults, $Existing) {
    if ($Defaults -is [System.Collections.IDictionary] -and $Existing -is [System.Collections.IDictionary]) {
        $result = @{}; foreach ($key in $Existing.psbase.Keys) { $result[$key] = $Existing[$key] }
        foreach ($key in $Defaults.psbase.Keys) {
            if ($Existing.Contains($key)) { $result[$key] = Merge-KosExisting $Defaults[$key] $Existing[$key] } else { $result[$key] = $Defaults[$key] }
        }
        return $result
    }
    if (($Defaults -is [array]) -ne ($Existing -is [array]) -or ($Defaults -is [bool]) -ne ($Existing -is [bool]) -or ($Defaults -is [string]) -ne ($Existing -is [string])) { throw 'CONFIG_TYPE_CONFLICT' }
    return ,$Existing
}
function Test-KosSchema($Value, $Schema, [string]$Location = '$') {
    $supported=@('$schema','$id','title','description','default','examples','deprecated','type','required','properties','additionalProperties','enum','const','items','uniqueItems','minItems','maxItems','pattern','minLength','maxLength','minimum','maximum','format')
    foreach($key in $Schema.psbase.Keys){if($key -notin $supported){throw "SCHEMA_UNSUPPORTED_KEYWORD:$Location"}}
    $type = $Schema['type']; $valid = $true
    switch ($type) {
        'object' { $valid = $Value -is [System.Collections.IDictionary] }
        'array' { $valid = $Value -is [array] }
        'string' { $valid = $Value -is [string] }
        'boolean' { $valid = $Value -is [bool] }
        'integer' { $valid = $Value -is [int] -or $Value -is [long] -or $Value -is [bigint] }
        'number' { $valid = $Value -is [int] -or $Value -is [long] -or $Value -is [double] -or $Value -is [decimal] }
        'null' { $valid = $null -eq $Value }
        default {if($type){$valid=$false}}
    }
    if (-not $valid) { throw "SCHEMA_TYPE:$Location" }
    if ($Schema.Contains('const') -and (Get-KosJson $Value) -cne (Get-KosJson $Schema['const'])) { throw "SCHEMA_CONST:$Location" }
    if ($Schema.Contains('enum') -and $Value -cnotin $Schema['enum']) { throw "SCHEMA_ENUM:$Location" }
    if ($Value -is [System.Collections.IDictionary]) {
        foreach ($key in $Schema['required']) { if (-not $Value.Contains($key)) { throw "SCHEMA_REQUIRED:$Location.$key" } }
        foreach ($key in $Value.psbase.Keys) {
            if ($Schema['properties'] -and $Schema['properties'].Contains($key)) { Test-KosSchema $Value[$key] $Schema['properties'][$key] "$Location.$key" }
            elseif ($Schema.Contains('additionalProperties') -and $Schema['additionalProperties'] -eq $false) { throw "SCHEMA_UNKNOWN:$Location" }
            elseif ($Schema['additionalProperties'] -is [System.Collections.IDictionary]) { Test-KosSchema $Value[$key] $Schema['additionalProperties'] "$Location.$key" }
        }
    }
    if ($Value -is [array]) {
        if ($Schema['minItems'] -and $Value.Count -lt $Schema['minItems']) { throw "SCHEMA_ARRAY_EMPTY:$Location" }
        if ($Schema.Contains('maxItems') -and $Value.Count -gt $Schema['maxItems']) { throw "SCHEMA_ARRAY_LENGTH:$Location" }
        foreach ($item in $Value) { if ($Schema['items']) { Test-KosSchema $item $Schema['items'] "$Location[]" } }
        if ($Schema['uniqueItems'] -and @($Value | ForEach-Object { Get-KosJson $_ } | Select-Object -Unique).Count -ne $Value.Count) { throw "SCHEMA_DUPLICATE:$Location" }
    }
    if ($Value -is [string] -and (($Schema['pattern'] -and $Value -cnotmatch $Schema['pattern']) -or $Value.Length -lt $Schema['minLength'])) { throw "SCHEMA_STRING:$Location" }
    if($Value -is [string]){
        if($Schema.Contains('maxLength') -and $Value.Length -gt $Schema['maxLength']){throw "SCHEMA_STRING:$Location"}
        if($Schema.Contains('format')){
            if($Schema['format'] -ne 'date'){throw "SCHEMA_UNSUPPORTED_FORMAT:$Location"}
            $dateValue=[DateTime]::MinValue
            if(-not [DateTime]::TryParseExact($Value,'yyyy-MM-dd',[Globalization.CultureInfo]::InvariantCulture,[Globalization.DateTimeStyles]::None,[ref]$dateValue)){throw "SCHEMA_DATE:$Location"}
        }
    }
    if($Value -is [ValueType] -and $Value -isnot [bool]){
        if(($Schema.Contains('minimum') -and $Value -lt $Schema['minimum']) -or ($Schema.Contains('maximum') -and $Value -gt $Schema['maximum'])){throw "SCHEMA_NUMBER_RANGE:$Location"}
    }
}
function Assert-KosSchema([string]$Name, $Value) { Test-KosSchema $Value (Read-KosJson (Join-Path $PSScriptRoot "schemas/$Name.schema.json")) }
$script:KosRelease = Read-KosJson (Join-Path $PSScriptRoot 'release.json')
function Get-KosCanonicalEdition([string]$Edition) {
    if($Edition -eq 'starter'){return 'community'}
    if($Edition -eq 'core'){return 'pro'}
    return $Edition
}
function Get-KosState([string]$Root) {
    $path = Get-KosSafe $Root $script:KosState
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $state = Read-KosJson $path; Assert-KosSchema 'installation' $state
    if ((Get-KosCanonicalEdition $state['edition']) -ne 'community') { throw 'EDITION_UNSUPPORTED' }
    if ($state['starterKitVersion'] -notin $script:KosRelease['supportedUpgradeVersions'] -or [version]$state['kosContractVersion'] -gt [version]$script:KosRelease['kosContractVersion']) { throw 'VERSION_UNSUPPORTED_OR_DOWNGRADE' }
    if ($state['communityVersion'] -and [version]$state['communityVersion'] -gt [version]$script:KosRelease['communityVersion']) { throw 'COMMUNITY_DOWNGRADE' }
    foreach ($rel in $state['components'].psbase.Keys) { Test-KosRelative $rel; Assert-KosSchema 'asset' $state['components'][$rel]; if ($state['components'][$rel]['path'] -cne $rel) { throw 'ASSET_PATH_MISMATCH' } }
    return $state
}
function Get-KosDetection([string]$Root, $Files) {
    if (-not (Test-Path -LiteralPath $Root)) { return 'new-target' }
    if ($Files.Count -eq 0) { return 'empty-directory' }
    $names = @($Files | Where-Object { $_.kind -ne 'link' } | ForEach-Object { $_.path })
    $proVersion = '00 - System/Core/version.json'
    if ($proVersion -in $names) {
        $record = Read-KosJson (Get-KosSafe $Root $proVersion)
        if ($record -isnot [System.Collections.IDictionary]) { throw 'VERSION_RECORD_INVALID' }
        if ($record['product_id'] -eq 'kos-pro' -or (Get-KosCanonicalEdition $record['edition']) -eq 'pro') { return 'pro-kos' }
    }
    if ($script:KosState -in $names) { return 'managed-kos' }
    if ('00 - System/Installation/installer-state.json' -in $names -or ('AGENTS.md' -in $names -and 'CONTEXT-POLICY.md' -in $names -and '00 - System' -in $names)) { return 'legacy-kos' }
    if ('.obsidian' -in $names) { return 'obsidian-vault' }; return 'ambiguous-mixed'
}
function Get-KosEvidence([string]$Root, $Files) {
    $found = @{}
    foreach ($file in $Files) {
        $rel = $file.path
        if ($file.kind -ne 'file' -or -not $rel.EndsWith('.json') -or $rel -eq $script:KosState) { continue }
        try {
            $path = Get-KosSafe $Root $rel
            if ((Get-Item -LiteralPath $path).Length -gt 1MB) { continue }
            $data = Read-KosJson $path
            if ($data -isnot [System.Collections.IDictionary]) { continue }
            $manifestCap=if($data['schema'] -eq 'kos-skill/v1'){'kos.skills.runtime'}elseif($data['schema'] -eq 'kos-powerup/v1'){'kos.powerups.runtime'}else{''}
            if($manifestCap){
                $entries=if($data['entrypoints']){$data['entrypoints']}elseif($data['entrypoint']){@($data['entrypoint'])}else{@('SKILL.md')}
                $parent=($rel -split '/' | Select-Object -SkipLast 1) -join '/';$paths=@();$valid=$true
                foreach($entry in $entries){$candidate=if($parent){$parent+'/'+$entry}else{$entry};$paths+=@($candidate);try{if(-not (Test-Path -LiteralPath (Get-KosSafe $Root $candidate) -PathType Leaf)){$valid=$false}}catch{$valid=$false}}
                if(-not $found.Contains($manifestCap)){$found[$manifestCap]=@()};$found[$manifestCap]+=@{source=$rel;paths=$paths;valid=($valid -and $paths.Count -gt 0)}
            }
            if ($data['capabilities'] -isnot [array]) { continue }
            foreach ($cap in $data['capabilities']) {
                if ($cap -isnot [System.Collections.IDictionary] -or $cap['id'] -isnot [string]) { continue }
                $valid = $cap['paths'] -is [array] -and $cap['paths'].Count -gt 0
                foreach ($entry in $cap['paths']) { try { if (-not (Test-Path -LiteralPath (Get-KosSafe $Root $entry) -PathType Leaf)) { $valid = $false } } catch { $valid = $false } }
                if (-not $found.Contains($cap['id'])) { $found[$cap['id']] = @() }
                $found[$cap['id']] += @{source=$rel;paths=$cap['paths'];valid=$valid}
            }
        } catch { continue }
    }
    return $found
}
function Add-KosMetadata($Root, $Plan, $Payload, $Relative, [byte[]]$Bytes) {
    $current = Get-KosCurrent $Root $Relative; $hash = Get-KosHash $Bytes
    $action = if ($current -eq $hash) { 'UNCHANGED' } elseif ($null -eq $current) { 'CREATE' } else { 'MERGE' }
    $class = if ($action -eq 'UNCHANGED') { 'IDENTICAL' } elseif ($null -eq $current) { 'MISSING' } else { 'CONFIG_CONFLICT' }
    $Plan.items.Add(@{path=$Relative;classification=$class;action=$action;currentHash=$current;desiredHash=$hash;ownership='managed'})
    $Payload[$Relative] = $Bytes
}
function New-KosPlan([string]$Root, [string]$Operation, $Answers, [string]$Profile='standard', $Decisions=@{}) {
    $files = Get-KosInventory $Root; $kind = Get-KosDetection $Root $files; $state = Get-KosState $Root
    if ($Operation -eq 'new' -and $kind -notin @('new-target','empty-directory')) { throw 'NEW_REQUIRES_EMPTY: select upgrade or enhance' }
    if ($Operation -in @('upgrade','repair') -and $kind -notin @('managed-kos','legacy-kos')) { throw 'KOS_NOT_DETECTED' }
    if ($Operation -eq 'enhance' -and $kind -notin @('obsidian-vault','managed-kos')) { throw 'OBSIDIAN_NOT_DETECTED' }
    if ($Operation -eq 'enhance' -and $state -and $state['origin'] -ne 'enhance') { throw 'USE_UPGRADE_FOR_MANAGED_KOS' }
    if ($state) { $Profile = $state['profile']; $Answers['installation']['providers'] = $state['providers'];$Answers['installation']['include_samples']=[bool]$state['includeSamples'];$Answers['installation']['custom_modules']=@($state['customModules']) }
    $old = if ($state) { $state['components'] } else { @{} }
    $components = @{}; foreach ($key in $old.psbase.Keys) { $components[$key] = $old[$key] }
    $items = New-Object System.Collections.Generic.List[object]
    $plan = @{schemaVersion='1.0.0';operation=$Operation;targetType=$kind;previousVersion=$(if($state){$state['starterKitVersion']}else{$null});resultingVersion=$script:KosRelease['starterKitVersion'];edition=$(if($state){Get-KosCanonicalEdition $state['edition']}else{$script:KosRelease['edition']});profile=$Profile;items=$items;links=@($files | Where-Object {$_.kind -eq 'link'} | ForEach-Object {$_.path});decisions=$Decisions;folderMappings=@()}
    $plan.inventorySummary=@{files=@($files | Where-Object {$_.kind -eq 'file'}).Count;directories=@($files | Where-Object {$_.kind -eq 'directory'}).Count;links=$plan.links.Count}
    $plan.postActions=@();if($Operation -eq 'new' -and $Answers.installation['initialize_git']){$plan.postActions=@('INITIALIZE_GIT')}
    if($Answers.installation['create_initial_commit']){throw 'INITIAL_COMMIT_REQUIRES_MANUAL_CONTENT_REVIEW'}
    if ($kind -eq 'legacy-kos') {
        $legacy = Get-KosSafe $Root '00 - System/Installation/installer-state.json'
        if (Test-Path -LiteralPath $legacy -PathType Leaf) {
            $prior = (Read-KosJson $legacy)['installer_version']
            if ($prior -and $prior -notin $script:KosRelease['supportedUpgradeVersions']) { throw 'VERSION_UNSUPPORTED_OR_DOWNGRADE' }; $plan.previousVersion = $prior
        }
    }
    if ($Operation -eq 'enhance') { $plan.folderMappings = @($files | Where-Object {$_.kind -eq 'directory' -and -not $_.path.Contains('/') -and -not $_.path.StartsWith('.')} | ForEach-Object { @{existing=$_.path;recommendation='retain in place; map explicitly in context policy'} }) }
    $catalog = Read-KosJson (Join-Path $PSScriptRoot 'assets.json'); $found = Get-KosEvidence $Root $files
    $historical=(Read-KosJson (Join-Path $PSScriptRoot 'historical-templates.json')).templates
    $values = @{}; foreach ($section in @('user','system','privacy','rhythm')) { foreach ($key in $Answers[$section].psbase.Keys) {
        $value = $Answers[$section][$key]
        $values[$key] = if ($value -is [bool]) { $value.ToString().ToLowerInvariant() } elseif ($value -is [array]) { $value -join ', ' } else { [string]$value }
    } }
    $values['system_name']=$Answers['system']['name'];$values['system_short_name']=$Answers['system']['short_name'];$values['system_description']=$Answers['system']['description']
    $values['starter_kit_version']=$script:KosRelease.starterKitVersion;$values['community_version']=$script:KosRelease.communityVersion;$values['kos_contract_version']=$script:KosRelease.kosContractVersion
    $payload=@{}; $installedCaps=New-Object System.Collections.Generic.List[object]
    foreach ($asset in $catalog.assets) {
        if($asset['sample'] -and -not $Answers.installation['include_samples']){continue}
        if($Profile -in @('lean','custom') -and $asset['module'] -in @('business','personal','hobbies','knowledge') -and ($Profile -eq 'lean' -or $asset['module'] -notin $Answers.installation['custom_modules'])){continue}
        if ($asset['provider'] -and $asset['provider'] -notin $Answers['installation']['providers']) { continue }
        if ($Profile -eq 'minimal' -and -not $asset['minimal']) { continue }
        $rel=$asset.path; $text=[IO.File]::ReadAllText((Get-KosSafe $script:KosRoot $asset.source),$script:Utf8).Replace("`r`n","`n")
        $renderValues=@{}
        foreach($match in [regex]::Matches($text,'\{\{([a-z0-9_]+)\}\}')){$key=$match.Groups[1].Value;if($key -notin @('starter_kit_version','community_version','kos_contract_version')){$renderValues[$key]=$values[$key]}}
        $renderFingerprint=if($renderValues.psbase.Count){Get-KosHash (Get-KosBytes $renderValues)}else{''}
        $text=[regex]::Replace($text,'\{\{([a-z0-9_]+)\}\}',{param($m) if($values.Contains($m.Groups[1].Value)){$values[$m.Groups[1].Value]}else{$m.Value}})
        $historicalHashes=@()
        foreach($snapshot in $historical){if($snapshot.path -eq $rel){
            $prior=[regex]::Replace($snapshot.text,'\{\{([a-z0-9_]+)\}\}',{param($m) if($values.Contains($m.Groups[1].Value)){$values[$m.Groups[1].Value]}else{$m.Value}})
            $historicalHashes+=Get-KosTextHashes $prior
        }}
        if ($text -match '\{\{[a-z0-9_]+\}\}') { throw 'TEMPLATE_UNRESOLVED' }
        $bytes=$script:Utf8.GetBytes($text); $current=$null; $owner=if($old.Contains($rel)){$old[$rel]['ownership']}else{$asset.ownership}
        $cap=$asset['capability'];$class='MISSING';$action='CREATE'
        try {
            $path=Get-KosSafe $Root $rel
            if (Test-Path -LiteralPath $path -PathType Container) { $class='PATH_CONFLICT';$action='BLOCK' }
            else {
                $current=Get-KosCurrent $Root $rel
                if ($current -eq (Get-KosHash $bytes)) { $class='IDENTICAL';$action='UNCHANGED' }
                elseif($current -in (Get-KosTextHashes $text)){$class='COMPATIBLE_EXISTING';$action='UNCHANGED'}
                elseif ($null -ne $current) {
                    if ($asset['merge'] -eq 'existing-priority') {
                        try {
                            $existing=Read-KosJson $path; if($asset['schema']){Assert-KosSchema $asset['schema'] $existing}
                            $mergedConfig=Merge-KosExisting (Convert-KosObject ($text | ConvertFrom-Json)) $existing
                            if((Get-KosJson $mergedConfig) -ceq (Get-KosJson $existing)){$bytes=[IO.File]::ReadAllBytes($path)}else{$bytes=Get-KosBytes $mergedConfig}
                            if ((Get-KosHash $bytes) -eq $current) {$class='COMPATIBLE_EXISTING';$action='UNCHANGED'}else{$class='CONFIG_CONFLICT';$action='MERGE'}
                        } catch {$class='CONFIG_CONFLICT';$action='BLOCK'}
                    } elseif (-not $old.Contains($rel) -and $plan.previousVersion -eq '1.1.0' -and $current -in $historicalHashes) {$class='OLDER_MANAGED';$action='UPDATE_SAFE'}
                    elseif ($old.Contains($rel) -and $current -eq $old[$rel]['installedHash'] -and $owner -in @('managed','managed-customizable')) {
                        if($renderFingerprint -and $old[$rel]['renderFingerprint'] -ne $renderFingerprint){$class='CONFIG_CONFLICT';$action='PROPOSE'}else{$class='OLDER_MANAGED';$action='UPDATE_SAFE'}
                    }
                    else {$class='USER_MODIFIED';$action='PROPOSE';if(-not $old.Contains($rel)){$owner='user-owned'}}
                }
                if ($cap -and $null -eq $current -and $found.Contains($cap)) {
                    $equivalent=@($found[$cap] | Where-Object {$rel -notin $_.paths})
                    if($equivalent.Count){$class='SEMANTIC_DUPLICATE';$action='BLOCK';if($Decisions[$rel] -eq 'adopt' -and @($equivalent | Where-Object {-not $_.valid}).Count -eq 0){$action='ADOPT'}}
                }
                if ($asset['registry'] -and $null -eq $current) {
                    foreach ($file in $files) {
                        if ($file.kind -eq 'file' -and $file.path -ne $rel -and $file.path -match '(skill.json|registry.yaml|skills.json|power-ups.json)$') {
                            if (($asset['registry'] -eq 'skill' -and $file.path -match 'skill') -or ($asset['registry'] -eq 'powerup' -and $file.path -match 'power')) {$class='SEMANTIC_DUPLICATE';$action='BLOCK'}
                        }
                    }
                }
            }
        } catch {$class='SECURITY_CONFLICT';$action='BLOCK'}
        $choice=$Decisions[$rel]
        if ($choice -in @('keep','skip') -and $class -notin @('SECURITY_CONFLICT','RESERVED_PATH_CONFLICT')) {$action=if($choice -eq 'keep'){'PRESERVE'}else{'SKIP'}}
        elseif ($choice -eq 'replace' -and $class -eq 'USER_MODIFIED' -and $owner -in @('managed','managed-customizable')) {$action='UPDATE_APPROVED'}
        elseif ($choice -eq 'propose' -and $class -eq 'USER_MODIFIED') {$action='PROPOSE'}
        elseif ($choice -and $choice -notin @('keep','skip','replace','propose','adopt')) {throw 'DECISION_INVALID'}
        $hash=Get-KosHash $bytes
        if ($action -eq 'PROPOSE' -and $old.Contains($rel) -and $old[$rel]['proposalHash'] -eq $hash) {$action='PRESERVE'}
        $items.Add(@{path=$rel;classification=$class;action=$action;currentHash=$current;desiredHash=$hash;ownership=$owner;componentId=$asset.componentId});$payload[$rel]=$bytes
        if ($action -in @('CREATE','UPDATE_SAFE','UPDATE_APPROVED','MERGE','UNCHANGED')) {
            $record=@{path=$rel;componentId=$asset.componentId;ownership=$owner;sourceVersion=$script:KosRelease.starterKitVersion;installedHash=$hash;lastInstallerAction=$action}
            if($action -eq 'UNCHANGED'){$record.installedHash=$current}
            if($renderFingerprint){$record.renderFingerprint=$renderFingerprint}
            if($old.Contains($rel) -and $action -eq 'UNCHANGED' -and $old[$rel].installedHash -eq $current){$record=$old[$rel]};$components[$rel]=$record
            if($cap){$installedCaps.Add(@{id=$cap;version=$(if($asset['provider']){$script:KosRelease.adapterVersion}else{$script:KosRelease.kosContractVersion});paths=@($rel)})}
        } elseif ($action -eq 'PROPOSE') {
            $record=if($old.Contains($rel)){$old[$rel].Clone()}else{@{path=$rel;componentId=$asset.componentId;ownership='user-owned';sourceVersion='unknown';installedHash=$current;lastInstallerAction='PRESERVE'}}
            $record['proposalHash']=$hash;$components[$rel]=$record
        } elseif ($action -eq 'ADOPT') {foreach($e in $found[$cap]){$installedCaps.Add(@{id=$cap;version=$script:KosRelease.kosContractVersion;paths=$e.paths})}}
    }
    $capsPath=Get-KosSafe $Root $script:KosCaps;$caps=if(Test-Path -LiteralPath $capsPath){Read-KosJson $capsPath}else{@{schemaVersion='1.0.0';capabilities=@()}}
    Assert-KosSchema 'capabilities' $caps;$merged=@{}
    foreach($cap in $caps.capabilities){if($merged.Contains($cap.id)){throw 'CAPABILITY_DUPLICATE'};$merged[$cap.id]=$cap}
    foreach($cap in $installedCaps){if(-not $merged.Contains($cap.id)){$merged[$cap.id]=$cap}}
    $caps.capabilities=@($merged.psbase.Values | Sort-Object {$_.id});Add-KosMetadata $Root $plan $payload $script:KosCaps (Get-KosBytes $caps)
    $next=if($state){$state.Clone()}else{@{schemaVersion='1.0.0';edition=$script:KosRelease['edition'];origin=$Operation}}
    $next.edition=Get-KosCanonicalEdition $(if($next['edition']){$next['edition']}else{$script:KosRelease['edition']})
    foreach($key in @('starterKitVersion','installerVersion','communityVersion','kosContractVersion')){$next[$key]=$script:KosRelease[$key]}
    $next.profile=$Profile;$next.providers=$Answers['installation']['providers'];$next.components=$components;$next.capabilities=@($merged.psbase.Keys | Sort-Object)
    $next.includeSamples=[bool]$Answers.installation['include_samples'];$next.customModules=$Answers.installation['custom_modules']
    Add-KosMetadata $Root $plan $payload $script:KosState (Get-KosBytes $next)
    foreach($rel in $catalog.directories){
        $domain=@{'01 - Business'='business';'03 - Personal'='personal';'04 - Hobbies'='hobbies';'05 - Knowledge'='knowledge'}[($rel -split '/')[0]]
        if($domain -and $Profile -in @('lean','custom') -and ($Profile -eq 'lean' -or $domain -notin $Answers.installation['custom_modules'])){continue}
        if($Profile -eq 'minimal' -and $rel -notmatch '^(00 - System|\.agents|06 - Inbox|08 - Templates|99 - Archive)'){continue}
        try{$path=Get-KosSafe $Root $rel;if(Test-Path -LiteralPath $path -PathType Container){$action='UNCHANGED';$class='IDENTICAL'}elseif(Test-Path -LiteralPath $path){$action='BLOCK';$class='PATH_CONFLICT'}else{$action='CREATE_DIRECTORY';$class='MISSING'}}catch{$action='BLOCK';$class='SECURITY_CONFLICT'}
        $items.Add(@{path=$rel;action=$action;classification=$class;kind='directory'})
    }
    $plan.items=@($items | Sort-Object {$_.path})
    if($Operation -in @('upgrade','enhance','repair')){
        $plan.linkAudit=Get-KosLinkAudit $Root $files $plan.items
        foreach($source in @($plan.linkAudit.regressions | ForEach-Object {$_.source} | Sort-Object -Unique)){
            $items.Add(@{path=$source;classification='DEPENDENCY_CONFLICT';action='BLOCK';rule='LINK_RESOLUTION_REGRESSION'})
        }
        $plan.items=@($items | Sort-Object {$_.path})
    }
    $plan.blocked=@($items | Where-Object {$_.action -eq 'BLOCK'}).Count -gt 0
    return @{plan=$plan;payload=$payload}
}

function Write-KosDurable([string]$Path,[byte[]]$Bytes,[bool]$Exclusive=$false) {
    $mode=if($Exclusive){[IO.FileMode]::CreateNew}else{[IO.FileMode]::Create}
    $stream=New-Object IO.FileStream($Path,$mode,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
function Move-KosAtomic([string]$Source,[string]$Destination) {
    if($env:OS -eq 'Windows_NT') {
        if(-not ('KosNativeFile' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class KosNativeFile {
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool MoveFileEx(string source, string destination, uint flags);
}
'@
        }
        if(-not [KosNativeFile]::MoveFileEx($Source,$Destination,9)) { throw 'ATOMIC_RENAME_FAILED' }
    } elseif([IO.File]::Exists($Destination)) { [IO.File]::Replace($Source,$Destination,[NullString]::Value) }
    else { [IO.File]::Move($Source,$Destination) }
}
function Save-KosJournal($Tx) {
    $path=Get-KosSafe $Tx.root ($Tx.rel+'/journal.json');$temp=Get-KosSafe $Tx.root ($Tx.rel+'/journal.next')
    # Journals are evidence, not signed objects; native serialization avoids
    # repeatedly canonicalizing the growing write-ahead log.
    Write-KosDurable $temp ($script:Utf8.GetBytes(($Tx.journal | ConvertTo-Json -Depth 100 -Compress)+"`n"))
    Move-KosAtomic $temp $path
}
function New-KosDirectory($Tx,[string]$Relative) {
    if(-not $Relative -or $Relative -eq '.'){return}
    $path=Get-KosSafe $Tx.root $Relative
    if(Test-Path -LiteralPath $path -PathType Container){return};if(Test-Path -LiteralPath $path){throw 'PATH_NOT_DIRECTORY'}
    $parent=($Relative -split '/') | Select-Object -SkipLast 1;New-KosDirectory $Tx ($parent -join '/')
    $entry=@{path=$Relative;kind='directory';status='intent'};$Tx.journal.entries.Add($entry);Save-KosJournal $Tx
    $null=[IO.Directory]::CreateDirectory($path);$entry.status='written';Save-KosJournal $Tx
}
function Write-KosTransaction($Tx,[string]$Relative,$Bytes,$Expected,[string]$Ownership='managed') {
    $path=Get-KosSafe $Tx.root $Relative
    if((Get-KosCurrent $Tx.root $Relative) -ne $Expected){throw 'TARGET_CHANGED_SINCE_PLAN'}
    $after=if($null -ne $Bytes){Get-KosHash $Bytes}else{$null};if($after -eq $Expected){return}
    $entry=@{path=$Relative;beforeHash=$Expected;afterHash=$after;ownership=$Ownership;status='intent'};$Tx.journal.entries.Add($entry);Save-KosJournal $Tx
    if($null -ne $Expected){
        $backupRel=$Tx.rel+'/backup/'+$Relative;$backup=Get-KosSafe $Tx.root $backupRel;$null=[IO.Directory]::CreateDirectory((Split-Path -Parent $backup))
        $original=[IO.File]::ReadAllBytes($path);if((Get-KosHash $original) -ne $Expected){throw 'TARGET_CHANGED_DURING_BACKUP'}
        Write-KosDurable $backup $original $true;$entry.backup=$backupRel;Save-KosJournal $Tx
    }
    $parent=($Relative -split '/') | Select-Object -SkipLast 1;New-KosDirectory $Tx ($parent -join '/')
    if((Get-KosCurrent $Tx.root $Relative) -ne $Expected){throw 'TARGET_CHANGED_BEFORE_WRITE'}
    if($null -eq $Bytes){[IO.File]::Delete($path)}elseif($null -eq $Expected){Write-KosDurable $path $Bytes $true}else{
        $temp=Get-KosSafe $Tx.root ($Tx.rel+'/replacement');Write-KosDurable $temp $Bytes;$null=Get-KosSafe $Tx.root $Relative;Move-KosAtomic $temp $path
    }
    $entry.status='written';Save-KosJournal $Tx
}
function Get-KosReport($Plan,[string]$Status='PLANNED',[string]$Run='') {
    if($Plan['recovery'] -eq 'incomplete' -and $Status -in @('COMPLETE','complete','UNCHANGED')){$Status='INCOMPLETE'}
    $lines=@('# KOS operation report','','Status: '+$Status,'Operation: '+$Plan.operation,'Target type: '+$Plan.targetType,'Previous Starter Kit: '+$Plan['previousVersion'],'Resulting Starter Kit: '+$Plan['resultingVersion'],'Edition: '+$Plan['edition'],'')
    foreach($item in $Plan.items){$lines+=('- `'+$item.path+'`: '+$item.classification+' / '+$item.action)}
    if($Plan['recovery']){$lines+=('Recovery: '+$Plan.recovery)}
    foreach($item in $Plan['links']){$lines+=('- Preserved link (not traversed): `'+$item+'`')}
    if($Plan['linkAudit']){
        $audit=$Plan.linkAudit
        $lines+=('Link audit: Markdown files='+$audit.scannedMarkdownFiles+', references='+$audit.references+', preexisting unresolved='+$audit.preexistingUnresolved+', preexisting ambiguous='+$audit.preexistingAmbiguous)
        $lines+=('New basename collisions: '+@($audit.newBasenameCollisions).Count+'; resolution regressions: '+@($audit.regressions).Count)
        foreach($item in $audit.regressions){$lines+=('- Link resolution regression: `'+$item.source+'` -> `'+$item.target+'`')}
    }
    if($Run){$lines+=('Backup: '+$script:KosRuns+'/'+$Run+'/backup');$lines+=('Rollback: -Operation rollback -RunId '+$Run)}
    $lines+='User action: review preserved files, proposals and BLOCK items. Diagnostics omit file contents.'
    return ($lines -join "`n")+"`n"
}
function Invoke-KosApply([string]$Root,$Plan,$Payload) {
    if($Plan.blocked){throw 'PLAN_HAS_BLOCKING_CONFLICTS'}
    $changes=@($Plan.items | Where-Object {$_.action -in @('CREATE','MERGE','UPDATE_SAFE','UPDATE_APPROVED','PROPOSE','CREATE_DIRECTORY','REMOVE','RESTORE')})
    if(-not $changes.Count){return $null}
    foreach($item in $changes){$null=Get-KosSafe $Root $item.path;if($item['kind'] -ne 'directory' -and (Get-KosCurrent $Root $item.path) -ne $item['currentHash']){throw 'TARGET_CHANGED_SINCE_PLAN'}}
    $control=Get-KosSafe $Root '00 - System/Installation';$null=[IO.Directory]::CreateDirectory($control)
    $run=[Guid]::NewGuid().ToString('N');$lock=Get-KosSafe $Root '00 - System/Installation/operation.lock'
    try{Write-KosDurable $lock (Get-KosBytes @{runId=$run}) $true}catch{if(Test-Path -LiteralPath $lock){throw 'OPERATION_LOCKED'};throw}
    $tx=@{root=$Root;run=$run;rel=$script:KosRuns+'/'+$run;journal=@{schemaVersion='1.0.0';runId=$run;status='in-progress';operation=$Plan.operation;decisions=$Plan['decisions'];entries=(New-Object System.Collections.Generic.List[object])}}
    try {
        $null=[IO.Directory]::CreateDirectory((Get-KosSafe $Root $tx.rel));Save-KosJournal $tx
        Write-KosDurable (Get-KosSafe $Root ($tx.rel+'/plan.json')) (Get-KosBytes $Plan) $true
        foreach($item in ($changes | Sort-Object {if($_.path -in @($script:KosState,$script:KosCaps) -or $_.path -match '(skills.json|power-ups.json|packages.json)$'){1}else{0}},{$_.path})){
            if($item.path -in @($script:KosState,$script:KosCaps) -or $item.path -match '(skills.json|power-ups.json|packages.json)$'){
                foreach($entry in $tx.journal.entries){if($entry['kind'] -ne 'directory' -and (Get-KosCurrent $Root $entry.path) -ne $entry.afterHash){throw 'PRE_ACTIVATION_INTEGRITY_FAILURE'}}
            }
            if($item.action -eq 'CREATE_DIRECTORY'){New-KosDirectory $tx $item.path}
            elseif($item.action -eq 'PROPOSE'){Write-KosTransaction $tx ($tx.rel+'/proposals/'+$item.path) $Payload[$item.path] $null}
            else{Write-KosTransaction $tx $item.path $Payload[$item.path] $item['currentHash'] $(if($item['ownership']){$item['ownership']}else{'managed'})}
        }
        $tx.journal.validation='written hashes and paths verified before metadata activation'
        if('INITIALIZE_GIT' -in $Plan['postActions']){
            $entry=@{path='.git';kind='git';ownership='runtime';status='intent'};$tx.journal.entries.Add($entry);Save-KosJournal $tx
            $null=Get-KosSafe $Root '.git';$null=& git -C $Root init -b main
            if($LASTEXITCODE -ne 0){throw 'GIT_INITIALIZATION_FAILED'};$entry.status='written';Save-KosJournal $tx
        }
        $tx.journal.status=if($Plan['recovery'] -eq 'incomplete'){'incomplete'}else{'complete'}
        if($Plan['recovery']){$tx.journal.recovery=$Plan.recovery}
    } catch {$tx.journal.status='failed';throw} finally {
        Save-KosJournal $tx
        Write-KosDurable (Get-KosSafe $Root ($tx.rel+'/report.md')) ($script:Utf8.GetBytes((Get-KosReport $Plan $tx.journal.status $run)))
        if((Test-Path -LiteralPath $lock) -and (Read-KosJson $lock)['runId'] -eq $run){[IO.File]::Delete($lock)}
    }
    return $run
}
