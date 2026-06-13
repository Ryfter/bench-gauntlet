"""Aggregate CaseResults into a Cell, assemble a Scorecard, and emit it as
canonical JSON + a Markdown report. Private vs shared (`--share`) differ only in
whether the hostname label is dropped; neither mode ever carries a base_url/IP
(the Cell has no such field), and `assert_no_leak` is a belt-and-braces guard."""
from __future__ import annotations

from gauntlet.models import CaseResult, Cell


def aggregate_cell(
    model: str,
    target: str | None,
    box: str,
    context: int,
    capability: str,
    results: list[CaseResult],
    latency_p50_s: float | None = None,
    tokens_per_s: float | None = None,
    errors: int = 0,
) -> Cell:
    scored = [r.score for r in results if r.score is not None]
    quality = sum(scored) / len(scored) if scored else None
    pass_rate = (sum(1 for r in results if r.passed) / len(results)) if results else None
    return Cell(
        model=model, target=target, box=box, context=context, capability=capability,
        quality=quality, pass_rate=pass_rate, latency_p50_s=latency_p50_s,
        tokens_per_s=tokens_per_s, cases=len(results), errors=errors,
    )
