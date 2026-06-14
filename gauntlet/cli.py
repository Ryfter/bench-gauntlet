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


if __name__ == "__main__":
    app()
