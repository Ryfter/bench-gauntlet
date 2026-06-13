import pytest

from gauntlet import errors


def test_config_not_found_carries_path():
    err = errors.ConfigNotFound("/nope/targets.yaml")
    assert "/nope/targets.yaml" in str(err)
    assert isinstance(err, errors.GauntletError)


def test_bad_battery_names_the_file():
    err = errors.BadBattery("batteries/extract-json.yaml", "missing 'capability'")
    assert "extract-json.yaml" in str(err)
    assert "missing 'capability'" in str(err)
    assert isinstance(err, errors.GauntletError)
