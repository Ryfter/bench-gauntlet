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
| `judge` | `rubric` | a different-family judge model scores it >= 0.5 |

Prefer deterministic scorers; reserve `judge` for open-ended quality. A judge never
grades its own model family, and an unjudgeable case is recorded `unscored` (never
silently 0 — a scorecard must not overstate confidence).

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
