import json

from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()

CARD = {
    "run": {"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
    "cells": [{"model": "gemma3:1b", "target": "box-b-ollama",
               "box": "RTX 2070 Super laptop", "context": 8192,
               "capability": "extract-json", "quality": 0.9, "pass_rate": 0.9,
               "latency_p50_s": 2.0, "tokens_per_s": 38.0, "judge": None,
               "cases": 10, "errors": 0}],
    "context_depth": [], "baseline_gaps": [],
}


def test_report_prints_markdown(tmp_path):
    src = tmp_path / "card.json"
    src.write_text(json.dumps(CARD), encoding="utf-8")
    result = runner.invoke(app, ["report", str(src)])
    assert result.exit_code == 0
    assert "# Gauntlet scorecard" in result.stdout
    assert "gemma3:1b" in result.stdout


def test_report_share_writes_sanitized_json(tmp_path):
    src = tmp_path / "card.json"
    src.write_text(json.dumps(CARD), encoding="utf-8")
    out = tmp_path / "shared.json"
    result = runner.invoke(app, ["report", str(src), "--share", "--json-out", str(out)])
    assert result.exit_code == 0
    shared = json.loads(out.read_text(encoding="utf-8"))
    assert "target" not in shared["cells"][0]
    assert shared["cells"][0]["box"] == "RTX 2070 Super laptop"
