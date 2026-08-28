from __future__ import annotations

import json
import re

import jsonschema

from gauntlet.scoring import _extract_json, _strip_fences

# type[(scope)][!]: description
_CONVENTIONAL_RE = re.compile(
    r"^(?P<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(?P<scope>\([^)]+\))?(?P<breaking>!)?: .+",
)


def json_schema_match(output: str, schema: dict) -> bool:
    try:
        data = _extract_json(output)
    except json.JSONDecodeError:
        return False
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError:
        return False
    return True


def conventional_commit_match(output: str, *, commit_type: str | None = None,
                              required_terms: list[str] | None = None,
                              require_breaking: bool = False) -> bool:
    text = _strip_fences(output)
    first_line = text.splitlines()[0] if text.strip() else ""
    match = _CONVENTIONAL_RE.fullmatch(first_line)
    if match is None:
        return False
    if commit_type is not None and match.group("type") != commit_type:
        return False
    lowered = text.lower()
    if any(term.lower() not in lowered for term in (required_terms or [])):
        return False
    if require_breaking:
        return bool(match.group("breaking")) and "breaking change:" in lowered
    return True


def compilable_code_match(output: str, lang: str = "python") -> bool:
    code = _strip_fences(output)
    if lang == "python":
        try:
            compile(code, "<case>", "exec")
        except SyntaxError:
            return False
        return True
    raise ValueError(f"compilable-code: unsupported lang {lang!r}")
