# Fan out case authoring across the remaining dimensions, 3 at a time.
# Each job produces one JSON batch file; validation happens separately so a
# bad batch never reaches the battery.
$scratch = $PSScriptRoot

$dims = @(
  @{ n="stdlib-api-use";        t="T1,T2,T3,T4"; b="Multi-clause specs requiring correct use of the standard library: re, itertools, collections, datetime, csv, json, pathlib, dataclasses, functools, heapq, bisect, textwrap. The difficulty is in combining several clauses correctly, not in the algorithm." },
  @{ n="stdlib-api-use";        t="T2,T3,T3,T4"; b="As above, but pick DIFFERENT stdlib modules and different domains than a typical first pass would choose. Favour collections.Counter/deque, heapq, bisect, functools.reduce, textwrap and zoneinfo-free datetime arithmetic." },
  @{ n="class-level-stateful";  t="T1,T2,T3,T4"; b="Multi-method classes with interdependent methods, shared mutable state, and invariants that must hold across a SEQUENCE of operations. The hidden tests should drive a sequence of calls and assert the invariant survives. State the exact class name and method signatures." },
  @{ n="class-level-stateful";  t="T2,T3,T3,T4"; b="As above with different domains: a booking ledger, a windowed rate limiter, an undo/redo stack, a hierarchical counter. Emphasise invariants that only break after several operations." },
  @{ n="multi-function";        t="T1,T2,T3,T4"; b="The model must write a helper function AND a caller that uses it correctly. Hidden tests exercise BOTH by name, so the prompt must state both exact names and signatures. Failure to factor properly should cost real points." },
  @{ n="complexity-constrained"; t="T2,T3,T3,T4"; b="Correctness PLUS a stated complexity bound. The hidden tests include one assertion that runs the function against a LARGE input (e.g. 200k elements) which completes quickly only if the model met the bound; an accidentally-quadratic solution will blow the sandbox timeout. Keep the reference solution comfortably within the bound." },
  @{ n="bug-fix";               t="T1,T2,T3,T4"; b="Give the model broken code plus the symptom of a failing test, and ask for a fix. The prompt embeds the buggy source. Hidden tests verify the bug is fixed AND that untouched behaviour still works, so an over-broad rewrite loses points. State the exact function name to keep." },
  @{ n="surface-constraints";   t="T1,T2,T3,T4"; b="Correctness plus a hard surface-form constraint stated in the prompt: must not import anything, must be a single expression, must mutate in place and return None, must use a generator, must not call sorted(). Include assertions that CHECK THE CONSTRAINT by inspecting behaviour (e.g. that the input list object was mutated, or that the result is a lazy generator), not just the answer." },
  @{ n="robustness-contracts";  t="T1,T2,T3,T4"; b="The function must raise a SPECIFIC exception type under specific invalid input, and behave normally otherwise. Hidden tests use a try/except that returns True only when the exact expected exception type is raised. Mix ValueError, TypeError, KeyError and a custom exception the prompt defines." },
  @{ n="behavior-preserving-refactor"; t="T2,T3,T3,T4"; b="Give working but ugly code (deep nesting, duplicated branches, magic numbers) and ask for a refactor to a stated shape. Hidden tests assert behaviour is UNCHANGED across many inputs including edge cases. The embedded original must be genuinely correct so any behavioural drift is the model's fault." },
  @{ n="test-authoring";        t="T2,T3,T3,T4"; b="Give a spec plus an implementation containing a PLANTED bug, and ask the model to write a test function named exactly test_suite() that returns a list of booleans (True = a check passed) against a function it is given. Hidden tests import the model's test_suite, run it against BOTH a correct implementation and the buggy one, and score whether its tests pass the correct one and CATCH the buggy one. This measures whether the model writes tests that actually discriminate." },
  @{ n="data-text-munging";     t="T1,T2,T3,T4"; b="Realistic parsing and reshaping: log lines, CSV rows, semver ranges, ISO timestamps, config blocks, fixed-width records. The everyday work a coding harness would offload. Edge cases: malformed rows, trailing delimiters, quoted fields with embedded separators, mixed line endings, blank lines." },
  @{ n="data-text-munging";     t="T2,T3,T3,T4"; b="As above with harder shapes: nested key=value with escaping, duration strings like '1h30m', byte-size suffixes, ambiguous date orderings that the spec must pin down, and grouping/aggregation over parsed records." },
  @{ n="adversarial-correctness"; t="T2,T3,T3,T4"; b="A second pass on adversarial edge-case correctness. Use domains different from stock reconciliation, gap lengths, span merging and auction ranking. Emphasise off-by-one, tie-breaking rules, and behaviour on inputs at exactly the boundary." }
)

$i = 0
$jobs = @()
foreach ($d in $dims) {
  $i++
  $out = "batch-{0:d2}-{1}.json" -f $i, $d.n
  $jobs += Start-Job -ScriptBlock {
    param($scratch, $dim, $tiers, $brief, $out)
    & (Join-Path $scratch "run_batch.ps1") -Dimension $dim -Tiers $tiers -Brief $brief -Out $out
  } -ArgumentList $scratch, $d.n, $d.t, $d.b, $out

  # Cap concurrency at 3 so the provider is not hammered.
  while (@(Get-Job -State Running).Count -ge 3) { Start-Sleep -Seconds 5 }
}

$jobs | Wait-Job | Out-Null
$jobs | ForEach-Object { Receive-Job $_ }
$jobs | Remove-Job
Write-Host "ALL BATCHES DONE"
