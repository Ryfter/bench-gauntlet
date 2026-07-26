"""A reply cut off by the token budget is not a capability failure.

The first full fleet run scored seven of nine models at ~0.00 on code-gen with
`no_code_emitted` for almost every case. They had not failed to write code --
they were reasoning models that spent the whole 512-token budget thinking and
were cut off before the answer. gemma-4-12b, scored 0.01, writes correct code
given 4096 tokens.

That is the benchmark measuring its own configuration and reporting it as a
property of the model. Per the scoring-honesty invariant, a case we cannot
judge is `unscored` -- never silently 0.
"""
from __future__ import annotations

import pytest

from gauntlet.models import CaseResult
from gauntlet.runner import attribute_truncation


def _r(mode: str, score: float | None, detail: str = "") -> CaseResult:
    return CaseResult(case_id="c", method="code-exec", score=score,
                      passed=score == 1.0, failure_mode=mode, detail=detail)


# --- truncation excuses failures consistent with being cut off ----------------

@pytest.mark.parametrize("mode", ["no_code_emitted", "syntax_error"])
def test_truncated_reply_without_usable_code_becomes_unscored(mode):
    """Both outcomes are exactly what a mid-sentence cut looks like. We cannot
    tell whether the model could not do it or was not allowed to finish, and
    saying `unscored` is the only honest answer."""
    result = attribute_truncation(_r(mode, 0.0), truncated=True)
    assert result.score is None
    assert result.failure_mode == "truncated"
    assert not result.passed


def test_the_unscored_reason_is_recorded_not_just_the_mode():
    result = attribute_truncation(_r("no_code_emitted", 0.0), truncated=True)
    assert "truncat" in result.detail.lower()


# --- truncation does NOT excuse a result the model actually produced ----------

def test_truncated_but_wrong_answer_keeps_its_score():
    """`wrong_answer` means the code ran, so it was complete enough to execute.
    The trailing prose being cut off says nothing about the defect in it --
    excusing this would throw away real signal."""
    result = attribute_truncation(_r("wrong_answer", 0.4), truncated=True)
    assert result.score == 0.4
    assert result.failure_mode == "wrong_answer"


def test_truncated_but_fully_correct_keeps_its_pass():
    result = attribute_truncation(_r("none", 1.0), truncated=True)
    assert result.score == 1.0
    assert result.failure_mode == "none"


@pytest.mark.parametrize("mode", ["timeout", "runtime_exception", "integrity_violation"])
def test_truncation_never_masks_an_unrelated_failure(mode):
    result = attribute_truncation(_r(mode, 0.0), truncated=True)
    assert result.failure_mode == mode


# --- an untruncated reply is untouched ----------------------------------------

@pytest.mark.parametrize("mode", ["no_code_emitted", "syntax_error", "wrong_answer"])
def test_an_untruncated_reply_is_returned_unchanged(mode):
    """A model that emits prose inside its budget genuinely failed the task.
    That is the finding the battery exists to produce -- do not soften it."""
    original = _r(mode, 0.0)
    result = attribute_truncation(original, truncated=False)
    assert result.score == 0.0
    assert result.failure_mode == mode


def test_a_non_code_exec_result_is_left_alone():
    """Only code-exec carries a failure_mode. A judge or exact-match result has
    none, and must pass through untouched rather than acquiring one."""
    plain = CaseResult(case_id="c", method="exact", score=0.0, passed=False)
    result = attribute_truncation(plain, truncated=True)
    assert result.score == 0.0
    assert result.failure_mode is None
