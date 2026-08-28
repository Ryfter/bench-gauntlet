from pathlib import Path

import pytest

from gauntlet import errors
from gauntlet.models import Cell, RunMeta
from gauntlet.runner import RunPaths, append_cell, cell_key, read_completed, write_meta


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
