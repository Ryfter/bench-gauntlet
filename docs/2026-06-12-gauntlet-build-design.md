# Gauntlet — build design (full-spec implementation)

**Status:** approved 2026-06-12, build starting. Supersedes the deferred spec
[`2026-06-11-gauntlet-design.md`](2026-06-11-gauntlet-design.md) (still the
canonical statement of *purpose, non-goals, and the 8 decisions* — read it for
the "why"; this doc is the "how we build it").
**Scope decision:** full spec in one cycle (Kevin, 2026-06-12), decomposed into
ordered phases so it builds as a walking skeleton that grows.
**Language:** Python 3.12+ — httpx, pydantic, PyYAML, jsonschema, Typer, pytest.

## What this doc adds over the 2026-06-11 spec

The original spec fixed purpose, the targets/battery/scorecard shapes, and 8
decisions. This build design fixes the **module decomposition, the public/private
split, the runtime behavior, the phase order, and the test philosophy** needed to
actually implement it. Where the two differ, this doc wins for implementation.

## Testing philosophy (decided 2026-06-12)

Gauntlet's purpose is empirical data from **real** local models, so we do **not**
build an elaborate fake of the thing under test. Instead we split by *what is
being verified*:

- **Pure logic** (scorers, sequencer, scorecard emit, config/battery validation,
  resume bookkeeping) — pure functions over strings/dicts. Fast deterministic
  `pytest` against **static fixtures** (a sample model output → expected score).
  No model, real or fake. This is where correctness bugs hide; it gets the bulk
  of the TDD.
- **Harness end-to-end** — validated by pointing at a **real endpoint**; that run
  also produces the first genuine scorecard. The real models *are* the
  integration test.
- **Nasty error paths** — unreachable target and malformed battery are trivial to
  provoke for real (dead port, bad YAML) and are tested directly. True OOM is
  hard to force on demand; handled defensively, exercised in the wild.

Live tests are opt-in (`pytest -m live`) and **never run firefly inference**
(see "don't run while gaming" below); they target wraith2 with a tiny model.

## A. Module decomposition & package layout

Every unit is small, single-purpose, and independently testable behind a clean
interface. `client.py` is the *only* thing that does HTTP, so everything else is
pure-logic-testable without a server.

```
gauntlet/
  __init__.py
  cli.py            # Typer entry: `gauntlet run | baseline | targets | report`
  config.py         # load+validate private config → Targets/Boxes/Models/keep_list
  battery.py        # load+validate batteries/*.yaml + cases/* → Battery/Case
  models.py         # pydantic contracts: Cell, Scorecard, ContextDepth, BaselineGap
  client.py         # OpenAIClient: chat/completions + embeddings over httpx (ONLY transport)
  enrich/
    __init__.py     # Enricher protocol → {context, quant, size, caps, loaded}
    lmstudio.py     # /api/v1/models adapter (real shape)
    ollama.py       # /api/tags adapter (real shape)
  scoring/
    __init__.py     # Scorer protocol: (case, output) -> CaseResult
    exact.py        # exact / regex
    schema.py       # json-schema validate, conventional-commit, compilable-code
    judge.py        # LLM judge: non-reasoning strict-JSON, records judge identity
  batteries/
    context_depth.py # needle-at-depth → effective-context curve (special runner)
  runner.py         # sequences cells, resume/checkpoint, busy/VRAM-aware ordering
  sequencer.py      # box VRAM budget + tight/broad class ordering + busy guard (pure)
  scorecard.py      # assemble + write JSON (canonical) and MD (report)
  errors.py         # typed outcomes: Unreachable, OOM, JudgeUnavailable, BadBattery, BoxBusy
tests/              # pytest: pure-logic unit + opt-in live integration (-m live)
```

**Boundary rules:** scorers and the sequencer are pure functions; enrichers and
judges are protocols with concrete adapters (new servers/judges plug in without
touching the runner); `runner.py` orchestrates but delegates every decision — it
is the integration seam validated against real boxes.

## A.5 Public / private split

Rule: **personal network info should be physically incapable of living in the
public tree, not merely gitignored.** Three tiers:

1. **PUBLIC** (committed, OSS-ready): all `gauntlet/` code, `batteries/*.yaml`,
   `cases/*`, `docs/`, `tests/`, README, and `*.example.yaml` templates. Zero
   personal data by construction.
2. **PRIVATE config** (never committed): real endpoint roster — base_urls,
   Tailscale IPs, box ids, VRAM budgets, usage classes, `keep_list`. Loaded by a
   resolution order that **defaults to outside the repo**:
   1. `--config <path>` →
   2. `$GAUNTLET_CONFIG` →
   3. OS user-config dir — `%APPDATA%\gauntlet\targets.yaml` (Windows) /
      `~/.config/gauntlet/targets.yaml` →
   4. repo-local `./targets.yaml` (gitignored fallback, convenience only).
3. **SECRETS** (never on disk in the repo): API keys (frontier baseline's
   `ANTHROPIC_API_KEY`), any per-endpoint auth — **environment variables only**
   (`GAUNTLET_<TARGET>_API_KEY`), optionally from a gitignored `.env` for dev.
   No secret in any YAML.

**Box identity is dual:**
- a **private id** (`firefly`, `wraith2`) — private config + private scorecards only;
- a **public hardware descriptor** (`"RTX 5090 desktop"`, `"RTX 2070 Super laptop"`,
  incoming `"RTX 4090 desktop"`) — the *only* box label in a shared scorecard.
  Hardware class is the useful public quality-per-resource axis; the hostname is not.

**Scorecard privacy:** the schema has **no field for a base_url or IP, ever**. A
cell names `box` (hardware label) and, in private mode only, `target` (hostname
label). `--share` drops the hostname *and* target name, keeping
`hardware label + model id + context + capability + metrics`. A pre-write
assertion scans serialized output for IP/URL patterns and refuses to write if any
appear. Scorecards stay gitignored by default; sharing is explicit and sanitized.

## B. Data contracts

**Private config** (`targets.yaml`, out-of-tree):
```yaml
targets:
  - { name: firefly-lmstudio, base_url: http://localhost:1234, api: openai, enrich: lmstudio, box: firefly }
  - { name: wraith2-ollama,  base_url: http://203.0.113.10:11434, api: openai, enrich: ollama,  box: wraith2 }
boxes:                       # the infra inventory the spec's `box:` joins to
  - { id: firefly, hardware: "RTX 5090 desktop",      vram_gb: 32, usage_class: broad, busy: false }
  - { id: wraith2, hardware: "RTX 2070 Super laptop", vram_gb: 8,  usage_class: tight, busy: false }
models:                      # load profiles: model @ context
  - { target: firefly-lmstudio, id: 'google/gemma-4-31b', context: 8192 }
keep_list: [ '*heretic*', '*swahili*' ]
```
- `busy` is the per-box "don't run while gaming" guard.
- `usage_class` (tight/broad) + `vram_gb` drive the sequencer.

**Battery** (`batteries/<cap>.yaml`, public) — per the 2026-06-11 spec G.2:
`capability`, `context_floor`, `cases[]` (each `id`, `prompt_file`, `scoring`,
plus `schema_file`/`rubric` as the method needs), `weights`.

**Scorecard** (the contract) — one in-memory model, two emission modes:

| field | private JSON | shared JSON (`--share`) |
|---|---|---|
| `model`, `context`, `capability` | ✓ | ✓ |
| `quality`, `pass_rate`, `latency_p50_s`, `tokens_per_s`, `cases`, `errors` | ✓ | ✓ |
| `box` (hardware label) | ✓ | ✓ |
| `target` (hostname label) | ✓ | **dropped** |
| `base_url` / any IP | no such field | no such field |
| `judge` identity | ✓ | ✓ |

Plus `context_depth[]` (`model`, `advertised`, `effective_90pct`) and
`baseline_gaps[]` (`capability`, `local_champion`, `frontier`, `gap`) per spec G.4.

## C. Runtime behavior

**Work matrix.** Cells = load profile (`model @ context`) × applicable batteries,
a battery applying only if the profile's context ≥ its `context_floor`.
`keep_list` models excluded unless named explicitly on the CLI.

**Sequencing** (`sequencer.py`, pure: cells + box inventory → ordered plan):
- **Load profile is the outer loop, batteries the inner loop** — each
  `model @ context` loads once and runs all its batteries before unloading (main
  efficiency lever; avoids reload thrash).
- **Busy guard:** a cell whose box is `busy: true` is *deferred and counted*,
  never forced.
- **VRAM classes:** within a box, `broad` models run exclusively (unload before
  the next); `tight` tools may co-reside up to `vram_gb`, footprint estimated as
  weights (enrichment `size_bytes`) + KV(context). Unknown footprint → treated as
  exclusive (safe default).

**Execution & resume.** A run owns `scorecards/<run-id>/` with an append-only
`cells.jsonl` (one line per completed cell) + `meta.json`. Models auto-load on
first request (LM Studio/Ollama both do). A cell fires its cases, scores them,
records metrics, appends immediately. `--resume <run-id>` reads `cells.jsonl`,
skips completed cells, continues — a crash loses at most the in-flight cell. The
final `<date>-<run-id>.json` + `.md` are assembled from `cells.jsonl`.

**Per-cell metrics:** mean quality / pass-rate, latency p50, tokens/sec (usage +
timing), configured context, observed footprint (enrichment `loaded_instances`/
size where available), error count.

**Scoring dispatch** — `Scorer` protocol `score(case, output) -> CaseResult{score,
passed, method, detail}`, by `case.scoring`:
- `exact` / `regex` → `exact.py`
- `json-schema`, `conventional-commit`, `compilable-code` → `schema.py`
- `judge` → `judge.py`: a **non-reasoning strict-JSON** judge; records *which*
  judge scored; the runner never lets a judge grade its **own model family**
  (picks a different-family judge, else marks `unscored`).

Cell `quality` = battery-weighted aggregate of case scores; `pass_rate` =
fraction passed.

**Error taxonomy** (`errors.py`) — typed outcomes, the run *never aborts*:

| condition | outcome |
|---|---|
| target unreachable | its cells skipped + counted; run continues |
| model load fail / OOM | cell `errored` with reason; continue |
| judge unavailable | judge-scored cases → `unscored` (never silently heuristic) |
| malformed battery file | named loudly at startup; that battery dropped, rest proceed |
| box busy | cells deferred + counted (a skip, not an error) |

## "Don't run while gaming" (firefly)

`firefly` (localhost) is Kevin's gaming PC. Metadata-only probes
(`/v1/models`, `/api/v1/models`, `/api/tags`) never load a model and are safe
anytime. **No inference is run against firefly while gaming** — dev-loop inference
targets wraith2 (headless), and firefly is exercised only when Kevin clears it.
This is enforced in the design by the per-box `busy` guard, and in automated
tests by never including firefly in the live suite.

## D. Phase plan

| # | Phase | Lands | Verified by |
|---|---|---|---|
| 0 | Scaffold | `pyproject.toml` (httpx, pydantic, pyyaml, jsonschema, typer, pytest), package skeleton, out-of-tree config resolution, `.gitignore` hardening (`.env`, user-config) | imports + `gauntlet --help` |
| 1 | Contracts & config | `config.py`, `battery.py`, `models.py`; load+validate with friendly errors | pure-logic tests |
| 2 | Client + enrichment | `OpenAIClient`; `enrich/lmstudio`, `enrich/ollama` (real shapes) | metadata-only live calls (VRAM-safe) |
| 3 | Scoring | exact/regex, schema (json-schema, conventional-commit, compilable-code), judge | TDD: fixture outputs → expected scores |
| 4 | Scorecard | assemble + JSON/MD emit, private vs `--share`, leak assertion | pure-logic tests |
| 5 | Sequencer | load-profile-outer ordering, busy guard, VRAM/tight-broad classes | pure-logic tests |
| 6 | Runner + resume | cell orchestration, `cells.jsonl` checkpoint, `--resume`, error taxonomy | live end-to-end on wraith2 (`gemma3:1b`) |
| 7 | CLI | `gauntlet run \| baseline \| targets \| report` + flags | live smoke |
| 8 | Special batteries | `context-depth` (needle→effective-context curve), `embed` (retrieval eval) | wraith2 |
| 9 | Frontier baseline | `baseline --capability X --sample N`, env-key gated, `baseline_gaps` | mocked key path + 1 real sample |
| 10 | Seed batteries/cases | author real `batteries/*.yaml` + `cases/*` (commit-msg, extract-json, summarize ×2, synthesize, writing registers ×3, code-gen/transform, ocr, embed, judge, context-depth) | first genuine overnight scorecard |

Large plan → expect writing-plans to split it into 2–3 plan docs rather than one.
The contract (phases 1+4) stabilizes early so consumers can build against it.

## Out of scope (unchanged)

Routing/dispatch (Baton), fine-tuning, model downloads, GUI. Per the 2026-06-11
spec's non-goals.
