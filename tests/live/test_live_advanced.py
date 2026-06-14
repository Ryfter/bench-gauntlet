"""Opt-in live smoke for the special batteries. Run only against a headless box
(box-b) — NEVER box-a while gaming. Skipped unless the env vars are set."""
import os

import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.environ.get("GAUNTLET_LIVE_BASE_URL"),
                    reason="set GAUNTLET_LIVE_BASE_URL to a box-b chat endpoint")
def test_live_context_depth_smoke():
    from gauntlet.batteries.context_depth import run_context_depth
    from gauntlet.client import OpenAIClient

    model = os.environ.get("GAUNTLET_LIVE_MODEL", "gemma3:1b")
    client = OpenAIClient(base_url=os.environ["GAUNTLET_LIVE_BASE_URL"])
    try:
        cd = run_context_depth(client, model=model, advertised=4096,
                               lengths=[512, 1024], depths=[0.5])
    finally:
        client.close()
    assert cd.model == model
    assert cd.effective_90pct >= 0          # a real curve was produced


@pytest.mark.skipif(not os.environ.get("GAUNTLET_LIVE_EMBED_URL"),
                    reason="set GAUNTLET_LIVE_EMBED_URL to a box-b embeddings endpoint")
def test_live_embed_smoke():
    from gauntlet.batteries.embed import run_embed_cell
    from gauntlet.client import OpenAIClient

    model = os.environ.get("GAUNTLET_LIVE_EMBED_MODEL", "nomic-embed-text")
    client = OpenAIClient(base_url=os.environ["GAUNTLET_LIVE_EMBED_URL"])
    try:
        cell = run_embed_cell(
            client, model=model, target="box-b", box="RTX 2070 Super laptop",
            context=0,
            corpus=["A cat is a feline pet.", "A car is a motor vehicle."],
            queries=["feline house pet"], relevant=[0],
        )
    finally:
        client.close()
    assert cell.capability == "embed"
    assert cell.cases == 1
