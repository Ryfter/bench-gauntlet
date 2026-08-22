"""Per-dimension quality aggregation, and the per-case row written alongside it.

The tier profile says how *hard* a model can go; the dimension profile says what
it is good *at*. Baton routes on the second one — "use this model for bug-fix,
that one for refactors" — so a run that only records the aggregate is a run that
cannot answer the question it was launched to answer.
"""
from __future__ import annotations

import json

from gauntlet.models import CaseResult
from gauntlet.runner import RunPaths, append_case_rows
from gauntlet.scorecard import aggregate_cell, quality_by_dimension


def _r(case_id: str, score: float | None, *, dimension: str | None = None,
       tier: str | None = None, mode: str | None = None,
       passed: bool = False) -> CaseResult:
    return CaseResult(case_id=case_id, method="code-exec", score=score,
                      passed=passed, tier=tier, dimension=dimension,
                      failure_mode=mode)


def test_quality_by_dimension_averages_within_each_dimension():
    results = [
        _r("a", 1.0, dimension="bug-fix"), _r("b", 0.5, dimension="bug-fix"),
        _r("c", 0.2, dimension="multi-function"),
    ]
    assert quality_by_dimension(results) == {"bug-fix": 0.75, "multi-function": 0.2}


def test_quality_by_dimension_excludes_unscored_rather_than_counting_them_zero():
    """An unscored case is an admission we don't know, not evidence of failure.
    Averaging it in as 0.0 would understate the model and, worse, look like data."""
    results = [_r("a", 1.0, dimension="bug-fix"), _r("b", None, dimension="bug-fix")]
    assert quality_by_dimension(results) == {"bug-fix": 1.0}


def test_quality_by_dimension_is_none_when_no_case_carries_a_dimension():
    assert quality_by_dimension([_r("a", 1.0)]) is None


def test_aggregate_cell_carries_the_dimension_profile():
    cell = aggregate_cell(
        model="m", target="t", box="b", context=8192, capability="code-gen",
        results=[_r("a", 1.0, dimension="bug-fix"), _r("b", 0.0, dimension="stdlib-api-use")],
    )
    assert cell.quality_by_dimension == {"bug-fix": 1.0, "stdlib-api-use": 0.0}


def test_append_case_rows_persists_one_line_per_case(tmp_path):
    """Per-case rows are the raw material every later question is answered from.
    Discarding them means a new question costs a whole re-run of the fleet."""
    paths = RunPaths(tmp_path / "run")
    paths.ensure()
    append_case_rows(
        paths, model="m", target="t", context=8192, capability="code-gen",
        results=[
            _r("a", 1.0, dimension="bug-fix", tier="T1", mode="none", passed=True),
            _r("b", None, dimension="multi-function", tier="T4"),
        ],
    )
    rows = [json.loads(line) for line in
            paths.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [r["case_id"] for r in rows] == ["a", "b"]
    assert rows[0] == {
        "model": "m", "target": "t", "context": 8192, "capability": "code-gen",
        "case_id": "a", "tier": "T1", "dimension": "bug-fix",
        "score": 1.0, "passed": True, "failure_mode": "none",
    }
    # Unscored stays null on the way to disk — it must never round-trip as 0.0.
    assert rows[1]["score"] is None


def test_append_case_rows_is_append_only(tmp_path):
    paths = RunPaths(tmp_path / "run")
    paths.ensure()
    for case_id in ("a", "b"):
        append_case_rows(paths, model="m", target="t", context=8192,
                         capability="code-gen", results=[_r(case_id, 1.0)])
    assert len(paths.cases.read_text(encoding="utf-8").strip().splitlines()) == 2
