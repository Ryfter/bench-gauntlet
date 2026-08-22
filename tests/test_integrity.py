"""Benchmark-integrity controls.

A benchmark that can be shortcut measures nothing, so each control here is
exercised with a fixture that genuinely attempts the shortcut rather than a
mock that asserts a flag was set.
"""
from __future__ import annotations

import pytest

from gauntlet import integrity
from gauntlet.scoring.execute import (
    CANARY_RE,
    canary_for,
    code_execution_match,
)

# A hidden test whose asserts always pass, so anything below 1.0 or unscored is
# the integrity layer acting rather than the candidate being wrong.
_PERMISSIVE = """
# {canary}
def check(ns):
    return [True, True, True]
"""


@pytest.fixture()
def tests_file(tmp_path):
    def _make(case_id="demo"):
        p = tmp_path / "hidden_tests.py"
        p.write_text(_PERMISSIVE.format(canary=canary_for(case_id)), encoding="utf-8")
        return p
    return _make


# --- Vector D: inference-time tool use ---------------------------------------

@pytest.mark.parametrize("field", integrity.FORBIDDEN_REQUEST_FIELDS)
def test_request_carrying_a_tool_field_is_refused(field):
    payload = {"model": "m", "messages": [], field: [{"x": 1}]}
    with pytest.raises(integrity.IntegrityError) as exc:
        integrity.assert_request_is_tool_free(payload)
    assert field in str(exc.value)


def test_ordinary_request_passes():
    integrity.assert_request_is_tool_free(
        {"model": "m", "messages": [], "max_tokens": 512, "stream": True})


def test_empty_tool_field_is_not_a_violation():
    # Serving stacks routinely send `tools: []`; only a populated field means
    # the server could actually have answered.
    integrity.assert_request_is_tool_free({"model": "m", "tools": []})


@pytest.mark.parametrize("choice", [
    {"message": {"tool_calls": [{"id": "1"}]}},
    {"message": {"function_call": {"name": "search"}}},
    {"finish_reason": "tool_calls"},
    {"delta": {"tool_calls": [{"id": "1"}]}},
])
def test_tool_using_responses_are_detected(choice):
    assert integrity.response_used_tools(choice) is True


def test_plain_response_is_not_flagged():
    assert integrity.response_used_tools(
        {"message": {"content": "hi"}, "finish_reason": "stop"}) is False


# --- Vector A: prompt leakage -------------------------------------------------

def test_leaked_assertion_in_prompt_is_caught():
    secret = 'def check(ns):\n    return [t(lambda: f([3, 1, 2]) == [1, 2, 3])]\n'
    prompt = "Write a sort.\nHint: f([3, 1, 2]) == [1, 2, 3]\n"
    # The leaked line is embedded verbatim in a longer prompt line.
    prompt = "Write a sort.\n" + secret.splitlines()[1].strip() + "\n"
    with pytest.raises(integrity.IntegrityError):
        integrity.assert_no_prompt_leak(prompt, secret, case_id="c")


def test_clean_prompt_passes():
    secret = 'def check(ns):\n    return [t(lambda: f([3, 1, 2]) == [1, 2, 3])]\n'
    integrity.assert_no_prompt_leak(
        "Write a function that sorts a list ascending.", secret, case_id="c")


def test_short_shared_boilerplate_is_not_a_false_positive():
    # `return []` and friends appear in both by coincidence, constantly.
    secret = "def check(ns):\n    return []\n    for i in x:\n"
    integrity.assert_no_prompt_leak(
        "Write code that may return [] and use for i in x:", secret, case_id="c")


def test_test_authoring_is_exempt_from_the_leak_check():
    # There the prompt legitimately contains the implementation under test.
    # The line must clear _MIN_NGRAM_CHARS, or the exemption is untested: a
    # short line is ignored for every dimension and would pass either way.
    secret = ("def tally(rows, *, skip_zero=True, scale=1):\n"
              "    return sum(r * scale for r in rows if r or not skip_zero)\n")
    assert max(len(line.strip()) for line in secret.splitlines()) >= 40

    integrity.assert_no_prompt_leak(
        secret, secret, case_id="c", dimension="test-authoring")
    with pytest.raises(integrity.IntegrityError):
        integrity.assert_no_prompt_leak(secret, secret, case_id="c",
                                        dimension="adversarial-correctness")


# --- Vector E: canaries -------------------------------------------------------

def test_canary_is_deterministic_and_well_formed():
    assert canary_for("abc") == canary_for("abc")
    assert canary_for("abc") != canary_for("abd")
    assert CANARY_RE.fullmatch(canary_for("abc"))


def test_echoing_a_canary_is_unscored_not_zero(tests_file):
    """A model that echoes the canary saw the answers. We cannot say what it
    can do — only that this number is not evidence of it."""
    output = f"# seen: {canary_for('demo')}\ndef solve(x):\n    return x\n"
    result = code_execution_match(output, tests_file("demo"))
    assert result.failure_mode == "integrity_violation"
    assert result.score is None, "a tainted cell must be unscored, never 0"
    assert result.integrity_violations[0]["kind"] == "canary"


def test_clean_output_against_a_canaried_file_scores_normally(tests_file):
    result = code_execution_match("def solve(x):\n    return x\n", tests_file("demo"))
    assert result.score == 1.0
    assert result.failure_mode == "none"
    assert result.integrity_violations == []
