"""Tests for `gauntlet add-case` — interactive case addition to an existing battery."""
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gauntlet.battery import load_battery
from gauntlet.cli import app

runner = CliRunner()

COMMIT_MSG_YAML = """\
capability: commit-msg
context_floor: 0
cases:
  - id: existing-01
    prompt_file: cases/commit-msg/existing-01.txt
    scoring: conventional-commit
weights: { quality: 1.0 }
"""


def _make_battery(tmp_path: Path, yaml_content: str = COMMIT_MSG_YAML, capability: str = "commit-msg") -> Path:
    bat_dir = tmp_path / "batteries"
    bat_dir.mkdir(exist_ok=True)
    (bat_dir / f"{capability}.yaml").write_text(yaml_content, encoding="utf-8")
    return bat_dir


# ---------------------------------------------------------------------------
# Happy-path: compilable-code (no extra fields)
# ---------------------------------------------------------------------------

def test_add_case_compilable_code_creates_prompt_and_updates_yaml(tmp_path):
    bat_dir = _make_battery(tmp_path)
    result = runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        input="new-case\ncompilable-code\nWrite a Python function.\n\n",
    )
    assert result.exit_code == 0, result.output

    prompt_file = tmp_path / "cases" / "commit-msg" / "new-case.txt"
    assert prompt_file.exists()
    assert "Write a Python function." in prompt_file.read_text(encoding="utf-8")

    bat = load_battery(bat_dir / "commit-msg.yaml")
    ids = [c.id for c in bat.cases]
    assert "existing-01" in ids
    assert "new-case" in ids
    new = next(c for c in bat.cases if c.id == "new-case")
    assert new.scoring == "compilable-code"
    assert new.prompt_file == "cases/commit-msg/new-case.txt"


# ---------------------------------------------------------------------------
# Exact scoring — expect field preserved
# ---------------------------------------------------------------------------

def test_add_case_exact_scoring_writes_expect(tmp_path):
    bat_dir = _make_battery(tmp_path)
    result = runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        input="exact-case\nexact\n42\nWhat is 6 * 7?\n\n",
    )
    assert result.exit_code == 0, result.output

    bat = load_battery(bat_dir / "commit-msg.yaml")
    new = next(c for c in bat.cases if c.id == "exact-case")
    assert new.scoring == "exact"
    assert new.expect == "42"


# ---------------------------------------------------------------------------
# Regex scoring — backslash patterns survive YAML round-trip
# ---------------------------------------------------------------------------

def test_add_case_regex_scoring_preserves_backslash_pattern(tmp_path):
    bat_dir = _make_battery(tmp_path)
    result = runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        # double-backslash in the Python string becomes single backslash in stdin
        input="regex-case\nregex\nreturn\\s+result\nFix the missing return.\n\n",
    )
    assert result.exit_code == 0, result.output

    bat = load_battery(bat_dir / "commit-msg.yaml")
    new = next(c for c in bat.cases if c.id == "regex-case")
    assert new.scoring == "regex"
    assert new.pattern == r"return\s+result"  # single backslash


# ---------------------------------------------------------------------------
# Judge scoring — rubric field written
# ---------------------------------------------------------------------------

def test_add_case_judge_scoring_writes_rubric(tmp_path):
    bat_dir = _make_battery(tmp_path)
    result = runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        input="judge-case\njudge\nScore 0-1 for clarity.\nWrite a commit message.\n\n",
    )
    assert result.exit_code == 0, result.output

    bat = load_battery(bat_dir / "commit-msg.yaml")
    new = next(c for c in bat.cases if c.id == "judge-case")
    assert new.scoring == "judge"
    assert new.rubric == "Score 0-1 for clarity."


# ---------------------------------------------------------------------------
# json-schema scoring — schema_file field written, nothing else required
# ---------------------------------------------------------------------------

def test_add_case_json_schema_writes_schema_file_field(tmp_path):
    bat_dir = _make_battery(tmp_path)
    result = runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        input="schema-case\njson-schema\nExtract the JSON.\n\n",
    )
    assert result.exit_code == 0, result.output

    bat = load_battery(bat_dir / "commit-msg.yaml")
    new = next(c for c in bat.cases if c.id == "schema-case")
    assert new.scoring == "json-schema"
    assert new.schema_file == "cases/commit-msg/schema-case.schema.json"


# ---------------------------------------------------------------------------
# Duplicate ID is rejected (loop asks again)
# ---------------------------------------------------------------------------

def test_add_case_duplicate_id_prompts_again(tmp_path):
    bat_dir = _make_battery(tmp_path)
    result = runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        # first attempt: existing ID → rejected; second: fresh ID → accepted
        input="existing-01\nunique-new\ncompilable-code\nSome prompt.\n\n",
    )
    assert result.exit_code == 0, result.output
    assert "already exists" in result.output

    bat = load_battery(bat_dir / "commit-msg.yaml")
    assert any(c.id == "unique-new" for c in bat.cases)


# ---------------------------------------------------------------------------
# Unknown capability → non-zero exit
# ---------------------------------------------------------------------------

def test_add_case_unknown_capability_exits_nonzero(tmp_path):
    bat_dir = tmp_path / "batteries"
    bat_dir.mkdir()
    result = runner.invoke(
        app,
        ["add-case", "nonexistent", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# --from-file reads prompt from disk instead of stdin
# ---------------------------------------------------------------------------

def test_add_case_from_file_reads_prompt_content(tmp_path):
    bat_dir = _make_battery(tmp_path)
    src = tmp_path / "my_prompt.txt"
    src.write_text("Prompt loaded from file.\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["add-case", "commit-msg",
         "--batteries", str(bat_dir),
         "--prompts", str(tmp_path),
         "--from-file", str(src)],
        input="file-case\nconventional-commit\n",
    )
    assert result.exit_code == 0, result.output

    prompt_file = tmp_path / "cases" / "commit-msg" / "file-case.txt"
    assert prompt_file.read_text(encoding="utf-8") == "Prompt loaded from file.\n"


# ---------------------------------------------------------------------------
# Empty cases: [] (flow sequence) is handled correctly
# ---------------------------------------------------------------------------

def test_add_case_empty_flow_sequence_battery(tmp_path):
    bat_dir = tmp_path / "batteries"
    bat_dir.mkdir()
    (bat_dir / "reasoning.yaml").write_text(
        "capability: reasoning\ncontext_floor: 0\ncases: []\nweights: { quality: 1.0 }\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["add-case", "reasoning", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        input="q1\nexact\n42\nWhat is 6 * 7?\n\n",
    )
    assert result.exit_code == 0, result.output

    bat = load_battery(bat_dir / "reasoning.yaml")
    assert len(bat.cases) == 1
    assert bat.cases[0].id == "q1"
    assert bat.cases[0].expect == "42"


# ---------------------------------------------------------------------------
# Battery is still loadable after add-case (round-trip sanity)
# ---------------------------------------------------------------------------

def test_add_case_battery_round_trips_correctly(tmp_path):
    bat_dir = _make_battery(tmp_path)
    runner.invoke(
        app,
        ["add-case", "commit-msg", "--batteries", str(bat_dir), "--prompts", str(tmp_path)],
        input="rt-case\ncompilable-code\nRound-trip prompt.\n\n",
    )

    bat = load_battery(bat_dir / "commit-msg.yaml")
    assert bat.capability == "commit-msg"
    assert bat.context_floor == 0
    assert len(bat.cases) == 2
    ids = [c.id for c in bat.cases]
    assert "existing-01" in ids
    assert "rt-case" in ids
