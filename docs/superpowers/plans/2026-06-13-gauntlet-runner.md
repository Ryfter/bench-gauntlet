# Gauntlet Runner Implementation Plan (Plan 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the execution engine — a pure sequencer that orders the work matrix (load-profile-outer, busy guard, VRAM tight/broad classes), a resumable runner that fires cases against live models and checkpoints each cell to `cells.jsonl`, and a `gauntlet run` CLI command.

**Architecture:** `sequencer.py` is pure (config + batteries + optional footprints → ordered load groups + deferred cells). `runner.py` orchestrates: per load group it drives the `OpenAIClient` (the sole HTTP boundary) through each cell's cases, scores them with the existing `scoring` package (deterministic + judge), aggregates via `scorecard.aggregate_cell`, and appends to an append-only `cells.jsonl`. `--resume` reads completed cells and skips them. The final scorecard is assembled from `cells.jsonl` using the Plan 2 emit path. The run *never aborts* — unreachable/OOM/busy become typed cell outcomes.

**Tech Stack:** Python 3.12+, httpx (via existing `OpenAIClient`), pydantic v2, Typer. Pure-logic TDD for the sequencer and checkpoint I/O; live end-to-end smoke on box-b (`gemma3:1b`) only — **never box-a while gaming.**

---

## Phasing & boundaries

- **Phase 5 (Tasks 3.1–3.3):** `gauntlet/sequencer.py` — pure. No network.
- **Phase 6 (Tasks 3.4–3.7):** `gauntlet/runner.py` — checkpoint I/O (pure file ops) + cell execution (driven through `httpx.MockTransport` in tests) + scorecard assembly.
- **Phase 7 (Task 3.8):** `gauntlet run` CLI command + a live smoke test marked `live`.

**Invariants carried forward:** the `OpenAIClient` is the only thing that does HTTP; the live test suite never includes box-a; a busy box defers (skip, not error); a missing/ineligible judge marks cases `unscored`, never silently 0.

---

## File Structure

- Create: `gauntlet/sequencer.py` — pure work-matrix planner (`PlannedCell`, `LoadGroup`, `SequencePlan`, `build_cells`, `estimate_footprint_gb`, `plan_run`, `model_family`).
- Create: `gauntlet/runner.py` — `RunPaths`, checkpoint I/O (`append_cell`, `read_completed`, `write_meta`, `cell_key`), `load_prompt`, `run_cell`, `execute_plan`, `assemble_scorecard`.
- Modify: `gauntlet/cli.py` — add the `run` command.
- Test: `tests/test_sequencer.py`, `tests/test_runner_checkpoint.py`, `tests/test_runner_cell.py`, `tests/test_runner_execute.py`, `tests/test_runner_assemble.py`, `tests/test_cli_run.py`, `tests/live/test_live_run.py`.

---

## Task 3.1: Work matrix — `PlannedCell`, `model_family`, `build_cells`

**Files:**
- Create: `gauntlet/sequencer.py`
- Test: `tests/test_sequencer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sequencer.py
from gauntlet.battery import Battery, Case
from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
from gauntlet.sequencer import build_cells, model_family


def _cfg():
    return GauntletConfig(
        targets=[Target(name="box-b", base_url="http://w:1", enrich="ollama", box="box-b")],
        boxes=[Box(id="box-b", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="tight")],
        models=[
            ModelProfile(target="box-b", id="gemma3:1b", context=4096),
            ModelProfile(target="box-b", id="qwen2.5:7b", context=8192),
        ],
        keep_list=["*embed*"],
    )


def _batteries():
    return [
        Battery(capability="commit-msg", context_floor=0,
                cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p1.txt")]),
        Battery(capability="long-ctx", context_floor=8000,
                cases=[Case(id="c2", scoring="exact", expect="ok", prompt_file="p2.txt")]),
    ]


def test_model_family_splits_on_colon():
    assert model_family("gemma3:1b") == "gemma3"
    assert model_family("dolphin3:8b") == "dolphin3"
    assert model_family("plain-model") == "plain-model"


def test_build_cells_applies_context_floor():
    cells = build_cells(_cfg(), _batteries())
    # gemma3@4096 -> only commit-msg (long-ctx floor 8000 excludes it)
    gemma = [c for c in cells if c.model == "gemma3:1b"]
    assert {c.capability for c in gemma} == {"commit-msg"}
    # qwen@8192 -> both batteries apply
    qwen = [c for c in cells if c.model == "qwen2.5:7b"]
    assert {c.capability for c in qwen} == {"commit-msg", "long-ctx"}


def test_build_cells_resolves_box_label():
    cells = build_cells(_cfg(), _batteries())
    assert all(c.box_hardware == "RTX 2070 Super laptop" for c in cells)
    assert all(c.box_id == "box-b" for c in cells)


def test_build_cells_excludes_keep_list_unless_named():
    cfg = _cfg()
    cfg.models.append(ModelProfile(target="box-b", id="nomic-embed-text", context=2048))
    # keep_list glob *embed* matches -> excluded by default
    assert not any(c.model == "nomic-embed-text" for c in build_cells(cfg, _batteries()))
    # named explicitly -> included
    cells = build_cells(cfg, _batteries(), only_models=["nomic-embed-text"])
    assert all(c.model == "nomic-embed-text" for c in cells)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_sequencer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.sequencer'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/sequencer.py
"""Pure run planner. Turns config + batteries (+ optional model footprints from
metadata-only enrichment) into an ordered list of load groups plus a deferred
list. No network, no model loads — deterministic and unit-testable.

Ordering rule (design C): the load profile (model @ context) is the OUTER loop and
batteries the INNER loop, so each profile loads once and runs all its batteries
before the next profile. Busy boxes defer; broad models run exclusively; tight
models co-reside up to the box VRAM budget."""
from __future__ import annotations

from pydantic import BaseModel, Field

from gauntlet.battery import Battery
from gauntlet.config import GauntletConfig


def model_family(model_id: str) -> str:
    """Coarse family key for judge same-family avoidance: the segment before ':'."""
    return model_id.split(":", 1)[0].lower()


class PlannedCell(BaseModel):
    target: str
    model: str
    context: int
    capability: str
    box_id: str | None
    box_hardware: str
    deferred: bool = False
    defer_reason: str = ""


def build_cells(
    config: GauntletConfig,
    batteries: list[Battery],
    only_models: list[str] | None = None,
) -> list[PlannedCell]:
    """The work matrix: profile × applicable batteries. keep_list models are
    excluded unless explicitly named in `only_models`. Profile order is preserved
    (it drives the outer loop)."""
    cells: list[PlannedCell] = []
    for profile in config.models:
        if only_models is not None and profile.id not in only_models:
            continue
        if only_models is None and config.is_kept(profile.id):
            continue
        box = config.box_for_target(profile.target)
        for battery in batteries:
            if not battery.applies_to(profile.context):
                continue
            cells.append(PlannedCell(
                target=profile.target, model=profile.id, context=profile.context,
                capability=battery.capability,
                box_id=box.id if box else None,
                box_hardware=box.hardware if box else "(no box)",
            ))
    return cells
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_sequencer.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/sequencer.py tests/test_sequencer.py
git commit -m "feat: sequencer work matrix (build_cells, context_floor, keep_list, model_family)"
```

---

## Task 3.2: VRAM footprint estimate — `estimate_footprint_gb`

**Files:**
- Modify: `gauntlet/sequencer.py`
- Test: `tests/test_sequencer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_sequencer.py
from gauntlet.sequencer import estimate_footprint_gb


def test_estimate_footprint_unknown_size_is_none():
    assert estimate_footprint_gb(None, 4096) is None


def test_estimate_footprint_weights_plus_kv():
    # 4 GB weights + 8192 tokens * 100_000 B/token KV ~= 4.82 GB
    gb = estimate_footprint_gb(4_000_000_000, 8192)
    assert abs(gb - 4.82) < 0.05
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_sequencer.py -k footprint -v`
Expected: FAIL — `cannot import name 'estimate_footprint_gb'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to gauntlet/sequencer.py (after model_family)

# Coarse KV-cache cost per context token (fp16, conservative). This is a SAFETY
# estimate for co-residency packing, not an exact accounting — when in doubt the
# planner falls back to exclusive loading.
_KV_BYTES_PER_TOKEN = 100_000


def estimate_footprint_gb(size_bytes: int | None, context: int) -> float | None:
    """Approx VRAM footprint in GB = weights (enrichment size_bytes) + KV(context).
    Returns None when the weight size is unknown (caller treats that as exclusive)."""
    if size_bytes is None:
        return None
    return (size_bytes + context * _KV_BYTES_PER_TOKEN) / 1e9
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_sequencer.py -k footprint -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/sequencer.py tests/test_sequencer.py
git commit -m "feat: estimate_footprint_gb (weights + coarse KV; None when size unknown)"
```

---

## Task 3.3: Load groups — `plan_run` (busy guard, broad-exclusive, tight-packing)

**Files:**
- Modify: `gauntlet/sequencer.py`
- Test: `tests/test_sequencer.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_sequencer.py
from gauntlet.sequencer import plan_run


def test_plan_run_broad_box_one_exclusive_group_per_profile():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="RTX 5090 desktop", vram_gb=32, usage_class="broad")],
        models=[ModelProfile(target="t", id="m1", context=4096),
                ModelProfile(target="t", id="m2", context=4096)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    plan = plan_run(cfg, bats)
    assert len(plan.groups) == 2
    assert all(g.exclusive for g in plan.groups)
    assert plan.deferred == []


def test_plan_run_busy_box_defers_all_its_cells():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="RTX 5090 desktop", vram_gb=32, busy=True)],
        models=[ModelProfile(target="t", id="m1", context=4096)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    plan = plan_run(cfg, bats)
    assert plan.groups == []
    assert len(plan.deferred) == 1
    assert plan.deferred[0].deferred is True
    assert "busy" in plan.deferred[0].defer_reason


def test_plan_run_tight_box_packs_to_vram_budget():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="RTX 2070 Super laptop", vram_gb=24, usage_class="tight")],
        models=[ModelProfile(target="t", id="a", context=2048),
                ModelProfile(target="t", id="b", context=2048),
                ModelProfile(target="t", id="c", context=2048)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    footprints = {"a": 3_000_000_000, "b": 4_000_000_000, "c": 20_000_000_000}
    plan = plan_run(cfg, bats, footprints=footprints)
    # a(~3.2) + b(~4.2) = ~7.4 <= 24 co-reside; c(~20.2) pushes a 2nd group
    assert len(plan.groups) == 2
    assert {p[1] for p in plan.groups[0].profiles} == {"a", "b"}
    assert {p[1] for p in plan.groups[1].profiles} == {"c"}


def test_plan_run_tight_unknown_footprint_is_exclusive():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="laptop", vram_gb=8, usage_class="tight")],
        models=[ModelProfile(target="t", id="a", context=2048),
                ModelProfile(target="t", id="b", context=2048)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    plan = plan_run(cfg, bats)  # no footprints -> unknown -> exclusive
    assert len(plan.groups) == 2
    assert all(g.exclusive for g in plan.groups)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_sequencer.py -k plan_run -v`
Expected: FAIL — `cannot import name 'plan_run'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to gauntlet/sequencer.py

class LoadGroup(BaseModel):
    """A set of profiles that may be resident on a box at the same time, with all
    their cells. `exclusive` groups hold exactly one profile (unload before next)."""
    box_id: str | None
    box_hardware: str
    exclusive: bool
    profiles: list[tuple[str, str, int]] = Field(default_factory=list)  # (target, model, context)
    cells: list[PlannedCell] = Field(default_factory=list)


class SequencePlan(BaseModel):
    groups: list[LoadGroup] = Field(default_factory=list)
    deferred: list[PlannedCell] = Field(default_factory=list)


def _profile_key(cell: PlannedCell) -> tuple[str, str, int]:
    return (cell.target, cell.model, cell.context)


def plan_run(
    config: GauntletConfig,
    batteries: list[Battery],
    footprints: dict[str, int] | None = None,
    only_models: list[str] | None = None,
) -> SequencePlan:
    """Order cells into load groups (profile-outer). Busy boxes defer; broad and
    unknown-footprint profiles get exclusive groups; tight profiles with known
    footprints greedily co-reside up to the box VRAM budget."""
    footprints = footprints or {}
    cells = build_cells(config, batteries, only_models=only_models)

    # Group cells by load profile, preserving first-seen (config) order.
    by_profile: dict[tuple[str, str, int], list[PlannedCell]] = {}
    for cell in cells:
        by_profile.setdefault(_profile_key(cell), []).append(cell)

    plan = SequencePlan()
    open_tight: dict[str, LoadGroup] = {}   # box_id -> current packing group
    open_tight_used: dict[str, float] = {}  # box_id -> GB used in current group

    for key, profile_cells in by_profile.items():
        target, model, context = key
        box = config.box_for_target(target)

        if box is not None and box.busy:
            for c in profile_cells:
                c.deferred = True
                c.defer_reason = f"box {box.id} busy"
                plan.deferred.append(c)
            continue

        footprint = estimate_footprint_gb(footprints.get(model), context)
        tight = box is not None and box.usage_class == "tight" and footprint is not None

        if not tight:
            plan.groups.append(LoadGroup(
                box_id=box.id if box else None,
                box_hardware=box.hardware if box else "(no box)",
                exclusive=True, profiles=[key], cells=list(profile_cells),
            ))
            continue

        # tight + known footprint: pack into the box's open group if it fits.
        group = open_tight.get(box.id)
        if group is None or open_tight_used[box.id] + footprint > box.vram_gb:
            group = LoadGroup(box_id=box.id, box_hardware=box.hardware, exclusive=False)
            plan.groups.append(group)
            open_tight[box.id] = group
            open_tight_used[box.id] = 0.0
        group.profiles.append(key)
        group.cells.extend(profile_cells)
        open_tight_used[box.id] += footprint

    return plan
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_sequencer.py -v`
Expected: PASS (all sequencer tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/sequencer.py tests/test_sequencer.py
git commit -m "feat: plan_run load groups (busy defer, broad-exclusive, tight VRAM packing)"
```

---

## Task 3.4: Run directory & checkpoint I/O

**Files:**
- Create: `gauntlet/runner.py`
- Test: `tests/test_runner_checkpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner_checkpoint.py
from gauntlet.models import Cell, RunMeta
from gauntlet.runner import RunPaths, append_cell, cell_key, read_completed, write_meta


def _cell(cap):
    return Cell(model="gemma3:1b", target="box-b", box="RTX 2070 Super laptop",
                context=4096, capability=cap, quality=1.0, pass_rate=1.0, cases=1)


def test_cell_key_identity():
    assert cell_key(_cell("commit-msg")) == ("box-b", "gemma3:1b", 4096, "commit-msg")


def test_append_and_read_completed_roundtrip(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    append_cell(paths, _cell("extract-json"))
    done = read_completed(paths)
    assert done == {
        ("box-b", "gemma3:1b", 4096, "commit-msg"),
        ("box-b", "gemma3:1b", 4096, "extract-json"),
    }


def test_read_completed_missing_file_is_empty(tmp_path):
    paths = RunPaths(tmp_path / "nope")
    assert read_completed(paths) == set()


def test_write_meta_writes_json(tmp_path):
    paths = RunPaths(tmp_path / "run-2")
    paths.ensure()
    write_meta(paths, RunMeta(id="run-2", date="2026-06-13", gauntlet_version="0.1.0"))
    assert paths.meta.exists()
    assert "run-2" in paths.meta.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_runner_checkpoint.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.runner'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/runner.py
"""Run orchestration. Owns a run directory (`scorecards/<run-id>/`) with an
append-only `cells.jsonl` (one completed Cell per line) + `meta.json`. Drives the
OpenAIClient through each cell's cases, scores with the `scoring` package, and
checkpoints immediately so `--resume` loses at most the in-flight cell. The run
NEVER aborts: unreachable / load-fail / busy become typed cell outcomes."""
from __future__ import annotations

from pathlib import Path

from gauntlet.models import Cell, RunMeta


class RunPaths:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.cells = self.root / "cells.jsonl"
        self.meta = self.root / "meta.json"

    def ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def cell_key(cell: Cell) -> tuple[str | None, str, int, str]:
    return (cell.target, cell.model, cell.context, cell.capability)


def append_cell(paths: RunPaths, cell: Cell) -> None:
    with paths.cells.open("a", encoding="utf-8") as fh:
        fh.write(cell.model_dump_json() + "\n")


def read_completed(paths: RunPaths) -> set[tuple]:
    if not paths.cells.exists():
        return set()
    done: set[tuple] = set()
    for line in paths.cells.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            done.add(cell_key(Cell.model_validate_json(line)))
    return done


def write_meta(paths: RunPaths, run: RunMeta) -> None:
    paths.meta.write_text(run.model_dump_json(indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_runner_checkpoint.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/runner.py tests/test_runner_checkpoint.py
git commit -m "feat: runner checkpoint I/O (RunPaths, append/read cells.jsonl, write_meta)"
```

---

## Task 3.5: Per-cell execution — `load_prompt`, `run_cell`

**Files:**
- Modify: `gauntlet/runner.py`
- Test: `tests/test_runner_cell.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner_cell.py
import httpx

from gauntlet.battery import Battery, Case
from gauntlet.client import OpenAIClient
from gauntlet.runner import run_cell


def _client(reply_text):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": reply_text}}],
            "usage": {"completion_tokens": 7},
        })
    return OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))


def test_run_cell_scores_deterministic_cases(tmp_path):
    (tmp_path / "p.txt").write_text("write a commit message", encoding="utf-8")
    battery = Battery(capability="commit-msg",
                      cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p.txt")])
    cell = run_cell(_client("feat: add the thing"), model="gemma3:1b", target="box-b",
                    box="RTX 2070 Super laptop", context=4096, battery=battery, base_dir=tmp_path)
    assert cell.capability == "commit-msg"
    assert cell.quality == 1.0
    assert cell.pass_rate == 1.0
    assert cell.cases == 1
    assert cell.errors == 0
    assert cell.tokens_per_s is not None and cell.tokens_per_s > 0


def test_run_cell_unreachable_marks_errored_cell(tmp_path):
    (tmp_path / "p.txt").write_text("hi", encoding="utf-8")
    def handler(request):
        raise httpx.ConnectError("refused")
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))
    battery = Battery(capability="commit-msg",
                      cases=[Case(id="c1", scoring="exact", expect="x", prompt_file="p.txt")])
    cell = run_cell(client, model="gemma3:1b", target="box-b", box="laptop",
                    context=4096, battery=battery, base_dir=tmp_path)
    assert cell.errors == 1
    assert cell.quality is None          # nothing scored
    assert cell.cases == 1


def test_run_cell_judge_uses_eligible_pool(tmp_path):
    (tmp_path / "p.txt").write_text("summarize", encoding="utf-8")
    # model under test is gemma3; judge pool offers a different family -> judged.
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        if "strict grader" in body:
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"score":0.8,"passed":true}'}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "some summary"}}],
                                         "usage": {"completion_tokens": 5}})
    client = OpenAIClient(base_url="http://w:1", transport=httpx.MockTransport(handler))
    battery = Battery(capability="summarize",
                      cases=[Case(id="c1", scoring="judge", rubric="grade it", prompt_file="p.txt")])
    cell = run_cell(client, model="gemma3:1b", target="box-b", box="laptop", context=4096,
                    battery=battery, base_dir=tmp_path, judge_pool=[("dolphin3:8b", "dolphin3")])
    assert cell.quality == 0.8
    assert cell.judge == "dolphin3:8b"


def test_run_cell_no_eligible_judge_marks_unscored(tmp_path):
    (tmp_path / "p.txt").write_text("summarize", encoding="utf-8")
    battery = Battery(capability="summarize",
                      cases=[Case(id="c1", scoring="judge", rubric="grade it", prompt_file="p.txt")])
    cell = run_cell(_client("some summary"), model="gemma3:1b", target="box-b", box="laptop",
                    context=4096, battery=battery, base_dir=tmp_path,
                    judge_pool=[("gemma3:27b", "gemma3")])  # same family only
    assert cell.quality is None          # unscored, never silently 0
    assert cell.pass_rate == 0.0
    assert cell.cases == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_runner_cell.py -v`
Expected: FAIL — `cannot import name 'run_cell'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to gauntlet/runner.py
import statistics
from typing import TYPE_CHECKING

from gauntlet import errors
from gauntlet.models import CaseResult
from gauntlet.scorecard import aggregate_cell
from gauntlet.scoring import NEEDS_JUDGE, score_case
from gauntlet.scoring.judge import score_with_judge, select_judge

if TYPE_CHECKING:
    from gauntlet.battery import Battery, Case
    from gauntlet.client import OpenAIClient


def load_prompt(case: "Case", base_dir) -> str:
    """Read the case prompt from disk. A case with no prompt_file has an empty prompt."""
    if not case.prompt_file:
        return ""
    return (Path(base_dir) / case.prompt_file).read_text(encoding="utf-8")


def run_cell(
    client: "OpenAIClient",
    model: str,
    target: str | None,
    box: str,
    context: int,
    battery: "Battery",
    base_dir,
    judge_pool: list[tuple[str, str]] | None = None,
) -> Cell:
    """Fire every case of one battery against one loaded profile, score, and
    aggregate into a Cell. Per-case transport failures are counted as errors and
    never raised — the run must continue (design error taxonomy)."""
    from gauntlet.sequencer import model_family

    results: list[CaseResult] = []
    latencies: list[float] = []
    total_tokens = 0
    error_count = 0
    judge_used: str | None = None

    for case in battery.cases:
        prompt = load_prompt(case, base_dir)
        try:
            reply = client.chat(model=model, prompt=prompt)
        except errors.GauntletError:
            error_count += 1
            continue
        latencies.append(reply.latency_s)
        if reply.completion_tokens:
            total_tokens += reply.completion_tokens

        result = score_case(case, reply.text, base_dir=base_dir)
        if result is NEEDS_JUDGE:
            judge = select_judge(judge_pool or [], target_family=model_family(model))
            if judge is None:
                results.append(CaseResult(case_id=case.id, method="judge", score=None,
                                          passed=False, detail="unscored: no eligible judge"))
                continue
            judge_used = judge
            results.append(score_with_judge(client, judge_model=judge,
                                             rubric=case.rubric or "", output=reply.text,
                                             case_id=case.id))
        else:
            result.case_id = case.id
            results.append(result)

    p50 = statistics.median(latencies) if latencies else None
    total_latency = sum(latencies)
    tps = (total_tokens / total_latency) if total_tokens and total_latency else None

    cell = aggregate_cell(model=model, target=target, box=box, context=context,
                          capability=battery.capability, results=results,
                          latency_p50_s=p50, tokens_per_s=tps, errors=error_count)
    cell.judge = judge_used
    return cell
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_runner_cell.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/runner.py tests/test_runner_cell.py
git commit -m "feat: run_cell — fire cases, deterministic+judge scoring, metrics, error taxonomy"
```

---

## Task 3.6: Orchestration with resume — `execute_plan`

**Files:**
- Modify: `gauntlet/runner.py`
- Test: `tests/test_runner_execute.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner_execute.py
import httpx

from gauntlet.battery import Battery, Case
from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
from gauntlet.runner import RunPaths, execute_plan, read_completed


def _cfg():
    return GauntletConfig(
        targets=[Target(name="box-b", base_url="http://w:1", box="box-b")],
        boxes=[Box(id="box-b", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="broad")],
        models=[ModelProfile(target="box-b", id="gemma3:1b", context=4096)],
    )


def _batteries(tmp_path):
    (tmp_path / "p.txt").write_text("go", encoding="utf-8")
    return [Battery(capability="commit-msg",
                    cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p.txt")])]


def _client_factory(text):
    def make(base_url, api_key=None):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": text}}],
                                             "usage": {"completion_tokens": 4}})
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    return make


def test_execute_plan_runs_all_cells_and_checkpoints(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    cells = execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                         client_factory=_client_factory("feat: x"))
    assert len(cells) == 1
    assert cells[0].quality == 1.0
    # checkpoint written
    assert read_completed(paths) == {("box-b", "gemma3:1b", 4096, "commit-msg")}


def test_execute_plan_resume_skips_completed(tmp_path):
    paths = RunPaths(tmp_path / "run-2")
    # first run completes the only cell
    execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                 client_factory=_client_factory("feat: x"))
    # second run with a client that would FAIL if called — proves the cell is skipped
    def exploding_factory(base_url, api_key=None):
        def handler(request):
            raise AssertionError("should not be called on resume")
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    cells = execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                         client_factory=exploding_factory, resume=True)
    assert cells == []   # nothing left to do


def test_execute_plan_unreachable_target_continues(tmp_path):
    def dead_factory(base_url, api_key=None):
        def handler(request):
            raise httpx.ConnectError("refused")
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    paths = RunPaths(tmp_path / "run-3")
    cells = execute_plan(_cfg(), _batteries(tmp_path), paths, base_dir=tmp_path,
                         client_factory=dead_factory)
    assert len(cells) == 1
    assert cells[0].errors == 1     # errored, but run produced the cell and did not abort
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_runner_execute.py -v`
Expected: FAIL — `cannot import name 'execute_plan'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to gauntlet/runner.py
from gauntlet.sequencer import model_family as _model_family
from gauntlet.sequencer import plan_run


def _judge_pool_for(config, target_name: str) -> list[tuple[str, str]]:
    """Other models configured on the same target, as (model_id, family) — the
    candidate judges for a cell on that target (cross-target judging is future work)."""
    return [(p.id, _model_family(p.id)) for p in config.models if p.target == target_name]


def execute_plan(
    config,
    batteries,
    paths: RunPaths,
    base_dir,
    client_factory,
    footprints: dict[str, int] | None = None,
    only_models: list[str] | None = None,
    resume: bool = False,
) -> list[Cell]:
    """Drive the sequenced plan to completion. Opens one client per target (lazily,
    via client_factory), runs each cell, and appends it to cells.jsonl immediately.
    Deferred (busy) cells are skipped; nothing aborts the run."""
    paths.ensure()
    done = read_completed(paths) if resume else set()
    plan = plan_run(config, batteries, footprints=footprints, only_models=only_models)
    battery_by_cap = {b.capability: b for b in batteries}

    clients: dict[str, object] = {}
    produced: list[Cell] = []
    try:
        for group in plan.groups:
            for (target, model, context) in group.profiles:
                for cell_plan in group.cells:
                    if (cell_plan.target, cell_plan.model, cell_plan.context) != (target, model, context):
                        continue
                    key = (target, model, context, cell_plan.capability)
                    if key in done:
                        continue
                    tgt = config.target_by_name(target)
                    client = clients.get(target)
                    if client is None:
                        client = client_factory(tgt.base_url)
                        clients[target] = client
                    cell = run_cell(client, model=model, target=target,
                                    box=cell_plan.box_hardware, context=context,
                                    battery=battery_by_cap[cell_plan.capability], base_dir=base_dir,
                                    judge_pool=_judge_pool_for(config, target))
                    append_cell(paths, cell)
                    done.add(key)
                    produced.append(cell)
    finally:
        for client in clients.values():
            client.close()
    return produced
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_runner_execute.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/runner.py tests/test_runner_execute.py
git commit -m "feat: execute_plan — sequenced run, per-target clients, resume skip, no-abort"
```

---

## Task 3.7: Assemble final scorecard — `assemble_scorecard`

**Files:**
- Modify: `gauntlet/runner.py`
- Test: `tests/test_runner_assemble.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_runner_assemble.py
from gauntlet.models import Cell, RunMeta
from gauntlet.runner import RunPaths, append_cell, assemble_scorecard


def _cell(cap):
    return Cell(model="gemma3:1b", target="box-b", box="RTX 2070 Super laptop",
                context=4096, capability=cap, quality=1.0, pass_rate=1.0, cases=1)


def test_assemble_scorecard_reads_all_cells(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    append_cell(paths, _cell("extract-json"))
    run = RunMeta(id="run-1", date="2026-06-13", gauntlet_version="0.1.0")
    sc = assemble_scorecard(run, paths)
    assert sc.run.id == "run-1"
    assert {c.capability for c in sc.cells} == {"commit-msg", "extract-json"}
    assert sc.context_depth == []
    assert sc.baseline_gaps == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_runner_assemble.py -v`
Expected: FAIL — `cannot import name 'assemble_scorecard'`

- [ ] **Step 3: Write minimal implementation**

```python
# add to gauntlet/runner.py
from gauntlet.models import Scorecard


def assemble_scorecard(run: RunMeta, paths: RunPaths) -> Scorecard:
    """Build the final Scorecard from the append-only cells.jsonl. context_depth and
    baseline_gaps stay empty until Plan 4 fills them."""
    cells: list[Cell] = []
    if paths.cells.exists():
        for line in paths.cells.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                cells.append(Cell.model_validate_json(line))
    return Scorecard(run=run, cells=cells)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_runner_assemble.py -v`
Expected: PASS (1 test)

- [ ] **Step 5: Commit**

```bash
git add gauntlet/runner.py tests/test_runner_assemble.py
git commit -m "feat: assemble_scorecard from cells.jsonl (context_depth/baseline_gaps deferred)"
```

---

## Task 3.8: `gauntlet run` CLI command

**Files:**
- Modify: `gauntlet/cli.py`
- Test: `tests/test_cli_run.py`, `tests/live/test_live_run.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_run.py
import json

from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def _write_config(tmp_path):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        "  - {name: box-b, base_url: 'http://127.0.0.1:65000', box: box-b}\n"
        "boxes:\n"
        "  - {id: box-b, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: broad}\n"
        "models:\n"
        "  - {target: box-b, id: 'gemma3:1b', context: 4096}\n",
        encoding="utf-8",
    )
    return cfg


def _write_battery(tmp_path):
    bdir = tmp_path / "batteries"
    bdir.mkdir()
    (tmp_path / "p.txt").write_text("write a commit message", encoding="utf-8")
    (bdir / "commit.yaml").write_text(
        "capability: commit-msg\n"
        "context_floor: 0\n"
        "cases:\n"
        "  - {id: c1, scoring: conventional-commit, prompt_file: p.txt}\n",
        encoding="utf-8",
    )
    return bdir


def test_run_unreachable_target_writes_scorecard_and_does_not_crash(tmp_path):
    cfg = _write_config(tmp_path)
    bdir = _write_battery(tmp_path)
    out = tmp_path / "card.json"
    # 127.0.0.1:65000 is closed -> Unreachable -> errored cell, run still completes.
    result = runner.invoke(app, [
        "run", "--config", str(cfg), "--batteries", str(bdir),
        "--prompts", str(tmp_path), "--out", str(out), "--run-id", "test-run",
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run"]["id"] == "test-run"
    assert len(data["cells"]) == 1
    assert data["cells"][0]["errors"] == 1
```

```python
# tests/live/test_live_run.py
import os

import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("GAUNTLET_LIVE_BASE_URL"),
                    reason="set GAUNTLET_LIVE_BASE_URL to a box-b endpoint (never box-a while gaming)")
def test_live_run_smoke(tmp_path):
    """End-to-end on box-b with gemma3:1b. NEVER point this at box-a while gaming."""
    from gauntlet.battery import Battery, Case
    from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
    from gauntlet.runner import RunPaths, execute_plan

    base = os.environ["GAUNTLET_LIVE_BASE_URL"]
    cfg = GauntletConfig(
        targets=[Target(name="box-b", base_url=base, box="box-b")],
        boxes=[Box(id="box-b", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="broad")],
        models=[ModelProfile(target="box-b", id="gemma3:1b", context=4096)],
    )
    (tmp_path / "p.txt").write_text("Write a one-line conventional commit for adding a runner.",
                                    encoding="utf-8")
    bats = [Battery(capability="commit-msg",
                    cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p.txt")])]

    def factory(base_url, api_key=None):
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url)

    cells = execute_plan(cfg, bats, RunPaths(tmp_path / "run"), base_dir=tmp_path,
                         client_factory=factory)
    assert len(cells) == 1
    assert cells[0].cases == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_cli_run.py -v`
Expected: FAIL — `run` is not a command (`Error: No such command 'run'`)

- [ ] **Step 3: Write minimal implementation**

```python
# add to gauntlet/cli.py (new command, after `report`)
@app.command()
def run(
    config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml"),
    batteries: str = typer.Option("batteries", "--batteries", help="Directory of battery YAML files"),
    prompts: str = typer.Option(".", "--prompts", help="Base dir for case prompt_file/schema_file paths"),
    out: str = typer.Option(None, "--out", help="Write the final scorecard JSON here"),
    models: list[str] = typer.Option(None, "--model", help="Only run these model ids (repeatable; overrides keep_list)"),
    resume_id: str = typer.Option(None, "--resume", help="Resume an existing run id (skip completed cells)"),
    run_id: str = typer.Option(None, "--run-id", help="Run id (default: timestamp)"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels in the written scorecard"),
) -> None:
    """Run the gauntlet: sequence the work matrix and execute it against live targets."""
    from datetime import datetime, timezone
    from pathlib import Path

    from gauntlet import __version__
    from gauntlet.battery import load_batteries
    from gauntlet.client import OpenAIClient
    from gauntlet.config import load_config
    from gauntlet.models import RunMeta
    from gauntlet.runner import RunPaths, assemble_scorecard, execute_plan, write_meta
    from gauntlet.scorecard import render_markdown, write_json

    cfg = load_config(config)
    bats = load_batteries(batteries)
    if not bats:
        typer.echo(f"No batteries found in {batteries}/ — nothing to run.")
        raise typer.Exit(code=0)

    rid = resume_id or run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = RunPaths(Path("scorecards") / rid)

    def factory(base_url: str, api_key=None) -> OpenAIClient:
        import os
        return OpenAIClient(base_url=base_url, api_key=os.environ.get("GAUNTLET_API_KEY"))

    cells = execute_plan(cfg, bats, paths, base_dir=prompts, client_factory=factory,
                         only_models=list(models) if models else None,
                         resume=bool(resume_id))

    meta = RunMeta(id=rid, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                   gauntlet_version=__version__)
    write_meta(paths, meta)
    scorecard = assemble_scorecard(meta, paths)
    typer.echo(render_markdown(scorecard, share=share))
    typer.echo(f"\nRan {len(cells)} cell(s). Run dir: {paths.root}")
    if out:
        write_json(scorecard, out, share=share)
        typer.echo(f"Scorecard written to {out}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_cli_run.py -v`
Expected: PASS (1 test). The live test is collected but skipped without `GAUNTLET_LIVE_BASE_URL`.

- [ ] **Step 5: Run the full default suite (no live)**

Run: `.venv/Scripts/python -m pytest`
Expected: PASS — all prior tests plus the new runner suite green (live tests deselected by `addopts = -m 'not live'`).

- [ ] **Step 6: Commit**

```bash
git add gauntlet/cli.py tests/test_cli_run.py tests/live/test_live_run.py
git commit -m "feat: gauntlet run command (sequence + execute + assemble scorecard; live smoke opt-in)"
```

---

## Manual live verification (optional, box-b only)

After the suite is green, optionally confirm a real run against **box-b** (headless) — **never box-a while gaming:**

```bash
# PowerShell — point at the box-b Ollama endpoint, then:
$env:GAUNTLET_LIVE_BASE_URL = "http://<box-b>:11434"
.venv/Scripts/python -m pytest tests/live/test_live_run.py -m live -v
```

Expected: one cell produced against `gemma3:1b`, `cases == 1`.

---

## Self-review notes (coverage vs design phases 5–7)

- **Phase 5 (Sequencer):** load-profile-outer ordering (Task 3.1 preserves profile order, 3.3 groups by profile), busy guard (3.3), VRAM tight/broad with unknown→exclusive safe default (3.2 + 3.3). ✅
- **Phase 6 (Runner + resume):** `cells.jsonl` checkpoint + `--resume` skip (3.4, 3.6), cell orchestration with deterministic + judge scoring (3.5), error taxonomy — unreachable/OOM→errored cell, no-eligible-judge→unscored, busy→deferred, run never aborts (3.5, 3.6), final assembly (3.7). ✅
- **Phase 7 (CLI):** `gauntlet run` with `--config/--batteries/--prompts/--out/--model/--resume/--run-id/--share`; live smoke opt-in and box-a-excluded (3.8). ✅
- **Privacy invariants:** scorecard emit reuses Plan 2's `write_json` (leak guard + `--share`); the Cell still has no base_url field; the live suite is `-m live` and never names box-a. ✅
