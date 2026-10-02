[CmdletBinding()]
param([switch]$DryRun)
$ErrorActionPreference = "Stop"

# TODO: implement the sequence in docs/upgrade.md -- check kos_compatibility,
# back up current manifest/config, preserve user data, migrate only when
# declared, update the registry version only after validation passes.

if ($DryRun) {
    Write-Output "Dry run: kos-example upgrade would run here. No changes made."
    exit 0
}

Write-Output "kos-example: upgrade not yet implemented (template stub)."
exit 0
