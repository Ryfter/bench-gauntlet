# bench-gauntlet — agent guide

This is a **standalone** app: it autonomously benchmarks local LLMs and emits a
scorecard. It is consumed by [Baton](https://github.com/Ryfter/baton) but has **no
dependency on any other repo**. All design and decisions live in this repo — do not
reference or write to any external knowledge base.

Read **[CLAUDE.md](CLAUDE.md)** for the full agent guide and invariants (privacy /
no committed IPs, the single `OpenAIClient` HTTP boundary, resource safety, scoring
honesty). Architecture decisions: **[docs/decisions.md](docs/decisions.md)**. Build
history: **[CHANGELOG.md](CHANGELOG.md)**.

## In flight (2026-07-25)

Branch **`feat/codegen-execution-scorer`**, open as **draft PR #1**, 12 commits
ahead of master and **not merged** — it is awaiting review. Do not branch new work
off master without accounting for it.

It completes item #1 of
**[the discriminative scoring v2 roadmap](docs/superpowers/plans/2026-07-04-discriminative-scoring-v2-plan.md)**:

- `code-exec` scoring — candidate code runs in a subprocess sandbox against hidden
  asserts; score is the **fraction passed**, not whether it parses. Replaces
  `compilable-code`, which scored ~1.0 for every model and measured nothing.
- **108 cases across 12 dimensions** with a T1–T4 difficulty ladder. The fleet is
  1B–30B local models, so all-1.0 and all-0.0 are equally non-discriminative;
  the ladder exists to spread scores. See **[batteries/README.md](batteries/README.md)**.
- Structured `failure_mode` + per-tier scorecard profile, so a scorecard says *why*
  a model missed — the capability-gap vs working-memory distinction Baton needs.
- A benchmark-integrity layer:
  **[threat model](docs/2026-07-25-benchmark-integrity-threat-model.md)**. It blocks
  casual cheating and is **explicitly not a security boundary** — in-process grading
  is structurally reachable. Do not describe it as more than it is.

Two rules that are easy to violate by accident:

1. **Every case must prove itself.** A case only enters the battery if its reference
   solution scores exactly 1.0 and a deliberately-wrong solution scores below it,
   enforced by `tests/test_case_validation.py`. Never hand-add a case to
   `batteries/code-gen.yaml` — the YAML is generated from
   `cases/code-gen/registry.json`. Use
   **[scripts/battery-authoring/](scripts/battery-authoring/README.md)**.
2. **Test on Windows, not just Linux.** Kevin runs Gauntlet on Windows. An earlier
   cloud-authored change shipped POSIX-only process teardown (`os.killpg`/`SIGKILL`)
   that broke every sandbox timeout on his box while passing CI on Linux.

Items #2–5 (v2 spec, raw-vs-scaffolded, pipeline economics, ToC scheduler) need
local inference and/or design sign-off — not autonomously actionable.

