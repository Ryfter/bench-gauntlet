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


import json as _json  # noqa: E402
from pathlib import Path  # noqa: E402

from gauntlet.battery import Case  # noqa: E402

# Sentinel: this case needs the live judge path (filled in by the runner, Plan 3).
NEEDS_JUDGE = CaseResult(case_id="", method="judge", score=None, passed=False,
                         detail="needs judge")


def _result(case: Case, method: str, ok: bool, detail: str = "") -> CaseResult:
    return CaseResult(case_id=case.id, method=method, score=1.0 if ok else 0.0,
                      passed=ok, detail=detail)


def score_case(case: Case, output: str, base_dir: Path | str | None = None) -> CaseResult:
    from gauntlet.scoring import exact, schema

    method = case.scoring
    if method == "exact":
        if case.expect is None:
            raise ValueError(f"case {case.id}: exact scoring requires 'expect'")
        return _result(case, method, exact.exact_match(output, case.expect))
    if method == "regex":
        if case.pattern is None:
            raise ValueError(f"case {case.id}: regex scoring requires 'pattern'")
        return _result(case, method, exact.regex_match(output, case.pattern))
    if method == "json-schema":
        if case.schema_file is None:
            raise ValueError(f"case {case.id}: json-schema scoring requires 'schema_file'")
        path = Path(base_dir or ".") / case.schema_file
        schema_dict = _json.loads(path.read_text(encoding="utf-8"))
        return _result(case, method, schema.json_schema_match(output, schema_dict))
    if method == "conventional-commit":
        return _result(case, method, schema.conventional_commit_match(output))
    if method == "compilable-code":
        return _result(case, method, schema.compilable_code_match(output))
    if method == "judge":
        return NEEDS_JUDGE
    raise ValueError(f"case {case.id}: unknown scoring method {method!r}")
