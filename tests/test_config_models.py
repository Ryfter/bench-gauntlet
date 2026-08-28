import pytest
from pydantic import ValidationError

from gauntlet import errors
from gauntlet.config import GauntletConfig


def _cfg() -> GauntletConfig:
    return GauntletConfig.model_validate(
        {
            "targets": [
                {"name": "box-a-lmstudio", "base_url": "http://localhost:1234",
                 "api": "openai", "enrich": "lmstudio", "box": "box-a"},
            ],
            "boxes": [
                {"id": "box-a", "hardware": "RTX 5090 desktop", "vram_gb": 32,
                 "usage_class": "broad", "busy": False},
            ],
            "models": [
                {"target": "box-a-lmstudio", "id": "google/gemma-4-31b", "context": 8192},
            ],
            "keep_list": ["*heretic*", "*swahili*"],
        }
    )


def test_box_lookup_by_target_returns_hardware():
    cfg = _cfg()
    box = cfg.box_for_target("box-a-lmstudio")
    assert box is not None
    assert box.hardware == "RTX 5090 desktop"
    assert box.usage_class == "broad"


def test_keep_list_globs_match_case_insensitively():
    cfg = _cfg()
    assert cfg.is_kept("gemma-3-12b-it-heretic-v2") is True
    assert cfg.is_kept("Some-Swahili-Tutor") is True
    assert cfg.is_kept("google/gemma-4-31b") is False


def test_defaults_are_safe():
    box = GauntletConfig.model_validate(
        {"boxes": [{"id": "x", "hardware": "h", "vram_gb": 8}]}
    ).boxes[0]
    assert box.usage_class == "broad"
    assert box.busy is False


@pytest.mark.parametrize("data", [
    {"targets": [{"name": "t", "base_url": "http://localhost", "box": "missing"}]},
    {"models": [{"target": "missing", "id": "m", "context": 1}]},
])
def test_config_rejects_unresolved_target_and_box_references(data):
    with pytest.raises(ValidationError):
        GauntletConfig.model_validate(data)


def test_orchestrate_rejects_empty_model_fleet():
    from gauntlet.orchestrate import orchestrate

    cfg = GauntletConfig.model_validate({
        "targets": [{"name": "t", "base_url": "http://localhost", "box": "x"}],
        "boxes": [{"id": "x", "hardware": "h", "vram_gb": 8}],
        "models": [],
    })
    with pytest.raises(errors.GauntletError, match="model"):
        orchestrate(cfg, batteries=[], run_id="r1", base_dir=".", api_key=None)


def test_require_runnable_target_fails_closed_for_busy_box():
    cfg = _cfg()
    cfg.boxes[0].busy = True
    with pytest.raises(errors.BoxBusy):
        cfg.require_runnable_target("box-a-lmstudio")
