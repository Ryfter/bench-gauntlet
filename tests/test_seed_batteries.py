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
            if case.tests_file:
                assert (ROOT / case.tests_file).exists(), case.tests_file


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
            if case.scoring == "code-exec":
                assert case.tests_file is not None, case.id


def test_seeded_json_schemas_are_valid():
    bats = load_batteries(ROOT / "batteries")
    for b in bats:
        for case in b.cases:
            if case.schema_file:
                schema = json.loads((ROOT / case.schema_file).read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)


def test_extract_json_cases_accept_sources_and_reject_degenerate_constants():
    from gauntlet.scoring import score_case
    battery = next(b for b in load_batteries(ROOT / "batteries")
                   if b.capability == "extract-json")
    correct = {
        "invoice-01": {"invoice_no": "A-1007", "total": 4250.0},
        "contact-card": {"name": "Sarah Chen", "email": "sarah.chen@nexaflow.io",
                         "phone": "+1 (415) 882-0034", "company": "Nexaflow Systems"},
        "event-announce": {"title": "Mountain West Developer Summit",
                           "date": "August 14, 2026",
                           "location": "Salt Lake Convention Center, Hall C",
                           "price_usd": 149},
        "product-list": [
            {"name": "Apex Trail Runner", "price_usd": 129.99},
            {"name": "Summit Daypack", "price_usd": 84.50},
            {"name": "HydroCore water filter", "price_usd": 49.00},
            {"name": "Ridgeline Trekking Poles", "price_usd": 67.95},
        ],
    }
    for case in battery.cases:
        good = score_case(case, json.dumps(correct[case.id]), base_dir=ROOT)
        bad_value = [] if case.id == "product-list" else {
            key: (0 if key in {"total", "price_usd"} else "")
            for key in correct[case.id]
        }
        bad = score_case(case, json.dumps(bad_value), base_dir=ROOT)
        assert good.passed, case.id
        assert not bad.passed, case.id


def test_embed_corpus_is_well_formed():
    spec = yaml.safe_load((ROOT / "cases/embed/corpus.yaml").read_text(encoding="utf-8"))
    assert len(spec["queries"]) == len(spec["relevant"])
    assert all(0 <= i < len(spec["corpus"]) for i in spec["relevant"])
