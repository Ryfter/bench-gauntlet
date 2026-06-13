from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def test_targets_lists_models(tmp_path, monkeypatch):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        "  - { name: wraith2-ollama, base_url: 'http://h:11434', enrich: ollama, box: wraith2 }\n"
        "boxes:\n"
        "  - { id: wraith2, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: tight }\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GAUNTLET_CONFIG", str(cfg))

    # Patch the enrich registry so no network is touched in this unit test.
    from gauntlet import enrich
    from gauntlet.enrich import ModelMeta
    monkeypatch.setitem(
        enrich.REGISTRY, "ollama",
        lambda base_url, transport=None: [ModelMeta(id="gemma3:1b", size_bytes=815319791)],
    )

    result = runner.invoke(app, ["targets"])
    assert result.exit_code == 0
    assert "wraith2-ollama" in result.stdout
    assert "gemma3:1b" in result.stdout
    assert "RTX 2070 Super laptop" in result.stdout
