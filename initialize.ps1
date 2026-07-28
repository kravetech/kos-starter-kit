[CmdletBinding()]
param(
    [ValidateSet("auto","codex","claude")]
    [string]$Agent = "auto",
    [string]$Answers,
    [switch]$DryRun,
    [switch]$Resume,
    [switch]$Migration
)

$ErrorActionPreference = "Stop"
$starterRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$installer = Join-Path $starterRoot "KOS-INSTALLER.md"
$logRoot = Join-Path $starterRoot "logs"
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath = Join-Path $logRoot ("initialize-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

try {
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
        throw "KOS-INSTALLER.md not found in starter-kit root."
    }
    $codex = Get-Command codex -ErrorAction SilentlyContinue
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if ($Agent -eq "auto") {
        if ($codex) { $Agent = "codex" }
        elseif ($claude) { $Agent = "claude" }
        else { throw "Neither codex nor claude was found on PATH." }
    }
    if ($Agent -eq "codex" -and -not $codex) { throw "codex was not found on PATH." }
    if ($Agent -eq "claude" -and -not $claude) { throw "claude was not found on PATH." }
    $answerPath = ""
    if ($Answers) {
        $candidate = if ([System.IO.Path]::IsPathRooted($Answers)) { $Answers } else { Join-Path $starterRoot $Answers }
        $answerPath = [System.IO.Path]::GetFullPath($candidate)
        if (-not (Test-Path -LiteralPath $answerPath -PathType Leaf)) { throw "Answer file not found: $answerPath" }
    }
    $directives = @("Read KOS-INSTALLER.md and execute the installation.")
    if ($answerPath) { $directives += "Use answer file: $answerPath" }
    if ($DryRun) { $directives += "Run in dry-run mode only." }
    if ($Resume) { $directives += "Resume from saved installer state." }
    if ($Migration) { $directives += "Use migration mode and preserve existing files." }
    $prompt = $directives -join " "
    @(
        "Time: $([DateTimeOffset]::Now.ToString('o'))"
        "Starter root: $starterRoot"
        "Agent: $Agent"
        "Answer file supplied: $([bool]$answerPath)"
        "Dry run: $DryRun"
        "Resume: $Resume"
        "Migration: $Migration"
    ) | Set-Content -LiteralPath $logPath -Encoding utf8
    Push-Location $starterRoot
    try {
        if ($Agent -eq "codex") {
            & $codex.Source -C $starterRoot $prompt
        }
        else {
            & $claude.Source --add-dir $starterRoot $prompt
        }
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    Add-Content -LiteralPath $logPath -Value "Exit code: $exitCode"
    exit $exitCode
}
catch {
    Add-Content -LiteralPath $logPath -Value "ERROR: $($_.Exception.Message)"
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 3
}
