from gauntlet.battery import Battery, Case
from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
from gauntlet.sequencer import (
    build_cells,
    estimate_footprint_gb,
    model_family,
    plan_run,
)


def _cfg():
    return GauntletConfig(
        targets=[Target(name="box-b", base_url="http://w:1", enrich="ollama", box="box-b")],
        boxes=[Box(id="box-b", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="tight")],
        models=[
            ModelProfile(target="box-b", id="gemma3:1b", context=4096),
            ModelProfile(target="box-b", id="qwen2.5:7b", context=8192),
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
    assert all(c.box_id == "box-b" for c in cells)


def test_build_cells_excludes_keep_list_unless_named():
    cfg = _cfg()
    cfg.models.append(ModelProfile(target="box-b", id="nomic-embed-text", context=2048))
    # keep_list glob *embed* matches -> excluded by default
    assert not any(c.model == "nomic-embed-text" for c in build_cells(cfg, _batteries()))
    # named explicitly -> included
    cells = build_cells(cfg, _batteries(), only_models=["nomic-embed-text"])
    assert all(c.model == "nomic-embed-text" for c in cells)


def test_estimate_footprint_unknown_size_is_none():
    assert estimate_footprint_gb(None, 4096) is None


def test_estimate_footprint_weights_plus_kv():
    # 4 GB weights + 8192 tokens * 100_000 B/token KV ~= 4.82 GB
    gb = estimate_footprint_gb(4_000_000_000, 8192)
    assert abs(gb - 4.82) < 0.05


def test_plan_run_broad_box_one_exclusive_group_per_profile():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="RTX 5090 desktop", vram_gb=32, usage_class="broad")],
        models=[ModelProfile(target="t", id="m1", context=4096),
                ModelProfile(target="t", id="m2", context=4096)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    plan = plan_run(cfg, bats)
    assert len(plan.groups) == 2
    assert all(g.exclusive for g in plan.groups)
    assert plan.deferred == []


def test_plan_run_busy_box_defers_all_its_cells():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="RTX 5090 desktop", vram_gb=32, busy=True)],
        models=[ModelProfile(target="t", id="m1", context=4096)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    plan = plan_run(cfg, bats)
    assert plan.groups == []
    assert len(plan.deferred) == 1
    assert plan.deferred[0].deferred is True
    assert "busy" in plan.deferred[0].defer_reason


def test_plan_run_tight_box_packs_to_vram_budget():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="RTX 2070 Super laptop", vram_gb=24, usage_class="tight")],
        models=[ModelProfile(target="t", id="a", context=2048),
                ModelProfile(target="t", id="b", context=2048),
                ModelProfile(target="t", id="c", context=2048)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    footprints = {"a": 3_000_000_000, "b": 4_000_000_000, "c": 20_000_000_000}
    plan = plan_run(cfg, bats, footprints=footprints)
    # a(~3.2) + b(~4.2) = ~7.4 <= 24 co-reside; c(~20.2) pushes a 2nd group
    assert len(plan.groups) == 2
    assert {p[1] for p in plan.groups[0].profiles} == {"a", "b"}
    assert {p[1] for p in plan.groups[1].profiles} == {"c"}


def test_plan_run_tight_unknown_footprint_is_exclusive():
    cfg = GauntletConfig(
        targets=[Target(name="t", base_url="http://t:1", box="b")],
        boxes=[Box(id="b", hardware="laptop", vram_gb=8, usage_class="tight")],
        models=[ModelProfile(target="t", id="a", context=2048),
                ModelProfile(target="t", id="b", context=2048)],
    )
    bats = [Battery(capability="cap", cases=[Case(id="c", scoring="exact", expect="x")])]
    plan = plan_run(cfg, bats)  # no footprints -> unknown -> exclusive
    assert len(plan.groups) == 2
    assert all(g.exclusive for g in plan.groups)
