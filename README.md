# Gauntlet

**A gauntlet of trials for local models.** Gauntlet empirically answers — while
your GPUs are otherwise idle — *which local model is best at which job, at what
resource cost*, so model-selection decisions rest on measured data instead of
reputation or vibes.

> Consumed by [Baton](https://github.com/Ryfter/baton) (which uses the scores to
> pick local LLMs as tools), but **standalone by design** — all it asks of a target
> is an OpenAI-compatible endpoint. No dependency on any other repo.

**Version:** 0.6.0 — full-spec build (phases 0–10) plus post-release additions:
think-tag stripping for thinking models, parallel `orchestrate` command, SSE streaming
with TTFT measurement, token-usage and cost-savings metrics, 7 capability batteries
covering code-gen, code-debug, commit messages, JSON extraction, reasoning,
classification, and summarization, and `gauntlet add-case` for interactive battery
authoring (127 tests).

---

## About

Local-model ecosystems move fast and the "best" model is rarely the biggest one.
A 3B model that nails commit messages at 40 tokens/sec on a laptop can be a better
*tool* than a 70B model that does it marginally better but ties up a desktop GPU.
The only way to know is to measure — per job, per machine, at the context depth you
actually use.

Gauntlet is that measurement harness. You point it at the OpenAI-compatible
endpoints you already run (LM Studio, Ollama, llama.cpp, a remote box over a VPN —
anything that speaks `/v1/chat/completions`), describe the capabilities you care
about as **batteries**, and it produces a **scorecard**: for each `model @ context`
on each machine, a quality score and pass-rate per capability alongside latency,
throughput, and an error count. Run it overnight; read the scorecard in the morning.

**Why it exists:** to turn "I think this model is good at X" into "this model scores
0.88 on X at 38 tok/s on the RTX 2070, vs 0.91 for the frontier — close enough to
make X a permanent $0 local route." That last judgment — *when a small local model
has closed the gap with a paid frontier model* — is the high-value output, and it's
what Baton consumes to route work.

**What it is not:** not a router (Baton does that), not a leaderboard scraper, not a
trainer or a model downloader. It runs trials and reports numbers.

---

## How it works

The pipeline is five stages, and almost all of it is pure logic — only one module
(`client.py`) ever touches the network, which is why the bulk of the system is
unit-tested without a server or a fake.

```
config + batteries ──▶ sequencer ──▶ runner ──▶ scorecard ──▶ report
   (what to test)      (what order)   (run it)   (the data)   (the story)
```

1. **Load profiles are the unit under test.** A profile is a `model @ context`
   pair, because VRAM footprint is *weights + KV-cache(context)* and quality
   changes with context depth — so "gemma3 at 4k" and "gemma3 at 32k" are different
   subjects, not the same model twice.

2. **Batteries define the jobs.** Each `batteries/<capability>.yaml` is one
   capability's test suite (commit-msg, extract-json, code-gen, summarize, …). A
   battery's cases carry a prompt and a **scorer**. Deterministic scorers are
   preferred — `exact`, `regex`, `json-schema`, `conventional-commit`,
   `compilable-code` — and an **LLM judge** (non-reasoning, strict-JSON) is used
   only where quality is genuinely open-ended. A battery runs against a profile
   only if the profile's context clears the battery's `context_floor`.

3. **The sequencer plans the work (pure function).** It builds the work matrix
   (profiles × applicable batteries), then orders it: the **load profile is the
   outer loop** so each model loads once and runs all its batteries before
   unloading (avoiding reload thrash). It respects each box's VRAM budget and
   tight/broad usage class — `broad` models run exclusively, `tight` models may
   co-reside up to the budget — and it **defers** any box marked `busy`.

4. **The runner executes and checkpoints.** For each cell it fires the cases,
   scores them, and records quality, pass-rate, latency p50, tokens/sec, prompt and
   completion token counts, and errors — appending each completed cell to an
   append-only `cells.jsonl`. A crash
   loses at most the in-flight cell; `--resume <run-id>` skips what's done. **The
   run never aborts:** an unreachable target → its cells errored and counted; a
   busy box → deferred; an ineligible judge → the case is `unscored` (never
   silently scored 0). A scorecard must never overstate confidence.

5. **The scorecard is the contract.** `scorecards/<run-id>.json` is the canonical
   output; the Markdown report is the human/teaching view. Consumers depend only on
   the JSON shape.

**Special evaluations** don't fit the per-case loop and have their own commands:

- **`gauntlet depth`** — needle-at-depth retrieval: buries a fact at varying depths
  in filler sized to a target context length, sweeps lengths, and reduces the
  accuracy curve to an *effective* context (`effective_90pct`) — turning a model's
  *advertised* context into the context it can actually use.
- **`gauntlet embed`** — embeds a small corpus + queries, ranks by cosine
  similarity, and scores retrieval recall@k.
- **`gauntlet baseline`** — the opt-in frontier comparison: samples a capability's
  cases against a frontier API and reports the gap to your local champion. It
  **costs money, so it never runs by default** — it's gated behind
  `GAUNTLET_FRONTIER_API_KEY` and exits cleanly if the key is unset.

---

## Why these choices (reasoning)

- **One HTTP boundary.** `client.py` (`OpenAIClient`) is the *only* code that does
  network I/O. Everything else — scorers, sequencer, scorecard emit, resume
  bookkeeping — is a pure function over strings/dicts. That's what makes the system
  fast and deterministic to test: correctness bugs hide in the logic, and the logic
  needs no server, real or faked. We deliberately do **not** build an elaborate
  fake of the thing under test; the real models *are* the integration test (opt-in,
  `-m live`).

- **Deterministic scoring preferred; honest judging otherwise.** A regex or
  JSON-schema check is reproducible and free. When a judge is unavoidable, it's a
  non-reasoning strict-JSON grader that **never grades its own model family** (to
  avoid self-preference bias), and any case it can't score is marked `unscored`
  rather than guessed — so the scorecard never inflates confidence.

- **Quality-per-resource, not max quality.** The scorecard carries quality
  *alongside* latency, throughput, and footprint, so a consumer can apply bars
  ("good enough at this speed on this GPU") instead of chasing a single maximum.
  The Markdown report also renders a **cost-savings section**: what the same token
  budget would have cost at each frontier API tier (Anthropic, OpenAI), so "close
  enough to route locally" has a dollar figure attached.

- **Privacy by construction.** The engine is public; your network is not. The
  scorecard schema has **no field for a base_url or IP, ever**; box identity is
  dual (a private hostname for local use vs a public *hardware label* like
  "RTX 5090 desktop" for sharing); `--share` drops the hostname; and a pre-write
  leak guard refuses to emit any scorecard containing an IP or URL. Real endpoint
  rosters live *outside* the repo by default (see Privacy boundary below).

- **Idle-time and resumable.** Runs are meant to happen overnight via your OS
  scheduler; Gauntlet itself stays scheduler-agnostic. Because every cell
  checkpoints, an interrupted run resumes instead of restarting.

The full rationale is in [`docs/2026-06-11-gauntlet-design.md`](docs/2026-06-11-gauntlet-design.md)
(purpose, non-goals, the 8 decisions) and [`docs/2026-06-12-gauntlet-build-design.md`](docs/2026-06-12-gauntlet-build-design.md)
(architecture). Cross-cutting and post-build decisions are in
[`docs/decisions.md`](docs/decisions.md); the build history is in
[`CHANGELOG.md`](CHANGELOG.md).

---

## Quickstart

```bash
# 1. Install
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # Windows; use .venv/bin on *nix

# 2. Configure your endpoints (kept OUTSIDE the repo by default)
cp targets.example.yaml targets.yaml                 # then edit; targets.yaml is gitignored

# 3. List what each target exposes (metadata only — no model loads, VRAM-safe)
.venv/Scripts/gauntlet targets

# 4. Run the batteries and write a scorecard
.venv/Scripts/gauntlet run --out scorecards/$(date +%F).json

# 5. Read it
.venv/Scripts/gauntlet report scorecards/$(date +%F).json
```

### Configuration

A `targets.yaml` describes your endpoints (`targets`), your machines (`boxes`), the
load profiles to test (`models`), and models to skip (`keep_list`). The committed
[`targets.example.yaml`](targets.example.yaml) is the template; your real roster is
gitignored. Secrets (frontier API keys, per-endpoint auth) are **environment
variables only** — never in YAML.

---

## Commands

| command | what it does |
|---|---|
| `gauntlet targets` | list configured targets + models (metadata only, no model loads) |
| `gauntlet run` | sequence the work matrix and run batteries against live targets; resumable (`--resume <run-id>`) |
| `gauntlet orchestrate` | run batteries across multiple targets in parallel; prints a compact summary table |
| `gauntlet depth` | measure effective context via needle-at-depth retrieval (special battery) |
| `gauntlet embed` | evaluate an embedding model by retrieval recall@k |
| `gauntlet baseline` | opt-in frontier comparison (gated by `GAUNTLET_FRONTIER_API_KEY`) |
| `gauntlet add-case` | interactively add a new test case to an existing battery |
| `gauntlet report` | render a scorecard JSON to Markdown (`--share` to sanitize) |

See [batteries/README.md](batteries/README.md) for how to author a battery.

### Overnight run (example)

```bash
gauntlet run      --config <private targets.yaml> --out scorecards/2026-06-13.json
gauntlet depth    --target box-b --model gemma3:1b --max-context 8192 --into scorecards/2026-06-13.json
gauntlet embed    --target box-b --model nomic-embed --into scorecards/2026-06-13.json
gauntlet report   scorecards/2026-06-13.json --share
```

**Resource safety:** real inference must target a headless box. Do not run
inference against a box you are gaming on — mark it `busy: true` in config to defer
its cells. The frontier baseline never runs without `GAUNTLET_FRONTIER_API_KEY` set.

---

## The scorecard contract

```jsonc
{ "run": { "id": "...", "date": "...", "gauntlet_version": "0.6.0" },
  "cells": [ { "model": "gemma3:1b", "box": "RTX 2070 Super laptop", "context": 4096,
               "capability": "commit-msg", "quality": 0.88, "pass_rate": 0.86,
               "latency_p50_s": 2.1, "tokens_per_s": 38, "ttft_p50_s": null,
               "prompt_tokens": 1820, "completion_tokens": 312,
               "judge": null, "cases": 14, "errors": 0 } ],
  "context_depth": [ { "model": "...", "advertised": 32768, "effective_90pct": 16384 } ],
  "baseline_gaps": [ { "capability": "commit-msg", "local_champion": "gemma3:1b",
                       "frontier": "claude", "gap": 0.03 } ] }
```

A cell carries a `box` (hardware label) and, in private mode only, a `target`
(hostname). There is **no** base_url/IP field by design. `--share` drops the
hostname, keeping `hardware label + model + context + capability + metrics`.

---

## Privacy boundary

The **engine** (code, batteries, examples) is the shareable part. **Targets and
results are private to the owner's boxes** — which models live on which machine,
endpoints, and scores never ship with the engine. Concretely:

- `targets.yaml` (your real roster) and `scorecards/` are gitignored.
- Config resolution defaults to *outside* the repo: `--config` → `$GAUNTLET_CONFIG`
  → OS user-config dir (`%APPDATA%\gauntlet\` / `~/.config/gauntlet/`) →
  repo-local `./targets.yaml` (gitignored fallback only).
- The scorecard schema has no base_url/IP field; `--share` drops the hostname; a
  pre-write leak guard rejects any IP/URL in emitted output.
- In docs and tests, use placeholders (`<box-b-host>`) and TEST-NET addresses
  (`203.0.113.0/24`) — never a real host.

---

## Project layout

```
gauntlet/      the engine (client, config, battery, sequencer, runner, scoring, scorecard, batteries/)
batteries/     <capability>.yaml battery definitions  (+ authoring guide)
cases/         per-battery prompt/schema/fixture files
docs/          design specs, decisions, per-plan implementation plans
tests/         pytest: pure-logic unit suite + opt-in live integration (-m live)
scorecards/    run outputs (JSON + MD) — gitignored, box-private
targets.example.yaml   endpoint roster template (real roster = targets.yaml, gitignored)
```

## Developing

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest            # default suite (no network), 127 tests
.venv/Scripts/gauntlet targets            # list models per target (metadata only)
```

Live tests are opt-in and metadata-only or headless-box-only:
`GAUNTLET_LIVE_OLLAMA=http://<box-b-host>:11434 .venv/Scripts/python -m pytest -m live`.
Never point inference tests at a box someone is gaming on.

## License

See [LICENSE](LICENSE).
