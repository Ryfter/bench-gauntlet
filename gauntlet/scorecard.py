"""Aggregate CaseResults into a Cell, assemble a Scorecard, and emit it as
canonical JSON + a Markdown report. Private vs shared (`--share`) differ only in
whether the hostname label is dropped; neither mode ever carries a base_url/IP
(the Cell has no such field), and `assert_no_leak` is a belt-and-braces guard."""
from __future__ import annotations

import json
import re
from pathlib import Path

from gauntlet import errors
from gauntlet.models import BaselineGap, CaseResult, Cell, ContextDepth, Scorecard
from gauntlet.pricing import DEFAULT_COMPARE, savings_summary

# IPv4 (with optional :port) or any URL scheme — a scorecard must contain neither.
_LEAK_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b|[a-zA-Z][a-zA-Z0-9+.-]*://")


def aggregate_cell(
    model: str,
    target: str | None,
    box: str,
    context: int,
    capability: str,
    results: list[CaseResult],
    latency_p50_s: float | None = None,
    tokens_per_s: float | None = None,
    ttft_p50_s: float | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    errors: int = 0,
) -> Cell:
    scored = [r.score for r in results if r.score is not None]
    quality = sum(scored) / len(scored) if scored else None
    pass_rate = (sum(1 for r in results if r.passed) / len(results)) if results else None
    return Cell(
        model=model, target=target, box=box, context=context, capability=capability,
        quality=quality, pass_rate=pass_rate, latency_p50_s=latency_p50_s,
        tokens_per_s=tokens_per_s, ttft_p50_s=ttft_p50_s,
        prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
        cases=len(results), errors=errors,
    )


def to_dict(scorecard: Scorecard, share: bool = False) -> dict:
    data = scorecard.model_dump()
    if share:
        for cell in data["cells"]:
            cell.pop("target", None)
    return data


def assert_no_leak(text: str) -> None:
    """Refuse to emit a scorecard that contains an IP address or URL."""
    match = _LEAK_RE.search(text)
    if match:
        raise errors.GauntletError(
            f"refusing to write scorecard: looks like a leaked endpoint ({match.group()!r})"
        )


def write_json(scorecard: Scorecard, path: str | Path, share: bool = False) -> None:
    payload = json.dumps(to_dict(scorecard, share=share), indent=2)
    assert_no_leak(payload)
    Path(path).write_text(payload, encoding="utf-8")


def _fmt(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def render_markdown(scorecard: Scorecard, share: bool = False,
                    compare: list[str] | None = None) -> str:
    run = scorecard.run
    lines = [
        "# Gauntlet scorecard",
        "",
        f"- **run:** {run.id}  **date:** {run.date}  **gauntlet:** {run.gauntlet_version}",
        "",
    ]
    header = ["model", "box", "ctx", "capability", "quality", "pass", "tok/s", "ttft", "cases", "err"]
    if not share:
        header.insert(2, "target")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for c in scorecard.cells:
        row = [c.model, c.box]
        if not share:
            row.append(c.target or "—")
        row += [
            str(c.context), c.capability, _fmt(c.quality), _fmt(c.pass_rate),
            _fmt(c.tokens_per_s, 0), _fmt(c.ttft_p50_s, 2), str(c.cases), str(c.errors),
        ]
        lines.append("| " + " | ".join(row) + " |")

    savings = savings_summary(scorecard.cells, compare=compare or DEFAULT_COMPARE)
    if savings:
        lines.append(savings)

    return "\n".join(lines) + "\n"


def write_markdown(scorecard: Scorecard, path: str | Path, share: bool = False) -> None:
    text = render_markdown(scorecard, share=share)
    assert_no_leak(text)
    Path(path).write_text(text, encoding="utf-8")


def merge_into_scorecard(
    path: str | Path,
    *,
    cells: list[Cell] | None = None,
    context_depth: list[ContextDepth] | None = None,
    baseline_gaps: list[BaselineGap] | None = None,
    share: bool = False,
) -> None:
    """Load an existing scorecard JSON, append the given sections, and rewrite it
    (through the same leak guard). Lets `depth`/`embed`/`baseline` enrich a prior run."""
    sc = Scorecard.model_validate_json(Path(path).read_text(encoding="utf-8"))
    if cells:
        sc.cells.extend(cells)
    if context_depth:
        sc.context_depth.extend(context_depth)
    if baseline_gaps:
        sc.baseline_gaps.extend(baseline_gaps)
    write_json(sc, path, share=share)
