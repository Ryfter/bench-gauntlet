import json

from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def _write_config(tmp_path):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        "  - {name: box-b, base_url: 'http://127.0.0.1:65000', box: box-b}\n"
        "boxes:\n"
        "  - {id: box-b, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: broad}\n"
        "models:\n"
        "  - {target: box-b, id: 'gemma3:1b', context: 4096}\n",
        encoding="utf-8",
    )
    return cfg


def _write_battery(tmp_path):
    bdir = tmp_path / "batteries"
    bdir.mkdir()
    (tmp_path / "p.txt").write_text("write a commit message", encoding="utf-8")
    (bdir / "commit.yaml").write_text(
        "capability: commit-msg\n"
        "context_floor: 0\n"
        "cases:\n"
        "  - {id: c1, scoring: conventional-commit, prompt_file: p.txt}\n",
        encoding="utf-8",
    )
    return bdir


def test_run_unreachable_target_writes_scorecard_and_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _write_config(tmp_path)
    bdir = _write_battery(tmp_path)
    out = tmp_path / "card.json"
    # 127.0.0.1:65000 is closed -> Unreachable -> errored cell, run still completes.
    result = runner.invoke(app, [
        "run", "--config", str(cfg), "--batteries", str(bdir),
        "--prompts", str(tmp_path), "--out", str(out), "--run-id", "test-run",
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["run"]["id"] == "test-run"
    assert len(data["cells"]) == 1
    assert data["cells"][0]["errors"] == 1
