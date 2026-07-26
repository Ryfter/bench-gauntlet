import os
import sys

import typer

app = typer.Typer(help="A gauntlet of trials for local models.")


@app.callback()
def main() -> None:
    """Gauntlet — empirically rate local models per job, at what resource cost."""
    # Reports use Unicode (em-dash for unscored cells); keep console output from
    # garbling on legacy Windows code pages. Guarded — no-op if unsupported.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


@app.command()
def version() -> None:
    """Print the Gauntlet version."""
    from gauntlet import __version__

    typer.echo(__version__)


@app.command()
def targets(config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml")) -> None:
    """List configured targets and the models each exposes (metadata only — no model loads)."""
    from gauntlet import enrich
    from gauntlet.config import load_config

    cfg = load_config(config)
    for t in cfg.targets:
        box = cfg.box_for_target(t.name)
        label = box.hardware if box else "(no box)"
        typer.echo(f"\n{t.name}  [{label}]  {t.base_url}")
        fetch = enrich.REGISTRY.get(t.enrich or "")
        if fetch is None:
            typer.echo("  (no enrichment adapter; OpenAI /v1/models only)")
            continue
        try:
            for m in fetch(t.base_url):
                ctx = f"ctx={m.max_context}" if m.max_context else "ctx=?"
                size = f"{m.size_bytes / 1e9:.1f}GB" if m.size_bytes else "?GB"
                typer.echo(f"  - {m.id:40s} {m.quant or '?':8s} {size:8s} {ctx}")
        except Exception as exc:  # unreachable target must not crash the listing
            typer.echo(f"  ! unreachable: {exc}")


@app.command()
def report(
    scorecard_json: str = typer.Argument(..., help="Path to a scorecard JSON file"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels for sharing"),
    json_out: str = typer.Option(None, "--json-out", help="Also write sanitized JSON here"),
) -> None:
    """Render a Markdown report from a scorecard JSON (optionally sanitized for sharing)."""
    import json as _json
    from pathlib import Path

    from gauntlet.models import Scorecard
    from gauntlet.scorecard import render_markdown, write_json

    data = _json.loads(Path(scorecard_json).read_text(encoding="utf-8"))
    sc = Scorecard.model_validate(data)
    typer.echo(render_markdown(sc, share=share))
    if json_out:
        write_json(sc, json_out, share=share)


@app.command()
def status() -> None:
    """Is Gauntlet using the GPU right now? Also shows what is resident in VRAM.

    Exists so the answer to "why is my machine loud?" never requires reading a
    log file or hunting for a process.
    """
    from gauntlet import vram
    from gauntlet.runstatus import DEFAULT_STATUS_PATH, read_status

    st = read_status(DEFAULT_STATUS_PATH)
    if st is None:
        typer.echo("Gauntlet: idle — no run in progress.")
    elif not st.is_alive:
        typer.echo(f"Gauntlet: idle — run {st.run_id} left a stale marker "
                   f"(pid {st.pid} is gone; it was killed or crashed).")
        typer.echo(f"  last seen: {st.updated_at}  "
                   f"cells: {st.cells_done}/{st.cells_total or '?'}")
        typer.echo(f"  resume with: gauntlet run --resume {st.run_id}")
    else:
        pct = "" if st.progress is None else f" ({st.progress * 100:.0f}%)"
        typer.echo(f"Gauntlet: RUNNING — run {st.run_id} (pid {st.pid})")
        typer.echo(f"  started: {st.started_at}   updated: {st.updated_at}")
        typer.echo(f"  cells:   {st.cells_done}/{st.cells_total or '?'}{pct}")
        if st.model:
            within = (f"  case {st.cases_done}/{st.cases_total}"
                      if st.cases_total else "")
            typer.echo(f"  current: {st.model}  [{st.capability}]{within}")

    loaded = vram.loaded_models()
    if loaded is None:
        typer.echo("\nVRAM: unknown (`lms` not available).")
    elif not loaded:
        typer.echo("\nVRAM: no models loaded.")
    else:
        typer.echo(f"\nVRAM: {len(loaded)} model(s) loaded:")
        for m in loaded:
            typer.echo(f"  - {m}")
        typer.echo("  (Gauntlet frees only the models it loaded; anything else "
                   "is another session's.)")


def _spawn_overlay():
    """Launch the lamp beside a run, or return None if it cannot start.

    Detached and best-effort on purpose: an indicator that fails must never take
    the benchmark down with it. A headless box has no display and simply gets no
    lamp.
    """
    import subprocess
    import sys as _sys

    from gauntlet.overlay import existing_overlay_pid

    if existing_overlay_pid() is not None:
        return None  # one is already up; it reads the same marker

    try:
        kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        return subprocess.Popen([_sys.executable, "-m", "gauntlet.cli", "overlay"], **kwargs)
    except (OSError, subprocess.SubprocessError):
        return None


def _stop_overlay(proc) -> None:
    """Close the lamp when the run ends, so a finished run leaves nothing behind."""
    import subprocess

    try:
        proc.terminate()
        proc.wait(timeout=10)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


@app.command()
def overlay() -> None:
    """Show a small draggable always-on-top lamp for local-model GPU use.

    green = inference running, yellow = a model is resident but idle (power
    spent for nothing), red = nothing loaded. Drag it anywhere; click ✕ or press
    Escape to close. Position is remembered.

    Runs as its own process polling the run marker, so it can never slow down or
    interfere with a benchmark.
    """
    from gauntlet.overlay import existing_overlay_pid, run_overlay

    already = existing_overlay_pid()
    if already is not None:
        typer.echo(f"An overlay is already on screen (pid {already}). "
                   f"A second one would stack invisibly on top of it.")
        raise typer.Exit(code=0)

    try:
        run_overlay()
    except ImportError:
        typer.echo("The overlay needs tkinter, which this Python was built "
                   "without. `gauntlet status` gives the same information.")
        raise typer.Exit(code=1) from None


@app.command()
def release() -> None:
    """Free VRAM left behind by a killed run.

    A run releases the GPU itself on a clean exit, but `finally` does not run
    when the process is SIGKILLed -- which is how an interrupted run usually
    ends. This finishes the job from the status file, which records both halves
    of the snapshot-diff so a model from another session is still never touched.
    """
    from gauntlet import vram
    from gauntlet.runstatus import DEFAULT_STATUS_PATH, clear_status, read_status

    st = read_status(DEFAULT_STATUS_PATH)
    if st is None:
        typer.echo("Nothing to release — no run marker found.")
        raise typer.Exit(code=0)
    if st.is_alive:
        typer.echo(f"Run {st.run_id} is still going (pid {st.pid}). "
                   f"Stop it first; it frees the GPU on a clean exit.")
        raise typer.Exit(code=1)

    if st.vram_before is None:
        typer.echo("Refusing to unload: the run never recorded what was already "
                   "loaded, so anything resident might not be ours.")
        typer.echo("Unload by hand with `lms unload <model>` if you are sure.")
        raise typer.Exit(code=1)

    freed = vram.release_after_run(st.vram_before, st.models_ran)
    if freed:
        typer.echo(f"Released {len(freed)} model(s) from run {st.run_id}:")
        for m in freed:
            typer.echo(f"  - {m}")
    else:
        typer.echo(f"Nothing to release from run {st.run_id} — everything still "
                   f"loaded was already there before it started.")
    clear_status(DEFAULT_STATUS_PATH)


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
    overlay: bool = typer.Option(True, "--overlay/--no-overlay",
                                 help="Show the on-screen GPU-use lamp for the duration of the run"),
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
    from gauntlet.runstatus import DEFAULT_STATUS_PATH
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

    typer.echo(f"Starting run {rid}: this holds the GPU at sustained load until "
               f"it finishes. Check progress from another shell with "
               f"`gauntlet status`; the card is released at the end.")

    lamp = _spawn_overlay() if overlay else None
    cells = execute_plan(cfg, bats, paths, base_dir=prompts, client_factory=factory,
                         only_models=list(models) if models else None,
                         resume=bool(resume_id),
                         status_path=DEFAULT_STATUS_PATH)

    if lamp is not None:
        _stop_overlay(lamp)

    meta = RunMeta(id=rid, date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                   gauntlet_version=__version__)
    write_meta(paths, meta)
    scorecard = assemble_scorecard(meta, paths)
    typer.echo(render_markdown(scorecard, share=share))
    typer.echo(f"\nRan {len(cells)} cell(s). Run dir: {paths.root}")
    if out:
        write_json(scorecard, out, share=share)
        typer.echo(f"Scorecard written to {out}")


@app.command()
def depth(
    config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml"),
    target: str = typer.Option(..., "--target", help="Target name from config"),
    model: str = typer.Option(..., "--model", help="Model id to probe"),
    max_context: int = typer.Option(8192, "--max-context", help="Largest context length to probe"),
    out: str = typer.Option(None, "--out", help="Write/merge the scorecard JSON here"),
    into: str = typer.Option(None, "--into", help="Merge the curve into an existing scorecard JSON"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels when writing"),
) -> None:
    """Measure effective context via needle-at-depth retrieval (special battery)."""
    import os
    from datetime import datetime, timezone

    from gauntlet import __version__
    from gauntlet.batteries.context_depth import run_context_depth
    from gauntlet.client import OpenAIClient
    from gauntlet.config import load_config
    from gauntlet.models import RunMeta, Scorecard
    from gauntlet.scorecard import merge_into_scorecard, write_json

    cfg = load_config(config)
    tgt = cfg.target_by_name(target)
    if tgt is None:
        typer.echo(f"No target named {target!r} in config.")
        raise typer.Exit(code=1)

    # Geometric-ish sweep up to max_context: 512, 1024, ... <= max_context.
    lengths, n = [], 512
    while n <= max_context:
        lengths.append(n)
        n *= 2
    lengths = lengths or [max_context]

    client = OpenAIClient(base_url=tgt.base_url, api_key=os.environ.get("GAUNTLET_API_KEY"))
    try:
        cd = run_context_depth(client, model=model, advertised=max_context, lengths=lengths)
    finally:
        client.close()

    typer.echo(f"{model}: advertised {max_context} -> effective_90pct {cd.effective_90pct}")
    if into:
        merge_into_scorecard(into, context_depth=[cd], share=share)
        typer.echo(f"Merged into {into}")
    if out:
        meta = RunMeta(id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                       date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                       gauntlet_version=__version__)
        write_json(Scorecard(run=meta, context_depth=[cd]), out, share=share)
        typer.echo(f"Scorecard written to {out}")


@app.command()
def embed(
    config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml"),
    target: str = typer.Option(..., "--target", help="Target name from config"),
    model: str = typer.Option(..., "--model", help="Embedding model id"),
    corpus: str = typer.Option("cases/embed/corpus.yaml", "--corpus",
                               help="YAML with keys: corpus[], queries[], relevant[]"),
    k: int = typer.Option(1, "--k", help="recall@k"),
    out: str = typer.Option(None, "--out", help="Write the scorecard JSON here"),
    into: str = typer.Option(None, "--into", help="Merge the embed cell into an existing scorecard"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels when writing"),
) -> None:
    """Evaluate an embedding model by retrieval recall@k over a small corpus."""
    import os
    from datetime import datetime, timezone
    from pathlib import Path

    import yaml

    from gauntlet import __version__
    from gauntlet.batteries.embed import run_embed_cell
    from gauntlet.client import OpenAIClient
    from gauntlet.config import load_config
    from gauntlet.models import RunMeta, Scorecard
    from gauntlet.scorecard import merge_into_scorecard, write_json

    cpath = Path(corpus)
    if not cpath.exists():
        typer.echo(f"Embed corpus file not found: {corpus}")
        raise typer.Exit(code=1)
    spec = yaml.safe_load(cpath.read_text(encoding="utf-8"))

    cfg = load_config(config)
    tgt = cfg.target_by_name(target)
    if tgt is None:
        typer.echo(f"No target named {target!r} in config.")
        raise typer.Exit(code=1)
    box = cfg.box_for_target(target)

    client = OpenAIClient(base_url=tgt.base_url, api_key=os.environ.get("GAUNTLET_API_KEY"))
    try:
        cell = run_embed_cell(client, model=model, target=target,
                              box=box.hardware if box else "(no box)", context=0,
                              corpus=spec["corpus"], queries=spec["queries"],
                              relevant=spec["relevant"], k=k)
    finally:
        client.close()

    typer.echo(f"{model}: embed recall@{k} = {cell.quality}")
    if into:
        merge_into_scorecard(into, cells=[cell], share=share)
        typer.echo(f"Merged into {into}")
    if out:
        meta = RunMeta(id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                       date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                       gauntlet_version=__version__)
        write_json(Scorecard(run=meta, cells=[cell]), out, share=share)
        typer.echo(f"Scorecard written to {out}")


@app.command()
def orchestrate(
    config: str = typer.Option(None, "--config", "-c", help="Path to targets.yaml"),
    batteries: str = typer.Option("batteries", "--batteries", help="Directory of battery YAML files"),
    prompts: str = typer.Option(".", "--prompts", help="Base dir for prompt/schema files"),
    run_id: str = typer.Option(None, "--run-id", help="Run id (default: timestamp)"),
    out: str = typer.Option(None, "--out", help="Write merged scorecard JSON here"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels in the scorecard"),
) -> None:
    """Fan out to ALL configured targets in parallel, then print a compact best-per-capability summary."""
    import os
    from datetime import datetime, timezone

    from gauntlet import __version__
    from gauntlet.battery import load_batteries
    from gauntlet.config import load_config
    from gauntlet.models import RunMeta, Scorecard
    from gauntlet.orchestrate import compact_summary
    from gauntlet.orchestrate import orchestrate as _orchestrate
    from gauntlet.scorecard import write_json

    cfg = load_config(config)
    bats = load_batteries(batteries)
    if not bats:
        typer.echo(f"No batteries found in {batteries}/ — nothing to run.")
        raise typer.Exit(code=0)

    rid = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    api_key = os.environ.get("GAUNTLET_API_KEY")

    targets = list(dict.fromkeys(m.target for m in cfg.models))
    n_models = len(cfg.models)
    n_cells = n_models * len(bats)
    typer.echo(
        f"Orchestrating {n_models} model(s) × {len(bats)} battery/ies"
        f" across {len(targets)} target(s)  [run: {rid}]"
    )
    typer.echo(f"Targets: {', '.join(targets)}\n")

    def progress(target_name: str, n: int, exc) -> None:
        if exc:
            typer.echo(f"  ✗ {target_name}: {exc}", err=True)
        else:
            typer.echo(f"  ✓ {target_name}: {n} cell(s)")

    cells = _orchestrate(cfg, bats, rid, base_dir=prompts, api_key=api_key,
                         progress_cb=progress)

    typer.echo(f"\n{'═' * 60}")
    typer.echo(f"Compact summary — {rid}")
    typer.echo(f"{'═' * 60}\n")
    typer.echo(compact_summary(cells))
    typer.echo(f"\nTotal: {len(cells)} cell(s) across {len(targets)} target(s)")

    if out:
        meta = RunMeta(
            id=rid,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            gauntlet_version=__version__,
        )
        sc = Scorecard(run=meta, cells=cells)
        write_json(sc, out, share=share)
        typer.echo(f"Scorecard written to {out}")


def _frontier_client(base_url: str, api_key: str | None = None):
    """Frontier endpoint client. Separated so tests can patch it with a MockTransport."""
    from gauntlet.client import OpenAIClient
    return OpenAIClient(base_url=base_url, api_key=api_key)


@app.command()
def baseline(
    capability: str = typer.Option(..., "--capability", help="Capability to baseline (battery capability)"),
    sample: int = typer.Option(3, "--sample", help="Number of cases to sample from the battery"),
    batteries: str = typer.Option("batteries", "--batteries", help="Directory of battery YAML files"),
    prompts: str = typer.Option(".", "--prompts", help="Base dir for case prompt/schema files"),
    frontier_url: str = typer.Option(..., "--frontier-url", help="Frontier OpenAI-compatible base URL"),
    frontier_model: str = typer.Option(..., "--frontier-model", help="Frontier model id"),
    local: str = typer.Option(None, "--local", help="Local scorecard JSON to compare against"),
    into: str = typer.Option(None, "--into", help="Write baseline_gaps into this scorecard JSON"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels when writing"),
) -> None:
    """Opt-in frontier comparison. Costs money — gated behind GAUNTLET_FRONTIER_API_KEY;
    with no key set it prints guidance and exits without calling anything."""
    import os
    from pathlib import Path

    from datetime import datetime, timezone

    from gauntlet import __version__
    from gauntlet.baseline import compute_gaps
    from gauntlet.battery import load_batteries
    from gauntlet.models import RunMeta, Scorecard
    from gauntlet.runner import run_cell
    from gauntlet.scorecard import write_json

    key = os.environ.get("GAUNTLET_FRONTIER_API_KEY")
    if not key:
        typer.echo("Frontier baseline is opt-in and costs money. Set GAUNTLET_FRONTIER_API_KEY "
                   "to enable it. Skipped.")
        raise typer.Exit(code=0)

    bats = {b.capability: b for b in load_batteries(batteries)}
    battery = bats.get(capability)
    if battery is None:
        typer.echo(f"No battery for capability {capability!r} in {batteries}/.")
        raise typer.Exit(code=1)

    # Sample N cases into a sub-battery.
    sampled = battery.model_copy(update={"cases": battery.cases[:max(1, sample)]})

    client = _frontier_client(frontier_url, api_key=key)
    try:
        fcell = run_cell(client, model=frontier_model, target=None, box="frontier",
                         context=0, battery=sampled, base_dir=prompts)
    finally:
        client.close()
    typer.echo(f"frontier {frontier_model}: {capability} quality = {fcell.quality}")

    local_sc = None
    local_cells = []
    if local:
        local_sc = Scorecard.model_validate_json(Path(local).read_text(encoding="utf-8"))
        local_cells = local_sc.cells
    gaps = compute_gaps(local_cells, [fcell])
    for g in gaps:
        typer.echo(f"  gap[{g.capability}] champion={g.local_champion} vs {g.frontier}: {g.gap:+.3f}")

    if into:
        # Merge into an existing scorecard if present; otherwise seed from the local
        # scorecard (so champions stay visible) or a fresh run.
        if Path(into).exists():
            out_sc = Scorecard.model_validate_json(Path(into).read_text(encoding="utf-8"))
        elif local_sc is not None:
            out_sc = local_sc
        else:
            out_sc = Scorecard(run=RunMeta(
                id=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                gauntlet_version=__version__))
        out_sc.cells.append(fcell)
        out_sc.baseline_gaps.extend(gaps)
        write_json(out_sc, into, share=share)
        typer.echo(f"Wrote baseline into {into}")


def _yaml_scalar(value: str) -> str:
    """Single-quote a YAML scalar — YAML single-quoted strings are fully literal
    (backslashes are not escape characters), so regex patterns survive round-trips."""
    return "'" + value.replace("'", "''") + "'"


@app.command("add-case")
def add_case(
    capability: str = typer.Argument(..., help="Battery capability to extend (e.g. commit-msg, code-gen)"),
    batteries_dir: str = typer.Option("batteries", "--batteries", help="Directory of battery YAML files"),
    prompts_dir: str = typer.Option(".", "--prompts", help="Base dir for prompt_file paths"),
    from_file: str = typer.Option(None, "--from-file", help="Read prompt text from this file instead of stdin"),
) -> None:
    """Add a new test case to an existing battery interactively."""
    import re
    import sys
    from pathlib import Path

    from gauntlet.battery import load_battery

    bat_path = Path(batteries_dir) / f"{capability}.yaml"
    if not bat_path.exists():
        known = sorted(p.stem for p in Path(batteries_dir).glob("*.yaml")) if Path(batteries_dir).is_dir() else []
        typer.echo(
            f"No battery '{capability}' in {batteries_dir}/."
            + (f"  Known: {', '.join(known)}" if known else "  (directory is empty)")
        )
        raise typer.Exit(code=1)

    battery = load_battery(bat_path)
    existing_ids = {c.id for c in battery.cases}

    # --- Case ID ---
    while True:
        case_id = typer.prompt("Case ID").strip()
        if not case_id:
            typer.echo("Case ID cannot be empty.")
            continue
        if "/" in case_id or "\\" in case_id:
            typer.echo("Case ID must not contain slashes.")
            continue
        if case_id in existing_ids:
            typer.echo(f"'{case_id}' already exists in {capability}. Use a different ID.")
            continue
        break

    # --- Scoring method ---
    valid_methods = ("exact", "regex", "json-schema", "conventional-commit", "compilable-code", "judge")
    typer.echo(f"Scoring methods: {', '.join(valid_methods)}")
    while True:
        scoring = typer.prompt("Scoring", default="compilable-code").strip()
        if scoring in valid_methods:
            break
        typer.echo(f"Unknown method. Choose from: {', '.join(valid_methods)}")

    # --- Scorer-specific extras ---
    extra: dict[str, str] = {}
    if scoring == "exact":
        extra["expect"] = typer.prompt("Expected output (exact match after stripping fences)").strip()
    elif scoring == "regex":
        extra["pattern"] = typer.prompt("Regex pattern (re.search)").strip()
    elif scoring == "judge":
        extra["rubric"] = typer.prompt("Judge rubric").strip()
    elif scoring == "json-schema":
        schema_rel = f"cases/{capability}/{case_id}.schema.json"
        extra["schema_file"] = schema_rel
        typer.echo(f"Schema file: create {Path(prompts_dir) / schema_rel} before running.")

    # --- Prompt text ---
    prompt_rel = f"cases/{capability}/{case_id}.txt"
    prompt_abs = Path(prompts_dir) / prompt_rel
    prompt_abs.parent.mkdir(parents=True, exist_ok=True)

    if from_file:
        src = Path(from_file)
        if not src.exists():
            typer.echo(f"File not found: {from_file}")
            raise typer.Exit(code=1)
        prompt_abs.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        typer.echo("Prompt text (blank line to finish):")
        lines: list[str] = []
        while True:
            line = sys.stdin.readline()
            if line in ("", "\n"):
                break
            lines.append(line.rstrip("\n"))
        if not lines:
            typer.echo("Prompt cannot be empty.")
            raise typer.Exit(code=1)
        prompt_abs.write_text("\n".join(lines) + "\n", encoding="utf-8")

    typer.echo(f"→ Wrote {prompt_abs}")

    # --- Build case YAML block (2-space indent to match battery format) ---
    block = f"  - id: {case_id}\n"
    block += f"    prompt_file: {prompt_rel}\n"
    block += f"    scoring: {scoring}\n"
    for key, val in extra.items():
        block += f"    {key}: {_yaml_scalar(val)}\n"

    # --- Insert into battery YAML while preserving existing formatting ---
    raw = bat_path.read_text(encoding="utf-8")
    m = re.search(r"\ncases:\s*\[\]", raw)   # handle empty flow-sequence
    if m:
        raw = raw[: m.start()] + "\ncases:\n" + block.rstrip("\n") + raw[m.end():]
    else:
        idx = raw.rfind("\nweights:")
        if idx == -1:
            raw = raw.rstrip("\n") + "\n" + block
        else:
            raw = raw[:idx] + "\n" + block + raw[idx:]
    bat_path.write_text(raw, encoding="utf-8")

    typer.echo(f"→ Added case '{case_id}' to {bat_path}")


if __name__ == "__main__":
    app()
