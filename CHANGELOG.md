# Changelog

## v0.5.0 — 2026-06-14 (first public release)

First public release of Gauntlet. Delivers the complete pipeline (design phases
0–10): typed contracts + config, the single-HTTP-boundary `OpenAIClient`, metadata
enrichment, deterministic + judge scoring, the privacy-aware scorecard, the pure
sequencer, the resumable runner, the three special evaluations (`depth`, `embed`,
`baseline`), and a seeded starter set of batteries. 106 tests; MIT licensed.

Pre-release housekeeping for going public: decoupled from any external knowledge
base, scrubbed a committed Tailscale IP from history, and genericized example
hostnames to `box-a` / `box-b`.

---

The full-spec build shipped as four sequential plans (design phases 0–10). Each
plan was a feature branch → PR → merge to `master`, executed inline with TDD. This
file preserves the per-plan delivery narrative (the PRs themselves were process
artifacts and are not retained).

## Plan 1 — Foundation (phases 0–2)
- **Scaffold** — Python package, Typer CLI (`gauntlet version` / `targets`), pytest with an opt-in `live` marker (deselected by default).
- **Privacy** — `.gitignore` hardened; the scorecard contract has **no `base_url`/IP field** by construction; box identity split into a private hostname vs a public hardware label.
- **Contracts & config** — `errors.py` (typed taxonomy), `config.py` (`Target`/`Box`/`ModelProfile`, `keep_list` glob, out-of-tree config resolution + safe loader), `battery.py` (`Battery`/`Case`, malformed files skipped + reported), `models.py` (scorecard contracts).
- **Client + enrichment** — `OpenAIClient` (sole HTTP boundary; chat + embeddings; typed errors); LM Studio (`/api/v1/models`) + Ollama (`/api/tags`) metadata adapters built against real captured payloads.
- **`gauntlet targets`** — lists each target's models with hardware label, size, quant (metadata only, no model loads).
- 24 tests.

## Plan 2 — Scoring & Scorecard (phases 3–4)
- **Deterministic scorers** (`gauntlet/scoring/`) — exact, regex, json-schema, conventional-commit, compilable-code; pure functions over output strings, fence/prose tolerant.
- **`score_case` dispatch** — wires a `Case` to the right scorer; returns a `NEEDS_JUDGE` sentinel for judge cases.
- **Judge path** (`scoring/judge.py`) — strict-JSON verdict parsing, **same-family guard** (a judge never grades its own family), **unscored-on-garbage** (never silently 0).
- **Scorecard** (`gauntlet/scorecard.py`) — `aggregate_cell` (quality excludes unscored, pass_rate over all cases), JSON emit with `--share` dropping the hostname, a Markdown report, and a pre-write **IP/URL leak guard**.
- **`gauntlet report`** — renders Markdown from a scorecard JSON; UTF-8 console so the unscored em-dash doesn't garble on Windows.
- 60 tests.

## Plan 3 — Runner (phases 5–7)
- **`sequencer.py` (pure)** — `build_cells` (work matrix: profile × applicable batteries, `context_floor` filter, `keep_list` exclusion), `estimate_footprint_gb` (weights + coarse KV; `None` when size unknown), `plan_run` (load-profile-outer groups — busy boxes defer, broad models exclusive, tight models co-reside up to the box VRAM budget, unknown footprint → exclusive).
- **`runner.py`** — append-only `cells.jsonl` checkpoint + `meta.json`; `run_cell` (deterministic + judge scoring, latency p50 / tokens-per-sec, errored cases recorded as unscored failures); `execute_plan` (per-target clients, `--resume` skip); `assemble_scorecard`.
- **`gauntlet run`** — `--config/--batteries/--prompts/--out/--model/--resume/--run-id/--share`. The run never aborts: unreachable/load-fail → errored cell, busy → deferred, ineligible judge → unscored.
- First plan that does real inference — gated behind injected clients + the `-m live` marker; the live suite never targets a gaming box.
- 83 tests.

## Plan 4 — Advanced (phases 8–10)
- **Context-depth** (`gauntlet/batteries/context_depth.py`) — needle-at-depth retrieval; pure core (`build_haystack`, `score_retrieval`, `effective_context`) + `run_context_depth`. `gauntlet depth` fills `context_depth[]`.
- **Embeddings** (`gauntlet/batteries/embed.py`) — retrieval recall@k; pure core (`cosine`, `rank_indices`, `recall_at_k`) + `run_embed_cell`. `gauntlet embed` emits an `embed` cell.
- **Frontier baseline** (`gauntlet/baseline.py`) — pure `compute_gaps` (local champion vs frontier, skips unscored); `gauntlet baseline` is **env-key gated** (`GAUNTLET_FRONTIER_API_KEY`) — never runs by default.
- **Scorecard merge** — `merge_into_scorecard` enriches a prior run's scorecard through the same leak guard / `--share`.
- **Seeded content** — `batteries/{commit-msg,extract-json,code-gen,summarize-short}.yaml` + `cases/**` + `cases/embed/corpus.yaml` — a starter set covering every deterministic scorer plus a judge case.
- **Docs** — README command reference, `batteries/README.md` authoring guide.
- 106 tests.

## Post-build housekeeping
- Decoupled the repo from any external knowledge base; `CLAUDE.md` is now a
  self-contained standalone-app guide. See `docs/decisions.md`.
- Privacy remediation: scrubbed a real Tailscale IP that had been committed,
  rewrote history to purge it, and recreated the remote from clean history. See
  `docs/decisions.md` (D-2026-06-13c).
