import json

from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def _config(tmp_path, port=65000):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        f"  - {{name: box-b, base_url: 'http://127.0.0.1:{port}', box: box-b}}\n"
        "boxes:\n"
        "  - {id: box-b, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: broad}\n"
        "models:\n"
        "  - {target: box-b, id: 'gemma3:1b', context: 4096}\n",
        encoding="utf-8",
    )
    return cfg


def test_depth_command_unreachable_writes_zero_curve(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _config(tmp_path)
    out = tmp_path / "depth.json"
    result = runner.invoke(app, ["depth", "--config", str(cfg), "--target", "box-b",
                                 "--model", "gemma3:1b", "--max-context", "2048",
                                 "--out", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    # unreachable -> no retrieval -> effective_90pct 0, but the command still emits.
    assert data["context_depth"][0]["effective_90pct"] == 0


def test_embed_command_missing_corpus_exits_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _config(tmp_path)
    result = runner.invoke(app, ["embed", "--config", str(cfg), "--target", "box-b",
                                 "--model", "nomic-embed", "--corpus", str(tmp_path / "nope.yaml")])
    assert result.exit_code != 0
    assert "corpus" in result.output.lower()


def _battery_dir(tmp_path):
    bdir = tmp_path / "batteries"
    bdir.mkdir(exist_ok=True)
    (tmp_path / "p.txt").write_text("write a conventional commit", encoding="utf-8")
    (bdir / "commit.yaml").write_text(
        "capability: commit-msg\ncontext_floor: 0\n"
        "cases:\n  - {id: c1, scoring: conventional-commit, prompt_file: p.txt}\n",
        encoding="utf-8")
    return bdir


def test_baseline_without_key_is_skipped_not_crash(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GAUNTLET_FRONTIER_API_KEY", raising=False)
    bdir = _battery_dir(tmp_path)
    result = runner.invoke(app, ["baseline", "--capability", "commit-msg", "--sample", "1",
                                 "--batteries", str(bdir), "--prompts", str(tmp_path),
                                 "--frontier-url", "http://127.0.0.1:65000/v1",
                                 "--frontier-model", "frontier-x"])
    assert result.exit_code == 0
    assert "GAUNTLET_FRONTIER_API_KEY" in result.output      # clear guidance


def test_baseline_with_key_runs_and_writes_gaps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GAUNTLET_FRONTIER_API_KEY", "sk-test")
    bdir = _battery_dir(tmp_path)
    # a local scorecard with one commit-msg cell to compare against
    local = tmp_path / "local.json"
    local.write_text(json.dumps({
        "run": {"id": "r", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        "cells": [{"model": "small-a", "target": "t", "box": "b", "context": 4096,
                   "capability": "commit-msg", "quality": 0.7, "pass_rate": 0.7,
                   "cases": 1, "errors": 0}],
        "context_depth": [], "baseline_gaps": [],
    }), encoding="utf-8")
    out = tmp_path / "with_gaps.json"

    # Patch the frontier client factory to a MockTransport returning a good commit.
    import httpx

    import gauntlet.cli as cli_mod

    def fake_client(base_url, api_key=None):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": "feat: add x"}}],
                                             "usage": {"completion_tokens": 4}})
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(cli_mod, "_frontier_client", fake_client, raising=False)

    result = runner.invoke(app, ["baseline", "--capability", "commit-msg", "--sample", "1",
                                 "--batteries", str(bdir), "--prompts", str(tmp_path),
                                 "--frontier-url", "http://f/v1", "--frontier-model", "frontier-x",
                                 "--local", str(local), "--into", str(out)])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["baseline_gaps"][0]["capability"] == "commit-msg"
    assert data["baseline_gaps"][0]["local_champion"] == "small-a"
