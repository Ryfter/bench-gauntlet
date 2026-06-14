import os

import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("GAUNTLET_LIVE_BASE_URL"),
                    reason="set GAUNTLET_LIVE_BASE_URL to a box-b endpoint (never box-a while gaming)")
def test_live_run_smoke(tmp_path):
    """End-to-end on box-b with gemma3:1b. NEVER point this at box-a while gaming."""
    from gauntlet.battery import Battery, Case
    from gauntlet.config import Box, GauntletConfig, ModelProfile, Target
    from gauntlet.runner import RunPaths, execute_plan

    base = os.environ["GAUNTLET_LIVE_BASE_URL"]
    cfg = GauntletConfig(
        targets=[Target(name="box-b", base_url=base, box="box-b")],
        boxes=[Box(id="box-b", hardware="RTX 2070 Super laptop", vram_gb=8, usage_class="broad")],
        models=[ModelProfile(target="box-b", id="gemma3:1b", context=4096)],
    )
    (tmp_path / "p.txt").write_text("Write a one-line conventional commit for adding a runner.",
                                    encoding="utf-8")
    bats = [Battery(capability="commit-msg",
                    cases=[Case(id="c1", scoring="conventional-commit", prompt_file="p.txt")])]

    def factory(base_url, api_key=None):
        from gauntlet.client import OpenAIClient
        return OpenAIClient(base_url=base_url)

    cells = execute_plan(cfg, bats, RunPaths(tmp_path / "run"), base_dir=tmp_path,
                         client_factory=factory)
    assert len(cells) == 1
    assert cells[0].cases == 1
