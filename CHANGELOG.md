# Changelog

## v0.6.0 — 2026-06-21

### Post-v0.5.0 additions — session 3

### `gauntlet add-case` CLI helper
- **`gauntlet add-case <capability>`** — interactive command to add a new test case to an
  existing battery. Prompts for case ID (validates uniqueness), scoring method
  (`exact`, `regex`, `json-schema`, `conventional-commit`, `compilable-code`, `judge`),
  scorer-specific params (`expect`, `pattern`, `rubric`, `schema_file`), and prompt text
  (or `--from-file` to read from an existing file). Writes the prompt to
  `cases/<capability>/<id>.txt` and appends the case block to the battery YAML while
  preserving all existing formatting.
- 10 new tests covering every scoring method, duplicate-ID retry loop, `--from-file` flag,
  empty `cases: []` battery handling, and post-write round-trip loading.
- Test suite: 117 → 127 tests.

---

### Post-v0.5.0 additions — session 2

### TTFT streaming
- **SSE streaming** — `OpenAIClient.chat()` switched from a blocking POST to an SSE
  stream (`stream=True` + `stream_options.include_usage=True`). Time-to-first-token
  is now recorded when the first content chunk arrives; text is assembled from deltas;
  token counts come from the final `usage` chunk. `ttft_p50_s` is now populated on
  every run instead of always being `null`.
- **Shared test helper** — `tests/helpers.py` provides an `sse()` builder for
  MockTransport handlers; all chat-completion mock handlers updated to SSE format.

### Battery matrix expansion
- **`code-debug` battery (4 cases):** deterministic bug-fix verification — missing
  `return` statement, wrong arithmetic operator, off-by-one index error, inverted
  conditional. First three scored with `regex` to verify the specific fix; fourth
  with `compilable-code`.
- **`reasoning` battery (4 cases):** exact numeric/word answers — arithmetic word
  problem, percentage discount, doubling number sequence, 3-person logic deduction.
- **`classify` battery (5 cases):** exact single-word label output — sentiment
  (positive/negative), topic (technology), urgency triage (high), intent routing
  (billing). All scored with `exact`.
- Battery count: 4 → 7. Test suite stays at 117 (new batteries covered by
  `test_seeded_batteries_load_clean` and `test_seeded_case_prompt_files_exist`).

---

## Post-v0.5.0 additions — 2026-06-21

### Thinking-model correctness
- **Think-tag stripping** — `runner.py` strips `<think>…</think>` blocks (compiled
  regex, case-insensitive, dotall) from model output before ALL scoring paths.
  Thinking models (qwen3, openthinker) were producing compilation failures,
  commit-format mismatches, and JSON parse errors because chain-of-thought was
  included in the scored text. Same stripping applied to judge outputs before JSON
  verdict parse (the judge path was caught and fixed first in an earlier commit).

### Parallel orchestration
- **`gauntlet orchestrate`** — new command that runs the battery matrix across
  multiple targets in parallel using `concurrent.futures.ThreadPoolExecutor`. Each
  target runs in its own thread; a compact summary table is printed on completion
  alongside the per-target scorecard paths.

### Judge pool quality
- **`judge: false` flag** — `ModelProfile` now accepts `judge: false` to exclude a
  model from the judge pool. Models with known verdict-format problems can be
  blacklisted without removing them from the test roster. `tavernari/git-commit-message`
  is the first model so marked.

### Token metrics and cost-savings reporting
- **`pricing.py`** — frontier pricing table (Anthropic: Fable 5, Opus 4.8, Sonnet 4.6,
  Haiku 4.5; OpenAI: gpt-5.5, gpt-5.4, gpt-5.4-mini, gpt-5.4-nano, gpt-5.3-codex).
  `savings_summary()` computes what the same token budget would have cost at each
  frontier tier and renders a Markdown cost-savings section appended to every scorecard
  report. Default comparison baselines: Claude Sonnet 4.6 + Claude Haiku 4.5.
- **Token accumulation** — `run_cell()` accumulates `prompt_tokens` and
  `completion_tokens` separately from the API `usage` field. `Cell` carries both plus
  `ttft_p50_s` (median time-to-first-token, wired through but populated only when
  streaming). `tokens_per_s` corrected to use completion tokens only (previously
  used total tokens, overstating generation throughput).

### Battery expansion
- 19 new test cases across all four starter batteries:
  - `commit-msg`: feat with class body, error-handling refactor, breaking API change, large-scale architectural refactor
  - `code-gen`: binary search, LRU cache, palindrome check, CSV parsing
  - `extract-json`: contact card, event announcement, product list (with JSON schema)
  - `summarize-short`: technical article, long-form article, meeting notes with action items
- Test suite: 106 → 115 tests.

---

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
