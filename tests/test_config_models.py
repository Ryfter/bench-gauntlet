from gauntlet.config import GauntletConfig


def _cfg() -> GauntletConfig:
    return GauntletConfig.model_validate(
        {
            "targets": [
                {"name": "firefly-lmstudio", "base_url": "http://localhost:1234",
                 "api": "openai", "enrich": "lmstudio", "box": "firefly"},
            ],
            "boxes": [
                {"id": "firefly", "hardware": "RTX 5090 desktop", "vram_gb": 32,
                 "usage_class": "broad", "busy": False},
            ],
            "models": [
                {"target": "firefly-lmstudio", "id": "google/gemma-4-31b", "context": 8192},
            ],
            "keep_list": ["*heretic*", "*swahili*"],
        }
    )


def test_box_lookup_by_target_returns_hardware():
    cfg = _cfg()
    box = cfg.box_for_target("firefly-lmstudio")
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
