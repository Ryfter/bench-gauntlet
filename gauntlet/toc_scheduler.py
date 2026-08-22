"""Theory-of-Constraints placement across boxes — pure, no network.

Given a fleet of boxes and a work matrix of cells, produce an ordered batch plan:
critical-path cells on the strongest available box first, heavy non-critical work
on broad boxes exclusively, cheap cells packed in parallel on tight boxes when
VRAM allows. Busy boxes are skipped; affinity-pinned cells on a busy box defer."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Cells below this scheduling cost land on tight boxes when possible.
_CHEAP_COST_CEILING = 5.0


class TocBox(BaseModel):
    id: str
    vram_gb: float
    usage_class: Literal["tight", "broad"] = "broad"
    busy: bool = False


class TocCell(BaseModel):
    model: str
    context: int
    battery: str
    estimated_cost: float | None = None
    weight: float | None = None
    critical: bool = False
    vram_gb: float | None = None  # residency footprint for tight co-packing
    box_id: str | None = None     # optional affinity (target → box)
    deferred: bool = False
    defer_reason: str = ""

    @model_validator(mode="after")
    def _default_cost(self) -> TocCell:
        if self.estimated_cost is None and self.weight is None:
            object.__setattr__(self, "estimated_cost", 1.0)
        return self


def cell_cost(cell: TocCell) -> float:
    if cell.weight is not None:
        return cell.weight
    assert cell.estimated_cost is not None
    return cell.estimated_cost


class TocBatch(BaseModel):
    """Resident load on one box — exclusive (one profile) or parallel tight pack."""
    box_id: str
    exclusive: bool
    cells: list[TocCell] = Field(default_factory=list)


class TocPlacementPlan(BaseModel):
    batches: list[TocBatch] = Field(default_factory=list)
    deferred: list[TocCell] = Field(default_factory=list)


def _box_map(boxes: list[TocBox]) -> dict[str, TocBox]:
    return {b.id: b for b in boxes}


def _defer(cell: TocCell, reason: str) -> TocCell:
    return cell.model_copy(update={"deferred": True, "defer_reason": reason})


def _place_exclusive(plan: TocPlacementPlan, box: TocBox, cell: TocCell) -> None:
    plan.batches.append(TocBatch(box_id=box.id, exclusive=True, cells=[cell]))


def _place_tight(
    plan: TocPlacementPlan,
    box: TocBox,
    cell: TocCell,
    open_tight: dict[str, tuple[int, float]],
) -> None:
    footprint = cell.vram_gb
    if footprint is None:
        _place_exclusive(plan, box, cell)
        return
    idx, used = open_tight.get(box.id, (-1, 0.0))
    if idx < 0 or used + footprint > box.vram_gb:
        plan.batches.append(TocBatch(box_id=box.id, exclusive=True, cells=[cell]))
        open_tight[box.id] = (len(plan.batches) - 1, footprint)
        return
    batch = plan.batches[idx]
    batch.exclusive = False
    batch.cells.append(cell)
    open_tight[box.id] = (idx, used + footprint)


def plan_placement(boxes: list[TocBox], cells: list[TocCell]) -> TocPlacementPlan:
    """Order cells into box batches: critical → heavy → cheap; skip busy boxes."""
    by_id = _box_map(boxes)
    available = sorted(
        (b for b in boxes if not b.busy),
        key=lambda b: b.vram_gb,
        reverse=True,
    )
    busy_ids = {b.id for b in boxes if b.busy}
    plan = TocPlacementPlan()
    open_tight: dict[str, tuple[int, float]] = {}

    critical = sorted((c for c in cells if c.critical), key=lambda c: -cell_cost(c))
    non_critical = [c for c in cells if not c.critical]
    heavy = sorted(
        (c for c in non_critical if cell_cost(c) >= _CHEAP_COST_CEILING),
        key=lambda c: -cell_cost(c),
    )
    cheap = sorted(
        (c for c in non_critical if cell_cost(c) < _CHEAP_COST_CEILING),
        key=lambda c: cell_cost(c),
    )
    ordered = critical + heavy + cheap

    strongest = available[0] if available else None
    broad_available = [b for b in available if b.usage_class == "broad"]
    tight_available = [b for b in available if b.usage_class == "tight"]
    strongest_broad = broad_available[0] if broad_available else strongest

    for cell in ordered:
        affinity = cell.box_id
        if affinity is not None and affinity in busy_ids:
            plan.deferred.append(_defer(cell, f"box {affinity} busy"))
            continue
        if affinity is not None and affinity not in by_id:
            plan.deferred.append(_defer(cell, f"box {affinity} unknown"))
            continue
        if not available:
            plan.deferred.append(_defer(cell, "no available boxes"))
            continue

        if affinity is not None:
            box = by_id[affinity]
            if box.usage_class == "broad" or cell.vram_gb is None:
                _place_exclusive(plan, box, cell)
            else:
                _place_tight(plan, box, cell, open_tight)
            continue

        if cell.critical:
            assert strongest is not None
            _place_exclusive(plan, strongest, cell)
            continue

        if cell_cost(cell) >= _CHEAP_COST_CEILING:
            assert strongest_broad is not None
            _place_exclusive(plan, strongest_broad, cell)
            continue

        if tight_available:
            _place_tight(plan, tight_available[0], cell, open_tight)
        else:
            # No tight box — fall back to weakest available box exclusively.
            _place_exclusive(plan, available[-1], cell)

    return plan
