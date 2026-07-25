# Batteries — authoring guide

A **battery** is one capability's test suite: a `batteries/<capability>.yaml` file
plus its prompt/schema files under `cases/<capability>/`. `gauntlet run` loads
every `batteries/*.yaml`; a battery runs against a load profile only when the
profile's context >= the battery's `context_floor`.

## Schema

```yaml
capability: extract-json        # unique capability name (the scorecard groups by this)
context_floor: 4096             # profiles below this context skip this battery
cases:
  - id: invoice-01              # unique within the battery
    prompt_file: cases/extract-json/invoice-01.txt        # user prompt (relative to --prompts)
    scoring: json-schema        # see scorers below
    schema_file: cases/extract-json/invoice-01.schema.json   # json-schema only
  - id: messy-03
    prompt_file: cases/extract-json/messy-03.txt
    scoring: judge              # LLM-graded
    rubric: "Score 0-1: completeness and correctness, no invented fields."
weights: { quality: 1.0 }
```

## Scorers (deterministic preferred)

| `scoring` | needs | passes when |
|---|---|---|
| `exact` | `expect` | output equals `expect` (trimmed, fences stripped) |
| `regex` | `pattern` | `pattern` found in output |
| `json-schema` | `schema_file` | output parses and validates against the schema |
| `conventional-commit` | — | output is a valid Conventional Commits subject |
| `compilable-code` | — | output is a syntactically compilable code block |
| `code-exec` | `tests_file` | output, executed in a sandboxed subprocess, passes its hidden asserts |
| `judge` | `rubric` | a different-family judge model scores it >= 0.5 |

Prefer deterministic scorers; reserve `judge` for open-ended quality. A judge never
grades its own model family, and an unjudgeable case is recorded `unscored` (never
silently 0 — a scorecard must not overstate confidence).

### `code-exec`: execution-based code-gen scoring

`compilable-code` only checks that output parses — garbage that compiles scores 1.0.
`code-exec` checks **correctness**: the model's code is executed in an isolated
subprocess (fresh process, own process group, wall-clock timeout, scratch tempdir
cwd, minimal env — see `gauntlet/scoring/execute.py`) against a hidden,
maintainer-authored assert suite. Score is the fraction of hidden asserts passed;
`passed` requires all of them.

```yaml
- id: run-length-encode
  prompt_file: cases/code-gen/run-length-encode.txt
  scoring: code-exec
  tests_file: cases/code-gen/tests/run-length-encode.py   # optional: timeout_s (default 5.0)
```

The `tests_file` is a plain Python file defining `check(ns) -> list[bool]`, where
`ns` is the exec'd namespace of the candidate's code (so `ns.get("my_func")` looks
up whatever the prompt asked the model to define). Write it defensively: look up
symbols with `.get(...)` and wrap each per-case call in `try/except`, so a missing
function or wrong signature fails that assertion (score 0) instead of crashing the
whole suite (which would read as `unscored`, not a real 0). See any file under
`cases/code-gen/tests/` for the pattern — including a stateful class case
(`inventory-tracker.py`) and a multi-function case (`prime-pair.py`).

A bug in the hidden test file itself (not the candidate's fault) is recorded as
`unscored`, per the scoring-honesty invariant.

#### Failure modes

`code-exec` records *why* a case failed, not just that it did:

| `failure_mode` | meaning |
|---|---|
| `none` | scored 1.0 |
| `no_code_emitted` | the model returned prose, a refusal, or nothing |
| `syntax_error` | the source does not parse |
| `runtime_exception` | it raised while being exec'd |
| `wrong_answer` | it ran clean but some hidden asserts failed |
| `timeout` | exceeded the sandbox wall clock |
| `harness_error` | **our** bug — recorded `unscored`, never 0 |

This split matters more than the score. A model that emits no code at all has a
different problem from one that writes plausible code with an off-by-one, and
Baton needs to tell them apart: scaffolding and atomisation help a
working-memory failure and do nothing for a capability gap (D-2026-06-30c).

## The code-gen difficulty ladder

The fleet is local models roughly 1B–30B. A battery where everything scores 1.0
is non-discriminative — that was the original `compilable-code` problem — but so
is one where everything scores 0.0. Making cases *harder* is only useful up to
the point where the scores still spread.

Every case carries a `tier`:

| tier | target | share |
|---|---|---|
| `T1` | baseline sanity; a competent 3B model should pass. Keeps the floor visible and catches broken plumbing. | ~15% |
| `T2` | moderate: two concepts combined, or one fiddly edge case. | ~35% |
| `T3` | hard: multi-step logic, interacting edge cases. **Does most of the discriminating.** | ~35% |
| `T4` | stretch: subtle invariants, ordering/precision traps. Most locals fail today — deliberate headroom so the battery does not saturate as models improve. | ~15% |

The scorecard reports per-tier as well as overall, because the *shape* of a
model's tier profile says more than its mean: passing T1–T2 and collapsing at T3
is a different animal from scoring evenly across all four.

## Case dimensions

Cases also carry a `dimension` — the capability axis being probed. The set is
adapted from current industry code benchmarks, because breadth is what keeps a
benchmark honest once any single axis saturates:

| dimension | probes | after |
|---|---|---|
| `adversarial-correctness` | edge cases behind an ordinary-looking spec | EvalPlus / HumanEval+ |
| `stdlib-api-use` | multi-clause specs over `re`, `itertools`, `collections`, `heapq`, … | BigCodeBench |
| `class-level-stateful` | interdependent methods, invariants across an operation sequence | ClassEval |
| `multi-function` | writing a helper *and* a caller that uses it correctly | — |
| `complexity-constrained` | correctness plus a stated complexity bound | EffiBench / BigO(Bench) |
| `bug-fix` | patching broken code without breaking untouched behaviour | SWE-bench, at function scale |
| `surface-constraints` | instruction-following isolated from algorithmic skill | DS-1000 |
| `robustness-contracts` | raising the *right* exception on invalid input | TREAT |
| `behavior-preserving-refactor` | reading existing code correctly | — |
| `test-authoring` | writing tests that actually catch a planted bug | — |
| `data-text-munging` | the everyday parsing work a harness would offload | — |

### Anti-contamination

HumanEval is saturated (96–98% at the frontier) largely because it leaked into
training data. The same trap applies locally: `fizzbuzz`, `palindrome` and
`binary-search` scored ~1.0 for every model here, measuring memorisation rather
than capability. Those cases have been retired.

New cases must not be memorised classics — no fizzbuzz, fibonacci, two-sum,
palindrome, binary search, anagram, reverse-a-string, bubble sort, factorial.
Either invent an original problem or take a familiar shape and add a precise
twist that a memorised answer gets **wrong**. The ingest validator rejects a
case whose id or prompt mentions a banned classic.

### Every case must prove itself

A case is only trustworthy if its asserts are both *satisfiable* and *sharp*.
Each one therefore ships with two maintainer-authored solutions under
`cases/code-gen/tests/reference/`:

- `<id>.ref.py` — correct; must score exactly **1.0**
- `<id>.wrong.py` — subtly wrong; must score **< 1.0**

`tests/test_case_validation.py` enforces both for every case in
`cases/code-gen/registry.json`, and also asserts no hidden-test line leaks into
the prompt. An unsatisfiable case would score every model 0.0 and a toothless
one would score every model 1.0 — both look like data and are actually noise, so
a broken case fails CI rather than quietly skewing a scorecard.

The `wrong` solution should fail *some* asserts, not all: partial credit is what
separates a nearly-right model from a hopeless one, so order assertions
easy → hard.

### Surface-form constraints

`gauntlet/scoring/constraints.py` checks declared constraints against the
candidate's AST (`no-imports`, `single-expression`, `must-use-generator`,
`no-sorted`, `no-loops`, `no-recursion`, `no-global-state`, …). Violations are
reported *separately* from correctness so "solved it but ignored the
instruction" is never conflated with "could not solve it".

## Special batteries (own commands, not `gauntlet run`)

These don't fit the per-case scoring flow, so each has a dedicated command that
fills its own scorecard section:

- **context-depth:** `gauntlet depth --target T --model M --max-context N` —
  needle-at-depth retrieval across context lengths, fills `context_depth[]`
  (`advertised` vs `effective_90pct`).
- **embed:** `gauntlet embed --target T --model M --corpus cases/embed/corpus.yaml` —
  retrieval recall@k over a small corpus, emits an `embed` cell. The corpus YAML
  has keys `corpus[]`, `queries[]`, and `relevant[]` (the index of each query's
  correct doc).

## Seeded starter set

`commit-msg`, `extract-json`, `code-gen`, `summarize-short`, and the `embed`
corpus ship as worked examples covering every deterministic scorer plus a judge
case. Add the rest of the taxonomy (summarize-long, synthesize, write-personal /
-scientific / -formal, code-transform, ocr) by following the same pattern.
