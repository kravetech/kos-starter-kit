[CmdletBinding()]
param([string]$Root = (Split-Path -Parent $PSScriptRoot), [string]$Output)
$ErrorActionPreference = "Stop"
try {
    . (Join-Path (Split-Path -Parent $PSScriptRoot) 'installer/engine.ps1')
    $manifestRoot = [System.IO.Path]::GetFullPath($Root)
    if (-not $Output) { $Output = Join-Path $manifestRoot "build\file-manifest.json" }
    $allowlist=Read-KosJson (Get-KosSafe $manifestRoot 'installer/release-files.json')
    $files = @($allowlist.files | Sort-Object | ForEach-Object {
        $relative=$_;$file=Get-Item -LiteralPath (Get-KosSafe $manifestRoot $relative)
        [pscustomobject]@{
            path=$relative
            bytes=$file.Length
            sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null
    [pscustomobject]@{ generated_at=[DateTimeOffset]::Now.ToString("o"); files=$files } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Output -Encoding utf8
    Write-Output "Manifest generated: $Output"
    exit 0
} catch { [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)"); exit 3 }
