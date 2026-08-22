"""Unit tests for ToC placement — no live inference, box ids only."""

from gauntlet.toc_scheduler import TocBox, TocCell, cell_cost, plan_placement


def _cell(
    model: str,
    *,
    battery: str = "code-gen",
    context: int = 8192,
    cost: float | None = None,
    weight: float | None = None,
    critical: bool = False,
    vram_gb: float | None = None,
    box_id: str | None = None,
) -> TocCell:
    return TocCell(
        model=model,
        context=context,
        battery=battery,
        estimated_cost=cost,
        weight=weight,
        critical=critical,
        vram_gb=vram_gb,
        box_id=box_id,
    )


def test_busy_box_defers_affinity_cells():
    boxes = [
        TocBox(id="box-a", vram_gb=32, usage_class="broad", busy=True),
        TocBox(id="box-b", vram_gb=8, usage_class="tight"),
    ]
    cells = [_cell("gemma3:1b", box_id="box-a", cost=10.0)]
    plan = plan_placement(boxes, cells)
    assert plan.batches == []
    assert len(plan.deferred) == 1
    assert plan.deferred[0].deferred is True
    assert "busy" in plan.deferred[0].defer_reason


def test_broad_box_gets_exclusive_batches():
    boxes = [TocBox(id="desktop", vram_gb=32, usage_class="broad")]
    cells = [
        _cell("model-a", cost=20.0, vram_gb=10.0),
        _cell("model-b", cost=18.0, vram_gb=12.0),
    ]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 2
    assert all(b.exclusive for b in plan.batches)
    assert all(b.box_id == "desktop" for b in plan.batches)
    assert {b.cells[0].model for b in plan.batches} == {"model-a", "model-b"}


def test_tight_box_packs_cheap_cells_in_parallel():
    boxes = [TocBox(id="laptop", vram_gb=24, usage_class="tight")]
    cells = [
        _cell("small-a", battery="commit-msg", cost=1.0, vram_gb=3.0),
        _cell("small-b", battery="commit-msg", cost=1.5, vram_gb=4.0),
        _cell("large-c", battery="commit-msg", cost=2.0, vram_gb=20.0),
    ]
    plan = plan_placement(boxes, cells)
    assert plan.deferred == []
    parallel = [b for b in plan.batches if not b.exclusive]
    exclusive = [b for b in plan.batches if b.exclusive]
    assert len(parallel) == 1
    assert {c.model for c in parallel[0].cells} == {"small-a", "small-b"}
    assert len(exclusive) == 1
    assert exclusive[0].cells[0].model == "large-c"


def test_critical_cells_prefer_strongest_available_box():
    boxes = [
        TocBox(id="weak", vram_gb=8, usage_class="tight"),
        TocBox(id="strong", vram_gb=32, usage_class="broad"),
    ]
    cells = [
        _cell("cheap", battery="commit-msg", cost=1.0, critical=False),
        _cell("critical-heavy", cost=50.0, critical=True, vram_gb=15.0),
    ]
    plan = plan_placement(boxes, cells)
    assert plan.deferred == []
    critical_batch = plan.batches[0]
    assert critical_batch.box_id == "strong"
    assert critical_batch.cells[0].model == "critical-heavy"
    assert critical_batch.exclusive is True


def test_weight_field_used_when_estimated_cost_absent():
    boxes = [TocBox(id="desktop", vram_gb=32, usage_class="broad")]
    cells = [
        TocCell(model="m", context=8192, battery="code-gen", weight=50.0, estimated_cost=None),
    ]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].cells[0].model == "m"


def test_unknown_affinity_box_defers():
    boxes = [TocBox(id="known", vram_gb=32, usage_class="broad")]
    cells = [_cell("orphan", box_id="missing-box", cost=10.0)]
    plan = plan_placement(boxes, cells)
    assert plan.batches == []
    assert len(plan.deferred) == 1
    assert "unknown" in plan.deferred[0].defer_reason


def test_all_boxes_busy_defers_every_cell():
    boxes = [
        TocBox(id="a", vram_gb=32, usage_class="broad", busy=True),
        TocBox(id="b", vram_gb=8, usage_class="tight", busy=True),
    ]
    cells = [_cell("m1", cost=3.0), _cell("m2", cost=12.0, critical=True)]
    plan = plan_placement(boxes, cells)
    assert plan.batches == []
    assert len(plan.deferred) == 2
    assert all(c.deferred for c in plan.deferred)
    assert all("no available boxes" in c.defer_reason for c in plan.deferred)


def test_heavy_non_critical_routes_to_broad_not_tight():
    boxes = [
        TocBox(id="tight", vram_gb=8, usage_class="tight"),
        TocBox(id="broad", vram_gb=32, usage_class="broad"),
    ]
    cells = [_cell("heavy", cost=10.0, critical=False, vram_gb=6.0)]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].box_id == "broad"
    assert plan.batches[0].exclusive is True


def test_default_cost_when_weight_and_estimated_cost_absent():
    cell = TocCell(model="tiny", context=4096, battery="commit-msg")
    assert cell_cost(cell) == 1.0
    boxes = [TocBox(id="laptop", vram_gb=16, usage_class="tight")]
    plan = plan_placement(boxes, [cell])
    assert len(plan.batches) == 1
    assert plan.batches[0].cells[0].model == "tiny"


def test_vram_overflow_splits_tight_parallel_batch():
    boxes = [TocBox(id="laptop", vram_gb=10, usage_class="tight")]
    cells = [
        _cell("a", cost=1.0, vram_gb=4.0),
        _cell("b", cost=1.0, vram_gb=4.0),
        _cell("c", cost=1.0, vram_gb=4.0),
    ]
    plan = plan_placement(boxes, cells)
    parallel = [b for b in plan.batches if not b.exclusive]
    exclusive = [b for b in plan.batches if b.exclusive]
    assert len(parallel) == 1
    assert {c.model for c in parallel[0].cells} == {"a", "b"}
    assert len(exclusive) == 1
    assert exclusive[0].cells[0].model == "c"
