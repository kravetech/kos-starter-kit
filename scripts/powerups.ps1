[CmdletBinding()]
param(
    [Parameter(Mandatory, Position = 0)]
    [ValidateSet("discover", "status", "register")]
    [string]$Command,
    [Parameter(Mandatory)][string]$InstallationRoot,
    [string]$HomeDirectory,
    [string]$Id
)
$ErrorActionPreference = "Stop"
if ($Command -eq "register") {
    [Console]::Error.WriteLine("ERROR: Legacy Power-Up discovery is read-only. Use install.ps1 -PackageCommand install after reviewing an immutable package.")
    exit 2
}
. (Join-Path (Split-Path -Parent $PSScriptRoot) "installer\powerups.ps1")

function Resolve-PowerUpsHomeDirectory {
    param([object]$Settings, [string]$Override)
    if ($Override) { return $Override }
    $section = $Settings["power_ups"]
    if ($null -eq $section) { return $null }
    $envName = [string]$section["home_environment_variable"]
    if ($envName) {
        $envValue = [Environment]::GetEnvironmentVariable($envName)
        if ($envValue) { return $envValue }
    }
    $homeDir = [string]$section["home_directory"]
    if (-not $homeDir -or $homeDir.StartsWith("<")) { return $null }
    return $homeDir
}

function Get-KosCoreContractVersion {
    param([string]$Root)
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/engine.ps1')
    $statePath = Get-KosSafe $Root $script:KosState
    if (Test-Path -LiteralPath $statePath -PathType Leaf) {
        try {
            $state = Read-KosJson $statePath
            if ($state -is [Collections.IDictionary] -and $state.psbase.Keys -ccontains 'kosContractVersion') {
                $contract = $state['kosContractVersion']
                if ($contract -is [string] -and $contract -cmatch '\A[0-9]+\.[0-9]+\.[0-9]+\z') { return $contract }
            }
        } catch { }
    }
    $path = Get-KosSafe $Root 'ARCHITECTURE.md'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
    $reader = $null
    try {
        $reader = [IO.StreamReader]::new($path, [Text.UTF8Encoding]::new($false, $true), $false)
        $first = $reader.ReadLine()
        if ($null -eq $first -or $first.TrimStart([char]0xfeff).TrimEnd() -cne '---') { return $null }
        $contract = $null
        $seen = $false
        while ($null -ne ($line = $reader.ReadLine())) {
            $line = $line.TrimEnd()
            if ($line -in @('---', '...')) { return $contract }
            $field = [regex]::Match($line, '^(?:kos_contract_version|"kos_contract_version"|''kos_contract_version'')[ \t]*:(.*)$')
            if ($field.Success) {
                if ($seen) { return $null }
                $seen = $true
                $scalar = [regex]::Match($field.Groups[1].Value, '^[ \t]+(["'']?)([0-9]+\.[0-9]+\.[0-9]+)\1(?:[ \t]+#.*)?$')
                if ($scalar.Success) { $contract = $scalar.Groups[2].Value }
            }
        }
    } catch [Text.DecoderFallbackException] { return $null }
    catch [IO.IOException] { return $null }
    catch [UnauthorizedAccessException] { return $null }
    finally { if ($reader) { $reader.Dispose() } }
    return $null
}

try {
    $root = [System.IO.Path]::GetFullPath($InstallationRoot)
    $powerUpsDir = Join-Path $root "00 - System\Power-Ups"
    $registryPath = Join-Path $powerUpsDir "registry.yaml"
    $settingsPath = Join-Path $powerUpsDir "settings.yaml"
    if (-not (Test-Path -LiteralPath $registryPath -PathType Leaf)) {
        Write-Output "SKIPPED: Power-Ups support is not enabled for this installation: $root"
        exit 0
    }
    $settings = if (Test-Path -LiteralPath $settingsPath -PathType Leaf) { ConvertFrom-KosYaml (Get-Content -LiteralPath $settingsPath -Raw) } else { [ordered]@{} }
    $registry = ConvertFrom-KosYaml (Get-Content -LiteralPath $registryPath -Raw)
    $registeredIds = @()
    $existingEntries = $registry["power_ups"]
    if ($null -ne $existingEntries) {
        foreach ($e in $existingEntries) { if ($e -is [System.Collections.IDictionary]) { $registeredIds += [string]$e["id"] } }
    }
    $powerUpsHome = Resolve-PowerUpsHomeDirectory -Settings $settings -Override $HomeDirectory

    if ($Command -eq "discover") {
        if (-not $powerUpsHome) {
            Write-Output "WARN no resolvable Power-Ups home directory (pass -HomeDirectory, set the configured environment variable, or set settings.yaml power_ups.home_directory)"
            exit 0
        }
        $contract = Get-KosCoreContractVersion -Root $root
        $candidates = Find-KosPowerUps -HomeDirectory $powerUpsHome -RegisteredIds $registeredIds -KosVersion $contract
        if ($candidates.Count -eq 0) {
            Write-Output "No candidate Power-Ups found under $powerUpsHome"
            exit 0
        }
        foreach ($candidate in $candidates) {
            Write-Output "[$($candidate.Status)] $($candidate.Id) ($($candidate.Path))"
            foreach ($item in $candidate.Errors) { Write-Output "    ERROR $item" }
            foreach ($item in $candidate.Warnings) { Write-Output "    WARN  $item" }
        }
        $hasError = @($candidates | Where-Object { $_.Status -eq "ERROR" }).Count -gt 0
        if ($hasError) { exit 2 } else { exit 0 }
    }

    if ($Command -eq "status") {
        $result = Test-KosPowerUpRegistry -Registry $registry
        $entries = $registry["power_ups"]
        if ($null -eq $entries -or $entries.Count -eq 0) {
            Write-Output "No Power-Ups registered."
        } else {
            foreach ($entry in $entries) {
                Write-Output "$($entry['id']): status=$($entry['status']) version=$($entry['version']) mode=$($entry['installation_mode'])"
                $installPath = [string]$entry['install_path']
                $resolvedInstall = $installPath
                $envMatch = [regex]::Match($installPath, '\$\{([A-Za-z_][A-Za-z0-9_]*)\}')
                if ($envMatch.Success) {
                    $envValue = [Environment]::GetEnvironmentVariable($envMatch.Groups[1].Value)
                    if ($envValue) { $resolvedInstall = $installPath.Replace($envMatch.Value, $envValue) } else { $resolvedInstall = $null }
                }
                if ($resolvedInstall -and -not (Test-Path -LiteralPath $resolvedInstall)) {
                    Write-Output "  WARN external runtime not found at $installPath"
                }
                $manifestField = [string]$entry['manifest']
                if ($manifestField -and -not (Test-Path -LiteralPath (Join-Path $powerUpsDir $manifestField) -PathType Leaf)) {
                    Write-Output "  WARN local manifest copy missing: $manifestField"
                }
            }
        }
        foreach ($item in $result.Errors) { Write-Output "ERROR $item" }
        foreach ($item in $result.Warnings) { Write-Output "WARN $item" }
        if ($result.Errors.Count -gt 0) { exit 2 } else { exit 0 }
    }

    if ($Command -eq "register") {
        if (-not $Id) { throw "-Id <power-up-id> is required for register." }
        if (-not $powerUpsHome) { throw "No resolvable Power-Ups home directory; pass -HomeDirectory or configure settings.yaml/environment variable." }
        $contract = Get-KosCoreContractVersion -Root $root
        $candidates = Find-KosPowerUps -HomeDirectory $powerUpsHome -RegisteredIds $registeredIds -KosVersion $contract
        $match = $candidates | Where-Object { $_.Id -eq $Id } | Select-Object -First 1
        if (-not $match) { throw "'$Id' was not found under the configured Power-Ups home ($powerUpsHome)." }
        if ($match.Status -eq "ERROR") {
            Write-Output "'$Id' failed manifest validation and cannot be registered:"
            foreach ($item in $match.Errors) { Write-Output "  - $item" }
            exit 2
        }
        $manifestsDir = Join-Path $powerUpsDir "manifests"
        New-Item -ItemType Directory -Path $manifestsDir -Force | Out-Null
        Copy-Item -LiteralPath $match.ManifestPath -Destination (Join-Path $manifestsDir "$Id.yaml") -Force
        $now = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        $homeEnv = [string]$settings['power_ups']['home_environment_variable']
        if (-not $homeEnv) { $homeEnv = "KOS_POWERUPS_HOME" }
        $manifest = $match.Manifest
        $defaultMode = $null
        if ($manifest['installation'] -is [System.Collections.IDictionary]) { $defaultMode = $manifest['installation']['default_mode'] }
        if (-not $defaultMode) { $defaultMode = "external" }
        $entry = [ordered]@{
            id                   = $Id
            name                 = $(if ($manifest['name']) { [string]$manifest['name'] } else { $Id })
            version              = [string]$manifest['version']
            status               = "enabled"
            installation_mode    = [string]$defaultMode
            install_path         = "`${$homeEnv}/$Id"
            manifest             = "manifests/$Id.yaml"
            initialized_targets  = @()
            installed_at         = $now
            updated_at           = $now
        }
        Register-KosPowerUp -RegistryPath $registryPath -Entry $entry
        Write-Output "Registered '$Id' in $registryPath"
        exit 0
    }
} catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 3
}
