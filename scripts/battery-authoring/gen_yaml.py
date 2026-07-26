"""Regenerate batteries/code-gen.yaml from cases/code-gen/registry.json.

The contaminated classics (fizzbuzz / palindrome / binary-search / lru-cache /
csv-parse, all on the syntax-only `compilable-code` scorer) are deliberately
NOT carried over: they are memorised by even 1B models and score ~1.0 for
everyone, which is what made the axis non-discriminative in the first place.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path.cwd()
REG = json.loads((REPO / "cases" / "code-gen" / "registry.json").read_text(encoding="utf-8"))

TIER_ORDER = {"T1": 0, "T2": 1, "T3": 2, "T4": 3}

lines = [
    "capability: code-gen",
    "context_floor: 0",
    "# Reasoning models routinely spend 1500-3000 tokens thinking before their first",
    "# line of code. At the 512 default, seven of nine models in the 2026-07-26 fleet",
    "# run never reached an answer and scored ~0.00 -- the benchmark measuring its own",
    "# budget. gemma-4-12b writes correct code here given room to finish.",
    "max_tokens: 4096",
    "",
    "# Cases are execution-scored: the candidate's code is run against hidden",
    "# asserts in a subprocess sandbox and scored on the FRACTION passed, not on",
    "# whether it parses. Tiers T1-T4 form a difficulty ladder so scores spread",
    "# across a 1B-30B local fleet instead of collapsing to 1.0 or 0.0.",
    "# Regenerate with scratchpad/gen_yaml.py; see batteries/README.md.",
    "cases:",
]

items = sorted(REG.items(), key=lambda kv: (kv[1]["dimension"],
                                            TIER_ORDER[kv[1]["tier"]],
                                            kv[0]))
current_dim = None
for cid, meta in items:
    if meta["dimension"] != current_dim:
        current_dim = meta["dimension"]
        lines.append(f"  # --- {current_dim} ---")
    lines.append(f"  - id: {cid}")
    lines.append(f"    prompt_file: cases/code-gen/{cid}.txt")
    lines.append(f"    scoring: code-exec")
    lines.append(f"    tests_file: cases/code-gen/tests/{cid}.py")
    lines.append(f"    tier: {meta['tier']}")
    lines.append(f"    dimension: {meta['dimension']}")

lines += ["", "weights: { quality: 1.0 }", ""]

(REPO / "batteries" / "code-gen.yaml").write_text("\n".join(lines), encoding="utf-8")

tiers = Counter(m["tier"] for m in REG.values())
dims = Counter(m["dimension"] for m in REG.values())
total = len(REG)
print(f"{total} cases written to batteries/code-gen.yaml\n")
print("By tier:")
for t in ("T1", "T2", "T3", "T4"):
    n = tiers.get(t, 0)
    print(f"  {t}  {n:>3}  ({n / total:.0%})" if total else f"  {t}    0")
print("\nBy dimension:")
for d, n in sorted(dims.items()):
    print(f"  {d:<32} {n:>3}")
