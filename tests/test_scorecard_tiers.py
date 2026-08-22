"""Per-tier quality and failure-mode aggregation on a cell."""
from __future__ import annotations

from gauntlet.models import CaseResult
from gauntlet.scorecard import (
    aggregate_cell,
    failure_mode_counts,
    quality_by_tier,
)


def _r(case_id: str, score: float | None, *, tier: str | None = None,
       mode: str | None = None, passed: bool = False) -> CaseResult:
    return CaseResult(case_id=case_id, method="code-exec", score=score,
                      passed=passed, tier=tier, failure_mode=mode)


def test_quality_by_tier_averages_within_each_tier():
    results = [
        _r("a", 1.0, tier="T1"), _r("b", 0.5, tier="T1"),
        _r("c", 0.2, tier="T3"),
    ]
    assert quality_by_tier(results) == {"T1": 0.75, "T3": 0.2}


def test_quality_by_tier_excludes_unscored_rather_than_counting_them_zero():
    # An unscored case is our failure, not the model's. Averaging it in as 0
    # would understate the model — the scoring-honesty invariant in CLAUDE.md.
    results = [_r("a", 1.0, tier="T2"), _r("b", None, tier="T2", mode="harness_error")]
    assert quality_by_tier(results) == {"T2": 1.0}


def test_quality_by_tier_is_none_when_no_case_carries_a_tier():
    assert quality_by_tier([_r("a", 1.0)]) is None


def test_failure_modes_counted_and_clean_passes_excluded():
    results = [
        _r("a", 1.0, mode="none", passed=True),
        _r("b", 0.0, mode="timeout"),
        _r("c", 0.0, mode="timeout"),
        _r("d", 0.4, mode="wrong_answer"),
    ]
    assert failure_mode_counts(results) == {"timeout": 2, "wrong_answer": 1}


def test_failure_modes_none_when_everything_passed():
    assert failure_mode_counts([_r("a", 1.0, mode="none", passed=True)]) is None


def test_aggregate_cell_carries_tier_profile_and_failure_modes():
    results = [
        _r("a", 1.0, tier="T1", mode="none", passed=True),
        _r("b", 0.0, tier="T4", mode="no_code_emitted"),
    ]
    cell = aggregate_cell(model="m", target=None, box="box", context=8192,
                          capability="code-gen", results=results)
    assert cell.quality_by_tier == {"T1": 1.0, "T4": 0.0}
    assert cell.failure_modes == {"no_code_emitted": 1}
    assert cell.quality == 0.5
