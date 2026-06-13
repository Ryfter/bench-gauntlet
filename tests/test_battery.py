from pathlib import Path

import pytest

from gauntlet import errors
from gauntlet.battery import Battery, load_battery, load_batteries

FIX = Path(__file__).parent / "fixtures" / "batteries"


def test_load_valid_battery():
    bat = load_battery(FIX / "extract-json.yaml")
    assert bat.capability == "extract-json"
    assert bat.context_floor == 4096
    assert bat.cases[0].id == "invoice-01"
    assert bat.cases[0].scoring == "json-schema"


def test_applies_to_respects_context_floor():
    bat = Battery(capability="c", context_floor=4096, cases=[])
    assert bat.applies_to(context=8192) is True
    assert bat.applies_to(context=2048) is False


def test_missing_capability_raises_bad_battery(tmp_path):
    bad = tmp_path / "broken.yaml"
    bad.write_text("context_floor: 4096\ncases: []\n", encoding="utf-8")
    with pytest.raises(errors.BadBattery) as exc:
        load_battery(bad)
    assert "broken.yaml" in str(exc.value)


def test_load_batteries_skips_and_reports_bad_ones(tmp_path, capsys):
    good = tmp_path / "good.yaml"
    good.write_text("capability: g\ncontext_floor: 0\ncases: []\n", encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text("nonsense: true\n", encoding="utf-8")
    loaded = load_batteries(tmp_path)
    assert [b.capability for b in loaded] == ["g"]
    assert "bad.yaml" in capsys.readouterr().err
