"""Validate + ingest Grok-authored code-gen cases.

A case is only accepted if it is machine-proven discriminative:
  reference solution -> score 1.0   (the asserts are satisfiable)
  wrong solution     -> score < 1.0 (the asserts actually catch a defect)
Anything else is rejected with a reason and never reaches the battery, so a
badly-authored case cannot silently poison the benchmark.

Usage:  python ingest_cases.py <batch.json> [--apply]
Without --apply it validates and reports only (dry run).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[0]
# repo root is wherever we were invoked from; resolve relative to cwd
REPO = Path.cwd()
sys.path.insert(0, str(REPO))

from gauntlet.scoring.execute import code_execution_match  # noqa: E402

CASES_DIR = REPO / "cases" / "code-gen"
TESTS_DIR = CASES_DIR / "tests"
VALID_TIERS = {"T1", "T2", "T3", "T4"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,40}$")

# Problems memorised by even 1B models — banned outright (anti-contamination).
BANNED = [
    "fizzbuzz", "fizz buzz", "fibonacci", "two sum", "two-sum", "palindrome",
    "binary search", "anagram", "reverse a string", "reverse the string",
    "bubble sort", "hello world", "factorial",
]


def _reject(case_id: str, reason: str) -> dict:
    return {"id": case_id, "ok": False, "reason": reason}


def validate(case: dict) -> dict:
    cid = case.get("id", "<no-id>")
    for field in ("id", "dimension", "tier", "prompt", "hidden_tests",
                  "reference", "wrong"):
        if not str(case.get(field, "")).strip():
            return _reject(cid, f"missing/empty field: {field}")

    if not ID_RE.match(case["id"]):
        return _reject(cid, "id must be kebab-case, 3-41 chars")
    if case["tier"] not in VALID_TIERS:
        return _reject(cid, f"bad tier {case['tier']!r}")
    if "def check(" not in case["hidden_tests"]:
        return _reject(cid, "hidden_tests must define check(ns)")

    blob = f"{case['id']} {case['prompt']}".lower()
    for bad in BANNED:
        if bad in blob:
            return _reject(cid, f"contaminated classic: {bad!r}")

    # The prompt must not leak the asserts to the model.
    #
    # test-authoring is exempt: there the model is *given* an implementation and
    # asked to write tests that catch its bug, so the prompt and the hidden
    # tests necessarily share that implementation. The overlap is the task, not
    # a leak — the answer the model must find (which behaviour is wrong) is
    # still never stated.
    if case["dimension"] != "test-authoring":
        for line in case["hidden_tests"].splitlines():
            line = line.strip()
            if len(line) > 25 and line in case["prompt"]:
                return _reject(cid, "hidden test content leaks into the prompt")

    with tempfile.TemporaryDirectory() as tmp:
        tf = Path(tmp) / "hidden_tests.py"
        tf.write_text(case["hidden_tests"], encoding="utf-8")

        ref = code_execution_match(case["reference"], tf, timeout_s=10.0)
        if ref.score != 1.0:
            return _reject(cid,
                           f"reference solution scored {ref.score} "
                           f"({ref.failure_mode}): {ref.detail[:200]}")

        wrong = code_execution_match(case["wrong"], tf, timeout_s=10.0)
        if wrong.score is None:
            return _reject(cid, f"wrong solution unscored: {wrong.detail[:200]}")
        if wrong.score >= 1.0:
            return _reject(cid, "wrong solution also scored 1.0 — asserts too weak")

    return {"id": cid, "ok": True, "wrong_score": round(wrong.score, 3),
            "tier": case["tier"], "dimension": case["dimension"]}


def apply(case: dict) -> None:
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    (CASES_DIR / f"{case['id']}.txt").write_text(
        case["prompt"].rstrip() + "\n", encoding="utf-8")
    (TESTS_DIR / f"{case['id']}.py").write_text(
        case["hidden_tests"].rstrip() + "\n", encoding="utf-8")
    # Reference + wrong solutions back the case-validation meta-test.
    ref_dir = TESTS_DIR / "reference"
    ref_dir.mkdir(exist_ok=True)
    (ref_dir / f"{case['id']}.ref.py").write_text(
        case["reference"].rstrip() + "\n", encoding="utf-8")
    (ref_dir / f"{case['id']}.wrong.py").write_text(
        case["wrong"].rstrip() + "\n", encoding="utf-8")

    # Central registry: the battery YAML is generated from this, and the
    # case-validation meta-test walks it.
    reg_path = CASES_DIR / "registry.json"
    reg = {}
    if reg_path.exists():
        reg = json.loads(reg_path.read_text(encoding="utf-8"))
    reg[case["id"]] = {"tier": case["tier"], "dimension": case["dimension"]}
    reg_path.write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")


def main() -> int:
    batch_path = Path(sys.argv[1])
    do_apply = "--apply" in sys.argv
    cases = json.loads(batch_path.read_text(encoding="utf-8"))
    if isinstance(cases, dict):
        cases = cases.get("cases", [])

    accepted, rejected = [], []
    for case in cases:
        verdict = validate(case)
        if verdict["ok"]:
            accepted.append((case, verdict))
        else:
            rejected.append(verdict)

    for case, v in accepted:
        if do_apply:
            apply(case)
        print(f"  PASS {v['id']:<34} {v['tier']}  {v['dimension']:<26} "
              f"wrong={v['wrong_score']}")
    for v in rejected:
        print(f"  FAIL {v['id']:<34} {v['reason']}")

    print(f"\n{len(accepted)} accepted, {len(rejected)} rejected"
          f"{' (applied)' if do_apply else ' (dry run)'}")

    if do_apply and accepted:
        out = Path("scratch_accepted.json")
        out.write_text(json.dumps(
            [{"id": c["id"], "tier": c["tier"], "dimension": c["dimension"]}
             for c, _ in accepted], indent=2), encoding="utf-8")
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
