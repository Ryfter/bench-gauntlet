from gauntlet.scoring.schema import (
    compilable_code_match,
    conventional_commit_match,
    json_schema_match,
)

INVOICE_SCHEMA = {
    "type": "object",
    "required": ["invoice_no", "total"],
    "properties": {"invoice_no": {"type": "string"}, "total": {"type": "number"}},
}


def test_json_schema_match_validates_fenced_json():
    good = '```json\n{"invoice_no": "A-1", "total": 42.5}\n```'
    assert json_schema_match(good, INVOICE_SCHEMA) is True


def test_json_schema_match_rejects_missing_field():
    bad = '{"invoice_no": "A-1"}'
    assert json_schema_match(bad, INVOICE_SCHEMA) is False


def test_json_schema_match_rejects_non_json():
    assert json_schema_match("not json at all", INVOICE_SCHEMA) is False


def test_conventional_commit_match():
    assert conventional_commit_match("feat: add runner") is True
    assert conventional_commit_match("feat(scope)!: breaking") is True
    assert conventional_commit_match("just some text") is False


def test_compilable_code_match_python():
    assert compilable_code_match("def f(x):\n    return x + 1\n", lang="python") is True
    assert compilable_code_match("def f(x) return x", lang="python") is False  # missing colon


def test_compilable_code_strips_fences():
    assert compilable_code_match("```python\nx = 1\n```", lang="python") is True
