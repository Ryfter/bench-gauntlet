from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, ValidationError

from gauntlet import errors

Scoring = Literal["exact", "regex", "json-schema", "conventional-commit",
                  "compilable-code", "judge"]


class Case(BaseModel):
    id: str
    prompt_file: str | None = None
    scoring: Scoring
    schema_file: str | None = None
    rubric: str | None = None


class Battery(BaseModel):
    capability: str
    context_floor: int = 0
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
