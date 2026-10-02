param([Parameter(Mandatory)][string]$FixtureRoot)
$ErrorActionPreference='Stop'
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/engine.ps1')
. (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/packages-v1.ps1')
function Assert-Condition($Condition,[string]$Message){if(-not $Condition){throw $Message}}
function Write-Fixture($Root,$Relative,$Bytes){$path=Get-KosSafe $Root $Relative;$null=[IO.Directory]::CreateDirectory((Split-Path -Parent $path));[IO.File]::WriteAllBytes($path,$Bytes)}
$root=Get-KosTarget $FixtureRoot
$merged=Merge-KosExisting @{added=$true} @{keys='preserve';unknown=@{value=7};array=@()}
Assert-Condition ((Convert-KosJson (Get-KosJson $merged))['keys'] -eq 'preserve') 'unknown configuration field lost'
$answers=Read-KosJson (Join-Path $script:KosRoot 'installer/defaults.json')
$answers.installation.providers=@('codex','claude','gemini')
$result=New-KosPlan $root 'new' $answers 'minimal'
$run=Invoke-KosApply $root $result.plan $result.payload
Assert-Condition ($run.Length -eq 32) 'missing run ID'
$result=New-KosPlan $root 'upgrade' $answers 'minimal'
Assert-Condition ($null -eq (Invoke-KosApply $root $result.plan $result.payload)) 'repeat upgrade wrote files'
$findings=Test-KosInstallation $root
Assert-Condition (@($findings | Where-Object {$_.severity -eq 'error'}).Count -eq 0) ('validation failed: '+(Get-KosJson $findings))
Write-Fixture $root 'CODEX.md' ($script:Utf8.GetBytes('customized'))
$result=New-KosPlan $root 'upgrade' $answers 'minimal'
Assert-Condition (@($result.plan.items | Where-Object {$_.path -eq 'CODEX.md' -and $_.action -eq 'PROPOSE'}).Count -eq 1) 'customized file was not proposed'
$null=Invoke-KosApply $root $result.plan $result.payload
Assert-Condition ([IO.File]::ReadAllText((Join-Path $root 'CODEX.md')) -eq 'customized') 'customized file overwritten'
foreach($type in @('skill','powerup')){
    foreach($version in @('1.0.0','1.1.0')){
        $source=Join-Path (Split-Path -Parent $root) ($type+'-'+$version)
        $entry=if($type -eq 'skill'){'SKILL.md'}else{'README.md'};$content=$script:Utf8.GetBytes('synthetic '+$version)
        $manifest=@{schemaVersion='1.0.0';schema=$(if($type -eq 'skill'){'kos-skill/v1'}else{'kos-powerup/v1'});type=$type;id='example.'+$type;name='Example';version=$version;creator='Example Author';license='Apache-2.0';compatibility=@{min='1.0.0';maxExclusive='2.0.0'};supportedEditions=@('community','pro');scope='both';permissions=@();dependencies=@{};entrypoints=@($entry);entrypoint=$entry;enabledByDefault=$true;integrity=@{};configurationSchema=@{};defaults=@{}}
        $manifest.integrity[$entry]=Get-KosHash $content
        Write-Fixture $source 'manifest.json' (Get-KosBytes $manifest);Write-Fixture $source ('payload/'+$entry) $content
        if($version -eq '1.0.0'){
            Add-Type -AssemblyName System.IO.Compression
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $archive=$source+'.kospkg'
            # Older .NET CreateFromDirectory emits backslashes; the portable
            # package contract requires slash-separated ZIP entry names.
            $zip=[IO.Compression.ZipFile]::Open($archive,[IO.Compression.ZipArchiveMode]::Create)
            try {
                foreach($relative in @('manifest.json',('payload/'+$entry))){
                    $zipEntry=$zip.CreateEntry($relative)
                    $stream=$zipEntry.Open()
                    try {$bytes=[IO.File]::ReadAllBytes((Join-Path $source $relative));$stream.Write($bytes,0,$bytes.Length)}finally{$stream.Dispose()}
                }
            }finally{$zip.Dispose()}
            $fromArchive=Read-KosPackage $archive
            Assert-Condition ($fromArchive.identity -eq (Get-KosHash (Get-KosBytes $manifest))) 'archive identity mismatch'
        }
        $command=if($version -eq '1.0.0'){'install'}else{'update'}
        $result=New-KosPackagePlan $root $command $source '' '' '' $false
        $null=Invoke-KosApply $root $result.plan $result.payload
        $identical=New-KosPackagePlan $root 'install' $source '' '' '' $false
        Assert-Condition ($identical.plan.items.Count -eq 0) 'identical package not a no-op'
    }
    foreach($command in @('disable','enable','rollback','uninstall')){
        $result=New-KosPackagePlan $root $command '' ('example.'+$type) '' '' $false
        $null=Invoke-KosApply $root $result.plan $result.payload
    }
}
# A small transaction proves backup/rollback and preservation after later edits.
$path='synthetic-managed.md';Write-Fixture $root $path ($script:Utf8.GetBytes('before'))
$p=@{operation='repair';targetType='managed-kos';blocked=$false;items=@(@{path=$path;classification='OLDER_MANAGED';action='UPDATE_SAFE';currentHash=(Get-KosCurrent $root $path);ownership='managed'})}
$payload=@{};$payload[$path]=$script:Utf8.GetBytes('after')
$run=Invoke-KosApply $root $p $payload
$recovery=New-KosRollbackPlan $root $run
Assert-Condition ($recovery.plan.recovery -eq 'complete') 'rollback unexpectedly incomplete'
$null=Invoke-KosApply $root $recovery.plan $recovery.payload
Assert-Condition ([IO.File]::ReadAllText((Join-Path $root $path)) -eq 'before') 'rollback did not restore'
$run=Invoke-KosApply $root $p $payload
Write-Fixture $root $path ($script:Utf8.GetBytes('edited afterwards'))
$recovery=New-KosRollbackPlan $root $run
Assert-Condition ($recovery.plan.recovery -eq 'incomplete') 'post-install changes were not preserved'
Write-Output 'PASS native install, repeat, validation, proposals, Skill/Power-Up lifecycle and rollback'
$rsa=New-Object Security.Cryptography.RSACryptoServiceProvider(2048)
$rsa.PersistKeyInCsp=$false
try {
    $manifest=@{name='Synthetic signature fixture'}
    $signed=$rsa.SignData((Get-KosBytes $manifest),'SHA256')
    $public=$rsa.ExportParameters($false)
    $trust=Join-Path (Split-Path -Parent $root) 'synthetic-trust.json'
    $trustData=@{keys=@{synthetic=@{modulus=[Convert]::ToBase64String($public.Modulus);exponent=[Convert]::ToBase64String($public.Exponent)}}}
    [IO.File]::WriteAllBytes($trust,(Get-KosBytes $trustData))
    $manifest.signature=@{keyId='synthetic';algorithm='rsa-sha256';value=[Convert]::ToBase64String($signed)}
    Test-KosSignature $manifest $trust
    $manifest.name='Tampered';$rejected=$false
    try {Test-KosSignature $manifest $trust} catch {$rejected=$true}
    Assert-Condition $rejected 'invalid signature accepted'
} finally {$rsa.Dispose()}
Write-Output 'PASS native signature verification and unknown configuration preservation'
