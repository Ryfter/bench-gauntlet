from gauntlet.models import Cell, RunMeta
from gauntlet.runner import RunPaths, append_cell, cell_key, read_completed, write_meta


def _cell(cap):
    return Cell(model="gemma3:1b", target="wraith2", box="RTX 2070 Super laptop",
                context=4096, capability=cap, quality=1.0, pass_rate=1.0, cases=1)


def test_cell_key_identity():
    assert cell_key(_cell("commit-msg")) == ("wraith2", "gemma3:1b", 4096, "commit-msg")


def test_append_and_read_completed_roundtrip(tmp_path):
    paths = RunPaths(tmp_path / "run-1")
    paths.ensure()
    append_cell(paths, _cell("commit-msg"))
    append_cell(paths, _cell("extract-json"))
    done = read_completed(paths)
    assert done == {
        ("wraith2", "gemma3:1b", 4096, "commit-msg"),
        ("wraith2", "gemma3:1b", 4096, "extract-json"),
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
