[CmdletBinding()]
param([switch]$DryRun)
$ErrorActionPreference = "Stop"

# TODO: implement the sequence in docs/uninstall.md -- disable first, show
# affected files/workspaces, remove the runtime only after approval, preserve
# user data by default, and never touch canonical KOS files.

if ($DryRun) {
    Write-Output "Dry run: kos-example uninstall would run here. No changes made."
    exit 0
}

Write-Output "kos-example: uninstall not yet implemented (template stub)."
exit 0
