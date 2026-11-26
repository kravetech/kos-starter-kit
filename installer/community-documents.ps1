# Patch only known release fields; preserve the vault's own text and encoding.
function Test-KosInsideCodeFence([string]$Prefix) {
    $opening = ''
    foreach ($fence in [regex]::Matches($Prefix, '(?m)^ {0,3}(`{3,}|~{3,})([^\n]*)$')) {
        $marker = $fence.Groups[1].Value
        $tail = $fence.Groups[2].Value
        if ($opening) {
            if ($marker.StartsWith($opening) -and -not $tail.Trim()) { $opening = '' }
        } elseif ($marker.StartsWith('~') -or -not $tail.Contains('`')) {
            $opening = $marker
        }
    }
    return [bool]$opening
}

function Get-KosCommunityDocumentUpdate([string]$Name, [byte[]]$Raw, $Release) {
    $encoding = [Text.UTF8Encoding]::new($false, $true)
    try { $text = $encoding.GetString($Raw) }
    catch [Text.DecoderFallbackException] { return ,$Raw }
    $bom = $text.StartsWith([string][char]0xfeff, [StringComparison]::Ordinal)
    if ($bom) { $text = $text.Substring(1) }
    $newline = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $body = $text.Replace($newline, "`n")
    if ($body.Contains("`r") -or $body.Contains([string][char]0) -or
        ($newline -eq "`r`n" -and $text.Replace($newline, '').Contains("`n"))) { return ,$Raw }
    $header = ''
    if ($Name -ceq 'ARCHITECTURE.md') {
        if (-not $body.StartsWith("---`n", [StringComparison]::Ordinal)) { return ,$Raw }
        $end = $body.IndexOf("`n---`n", 4, [StringComparison]::Ordinal)
        if ($end -lt 0) { return ,$Raw }
        $header = $body.Substring(0, $end)
        $body = $body.Substring($end + 5)
    }
    $rules = Read-KosJson (Join-Path $PSScriptRoot 'community-document-rules.json')
    foreach ($rule in $rules[$Name]) {
        $original = if ($rule['frontMatter']) { $header } else { $body }
        $hits = @([regex]::Matches($original, $rule.pattern, [Text.RegularExpressions.RegexOptions]::Multiline) | Where-Object {
            $rule['frontMatter'] -or -not (Test-KosInsideCodeFence $original.Substring(0, $_.Index))
        })
        if ($hits.Count -eq 0 -and $rule['optional']) { continue }
        if ($hits.Count -ne 1) { return ,$Raw }
        $hit = $hits[0]
        $replacement = [regex]::Replace($rule.replacement, '{{(\w+)}}', {
            param($token)
            return [string]$Release[$token.Groups[1].Value]
        })
        $updated = $original.Substring(0, $hit.Index) + $replacement + $original.Substring($hit.Index + $hit.Length)
        if ($rule['frontMatter']) { $header = $updated } else { $body = $updated }
    }
    if ($header) { $body = $header + "`n---`n" + $body }
    if ($bom) { $body = [string][char]0xfeff + $body }
    return ,$encoding.GetBytes($body.Replace("`n", $newline))
}
