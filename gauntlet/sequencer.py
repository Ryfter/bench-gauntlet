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
