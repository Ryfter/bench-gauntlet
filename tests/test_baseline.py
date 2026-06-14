from gauntlet.baseline import compute_gaps
from gauntlet.models import Cell


def _cell(model, capability, quality):
    return Cell(model=model, target="t", box="b", context=4096,
                capability=capability, quality=quality, pass_rate=quality, cases=5)


def test_compute_gaps_picks_local_champion_per_capability():
    local = [
        _cell("small-a", "commit-msg", 0.80),
        _cell("small-b", "commit-msg", 0.88),   # champion for commit-msg
        _cell("small-c", "extract-json", 0.50),
    ]
    frontier = [
        _cell("claude", "commit-msg", 0.91),
        _cell("claude", "extract-json", 0.95),
    ]
    gaps = {g.capability: g for g in compute_gaps(local, frontier)}
    assert gaps["commit-msg"].local_champion == "small-b"
    assert abs(gaps["commit-msg"].gap - 0.03) < 1e-9      # 0.91 - 0.88
    assert gaps["extract-json"].local_champion == "small-c"
    assert abs(gaps["extract-json"].gap - 0.45) < 1e-9


def test_compute_gaps_ignores_capabilities_without_frontier():
    local = [_cell("small-a", "ocr", 0.4)]
    frontier = [_cell("claude", "commit-msg", 0.9)]
    assert compute_gaps(local, frontier) == []


def test_compute_gaps_skips_unscored_local_cells():
    local = [_cell("scored", "commit-msg", 0.7),
             Cell(model="unscored", target="t", box="b", context=4096,
                  capability="commit-msg", quality=None, pass_rate=None, cases=5)]
    frontier = [_cell("claude", "commit-msg", 0.9)]
    gaps = compute_gaps(local, frontier)
    assert len(gaps) == 1
    assert gaps[0].local_champion == "scored"
