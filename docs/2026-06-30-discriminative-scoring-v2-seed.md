# Discriminative Scoring v2 — design seed (ON HOLD until ~2026-07-02)

> Status: **brainstorming deferred** at Kevin's request (low on premium tokens;
> resume when they refresh). This note captures the goals and reasoning so the
> v2 design starts from here instead of re-deriving. Not a spec yet.

## Why now: the triggering observations

The first real Firefly run (`2026-06-30-firefly-expanded`, 9 models × 7 caps) exposed
three measurement weaknesses:

1. **code-gen is non-discriminative.** Scorer (`scoring/schema.py::compilable_code_match`)
   only runs `compile(code, "<case>", "exec")` — it checks **syntax, not correctness**.
   A `fizzbuzz` returning garbage scores 1.0. Result: 1.0 across nearly every model.
   Cases are also toy classics (fizzbuzz/palindrome/binary-search) memorized by 1B models.
2. **No raw-vs-scaffolded axis.** Gauntlet measures raw capability (normal prompt). Baton
   deploys models *with* scaffolding (decomposition, CoT-engineered prompts). The score
   that predicts production is the scaffolded one — and the **delta** between raw and
   scaffolded is the highest-value signal (tells Baton where scaffolding buys capability
   vs. where it's wasted).
3. **summarize is prompt-dominated.** Each case bakes one fixed prompt; low scores (≤0.49)
   partly reflect prompt↔rubric mismatch (e.g. meeting-notes rubric demands "exactly 3
   bullets w/ owner/action/date" — tests instruction-following as much as summarization).

## Kevin's two over-arching goals (these drive v2)

### Goal 1 — Find the best models for completing real "work"
Purpose: feed `/baton` (Kevin's work/coding harness) so local + inexpensive models reduce
token dependency on frontier models. **Concrete pain:** runs out of premium tokens
(<10% of week's Claude tokens left; ran out of Codex tokens mid-week). Stretching premium
tokens is the actual product requirement, not an abstract benchmark.

New measurement concepts this requires (beyond raw quality):

- **Handoff / "finish-the-job" economics.** Give a complex coding task to a local model,
  then hand its output to a premium model (Opus). Does the local get *enough right* that
  Opus spends ~10% of the tokens it would have spent from scratch? Or does it cost ~100%
  to redo **plus** tokens to *understand* the local-generated code? → the **comprehension
  tax**: cheap output can be net-negative if finding/fixing the wrong 20% costs more than
  starting fresh. v2 must measure **net token cost-to-completion of a pipeline**, not just
  quality-at-a-point.
- **Spec-handoff economics.** Draft a spec in a cheap model (e.g. Haiku), have Opus flesh
  it out. Does the total (cheap spec + premium fleshing) beat Opus-only? Measure it.

Implication: v2 needs a **pipeline/economics scoring mode** — cost (in premium-equivalent
tokens) to reach a *verified-correct* end state, across a model handoff — as a first-class
axis alongside quality.

### Goal 2 — A portable tool for others to test models on their OWN hardware
Let anyone benchmark local models on their own rigs to optimize cost. Personal, portable
"which models are best *here*" scorecard (Goal 2a = their own benchmark chart).

- Example intuition: "maybe my RTX 2080 rig does git-commits *good enough*, freeing the
  RTX 5090 for heavier work with stronger models."
- **Parallelism = efficiency.** Two processes in parallel usually beats one. Gauntlet
  already splits boxes (`firefly-lms`/`firefly-oll`, `busy:` flag) — v2 should make the
  scheduler **Theory-of-Constraints aware**:
  - Identify the bottleneck resource and key blockers.
  - Critical-path cells: start early; place where they finish soonest.
  - Non-critical but heavy cells: run on the strong box.
  - Cheap-capable cells (e.g. commit-msg): run on the weak box **in parallel**.
  - i.e. a light **project-management / scheduling layer** over the work matrix.

## How this internalizes into v2 (the axes to design)

v2 should treat scoring as **multiple distinct axes**, not one number:

1. **Raw capability** — current mode, but with discriminative scorers (see #3).
2. **Scaffolded capability** — same cases, atomized + CoT-engineered prompt; report
   raw-vs-scaffolded **delta** per model×capability.
3. **Pipeline economics** — net premium-equivalent token cost to a *verified-correct*
   finish across a cheap→premium handoff (the comprehension-tax / spec-handoff tests).
4. **Execution-based code-gen** (prerequisite, do first) — run generated code against
   hidden test cases in a sandbox/subprocess; correctness not parseability; harder + more
   varied problems with edge cases, state, multi-function asks.
5. **ToC-aware scheduling** — critical-path + bottleneck-aware placement across boxes for
   the portable tool; powers the personal benchmark chart (Goal 2a).

## Selective-offload principle (from D-2026-06-30c, confirmed by data)
Offload reasoning to local **selectively**. Scaffolding/atomization helps when the failure
is working-memory ("can't hold the whole problem") — NOT when it's a capability gap
("doesn't know the pattern"). Data: qwen3.5-9b reasons fine (0.86) → good offload
candidate; scores 0.00 on commit-msg even with explicit format → atomization won't fix it.
Gauntlet's job is to tell Baton *which* model×capability pairs are safe to offload.

## Sequencing when work resumes
1. **code-gen execution scorer** first — contained, high-impact, unblocks every other
   code number. (Run/verify against hidden asserts.)
2. Then brainstorm full v2 (raw vs scaffolded + pipeline-economics + ToC scheduling) into
   a proper spec under `docs/superpowers/specs/`.

Related decisions: [D-2026-06-30c prompt-optimization-limits], [D-2026-06-30b test-battery-expansion].
