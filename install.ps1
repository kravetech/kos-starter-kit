[CmdletBinding()]
param(
    [string]$Answers, [string]$Target,
    [ValidateSet("new","upgrade","enhance","pro","core","validate","repair","rollback")][string]$Operation,
    [ValidateSet("lean","standard","business","developer","creator","custom","migration","minimal","complete")][string]$Mode,
    [switch]$DryRun, [switch]$Approve, [switch]$Resume, [switch]$Migration, [switch]$AllowOverwrite,
    [string]$PlanOutput, [string]$Report, [string]$Decisions, [string]$RunId,
    [ValidateSet("validate","install","list","enable","disable","update","rollback","uninstall")][string]$PackageCommand,
    [string]$Package, [string]$Id, [string]$Version, [string]$Trust, [switch]$ApprovePermissions
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'installer/engine.ps1')
. (Join-Path $PSScriptRoot 'installer/packages-v1.ps1')
function Export-KosResult([string]$Path,[byte[]]$Bytes) {
    $destination=[IO.Path]::GetFullPath($Path);$null=Get-KosSafe (Split-Path -Parent $destination) (Split-Path -Leaf $destination)
    if($destination.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'DRY_RUN_EXPORT_MUST_BE_OUTSIDE_TARGET'}
    $null=[IO.Directory]::CreateDirectory((Split-Path -Parent $destination));Write-KosDurable $destination $Bytes $true
}
try {
    if($AllowOverwrite){throw 'GLOBAL_OVERWRITE_FORBIDDEN'}
    if($Resume){throw 'RESUME_REQUIRES_JOURNAL_REVIEW: rollback interrupted run then replan'}
    $defaults=Read-KosJson (Join-Path $PSScriptRoot 'installer/defaults.json')
    $suppliedAnswers=if($Answers){Read-KosJson ([IO.Path]::GetFullPath($Answers))}else{$null}
    if($suppliedAnswers -and $suppliedAnswers['installation'] -and $suppliedAnswers['installation'].Contains('backup_before_migration')){throw 'BACKUP_SETTING_UNSUPPORTED: create and verify a complete vault snapshot outside the target before migration'}
    $answerObject=if($Answers){Merge-KosExisting $defaults $suppliedAnswers}else{$defaults}
    Assert-KosSchema 'answers' $answerObject
    if(-not $Target){$Target=if([IO.Path]::IsPathRooted($answerObject.installation.target_directory)){$answerObject.installation.target_directory}else{Join-Path $PSScriptRoot $answerObject.installation.target_directory}}
    $root=Get-KosTarget $Target
    if($answerObject.installation['allow_overwrite']){throw 'GLOBAL_OVERWRITE_FORBIDDEN'}
    if(-not $Operation -and $answerObject.installation['operation']){$Operation=$answerObject.installation['operation']}
    if($Migration -or $Mode -eq 'migration'){$kind=Get-KosDetection $root (Get-KosInventory $root);$Operation=if($kind -in @('managed-kos','legacy-kos')){'upgrade'}else{'enhance'}}
    if($PackageCommand){$result=New-KosPackagePlan $root $PackageCommand $Package $Id $Version $Trust ([bool]$ApprovePermissions)}
    else {
        if(-not $Operation -and -not $Answers -and -not [Console]::IsInputRedirected){
            $detected=Get-KosDetection $root (Get-KosInventory $root)
            $recommended=@{'new-target'='new';'empty-directory'='new';'managed-kos'='upgrade';'legacy-kos'='upgrade';'obsidian-vault'='enhance'}[$detected]
            Write-Output ('Detected: '+$detected+'; recommended: '+$recommended)
            Write-Output '[1] Create a new KOS Community installation
[2] Upgrade an existing KOS Community installation
[3] Enhance an existing Obsidian vault
[4] Learn about KOS Pro availability
[5] Validate an existing installation
[6] Repair an existing KOS'
            $selection=[int](Read-Host 'Confirm operation [1-6]');if($selection -lt 1 -or $selection -gt 6){throw 'OPERATION_INVALID'}
            $Operation=@('new','upgrade','enhance','pro','validate','repair')[$selection-1]
        }
        if(-not $Operation){$Operation='new'}
        if($Operation -eq 'validate'){
            $findings=Test-KosInstallation $root;$plan=@{operation='validate';targetType=(Get-KosDetection $root (Get-KosInventory $root));items=@();findings=$findings}
            Write-Output ((Get-KosJson $plan)+"`n");if($Report){Export-KosResult $Report ($script:Utf8.GetBytes((Get-KosReport $plan)))}
            if(@($findings | Where-Object {$_.severity -eq 'error'}).Count){exit 2};exit 0
        }
        if($Operation -eq 'rollback'){$result=New-KosRollbackPlan $root $RunId}
        elseif($Operation -in @('pro','core')){
            $state=Get-KosState $root
            $plan=@{schemaVersion='1.0.0';operation='pro';targetType=$(if($state){'managed-kos'}else{'legacy-kos'});edition=$(if($state){Get-KosCanonicalEdition $state.edition}else{'community'});blocked=$true;items=@(@{path='KOS Pro';classification='BLOCKED';action='BLOCK';rule=$(if($Package){'PRO_TRUST_AND_ENTITLEMENT_PROVIDER_UNAVAILABLE'}else{'PRO_PACKAGE_UNAVAILABLE'})});requiredAction='KOS Pro is a separately licensed commercial edition and is not included in the KOS Starter Kit; no files changed.'}
            $result=@{plan=$plan;payload=@{}}
        } else {
            $profile=if($Mode -and $Mode -ne 'migration'){$Mode}else{$answerObject.installation.mode}
            if($Operation -eq 'enhance' -and -not $Mode){
                $profile='minimal'
                if(-not [Console]::IsInputRedirected -and -not $DryRun -and -not $Approve -and -not $Answers){
                    Write-Output '[1] Minimal KOS layer
[2] Complete KOS architecture'
                    $profileChoice=Read-Host 'Profile [1]'
                    if($profileChoice -eq '2'){$profile='complete'}
                    elseif($profileChoice -notin @('','1')){throw 'PROFILE_INVALID'}
                }
            }
            $decisionsObject=if($Decisions){Read-KosJson $Decisions}else{@{}}
            $result=New-KosPlan $root $Operation $answerObject $profile $decisionsObject
        }
    }
    $plan=$result.plan;Write-Output ((Get-KosJson $plan)+"`n")
    if($PlanOutput){Export-KosResult $PlanOutput (Get-KosBytes $plan)}
    if($Report){Export-KosResult $Report ($script:Utf8.GetBytes((Get-KosReport $plan)))}
    if($DryRun -or $PackageCommand -in @('list','validate')){if($plan.blocked){exit 2};if($Operation -eq 'rollback' -and $plan.recovery -eq 'incomplete'){exit 4};exit 0}
    $approved=[bool]$Approve -or ($Answers -and $Operation -eq 'new')
    if(-not $approved -and -not [Console]::IsInputRedirected){
        $plan.items | Group-Object classification | ForEach-Object {Write-Output ($_.Name+': '+$_.Count)}
        Write-Output '[1] Accept recommended safe actions
[2] Review conflicts one by one
[3] Review complete plan
[4] Export plan without changes
[5] Cancel'
        $choice=Read-Host 'Select [5]'
        if($choice -eq '1'){$approved=$true}
        elseif($choice -eq '2' -and -not $PackageCommand -and $Operation -in @('new','upgrade','enhance','repair')){
            $review=@{};foreach($key in $plan.decisions.psbase.Keys){$review[$key]=$plan.decisions[$key]}
            foreach($item in $plan.items){
                if($item.classification -notin @('USER_MODIFIED','CONFIG_CONFLICT','SEMANTIC_DUPLICATE')){continue}
                if($item.action -eq 'MERGE'){continue}
                Write-Output ($item.path+': '+$item.classification)
                $options=@('keep','skip')
                if($item.classification -eq 'USER_MODIFIED'){$options+=@('propose');if($item['ownership'] -in @('managed','managed-customizable')){$options+=@('replace')}}
                if($item.classification -eq 'SEMANTIC_DUPLICATE'){$options+=@('adopt')}
                $selected=Read-Host ('Action ('+($options -join '/')+', default keep)');if(-not $selected){$selected='keep'}
                if($selected -notin $options){throw 'DECISION_INVALID'};$review[$item.path]=$selected
            }
            $result=New-KosPlan $root $Operation $answerObject $profile $review;$plan=$result.plan
            Write-Output (Get-KosJson $plan);$approved=(Read-Host 'Approve this revised plan? [yes/no]') -eq 'yes'
        }
        elseif($choice -eq '3'){Write-Output (Get-KosReport $plan)}
        elseif($choice -eq '4'){Export-KosResult (Read-Host 'Export destination outside target') (Get-KosBytes $plan)}
    }
    if($plan.blocked){exit 2}
    if(-not $approved){Write-Output 'Approval required: review plan, then pass -Approve.';exit 2}
    $run=Invoke-KosApply $root $plan $result.payload
    Write-Output (Get-KosReport $plan $(if($run){'COMPLETE'}else{'UNCHANGED'}) $run)
    if($Operation -eq 'rollback' -and $plan.recovery -eq 'incomplete'){exit 4};exit 0
} catch {
    $failure=$_.Exception;$rule=($failure.Message -split ':')[0];$exitCode=2
    while($failure){if($failure -is [IO.IOException] -or $failure -is [UnauthorizedAccessException]){$exitCode=3};$failure=$failure.InnerException}
    if($rule -notmatch '^[A-Z_]+$'){$rule=if($exitCode -eq 3){'IO_FAILURE'}else{'INPUT_INVALID'}}
    $blocked=@{operation=$(if($Operation){$Operation}elseif($PackageCommand){$PackageCommand}else{'new'});targetType='unsafe-or-invalid';blocked=$true;items=@(@{path='target';classification='BLOCKED';action='BLOCK';rule=$rule})}
    [Console]::Error.WriteLine('BLOCKED: '+$rule);Write-Output (Get-KosJson $blocked)
    try{if($PlanOutput){Export-KosResult $PlanOutput (Get-KosBytes $blocked)};if($Report){Export-KosResult $Report ($script:Utf8.GetBytes((Get-KosReport $blocked 'BLOCKED')))}}catch{}
    exit $exitCode
}
