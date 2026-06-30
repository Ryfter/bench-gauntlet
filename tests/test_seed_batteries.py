import json
from pathlib import Path

import jsonschema
import yaml

from gauntlet.battery import load_batteries

ROOT = Path(__file__).resolve().parents[1]


def test_seeded_batteries_load_clean():
    bats = {b.capability: b for b in load_batteries(ROOT / "batteries")}
    # every seeded capability parses
    assert {"commit-msg", "extract-json", "code-gen", "summarize-short",
            "code-debug", "reasoning", "classify"} <= set(bats)
    # each battery has at least one case
    assert all(b.cases for b in bats.values())


def test_seeded_case_prompt_files_exist():
    bats = load_batteries(ROOT / "batteries")
    for b in bats:
        for case in b.cases:
            if case.prompt_file:
                assert (ROOT / case.prompt_file).exists(), case.prompt_file
            if case.schema_file:
                assert (ROOT / case.schema_file).exists(), case.schema_file


def test_seeded_case_ids_are_unique_per_battery():
    bats = load_batteries(ROOT / "batteries")
    for b in bats:
        ids = [case.id for case in b.cases]
        assert len(ids) == len(set(ids)), b.capability


def test_seeded_scoring_cases_have_required_fields():
    bats = load_batteries(ROOT / "batteries")
    for b in bats:
        for case in b.cases:
            if case.scoring == "exact":
                assert case.expect is not None, case.id
            if case.scoring == "regex":
                assert case.pattern is not None, case.id
            if case.scoring == "json-schema":
                assert case.schema_file is not None, case.id
            if case.scoring == "judge":
                assert case.rubric is not None, case.id


def test_seeded_json_schemas_are_valid():
    bats = load_batteries(ROOT / "batteries")
    for b in bats:
        for case in b.cases:
            if case.schema_file:
                schema = json.loads((ROOT / case.schema_file).read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)


def test_embed_corpus_is_well_formed():
    spec = yaml.safe_load((ROOT / "cases/embed/corpus.yaml").read_text(encoding="utf-8"))
    assert len(spec["queries"]) == len(spec["relevant"])
    assert all(0 <= i < len(spec["corpus"]) for i in spec["relevant"])
