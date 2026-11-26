[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallationRoot, [string]$Report)
$ErrorActionPreference = "Stop"
try {
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/engine.ps1')
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/packages-v1.ps1')
    $root=Get-KosTarget $InstallationRoot
    $installedRelease = @{}
    $findings=Test-KosInstallation $root $installedRelease
    $status=if(@($findings | Where-Object {$_.severity -eq 'error'}).Count){'FAIL'}else{'PASS'}
    $title = if ($installedRelease.communityVersion) { "# KOS Community $($installedRelease.communityVersion) Installation Validation Report" } else { '# KOS Community Installation Validation Report' }
    $body=@($title, '', "Status: $status", '')
    foreach($finding in $findings){$body+=($finding.severity+' '+$finding.rule+': '+$finding.path)}
    if($Report){
        $path = Get-KosExportPath $Report $root
        $null=[IO.Directory]::CreateDirectory((Split-Path -Parent $path));Write-KosDurable $path ($script:Utf8.GetBytes(($body -join "`n")+"`n")) $true
    }else{$body | Write-Output}
    if($status -eq 'PASS'){exit 0};exit 2
}catch{[Console]::Error.WriteLine('ERROR: '+$_.Exception.Message);exit 2}
