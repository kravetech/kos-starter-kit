[CmdletBinding()]
param([string]$Root, [string]$Output)
$ErrorActionPreference = "Stop"
try {
    $kitRoot = Split-Path -Parent $PSScriptRoot
    if (-not $Root) { $Root = $kitRoot }
    . (Join-Path $kitRoot 'installer/engine.ps1')
    $manifestRoot = [System.IO.Path]::GetFullPath($Root)
    if (-not $Output) { $Output = Join-Path $manifestRoot "build\file-manifest.json" }
    $Output = Get-KosSafe ([IO.Path]::GetFullPath($Output))
    $sourceList = Get-KosSafe $manifestRoot 'installer/release-files.json'
    $isSource = (Test-Path -LiteralPath $sourceList) -or (Test-Path -LiteralPath (Get-KosSafe $manifestRoot 'scripts/release.py'))
    $list = if ($isSource) { $sourceList } else { Get-KosSafe $manifestRoot 'installer/archive-files.json' }
    [string[]]$paths = (Read-KosJson $list).files
    [Array]::Sort($paths, [StringComparer]::Ordinal)
    $files = @(foreach ($relative in $paths) {
        $path = Get-KosSafe $manifestRoot $relative
        if ($path -eq $Output) {
            [Console]::Error.WriteLine('BLOCKED: MANIFEST_OUTPUT_IS_INPUT')
            exit 2
        }
        $bytes = [IO.File]::ReadAllBytes($path)
        [pscustomobject]@{
            path = $relative
            bytes = $bytes.LongLength
            sha256 = Get-KosHash $bytes
        }
    })
    New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null
    $json = [pscustomobject]@{ generated_at=[DateTimeOffset]::Now.ToString("o"); files=$files } | ConvertTo-Json -Depth 6
    $pending = Join-Path (Split-Path -Parent $Output) ([IO.Path]::GetRandomFileName())
    [IO.File]::Open($pending, [IO.FileMode]::CreateNew).Dispose()
    try {
        Write-KosDurable $pending ($script:Utf8.GetBytes($json + "`n"))
        Move-KosAtomic $pending $Output
    } finally {
        if ([IO.File]::Exists($pending)) { [IO.File]::Delete($pending) }
    }
    Write-Output "Manifest generated: $Output"
    exit 0
} catch { [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)"); exit 3 }
