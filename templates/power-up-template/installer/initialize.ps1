[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$TargetFolder,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"

# TODO: verify $TargetFolder exists inside the approved KOS vault, then create
# only the declared workspace (see manifest.yaml -> workspace) under
# "$TargetFolder/.kos/power-ups/kos-example/" without touching existing files.
# Record the target in this Power-Up's registry.yaml entry
# (initialized_targets) once the KOS-side registration step does so.

if ($DryRun) {
    Write-Output "Dry run: would initialize kos-example for '$TargetFolder'. No changes made."
    exit 0
}

Write-Output "kos-example: initialization not yet implemented for '$TargetFolder' (template stub)."
exit 0
