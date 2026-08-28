# Raw-vs-scaffolded axis — design spec

**Status:** design, awaiting Kevin sign-off before implementation.
**Roadmap item:** #3 of
[`docs/superpowers/plans/2026-07-04-discriminative-scoring-v2-plan.md`](../plans/2026-07-04-discriminative-scoring-v2-plan.md).
**Depends on:** item #1 (`code-exec` + 108-case code-gen battery) — shipped.
**Does not wait on:** item #2 (full multi-axis contract). This spec owns the
raw-vs-scaffolded slice of that contract so the experiment can run without
waiting for pipeline-economics or ToC scheduling to land.
**Scope:** `code-gen` only, for the first run. Other batteries stay single-arm
until this axis proves useful on the battery that has structured
`failure_mode` (the signal the hypothesis needs).

Related: [D-2026-06-30c](../../decisions/D-2026-06-30c-prompt-optimization-limits.md),
[seed doc](../../2026-06-30-discriminative-scoring-v2-seed.md),
[integrity threat model](../../2026-07-25-benchmark-integrity-threat-model.md).

---

## 1. Purpose and the falsifiable prediction

### What we are measuring

Baton does not ship a bare prompt to a local model and hope. It decomposes work,
adds structure, and sometimes multi-steps the model. Gauntlet today measures only
the bare path — one prompt, one reply, score. That number understates what a
model can do under the conditions Baton actually uses, and it cannot tell *where*
structure helps.

The raw-vs-scaffolded axis answers one question:

> For a given model × dimension, does decomposing the ask improve
> execution-scored quality relative to the same case raw?

The **delta** is the product. Absolute scaffolded quality matters for routing;
the delta is what distinguishes "scaffolding recovers capability" from "this
model never learned the pattern."

### The selective-offload hypothesis (D-2026-06-30c)

Scaffolding helps a **working-memory** failure ("can't hold the whole problem at
once") and does nothing for a **capability gap** ("never learned the pattern").
The fleet already records structured `failure_mode` per case. That makes the
hypothesis falsifiable for the first time:

| Dominant raw failure mode | Predicted scaffolding effect | Baton read |
|---|---|---|
| `wrong_answer` | **gain** — delta > 0 on dimensions where raw is mid-range | scaffolding candidate; structure recovers capability the model already has |
| `no_code_emitted` / `syntax_error` | **flat** — delta ≈ 0, raw near floor | not an offload candidate; atomization will not teach a missing pattern |
| `timeout` | **flat or worse** — multi-turn burns more wall clock | too slow for this battery as-is; scaffolding is not the lever |
| mixed / no dominant mode | **uncertain** — report the data, do not force a label | look per-dimension; do not trust a single aggregate |

The prediction is **per model × dimension**, not "scaffolding helps models." A
model can be `wrong_answer`-dominant overall and still flat on `test-authoring`
while gaining on `bug-fix`. That is the signal, not noise to average away.

### What would disconfirm D-2026-06-30c

If both groups gain **uniformly** — capability-gap models and scaffolding
candidates improve by similar deltas across dimensions — then the selective-
offload principle is **wrong**, or at least not the right cut for this fleet.
That is a valuable outcome. It means Baton can apply generic scaffolds more
broadly than the decision currently recommends, and Gauntlet should stop using
failure-mode dominance as a routing gate for scaffolding. The experiment exists
to find this out; a flat "scaffolding always helps" result is not a failed run.

D-2026-06-30c's original evidence was narrow (prompt-wording tweaks on
commit-msg / extract-json for two models). This axis is the proper test on
code-gen with execution scoring and 108 cases.

### What this does *not* claim

- It does not measure hand-tuned, per-case scaffolds. Those measure the author's
  decomposition skill (see §2).
- It does not measure iterative debugging against hidden tests. That is a
  stronger intervention and a leak (see §2, multi-turn hard constraint).
- It does not replace raw quality. Raw remains the control and the default cell
  shape for consumers that have not opted into multi-arm reporting.

---

## 2. The three arms

All three arms use the **same 108 cases**, the **same hidden tests**, and the
**same** `code_execution_match` scorer. Only the prompting path differs. If arms
were scored differently, the delta would be meaningless.

### Why generic runtime templates — not per-case authored scaffolds

Arms 2 and 3 apply **generic templates at run time**. There is no parallel
`cases/code-gen-scaffolded/` tree and no per-case scaffold text in the registry.

The argument is not elegance; it is external validity. Baton can only ever apply
a **generic** scaffold automatically at runtime — a fixed wrapper or a fixed
multi-turn recipe that does not know the case. A hand-tuned scaffold written by
a human who has read the hidden tests would measure the author's skill at
decomposing *this* problem, and would measure something Baton can never deploy.
That number would look impressive and transfer poorly. Generic templates measure
what production can actually do.

(If later evidence shows generic templates are too weak to recover working-memory
failures that a smarter automatic decomposer could recover, that is a finding
about template strength — see §8 — not a license to backfill hand-authored
scaffolds into the battery.)

### Arm 1 — raw (control)

The existing path: load `case.prompt_file`, one `client.chat(...)` call, strip
think-tags, score. No wrapper. This is today's `run_cell` behaviour and remains
the default when no arm is selected.

### Arm 2 — prompt-scaffolded (one call, structured wrapper)

One call. The case prompt is wrapped in a generic scaffold that forces numbered
steps, an explicit think-then-answer contract, and a hard output rule. The
wrapper is identical for every case.

**Exact template** (`{prompt}` is replaced with the full contents of
`case.prompt_file`):

```
You are solving a single programming task. Work the steps in order. Do not skip
steps. Do not invent requirements that are not in the task.

## Task
{prompt}

## Steps
1. Restate the requirements in your own words as a short bullet list. Include
   inputs, outputs, edge cases the task mentions, and any constraints (types,
   errors, complexity, mutation rules).
2. Sketch the approach in 2–5 bullets before writing code. Name the main data
   structures and the order of operations.
3. Implement the solution.
4. Mentally check the implementation against the edge cases you listed in step 1.
   If you find a defect, fix the code before emitting the final answer.

## Output contract
- Steps 1–2 and any self-check notes may be written as short prose or bullets.
- The final answer must be a single Python code block (fenced with ```python)
  containing only the implementation the task asked for — no tests, no example
  calls, no README.
- Do not mention hidden tests, graders, or scoring.
```

Rationale for this shape: it is the cheapest intervention Baton can apply (one
extra system-ish wrapper, one call). It tests whether *structure in the prompt*
alone moves the needle. Numbered steps and an output contract are deliberately
generic; they do not encode case-specific hints.

### Arm 3 — multi-turn (harness-driven, three turns, final artifact only)

Three sequential chat turns for the same case. The harness owns the turn
prompts; the model only ever sees its own prior outputs plus the next generic
instruction. **Only the final turn's artifact is scored.** Intermediate turns
are retained in `cases.jsonl` for diagnosis but do not contribute to quality.

**Hard constraint — no grader feedback, no hidden tests:**

> The multi-turn arm must **never** see the hidden tests, assert results, pass/
> fail signals, execution traces, `failure_mode`, scores, or any other output of
> the sandbox. Each turn receives only (a) the generic turn template and (b) the
> model's own prior reply text. Letting the model iterate against the grader is
> a different and much stronger intervention (test-time search / repair loop).
> It is also an answer leak: the score would measure "can fix code when told it
> failed," not "does decomposition help." That experiment, if wanted later, is
> a separate axis with its own integrity review.

**Turn 1 — restate the rules**

```
You will solve a programming task across three turns. This is turn 1 of 3.
Do not write the implementation yet.

## Task
{prompt}

## Your job this turn
Restate the requirements as a short bullet list:
- inputs and their types
- expected outputs and return types
- edge cases and error behaviour the task specifies
- constraints (in-place mutation, complexity, allowed imports, naming, etc.)

Output ONLY the bullet list. No code.
```

**Turn 2 — implement**

```
This is turn 2 of 3. Using your restatement below, implement the solution.

## Original task
{prompt}

## Your restatement (turn 1)
{turn1_text}

## Your job this turn
Write the full implementation. Output a single Python code block (fenced with
```python) containing only the implementation the task asked for — no tests,
no example calls, no README. You may include a one-line note before the fence
if needed; the code block is what will be kept.
```

**Turn 3 — self-check**

```
This is turn 3 of 3. Review your implementation against the requirements and
fix defects you can see. You do not have test results; reason from the spec.

## Original task
{prompt}

## Your restatement (turn 1)
{turn1_text}

## Your implementation (turn 2)
{turn2_text}

## Your job this turn
1. List edge cases from the task and whether your code handles them (brief).
2. If you find a defect, emit a corrected full implementation.
3. If the implementation is already correct, re-emit it unchanged.

Final output must include a single Python code block (fenced with ```python)
containing the final implementation. That code block is the only thing that
will be scored.
```

**Scoring input for arm 3:** after think-tag strip, run the existing code
extractor (`extract_code`) on **turn 3's** reply only, then
`code_execution_match` against the same hidden tests as arms 1 and 2. If turn 3
is truncated into `no_code_emitted` / `syntax_error`, apply the existing
`attribute_truncation` rule (see §4). Turns 1–2 are never scored for quality.

**Conversation mechanics:** each turn is a fresh `messages` list built by the
harness (user turns only, or user/assistant alternating with prior model text
as `assistant` content). Prefer alternating roles so the serving stack sees a
normal multi-turn chat:

1. `user`: turn-1 template → model reply₁  
2. `user`: turn-1 template, `assistant`: reply₁, `user`: turn-2 template → reply₂  
3. full history through turn-2, then turn-3 template → reply₃  

Prior model text is the raw reply (after optional think-tag strip for the
*next* prompt's embedding of `{turnN_text}`, so a thinking model does not blow
the context with a duplicated chain-of-thought). Think-tag strip before
**scoring** remains universal per D-2026-06-21a.

`OpenAIClient` today only accepts a single `prompt: str`. Arm 3 needs a thin
extension — either `chat(messages: list[dict])` or `chat(prompt=..., history=...)`
— still the sole HTTP boundary. Pure callers keep building message lists;
`client.py` remains the only place a request is constructed (and the only place
`assert_request_is_tool_free` runs).

### Token budget

`code-gen` already sets `max_tokens: 4096` per call. That budget applies **per
call**, not per case: arm 3 can emit up to 3 × 4096 completion tokens for one
case. Do not silently raise the budget for multi-turn to "make it fair"; the
point includes whether the extra turns are worth the cost. Truncation handling
is in §4 and §6.

---

## 3. Schema changes

### Design choice: additive optional fields, not a nested sub-object

Existing scorecards on disk (and anything Baton already parsed) must keep
loading. Pydantic models gain **optional fields with defaults** so old JSON
round-trips: missing `arm` means raw, missing delta fields mean "this cell was
not part of a multi-arm run."

A nested `scaffolding: { raw, scaffolded, delta }` sub-object was considered and
rejected for this item:

- Raw cells are the common case. Nesting forces every consumer to dig for
  quality in two places depending on run type.
- Deltas are **derived across cells**, not properties of a single case run. A
  case result knows which arm produced it; the delta lives on a paired summary
  or in the analyzer, not inside every `CaseResult`.
- Pipeline-economics (item #4) will need its own shape. Stuffing both into one
  vague `axes` object before that design exists invites a second migration.

Additive fields keep the existing `Cell.quality` meaning ("quality for this
cell's arm") and let the analyzer join arms by `(model, target, context,
capability, case_id)`.

### `CaseResult` — per-case arm tag and multi-turn detail

```python
class CaseResult(BaseModel):
    case_id: str
    method: str
    score: float | None          # None == unscored; never silently 0
    passed: bool
    detail: str = ""
    failure_mode: str | None = None
    tier: str | None = None
    dimension: str | None = None
    integrity_violations: list[dict] = Field(default_factory=list)

    # --- raw-vs-scaffolded (optional; absent/default = single-arm legacy) ---
    arm: Literal["raw", "prompt_scaffolded", "multi_turn"] = "raw"
    # For multi_turn only: per-turn completion token counts and finish reasons,
    # so truncation and cost can be diagnosed without re-running. Not scored.
    turn_metrics: list[dict] | None = None
    # True when this case was excluded from arm-comparison because a peer arm
    # was truncated/unscored while this one was not (or vice versa). The score
    # remains on the case for absolute reporting; paired delta ignores it.
    incomparable: bool = False
```

`turn_metrics` items are plain dicts of the form
`{"turn": 1|2|3, "prompt_tokens": int|None, "completion_tokens": int|None,
"finish_reason": str|None, "latency_s": float}` — enough to rebuild cost and
truncation without storing full reply text in the scorecard JSON (replies stay
out of the canonical scorecard; optional debug logging is a runner concern, not
schema).

### `Cell` — one cell per (model × capability × arm)

```python
class Cell(BaseModel):
    model: str
    target: str | None
    box: str
    context: int
    capability: str
    quality: float | None
    pass_rate: float | None
    # ... existing latency / token / tier / dimension / failure_modes fields ...

    arm: Literal["raw", "prompt_scaffolded", "multi_turn"] = "raw"
```

**Cell identity for resume and plan keys** expands from
`(target, model, context, capability)` to
`(target, model, context, capability, arm)`. A raw cell and a multi-turn cell
for the same model×battery are different cells; finishing one must not mark the
other done.

`quality`, `quality_by_tier`, `quality_by_dimension`, and `failure_modes` on a
cell are **always arm-local**. There is no `delta` field on `Cell`. Deltas are
computed at report time from paired cells (or from `cases.jsonl`) so a partial
run that finished raw but not multi-turn does not emit a half-baked delta that
looks complete.

### Scorecard / run meta — experiment labelling

```python
class RunMeta(BaseModel):
    id: str
    date: str
    gauntlet_version: str
    # Optional experiment tag; free string so other axes can reuse it later.
    # Examples: "raw-vs-scaffolded", "raw-only" (default/absent).
    experiment: str | None = None
    arms: list[str] | None = None   # e.g. ["raw", "prompt_scaffolded", "multi_turn"]
```

No new top-level scorecard section is required for v1 of this axis. The Markdown
report and `analyze_fleet.py` join cells by model×capability×arm. If a future
consumer wants a precomputed delta blob in JSON, add a `scaffolding_deltas: list
[ScaffoldingDelta]` section later without breaking cells — same pattern as
`context_depth[]` / `baseline_gaps[]`.

Optional precomputed record (analyzer may write a sidecar; not required on
`Scorecard` for the first implementation):

```python
class ScaffoldingDelta(BaseModel):
    model: str
    capability: str              # "code-gen"
    dimension: str               # or "*" for all-dimensions rollup
    arm: Literal["prompt_scaffolded", "multi_turn"]
    # Means over cases scored in BOTH this arm and raw (incomparable excluded).
    raw_quality: float | None
    arm_quality: float | None
    delta: float | None          # arm_quality - raw_quality; None if either side empty
    n_paired: int                # cases entering the means
    n_excluded_unscored: int
    n_excluded_incomparable: int
    # Classification for Baton — see §5.
    read: Literal[
        "scaffolding_recovers",
        "not_offload_candidate",
        "flat_already_capable",
        "insufficient_pairs",
    ]
```

### `cases.jsonl` rows

Extend the per-case append format (already arm-agnostic JSON objects):

```json
{
  "model": "...", "target": "...", "context": 8192,
  "capability": "code-gen", "case_id": "...",
  "arm": "multi_turn",
  "tier": "T3", "dimension": "bug-fix",
  "score": 0.75, "passed": false,
  "failure_mode": "wrong_answer",
  "incomparable": false
}
```

`arm` defaults to `"raw"` when absent so older run directories still analyze.

### Backward compatibility

| Artifact | Old behaviour | New behaviour |
|---|---|---|
| Scorecard JSON without `arm` | loads | `arm="raw"` via default |
| `cell_key` / resume | 4-tuple | 5-tuple including `arm`; old `cells.jsonl` lines without `arm` key as raw |
| `aggregate_cell` | unchanged inputs | pass `arm=` through; default raw |
| Baton / external parsers ignoring unknown fields | fine | new fields optional |
| Leak guard | unchanged | still no base_url/IP; arm names are not endpoints |

---

## 4. Run mechanics

### Selection

CLI (illustrative; exact flag names can match Typer style elsewhere):

```text
gauntlet run ... --arms raw,prompt_scaffolded,multi_turn
gauntlet run ... --arms raw                  # default; today's behaviour
gauntlet run ... --capability code-gen --arms raw,multi_turn
```

Rules:

- Default `--arms raw` preserves every existing workflow and fleet script.
- Multi-arm runs are restricted to batteries that declare support — for this
  spec, **only `code-gen`**. Passing `--arms prompt_scaffolded` for `commit-msg`
  is an error, not a silent no-op: other batteries lack the failure-mode
  vocabulary the hypothesis needs, and wrapping their "Output ONLY …" prompts
  would change the instruction-following measurement those batteries exist for.
- Arms run as **separate cells** in the plan (same model load, three cells for
  three arms), not as an inner loop that hides progress. Status and resume stay
  cell-granular.

### Run-id convention

Multi-arm experiments use an explicit run id, not a silent reuse of a raw fleet
directory:

```text
scorecards/rvs-<YYYYMMDD>-<short-label>/
  meta.json          # experiment: "raw-vs-scaffolded", arms: [...]
  cells.jsonl
  cases.jsonl
```

Example: `rvs-20260726-box-b-4model`. Do not append multi-arm cells into an
existing raw fleet run (`fleet-0726b` etc.) — mixing arms in a directory that
consumers treat as single-arm raw would silently double-count models in old
analyzers that ignore the `arm` field. A dedicated run id makes the experiment
opt-in at the directory level.

### Keeping the three arms comparable

Comparability is a property of a **case × model × arm triple**, not of the cell
mean alone.

1. **Same case definitions.** All arms load the same `Battery` / registry; no
   case subsetting per arm.
2. **Same scorer path.** `score_case` → `code-exec` → same `tests_file`, same
   sandbox, same integrity guards. Arm code may only change how the candidate
   source text is produced.
3. **Same extraction for scoring.** `extract_code` on the scored reply (arm 3:
   turn 3 only). Think-tag strip before score for all arms.
4. **Paired exclusion for deltas.** A case enters a raw-vs-arm delta only if
   **both** arms produced a numeric `score` (not `None`) **and** neither side
   was marked incomparable due to asymmetric truncation (below). Unscored stays
   unscored: never coerce `None` to `0.0` in a mean (scoring-honesty invariant;
   same rule as `analyze_fleet.mean_excluding_nulls`).

### Truncation and asymmetric exclusion

`attribute_truncation` already maps `truncated + (no_code_emitted|syntax_error)`
to `failure_mode="truncated"`, `score=None`. That rule applies **per call**. For
arm 3, if **any** of the three calls truncates in a way that excuses the final
artifact (turn 3 truncated into no code / syntax error, or turn 2 truncated so
turn 3 never received an implementation), the case is unscored for that arm.

**Asymmetric truncation:** if case C is truncated/unscored on arm A but scored
on arm B, the pair is **not** a valid scaffolding comparison. Mark both sides
`incomparable=True` for delta purposes (or mark at join time in the analyzer if
the flag was not written live). Absolute quality tables may still show each
arm's score; the delta table must drop the pair and count it under
`n_excluded_incomparable`.

Reading a truncated multi-turn miss as "scaffolding failed" would attribute a
token-budget artifact to the model. The existing unscored rule exists exactly
to prevent that class of lie; multi-arm reporting must not reintroduce it at the
delta layer.

### Resume

Resume keys on `(target, model, context, capability, arm)`:

- Finished raw cell, crash mid multi-turn cell → resume re-runs only multi-turn.
- Crash mid multi-turn **case** → the in-flight cell is incomplete and not
  appended (today's cell atomicity: append only after the full cell finishes).
  Re-running the cell redoes all 108 multi-turn cases for that cell. That is
  expensive but consistent with current runner semantics; case-level checkpoint
  for multi-turn is an optimization left for later if wall-clock demands it, and
  is not required to trust the science.

`read_completed` treats missing `arm` on old lines as `"raw"`.

### Ordering within a model load

For a fixed loaded model, run arms in order **raw → prompt_scaffolded →
multi_turn**. Raw first gives a control even if the run is cancelled early;
multi-turn last because it is the expensive arm. Exclusive-VRAM behaviour
unchanged: unload the model only after all requested arms for that model finish
(or after each model group, matching `execute_plan` today).

### Client / HTTP boundary

All turns go through `OpenAIClient`. No second HTTP stack. Multi-turn history is
pure data until `client.chat` builds the payload. Tool/web-search rejection
(`assert_request_is_tool_free`) runs on every request, including turns 2 and 3.

---

## 5. Reporting

### What `scripts/analyze_fleet.py` gains

A new section, emitted when the run directory contains more than one `arm` value
(or when `--arms-report` is passed):

1. **Per-model arm quality** — raw / prompt_scaffolded / multi_turn overall
   quality for `code-gen`, nulls excluded, with n_scored / n_unscored.
2. **Delta table per model × dimension** — the primary artifact (sketch below).
3. **Failure-mode × delta cross-read** — for each model, dominant raw
   `failure_mode` read (existing `failure_mode_read`) beside mean deltas, so the
   D-2026-06-30c prediction is visible next to the outcome.
4. **Incomparable / unscored accounting** — counts so a thin paired-n is not
   mistaken for a precise delta.

Never a single headline "scaffolded +0.12." That number is exactly what the
roadmap forbids: it hides the capability-gap vs working-memory split.

### Classification rules (per model × dimension)

Let `raw` and `arm` be means over paired comparable cases; `floor` = 0.10
(near-floor band); `eps` = 0.05 (flat band — small enough to ignore noise,
large enough to not call every ±0.02 a recovery).

| Condition | `read` | Meaning for Baton |
|---|---|---|
| `delta` is None or `n_paired` < 3 | `insufficient_pairs` | do not route on this cell |
| `delta > eps` | `scaffolding_recovers` | structure buys capability on this dimension |
| `delta` in `[-eps, eps]` AND `raw <= floor` | `not_offload_candidate` | flat **and** already near floor — scaffolding did not help a weak raw; not an offload target |
| `delta` in `[-eps, eps]` AND `raw > floor` | `flat_already_capable` | already works raw; scaffolding unnecessary (cost without gain) |
| `delta < -eps` | report as negative delta with the same bands | scaffolding hurt; note and do not auto-apply |

The critical distinction is **`not_offload_candidate` vs any positive delta**.
Both can look like "delta ~ 0" if someone only prints the mean delta; the
near-floor conjunction is what makes the first a routing refusal rather than a
null result.

### Sketch: delta table

```markdown
## Raw vs scaffolded deltas (code-gen)

Paired cases only. Unscored and asymmetrically truncated cases excluded from
deltas (never averaged as 0). eps=0.05, floor=0.10.

### prompt_scaffolded − raw

| model | dimension | raw | scaffolded | delta | n | read |
|---|---|---|---|---|---|---|
| qwen3.5-9b | bug-fix | 0.42 | 0.61 | +0.19 | 8 | scaffolding_recovers |
| qwen3.5-9b | test-authoring | 0.05 | 0.06 | +0.01 | 7 | not_offload_candidate |
| llama-3.2-1b | multi-function | 0.50 | 0.48 | -0.02 | 8 | flat_already_capable |
| … | … | … | … | … | … | … |

### multi_turn − raw

| model | dimension | raw | multi_turn | delta | n | read |
|---|---|---|---|---|---|---|
| … | … | … | … | … | … | … |

### Hypothesis check (D-2026-06-30c)

| model | raw failure read | mean Δ prompt_scaffolded | mean Δ multi_turn | consistent with prediction? |
|---|---|---|---|---|
| model-A | scaffolding candidate | +0.14 | +0.18 | yes — gains |
| model-B | capability gap | +0.02 | +0.01 | yes — flat |
| model-C | capability gap | +0.16 | +0.22 | **no — uniform gains; revisit D-2026-06-30c** |
```

"Consistent with prediction?" is a documentary aid, not a statistical test. With
8–12 cases per dimension the per-cell delta is noisy (§8); the table is honest
about n.

### Absolute arm tables still matter

Deltas without levels mislead: raw 0.90 → 0.93 is not the same decision as raw
0.20 → 0.45. The report keeps overall and per-tier quality per arm, then the
delta section. Token totals per arm sit beside quality so multi-turn's cost is
visible without opening `cells.jsonl`.

---

## 6. Cost

### Call arithmetic

| Arm | Calls per case | Calls per model (108 cases) |
|---|---|---|
| raw | 1 | 108 |
| prompt_scaffolded | 1 | 108 |
| multi_turn | 3 | 324 |
| **All three arms** | **5** | **540** |

For **4 models × 3 arms × 108 cases**:

- Total case-arm units: `4 × 108 × 3 = 1_296` scored case attempts  
- Total LLM calls: `4 × 540 = 2_160`  
- Of those calls, multi_turn is `4 × 324 = 1_296` (60% of all calls)

Raw-only control baseline for the same 4 models: `4 × 108 = 432` calls.
The full experiment is **5×** the call count of a raw-only 4-model code-gen
pass (540/108 = 5).

### Token arithmetic (budget and expected)

Per-call completion budget: **4096** (`batteries/code-gen.yaml`).

Worst-case completion tokens if every call saturated the budget:

- Per model, all arms: `540 × 4096 ≈ 2.21M` completion tokens  
- 4 models: `≈ 8.85M` completion tokens  

Observed raw code-gen on a small instruct model (fleet-0726b,
`llama-3.2-1b-instruct`, 108 cases): ~50.8k completion tokens total
(~470 completion tokens/case average), far below budget. Mid-size models that
think longer will sit higher; treat 470 as a lower reference and 1500–2500
completion tokens/case as a planning middle for models that use the budget more
heavily.

Middle-planning estimate at **~1500 completion tokens/call** average:

| Scope | Calls | Completion tokens (approx.) |
|---|---|---|
| 1 model, all arms | 540 | ~810k |
| 4 models, all arms | 2160 | ~3.2M |

Prompt tokens scale with arm: multi_turn turn 3 re-sends the task + restatement
+ implementation, so prompt tokens per case are substantially higher than raw.
Expect multi_turn prompt volume on the order of **3–6×** raw for the same case,
depending on how verbose the model is in turns 1–2.

### Wall-clock estimate

User-observed throughput band for a model that **fits in VRAM**: ~**40–60 tok/s**
completion. Generation time only (ignoring TTFT and prompt eval):

| Scenario | Seconds / call | Notes |
|---|---|---|
| 470 completion tokens @ 50 tok/s | ~9 s | small-model observed average |
| 1500 completion tokens @ 50 tok/s | ~30 s | mid planning |
| 4096 completion tokens @ 50 tok/s | ~82 s | full budget |
| 4096 @ 40 tok/s | ~102 s | full budget, slow end of band |

Add ~1–3 s TTFT and prompt processing per call (observed TTFT on box-b
code-gen cells ~2 s for a 1B model; larger models higher).

**Per model, all three arms**, mid planning (30 s generation + 3 s overhead ≈
33 s/call):

- 540 calls × 33 s ≈ **17_820 s ≈ 5.0 hours** per model  
- 4 models sequential on one box ≈ **20 hours**

**Per model, optimistic** (observed-small-model rate, ~12 s/call):

- 540 × 12 s ≈ **1.8 hours** per model  
- 4 models ≈ **7 hours**

**Per model, pessimistic** (often near budget, 90 s/call):

- 540 × 90 s ≈ **13.5 hours** per model  
- 4 models ≈ **54 hours** (~2.3 days) on one box

Multi-turn alone is 324/540 ≈ 60% of each model's call count; it dominates the
wall clock. Running multi_turn only on models that already look like scaffolding
candidates from a raw+prompt_scaffolded pass is a valid cost-reduction strategy
after the first full experiment, but the **first** run should complete all three
arms on the chosen four models so the hypothesis check is not confounded by
selection.

### Practical recommendation

- Pick **4 models** that span the failure-mode reads already seen on fleet runs
  (at least one `wrong_answer`-dominant scaffolding candidate, at least one
  `no_code_emitted`/`syntax_error`-dominant capability-gap model, plus two
  mid-pack). Do not burn 9 models × 3 arms on the first pass.
- Schedule on a **non-busy** headless box (resource-safety invariant); exclusive
  VRAM as today.
- Expect roughly **one evening to one long weekend** depending on which models
  fit cleanly in VRAM and how often they hit the 4096 ceiling.
- Record `prompt_tokens` / `completion_tokens` per cell (already on `Cell`) so
  the post-run cost section is measured, not re-estimated.

---

## 7. Testing

Pure-logic TDD is the default suite (`.venv/Scripts/python -m pytest`, no
network). Live multi-arm inference is opt-in and headless-box only — same rules
as the rest of Gauntlet.

### What gets unit-tested (no network)

| Area | Assertions |
|---|---|
| **Template application** | `apply_prompt_scaffold(prompt)` embeds the case text once, contains the step list and output contract, does not drop trailing content. Snapshot or substring tests on the full arm-2 string. |
| **Multi-turn message build** | `build_multi_turn_messages(prompt, replies_so_far)` produces the correct number of turns; turn 2/3 embed prior text; **no** path accepts or inserts hidden-test content, scores, or `failure_mode`. A dedicated test feeds a fake "tests_file body" into an optional kwarg channel and asserts it never appears in messages (API must not exist for that channel — the test documents the absence). |
| **Scoring arm invariance** | Same candidate source + same `tests_file` → identical `CaseResult.score` regardless of `arm` label. Arm is metadata; the scorer stays pure. |
| **Final-artifact-only** | Given three turn texts, only turn 3 is passed to `extract_code` / `score_case`. |
| **Truncation** | Existing `attribute_truncation` tests remain; add cases for multi-turn where turn 3 is truncated → unscored, and where turn 3 is fine but marked incomparable when raw was truncated. |
| **Paired delta math** | `compute_scaffolding_deltas(case_rows)` — null scores excluded; asymmetric truncation excluded; `delta = arm - raw`; classification bands (`scaffolding_recovers`, `not_offload_candidate`, …) match the table in §5; never coerces null to 0. |
| **Schema defaults** | `CaseResult` / `Cell` without `arm` validate as `arm="raw"`; old scorecard JSON fixtures still load. |
| **Resume keys** | `cell_key` includes `arm`; completed raw does not skip prompt_scaffolded. |
| **Analyze fleet** | Markdown section renders em dash for missing arms; delta table omits incomparable pairs; hypothesis-check rows built from failure_mode_read + mean delta. |

### What is not mocked as "the model"

Do not build a fake LLM to prove scaffolding helps. Harness tests use fixed
strings as model replies. Whether scaffolding helps is an empirical question
answered on box-b/box-c, not in CI.

### Live tests (opt-in)

At most a smoke: one model, one case, three arms, assert three `CaseResult`s
land with distinct `arm` values and that multi_turn made three HTTP calls
(transport mock or live headless). No gaming box.

---

## 8. Risks and what would invalidate the result

### Weak generic templates look like "scaffolding is useless"

If arm 2's wrapper is simply a bad prompt — too long, too rigid, fights the
model's chat template — then flat or negative deltas measure **template
quality**, not the selective-offload hypothesis. D-2026-06-30c already saw
over-prescriptive wording hurt a competent model on extract-json.

**Mitigation:** two scaffold arms, not one. If prompt_scaffolded is flat but
multi_turn gains for `wrong_answer` models, the hypothesis can still hold and
the single-shot wrapper is the weak link. If both arms are flat for those models,
that is stronger evidence for capability gap (or for "generic scaffolding does
not work on this fleet," which still informs Baton). Do not "fix" a null result
by hand-authoring per-case scaffolds; that changes the quantity under test.

### Arm 3's extra tokens confound the comparison

Multi-turn allows up to 3× completion budget and more wall clock. A gain on arm
3 might mean "more tokens / more chances to emit code," not "decomposition
helps working memory." A loss might mean truncation, not weaker reasoning.

**Mitigation:** report tokens and truncation counts beside deltas; exclude
asymmetric truncation from paired means; compare prompt_scaffolded (same call
count and budget as raw) as the primary clean test of structure-without-extra-
calls. Treat multi_turn as a stronger, costlier intervention whose gains must
exceed prompt_scaffolded enough to justify ~3× calls.

### Per-dimension n is small (8–12 cases)

With roughly 8–12 cases per dimension, a +0.15 delta can be a few cases flipping.
Dimension-level reads are directional, not precise effect sizes.

**Mitigation:** always print `n_paired`; require `n_paired >= 3` before a
routing label; prefer agreement across **multiple dimensions** and agreement
between the two scaffold arms before telling Baton to change behaviour. Overall
108-case paired delta is more stable and should be reported alongside, without
replacing the per-dimension table.

### Failure-mode dominance is measured on raw, then used to predict scaffold gains

If the raw failure-mode mix is itself noisy (or dominated by harness bugs — see
the `_strip_fences` / `extract_code` incident), the prediction groups are wrong
and the hypothesis check mis-fires.

**Mitigation:** use post-fix fleet failure modes; refuse to interpret a run
that shows elevated `harness_error`; keep extraction path identical across arms
so a harness bug does not hit one arm only.

### Contamination of multi-turn with grader signal

Any "helpful" future change that feeds "your code failed N asserts" into turn 3
invalidates the axis. The threat is internal (we build it later by accident),
not adversarial models.

**Mitigation:** tests that forbid hidden-test material in message builders; code
review checklist item; threat-model note if a repair-loop axis is ever added as
a separate experiment.

### Resume redoes whole multi-turn cells

A crash at case 107/108 of multi_turn redoes ~5 hours. That does not invalidate
science but can cause operators to cancel runs and ship partial data.

**Mitigation:** run-id discipline and analyzer that tolerate missing arms;
optional later case-level checkpoint (out of scope for correctness of this
spec).

### Selection bias on the four models

Picking only models that "look interesting" can confirm whatever we already
believe.

**Mitigation:** pre-register the four models from fleet failure-mode reads
before looking at scaffolding deltas; include at least one predicted flat and
one predicted gain.

### What would fully invalidate a published delta table

- Different hidden tests or scorer versions across arms  
- Hidden-test or pass/fail leakage into multi-turn  
- Null scores averaged as 0 in deltas  
- Truncated multi-turn cases counted as model failures in the delta  
- Per-case hand-authored scaffolds presented as "what Baton can do"  
- A single aggregate delta without per-dimension and near-floor breakdown  

Any of these means the table should not be used for routing.

---

## 9. Open questions for Kevin

1. **Model roster for the first rvs run.** Proposal: four models spanning
   failure-mode reads from fleet-0726b (one clear scaffolding candidate, one
   clear capability-gap, two mid). Confirm names once that fleet finishes, or
   name them now if you already know which four matter for Baton.

2. **Floor and eps thresholds.** Spec uses `floor=0.10` and `eps=0.05` for
   `not_offload_candidate` vs `scaffolding_recovers`. Prefer different bands
   (e.g. floor 0.15, eps 0.08) before the first report freezes language Baton
   will read?

3. **Is prompt_scaffolded enough for v1, with multi_turn deferred?** Multi_turn
   is ~60% of the calls and the integrity footgun. Running raw +
   prompt_scaffolded first (~40% of full cost) still falsifies a large part of
   the hypothesis. Full three-arm remains the complete design; sequencing is a
   cost call.

4. **Client API shape.** Prefer `chat(messages: list[dict])` as the general form
   with single-prompt as a wrapper, or a dedicated `chat_turn(history, user)` to
   keep the simple path obvious? (Implementation detail, but it touches the only
   HTTP boundary.)

5. **Should deltas ever land in scorecard JSON**, or stay analyzer-only forever?
   Analyzer-only keeps the scorecard contract smaller; a `scaffolding_deltas[]`
   section helps Baton consume without re-implementing join logic.

6. **Expand beyond code-gen later?** Other batteries lack structured
   failure_mode and often use "Output ONLY …" prompts where a scaffold wrapper
   would fight the measurement. Confirm code-gen-only until a second battery
   gains failure modes.

7. **Negative deltas on competent models.** D-2026-06-30c saw a competent model
   drop when prompts got stricter. If gemma-class models lose points on
   prompt_scaffolded, is the default Baton policy "apply scaffold only when
   raw failure read is scaffolding_candidate," or "A/B in production"?

---

## Implementation sketch (non-normative order)

For the implementer, after sign-off:

1. Schema defaults (`arm`, `RunMeta.experiment`, `turn_metrics`, `incomparable`).  
2. Pure template + multi-turn message builders + delta math + tests (no network).  
3. `OpenAIClient` multi-message support + integrity check on full payload.  
4. `run_cell` / plan / resume arm dimension; CLI `--arms`.  
5. `analyze_fleet.py` delta section + classification.  
6. Live smoke on headless box; then the four-model rvs run.

No part of this order requires network until step 6. Steps 1–5 are cloud-safe
and should stay green on Windows and Linux (process teardown and paths remain
the existing cross-platform ones; this axis does not touch the sandbox).
