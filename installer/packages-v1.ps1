# Immutable local package engine; dot-source after engine.ps1.
$script:KosRegistries=@{skill='.agents/registry/skills.json';powerup='00 - System/Power-Ups/Registry/power-ups.json'}
$script:KosGeneric='00 - System/Config/packages.json'
$script:KosHomes=@{skill='.agents/skills';powerup='00 - System/Power-Ups/Installed';adapter='00 - System/Adapters/Installed';integration='00 - System/Integrations/Installed';bundle='00 - System/Bundles/Installed'}
function Test-KosSignature($Manifest,[string]$Trust) {
    $signature=$Manifest['signature']
    if(-not $signature){if($Manifest['requiresSignature']){throw 'SIGNATURE_REQUIRED'};return}
    if(-not $Trust){throw 'SIGNATURE_TRUST_UNAVAILABLE'}
    $keys=Read-KosJson (Get-KosSafe ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($Trust))) ([IO.Path]::GetFileName($Trust)))
    $key=$keys['keys'][$signature['keyId']]
    if(-not $key -or $signature['algorithm'] -ne 'rsa-sha256'){throw 'SIGNATURE_UNTRUSTED'}
    $rsa=New-Object Security.Cryptography.RSACryptoServiceProvider
    $rsa.PersistKeyInCsp=$false
    try {
        $parameters=New-Object Security.Cryptography.RSAParameters
        $parameters.Modulus=[Convert]::FromBase64String($key['modulus']);$parameters.Exponent=[Convert]::FromBase64String($key['exponent'])
        if($parameters.Modulus.Length -lt 256){throw 'SIGNATURE_INVALID'}
        $rsa.ImportParameters($parameters);$unsigned=$Manifest.Clone();$unsigned.Remove('signature')
        if(-not $rsa.VerifyData((Get-KosBytes $unsigned),'SHA256',[Convert]::FromBase64String($signature['value']))){throw 'SIGNATURE_INVALID'}
    } finally {$rsa.Dispose()}
}
function Read-KosPackage([string]$Path,[string]$Trust='') {
    $absolute=[IO.Path]::GetFullPath($Path);$null=Get-KosSafe (Split-Path -Parent $absolute) (Split-Path -Leaf $absolute);$blobs=@{}
    if(Test-Path -LiteralPath $absolute -PathType Container){
        $names=@{};$total=0L
        foreach($item in (Get-KosInventory $absolute)){
            Test-KosRelative $item.path
            if($names.Contains($item.path.ToLowerInvariant()) -or ($item.path -split '/')[0] -in @('.git','00 - System')){throw 'PACKAGE_RESERVED_OR_DUPLICATE_PATH'}
            $names[$item.path.ToLowerInvariant()]=$true
            if($item.kind -eq 'link'){throw 'PACKAGE_LINK'}
            if($item.kind -eq 'file'){
                $source=Get-KosSafe $absolute $item.path;$size=(Get-Item -LiteralPath $source).Length;$total+=$size
                if($total -gt 64MB -or $names.Count -gt 4096 -or $size -gt 16MB){throw 'ARCHIVE_RESOURCE_LIMIT'}
                $blobs[$item.path]=[IO.File]::ReadAllBytes($source)
            }
        }
    }else{
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive=[IO.Compression.ZipFile]::OpenRead($absolute);$names=@{};$total=0L
        try{foreach($entry in $archive.Entries){
            $name=$entry.FullName.TrimEnd('/');Test-KosRelative $name
            if($names.Contains($name.ToLowerInvariant())){throw 'ARCHIVE_DUPLICATE_PATH'};$names[$name.ToLowerInvariant()]=$true
            $mode=($entry.ExternalAttributes -shr 16) -band 0xf000
            if($mode -notin @(0,0x8000,0x4000)){throw 'ARCHIVE_UNSAFE_ENTRY'}
            $total+=$entry.Length;if($total -gt 64MB -or $names.Count -gt 4096 -or $entry.Length -gt 16MB){throw 'ARCHIVE_RESOURCE_LIMIT'}
            if(-not $entry.FullName.EndsWith('/')){
                $source=$entry.Open();$memory=New-Object IO.MemoryStream
                try{$source.CopyTo($memory);$blobs[$name]=$memory.ToArray()}finally{$source.Dispose();$memory.Dispose()}
            }
        }}finally{$archive.Dispose()}
    }
    if(-not $blobs.Contains('manifest.json')){throw 'PACKAGE_MANIFEST_MISSING'}
    $manifest=Convert-KosJson ($script:Utf8.GetString($blobs['manifest.json']).TrimStart([char]0xfeff))
    Assert-KosSchema 'package' $manifest
    Test-KosSchema $manifest.defaults $manifest.configurationSchema
    $expectedSchema=if($manifest.type -eq 'skill'){'kos-skill/v1'}elseif($manifest.type -eq 'powerup'){'kos-powerup/v1'}else{'kos-package/v1'}
    if($manifest.schema -ne $expectedSchema){throw 'PACKAGE_SCHEMA_IDENTITY'}
    if([version]$script:KosRelease.kosContractVersion -lt [version]$manifest.compatibility.min -or [version]$script:KosRelease.kosContractVersion -ge [version]$manifest.compatibility.maxExclusive){throw 'PACKAGE_CONTRACT_INCOMPATIBLE'}
    $canonicalEditions=@($manifest.supportedEditions | ForEach-Object {Get-KosCanonicalEdition $_})
    if($canonicalEditions.Count -eq 1 -and $canonicalEditions[0] -eq 'pro' -and @($manifest['requiredCapabilities'] | Where-Object {$_ -like 'kos.pro.*' -or $_ -like 'kos.core.*'}).Count -eq 0){throw 'PRO_ONLY_REQUIRES_CAPABILITY'}
    if($canonicalEditions.Count -eq 1 -and $canonicalEditions[0] -eq 'enterprise' -and @($manifest['requiredCapabilities'] | Where-Object {$_ -like 'kos.enterprise.*'}).Count -eq 0){throw 'ENTERPRISE_ONLY_REQUIRES_CAPABILITY'}
    $declared=@($manifest.integrity.psbase.Keys)
    foreach($a in $declared){
        if($a.ToLowerInvariant() -in @('manifest.json','skill.json')){throw 'PACKAGE_RESERVED_MANIFEST_PATH'}
        foreach($b in $declared){if($a -cne $b -and ($a -ieq $b -or $a.StartsWith($b+'/',[StringComparison]::OrdinalIgnoreCase))){throw 'PACKAGE_PATH_CONFLICT'}}
    }
    if($blobs.Count -ne $manifest.integrity.Count+1){throw 'PACKAGE_UNDECLARED_OR_MISSING_FILES'}
    $payload=@{}
    foreach($rel in $manifest.integrity.psbase.Keys){
        Test-KosRelative $rel;$key='payload/'+$rel
        if(-not $blobs.Contains($key) -or (Get-KosHash $blobs[$key]) -cne $manifest.integrity[$rel]){throw 'PACKAGE_HASH_MISMATCH'}
        $payload[$rel]=$blobs[$key]
    }
    foreach($entry in $manifest.entrypoints){Test-KosRelative $entry;if(-not $manifest.integrity.Contains($entry)){throw 'PACKAGE_ENTRYPOINT_MISSING'}}
    if($manifest.type -eq 'skill' -and ($manifest['entrypoint'] -ne 'SKILL.md' -or -not $manifest.integrity.Contains('SKILL.md'))){throw 'SKILL_ENTRYPOINT_REQUIRED'}
    Test-KosSignature $manifest $Trust
    return @{manifest=$manifest;payload=$payload;identity=(Get-KosHash (Get-KosBytes $manifest))}
}
function Get-KosRegistries([string]$Root) {
    $result=@{}
    foreach($rel in @($script:KosRegistries.psbase.Values)+@($script:KosGeneric)){
        $path=Get-KosSafe $Root $rel;$data=if(Test-Path -LiteralPath $path){Read-KosJson $path}else{@{schemaVersion='1.0.0';packages=@{}}}
        Assert-KosSchema 'registry' $data;$result[$rel]=$data
    };return $result
}
function Test-KosInstalled([string]$Root,$Record) {
    Test-KosRelative $Record.path;Assert-KosSchema 'package' $Record.manifest
    if($Record.path -cne ($script:KosHomes[$Record.manifest.type]+'/'+$Record.manifest.id+'/'+$Record.manifest.version)){throw 'PACKAGE_RESERVED_PATH'}
    if((Get-KosHash (Get-KosBytes $Record.manifest)) -cne $Record.identity){throw 'REGISTRY_IDENTITY_CHANGED'}
    if((Get-KosJson (Read-KosJson (Get-KosSafe $Root ($Record.path+'/manifest.json')))) -cne (Get-KosJson $Record.manifest)){throw 'PACKAGE_MANIFEST_MODIFIED'}
    if($Record.manifest.type -eq 'skill' -and (Get-KosJson (Read-KosJson (Get-KosSafe $Root ($Record.path+'/skill.json')))) -cne (Get-KosJson $Record.manifest)){throw 'SKILL_MANIFEST_MODIFIED'}
    foreach($rel in $Record.manifest.integrity.psbase.Keys){Test-KosRelative $rel;if((Get-KosCurrent $Root ($Record.path+'/'+$rel)) -cne $Record.manifest.integrity[$rel]){throw 'PACKAGE_INSTALLED_MODIFIED'}}
}
function Test-KosDependencies($Manifest,$All) {
    $graph=@{}
    foreach($key in $All.psbase.Keys){$entry=$All[$key];if($entry.enabled -and $entry.activeVersion){$graph[$key]=$entry.versions[$entry.activeVersion].manifest.dependencies}}
    $graph[$Manifest.id]=$Manifest.dependencies
    foreach($key in $Manifest.dependencies.psbase.Keys){if(-not $All.Contains($key) -or -not $All[$key].enabled -or $All[$key].activeVersion -ne $Manifest.dependencies[$key]){throw 'DEPENDENCY_MISSING_OR_VERSION'}}
    $visiting=@{};$visited=@{}
    function Visit-KosDependency($Name){
        if($visiting.Contains($Name)){throw 'DEPENDENCY_CYCLE'};if($visited.Contains($Name)){return};$visiting[$Name]=$true
        if($graph.Contains($Name)){foreach($child in $graph[$Name].psbase.Keys){Visit-KosDependency $child}}
        $visiting.Remove($Name);$visited[$Name]=$true
    }
    foreach($key in @($graph.psbase.Keys)){Visit-KosDependency $key}
}
function New-KosPackagePlan([string]$Root,[string]$Command,[string]$Package,[string]$Id,[string]$Version,[string]$Trust,[bool]$ApprovePermissions) {
    $state=Get-KosState $Root;if(-not $state){throw 'PACKAGE_REQUIRES_MANAGED_KOS'}
    $data=Get-KosRegistries $Root;$all=@{}
    foreach($registry in $data.psbase.Values){foreach($key in $registry.packages.psbase.Keys){if($all.Contains($key)){throw 'PACKAGE_DUPLICATE_ID'};$all[$key]=$registry.packages[$key]}}
    $planned=@{schemaVersion='1.0.0';operation='package '+$Command;targetType='managed-kos';edition=(Get-KosCanonicalEdition $state.edition);previousVersion=$state.starterKitVersion;resultingVersion=$state.starterKitVersion;items=(New-Object System.Collections.Generic.List[object]);permissions=@();blocked=$false};$payload=@{}
    if($Command -eq 'list'){$planned.packages=$all;return @{plan=$planned;payload=$payload}}
    if($Command -in @('install','update','validate')){
        $parsed=Read-KosPackage $Package $Trust;$manifest=$parsed.manifest;$Id=$manifest.id
        $stateEdition=Get-KosCanonicalEdition $state.edition;$supported=@($manifest.supportedEditions | ForEach-Object {Get-KosCanonicalEdition $_})
        if($stateEdition -notin $supported){throw 'PACKAGE_EDITION_INCOMPATIBLE'}
        foreach($cap in $manifest['requiredCapabilities']){if($cap -notin $state.capabilities){throw 'PACKAGE_CAPABILITY_MISSING'}}
        Test-KosDependencies $manifest $all;$planned.permissions=$manifest.permissions
        if($Command -eq 'validate'){return @{plan=$planned;payload=$payload}}
        $regPath=if($script:KosRegistries.Contains($manifest.type)){$script:KosRegistries[$manifest.type]}else{$script:KosGeneric};$reg=$data[$regPath];$existing=$all[$Id]
        if($existing -and -not $reg.packages.Contains($Id)){throw 'PACKAGE_TYPE_CONFLICT'}
        if($Command -eq 'update' -and -not $existing){throw 'PACKAGE_UPDATE_NOT_INSTALLED'}
        $pkgVersion=$manifest.version
        if($existing -and [version]$pkgVersion -lt [version]$existing.activeVersion){throw 'PACKAGE_DOWNGRADE_USE_ROLLBACK'}
        if($existing -and $existing.versions.Contains($pkgVersion)){
            $record=$existing.versions[$pkgVersion];if($record.identity -cne $parsed.identity){throw 'PACKAGE_SAME_VERSION_DIFFERENT_CONTENT'}
            Test-KosInstalled $Root $record;return @{plan=$planned;payload=$payload}
        }
        if($manifest.permissions.Count -and -not $ApprovePermissions){$planned.blocked=$true;$planned.requiredAction='Review permissions and pass --approve-permissions'}
        if($existing){foreach($record in $existing.versions.psbase.Values){Test-KosInstalled $Root $record}}
        $base=$script:KosHomes[$manifest.type]+'/'+$Id+'/'+$pkgVersion
        if((Test-Path -LiteralPath (Get-KosSafe $Root $base)) -and @((Get-KosInventory (Get-KosSafe $Root $base)) | Where-Object {$_.kind -ne 'directory'}).Count){throw 'IMMUTABLE_VERSION_DIRECTORY_EXISTS'}
        $blobs=$parsed.payload;$blobs['manifest.json']=Get-KosBytes $manifest
        if($manifest.type -eq 'skill'){if($blobs.Contains('skill.json')){throw 'PACKAGE_RESERVED_MANIFEST_PATH'};$blobs['skill.json']=Get-KosBytes $manifest}
        foreach($rel in @($blobs.psbase.Keys | Sort-Object)){
            Test-KosRelative $rel;Add-KosMetadata $Root $planned $payload ($base+'/'+$rel) $blobs[$rel];$planned.items[$planned.items.Count-1].ownership='extension-owned'
        }
        $entry=if($existing){$existing}else{@{enabled=$manifest.enabledByDefault;versions=@{}}}
        $entry.versions[$pkgVersion]=@{path=$base;identity=$parsed.identity;manifest=$manifest};$entry.previousVersion=$entry['activeVersion'];$entry.activeVersion=$pkgVersion;$reg.packages[$Id]=$entry
        Add-KosMetadata $Root $planned $payload $regPath (Get-KosBytes $reg)
        return @{plan=$planned;payload=$payload}
    }
    if(-not $all.Contains($Id)){throw 'PACKAGE_NOT_INSTALLED'};$entry=$all[$Id];$regPath=@($data.psbase.Keys | Where-Object {$data[$_].packages.Contains($Id)})[0]
    if($Command -in @('disable','uninstall','rollback')){
        foreach($name in $all.psbase.Keys){$dependent=$all[$name];if($name -ne $Id -and $dependent.enabled -and $dependent.versions[$dependent.activeVersion].manifest.dependencies.Contains($Id)){throw 'PACKAGE_HAS_ACTIVE_DEPENDENTS'}}
    }
    switch($Command){
        'enable' {$record=$entry.versions[$entry.activeVersion];Test-KosInstalled $Root $record;Test-KosDependencies $record.manifest $all;$entry.enabled=$true}
        'disable' {$entry.enabled=$false}
        'rollback' {
            $previous=if($Version){$Version}else{$entry['previousVersion']};if(-not $previous -or -not $entry.versions.Contains($previous)){throw 'PACKAGE_PREVIOUS_VERSION_UNAVAILABLE'}
            $record=$entry.versions[$previous];Test-KosInstalled $Root $record;Test-KosDependencies $record.manifest $all;$entry.previousVersion=$entry.activeVersion;$entry.activeVersion=$previous
        }
        'uninstall' {
            foreach($record in $entry.versions.psbase.Values){Test-KosInstalled $Root $record
                $owned=@($record.manifest.integrity.psbase.Keys)+@('manifest.json');if($record.manifest.type -eq 'skill'){$owned+=@('skill.json')}
                foreach($rel in $owned){
                    Test-KosRelative $rel;$destination=$record.path+'/'+$rel
                    $planned.items.Add(@{path=$destination;classification='OLDER_MANAGED';action='REMOVE';currentHash=(Get-KosCurrent $Root $destination);ownership='extension-owned'});$payload[$destination]=$null
                }
            };$data[$regPath].packages.Remove($Id)
        }
        default {throw 'PACKAGE_COMMAND_INVALID'}
    }
    Add-KosMetadata $Root $planned $payload $regPath (Get-KosBytes $data[$regPath]);return @{plan=$planned;payload=$payload}
}

function New-KosRollbackPlan([string]$Root,[string]$RunId) {
    if($RunId -cnotmatch '^[a-f0-9]{32}$'){throw 'RUN_ID_INVALID'}
    $journal=Read-KosJson (Get-KosSafe $Root ($script:KosRuns+'/'+$RunId+'/journal.json'))
    if($journal.runId -cne $RunId){throw 'JOURNAL_ID_MISMATCH'}
    $plan=@{schemaVersion='1.0.0';operation='rollback';targetType='managed-kos';items=(New-Object System.Collections.Generic.List[object]);blocked=$false};$payload=@{}
    $entries=@($journal.entries);[Array]::Reverse($entries)
    foreach($entry in $entries){
        $rel=$entry.path;Test-KosRelative $rel
        if($rel.StartsWith($script:KosRuns+'/') -or $rel.EndsWith('operation.lock') -or $entry['kind'] -eq 'directory'){continue}
        if($entry['kind'] -eq 'git'){$plan.items.Add(@{path=$rel;action='PRESERVE';classification='USER_MODIFIED';currentHash=$null});continue}
        $action='UNCHANGED';$class='IDENTICAL';$actual=$null
        try{
            $actual=Get-KosCurrent $Root $rel
            if($actual -eq $entry.beforeHash){}
            elseif($actual -ne $entry.afterHash){$action='PRESERVE';$class='USER_MODIFIED'}
            elseif($null -eq $entry.beforeHash -and $entry.ownership -in @('user-owned','runtime')){$action='PRESERVE';$class='USER_MODIFIED'}
            else{
                if($null -ne $entry.beforeHash){
                    $original=[IO.File]::ReadAllBytes((Get-KosSafe $Root ($script:KosRuns+'/'+$RunId+'/backup/'+$rel)))
                    if((Get-KosHash $original) -cne $entry.beforeHash){throw 'BACKUP_HASH_MISMATCH'};$payload[$rel]=$original
                }else{$payload[$rel]=$null}
                $action='RESTORE';$class='OLDER_MANAGED'
            }
        }catch{$action='BLOCK';$class='SECURITY_CONFLICT'}
        $plan.items.Add(@{path=$rel;action=$action;classification=$class;currentHash=$actual})
    }
    $plan.recovery=if(@($plan.items | Where-Object {$_.action -in @('BLOCK','PRESERVE')}).Count){'incomplete'}else{'complete'}
    if($plan.recovery -eq 'incomplete'){foreach($item in $plan.items){if($item.path -match '(kos-installation.json|skills.json|power-ups.json|packages.json|capabilities.json)$'){$item.action='PRESERVE'}}}
    return @{plan=$plan;payload=$payload}
}
function Test-KosInstallation([string]$Root) {
    $findings=New-Object System.Collections.Generic.List[object]
    try{
        $files=Get-KosInventory $Root;$state=Get-KosState $Root
        if(-not $state){$findings.Add(@{rule='META_MISSING';path=$script:KosState;severity='error'});return ,$findings.ToArray()}
        foreach($rel in $state.components.psbase.Keys){
            try{$actual=Get-KosCurrent $Root $rel;if($null -eq $actual){$findings.Add(@{rule='ASSET_MISSING';path=$rel;severity='error'})}elseif($actual -ne $state.components[$rel].installedHash){$findings.Add(@{rule='ASSET_MODIFIED';path=$rel;severity='warning'})}}
            catch{$findings.Add(@{rule='ASSET_LINK_PRESERVED';path=$rel;severity='error'})}
        }
        $evidence=Get-KosEvidence $Root $files;foreach($key in $evidence.psbase.Keys){if(@($evidence[$key] | Where-Object {-not $_.valid}).Count){$findings.Add(@{rule='CAPABILITY_STALE';path=$key;severity='error'})}}
        $caps=Read-KosJson (Get-KosSafe $Root $script:KosCaps);Assert-KosSchema 'capabilities' $caps
        if((@($state.capabilities | Sort-Object) -join '|') -cne (@($caps.capabilities | ForEach-Object {$_.id} | Sort-Object) -join '|')){$findings.Add(@{rule='CAPABILITY_STATE_MISMATCH';path=$script:KosCaps;severity='error'})}
        foreach($registry in (Get-KosRegistries $Root).psbase.Values){foreach($entry in $registry.packages.psbase.Values){foreach($record in $entry.versions.psbase.Values){try{Test-KosInstalled $Root $record}catch{$findings.Add(@{rule='PACKAGE_INTEGRITY';path=$record.path;severity='error'})}}}}
        foreach($provider in $state.providers){
            $matching=@($caps.capabilities | Where-Object {$_.id -eq ('kos.provider.'+$provider)})
            $rel=if($matching.Count){$matching[0].paths[0]}else{$provider.ToUpperInvariant()+'.md'}
            $text=[IO.File]::ReadAllText((Get-KosSafe $Root $rel),$script:Utf8);if($text -notmatch 'AGENTS.md' -or ($text -split "`n").Count -gt 41){$findings.Add(@{rule='ADAPTER_ROUTING';path=$rel;severity='error'})}
        }
        foreach($file in $files){
            if($file.kind -eq 'link'){$findings.Add(@{rule='LINK_PRESERVED_NOT_TRAVERSED';path=$file.path;severity='warning'});continue}
            if($file.kind -eq 'file' -and $file.path -match '\.(md|json|yaml|yml|txt)$'){
                $path=Get-KosSafe $Root $file.path;if((Get-Item -LiteralPath $path).Length -gt 2MB){$findings.Add(@{rule='SCAN_SIZE_LIMIT';path=$file.path;severity='warning'});continue}
                $text=[IO.File]::ReadAllText($path,$script:Utf8)
                if($text -match '(?i)(password|api[_-]?key|access[_-]?token)\s*["'']?\s*[:=]\s*["'']?[A-Za-z0-9+/=_-]{12,}' -or $text.Contains('-----BEGIN '+'PRIVATE KEY-----')){$findings.Add(@{rule='SECRET_EXPOSURE';path=$file.path;severity='error'})}
                if($text -match '(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:Users|home)/[^/\s]+/'){$findings.Add(@{rule='MACHINE_PATH';path=$file.path;severity='warning'})}
            }
        }
        foreach($required in @('00 - System','06 - Inbox','08 - Templates','99 - Archive')){if(-not (Test-Path -LiteralPath (Get-KosSafe $Root $required) -PathType Container)){$findings.Add(@{rule='STRUCTURE_MISSING';path=$required;severity='error'})}}
    }catch{$findings.Add(@{rule='VALIDATION_UNSAFE_OR_INVALID_METADATA';path='';severity='error'})}
    return ,$findings.ToArray()
}
function Merge-KosLayers($Defaults,$Global,$Project) {
    $result=@{};foreach($key in $Defaults.psbase.Keys){$result[$key]=$Defaults[$key]}
    foreach($layer in @($Global,$Project)){foreach($key in $layer.psbase.Keys){
        $value=$layer[$key]
        if($value -is [System.Collections.IDictionary] -and $result[$key] -is [System.Collections.IDictionary]){$result[$key]=Merge-KosLayers $result[$key] $value @{}}
        else{$result[$key]=$value}
    }};return $result
}
function Resolve-KosPowerUp([string]$Root,[string]$Id,[string]$Project='') {
    $entry=(Get-KosRegistries $Root)[$script:KosRegistries.powerup].packages[$Id]
    if(-not $entry){throw 'PACKAGE_NOT_INSTALLED'};$override=@{}
    if($Project){
        Test-KosRelative $Project;if($Project.Contains('/')){throw 'PROJECT_NAME_INVALID'}
        $path=Get-KosSafe $Root ('02 - Projects/Active/'+$Project+'/power-ups.json')
        if(Test-Path -LiteralPath $path){$activation=Read-KosJson $path;Assert-KosSchema 'project-activation' $activation;if($activation.packages.Contains($Id)){$override=$activation.packages[$Id]}}
    }
    $selected=if($override.Contains('version')){$override.version}else{$entry.activeVersion}
    if(-not $entry.versions.Contains($selected)){throw 'PROJECT_VERSION_NOT_INSTALLED'}
    $record=$entry.versions[$selected];Test-KosInstalled $Root $record;$manifest=$record.manifest
    if($Project -and $manifest.scope -eq 'global'){throw 'PACKAGE_SCOPE_CONFLICT'}
    $path=Get-KosSafe $Root ('00 - System/Config/Power-Ups/'+$Id+'.json')
    $globalConfig=if(Test-Path -LiteralPath $path){Read-KosJson $path}else{@{}}
    if($globalConfig -isnot [System.Collections.IDictionary]){throw 'CONFIG_TYPE_CONFLICT'}
    $projectConfig=if($override.Contains('configuration')){$override.configuration}else{@{}}
    $config=Merge-KosLayers $manifest.defaults $globalConfig $projectConfig;Test-KosSchema $config $manifest.configurationSchema
    return @{id=$Id;version=$selected;enabled=($entry.enabled -and (-not $override.Contains('enabled') -or $override.enabled));entrypoints=@($manifest.entrypoints | ForEach-Object {$record.path+'/'+$_});configuration=$config}
}
