import json

import pytest

from gauntlet import errors
from gauntlet.models import Cell, Scorecard
from gauntlet.scorecard import assert_no_leak, to_dict, write_json


def _sc() -> Scorecard:
    return Scorecard(
        run={"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        cells=[Cell(model="gemma3:1b", target="box-b-ollama", box="RTX 2070 Super laptop",
                    context=8192, capability="extract-json", quality=0.9, pass_rate=0.9,
                    cases=10, errors=0)],
    )


def test_private_mode_keeps_target():
    d = to_dict(_sc(), share=False)
    assert d["cells"][0]["target"] == "box-b-ollama"
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
        assert_no_leak('{"host": "203.0.113.50"}')


@pytest.mark.parametrize("secret", ["fd00::1", "workstation:11434"])
def test_assert_no_leak_rejects_ipv6_and_host_port_without_echoing(secret):
    with pytest.raises(errors.GauntletError) as caught:
        assert_no_leak(json.dumps({"host": secret}))
    assert secret not in str(caught.value)


def test_share_mode_redacts_hostname_like_identifiers_in_all_sections():
    sc = _sc().model_copy(deep=True)
    sc.run.id = "workstation"
    sc.cells[0].model = "workstation:11434"
    sc.cells[0].box = "workstation"
    sc.cells[0].judge = "fd00::1"
    data = to_dict(sc, share=True)
    payload = json.dumps(data)
    for secret in ("workstation", "workstation:11434", "fd00::1"):
        assert secret not in payload


def test_assert_no_leak_allows_clean_scorecard():
    assert_no_leak(json.dumps(to_dict(_sc(), share=True)))  # no raise


def test_write_json_round_trips(tmp_path):
    path = tmp_path / "card.json"
    write_json(_sc(), path, share=False)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run"]["id"] == "r1"
    assert loaded["cells"][0]["model"] == "gemma3:1b"
