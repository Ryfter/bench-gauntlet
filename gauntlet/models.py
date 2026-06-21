from __future__ import annotations

from pydantic import BaseModel, Field


class RunMeta(BaseModel):
    id: str
    date: str
    gauntlet_version: str


class CaseResult(BaseModel):
    case_id: str
    method: str          # exact | regex | json-schema | conventional-commit | compilable-code | judge
    score: float | None  # None == unscored (e.g. judge unavailable) — never silently 0
    passed: bool
    detail: str = ""


class Cell(BaseModel):
    model: str
    target: str | None   # hostname label; dropped in --share mode (Plan 2)
    box: str             # hardware label, e.g. "RTX 2070 Super laptop"
    context: int
    capability: str
    quality: float | None
    pass_rate: float | None
    latency_p50_s: float | None = None
    tokens_per_s: float | None = None
    ttft_p50_s: float | None = None        # median time-to-first-token (streaming)
    prompt_tokens: int | None = None       # total prompt tokens across all cases
    completion_tokens: int | None = None   # total completion tokens across all cases
    judge: str | None = None
    cases: int = 0
    errors: int = 0
    # NOTE: deliberately no base_url / IP field — privacy invariant.


class ContextDepth(BaseModel):
    model: str
    advertised: int
    effective_90pct: int


class BaselineGap(BaseModel):
    capability: str
    local_champion: str
    frontier: str
    gap: float


class Scorecard(BaseModel):
    run: RunMeta
    cells: list[Cell] = Field(default_factory=list)
    context_depth: list[ContextDepth] = Field(default_factory=list)
    baseline_gaps: list[BaselineGap] = Field(default_factory=list)
