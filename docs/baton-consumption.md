# Baton scorecard consumption

How Baton (and Ox Alpha orchestrators doing local seating) should read Gauntlet
outputs without re-implementing join logic or leaking private topology.

## Where data lives

- **Run directory:** `scorecards/<run-id>/` — append-only, gitignored, box-private.
- **Required:** `cells.jsonl` (one aggregated row per model × capability × context).
- **Optional:** `cases.jsonl` (per-case rows; needed for dimension/tier/failure-mode joins).
- **Metadata:** `meta.json` holds `id`, `date`, `gauntlet_version` only.
- **Canonical JSON:** legacy `scorecards/<run-id>.json` may exist; prefer the directory layout for resume and analysis tools.

## Cell schema (what Baton routes on)

Each `cells.jsonl` row:

| Field | Use |
|---|---|
| `model` | Model ID at the endpoint |
| `box` | **Hardware label** only (e.g. `RTX 5090 desktop`) — safe to share |
| `target` | Private hostname/id — **strip before Ox or external prompts** |
| `context` | Load profile context depth |
| `capability` | Job type (commit-msg, code-gen, …) |
| `quality` | Mean score; **null = unscored, never treat as 0** |
| `pass_rate` | Fraction of cases passing threshold |
| `tokens_per_s`, `latency_p50_s`, `ttft_p50_s` | Cost / speed bars |
| `quality_by_dimension` | Per-dimension means (code-gen axes) |
| `quality_by_tier` | T1–T4 ladder (capability shape) |
| `failure_modes` | Aggregated counts — scaffolding vs capability-gap signal |
| `integrity` | Non-null → cell unreliable; exclude from routing |

There is **no** `base_url` or IP field by design.

## Choosing a run

1. Prefer the **newest finished** directory with `cells.jsonl` and no in-flight errors.
2. Richer runs have more cells (models × capabilities) and optional `cases.jsonl`.
3. Use `scripts/analyze_fleet.py <run-dir>` for a routing Markdown report (null-safe).

## Seating rules for Ox / local

- Match **capability** first, then filter by `box` hardware label for the seat (5090 vs 2070).
- Apply quality floor + `tokens_per_s` floor; prefer models with graceful tier profiles over erratic cliffs.
- For code-gen, read `failure_modes`: `wrong_answer`-dominant → scaffold candidate; `no_code_emitted` / `syntax_error` → do not scaffold.
- Never paste `target` hostnames into cloud prompts; use `box` + `model` + metrics only.
- **5090 constraint:** only one inference stack unbusy at a time (`firefly-lms` XOR `firefly-oll`).

## Share / export

- `gauntlet report <scorecard.json> --share` drops hostnames.
- Pre-write leak guard rejects IPs/URLs in emitted output.
- Commit **engine + docs** only; never commit `scorecards/` or `targets.yaml`.

## Related

- `README.md` — scorecard contract and privacy boundary
- `~/.baton/overnight/swarm/out/bg-fleet-analysis.md` — latest fleet routing brief
- Baton repo consumes the same cell shape for tool selection
