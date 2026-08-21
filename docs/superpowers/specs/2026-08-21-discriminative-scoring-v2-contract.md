# Discriminative Scoring v2 — multi-axis contract

**Status:** design draft — awaiting Kevin sign-off before items #3–5 proceed beyond pure algorithms.
**Roadmap item:** #2 of
[`2026-07-04-discriminative-scoring-v2-plan.md`](../plans/2026-07-04-discriminative-scoring-v2-plan.md).
**Gates:** raw-vs-scaffolded (#3), pipeline economics (#4), ToC scheduler (#5).
**Related:** [seed](../../2026-06-30-discriminative-scoring-v2-seed.md),
[RvS slice](./2026-07-26-raw-vs-scaffolded-design.md) (normative for #3 arms — reference only).

## 1. Stable fields (unchanged semantics)

Existing scorecards and Baton parsers ignoring unknown keys **must keep loading**:

| Model | Fields | Semantics |
|---|---|---|
| `RunMeta` | `id`, `date`, `gauntlet_version` | Run identity; no endpoint/IP leakage |
| `CaseResult` | `case_id`, `method`, `score`, `passed`, `detail`, `failure_mode`, `tier`, `dimension`, `integrity_violations` | Per-case outcome; `score=None` = unscored, never silently 0 |
| `Cell` | `model`, `target`, `box`, `context`, `capability`, `quality`, `pass_rate`, latency/token fields, `quality_by_tier`, `quality_by_dimension`, `failure_modes`, `integrity` | One completed model×capability run; `quality` is arm-local when arms exist |
| `ContextDepth` | `model`, `advertised`, `effective_90pct` | Context-window probe |
| `BaselineGap` | `capability`, `local_champion`, `frontier`, `gap` | Local vs frontier delta |
| `Scorecard` | `run`, `cells[]`, `context_depth[]`, `baseline_gaps[]` | Canonical JSON contract |

**Invariants:** no `base_url`/IP, null ≠ 0, integrity on cells, `quality_by_dimension` is primary routing axis.

## 2. Additive extensions

All new fields are **optional with defaults**. Missing field ⇒ legacy single-arm raw run.

### 2a. Raw-vs-scaffolded (item #3)

Arm templates, comparability, classification: [`2026-07-26-raw-vs-scaffolded-design.md`](./2026-07-26-raw-vs-scaffolded-design.md). Contract pins cross-axis shape only:

**Per-record tags**

```python
# CaseResult + Cell (default "raw")
arm: Literal["raw", "prompt_scaffolded", "multi_turn"] = "raw"
incomparable: bool = False          # CaseResult only — asymmetric truncation
turn_metrics: list[dict] | None     # CaseResult, multi_turn only

# RunMeta
experiment: str | None = None       # e.g. "raw-vs-scaffolded"
arms: list[str] | None = None
```

**Cell/resume key:** `(target, model, context, capability, arm)`. No `delta` on `Cell` — derived from paired cells/`cases.jsonl`. Optional top-level summary:

```python
class ScaffoldingDelta(BaseModel):
    model: str
    capability: str
    dimension: str                    # or "*"
    arm: Literal["prompt_scaffolded", "multi_turn"]
    raw_quality: float | None
    arm_quality: float | None
    delta: float | None               # arm - raw; None if unpaired
    n_paired: int
    n_excluded_unscored: int
    n_excluded_incomparable: int
    read: Literal[
        "scaffolding_recovers", "not_offload_candidate",
        "flat_already_capable", "insufficient_pairs",
    ]

# Scorecard (optional)
scaffolding_deltas: list[ScaffoldingDelta] = []
```

### 2b. Pipeline economics (item #4)

A **scoring mode**, not a per-case method swap. Represents net **premium-equivalent token cost** to reach a **verified-correct** finish across a cheap→premium handoff.

```python
class PipelineLeg(BaseModel):
    role: Literal["local", "frontier"]
    model: str                        # local id or frontier alias (e.g. "opus")
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    premium_equivalent_tokens: float | None = None  # normalized to frontier $/tok

class PipelineEconomicsResult(BaseModel):
    pipeline_id: str                  # e.g. "comprehension-tax", "spec-handoff"
    capability: str
    case_id: str | None = None        # None = battery-level aggregate
    local_model: str
    frontier_model: str
    legs: list[PipelineLeg]
    total_premium_equivalent_tokens: float | None
    verified_correct: bool | None     # None = could not verify
    verification_method: str          # scorer/judge that judged final artifact
    baseline_frontier_only_tokens: float | None  # same task, frontier solo
    net_savings_ratio: float | None   # 1 - (pipeline/frontier_only); None if either missing

# Scorecard (optional)
pipeline_economics: list[PipelineEconomicsResult] = []
```

**Verified-correct:** final artifact via existing deterministic/judge scorers; no human. Unscored ⇒ excluded from savings. **v1 pipeline_ids:** `comprehension-tax`, `spec-handoff` (prompts/cases = item #4 impl).

### 2c. ToC placement hints (item #5)

Pure scheduling output attached to a run plan or post-run scorecard. Does **not** mutate `Cell.quality`.

```python
class BoxResource(BaseModel):
    box_id: str
    hardware: str
    vram_gb: float | None = None
    busy: bool = False
    bottleneck_rank: int | None = None   # 1 = system constraint

class PlacementHint(BaseModel):
    target: str | None
    model: str
    context: int
    capability: str
    arm: str = "raw"
    recommended_box_id: str
    critical_path: bool = False
    parallel_group: str | None = None    # cells with same group may overlap
    rationale: str = ""                  # e.g. "heavy+non-critical → strong box"

class SequenceHints(BaseModel):
    boxes: list[BoxResource] = []
    placements: list[PlacementHint] = []
    estimated_wall_clock_s: float | None = None

# Scorecard or sidecar meta (optional)
sequence_hints: SequenceHints | None = None
```

Hints are advisory until multi-box validation (#5).

## 3. Baton consumption — routing brief shape

Derived `routing-brief/v2` JSON (Gauntlet post-run or Baton-reconstructed from scorecard + fleet report):

```json
{
  "schema_version": "routing-brief/v2",
  "source_run_id": "fleet-0726",
  "axes_present": ["raw", "scaffolding", "pipeline_economics", "sequence_hints"],
  "routes": [{
    "capability": "code-gen", "dimension": "bug-fix", "local_model": "qwen3.5-9b",
    "raw_quality": 0.42, "failure_mode_read": "scaffolding_candidate",
    "scaffolding": {"delta": 0.19, "read": "scaffolding_recovers", "n_paired": 8},
    "pipeline_economics": {"comprehension-tax": {"net_savings_ratio": 0.35}},
    "offload_decision": "selective"
  }],
  "champions": {"code-gen": "model-id"}, "placement": {}, "caveats": []
}
```

**Baton read rules (normative):**

| Signal | Route when | Refuse when |
|---|---|---|
| Raw `quality_by_dimension` | champion pick per dimension | any cell has unscored majority |
| `ScaffoldingDelta.read` | apply scaffold only on `scaffolding_recovers` | `not_offload_candidate`, `insufficient_pairs` |
| `failure_modes` dominance | predict scaffold expectation (D-2026-06-30c) | `capability gap` + flat delta |
| `PipelineEconomicsResult.net_savings_ratio` | pipeline beats frontier-only | `verified_correct` false/null |
| `PlacementHint` | parallel cheap caps on weak box | box `busy` or hints absent |

Never collapse axes into one headline. Fall back to raw-only when an axis is absent.

## 4. Open questions (Kevin sign-off)

1. **Precomputed vs analyzer-only deltas** — Should `scaffolding_deltas[]` live in scorecard JSON, or stay Markdown/analyzer-only? (RvS spec §9.5.)
2. **Pipeline economics case scope** — Battery-wide aggregates only, or per-case rows for comprehension-tax? Per-case explodes frontier API cost.
3. **Frontier model alias & pricing table** — Which frontier legs (Opus/Sonnet/Haiku) and where premium-equivalent normalization lives (Gauntlet vs Baton).
4. **Routing brief emitter** — Gauntlet writes `routing-brief.json` beside scorecard, or Baton derives from raw JSON + fleet report?
5. **ToC hints on scorecard vs plan sidecar** — Same run directory as `cells.jsonl`, or separate `plan.json` consumed only by Gauntlet CLI?
6. **Threshold constants** — Confirm `floor=0.10`, `eps=0.05` for scaffold reads before Baton locks policy language.
7. **Multi-arm scope** — Code-gen only for v1, or expansion criteria for a second battery?

## 5. Implementation gate

| Item | Allowed before sign-off | Blocked until sign-off |
|---|---|---|
| #1 code-exec | ✅ shipped | — |
| #3 raw-vs-scaffolded | Pure template/delta math/tests, schema defaults | Live multi-arm runs, `--arms` CLI |
| #4 pipeline economics | Cost math unit tests, stub record writers | Frontier API handoff runs |
| #5 ToC scheduler | Placement algorithm unit tests | End-to-end multi-box validation |

**Sign-off:** approve §2–§3; resolve §4.1–§4.4 (delta storage, pipeline scope, frontier alias, brief emitter). Thresholds (#4.6) may follow first RvS report.
