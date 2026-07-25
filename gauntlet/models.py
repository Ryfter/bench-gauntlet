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
    # Structured reason a case failed (code-exec only, for now). Aggregated per
    # cell so a scorecard says *why* a model missed, not just how often: a model
    # emitting no code at all has a different problem from one writing plausible
    # code with an off-by-one, and only the second is worth scaffolding
    # (selective-offload principle, D-2026-06-30c).
    failure_mode: str | None = None
    tier: str | None = None       # T1-T4 difficulty rung
    dimension: str | None = None  # capability axis (see batteries/README.md)


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
    # Difficulty profile: mean quality per tier (T1-T4). The shape says more
    # than the mean — clearing T1-T2 then collapsing at T3 is a different
    # proposition from scoring evenly across all four.
    quality_by_tier: dict[str, float] | None = None
    # Why cases failed, counted by structured failure mode. Distinguishes a
    # capability gap (no_code_emitted / syntax_error) from a defect in
    # otherwise-plausible code (wrong_answer) — only the latter is worth
    # scaffolding (D-2026-06-30c).
    failure_modes: dict[str, int] | None = None
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
