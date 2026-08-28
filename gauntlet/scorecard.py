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

# Endpoint forms that must never cross a public/reporting boundary.
_LEAK_RE = re.compile(
    r"\b\d{1,3}(?:\.\d{1,3}){3}\b|"
    r"[a-zA-Z][a-zA-Z0-9+.-]*://|"
    r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f]{0,4}(?![0-9A-Fa-f:])|"
    r"\b(?:[A-Za-z0-9-]+\.)*[A-Za-z0-9-]+:\d{2,5}\b"
)
_IDENTIFIER_FIELDS = frozenset({"id", "model", "judge", "box", "target"})
_BARE_HOST_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]*\Z")


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
        quality_by_tier=quality_by_tier(results),
        quality_by_dimension=quality_by_dimension(results),
        failure_modes=failure_mode_counts(results),
        integrity=integrity_counts(results),
    )


def integrity_counts(results: list[CaseResult]) -> dict[str, int] | None:
    """Count integrity violations by kind across a cell.

    `None` means clean. Anything else means the cell contains cases that were
    marked unscored because the candidate reached for the answers or the
    network — and that the surrounding numbers deserve scrutiny. Surfacing this
    is the difference between a scorecard that reports results and one that
    reports results it can vouch for.
    """
    counts: dict[str, int] = {}
    for r in results:
        for violation in r.integrity_violations or ():
            kind = violation.get("kind", "unknown")
            counts[kind] = counts.get(kind, 0) + 1
    return dict(sorted(counts.items())) or None


def quality_by_tier(results: list[CaseResult]) -> dict[str, float] | None:
    """Mean quality per difficulty tier.

    The *shape* of a tier profile carries more information than the mean: a
    model that clears T1-T2 and collapses at T3 is a different proposition from
    one scoring evenly across all four, and a single averaged number hides that
    completely. Unscored cases are excluded rather than counted as 0.
    """
    buckets: dict[str, list[float]] = {}
    for r in results:
        if r.tier and r.score is not None:
            buckets.setdefault(r.tier, []).append(r.score)
    if not buckets:
        return None
    return {tier: sum(v) / len(v) for tier, v in sorted(buckets.items())}


def quality_by_dimension(results: list[CaseResult]) -> dict[str, float] | None:
    """Mean quality per capability axis (bug-fix, multi-function, …).

    Where the tier profile says how hard a model can go, this says what it is
    good *at* — and that is the axis Baton actually routes on. A single
    code-gen number cannot distinguish a model that fixes bugs well but cannot
    hold a multi-file refactor from its exact opposite. Unscored cases are
    excluded rather than counted as 0.
    """
    buckets: dict[str, list[float]] = {}
    for r in results:
        if r.dimension and r.score is not None:
            buckets.setdefault(r.dimension, []).append(r.score)
    if not buckets:
        return None
    return {dim: sum(v) / len(v) for dim, v in sorted(buckets.items())}


def failure_mode_counts(results: list[CaseResult]) -> dict[str, int] | None:
    """How many cases failed each way (`none` — i.e. clean passes — excluded).

    This is what lets Baton distinguish a capability gap from a working-memory
    problem: `no_code_emitted` and `syntax_error` say the model cannot engage
    with the task at all, while `wrong_answer` says it produced plausible code
    with a defect. Only the latter is a candidate for scaffolding
    (selective-offload principle, D-2026-06-30c).
    """
    counts: dict[str, int] = {}
    for r in results:
        mode = r.failure_mode
        if mode and mode != "none":
            counts[mode] = counts.get(mode, 0) + 1
    return dict(sorted(counts.items())) or None


def to_dict(scorecard: Scorecard, share: bool = False) -> dict:
    data = scorecard.model_dump()
    if share:
        for cell in data["cells"]:
            cell.pop("target", None)
        data = _sanitize_shared(data)
    return data


def _sanitize_shared(value, *, key: str | None = None):
    if isinstance(value, dict):
        return {k: _sanitize_shared(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_shared(v, key=key) for v in value]
    if isinstance(value, str):
        identifier = key in _IDENTIFIER_FIELDS or (key or "").endswith("_model")
        if _LEAK_RE.search(value) or (identifier and _BARE_HOST_RE.fullmatch(value)):
            return "<redacted>"
    return value


def assert_no_leak(text: str) -> None:
    """Refuse to emit a scorecard that contains an IP address or URL."""
    match = _LEAK_RE.search(text)
    if match:
        raise errors.GauntletError(
            "refusing to write scorecard: a private endpoint pattern was detected"
        )


def write_json(scorecard: Scorecard, path: str | Path, share: bool = False) -> None:
    payload = json.dumps(to_dict(scorecard, share=share), indent=2)
    assert_no_leak(payload)
    Path(path).write_text(payload, encoding="utf-8")


def _fmt(value: float | None, places: int = 2) -> str:
    return "—" if value is None else f"{value:.{places}f}"


def render_markdown(scorecard: Scorecard, share: bool = False,
                    compare: list[str] | None = None) -> str:
    safe = to_dict(scorecard, share=share) if share else scorecard.model_dump()
    run = safe["run"]
    lines = [
        "# Gauntlet scorecard",
        "",
        f"- **run:** {run['id']}  **date:** {run['date']}  **gauntlet:** {run['gauntlet_version']}",
        "",
    ]
    header = ["model", "box", "ctx", "capability", "quality", "pass", "tok/s", "ttft", "cases", "err"]
    if not share:
        header.insert(2, "target")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    for c in safe["cells"]:
        row = [c["model"], c["box"]]
        if not share:
            row.append(c.get("target") or "—")
        row += [
            str(c["context"]), c["capability"], _fmt(c["quality"]), _fmt(c["pass_rate"]),
            _fmt(c["tokens_per_s"], 0), _fmt(c["ttft_p50_s"], 2), str(c["cases"]), str(c["errors"]),
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
