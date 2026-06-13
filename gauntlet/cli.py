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


if __name__ == "__main__":
    app()
