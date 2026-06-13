from gauntlet.models import Cell, RunMeta
from gauntlet.runner import RunPaths, append_cell, assemble_scorecard


def _cell(cap):
    return Cell(model="gemma3:1b", target="wraith2", box="RTX 2070 Super laptop",
                context=4096, capability=cap, quality=1.0, pass_rate=1.0, cases=1)


def test_assemble_scorecard_reads_all_cells(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    append_cell(paths, _cell("extract-json"))
    run = RunMeta(id="run-1", date="2026-06-13", gauntlet_version="0.1.0")
    sc = assemble_scorecard(run, paths)
    assert sc.run.id == "run-1"
    assert {c.capability for c in sc.cells} == {"commit-msg", "extract-json"}
    assert sc.context_depth == []
    assert sc.baseline_gaps == []
