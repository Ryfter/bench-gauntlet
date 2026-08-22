# Discriminative Scoring v2 — Kevin sign-off summary

**Branch:** `feat/codegen-execution-scorer` · **Full spec:** [`docs/superpowers/specs/2026-08-21-discriminative-scoring-v2-contract.md`](superpowers/specs/2026-08-21-discriminative-scoring-v2-contract.md)  
**Status:** **STAMPED** — Kevin approved 2026-08-22. Items #3–#5 may proceed beyond pure algorithms/tests.

---

## What you're approving

A **multi-axis scorecard contract** that keeps today's JSON loading unchanged while adding three optional extension axes. Baton never collapses axes into one headline number.

| Axis | Roadmap | Scorecard shape | Baton use |
|---|---|---|---|
| **Stable core** | existing | `RunMeta`, `CaseResult`, `Cell`, `Scorecard` — no IP, `score=None` ≠ 0 | Raw `quality_by_dimension` routing |
| **Raw-vs-scaffolded** | #3 | `arm` on Cell/CaseResult; optional `scaffolding_deltas[]` | Scaffold only when `read=scaffolding_recovers` |
| **Pipeline economics** | #4 | `pipeline_economics[]` — premium-equiv tokens, `verified_correct`, `net_savings_ratio` | Pipeline when savings beat frontier-only |
| **ToC placement** | #5 | `sequence_hints` — `BoxResource`, `PlacementHint` | Parallel cheap caps; critical path first |

**Resume/cell key** expands to 5-tuple: `(target, model, context, capability, arm)`.

**Routing brief:** derived `routing-brief/v2` JSON with per-dimension routes, champions, placement hints, and explicit refusal rules per axis.

---

## Already allowed (no sign-off needed)

- Item **#1** code-exec scoring — shipped.
- **Pure algorithms + unit tests** for #3 delta math, #4 cost math, #5 ToC placement (`gauntlet/toc_scheduler.py`).

## Blocked until you sign off

- Live **multi-arm** runs and `--arms` CLI (#3).
- **Frontier API** handoff runs (#4).
- End-to-end **multi-box** ToC validation (#5).

**Do not implement raw-vs-scaffolded #3 behavior** beyond schema defaults and tests until this doc is approved.

---

## Decisions needed (resolve §4.1–§4.4 to unblock #3–#5)

| # | Question | Options / note |
|---|---|---|
| 1 | Where do `scaffolding_deltas[]` live? | Precomputed in scorecard JSON **vs** analyzer-only Markdown |
| 2 | Pipeline economics scope? | Battery-wide aggregate **vs** per-case rows (API cost explodes) |
| 3 | Frontier alias + premium-equiv pricing? | Which models (Opus/Sonnet/Haiku); Gauntlet **vs** Baton owns table |
| 4 | Who emits `routing-brief.json`? | Gauntlet beside scorecard **vs** Baton reconstructs from scorecard + fleet report |
| 5 | ToC hints location? | On scorecard **vs** separate `plan.json` sidecar |
| 6 | Scaffold thresholds? | Confirm `floor=0.10`, `eps=0.05` (may follow first RvS report) |
| 7 | Multi-arm scope v1? | Code-gen only **vs** criteria for second battery |

---

## Sign-off checklist

- [x] **Approve §2–§3** — stable fields, additive extensions, Baton read/refuse rules, routing-brief shape.
- [ ] **Resolve #1–#4** above (delta storage, pipeline scope, frontier alias, brief emitter) — may refine on first RvS.
- [ ] **Note #5–#7** — can defer ToC sidecar choice, thresholds, and multi-arm scope to first RvS report if needed.

**Signed:** Kevin **Date:** 2026-08-22

**Notes:** Stamped via choices queue `ch-c5d002f8232e`. Core contract locked; §4 defaults remain tunable.
