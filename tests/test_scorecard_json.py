import json

import pytest

from gauntlet import errors
from gauntlet.models import Cell, Scorecard
from gauntlet.scorecard import assert_no_leak, to_dict, write_json


def _sc() -> Scorecard:
    return Scorecard(
        run={"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        cells=[Cell(model="gemma3:1b", target="wraith2-ollama", box="RTX 2070 Super laptop",
                    context=8192, capability="extract-json", quality=0.9, pass_rate=0.9,
                    cases=10, errors=0)],
    )


def test_private_mode_keeps_target():
    d = to_dict(_sc(), share=False)
    assert d["cells"][0]["target"] == "wraith2-ollama"
    assert d["cells"][0]["box"] == "RTX 2070 Super laptop"


def test_share_mode_drops_target_keeps_hardware():
    d = to_dict(_sc(), share=True)
    assert "target" not in d["cells"][0]
    assert d["cells"][0]["box"] == "RTX 2070 Super laptop"


def test_assert_no_leak_rejects_ip():
    with pytest.raises(errors.GauntletError):
        assert_no_leak('{"x": "see http://203.0.113.10:11434"}')


def test_assert_no_leak_rejects_bare_ipv4():
    with pytest.raises(errors.GauntletError):
        assert_no_leak('{"host": "192.168.1.50"}')


def test_assert_no_leak_allows_clean_scorecard():
    assert_no_leak(json.dumps(to_dict(_sc(), share=True)))  # no raise


def test_write_json_round_trips(tmp_path):
    path = tmp_path / "card.json"
    write_json(_sc(), path, share=False)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run"]["id"] == "r1"
    assert loaded["cells"][0]["model"] == "gemma3:1b"
