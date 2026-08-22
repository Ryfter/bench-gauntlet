# Discriminative Scoring v2 — Kevin sign-off summary

**Branch:** `feat/codegen-execution-scorer` · **Full spec:** [`docs/superpowers/specs/2026-08-21-discriminative-scoring-v2-contract.md`](superpowers/specs/2026-08-21-discriminative-scoring-v2-contract.md)  
**Status:** design draft — **your sign-off gates items #3–#5 beyond pure algorithms/tests.**

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

## Difficulty ladder

Cases are graded on a 4-rung difficulty ladder; each rung gates which extension axes may claim credit.

| Rung | Name | Definition | Axis eligibility |
|---|---|---|---|
| D1 | **Baseline** | Single-shot, no tools, gold context | Stable core only |
| D2 | **Tool-assisted** | Multi-step with tool loop, gold context | + Raw-vs-scaffolded (#3) |
| D3 | **Ambiguous-context** | Noisy/partial context; retrieval required | + Pipeline economics (#4) |
| D4 | **Open-ended** | Under-specified task; self-directed decomposition | + ToC placement (#5) |

- Ladder rung is recorded as `difficulty` on each `Cell`.
- A case contributes to an extension axis only if its rung meets that axis's minimum.
- Rung assignment is fixed at battery-authoring time — never inferred post-hoc from scores.

---

## Case self-proof requirement

Every `CaseResult` must carry a **self-proof**: machine-checkable evidence that the recorded outcome occurred as scored.

- **Form:** per-case `proof` object — transcript hash, executed-command exit codes, artifact digests, assertion results.
- **Demotion rule:** a case with `score != None` but missing/failing self-proof is rewritten to `score=None`, `status="unproven"` — counted as neither pass nor fail (`score=None` ≠ 0 still holds).
- **No retro-proofing:** proofs must be emitted by the runner during execution; post-hoc reconstruction from logs is rejected by the integrity layer.
- **All arms:** applies to raw and scaffolded alike; scaffolded-arm proofs must also include the scaffolding payload digest so #3 deltas stay attributable.

---

## Integrity layer

A validation pass that runs before any Baton consumption of a scorecard. It **refuses, never repairs**, malformed input.

1. **Schema conformance** — stable fields present; extensions validated against their optional-axis shapes.
2. **Cell key uniqueness** — 5-tuple `(target, model, context, capability, arm)` unique across cells.
3. **Self-proof verification** — every non-`None` score has a passing proof (see above).
4. **Arithmetic consistency** — aggregates recompute from cells within epsilon; mismatch ⇒ refuse entire scorecard.
5. **Provenance chain** — scorecard references its battery spec hash and scorer version; unknown versions refused.

Output is either clean pass-through or a refusal report listing failed checks with cell keys. Baton never consumes a refused scorecard, and refusals surface verbatim rather than being silently dropped.

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

- [ ] **Approve §2–§3** — stable fields, additive extensions, Baton read/refuse rules, routing-brief shape.
- [ ] **Approve difficulty ladder, self-proof rule, integrity layer** — rung gating per axis, unproven demotion, refusal-not-repair semantics.
- [ ] **Resolve #1–#4** above (delta storage, pipeline scope, frontier alias, brief emitter).
- [ ] **Note #5–#7** — can defer ToC sidecar choice, thresholds, and multi-arm scope to first RvS report if needed.

**Signed:** _________________________ **Date:** _____________

**Notes:**
