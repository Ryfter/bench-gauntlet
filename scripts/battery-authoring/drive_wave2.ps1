# Wave 2: top up the thin dimensions toward ~8-10 cases each (~110 total).
$scratch = $PSScriptRoot

$xpred = @"
CRUXEval-style CODE REASONING, not code writing. Show a short self-contained Python function
(5-15 lines, no imports) and have the model PREDICT its return values by tracing the logic.
The prompt shows the source, lists exactly 10 numbered call expressions, and instructs the
model to reply with ONLY 10 assignments: ANSWER_1 = <value> through ANSWER_10 = <value>.
Hidden tests read them from the namespace:
    def check(ns):
        def t(thunk):
            try: return bool(thunk())
            except Exception: return False
        return [ t(lambda: ns.get("ANSWER_1") == <expected literal>), ... ten total ]
Do NOT use the `if not callable(f)` guard here - there is no function to look up.
`reference` is exactly the 10 correct assignments; `wrong` has 3-5 of them mis-traced.
Trace your own function step by step to compute every expected value - one wrong literal
invalidates the case. Favour state mutation across calls, accumulators, early returns, slice
boundaries, and integer vs float division.
"@

$tauth = @"
The model is given a spec plus an implementation containing a PLANTED bug, and must write a
function named exactly test_suite(fn) that takes a candidate function and returns a list of
booleans (True = that check passed). Hidden tests import the model's test_suite and run it
against BOTH a correct implementation and the buggy one, scoring whether its tests pass the
correct one AND catch the buggy one. This measures whether the model writes tests that
actually discriminate, not tests that merely run.
"@

$dims = @(
  @{ n="multi-function";        t="T2,T3,T3,T4"; b="Helper + caller, both exercised by name. Domains: tariff computation with a band lookup helper, shift rostering with an overlap helper, manifest validation with a checksum helper, pricing with a rounding helper." },
  @{ n="multi-function";        t="T1,T2,T3,T4"; b="Helper + caller again, different domains: unit conversion, address normalisation, retry backoff schedules, seat-block allocation. The caller must genuinely delegate - hidden tests call the helper directly with inputs the caller never produces." },
  @{ n="surface-constraints";   t="T1,T2,T3,T3"; b="Correctness plus a hard surface-form constraint: no imports, single expression, mutate in place and return None, must use a generator, must not call sorted(). Assertions must CHECK THE CONSTRAINT behaviourally (the input object was mutated; the result is lazy; a large input is not fully materialised), not just the answer." },
  @{ n="surface-constraints";   t="T2,T3,T4,T4"; b="As above, harder: forbid both sorted() and .sort() so the model must merge manually; require a generator that stays lazy under early termination; require in-place mutation that preserves list identity while reordering." },
  @{ n="complexity-constrained"; t="T2,T3,T3,T4"; b="Correctness plus a stated complexity bound, with one assertion running a LARGE input (200k+) that only finishes in time if the bound was met - an accidentally quadratic solution blows the sandbox timeout. Keep the reference comfortably inside the bound. Domains: prefix sums, sliding windows, single-pass grouping, monotonic stacks." },
  @{ n="bug-fix";               t="T1,T2,T3,T4"; b="Broken code plus the failing symptom; the model patches it. Hidden tests verify the bug is fixed AND untouched behaviour still works, so an over-broad rewrite loses points. Bugs: wrong comparison operator, mutating during iteration, a truthiness test that mishandles 0 or empty string, a boundary excluded that should be included." },
  @{ n="robustness-contracts";  t="T2,T3,T3,T4"; b="Must raise a SPECIFIC exception type on specific invalid input and behave normally otherwise. Hidden tests return True only for the exact expected type. Mix ValueError, TypeError, KeyError, IndexError and a custom exception the prompt defines. Include cases where a NEARBY wrong exception type would be tempting." },
  @{ n="behavior-preserving-refactor"; t="T1,T2,T3,T4"; b="Working but ugly code (deep nesting, duplicated branches, magic numbers, repeated parsing) refactored to a stated shape. Hidden tests assert behaviour is UNCHANGED across many inputs including edge cases. The embedded original must be genuinely correct, including its quirks, so any drift is the model's fault." },
  @{ n="test-authoring";        t="T1,T2,T3,T4"; b=$tauth },
  @{ n="execution-prediction";  t="T1,T2,T3,T4"; b=$xpred },
  @{ n="execution-prediction";  t="T2,T3,T3,T4"; b=$xpred },
  @{ n="class-level-stateful";  t="T1,T2,T3,T4"; b="Multi-method classes, invariants across an operation sequence. New domains: a seat-hold expiry board, a two-phase commit log, a bounded LRU-ish cache with pinning, a running-median tracker. Hidden tests drive a long call sequence and assert the invariant survives." }
)

$i = 100
foreach ($d in $dims) {
  $i++
  $out = "batch-{0}-{1}.json" -f $i, $d.n
  Start-Job -ScriptBlock {
    param($scratch, $dim, $tiers, $brief, $out)
    & (Join-Path $scratch "run_batch.ps1") -Dimension $dim -Tiers $tiers -Brief $brief -Out $out
  } -ArgumentList $scratch, $d.n, $d.t, $d.b, $out | Out-Null
  while (@(Get-Job -State Running).Count -ge 3) { Start-Sleep -Seconds 5 }
}

Get-Job | Wait-Job | Out-Null
Get-Job | ForEach-Object { Receive-Job $_ }
Get-Job | Remove-Job
Write-Host "WAVE 2 DONE"
