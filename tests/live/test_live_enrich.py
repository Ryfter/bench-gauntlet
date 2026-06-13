"""Opt-in: hits a REAL endpoint, metadata-only (no model load, VRAM-safe).
Run with: pytest -m live  (set GAUNTLET_LIVE_OLLAMA to a reachable base_url)."""
import os

import pytest

pytestmark = pytest.mark.live


def test_live_ollama_tags():
    base = os.environ.get("GAUNTLET_LIVE_OLLAMA")
    if not base:
        pytest.skip("set GAUNTLET_LIVE_OLLAMA to a reachable Ollama base_url")
    from gauntlet.enrich.ollama import fetch
    metas = fetch(base)
    assert metas, "expected at least one installed model"
    assert all(m.id for m in metas)
