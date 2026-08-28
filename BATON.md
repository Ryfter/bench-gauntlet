# bench-gauntlet — Baton Conductor load brief

**Gauntlet** measures which local model is best at which job, at what cost.
Baton *consumes* scorecards; Gauntlet stays standalone (no Grimdex/Grimlore writes required).

## Read first
- `AGENTS.md` · `CLAUDE.md`
- `docs/superpowers/plans/2026-07-04-discriminative-scoring-v2-plan.md`
- Draft PR **#1** — `feat/codegen-execution-scorer` (item #1 shipped; awaiting review)

## Tonight
- Green Mac pytest (telemetry Darwin fix)
- Item **#2** multi-axis contract spec
- Item **#5** pure ToC placement + tests
- Resume `fleet-0726b` on box-b (5090) for incomplete models
- Never un-busy **both** `box-b-lms` and `box-b-oll` at once

## Privacy
No IPs/hostnames in the public tree. Scorecards stay local/gitignored.

Registry: `~/.baton/projects/bench-gauntlet` · Goal: `goals/08-bench-gauntlet.md`
