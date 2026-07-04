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
