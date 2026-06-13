"""Scoring. Pure scorers take an output string + params and return a bool/score;
`score_case` (Task 3.3) is the thin dispatch that wires a Case to a scorer."""
from __future__ import annotations

import json
import re
from typing import Protocol

from gauntlet.models import CaseResult

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n?|\n?```\s*$")


def _strip_fences(text: str) -> str:
    """Remove a single leading/trailing ``` code fence if present."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _FENCE_RE.sub("", stripped)
    return stripped.strip()


def _extract_json(text: str) -> object:
    """Parse JSON from output, tolerating code fences and surrounding prose."""
    candidate = _strip_fences(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    # Fall back to the first {...} or [...] span.
    for opener, closer in (("{", "}"), ("[", "]")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end > start:
            return json.loads(candidate[start : end + 1])
    raise json.JSONDecodeError("no JSON found", candidate, 0)


class Scorer(Protocol):
    def __call__(self, output: str, **params: object) -> CaseResult: ...
