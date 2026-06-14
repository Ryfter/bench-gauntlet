import json

from gauntlet.models import ContextDepth, RunMeta, Scorecard
from gauntlet.scorecard import merge_into_scorecard, write_json


def test_merge_into_scorecard_adds_context_depth(tmp_path):
    sc = Scorecard(run=RunMeta(id="r1", date="2026-06-13", gauntlet_version="0.1.0"))
    path = tmp_path / "card.json"
    write_json(sc, path)
    merge_into_scorecard(path, context_depth=[ContextDepth(model="m", advertised=8192,
                                                           effective_90pct=4096)])
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["context_depth"][0]["effective_90pct"] == 4096
    assert data["run"]["id"] == "r1"      # existing content preserved
