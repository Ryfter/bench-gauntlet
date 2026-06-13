import gauntlet


def test_version_exposed():
    assert isinstance(gauntlet.__version__, str)
    assert gauntlet.__version__.count(".") >= 1
