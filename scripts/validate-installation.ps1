[CmdletBinding()]
param([Parameter(Mandatory)][string]$InstallationRoot, [string]$Report)
$ErrorActionPreference = "Stop"
try {
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/engine.ps1')
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/packages-v1.ps1')
    $root=Get-KosTarget $InstallationRoot
    $findings=Test-KosInstallation $root
    $status=if(@($findings | Where-Object {$_.severity -eq 'error'}).Count){'FAIL'}else{'PASS'}
    $body=@('# Installation validation','','Status: '+$status,'')
    foreach($finding in $findings){$body+=($finding.severity+' '+$finding.rule+': '+$finding.path)}
    if($Report){
        $path=[IO.Path]::GetFullPath($Report);$null=Get-KosSafe (Split-Path -Parent $path) (Split-Path -Leaf $path)
        $null=[IO.Directory]::CreateDirectory((Split-Path -Parent $path));Write-KosDurable $path ($script:Utf8.GetBytes(($body -join "`n")+"`n")) $true
    }else{$body | Write-Output}
    if($status -eq 'PASS'){exit 0};exit 2
}catch{[Console]::Error.WriteLine('ERROR: '+$_.Exception.Message);exit 2}
