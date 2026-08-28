import json
import os
from pathlib import Path

import pytest

from gauntlet import errors
from gauntlet.models import CaseResult, Cell, RunMeta
from gauntlet.runner import (
    RunPaths,
    append_case_rows,
    append_cell,
    assemble_scorecard,
    cell_key,
    read_completed,
    write_meta,
)


def _cell(cap):
    return Cell(model="gemma3:1b", target="box-b", box="RTX 2070 Super laptop",
                context=4096, capability=cap, quality=1.0, pass_rate=1.0, cases=1)


def test_cell_key_identity():
    assert cell_key(_cell("commit-msg")) == ("box-b", "gemma3:1b", 4096, "commit-msg")


def test_append_and_read_completed_roundtrip(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    append_cell(paths, _cell("extract-json"))
    done = read_completed(paths)
    assert done == {
        ("box-b", "gemma3:1b", 4096, "commit-msg"),
        ("box-b", "gemma3:1b", 4096, "extract-json"),
    }


def test_read_completed_missing_file_is_empty(tmp_path):
    paths = RunPaths(tmp_path / "nope")
    assert read_completed(paths) == set()


def test_write_meta_writes_json(tmp_path):
    paths = RunPaths(tmp_path / "run-2")
    paths.ensure()
    write_meta(paths, RunMeta(id="run-2", date="2026-06-13", gauntlet_version="0.1.0"))
    assert paths.meta.exists()
    assert "run-2" in paths.meta.read_text(encoding="utf-8")


def test_run_paths_refuse_private_ledgers_inside_tracked_tree():
    paths = RunPaths(Path(__file__).resolve().parents[1] / "scorecards" / "leak")
    with pytest.raises(errors.GauntletError, match="private run data"):
        paths.ensure()


@pytest.mark.parametrize("run_id", [
    "", ".", "..", "../public", "nested/run", r"nested\run", "/absolute",
])
def test_private_run_paths_reject_unsafe_run_id_components(tmp_path, run_id):
    with pytest.raises(errors.GauntletError, match="safe run id"):
        RunPaths.for_run_id(run_id, private_root=tmp_path)


def test_private_run_paths_confine_every_ledger_beneath_private_root(tmp_path):
    private_root = tmp_path / "private"
    paths = RunPaths.for_run_id("run-1", private_root=private_root)
    paths.ensure()
    resolved_root = private_root.resolve()
    assert paths.root.parent == resolved_root
    assert all(path.resolve().is_relative_to(resolved_root)
               for path in (paths.cells, paths.cases, paths.meta))


def test_private_run_paths_reject_symlink_escape(tmp_path):
    private_root = tmp_path / "private"
    outside = tmp_path / "outside"
    private_root.mkdir()
    outside.mkdir()
    (private_root / "run-1").symlink_to(outside, target_is_directory=True)
    paths = RunPaths.for_run_id("run-1", private_root=private_root)
    with pytest.raises(errors.GauntletError, match="private run root"):
        paths.ensure()


def test_private_run_paths_reject_unsafe_namespace(tmp_path):
    with pytest.raises(errors.GauntletError, match="safe run id"):
        RunPaths.for_run_id("run-1", namespace="../target", private_root=tmp_path)


def test_read_completed_skips_torn_trailing_line(tmp_path):
    """A kill mid-append must not block resume of already-committed cells."""
    paths = RunPaths(tmp_path / "run-torn")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    with paths.cells.open("a", encoding="utf-8") as fh:
        fh.write('{"model":"partial"')
    done = read_completed(paths)
    assert done == {("box-b", "gemma3:1b", 4096, "commit-msg")}


def test_assemble_scorecard_skips_torn_trailing_line(tmp_path):
    paths = RunPaths(tmp_path / "run-torn-assemble")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    with paths.cells.open("a", encoding="utf-8") as fh:
        fh.write('{"model":"partial"')
    sc = assemble_scorecard(
        RunMeta(id="run-torn-assemble", date="2026-08-28", gauntlet_version="0.1.0"),
        paths,
    )
    assert [c.capability for c in sc.cells] == ["commit-msg"]


def test_append_cell_is_idempotent_for_the_same_key(tmp_path):
    paths = RunPaths(tmp_path / "run-upsert-cell")
    paths.ensure()
    first = _cell("commit-msg")
    retry = first.model_copy(update={"quality": 0.5, "pass_rate": 0.5})
    append_cell(paths, first)
    append_cell(paths, retry)
    lines = [line for line in paths.cells.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    done = read_completed(paths)
    assert done == {("box-b", "gemma3:1b", 4096, "commit-msg")}
    sc = assemble_scorecard(
        RunMeta(id="run-upsert-cell", date="2026-08-28", gauntlet_version="0.1.0"),
        paths,
    )
    assert sc.cells[0].quality == 0.5


def test_append_case_rows_is_idempotent_for_the_same_case_key(tmp_path):
    paths = RunPaths(tmp_path / "run-upsert-cases")
    paths.ensure()
    first = [CaseResult(case_id="c1", method="exact", score=0.0, passed=False)]
    retry = [CaseResult(case_id="c1", method="exact", score=1.0, passed=True)]
    kwargs = dict(model="gemma3:1b", target="box-b", context=4096, capability="commit-msg")
    append_case_rows(paths, results=first, **kwargs)
    append_case_rows(paths, results=retry, **kwargs)
    rows = [
        json.loads(line)
        for line in paths.cases.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    assert rows[0]["score"] == 1.0
    assert rows[0]["case_id"] == "c1"


def test_write_meta_crash_before_commit_keeps_prior_snapshot(tmp_path, monkeypatch):
    """Snapshots must not replace the live file until the new bytes are complete."""
    paths = RunPaths(tmp_path / "run-meta")
    paths.ensure()
    write_meta(paths, RunMeta(id="first", date="2026-01-01", gauntlet_version="0.1.0"))
    original = paths.meta.read_text(encoding="utf-8")

    def boom(src, dst, *args, **kwargs):
        raise OSError("injected crash before commit")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="injected crash"):
        write_meta(paths, RunMeta(id="second", date="2026-01-02", gauntlet_version="0.1.0"))
    assert paths.meta.read_text(encoding="utf-8") == original
    assert "second" not in original
