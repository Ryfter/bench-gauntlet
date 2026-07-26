param(
  [Parameter(Mandatory=$true)][string]$Dimension,
  [Parameter(Mandatory=$true)][string]$Tiers,
  [Parameter(Mandatory=$true)][string]$Brief,
  [string]$Out = "batch.json",
  [string]$Provider = "grok-cli"
)

$scratch  = $PSScriptRoot
$contract = Get-Content (Join-Path $scratch "grok_contract.md") -Raw

$prompt = @"
$contract

## YOUR ASSIGNMENT FOR THIS BATCH

Dimension: $Dimension
Tiers to produce (one case each, in this order): $Tiers

$Brief

Produce exactly $(($Tiers -split ',').Count) cases. Remember: raw JSON array only,
starting with [ and ending with ]. No fences, no commentary.
"@

. "$HOME/.claude/scripts/fleet-lib.ps1"
$r = Invoke-Fleet -Name $Provider -Prompt $prompt
$text = ($r.stdout | Out-String).Trim()

# Grok sometimes wraps output in fences or adds a preamble despite instructions.
if ($text -match '(?s)```(?:json)?\s*(.*?)\s*```') { $text = $Matches[1] }
$start = $text.IndexOf('[')
$end   = $text.LastIndexOf(']')
if ($start -ge 0 -and $end -gt $start) { $text = $text.Substring($start, $end - $start + 1) }

$outPath = Join-Path $scratch $Out
$text | Set-Content -Path $outPath -Encoding utf8

Write-Host "provider=$Provider exit=$($r.exit_code) dur=$($r.duration_s)s chars=$($text.Length)"
try {
  $parsed = $text | ConvertFrom-Json
  Write-Host "parsed OK: $($parsed.Count) cases -> $outPath"
  $parsed | ForEach-Object { Write-Host "   $($_.tier)  $($_.id)" }
} catch {
  Write-Host "JSON PARSE FAILED - inspect $outPath" -ForegroundColor Red
  Write-Host $text.Substring(0, [Math]::Min(400, $text.Length))
}
