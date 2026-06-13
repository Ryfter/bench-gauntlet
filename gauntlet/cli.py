import typer

app = typer.Typer(help="A gauntlet of trials for local models.")


@app.callback()
def main() -> None:
    """Gauntlet — empirically rate local models per job, at what resource cost."""


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


if __name__ == "__main__":
    app()
