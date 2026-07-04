# Discriminative Scoring v2 — roadmap

> Supersedes the brainstorming status of `docs/2026-06-30-discriminative-scoring-v2-seed.md`
> (that doc stays as the "why" — read it first). This is the tracked, ordered roadmap:
> what ships in what order, why that order, and what each item needs to run.

**Goal:** make Gauntlet's scoring tell Baton *which* model×capability pairs are safe
to offload, at what token cost, and where to place them across boxes — not just a
single raw-quality number per capability.

## Sequencing rationale

Item 1 is contained (pure-logic + subprocess, no design dependencies, no local
inference) and it unblocks every downstream code-gen number — every other item that
touches code-gen quality inherits whichever scorer is live, so it goes first and
alone. Items 3–5 all depend on a multi-axis scoring *contract* (how axes compose in
the `Cell`/`Scorecard` schema, how a delta or a pipeline-cost gets represented) that
doesn't exist yet — hence item 2 (the full spec) gates all three. Within 3–5 there's
no further ordering dependency on each other, but all three need live local
inference to produce real numbers, so none of them can proceed until the inference
boxes (firefly/wraith2) are available and not busy.

## 1. Code-gen execution scorer — DO FIRST

Run generated code against **hidden** assert-based tests in a subprocess sandbox;
score functional correctness, not parseability. Expand the case set with harder,
varied problems (edge cases, stateful objects, multi-function asks) — the toy
classics (fizzbuzz/palindrome/binary-search) are memorized even by 1B models and
don't discriminate.

- **Why first:** contained (pure-logic + subprocess), no design sign-off needed,
  **needs NO local inference** — can run entirely in a cloud/CI environment.
  High-impact: it's the prerequisite for every other code-gen number v2 produces.
- **Runs where:** anywhere (cloud-safe). No inference target required to build or
  test it; a local model is only needed later, to actually *score* one against it.
- **Status:** implemented this session — see `gauntlet/scoring/execute.py`,
  the `code-exec` scoring method, and the six new `code-gen` cases
  (`run-length-encode`, `matrix-transpose`, `safe-divide`, `factorial-strict`,
  `inventory-tracker`, `prime-pair`). `compilable-code` stays available for
  backward compat; scorer is selectable per case.

## 2. Full v2 brainstorm → proper spec

Turn the seed doc's three axes (raw, scaffolded, pipeline economics) plus the
scheduler idea into a real spec under `docs/superpowers/specs/`: exact `Cell`/
`Scorecard` schema changes, how a raw-vs-scaffolded delta is represented, how
pipeline-economics cost is computed and stored, and what a ToC-aware placement
decision looks like in the plan/sequencer output.

- **Why second:** gates items 3–5. Each of them needs the multi-axis scoring
  *contract* nailed down first — otherwise they'd each invent incompatible
  ad-hoc representations that have to be reconciled later.
- **Runs where:** design work — cloud-safe, no inference needed. Needs Kevin's
  sign-off before 3–5 start (this is a design gate, not an implementation one).

## 3. Raw-vs-scaffolded axis

Same cases, run twice: once with the current (raw) prompt, once atomized +
CoT-engineered. Report the per-model × capability **delta**, not just two
absolute numbers — the delta is the signal Baton needs (where scaffolding buys
capability vs. where it's wasted).

- **Selective-offload guardrail (D-2026-06-30c, confirmed by data — must not be
  papered over):** scaffolding only helps when the failure mode is
  working-memory ("can't hold the whole problem"), not a capability gap
  ("doesn't know the pattern"). Data point from the seed: qwen3.5-9b reasons at
  0.86 raw (a good offload candidate — the model *has* the capability) but
  scores 0.00 on commit-msg even with the format spelled out explicitly
  (atomization won't fix a pattern it never learned). Item 3's reporting must
  make this distinction visible per model×capability — e.g. flag cases where
  scaffolding delta ≈ 0 *and* raw score is already near-floor as "not an offload
  candidate," versus delta > 0 as "scaffolding recovers capability." A single
  aggregate "scaffolded score went up" number would hide exactly the failure
  mode Kevin needs to see.
- **Needs local inference:** yes — every case re-runs against real models.
- **Runs where:** local inference boxes only (firefly/wraith2, non-busy).

## 4. Pipeline economics

Net premium-equivalent token cost to reach a **verified-correct** finish across
a cheap→premium handoff:
- **Comprehension tax:** local model produces output, Opus is handed the output
  and must finish/fix it — does it cost ~10% of from-scratch tokens, or does
  understanding + fixing the wrong parts net out worse than a fresh Opus-only
  attempt?
- **Spec-handoff:** cheap model (e.g. Haiku) drafts a spec, Opus fleshes it out
  — does cheap-spec + premium-flesh-out beat Opus-only end to end?

This is a new scoring *mode* (cost-to-verified-correct across a handoff), not a
per-case scorer — it needs its own representation in the scorecard schema (item 2).

- **Needs local inference:** yes — the local leg of the handoff is a real model call.
- **Runs where:** local inference boxes only, plus a premium API key
  (`GAUNTLET_FRONTIER_API_KEY`) for the handoff leg.

## 5. ToC-aware scheduler

Theory-of-Constraints-aware cell placement across boxes: identify the
bottleneck resource, run critical-path cells where they finish soonest, place
non-critical-but-heavy cells on the strong box, and run cheap-capable cells
(e.g. commit-msg) on the weak box in parallel. Powers the portable "which
models are best *here*" chart (seed doc Goal 2a) — this is what makes Gauntlet
useful to someone else on their own rig, not just a fixed two-box setup.

- **Needs local inference:** yes, to validate the scheduler actually improves
  wall-clock on a real multi-box run (not just a scheduling-logic unit test —
  though the placement algorithm itself is pure and can be unit-tested without
  inference; only the end-to-end validation needs boxes).
- **Runs where:** placement algorithm is cloud-safe to build and unit-test;
  validation needs the local boxes (firefly/wraith2).

## Open questions carried into item 2

- Exact `Cell` schema shape for a delta (raw vs. scaffolded) and for a pipeline
  cost — additive fields vs. a nested sub-object.
- Where scaffolded-prompt variants live (parallel `cases/` tree vs. a
  transform applied at run time).
- How "verified-correct" is determined for pipeline economics without a human
  in the loop (presumably: the existing deterministic/judge scorers, applied to
  the *final* handoff output).
