"""Prove the code-exec axis discriminates instead of collapsing to 1.0 / 0.0.

Runs five synthetic "model outputs" of descending quality against every real
case and reports the score spread, plus the failure-mode breakdown. Under the
old compilable-code scorer, EVERY one of these except the non-code and
syntax-error rows would have scored 1.0.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from gauntlet.scoring.execute import code_execution_match

REPO = Path.cwd()
CASES = REPO / "cases" / "code-gen"
TESTS = CASES / "tests"
REF = TESTS / "reference"
REG = json.loads((CASES / "registry.json").read_text(encoding="utf-8"))

PROSE = "I'd be happy to help! Could you clarify the expected output format?"
BROKEN = "def solve(:\n    return None\n"
# Must hang at MODULE level. A `def` containing `while True` is never called
# by check() when the expected symbol is missing, so it returns instantly and
# scores wrong_answer — which measured the fixture, not the timeout path.
HANG = "def solve(x):\n    return x\n\nwhile True:\n    pass\n"


def run(label: str, source_for):
    scores, modes = [], Counter()
    for cid in sorted(REG):
        src = source_for(cid)
        if src is None:
            continue
        r = code_execution_match(src, TESTS / f"{cid}.py", timeout_s=5.0)
        scores.append(0.0 if r.score is None else r.score)
        modes[r.failure_mode] += 1
    mean = sum(scores) / len(scores) if scores else 0.0
    top = ", ".join(f"{m}={n}" for m, n in modes.most_common(3))
    print(f"  {label:<26} mean={mean:.3f}  n={len(scores):<4} {top}")
    return mean


def main():
    print(f"\nDiscrimination check over {len(REG)} execution-scored cases\n")
    means = {}
    means["excellent"] = run(
        "excellent (reference)",
        lambda c: (REF / f"{c}.ref.py").read_text(encoding="utf-8"))
    means["subtly wrong"] = run(
        "subtly wrong",
        lambda c: (REF / f"{c}.wrong.py").read_text(encoding="utf-8"))
    means["prose, no code"] = run("prose, no code", lambda c: PROSE)
    means["syntax error"] = run("syntax error", lambda c: BROKEN)
    means["infinite loop"] = run("infinite loop", lambda c: HANG)

    spread = means["excellent"] - means["prose, no code"]
    print(f"\n  spread (excellent - no code) = {spread:.3f}")
    mid = means["subtly wrong"]
    print(f"  subtly-wrong sits at {mid:.3f} — partial credit, not a cliff")
    print("\n  Under compilable-code, 'excellent' and 'subtly wrong' both "
          "scored 1.0.\n")


if __name__ == "__main__":
    main()
