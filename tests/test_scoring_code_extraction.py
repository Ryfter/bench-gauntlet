"""Pulling the candidate program out of a chat reply.

Models do not answer with bare source. They say "Here's the solution:", fence
the code, and sign off with "Hope this helps!". If the extractor only handles
a reply that *starts* with a fence, every one of those becomes a `syntax_error`
-- and the benchmark reports a scoring bug as a model failure, uniformly
punishing the models that are most chatty rather than the ones that are worst
at code. That is worse than a wrong number: it is a wrong number that looks
like a finding.
"""
from __future__ import annotations

import pytest

from gauntlet.scoring.execute import extract_code

FUNC = "def solve(x):\n    return x + 1"


def test_bare_source_is_returned_unchanged():
    assert extract_code(FUNC) == FUNC


def test_a_plain_fenced_block_is_unwrapped():
    assert extract_code(f"```python\n{FUNC}\n```") == FUNC


def test_a_fence_with_no_language_tag_is_unwrapped():
    assert extract_code(f"```\n{FUNC}\n```") == FUNC


def test_prose_before_the_fence_is_dropped():
    reply = f"Sure! Here's the solution:\n\n```python\n{FUNC}\n```"
    assert extract_code(reply) == FUNC


def test_prose_after_the_fence_is_dropped():
    reply = f"```python\n{FUNC}\n```\n\nHope this helps!"
    assert extract_code(reply) == FUNC


def test_prose_on_both_sides_is_dropped():
    reply = f"Here you go:\n\n```python\n{FUNC}\n```\n\nLet me know if you want tests."
    assert extract_code(reply) == FUNC


def test_the_longest_block_wins_when_a_reply_has_several():
    """Chatty models often show a one-line usage example beside the real
    implementation. The submission is the substantial block, not the snippet."""
    reply = (
        "First the helper:\n\n```python\nx = 1\n```\n\n"
        f"And the answer:\n\n```python\n{FUNC}\n```\n"
    )
    assert extract_code(reply) == FUNC


def test_an_unterminated_fence_still_yields_its_body():
    """Truncated output -- a model that hit its token limit mid-block. What it
    did write is still a real attempt and deserves to be run."""
    reply = f"Here:\n\n```python\n{FUNC}"
    assert extract_code(reply) == FUNC


def test_prose_with_no_fence_at_all_is_left_alone():
    """Not code, but the caller decides that -- `_looks_like_code` attributes it
    as `no_code_emitted`. The extractor must not invent a code block."""
    reply = "I'm not able to help with that."
    assert extract_code(reply) == reply


def test_tilde_fences_are_handled():
    assert extract_code(f"~~~python\n{FUNC}\n~~~") == FUNC


def test_empty_output_stays_empty():
    assert extract_code("") == ""
    assert extract_code("   \n  ") == ""


@pytest.mark.parametrize("lang", ["python", "py", "Python", "python3", ""])
def test_common_language_tags_are_all_stripped(lang):
    assert extract_code(f"```{lang}\n{FUNC}\n```") == FUNC


def test_indentation_inside_the_block_is_preserved():
    """Stripping a fence must never reflow the body -- Python is whitespace
    significant, so a lost indent turns a working program into a syntax error."""
    body = "class C:\n    def m(self):\n        if True:\n            return 42"
    assert extract_code(f"```python\n{body}\n```") == body
