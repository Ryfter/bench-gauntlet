"""Every code-exec case must be provably discriminative.

For each registered case we run two maintainer-authored solutions through the
real scorer:

    reference -> must score exactly 1.0   (the asserts are satisfiable at all)
    wrong     -> must score below 1.0     (the asserts actually catch a defect)

Without this, a case whose asserts are unsatisfiable scores every model 0.0,
and a case whose asserts are toothless scores every model 1.0. Both look like
data and are actually noise — the exact failure that made the original
`compilable-code` scorer worthless. A broken case must fail CI, not quietly
skew a scorecard.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gauntlet.scoring.execute import code_execution_match

CASES_DIR = Path(__file__).resolve().parents[1] / "cases" / "code-gen"
TESTS_DIR = CASES_DIR / "tests"
REF_DIR = TESTS_DIR / "reference"
REGISTRY = CASES_DIR / "registry.json"

VALID_TIERS = {"T1", "T2", "T3", "T4"}


def _registry() -> dict[str, dict]:
    if not REGISTRY.exists():
        return {}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    return sorted(_registry())


def test_registry_exists_and_is_populated():
    assert _case_ids(), "no registered code-exec cases — battery is empty"


@pytest.mark.parametrize("case_id", _case_ids())
def test_case_files_present_and_well_formed(case_id: str):
    meta = _registry()[case_id]
    assert meta["tier"] in VALID_TIERS, f"{case_id}: bad tier {meta['tier']!r}"
    assert meta.get("dimension"), f"{case_id}: missing dimension"

    for path in (CASES_DIR / f"{case_id}.txt",
                 TESTS_DIR / f"{case_id}.py",
                 REF_DIR / f"{case_id}.ref.py",
                 REF_DIR / f"{case_id}.wrong.py"):
        assert path.exists(), f"{case_id}: missing {path.name}"


@pytest.mark.parametrize("case_id", _case_ids())
def test_hidden_tests_do_not_leak_into_the_prompt(case_id: str):
    """The model must never be shown the assertions it is graded against."""
    prompt = (CASES_DIR / f"{case_id}.txt").read_text(encoding="utf-8")
    hidden = (TESTS_DIR / f"{case_id}.py").read_text(encoding="utf-8")

    for line in hidden.splitlines():
        line = line.strip()
        if len(line) > 25:
            assert line not in prompt, (
                f"{case_id}: hidden test line leaks into the prompt: {line[:60]!r}"
            )


@pytest.mark.parametrize("case_id", _case_ids())
def test_reference_solution_scores_one(case_id: str):
    src = (REF_DIR / f"{case_id}.ref.py").read_text(encoding="utf-8")
    result = code_execution_match(src, TESTS_DIR / f"{case_id}.py", timeout_s=15.0)
    assert result.score == 1.0, (
        f"{case_id}: reference solution scored {result.score} "
        f"({result.failure_mode}) — the case is unsatisfiable. {result.detail[:300]}"
    )


@pytest.mark.parametrize("case_id", _case_ids())
def test_wrong_solution_is_caught(case_id: str):
    src = (REF_DIR / f"{case_id}.wrong.py").read_text(encoding="utf-8")
    result = code_execution_match(src, TESTS_DIR / f"{case_id}.py", timeout_s=15.0)
    assert result.score is not None, (
        f"{case_id}: wrong solution came back unscored — {result.detail[:300]}"
    )
    assert result.score < 1.0, (
        f"{case_id}: the deliberately-wrong solution still scored 1.0 — "
        "the hidden asserts are too weak to discriminate"
    )
