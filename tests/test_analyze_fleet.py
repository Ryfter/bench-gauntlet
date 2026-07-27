"""Validation for `scripts/analyze_fleet.py`.

The script was drafted by a fleet model, so it does not get to land on trust:
these tests pin the properties that make its output safe to route on. The
non-negotiable one is that a null score never becomes a zero -- a zero says the
model failed, a null says we do not know, and a report that conflates them
manufactures failures out of missing data.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "analyze_fleet.py"


def _load():
    spec = importlib.util.spec_from_file_location("analyze_fleet", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_fleet"] = module
    spec.loader.exec_module(module)
    return module


analyze = _load()


def _run_dir(tmp_path: Path, cells: list[dict], cases: list[dict] | None = None) -> Path:
    root = tmp_path / "run"
    root.mkdir()
    (root / "cells.jsonl").write_text(
        "".join(json.dumps(c) + "\n" for c in cells), encoding="utf-8")
    if cases is not None:
        (root / "cases.jsonl").write_text(
            "".join(json.dumps(c) + "\n" for c in cases), encoding="utf-8")
    return root


def _cell(model: str, capability: str = "code-gen", **kw) -> dict:
    base = {"model": model, "target": "t", "box": "b", "context": 8192,
            "capability": capability, "quality": 1.0, "pass_rate": 1.0,
            "tokens_per_s": 10.0, "ttft_p50_s": 1.0, "cases": 10, "errors": 0}
    base.update(kw)
    return base


def _profile_row(report: str, model: str) -> str:
    """The model's row in the difficulty-profile table.

    Assert against this rather than the whole report: the section's legend
    names every shape, so a substring search over the full text always matches.
    """
    section = report.split("## Difficulty profile")[1].split("\n##")[0]
    rows = [line for line in section.splitlines() if line.startswith(f"| {model} ")]
    assert rows, f"no difficulty-profile row for {model!r}"
    return rows[0]


def _report(tmp_path, cells, cases=None, **kw) -> str:
    run_dir = _run_dir(tmp_path, cells, cases)
    return analyze.build_report(
        cells=cells, cases=cases or [], has_cases_file=cases is not None,
        capability=kw.get("capability"), top_n=kw.get("top_n", 3), run_dir=run_dir)


# --- the null-vs-zero contract -------------------------------------------------

def test_a_null_score_is_excluded_from_the_mean_not_counted_as_zero(tmp_path):
    cases = [
        {"model": "m", "capability": "code-gen", "case_id": "a", "tier": "T1",
         "dimension": "bug-fix", "score": 1.0, "passed": True, "failure_mode": "none"},
        {"model": "m", "capability": "code-gen", "case_id": "b", "tier": "T1",
         "dimension": "bug-fix", "score": None, "passed": False, "failure_mode": None},
    ]
    report = _report(tmp_path, [_cell("m", quality_by_dimension=None)], cases)
    # Mean of {1.0} is 1.00. Counting the null as 0.0 would print 0.50.
    assert "1.00" in report
    assert "0.50" not in report


def test_a_null_quality_never_renders_as_none(tmp_path):
    report = _report(tmp_path, [_cell("m", quality=None, tokens_per_s=None)])
    assert "None" not in report


# --- the shape classifier ------------------------------------------------------

@pytest.mark.parametrize("tiers,expected", [
    ({"T1": 0.80, "T2": 0.78, "T3": 0.72, "T4": 0.70}, "flat"),
    ({"T1": 0.90, "T2": 0.70, "T3": 0.50, "T4": 0.35}, "graceful"),
    ({"T1": 0.95, "T2": 0.90, "T3": 0.20, "T4": 0.15}, "cliff"),
    ({"T1": 0.20, "T2": 0.90, "T3": 0.30, "T4": 0.85}, "erratic"),
    # Two big drops is a collapse, not a single ledge -- `graceful` reads it as
    # a steady decline, which is the honest description.
    ({"T1": 0.95, "T2": 0.45, "T3": 0.02, "T4": 0.00}, "graceful"),
])
def test_difficulty_shape_is_classified_as_documented(tmp_path, tiers, expected):
    report = _report(tmp_path, [_cell("m", quality_by_tier=tiers)])
    assert expected in _profile_row(report, "m")


def test_a_missing_tier_is_skipped_rather_than_scored_zero(tmp_path):
    """A tier with no cases is absent, not failed -- it must not drag the shape
    into looking like a cliff."""
    report = _report(tmp_path, [_cell("m", quality_by_tier={"T1": 0.8, "T2": 0.75})])
    row = _profile_row(report, "m")
    assert "cliff" not in row
    assert "flat" in row


# --- the failure-mode read -----------------------------------------------------

@pytest.mark.parametrize("modes,expected", [
    ({"no_code_emitted": 6, "syntax_error": 2, "wrong_answer": 1}, "capability gap"),
    ({"wrong_answer": 8, "syntax_error": 1}, "scaffolding candidate"),
    ({"timeout": 7, "wrong_answer": 2}, "too slow"),
    ({"wrong_answer": 3, "timeout": 3, "syntax_error": 3}, "mixed"),
])
def test_failure_mode_read_follows_the_selective_offload_rule(tmp_path, modes, expected):
    report = _report(tmp_path, [_cell("m", failure_modes=modes)])
    section = report.split("## Failure-mode profile")[1].split("\n##")[0]
    rows = [ln for ln in section.splitlines() if ln.startswith("| m ")]
    assert rows, "no failure-mode row for the model"
    assert expected in rows[0]


# --- throughput ranking is not a cherry-pick -----------------------------------

def test_throughput_uses_a_case_weighted_mean_not_the_models_best_capability(tmp_path):
    """Reporting each model at its strongest capability would flatter every model.
    The 108-case cell must dominate the 8-case one."""
    cells = [
        _cell("m", capability="code-gen", quality=0.20, tokens_per_s=10.0, cases=108),
        _cell("m", capability="classify", quality=1.00, tokens_per_s=10.0, cases=8),
    ]
    report = _report(tmp_path, cells)
    expected = (0.20 * 108 + 1.00 * 8) / 116
    assert f"{expected:.2f}" in report
    assert "1.00" not in report.split("## Quality per unit time")[1]


# --- coverage: is this quality figure even comparable? --------------------------

def test_coverage_is_the_fraction_of_cases_that_produced_a_score(tmp_path):
    cell = _cell("m", cases=108, failure_modes={"truncated": 24, "wrong_answer": 3})
    assert analyze.coverage(cell) == pytest.approx((108 - 24) / 108)


def test_scored_failures_do_not_reduce_coverage(tmp_path):
    """A wrong answer IS a measurement. Only outcomes that yield no score --
    truncation, integrity blocks, harness faults -- shrink the denominator."""
    cell = _cell("m", cases=100, failure_modes={"wrong_answer": 60, "syntax_error": 20})
    assert analyze.coverage(cell) == 1.0


def test_low_coverage_is_flagged_in_the_row_and_explained(tmp_path):
    """gemma-4-12b scored 0.98 over 84 of 108 cases while tulu scored 0.66 over
    all 108. Presenting those in one ranked table without saying so invites
    exactly the wrong conclusion."""
    cells = [_cell("thorough", quality=0.66, cases=108, failure_modes={"wrong_answer": 60}),
             _cell("truncating", quality=0.98, cases=108,
                   failure_modes={"truncated": 24, "wrong_answer": 3})]
    report = _report(tmp_path, cells)
    # Split on "\n## " with the trailing space: the section contains "### `cap`"
    # subheadings, and "\n##" alone truncates at the first of those.
    section = report.split("## Leaderboard")[1].split("\n## ")[0]
    assert "78%" in section          # 84/108
    assert "100%" in section
    assert "⚠" in section
    assert "biased" in section.lower()


def test_no_warning_when_every_model_was_fully_measured(tmp_path):
    report = _report(tmp_path, [_cell("m", cases=108, failure_modes={"wrong_answer": 9})])
    assert "Coverage warning" not in report


# --- robustness ----------------------------------------------------------------

def test_missing_cases_file_degrades_instead_of_crashing(tmp_path):
    report = _report(tmp_path, [_cell("m")], cases=None)
    assert "Fleet routing report" in report


def test_cells_missing_every_optional_key_do_not_crash(tmp_path):
    sparse = {"model": "m", "capability": "code-gen"}
    report = _report(tmp_path, [sparse])
    assert "Fleet routing report" in report


def test_errors_and_integrity_are_surfaced_not_buried(tmp_path):
    cells = [_cell("m", errors=3, integrity={"filesystem_read": 2})]
    report = _report(tmp_path, cells)
    assert "3" in report and "filesystem_read" in report


def test_report_is_encodable_as_utf8_on_a_windows_console(tmp_path):
    """The first live run died here: the report uses em dashes and a Unicode
    minus, and a Windows console is cp1252 by default."""
    report = _report(tmp_path, [_cell("m", quality=None)])
    report.encode("utf-8")
    assert "—" in report  # em dash for missing values
