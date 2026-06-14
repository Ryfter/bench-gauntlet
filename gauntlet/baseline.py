"""Frontier baseline gap analysis (pure). Given local cells and frontier cells,
report per capability: the local champion (highest scored quality) and the gap to
the frontier model. Capabilities the frontier didn't cover are skipped; unscored
local cells (quality None) are ignored — a baseline must not overstate confidence."""
from __future__ import annotations

from gauntlet.models import BaselineGap, Cell


def compute_gaps(local: list[Cell], frontier: list[Cell]) -> list[BaselineGap]:
    frontier_by_cap = {c.capability: c for c in frontier if c.quality is not None}
    gaps: list[BaselineGap] = []
    for capability, fcell in frontier_by_cap.items():
        candidates = [c for c in local
                      if c.capability == capability and c.quality is not None]
        if not candidates:
            continue
        champion = max(candidates, key=lambda c: c.quality)
        gaps.append(BaselineGap(
            capability=capability,
            local_champion=champion.model,
            frontier=fcell.model,
            gap=fcell.quality - champion.quality,
        ))
    return gaps
