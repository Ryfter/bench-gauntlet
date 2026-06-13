import pytest

from gauntlet import errors
from gauntlet.config import config_path, load_config


def test_explicit_flag_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("GAUNTLET_CONFIG", str(tmp_path / "env.yaml"))
    explicit = tmp_path / "explicit.yaml"
    assert config_path(str(explicit)) == explicit


def test_env_var_used_when_no_flag(tmp_path, monkeypatch):
    env = tmp_path / "env.yaml"
    monkeypatch.setenv("GAUNTLET_CONFIG", str(env))
    assert config_path(None) == env


def test_missing_config_raises_config_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("GAUNTLET_CONFIG", str(tmp_path / "absent.yaml"))
    with pytest.raises(errors.ConfigNotFound):
        load_config()


def test_load_parses_yaml(tmp_path, monkeypatch):
    cfg_file = tmp_path / "targets.yaml"
    cfg_file.write_text(
        "targets:\n"
        "  - { name: t1, base_url: 'http://x:1', enrich: ollama, box: b1 }\n"
        "boxes:\n"
        "  - { id: b1, hardware: 'RTX 2070 Super laptop', vram_gb: 8, usage_class: tight }\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GAUNTLET_CONFIG", str(cfg_file))
    cfg = load_config()
    assert cfg.box_for_target("t1").hardware == "RTX 2070 Super laptop"


def test_malformed_yaml_raises_config_invalid(tmp_path, monkeypatch):
    cfg_file = tmp_path / "targets.yaml"
    cfg_file.write_text("targets: [ { name: t1 ", encoding="utf-8")  # broken
    monkeypatch.setenv("GAUNTLET_CONFIG", str(cfg_file))
    with pytest.raises(errors.ConfigInvalid):
        load_config()
