# Finish a Gauntlet fleet run inside the quiet window (2am-6am).
#
# Kevin's desktop is near-silent in normal use, so long benchmarks belong at
# night rather than being started opportunistically during the day. This resumes
# an existing run id -- completed cells are skipped, so it is safe to re-invoke.
#
# The run releases the GPU on a clean exit; models are also loaded with a TTL as
# a backstop in case this is killed hard. Stops itself at the end of the window.
param(
    [string] $RunId  = "fleet-0726b",
    [string] $StopAt = "06:00"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$python = ".\.venv\Scripts\python.exe"
$models = @(
    "llama-3.2-1b-instruct", "nvidia/nemotron-3-nano-4b",
    "matrixportalx/tulu-3.1-8b-supernova", "google/gemma-4-12b",
    "qwen/qwen3.5-9b", "openai_gpt-oss-20b", "nvidia/nemotron-3-nano",
    "google/gemma-4-31b", "zai-org/glm-4.7-flash"
)

$modelArgs = @()
foreach ($m in $models) { $modelArgs += @("--model", $m) }

# Refuse to start if a run is already going. This exists as a safety net for a
# run started earlier in the day, so it must never become a second writer to the
# same run directory -- two processes appending to cells.jsonl would corrupt it.
$existing = & $python -m gauntlet.cli status 2>&1 | Out-String
if ($existing -match "RUNNING") {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] a run is already in progress - nothing to do"
    Write-Host $existing.Trim()
    exit 0
}

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] resuming $RunId (quiet window, stop by $StopAt)"

# --no-overlay: nobody is at the machine, and the lamp would only add a poll loop.
$proc = Start-Process -FilePath $python -PassThru -NoNewWindow -ArgumentList (
    @("-m", "gauntlet.cli", "run", "--resume", $RunId, "--no-overlay") + $modelArgs
)

# Hard stop at the end of the window: being finished matters less than the
# machine being quiet again before Kevin is back at it.
$deadline = [datetime]::Today.AddDays(
    $(if ((Get-Date).TimeOfDay -gt [timespan]::Parse($StopAt)) { 1 } else { 0 })
).Add([timespan]::Parse($StopAt))

while (-not $proc.HasExited) {
    if ((Get-Date) -ge $deadline) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] window closed - stopping run"
        Stop-Process -Id $proc.Id -Force -Confirm:$false
        Start-Sleep -Seconds 5
        # A hard stop skips the in-process cleanup, so free the GPU explicitly.
        & $python -m gauntlet.cli release
        break
    }
    Start-Sleep -Seconds 60
}

Write-Host "[$(Get-Date -Format 'HH:mm:ss')] done"
& $python -m gauntlet.cli status
