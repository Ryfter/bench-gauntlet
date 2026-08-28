from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from gauntlet import errors

Scoring = Literal["exact", "regex", "json-schema", "conventional-commit",
                  "compilable-code", "code-exec", "judge"]

# Difficulty ladder. The fleet is local models roughly 1B-30B: a battery where
# everything scores 1.0 is non-discriminative, but so is one where everything
# scores 0.0. Tiers spread scores across that range and leave headroom at T4 so
# the battery does not saturate as models improve.
#   T1 baseline sanity (most models pass; keeps the floor visible)
#   T2 moderate
#   T3 hard  <- does most of the discriminating
#   T4 stretch (most locals fail today; intentional headroom)
Tier = Literal["T1", "T2", "T3", "T4"]


class Case(BaseModel):
    id: str
    prompt_file: str | None = None
    scoring: Scoring
    tier: Tier = "T2"             # difficulty rung; scorecard reports per-tier
    dimension: str | None = None  # capability axis (see batteries/README.md)
    schema_file: str | None = None
    rubric: str | None = None
    expect: str | None = None     # exact scoring: the expected output
    pattern: str | None = None    # regex scoring: the pattern to find
    tests_file: str | None = None   # code-exec scoring: hidden asserts (see scoring/execute.py)
    timeout_s: float | None = None  # code-exec scoring: sandbox wall-clock timeout (default 5.0)
    commit_type: str | None = None
    required_terms: list[str] = Field(default_factory=list)
    require_breaking: bool = False


class Battery(BaseModel):
    capability: str
    context_floor: int = 0
    # Generation budget per case. Reasoning models spend thousands of tokens
    # thinking before their first line of answer, so a budget tuned for
    # short-answer batteries scores them at zero for running out of room
    # rather than for being unable to do the task. Set it per battery: the
    # answer to "classify this in one word" needs a fraction of what "write
    # this function" does.
    max_tokens: int = 512
    cases: list[Case] = Field(default_factory=list)
    weights: dict[str, float] = Field(default_factory=lambda: {"quality": 1.0})

    def applies_to(self, context: int) -> bool:
        return context >= self.context_floor


def load_battery(path: str | Path) -> Battery:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise errors.BadBattery(str(path), f"YAML parse error: {exc}") from exc
    try:
        return Battery.model_validate(data)
    except ValidationError as exc:
        raise errors.BadBattery(str(path), str(exc)) from exc


def load_batteries(directory: str | Path) -> list[Battery]:
    """Load every *.yaml in `directory`. Malformed files are named loudly on
    stderr and skipped; the rest load (design G.5)."""
    directory = Path(directory)
    out: list[Battery] = []
    for path in sorted(directory.glob("*.yaml")):
        try:
            out.append(load_battery(path))
        except errors.BadBattery as exc:
            print(f"WARNING: skipping {exc}", file=sys.stderr)
    return out
