You are authoring test cases for a benchmark that measures how well LOCAL open-source
LLMs (roughly 1B-30B parameters) can write Python. Output quality matters enormously:
each case is machine-validated and silently discarded if it does not meet the contract.

## Output format — READ CAREFULLY

Output ONLY a raw JSON array. No prose before or after. No markdown code fences.
Start your reply with `[` and end it with `]`.

Each element:

{
  "id": "kebab-case-id",
  "dimension": "<the dimension given below>",
  "tier": "T1" | "T2" | "T3" | "T4",
  "prompt": "the task description shown to the model under test",
  "hidden_tests": "python source defining check(ns) -> list[bool]",
  "reference": "python source: a CORRECT solution",
  "wrong": "python source: a SUBTLY WRONG solution"
}

## The hidden_tests contract (most important part)

`check(ns)` receives `ns`, the namespace dict produced by exec'ing the candidate's
code. It returns a list of booleans, one per assertion. Score = fraction True.

EVERY case must use exactly this shape:

def check(ns):
    f = ns.get("EXACT_FUNCTION_NAME")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(...) == ...),
        t(lambda: f(...) == ...),
        # ... 10 total
    ]

Rules, all mandatory:
- Wrap EVERY assertion in `t(lambda: ...)`. Never let an exception escape `check`:
  an escaping exception makes the case unscorable rather than scored, which is a
  benchmark bug. The `[False] * 10` guard and the per-assert `t()` are what make
  a missing or broken candidate score 0.0 instead of blowing up.
- Return EXACTLY 10 assertions, and make the count in `[False] * 10` match.
- Order them easy -> hard. Early ones check the happy path; later ones check the
  edge cases. This is what produces useful partial credit and separates a
  nearly-right model from a hopeless one.
- Include real edge cases: empty input, single element, zero, negatives,
  duplicates, unicode, boundary/off-by-one, large input, None where meaningful.
- Compare against literal expected values you have computed yourself. Do NOT
  reimplement the solution inside the test and compare two computations.

## The `wrong` solution contract

It must be SUBTLY wrong: it passes the early/easy assertions and fails several
later ones. A solution that fails everything proves nothing. Typical good defects:
an off-by-one, mishandling the empty case, ignoring duplicates, wrong tie-break,
losing sign on negatives. It MUST be syntactically valid and must run.

## The `prompt` contract

- State the EXACT function name and signature. The hidden tests look it up by that
  exact name, so any drift means an automatic zero.
- Fully specify behaviour on the edge cases you test. Unambiguous, but not
  googleable. If a competent developer could reasonably return something else,
  the spec is underspecified — tighten it.
- Never reveal the assertions or the expected outputs.
- Python standard library only. No third-party packages. No file, network, or
  clock access (nothing non-deterministic).

## Anti-contamination — hard rule

These are memorised by even 1B models and are automatically rejected: fizzbuzz,
fibonacci, two-sum, palindrome, binary search, anagram, reverse-a-string, bubble
sort, factorial, hello world, and any LeetCode-famous problem.

Invent ORIGINAL problems, or take a familiar shape and add a precise unusual twist
that a memorised answer gets WRONG. Draw on varied, concrete domains: log parsing,
seat allocation, inventory reconciliation, version ranges, schedule merging, text
wrapping, tariff bands, shipping manifests, sensor debouncing, spreadsheet ranges.

## Difficulty tiers

- T1 baseline: a competent 3B model should pass. Single concept, few edge cases.
- T2 moderate: two concepts combined, or one genuinely fiddly edge case.
- T3 hard: multi-step logic, several interacting edge cases, easy to get 80% right
  and 100% wrong. This tier does most of the discriminating — make it count.
- T4 stretch: subtle invariants, tricky state, or precision/ordering traps. Most
  local models should fail this today. That is intentional headroom.
