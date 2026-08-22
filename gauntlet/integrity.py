"""Benchmark-integrity controls that live outside the sandbox.

A score is only worth the integrity of how it was obtained. Two ways a number
can be worthless even when the plumbing works:

  - the model was *shown* the answer (leakage into the prompt)
  - the model didn't answer at all — a serving stack did, via web search or a
    tool call (we then measured the stack, not the model)

Both produce high scores that mean nothing, and neither is visible in the score
itself. The sandbox-side controls (filesystem/network/canary) live in
`scoring/_guard.py` and `scoring/execute.py`.

Everything here is fail-loud on purpose. A silent integrity control is worse
than none: it lets a scorecard claim a guarantee it never actually enforced.
"""
from __future__ import annotations

import re

# Fields that would let a serving stack answer on the model's behalf. Gauntlet
# measures raw model capability, so a request carrying any of these is not the
# experiment we think we are running.
FORBIDDEN_REQUEST_FIELDS = (
    "tools",
    "functions",
    "tool_choice",
    "function_call",
    "plugins",
    "web_search",
    "web_search_options",
    "retrieval",
    "connectors",
)

_WS_RE = re.compile(r"\s+")
# Below this, shared text is coincidence (`return []`, `for i in x`) rather than
# a leak. Tuned to admit ordinary Python boilerplate and catch real assertions.
_MIN_NGRAM_CHARS = 40


class IntegrityError(RuntimeError):
    """An integrity control was violated. Never caught-and-continued."""


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def assert_request_is_tool_free(payload: dict) -> None:
    """Reject an outgoing chat request that would let the server do the work.

    Called from the HTTP boundary (`client.py`), the only place requests are
    built, so there is no path that bypasses it.
    """
    present = sorted(f for f in FORBIDDEN_REQUEST_FIELDS if payload.get(f))
    if present:
        raise IntegrityError(
            "refusing to send a request carrying "
            f"{', '.join(present)}: Gauntlet measures the raw model, and a "
            "server-side tool or search call would be scored as if the model "
            "had produced it"
        )


def response_used_tools(choice: dict) -> bool:
    """Did the model reply with tool calls rather than an answer?

    Even with a tool-free request, a gateway may inject its own. The reply
    shape gives it away.
    """
    message = choice.get("message") or choice.get("delta") or {}
    if message.get("tool_calls") or message.get("function_call"):
        return True
    return choice.get("finish_reason") in {"tool_calls", "function_call"}


def find_prompt_leak(prompt: str, secret: str) -> str | None:
    """Return the first meaningful run of `secret` that appears in `prompt`.

    Compares whitespace-normalised lines rather than tokens: a token-level
    check drowns in false positives on ordinary Python, and a whole-file check
    misses a single leaked assertion — which is all it takes.

    `None` means clean.
    """
    haystack = _normalise(prompt)
    for line in secret.splitlines():
        candidate = _normalise(line)
        if len(candidate) < _MIN_NGRAM_CHARS:
            continue
        if candidate in haystack:
            return candidate
    return None


def assert_no_prompt_leak(prompt: str, secret: str, *, case_id: str,
                          dimension: str | None = None) -> None:
    """Fail loudly if a case's hidden material reached the model's prompt.

    `test-authoring` is exempt: there the model is handed an implementation and
    asked to write tests that catch its planted bug, so prompt/hidden-test
    overlap *is* the task. What stays hidden is which behaviour is wrong.
    """
    if dimension == "test-authoring":
        return
    leaked = find_prompt_leak(prompt, secret)
    if leaked is not None:
        raise IntegrityError(
            f"case {case_id}: hidden test content reached the prompt — "
            f"{leaked[:80]!r}. Any score from this case would measure "
            "recall of the answer, not capability."
        )
