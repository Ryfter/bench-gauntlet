import json

import pytest

from gauntlet.battery import Case
from gauntlet.scoring import NEEDS_JUDGE, score_case


def test_dispatch_exact():
    case = Case(id="c1", scoring="exact", expect="hello")
    res = score_case(case, "  hello ")
    assert res.method == "exact"
    assert res.passed is True
    assert res.score == 1.0


def test_dispatch_regex_fail_scores_zero():
    case = Case(id="c2", scoring="regex", pattern=r"\d{6}")
    res = score_case(case, "no digits")
    assert res.passed is False
    assert res.score == 0.0


def test_dispatch_json_schema_reads_schema_file(tmp_path):
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "number"}}}
    sf = tmp_path / "s.json"
    sf.write_text(json.dumps(schema), encoding="utf-8")
    case = Case(id="c3", scoring="json-schema", schema_file="s.json")
    res = score_case(case, '{"x": 1}', base_dir=tmp_path)
    assert res.passed is True
    assert res.score == 1.0


def test_dispatch_conventional_commit():
    case = Case(id="c4", scoring="conventional-commit")
    assert score_case(case, "feat: x").passed is True


def test_dispatch_judge_returns_needs_judge_sentinel():
    case = Case(id="c5", scoring="judge", rubric="grade it")
    res = score_case(case, "anything")
    assert res is NEEDS_JUDGE


def test_dispatch_missing_param_raises():
    case = Case(id="c6", scoring="exact")  # no expect
    with pytest.raises(ValueError):
        score_case(case, "x")
