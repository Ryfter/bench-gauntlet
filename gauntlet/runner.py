"""Run orchestration. Owns a run directory (`scorecards/<run-id>/`) with an
append-only `cells.jsonl` (one completed Cell per line) + `meta.json`. Drives the
OpenAIClient through each cell's cases, scores with the `scoring` package, and
checkpoints immediately so `--resume` loses at most the in-flight cell. The run
NEVER aborts: unreachable / load-fail / busy become typed cell outcomes."""
from __future__ import annotations

import re
import statistics
from pathlib import Path
from typing import TYPE_CHECKING

from gauntlet import errors
from gauntlet.models import CaseResult, Cell, RunMeta, Scorecard
from gauntlet.scorecard import aggregate_cell
from gauntlet.scoring import NEEDS_JUDGE, score_case
from gauntlet.scoring.judge import score_with_judge, select_judge
from gauntlet.sequencer import model_family as _model_family
from gauntlet.sequencer import plan_run

if TYPE_CHECKING:
    from gauntlet.battery import Battery, Case
    from gauntlet.client import OpenAIClient
    from gauntlet.config import GauntletConfig

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


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
    results: list[CaseResult] = []
    latencies: list[float] = []
    total_tokens = 0
    error_count = 0
    judge_used: str | None = None

    for case in battery.cases:
        prompt = load_prompt(case, base_dir)
        try:
            reply = client.chat(model=model, prompt=prompt)
        except errors.GauntletError as exc:
            # Transport/load failure: count the error AND record the case as an
            # unscored failure so it still counts toward `cases` (never silently 0).
            error_count += 1
            results.append(CaseResult(case_id=case.id, method=case.scoring, score=None,
                                      passed=False, detail=f"errored: {exc}"))
            continue
        latencies.append(reply.latency_s)
        if reply.completion_tokens:
            total_tokens += reply.completion_tokens

        # Strip think-tags so deterministic scorers see only the final answer.
        # Thinking models wrap chain-of-thought in <think>…</think>; leaving it
        # in causes compilation failures, commit-format mismatches, and bad JSON parses.
        scored_text = _THINK_RE.sub("", reply.text).strip()

        result = score_case(case, scored_text, base_dir=base_dir)
        if result is NEEDS_JUDGE:
            judge = select_judge(judge_pool or [], target_family=_model_family(model))
            if judge is None:
                results.append(CaseResult(case_id=case.id, method="judge", score=None,
                                          passed=False, detail="unscored: no eligible judge"))
                continue
            judge_used = judge
            results.append(score_with_judge(client, judge_model=judge,
                                             rubric=case.rubric or "", output=scored_text,
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


def _judge_pool_for(config: "GauntletConfig", target_name: str) -> list[tuple[str, str]]:
    """Other models configured on the same target, as (model_id, family) — the
    candidate judges for a cell on that target (cross-target judging is future work)."""
    return [(p.id, _model_family(p.id)) for p in config.models
            if p.target == target_name and p.judge]


def execute_plan(
    config: "GauntletConfig",
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
