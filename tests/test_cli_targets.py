from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()


def test_targets_lists_models(tmp_path, monkeypatch):
    cfg = tmp_path / "targets.yaml"
    cfg.write_text(
        "targets:\n"
        "  - { name: box-b-ollama, base_url: 'http://h:11434', enrich: ollama, box: box-b }\n"
        "boxes:\n"
        "  - { id: box-b, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: tight }\n",
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
    assert "box-b-ollama" in result.stdout
    assert "gemma3:1b" in result.stdout
    assert "RTX 2070 Super laptop" in result.stdout
