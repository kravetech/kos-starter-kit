[CmdletBinding()]
param([string]$Root = (Split-Path -Parent $PSScriptRoot), [string]$Output)
$ErrorActionPreference = "Stop"
try {
    $manifestRoot = [System.IO.Path]::GetFullPath($Root)
    if (-not $Output) { $Output = Join-Path $manifestRoot "build\file-manifest.json" }
    $files = @(Get-ChildItem -LiteralPath $manifestRoot -Recurse -File -Force | Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' } | Sort-Object FullName | ForEach-Object {
        [pscustomobject]@{
            path=$_.FullName.Substring($manifestRoot.Length).TrimStart('\').Replace('\','/')
            bytes=$_.Length
            sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
    New-Item -ItemType Directory -Path (Split-Path -Parent $Output) -Force | Out-Null
    [pscustomobject]@{ generated_at=[DateTimeOffset]::Now.ToString("o"); files=$files } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Output -Encoding utf8
    Write-Output "Manifest generated: $Output"
    exit 0
} catch { [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)"); exit 3 }
