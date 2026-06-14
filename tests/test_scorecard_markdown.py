from gauntlet.models import Cell, Scorecard
from gauntlet.scorecard import render_markdown


def _sc() -> Scorecard:
    return Scorecard(
        run={"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        cells=[
            Cell(model="gemma3:1b", target="box-b-ollama", box="RTX 2070 Super laptop",
                 context=8192, capability="extract-json", quality=0.91, pass_rate=0.86,
                 latency_p50_s=2.1, tokens_per_s=38.0, cases=14, errors=0),
            Cell(model="dolphin3:8b", target="box-b-ollama", box="RTX 2070 Super laptop",
                 context=8192, capability="extract-json", quality=None, pass_rate=None,
                 cases=2, errors=2),
        ],
    )


def test_markdown_has_run_header_and_rows():
    md = render_markdown(_sc(), share=True)
    assert "# Gauntlet scorecard" in md
    assert "r1" in md and "2026-06-13" in md
    assert "gemma3:1b" in md
    assert "RTX 2070 Super laptop" in md
    # share mode must not print the hostname label
    assert "box-b-ollama" not in md


def test_markdown_renders_unscored_as_dash():
    md = render_markdown(_sc(), share=True)
    # the dolphin row has quality=None -> rendered as "—", not "0"
    assert "—" in md
