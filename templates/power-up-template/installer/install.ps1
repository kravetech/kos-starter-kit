[CmdletBinding()]
param([switch]$DryRun)
$ErrorActionPreference = "Stop"

# TODO: install this Power-Up's own runtime dependencies (if any) into its
# external install directory. Do not touch any KOS vault from here -- vault
# registration and folder initialization are separate steps (see
# initialize.ps1 and docs/installation.md).

if ($DryRun) {
    Write-Output "Dry run: kos-example install would run here. No changes made."
    exit 0
}

Write-Output "kos-example: nothing to install yet (template stub)."
exit 0
