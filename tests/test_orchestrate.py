"""Tests for compact_summary — pure logic, no network."""
from gauntlet.models import Cell
from gauntlet.orchestrate import compact_summary


def _cell(cap, model, quality, pass_rate, tps=None, box="RTX 5090"):
    return Cell(capability=cap, model=model, target="t", box=box,
                context=8192, quality=quality, pass_rate=pass_rate,
                tokens_per_s=tps, latency_p50_s=None, errors=0, cases=5)


def test_compact_summary_picks_best_per_capability():
    cells = [
        _cell("code-gen", "gemma3:27b", 1.00, 1.00, tps=25),
        _cell("code-gen", "phi4:14b",   0.80, 0.80, tps=60),
        _cell("commit-msg", "devstral:latest", 1.00, 1.00, tps=22),
        _cell("commit-msg", "phi4:14b",         0.60, 0.60, tps=60),
    ]
    out = compact_summary(cells)
    lines = out.splitlines()
    # header + sep + 2 data rows
    assert len(lines) == 4
    code_row = next(l for l in lines if "code-gen" in l)
    assert "gemma3:27b" in code_row
    commit_row = next(l for l in lines if "commit-msg" in l)
    assert "devstral" in commit_row


def test_compact_summary_excludes_none_quality():
    cells = [
        _cell("code-gen", "good-model", 1.00, 1.00),
        _cell("code-gen", "broken",     None, 0.00),
    ]
    out = compact_summary(cells)
    assert "good-model" in out
    assert "broken" not in out


def test_compact_summary_marks_unscored_caps():
    cells = [
        _cell("code-gen", "m", 1.00, 1.00),
        _cell("summarize-short", "m", None, 0.00),  # all unscored
    ]
    out = compact_summary(cells)
    assert "unscored" in out
    assert "summarize-short" in out


def test_compact_summary_empty():
    assert "no scored" in compact_summary([])


def test_compact_summary_truncates_long_model_names():
    long_name = "a" * 50
    cells = [_cell("code-gen", long_name, 1.00, 1.00)]
    out = compact_summary(cells)
    assert long_name not in out      # truncated
    assert "a" * 33 in out           # prefix present
