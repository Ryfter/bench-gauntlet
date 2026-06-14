# Gauntlet Scoring & Scorecard Implementation Plan (Plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn model outputs into scores, and scores into the scorecard contract — deterministic scorers, a pluggable judge, cell aggregation, and JSON/Markdown emission with a private/shared split and a leak guard.

**Architecture:** Pure scoring functions (output string + params → result) live under `gauntlet/scoring/`; a thin `score_case` dispatch resolves a `Case` to the right scorer. `gauntlet/scorecard.py` aggregates `CaseResult`s into a `Cell`, assembles a `Scorecard`, and emits canonical JSON + a Markdown report, with `--share` dropping the private hostname and a pre-write assertion refusing any IP/URL leak. Builds on Plan 1's `models.py`, `battery.py`, `client.py`, `errors.py`. Covers design Phases 3–4.

**Tech Stack:** Python 3.12+, pydantic v2, jsonschema, httpx (judge path, tested via `httpx.MockTransport`), Typer, pytest.

**Source of truth:** `docs/2026-06-12-gauntlet-build-design.md` (Section C "Scoring dispatch" + "Error taxonomy"; Section A.5 + B for the scorecard split). Plan 1 already shipped the contracts this plan consumes.

---

## File Structure

- `gauntlet/scoring/__init__.py` — `Scorer` protocol, `_strip_fences`/`_extract_json` helpers, `score_case` dispatch
- `gauntlet/scoring/exact.py` — `exact_match`, `regex_match`
- `gauntlet/scoring/schema.py` — `json_schema_match`, `conventional_commit_match`, `compilable_code_match`
- `gauntlet/scoring/judge.py` — `parse_verdict`, `select_judge`, `score_with_judge`
- `gauntlet/scorecard.py` — `aggregate_cell`, `to_dict`, `assert_no_leak`, `write_json`, `render_markdown`, `write_markdown`
- `gauntlet/battery.py` — MODIFY: add optional `expect` / `pattern` fields to `Case`
- `gauntlet/cli.py` — MODIFY: add `report` command
- `tests/test_scoring_*.py`, `tests/test_scorecard*.py`, `tests/test_cli_report.py`

**Reused from Plan 1 (do not redefine):** `gauntlet.models.CaseResult` (`case_id`, `method`, `score: float|None`, `passed`, `detail`), `gauntlet.models.Cell` / `Scorecard` / `RunMeta`, `gauntlet.battery.Case` / `Battery`, `gauntlet.client.OpenAIClient` (`chat(model, prompt, max_tokens, temperature) -> ChatResult(text, completion_tokens, latency_s)`), `gauntlet.errors`.

---

## Task 3.1: Exact + regex scorers (and Case gains expect/pattern)

**Files:**
- Modify: `gauntlet/battery.py` (add `expect`, `pattern` to `Case`)
- Create: `gauntlet/scoring/__init__.py`, `gauntlet/scoring/exact.py`, `tests/test_scoring_exact.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scoring_exact.py
from gauntlet.scoring.exact import exact_match, regex_match


def test_exact_match_trims_and_compares():
    assert exact_match("  hello\n", "hello") is True
    assert exact_match("hello", "world") is False


def test_exact_match_strips_code_fences():
    assert exact_match("```\nhello\n```", "hello") is True


def test_regex_match_searches():
    assert regex_match("commit abc123 done", r"[0-9a-f]{6}") is True
    assert regex_match("no hex here", r"[0-9a-f]{6}") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_exact.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.scoring'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/scoring/__init__.py
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
```

```python
# gauntlet/scoring/exact.py
from __future__ import annotations

import re

from gauntlet.scoring import _strip_fences


def exact_match(output: str, expect: str) -> bool:
    return _strip_fences(output) == expect.strip()


def regex_match(output: str, pattern: str) -> bool:
    return re.search(pattern, output) is not None
```

- [ ] **Step 4: Add the optional Case fields**

In `gauntlet/battery.py`, extend `Case` (keep existing fields):

```python
class Case(BaseModel):
    id: str
    prompt_file: str | None = None
    scoring: Scoring
    schema_file: str | None = None
    rubric: str | None = None
    expect: str | None = None     # exact scoring: the expected output
    pattern: str | None = None    # regex scoring: the pattern to find
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_exact.py tests/test_battery.py -v`
Expected: PASS (existing battery tests still green)

- [ ] **Step 6: Commit**

```bash
git add gauntlet/scoring/__init__.py gauntlet/scoring/exact.py gauntlet/battery.py tests/test_scoring_exact.py
git commit -m "feat: exact + regex scorers; Case gains expect/pattern"
```

---

## Task 3.2: Schema, conventional-commit, compilable-code scorers

**Files:**
- Create: `gauntlet/scoring/schema.py`, `tests/test_scoring_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scoring_schema.py
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
    assert compilable_code_match("def f(x): return", lang="python") is False


def test_compilable_code_strips_fences():
    assert compilable_code_match("```python\nx = 1\n```", lang="python") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.scoring.schema'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/scoring/schema.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/scoring/schema.py tests/test_scoring_schema.py
git commit -m "feat: json-schema, conventional-commit, compilable-code scorers"
```

---

## Task 3.3: `score_case` dispatch

**Files:**
- Modify: `gauntlet/scoring/__init__.py`
- Create: `tests/test_scoring_dispatch.py`

The dispatch reads a `Case`, resolves any `schema_file` relative to a base dir,
calls the right pure scorer, and returns a `CaseResult`. The `judge` method is
NOT handled here (it needs a live client) — dispatch returns a sentinel the
runner (Plan 3) fulfils; this task asserts that contract.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scoring_dispatch.py
import json

import pytest

from gauntlet.battery import Case
from gauntlet.scoring import NEEDS_JUDGE, score_case


def test_dispatch_exact():
    case = Case(id="c1", scoring="exact", expect="hello")
    res = score_case(case, "  hello ")
    assert res.method == "exact"
    assert res.passed is True
    assert res.score == 1.0


def test_dispatch_regex_fail_scores_zero():
    case = Case(id="c2", scoring="regex", pattern=r"\d{6}")
    res = score_case(case, "no digits")
    assert res.passed is False
    assert res.score == 0.0


def test_dispatch_json_schema_reads_schema_file(tmp_path):
    schema = {"type": "object", "required": ["x"], "properties": {"x": {"type": "number"}}}
    sf = tmp_path / "s.json"
    sf.write_text(json.dumps(schema), encoding="utf-8")
    case = Case(id="c3", scoring="json-schema", schema_file="s.json")
    res = score_case(case, '{"x": 1}', base_dir=tmp_path)
    assert res.passed is True
    assert res.score == 1.0


def test_dispatch_conventional_commit():
    case = Case(id="c4", scoring="conventional-commit")
    assert score_case(case, "feat: x").passed is True


def test_dispatch_judge_returns_needs_judge_sentinel():
    case = Case(id="c5", scoring="judge", rubric="grade it")
    res = score_case(case, "anything")
    assert res is NEEDS_JUDGE


def test_dispatch_missing_param_raises():
    case = Case(id="c6", scoring="exact")  # no expect
    with pytest.raises(ValueError):
        score_case(case, "x")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_dispatch.py -v`
Expected: FAIL — `ImportError: cannot import name 'NEEDS_JUDGE'`

- [ ] **Step 3: Write minimal implementation**

Append to `gauntlet/scoring/__init__.py`:

```python
import json as _json
from pathlib import Path

from gauntlet.battery import Case

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_dispatch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/scoring/__init__.py tests/test_scoring_dispatch.py
git commit -m "feat: score_case dispatch (deterministic methods + NEEDS_JUDGE sentinel)"
```

---

## Task 3.4: Judge path — verdict parsing, same-family guard, scoring

**Files:**
- Create: `gauntlet/scoring/judge.py`, `tests/test_scoring_judge.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scoring_judge.py
import httpx

from gauntlet.client import OpenAIClient
from gauntlet.scoring.judge import parse_verdict, score_with_judge, select_judge


def test_parse_verdict_reads_score_and_passed():
    score, passed = parse_verdict('{"score": 0.8, "passed": true, "reason": "ok"}')
    assert score == 0.8
    assert passed is True


def test_parse_verdict_tolerates_fences_and_prose():
    score, passed = parse_verdict('Here:\n```json\n{"score": 1, "passed": true}\n```')
    assert score == 1.0
    assert passed is True


def test_parse_verdict_clamps_and_derives_passed_from_threshold():
    # passed omitted -> derived from score >= 0.5
    score, passed = parse_verdict('{"score": 0.4}')
    assert score == 0.4
    assert passed is False


def test_parse_verdict_bad_json_raises():
    import pytest
    with pytest.raises(ValueError):
        parse_verdict("not a verdict")


def test_select_judge_avoids_same_family():
    candidates = [("gemma3:12b", "gemma3"), ("dolphin3:8b", "llama")]
    assert select_judge(candidates, target_family="gemma3") == "dolphin3:8b"


def test_select_judge_none_when_all_same_family():
    candidates = [("gemma3:12b", "gemma3")]
    assert select_judge(candidates, target_family="gemma3") is None


def test_score_with_judge_calls_model_and_returns_caseresult():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"score": 0.9, "passed": true}'}}],
        })

    client = OpenAIClient(base_url="http://j:1", transport=httpx.MockTransport(handler))
    res = score_with_judge(client, judge_model="dolphin3:8b",
                           rubric="grade completeness", output="some answer", case_id="c1")
    assert res.case_id == "c1"
    assert res.method == "judge"
    assert res.score == 0.9
    assert res.passed is True


def test_score_with_judge_unparseable_marks_unscored():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "garbage"}}]})

    client = OpenAIClient(base_url="http://j:1", transport=httpx.MockTransport(handler))
    res = score_with_judge(client, judge_model="dolphin3:8b",
                           rubric="x", output="y", case_id="c2")
    assert res.score is None       # unscored — never silently 0
    assert res.passed is False
    assert "unscored" in res.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.scoring.judge'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/scoring/judge.py
"""LLM-judge scoring. The judge must be a non-reasoning strict-JSON model, and a
judge never grades its own model family (select_judge enforces this). A verdict
that cannot be parsed is recorded as unscored — never silently 0 (design G.5)."""
from __future__ import annotations

import json

from gauntlet.client import OpenAIClient
from gauntlet.models import CaseResult
from gauntlet.scoring import _extract_json

_PASS_THRESHOLD = 0.5

JUDGE_PROMPT = (
    "You are a strict grader. Apply the rubric to the answer and respond with "
    "ONLY a JSON object: {{\"score\": <0..1 float>, \"passed\": <bool>}}.\n\n"
    "Rubric: {rubric}\n\nAnswer:\n{output}\n"
)


def parse_verdict(text: str) -> tuple[float, bool]:
    """Return (score in 0..1, passed). Raises ValueError if no usable verdict."""
    try:
        data = _extract_json(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"unparseable judge verdict: {text!r}") from exc
    if not isinstance(data, dict) or "score" not in data:
        raise ValueError(f"verdict missing 'score': {data!r}")
    score = max(0.0, min(1.0, float(data["score"])))
    passed = bool(data["passed"]) if "passed" in data else score >= _PASS_THRESHOLD
    return score, passed


def select_judge(candidates: list[tuple[str, str]], target_family: str) -> str | None:
    """Pick the first (model_id, family) whose family differs from the model under
    test. Returns None if no different-family judge is available."""
    for model_id, family in candidates:
        if family != target_family:
            return model_id
    return None


def score_with_judge(client: OpenAIClient, judge_model: str, rubric: str,
                     output: str, case_id: str) -> CaseResult:
    prompt = JUDGE_PROMPT.format(rubric=rubric, output=output)
    reply = client.chat(model=judge_model, prompt=prompt, max_tokens=200)
    try:
        score, passed = parse_verdict(reply.text)
    except ValueError as exc:
        return CaseResult(case_id=case_id, method="judge", score=None, passed=False,
                          detail=f"unscored: {exc}")
    return CaseResult(case_id=case_id, method="judge", score=score, passed=passed,
                      detail=f"judge={judge_model}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scoring_judge.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/scoring/judge.py tests/test_scoring_judge.py
git commit -m "feat: judge path — verdict parsing, same-family guard, unscored-on-garbage"
```

---

## Task 4.1: Cell aggregation

**Files:**
- Create: `gauntlet/scorecard.py`, `tests/test_scorecard_aggregate.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scorecard_aggregate.py
from gauntlet.models import CaseResult
from gauntlet.scorecard import aggregate_cell


def _r(score, passed, method="exact"):
    return CaseResult(case_id="x", method=method, score=score, passed=passed)


def test_aggregate_quality_and_pass_rate():
    results = [_r(1.0, True), _r(0.0, False), _r(0.5, True)]
    cell = aggregate_cell(
        model="gemma3:1b", target="box-b-ollama", box="RTX 2070 Super laptop",
        context=8192, capability="extract-json", results=results,
        latency_p50_s=2.0, tokens_per_s=40.0,
    )
    assert cell.cases == 3
    assert cell.pass_rate == 2 / 3
    assert abs(cell.quality - 0.5) < 1e-9   # mean of scored: (1+0+0.5)/3
    assert cell.errors == 0


def test_aggregate_excludes_unscored_from_quality_but_counts_case():
    results = [_r(1.0, True), _r(None, False, method="judge")]
    cell = aggregate_cell(
        model="m", target="t", box="b", context=8192, capability="c", results=results,
    )
    assert cell.cases == 2
    assert cell.quality == 1.0          # only the scored case counts toward quality
    assert cell.pass_rate == 0.5        # passed / total cases


def test_aggregate_all_unscored_yields_none_quality():
    results = [_r(None, False, method="judge")]
    cell = aggregate_cell(model="m", target="t", box="b", context=1, capability="c",
                          results=results)
    assert cell.quality is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scorecard_aggregate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gauntlet.scorecard'`

- [ ] **Step 3: Write minimal implementation**

```python
# gauntlet/scorecard.py
"""Aggregate CaseResults into a Cell, assemble a Scorecard, and emit it as
canonical JSON + a Markdown report. Private vs shared (`--share`) differ only in
whether the hostname label is dropped; neither mode ever carries a base_url/IP
(the Cell has no such field), and `assert_no_leak` is a belt-and-braces guard."""
from __future__ import annotations

from gauntlet.models import Cell, CaseResult


def aggregate_cell(
    model: str,
    target: str | None,
    box: str,
    context: int,
    capability: str,
    results: list[CaseResult],
    latency_p50_s: float | None = None,
    tokens_per_s: float | None = None,
    errors: int = 0,
) -> Cell:
    scored = [r.score for r in results if r.score is not None]
    quality = sum(scored) / len(scored) if scored else None
    pass_rate = (sum(1 for r in results if r.passed) / len(results)) if results else None
    return Cell(
        model=model, target=target, box=box, context=context, capability=capability,
        quality=quality, pass_rate=pass_rate, latency_p50_s=latency_p50_s,
        tokens_per_s=tokens_per_s, cases=len(results), errors=errors,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scorecard_aggregate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/scorecard.py tests/test_scorecard_aggregate.py
git commit -m "feat: aggregate_cell (quality excludes unscored; pass_rate over all cases)"
```

---

## Task 4.2: JSON emission, `--share`, and leak guard

**Files:**
- Modify: `gauntlet/scorecard.py`
- Create: `tests/test_scorecard_json.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scorecard_json.py
import json

import pytest

from gauntlet import errors
from gauntlet.models import Cell, Scorecard
from gauntlet.scorecard import assert_no_leak, to_dict, write_json


def _sc() -> Scorecard:
    return Scorecard(
        run={"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        cells=[Cell(model="gemma3:1b", target="box-b-ollama", box="RTX 2070 Super laptop",
                    context=8192, capability="extract-json", quality=0.9, pass_rate=0.9,
                    cases=10, errors=0)],
    )


def test_private_mode_keeps_target():
    d = to_dict(_sc(), share=False)
    assert d["cells"][0]["target"] == "box-b-ollama"
    assert d["cells"][0]["box"] == "RTX 2070 Super laptop"


def test_share_mode_drops_target_keeps_hardware():
    d = to_dict(_sc(), share=True)
    assert "target" not in d["cells"][0]
    assert d["cells"][0]["box"] == "RTX 2070 Super laptop"


def test_assert_no_leak_rejects_ip():
    with pytest.raises(errors.GauntletError):
        assert_no_leak('{"x": "see http://203.0.113.10:11434"}')


def test_assert_no_leak_rejects_bare_ipv4():
    with pytest.raises(errors.GauntletError):
        assert_no_leak('{"host": "192.168.1.50"}')


def test_assert_no_leak_allows_clean_scorecard():
    assert_no_leak(json.dumps(to_dict(_sc(), share=True)))  # no raise


def test_write_json_round_trips(tmp_path):
    path = tmp_path / "card.json"
    write_json(_sc(), path, share=False)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["run"]["id"] == "r1"
    assert loaded["cells"][0]["model"] == "gemma3:1b"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scorecard_json.py -v`
Expected: FAIL — `ImportError: cannot import name 'to_dict'`

- [ ] **Step 3: Write minimal implementation**

Append to `gauntlet/scorecard.py`:

```python
import json
import re
from pathlib import Path

from gauntlet import errors
from gauntlet.models import Scorecard

# IPv4 (with optional :port) or any URL scheme — a scorecard must contain neither.
_LEAK_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b|[a-zA-Z][a-zA-Z0-9+.-]*://")


def to_dict(scorecard: Scorecard, share: bool = False) -> dict:
    data = scorecard.model_dump()
    if share:
        for cell in data["cells"]:
            cell.pop("target", None)
    return data


def assert_no_leak(text: str) -> None:
    """Refuse to emit a scorecard that contains an IP address or URL."""
    match = _LEAK_RE.search(text)
    if match:
        raise errors.GauntletError(
            f"refusing to write scorecard: looks like a leaked endpoint ({match.group()!r})"
        )


def write_json(scorecard: Scorecard, path: str | Path, share: bool = False) -> None:
    payload = json.dumps(to_dict(scorecard, share=share), indent=2)
    assert_no_leak(payload)
    Path(path).write_text(payload, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scorecard_json.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/scorecard.py tests/test_scorecard_json.py
git commit -m "feat: scorecard JSON emit + --share (drop hostname) + IP/URL leak guard"
```

---

## Task 4.3: Markdown report

**Files:**
- Modify: `gauntlet/scorecard.py`
- Create: `tests/test_scorecard_markdown.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scorecard_markdown.py
from gauntlet.models import Cell, Scorecard
from gauntlet.scorecard import render_markdown


def _sc() -> Scorecard:
    return Scorecard(
        run={"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
        cells=[
            Cell(model="gemma3:1b", target="box-b-ollama", box="RTX 2070 Super laptop",
                 context=8192, capability="extract-json", quality=0.91, pass_rate=0.86,
                 latency_p50_s=2.1, tokens_per_s=38.0, cases=14, errors=0),
            Cell(model="dolphin3:8b", target="box-b-ollama", box="RTX 2070 Super laptop",
                 context=8192, capability="extract-json", quality=None, pass_rate=None,
                 cases=2, errors=2),
        ],
    )


def test_markdown_has_run_header_and_rows():
    md = render_markdown(_sc(), share=True)
    assert "# Gauntlet scorecard" in md
    assert "r1" in md and "2026-06-13" in md
    assert "gemma3:1b" in md
    assert "RTX 2070 Super laptop" in md
    # share mode must not print the hostname label
    assert "box-b-ollama" not in md


def test_markdown_renders_unscored_as_dash():
    md = render_markdown(_sc(), share=True)
    # the dolphin row has quality=None -> rendered as "—", not "0"
    assert "—" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scorecard_markdown.py -v`
Expected: FAIL — `ImportError: cannot import name 'render_markdown'`

- [ ] **Step 3: Write minimal implementation**

Append to `gauntlet/scorecard.py`:

```python
def _fmt(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def render_markdown(scorecard: Scorecard, share: bool = False) -> str:
    run = scorecard.run
    lines = [
        "# Gauntlet scorecard",
        "",
        f"- **run:** {run.id}  **date:** {run.date}  **gauntlet:** {run.gauntlet_version}",
        "",
    ]
    header = ["model", "box", "ctx", "capability", "quality", "pass", "tok/s", "cases", "err"]
    if not share:
        header.insert(2, "target")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for c in scorecard.cells:
        row = [c.model, c.box]
        if not share:
            row.append(c.target or "—")
        row += [
            str(c.context), c.capability, _fmt(c.quality), _fmt(c.pass_rate),
            _fmt(c.tokens_per_s, 0), str(c.cases), str(c.errors),
        ]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def write_markdown(scorecard: Scorecard, path: str | Path, share: bool = False) -> None:
    text = render_markdown(scorecard, share=share)
    assert_no_leak(text)
    Path(path).write_text(text, encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python -m pytest tests/test_scorecard_markdown.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gauntlet/scorecard.py tests/test_scorecard_markdown.py
git commit -m "feat: scorecard Markdown report (unscored as em-dash, share drops hostname)"
```

---

## Task 4.4: `gauntlet report` command + full suite

**Files:**
- Modify: `gauntlet/cli.py`
- Create: `tests/test_cli_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_report.py
import json

from typer.testing import CliRunner

from gauntlet.cli import app

runner = CliRunner()

CARD = {
    "run": {"id": "r1", "date": "2026-06-13", "gauntlet_version": "0.1.0"},
    "cells": [{"model": "gemma3:1b", "target": "box-b-ollama",
               "box": "RTX 2070 Super laptop", "context": 8192,
               "capability": "extract-json", "quality": 0.9, "pass_rate": 0.9,
               "latency_p50_s": 2.0, "tokens_per_s": 38.0, "judge": None,
               "cases": 10, "errors": 0}],
    "context_depth": [], "baseline_gaps": [],
}


def test_report_prints_markdown(tmp_path):
    src = tmp_path / "card.json"
    src.write_text(json.dumps(CARD), encoding="utf-8")
    result = runner.invoke(app, ["report", str(src)])
    assert result.exit_code == 0
    assert "# Gauntlet scorecard" in result.stdout
    assert "gemma3:1b" in result.stdout


def test_report_share_writes_sanitized_json(tmp_path):
    src = tmp_path / "card.json"
    src.write_text(json.dumps(CARD), encoding="utf-8")
    out = tmp_path / "shared.json"
    result = runner.invoke(app, ["report", str(src), "--share", "--json-out", str(out)])
    assert result.exit_code == 0
    shared = json.loads(out.read_text(encoding="utf-8"))
    assert "target" not in shared["cells"][0]
    assert shared["cells"][0]["box"] == "RTX 2070 Super laptop"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_cli_report.py -v`
Expected: FAIL — report command missing (`No such command 'report'`)

- [ ] **Step 3: Write minimal implementation**

Append to `gauntlet/cli.py` (before the `if __name__` block):

```python
@app.command()
def report(
    scorecard_json: str = typer.Argument(..., help="Path to a scorecard JSON file"),
    share: bool = typer.Option(False, "--share", help="Drop hostname labels for sharing"),
    json_out: str = typer.Option(None, "--json-out", help="Also write sanitized JSON here"),
) -> None:
    """Render a Markdown report from a scorecard JSON (optionally sanitized for sharing)."""
    import json as _json

    from gauntlet.models import Scorecard
    from gauntlet.scorecard import render_markdown, write_json

    data = _json.loads(open(scorecard_json, encoding="utf-8").read())
    sc = Scorecard.model_validate(data)
    typer.echo(render_markdown(sc, share=share))
    if json_out:
        write_json(sc, json_out, share=share)
```

- [ ] **Step 4: Run tests + full suite**

Run: `.venv/Scripts/python -m pytest tests/test_cli_report.py -v`
Expected: PASS
Run: `.venv/Scripts/python -m pytest`
Expected: ALL PASS (live deselected).

- [ ] **Step 5: Commit**

```bash
git add gauntlet/cli.py tests/test_cli_report.py
git commit -m "feat: gauntlet report command (markdown + optional sanitized JSON)"
```

---

## Self-Review (completed during authoring)

- **Spec coverage (Phases 3–4):** exact/regex ✓ (3.1), json-schema/conventional-commit/compilable-code ✓ (3.2), dispatch ✓ (3.3), judge with non-reasoning strict-JSON + same-family guard + records which judge + unscored-on-failure ✓ (3.4), cell aggregation ✓ (4.1), JSON emit + `--share` dropping hostname + leak assertion ✓ (4.2), Markdown report ✓ (4.3), `report` command ✓ (4.4).
- **Deferred (intentional):** wiring judge into a live run, picking judge candidates from the roster, and producing real scorecards belong to Plan 3 (runner); `NEEDS_JUDGE` is the seam. `context_depth`/`baseline_gaps` population are Plan 4.
- **Placeholder scan:** none — every step has real code/commands.
- **Type consistency:** uses Plan 1's actual signatures — `CaseResult(case_id, method, score, passed, detail)`, `Cell(model, target, box, context, capability, quality, pass_rate, latency_p50_s, tokens_per_s, judge, cases, errors)`, `OpenAIClient.chat(model, prompt, max_tokens, ...) -> ChatResult(text, ...)`, `errors.GauntletError`. `score_case(case, output, base_dir=None)`, `aggregate_cell(...)`, `to_dict(sc, share)`, `render_markdown(sc, share)`, `write_json(sc, path, share)` names are consistent across tasks and tests.
```
