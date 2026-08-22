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
    estimated_cost: float | None = None,
) -> TocCell:
    eff_cost = cost if cost is not None else estimated_cost
    return TocCell(
        model=model,
        context=context,
        battery=battery,
        estimated_cost=eff_cost,
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


def test_multiple_critical_cells_route_to_strongest_in_cost_order():
    boxes = [
        TocBox(id="weak", vram_gb=8, usage_class="tight"),
        TocBox(id="strong", vram_gb=32, usage_class="broad"),
    ]
    cells = [
        _cell("crit-light", cost=10.0, critical=True),
        _cell("crit-heavy", cost=40.0, critical=True),
    ]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 2
    assert plan.batches[0].cells[0].model == "crit-heavy"
    assert plan.batches[1].cells[0].model == "crit-light"
    assert all(b.box_id == "strong" for b in plan.batches)


def test_empty_box_list_defers_every_cell():
    cells = [_cell("solo", cost=2.0), _cell("pair", cost=8.0, critical=True)]
    plan = plan_placement([], cells)
    assert plan.batches == []
    assert len(plan.deferred) == 2
    assert all("no available boxes" in c.defer_reason for c in plan.deferred)


def test_cheap_cells_pack_on_tight_before_broad_fallback():
    boxes = [
        TocBox(id="tight", vram_gb=16, usage_class="tight"),
        TocBox(id="broad", vram_gb=32, usage_class="broad"),
    ]
    cells = [_cell("cheap-a", cost=2.0, vram_gb=3.0), _cell("cheap-b", cost=3.0, vram_gb=4.0)]
    plan = plan_placement(boxes, cells)
    assert len(plan.deferred) == 0
    parallel = [b for b in plan.batches if not b.exclusive]
    assert len(parallel) == 1
    assert parallel[0].box_id == "tight"
    assert {c.model for c in parallel[0].cells} == {"cheap-a", "cheap-b"}


def test_no_tight_boxes_cheap_uses_weakest_available_exclusive():
    boxes = [TocBox(id="broad-a", vram_gb=32, usage_class="broad")]
    cells = [_cell("cheap", cost=1.0)]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].box_id == "broad-a"
    assert plan.batches[0].exclusive is True


def test_affinity_on_tight_box_respects_vram_packing():
    boxes = [TocBox(id="pin", vram_gb=10, usage_class="tight")]
    cells = [
        _cell("a", box_id="pin", cost=1.0, vram_gb=4.0),
        _cell("b", box_id="pin", cost=1.0, vram_gb=4.0),
        _cell("c", box_id="pin", cost=1.0, vram_gb=4.0),
    ]
    plan = plan_placement(boxes, cells)
    parallel = [b for b in plan.batches if not b.exclusive]
    exclusive = [b for b in plan.batches if b.exclusive]
    assert len(parallel) == 1
    assert parallel[0].box_id == "pin"
    assert {c.model for c in parallel[0].cells} == {"a", "b"}
    assert len(exclusive) == 1
    assert exclusive[0].cells[0].model == "c"


def test_weight_beats_default_cost_for_scheduling_order():
    boxes = [TocBox(id="desktop", vram_gb=32, usage_class="broad")]
    cells = [
        _cell("heavy-weight", weight=50.0, estimated_cost=None),
        _cell("light-weight", weight=2.0, estimated_cost=None),
    ]
    plan = plan_placement(boxes, cells)
    assert [b.cells[0].model for b in plan.batches] == ["heavy-weight", "light-weight"]


def test_empty_cell_list_yields_empty_plan():
    boxes = [TocBox(id="desktop", vram_gb=32, usage_class="broad")]
    plan = plan_placement(boxes, [])
    assert plan.batches == []
    assert plan.deferred == []


def test_cell_cost_prefers_weight_over_estimated_cost():
    cell = TocCell(
        model="dual",
        context=8192,
        battery="code-gen",
        weight=99.0,
        estimated_cost=1.0,
    )
    assert cell_cost(cell) == 99.0


def test_cost_ceiling_boundary_heavy_at_five():
    boxes = [
        TocBox(id="tight", vram_gb=16, usage_class="tight"),
        TocBox(id="broad", vram_gb=32, usage_class="broad"),
    ]
    heavy = _cell("at-ceiling", cost=5.0, vram_gb=2.0)
    cheap = _cell("under-ceiling", cost=4.99, vram_gb=2.0)
    heavy_plan = plan_placement(boxes, [heavy])
    cheap_plan = plan_placement(boxes, [cheap])
    assert heavy_plan.batches[0].box_id == "broad"
    assert heavy_plan.batches[0].exclusive is True
    assert cheap_plan.batches[0].box_id == "tight"
    # First cheap cell opens a tight batch (exclusive until a second joins).
    assert cheap_plan.batches[0].exclusive is True


def test_cost_ceiling_boundary_cheap_packs_in_parallel_on_tight():
    boxes = [
        TocBox(id="tight", vram_gb=16, usage_class="tight"),
        TocBox(id="broad", vram_gb=32, usage_class="broad"),
    ]
    cells = [
        _cell("cheap-a", cost=4.99, vram_gb=2.0),
        _cell("cheap-b", cost=4.5, vram_gb=2.0),
    ]
    plan = plan_placement(boxes, cells)
    parallel = [b for b in plan.batches if not b.exclusive]
    assert len(parallel) == 1
    assert parallel[0].box_id == "tight"
    assert {c.model for c in parallel[0].cells} == {"cheap-a", "cheap-b"}


def test_critical_with_affinity_uses_pinned_box():
    boxes = [
        TocBox(id="weak", vram_gb=8, usage_class="tight"),
        TocBox(id="pin", vram_gb=16, usage_class="tight"),
        TocBox(id="strong", vram_gb=32, usage_class="broad"),
    ]
    cells = [_cell("crit-pinned", cost=40.0, critical=True, box_id="pin")]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].box_id == "pin"
    assert plan.batches[0].cells[0].model == "crit-pinned"


def test_heavy_routes_to_highest_vram_broad():
    boxes = [
        TocBox(id="broad-small", vram_gb=24, usage_class="broad"),
        TocBox(id="broad-big", vram_gb=48, usage_class="broad"),
    ]
    cells = [_cell("heavy", cost=20.0, vram_gb=10.0)]
    plan = plan_placement(boxes, cells)
    assert plan.batches[0].box_id == "broad-big"


def test_heavy_when_only_tight_boxes_uses_strongest_available():
    boxes = [
        TocBox(id="tight-a", vram_gb=8, usage_class="tight"),
        TocBox(id="tight-b", vram_gb=16, usage_class="tight"),
    ]
    cells = [_cell("heavy", cost=12.0, vram_gb=6.0)]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].box_id == "tight-b"
    assert plan.batches[0].exclusive is True


def test_affinity_to_broad_is_always_exclusive():
    boxes = [TocBox(id="broad", vram_gb=32, usage_class="broad")]
    cells = [
        _cell("pinned", box_id="broad", cost=1.0, vram_gb=4.0),
        _cell("pinned-2", box_id="broad", cost=1.5, vram_gb=4.0),
    ]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 2
    assert all(b.exclusive for b in plan.batches)
    assert all(b.box_id == "broad" for b in plan.batches)


def test_second_cheap_joins_open_tight_batch():
    boxes = [TocBox(id="laptop", vram_gb=20, usage_class="tight")]
    cells = [
        _cell("first", cost=1.0, vram_gb=5.0),
        _cell("second", cost=2.0, vram_gb=5.0),
    ]
    plan = plan_placement(boxes, cells)
    parallel = [b for b in plan.batches if not b.exclusive]
    assert len(parallel) == 1
    assert {c.model for c in parallel[0].cells} == {"first", "second"}


def test_tight_cell_without_vram_footprint_is_exclusive():
    boxes = [TocBox(id="laptop", vram_gb=16, usage_class="tight")]
    cells = [_cell("no-vram", cost=1.0, vram_gb=None)]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].exclusive is True


def test_critical_skips_busy_strongest_uses_next_available():
    boxes = [
        TocBox(id="strong", vram_gb=32, usage_class="broad", busy=True),
        TocBox(id="backup", vram_gb=16, usage_class="tight"),
    ]
    cells = [_cell("crit", cost=30.0, critical=True)]
    plan = plan_placement(boxes, cells)
    assert len(plan.batches) == 1
    assert plan.batches[0].box_id == "backup"


def test_mixed_queue_respects_critical_then_heavy_then_cheap():
    boxes = [
        TocBox(id="tight", vram_gb=16, usage_class="tight"),
        TocBox(id="broad", vram_gb=32, usage_class="broad"),
    ]
    cells = [
        _cell("cheap", cost=1.0, vram_gb=3.0),
        _cell("heavy", cost=10.0, vram_gb=8.0),
        _cell("crit", cost=25.0, critical=True, vram_gb=6.0),
    ]
    plan = plan_placement(boxes, cells)
    order = [b.cells[0].model for b in plan.batches if len(b.cells) == 1]
    # critical first (exclusive on broad), heavy second, cheap may pack on tight
    assert plan.batches[0].cells[0].model == "crit"
    assert plan.batches[0].box_id == "broad"
    models_scheduled = {c.model for b in plan.batches for c in b.cells}
    assert models_scheduled == {"cheap", "heavy", "crit"}


def test_deferred_cell_is_copy_not_mutating_input():
    boxes = [TocBox(id="only", vram_gb=8, usage_class="tight", busy=True)]
    original = _cell("x", cost=2.0)
    plan = plan_placement(boxes, [original])
    assert original.deferred is False
    assert plan.deferred[0].deferred is True
    assert plan.deferred[0] is not original
