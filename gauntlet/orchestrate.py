"""Parallel multi-target orchestration. Fans out gauntlet runs to every
configured target simultaneously, collects cells, and reports a compact
best-per-capability summary — keeping frontier-model context costs minimal."""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from gauntlet import __version__
from gauntlet.models import Cell, RunMeta
from gauntlet.runner import RunPaths, execute_plan, write_meta

if TYPE_CHECKING:
    from gauntlet.battery import Battery
    from gauntlet.config import GauntletConfig


def _run_target(
    target_name: str,
    config: "GauntletConfig",
    batteries: list["Battery"],
    run_id: str,
    base_dir: str,
    api_key: str | None,
) -> tuple[str, list[Cell]]:
    """Run all batteries for one target in a thread. Returns (target_name, cells)."""
    from gauntlet.client import OpenAIClient

    target_cfg = config.model_copy(update={
        "models": [m for m in config.models if m.target == target_name]
    })
    paths = RunPaths(Path("scorecards") / run_id / target_name)

    def factory(base_url: str) -> OpenAIClient:
        return OpenAIClient(base_url=base_url, api_key=api_key)

    cells = execute_plan(target_cfg, batteries, paths, base_dir=base_dir,
                         client_factory=factory)
    meta = RunMeta(
        id=run_id,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        gauntlet_version=__version__,
    )
    write_meta(paths, meta)
    return target_name, cells


def orchestrate(
    config: "GauntletConfig",
    batteries: list["Battery"],
    run_id: str,
    base_dir: str,
    api_key: str | None,
    progress_cb=None,
) -> list[Cell]:
    """Fan out to all unique targets in parallel; return merged cell list.

    progress_cb(target_name, n_cells, error) is called as each target finishes.
    """
    target_names = list(dict.fromkeys(m.target for m in config.models))
    all_cells: list[Cell] = []

    with ThreadPoolExecutor(max_workers=len(target_names)) as pool:
        futures = {
            pool.submit(_run_target, t, config, batteries, run_id, base_dir, api_key): t
            for t in target_names
        }
        for fut in as_completed(futures):
            target = futures[fut]
            try:
                _, cells = fut.result()
                all_cells.extend(cells)
                if progress_cb:
                    progress_cb(target, len(cells), None)
            except Exception as exc:
                if progress_cb:
                    progress_cb(target, 0, exc)

    return all_cells


def compact_summary(cells: list[Cell]) -> str:
    """Render a compact best-per-capability table for reporting back to a
    frontier model — ~one line per capability instead of one line per cell."""
    by_cap: dict[str, list[Cell]] = defaultdict(list)
    for c in cells:
        if c.quality is not None:
            by_cap[c.capability].append(c)

    if not by_cap:
        return "(no scored cells — all errored or unscored)"

    col_model = 34
    header = (f"{'capability':<18} {'champion':<{col_model}} "
              f"{'quality':>7} {'pass':>5} {'tok/s':>6}  box")
    sep = "─" * len(header)
    rows = [header, sep]

    for cap in sorted(by_cap):
        best = max(by_cap[cap], key=lambda c: (c.quality or 0, c.pass_rate or 0))
        tps = f"{best.tokens_per_s:.0f}" if best.tokens_per_s else "—"
        model = best.model
        if len(model) > col_model:
            model = model[: col_model - 1] + "…"
        rows.append(
            f"{cap:<18} {model:<{col_model}} "
            f"{best.quality or 0:>7.2f} {best.pass_rate or 0:>5.2f} {tps:>6}  {best.box}"
        )

    all_caps = {c.capability for c in cells}
    for cap in sorted(all_caps - set(by_cap)):
        rows.append(f"{cap:<18} (unscored)")

    return "\n".join(rows)
