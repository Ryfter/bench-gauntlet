"""Run orchestration. Owns a run directory (`scorecards/<run-id>/`) with an
append-only `cells.jsonl` (one completed Cell per line) + `meta.json`. Drives the
OpenAIClient through each cell's cases, scores with the `scoring` package, and
checkpoints immediately so `--resume` loses at most the in-flight cell. The run
NEVER aborts: unreachable / load-fail / busy become typed cell outcomes."""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from gauntlet import errors, integrity, vram
from gauntlet.models import CaseResult, Cell, RunMeta, Scorecard
from gauntlet.runstatus import RunStatus, clear_status, now_iso, write_status
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
_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SAFE_RUN_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def private_run_root() -> Path:
    """OS-private home for raw target-bearing run ledgers.

    ``scorecards/`` remains an intentional export location, not a checkpoint
    store. Tests and managed deployments may override this root explicitly.
    """
    configured = os.environ.get("GAUNTLET_PRIVATE_RUN_ROOT")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "bench-gauntlet" / "runs"


def validate_run_component(value: str) -> str:
    """Accept one portable, non-traversing run-path component."""
    if not isinstance(value, str) or not _SAFE_RUN_COMPONENT_RE.fullmatch(value):
        raise errors.GauntletError(
            "run identifiers must be a safe run id using only ASCII letters, "
            "digits, dot, underscore, or hyphen"
        )
    return value


class RunPaths:
    def __init__(self, root: str | Path, *, confinement_root: str | Path | None = None) -> None:
        self.root = Path(root)
        self._confinement_root = (Path(confinement_root)
                                  if confinement_root is not None else None)
        self.cells = self.root / "cells.jsonl"
        self.cases = self.root / "cases.jsonl"
        self.meta = self.root / "meta.json"

    @classmethod
    def for_run_id(
        cls,
        run_id: str,
        *,
        namespace: str | None = None,
        private_root: str | Path | None = None,
    ) -> "RunPaths":
        base = (Path(private_root) if private_root is not None
                else globals()["private_run_root"]())
        root = base / validate_run_component(run_id)
        if namespace is not None:
            root = root / validate_run_component(namespace)
        return cls(root, confinement_root=base)

    def ensure(self) -> None:
        resolved = self.root.expanduser().resolve()
        if resolved == _REPOSITORY_ROOT or resolved.is_relative_to(_REPOSITORY_ROOT):
            raise errors.GauntletError(
                "refusing to store private run data inside the tracked repository"
            )
        if self._confinement_root is not None:
            boundary = self._confinement_root.expanduser().resolve()
            if resolved == boundary or not resolved.is_relative_to(boundary):
                raise errors.GauntletError(
                    "refusing a ledger path outside the dedicated private run root"
                )
        self.root = resolved
        self.cells = self.root / "cells.jsonl"
        self.cases = self.root / "cases.jsonl"
        self.meta = self.root / "meta.json"
        if self._confinement_root is not None:
            for ledger in (self.cells, self.cases, self.meta):
                if not ledger.resolve().is_relative_to(boundary):
                    raise errors.GauntletError(
                        "refusing a ledger path outside the dedicated private run root"
                    )
        self.root.mkdir(parents=True, exist_ok=True)


def cell_key(cell: Cell) -> tuple[str | None, str, int, str]:
    return (cell.target, cell.model, cell.context, cell.capability)


def append_cell(paths: RunPaths, cell: Cell) -> None:
    with paths.cells.open("a", encoding="utf-8") as fh:
        fh.write(cell.model_dump_json() + "\n")


# Failures that a mid-sentence cut is a sufficient explanation for. Anything
# else -- the code ran and was wrong, it hung, it reached for the answers --
# happened before the budget mattered and keeps its result.
_TRUNCATION_EXCUSES = frozenset({"no_code_emitted", "syntax_error"})


def attribute_truncation(result: CaseResult, *, truncated: bool) -> CaseResult:
    """Re-attribute a failure that the token budget, not the model, caused.

    A reasoning model can spend its entire budget thinking and be cut off before
    writing a line. Scored naively that is `no_code_emitted` at 0.0 -- the
    benchmark measuring its own configuration and reporting it as a property of
    the model. We cannot tell whether it could not do the task or was not
    allowed to finish, so the honest answer is `unscored` (scoring-honesty
    invariant: never silently 0).

    This does not soften a real failure: a model that emits prose *within* its
    budget genuinely failed, and a `wrong_answer` ran to completion, so the
    defect in it is real regardless of what was cut off afterwards.
    """
    if not truncated or result.failure_mode not in _TRUNCATION_EXCUSES:
        return result
    return result.model_copy(update={
        "score": None,
        "passed": False,
        "failure_mode": "truncated",
        "detail": f"unscored: reply truncated by the token budget ({result.failure_mode})",
    })


_DEAD_ENDPOINT_HINT = (
    "unscored: target not serving when the run reached it. If this is LM Studio, "
    "opening the desktop app stops its headless server (`lms server start`)."
)


def _unreachable_cell(*, model: str, target: str, box: str, context: int,
                      battery: "Battery") -> Cell:
    """A cell for a target that was not serving, without calling it case by case.

    Recorded rather than skipped so the gap is visible in the scorecard, and
    `unscored` rather than 0.0 because a dead endpoint says nothing whatever
    about the model. Building it up front also avoids the failure mode this
    exists to prevent: hammering a refused port once per case and calling the
    result a measurement.
    """
    results = [CaseResult(case_id=case.id, method=case.scoring, score=None,
                          passed=False, detail=_DEAD_ENDPOINT_HINT)
               for case in battery.cases]
    return aggregate_cell(model=model, target=target, box=box, context=context,
                          capability=battery.capability, results=results,
                          errors=len(results))


def _load_failed_cell(*, model: str, target: str, box: str, context: int,
                      battery: "Battery") -> Cell:
    results = [CaseResult(
        case_id=case.id, method=case.scoring, score=None, passed=False,
        detail="unscored: requested model profile failed to load",
        failure_mode="load_error", tier=case.tier, dimension=case.dimension,
    ) for case in battery.cases]
    return aggregate_cell(model=model, target=target, box=box, context=context,
                          capability=battery.capability, results=results,
                          errors=len(results))


def _case_heartbeat(status_path, status: RunStatus | None):
    """A per-case tick for the run indicator, or None when nothing is watching.

    Cheap by design -- one small file rewrite per case -- because the
    alternative is an indicator that sits unchanged for the hours a single
    108-case cell can take, which is indistinguishable from a hung run.
    """
    if not status_path or status is None:
        return None

    def tick(done: int, total: int) -> None:
        status.cases_done = done
        status.cases_total = total
        write_status(status_path, status)

    return tick


def append_case_rows(
    paths: RunPaths,
    *,
    model: str,
    target: str | None,
    context: int,
    capability: str,
    results: list[CaseResult],
) -> None:
    """Persist one row per individual case beside the aggregated cell.

    A cell is a summary, and a summary can only answer the questions it was
    designed for. A full fleet run costs hours of GPU time, so throwing away
    the per-case detail means the next question — "which cases did every model
    miss?", "is this dimension too hard?" — costs another whole run. `score`
    stays `None` for unscored cases; it must never reach disk as 0.0.
    """
    with paths.cases.open("a", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({
                "model": model, "target": target, "context": context,
                "capability": capability, "case_id": r.case_id,
                "tier": r.tier, "dimension": r.dimension,
                "score": r.score, "passed": r.passed,
                "failure_mode": r.failure_mode,
            }) + "\n")


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
    case_sink: "Callable[[list[CaseResult]], None] | None" = None,
    on_case: "Callable[[int, int], None] | None" = None,
) -> Cell:
    """Fire every case of one battery against one loaded profile, score, and
    aggregate into a Cell. Per-case transport failures are counted as errors and
    never raised — the run must continue (design error taxonomy)."""
    results: list[CaseResult] = []
    latencies: list[float] = []
    ttfts: list[float] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    error_count = 0
    judge_used: str | None = None

    total_cases = len(battery.cases)
    for index, case in enumerate(battery.cases):
        if on_case is not None:
            on_case(index, total_cases)
        prompt = load_prompt(case, base_dir)
        if case.scoring == "code-exec" and case.tests_file:
            hidden_path = Path(base_dir) / case.tests_file
            try:
                hidden_material = hidden_path.read_text(encoding="utf-8")
            except OSError:
                hidden_material = None
            if hidden_material is not None:
                integrity.assert_no_prompt_leak(
                    prompt, hidden_material, case_id=case.id,
                    dimension=case.dimension,
                )
        try:
            reply = client.chat(model=model, prompt=prompt,
                                max_tokens=battery.max_tokens)
        except integrity.IntegrityError:
            results.append(CaseResult(
                case_id=case.id, method=case.scoring, score=None, passed=False,
                detail="unscored: response used server-side tools",
                failure_mode="integrity_violation", tier=case.tier,
                dimension=case.dimension,
                integrity_violations=[{"kind": "tool_use", "detail": "response"}],
            ))
            continue
        except errors.GauntletError as exc:
            # Transport/load failure: count the error AND record the case as an
            # unscored failure so it still counts toward `cases` (never silently 0).
            error_count += 1
            results.append(CaseResult(case_id=case.id, method=case.scoring, score=None,
                                      passed=False, detail=f"errored: {exc}"))
            continue
        latencies.append(reply.latency_s)
        if reply.ttft_s is not None:
            ttfts.append(reply.ttft_s)
        if reply.prompt_tokens:
            total_prompt_tokens += reply.prompt_tokens
        if reply.completion_tokens:
            total_completion_tokens += reply.completion_tokens

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
            try:
                judged = score_with_judge(client, judge_model=judge,
                                          rubric=case.rubric or "", output=scored_text,
                                          case_id=case.id)
            except errors.GauntletError:
                error_count += 1
                judged = CaseResult(
                    case_id=case.id, method="judge", score=None, passed=False,
                    detail="unscored: judge transport or load failure",
                    failure_mode="transport_error", tier=case.tier,
                    dimension=case.dimension,
                )
            results.append(judged)
        else:
            result.case_id = case.id
            results.append(attribute_truncation(result, truncated=reply.truncated))

    # Checkpoint the raw per-case detail before the summary, so a crash between
    # the two loses the cell (which resume re-runs) rather than the detail.
    if case_sink is not None:
        case_sink(results)

    p50 = statistics.median(latencies) if latencies else None
    ttft_p50 = statistics.median(ttfts) if ttfts else None
    total_latency = sum(latencies)
    tps = (total_completion_tokens / total_latency) if total_completion_tokens and total_latency else None

    cell = aggregate_cell(model=model, target=target, box=box, context=context,
                          capability=battery.capability, results=results,
                          latency_p50_s=p50, tokens_per_s=tps,
                          ttft_p50_s=ttft_p50,
                          prompt_tokens=total_prompt_tokens or None,
                          completion_tokens=total_completion_tokens or None,
                          errors=error_count)
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
    status_path: str | Path | None = None,
    release_gpu: bool = True,
    exclusive_vram: bool = True,
) -> list[Cell]:
    """Drive the sequenced plan to completion. Opens one client per target (lazily,
    via client_factory), runs each cell, and appends it to cells.jsonl immediately.
    Deferred (busy) cells are skipped; nothing aborts the run."""
    paths.ensure()
    done = read_completed(paths) if resume else set()
    plan = plan_run(config, batteries, footprints=footprints, only_models=only_models)
    battery_by_cap = {b.capability: b for b in batteries}

    total_cells = sum(len(g.cells) for g in plan.groups)
    if total_cells == 0:
        return []
    # Count cells finished by an earlier attempt too. A resumed run reporting
    # 0/63 when 23 are on disk understates progress at exactly the moment
    # someone is looking at it to decide whether to wait.
    #
    # Only those inside *this* plan, though. `done` holds every cell in the run
    # directory, so when a resume narrows the model list -- rerunning two models
    # out of nine -- counting all of them reports 51/14, which is worse than no
    # number at all.
    planned = {(c.target, c.model, c.context, c.capability)
               for g in plan.groups for c in g.cells}
    resumed_cells = len(done & planned)
    # Exclusive-VRAM: start from an empty card. A model sharing VRAM spills
    # layers to CPU, and the number that comes out then describes the
    # contention rather than the model -- which is not a benchmark result. One
    # model resident at a time also keeps power draw to what the work needs.
    if exclusive_vram:
        vram.unload_all_local()
    # Snapshot after clearing, so the diff still only ever claims our own loads.
    vram_before = vram.loaded_models() if release_gpu else None
    ran_models: list[str] = []
    status = RunStatus(run_id=paths.root.name, pid=os.getpid(),
                       started_at=now_iso(), cells_total=total_cells,
                       cells_done=resumed_cells, vram_before=vram_before)
    if status_path:
        write_status(status_path, status)

    clients: dict[str, object] = {}
    dead_targets: set[str] = set()
    failed_profiles: set[tuple[str, str, int]] = set()
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
                    if status_path:
                        status.model = model
                        status.capability = cell_plan.capability
                        write_status(status_path, status)
                    if model not in ran_models:
                        ran_models.append(model)
                        # Load explicitly at the context we actually use.
                        # Otherwise LM Studio JIT-loads at its own defaults and
                        # sizes the KV cache for many times the work in hand.
                        if exclusive_vram:
                            if not vram.load(model, context=context):
                                failed_profiles.add((target, model, context))
                        if status_path:
                            status.models_ran = list(ran_models)
                            write_status(status_path, status)
                    if (target, model, context) in failed_profiles:
                        battery = battery_by_cap[cell_plan.capability]
                        cell = _load_failed_cell(
                            model=model, target=target, box=cell_plan.box_hardware,
                            context=context, battery=battery)
                        append_cell(paths, cell)
                        done.add(key)
                        produced.append(cell)
                        continue
                    tgt = config.target_by_name(target)
                    client = clients.get(target)
                    if client is None:
                        client = client_factory(tgt.base_url)
                        clients[target] = client
                        # Check the endpoint is serving before committing a
                        # model's worth of work to it. A dead server refuses
                        # every request instantly, so without this a whole
                        # battery burns through in seconds and lands as cells
                        # that look measured. The run still continues -- an
                        # unreachable target is a cell outcome, never an abort.
                        if not client.ping():
                            dead_targets.add(target)
                    if target in dead_targets:
                        battery = battery_by_cap[cell_plan.capability]
                        cell = _unreachable_cell(
                            model=model, target=target, box=cell_plan.box_hardware,
                            context=context, battery=battery)
                        append_cell(paths, cell)
                        done.add(key)
                        produced.append(cell)
                        continue
                    cell = run_cell(client, model=model, target=target,
                                    box=cell_plan.box_hardware, context=context,
                                    battery=battery_by_cap[cell_plan.capability], base_dir=base_dir,
                                    judge_pool=_judge_pool_for(config, target),
                                    case_sink=lambda results, _t=target, _m=model, _c=context,
                                                     _cap=cell_plan.capability: append_case_rows(
                                        paths, model=_m, target=_t, context=_c,
                                        capability=_cap, results=results),
                                    on_case=_case_heartbeat(status_path, status))
                    append_cell(paths, cell)
                    done.add(key)
                    produced.append(cell)
                    if status_path:
                        status.cells_done = resumed_cells + len(produced)
                        write_status(status_path, status)
                # Every battery for this model is done; free it before the next
                # one loads rather than holding it for the rest of the run.
                if exclusive_vram:
                    vram.unload(model)
    finally:
        for client in clients.values():
            client.close()
        # Hand the GPU back. A loaded-but-idle model costs power for nothing,
        # and this runs on a desktop. Only models we caused to load are freed.
        if release_gpu:
            vram.release_after_run(vram_before, ran_models)
        if status_path:
            clear_status(status_path)
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
