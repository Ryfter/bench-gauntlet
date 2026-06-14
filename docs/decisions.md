# Decisions

In-repo decision log (this project keeps its reasoning with the code, not in an
external knowledge base). The original product decisions live in
[`2026-06-11-gauntlet-design.md`](2026-06-11-gauntlet-design.md) (the 8 decisions)
and the architecture in [`2026-06-12-gauntlet-build-design.md`](2026-06-12-gauntlet-build-design.md).
This file records cross-cutting and post-build decisions.

---

## D-2026-06-13a — Gauntlet is standalone; no external knowledge-base dependency
**Decision:** Gauntlet has no build/runtime/process dependency on any other repo.
All design, decisions, and lessons live in this repo. The repo's `CLAUDE.md` was
rewritten from a pointer at an external coding knowledge base into a self-contained
agent guide.

**Why:** Gauntlet is meant to be a public, standalone app that autonomously
benchmarks local LLMs. Its scores are fed back into [Baton](https://github.com/Ryfter/baton)
to guide picking local LLMs as tools — but that is a *consumer* relationship, not a
dependency. Hanging an external-KB dependency on it would couple a clean standalone
tool to private tooling and leak a private local path into the public tree.

**Consequences:** New architecture/coding decisions are recorded here under
`docs/`. Nothing references or writes to an external KB.

---

## D-2026-06-13b — Special evals are dedicated subcommands, not auto-dispatched in `gauntlet run`
**Decision:** Context-depth and embeddings retrieval are run by their own CLI
subcommands (`gauntlet depth`, `gauntlet embed`), and the frontier baseline by
`gauntlet baseline` — not folded into `gauntlet run`'s per-case loop. Each fills its
own scorecard section (`context_depth[]`, an `embed` cell, `baseline_gaps[]`), and
`scorecard.merge_into_scorecard` lets a special command enrich a prior run's
scorecard.

**Why:** These evals don't fit the `Case` → `score_case(output)` flow that `run`
is built on. Context-depth sweeps synthetic prompts across lengths/depths and
reduces a curve; embeddings rank a corpus by cosine similarity; the baseline calls a
paid external endpoint. Modelling each as a "special battery" with a pure core +
thin live runner keeps `runner.py` simple, keeps every core unit-testable without a
network, and keeps the paid/opt-in path (baseline) explicitly separate from the
default run.

**Consequences:** An overnight flow is `run` then the special commands, each
merging into the same scorecard JSON (see README "Overnight run"). The frontier
baseline is gated behind `GAUNTLET_FRONTIER_API_KEY` and never runs by default.

---

## D-2026-06-13c — Privacy remediation: scrub committed IP, rewrite history, recreate remote
**Decision:** A real Tailscale IP had been committed to tracked files (the
scorecard leak-guard test fixtures and config examples). Remediation: replace it in
HEAD with placeholders (`<wraith2-host>` in docs) and TEST-NET `203.0.113.10` in
test fixtures; rewrite git history (`git filter-repo --replace-text`) to purge it
from every commit; and recreate the private GitHub remote from the clean local
history so no merged-PR ref retains the old commits.

**Why:** The standing privacy rule is that personal network info must be
*physically incapable* of entering the public tree, not merely gitignored. Even
though the IP is a non-routable tailnet (CGNAT `100.64.0.0/10`) address in a private
repo — so real exposure was negligible — the repo is intended to go public, and the
clean-slate fix is cheap on a young repo with no stars/forks.

**Consequences:** Reinforced in `CLAUDE.md`: never commit a real IP/host — use
`<wraith2-host>` placeholders in docs and TEST-NET (`203.0.113.0/24`) in test
fixtures. The leak guard (`scorecard.assert_no_leak`) remains the automated backstop
on emitted scorecards.
