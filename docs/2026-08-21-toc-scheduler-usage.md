# ToC scheduler — wiring guide (future)

`gauntlet/toc_scheduler.py` is **pure** (no network). It ships with unit tests but is **not** wired to the live runner yet. Use this when item #5 moves from algorithm-only to end-to-end multi-box validation (after discriminative-scoring v2 sign-off).

## What it does

`plan_placement(boxes, cells) -> TocPlacementPlan` orders work into box batches:

1. **Critical** cells → strongest available box (exclusive)
2. **Heavy** non-critical (cost ≥ 5) → strongest **broad** box (exclusive)
3. **Cheap** cells → **tight** boxes, co-packed when `vram_gb` fits
4. **Busy** boxes skipped; affinity-pinned cells on a busy box → `deferred`

Inputs: `TocBox` (`id`, `vram_gb`, `usage_class`, `busy`), `TocCell` (`model`, `context`, `battery`/capability, `estimated_cost` or `weight`, `critical`, `vram_gb`, optional `box_id` affinity).

## Current vs ToC planner

| Layer | Today | After wiring |
|---|---|---|
| Planner | `sequencer.plan_run` — profile-outer, battery-inner | `toc_scheduler.plan_placement` — cell cost + box class |
| Config | `GauntletConfig.boxes` + `targets.yaml` | same; map `Box` → `TocBox` |
| Footprint | `sequencer.estimate_footprint_gb` | reuse for `TocCell.vram_gb` |
| Execution | `runner.execute_plan` iterates `LoadGroup` | iterate `TocBatch`; honor `exclusive` vs parallel tight packs |

## Integration steps (minimal diff)

1. **Adapter** (`gauntlet/toc_adapter.py`): `box_to_toc(b: Box) -> TocBox`; `planned_cell_to_toc(c, footprint, critical=False) -> TocCell` (capability → `battery` field).
2. **Plan entry** in `runner.execute_plan`: build cells via `sequencer.build_cells`, enrich footprints, call `plan_placement`, map `TocBatch` → existing `LoadGroup` shape (or teach the loop batches directly).
3. **Critical flag**: mark code-gen @ highest context or explicit CLI `--critical-models` until pipeline economics (#4) supplies weights.
4. **Sidecar** (optional): emit `sequence_hints.json` per `docs/superpowers/specs/2026-08-21-discriminative-scoring-v2-contract.md` §2c — advisory only; never mutates `Cell.quality`.
5. **CLI gate**: hide behind `--planner toc` until multi-box wall-clock validation passes; default stays `sequencer`.

## Tests before merge

- Existing: `tests/test_toc_scheduler.py` (pure placement)
- Add: adapter round-trip + `execute_plan` smoke with two mock boxes (busy deferral, tight co-pack)
- Validate on box-b (5090 broad) + box-c (2070 tight) — never un-busy both `box-b-lms` and `box-b-oll`

## Related

- Contract: `docs/superpowers/specs/2026-08-21-discriminative-scoring-v2-contract.md` §2c
- Roadmap: `docs/superpowers/plans/2026-07-04-discriminative-scoring-v2-plan.md` §5
