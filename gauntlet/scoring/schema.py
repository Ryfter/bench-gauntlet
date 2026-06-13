from __future__ import annotations

import json
import re

import jsonschema

from gauntlet.scoring import _extract_json, _strip_fences

# type[(scope)][!]: description
_CONVENTIONAL_RE = re.compile(
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\([^)]+\))?!?: .+",
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


def conventional_commit_match(output: str) -> bool:
    first_line = _strip_fences(output).splitlines()[0] if output.strip() else ""
    return _CONVENTIONAL_RE.match(first_line) is not None


def compilable_code_match(output: str, lang: str = "python") -> bool:
    code = _strip_fences(output)
    if lang == "python":
        try:
            compile(code, "<case>", "exec")
        except SyntaxError:
            return False
        return True
    raise ValueError(f"compilable-code: unsupported lang {lang!r}")
