from gauntlet.battery import Battery, Case
from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
from gauntlet.sequencer import build_cells, model_family


def _cfg():
    return GauntletConfig(
        targets=[Target(name="wraith2", base_url="http://w:1", enrich="ollama", box="wraith2")],
        boxes=[Box(id="wraith2", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="tight")],
        models=[
            ModelProfile(target="wraith2", id="gemma3:1b", context=4096),
            ModelProfile(target="wraith2", id="qwen2.5:7b", context=8192),
        ],
        keep_list=["*embed*"],
    )


def _batteries():
    return [
        Battery(capability="commit-msg", context_floor=0,
                cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p1.txt")]),
        Battery(capability="long-ctx", context_floor=8000,
                cases=[Case(id="c2", scoring="exact", expect="ok", prompt_file="p2.txt")]),
    ]


def test_model_family_splits_on_colon():
    assert model_family("gemma3:1b") == "gemma3"
    assert model_family("dolphin3:8b") == "dolphin3"
    assert model_family("plain-model") == "plain-model"


def test_build_cells_applies_context_floor():
    cells = build_cells(_cfg(), _batteries())
    # gemma3@4096 -> only commit-msg (long-ctx floor 8000 excludes it)
    gemma = [c for c in cells if c.model == "gemma3:1b"]
    assert {c.capability for c in gemma} == {"commit-msg"}
    # qwen@8192 -> both batteries apply
    qwen = [c for c in cells if c.model == "qwen2.5:7b"]
    assert {c.capability for c in qwen} == {"commit-msg", "long-ctx"}


def test_build_cells_resolves_box_label():
    cells = build_cells(_cfg(), _batteries())
    assert all(c.box_hardware == "RTX 2070 Super laptop" for c in cells)
    assert all(c.box_id == "wraith2" for c in cells)


def test_build_cells_excludes_keep_list_unless_named():
    cfg = _cfg()
    cfg.models.append(ModelProfile(target="wraith2", id="nomic-embed-text", context=2048))
    # keep_list glob *embed* matches -> excluded by default
    assert not any(c.model == "nomic-embed-text" for c in build_cells(cfg, _batteries()))
    # named explicitly -> included
    cells = build_cells(cfg, _batteries(), only_models=["nomic-embed-text"])
    assert all(c.model == "nomic-embed-text" for c in cells)
