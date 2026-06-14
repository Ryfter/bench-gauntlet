# bench-gauntlet — agent guide (read first)

Gauntlet is a **standalone** application: it autonomously benchmarks local LLMs
across many capabilities and emits a scorecard rating *which model is best at which
job, at what resource cost*. It is **consumed by** [Baton](https://github.com/Ryfter/baton)
— which feeds the scores back in to guide picking local LLMs as tools — but Gauntlet
has **no build/runtime dependency on any other repo**, and we keep it that way.

All design, decisions, and lessons live **in this repo**. Do not reference or write
to any external knowledge base.

## Where things live
- **Purpose / "why":** `docs/2026-06-11-gauntlet-design.md` (purpose, non-goals, the 8 decisions).
- **Build design / "how":** `docs/2026-06-12-gauntlet-build-design.md`.
- **Implementation plans:** `docs/superpowers/plans/`.
- **Battery authoring:** `batteries/README.md`.
- **New architecture/coding decisions:** add a dated note under `docs/` (keep the
  rationale with the code it governs; don't send it to an external KB).

## Invariants — do not break
- **Privacy (hard rule):** personal network info (Tailscale IPs, hostnames, logins,
  endpoints) must be *physically incapable* of entering the public tree — not merely
  gitignored. The scorecard schema has no base_url/IP field; box identity is dual
  (private hostname vs public hardware label); `targets.yaml` and `scorecards/` are
  gitignored; `--share` drops hostnames; a pre-write leak guard rejects IP/URL in
  emitted scorecards. Never commit a real IP/host — use placeholders
  (`<wraith2-host>`) in docs and TEST-NET (`203.0.113.0/24`) in test fixtures.
- **HTTP boundary:** `gauntlet/client.py` (`OpenAIClient`) is the ONLY component that
  performs HTTP. Everything else stays pure-logic-testable.
- **Resource safety:** real inference targets a headless box. Never run inference
  against a box being gamed on — mark it `busy: true` to defer its cells. The
  frontier baseline never runs without `GAUNTLET_FRONTIER_API_KEY`.
- **Scoring honesty:** deterministic scorers preferred; an LLM judge never grades its
  own model family; an unjudgeable case is `unscored`, never silently 0.

## Tests
Pure-logic TDD is the default suite (`.venv/Scripts/python -m pytest`, no network).
Live integration is opt-in (`pytest -m live`) and is metadata-only or
headless-box-only — the live suite never targets a gaming box.
