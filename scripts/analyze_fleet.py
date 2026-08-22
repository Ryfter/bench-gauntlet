#!/usr/bin/env python3
"""Analyze a Gauntlet fleet run into a model-routing report.

Answers: which local model is best at which job, at what cost?

Gauntlet scorecards deliberately distinguish *null* from *zero*. A score of
0.0 is a claim that the model failed the case. A null (or missing) score is an
admission that we do not know — judge unavailable, integrity block, run error,
etc. Treating null as 0.0 would invent failures and corrupt means used for
routing. This script therefore:

  * never coerces null/missing scores to 0.0
  * excludes nulls from means and reports how many were excluded
  * renders missing display values as an em dash (—), never bare None

Reads an append-only run directory (cells.jsonl + optional cases.jsonl) and
emits Markdown suitable for deciding local-model routing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


EM_DASH = "—"
TIERS = ("T1", "T2", "T3", "T4")


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError as exc:
                die(f"{path}: line {lineno}: invalid JSON: {exc}")
            if not isinstance(obj, dict):
                die(f"{path}: line {lineno}: expected a JSON object, got {type(obj).__name__}")
            rows.append(obj)
    return rows


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def esc_cell(value: Any) -> str:
    """Render a table cell; never bare None; escape pipe for Markdown tables."""
    if value is None:
        return EM_DASH
    text = str(value)
    return text.replace("|", "\\|")


def fmt_quality(value: Any) -> str:
    if value is None:
        return EM_DASH
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return EM_DASH


def fmt_toks(value: Any) -> str:
    if value is None:
        return EM_DASH
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return EM_DASH


def fmt_ttft(value: Any) -> str:
    if value is None:
        return EM_DASH
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return EM_DASH


def fmt_product(value: float) -> str:
    return f"{value:.2f}"


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    header_line = "| " + " | ".join(esc_cell(h) for h in headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    body = [
        "| " + " | ".join(esc_cell(c) for c in row) + " |"
        for row in rows
    ]
    return "\n".join([header_line, sep_line, *body])


def as_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def quality_sort_key(cell: Mapping[str, Any]) -> tuple:
    """Sort by quality descending; null quality sorts last."""
    q = as_float_or_none(cell.get("quality"))
    if q is None:
        return (1, 0.0, cell.get("model") or "")
    return (0, -q, cell.get("model") or "")


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def mean_excluding_nulls(values: Iterable[Any]) -> tuple[float | None, int, int]:
    """Return (mean, n_used, n_excluded). Null/missing never become 0.0."""
    used: list[float] = []
    excluded = 0
    for v in values:
        f = as_float_or_none(v)
        if f is None:
            excluded += 1
        else:
            used.append(f)
    if not used:
        return None, 0, excluded
    return sum(used) / len(used), len(used), excluded


def tier_shape(tier_map: Mapping[str, Any] | None) -> str:
    """Classify difficulty curve from present tier scores only."""
    if not tier_map:
        return EM_DASH
    present: list[tuple[str, float]] = []
    for t in TIERS:
        if t not in tier_map:
            continue
        f = as_float_or_none(tier_map.get(t))
        if f is None:
            continue
        present.append((t, f))
    if len(present) < 2:
        return EM_DASH

    scores = [s for _, s in present]
    spread = max(scores) - min(scores)
    if spread <= 0.15:
        return "flat"

    # Adjacent in the ordered present sequence (missing tiers skipped).
    deltas = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
    non_increasing = all(d <= 1e-12 for d in deltas)
    big_drops = sum(1 for d in deltas if -d > 0.4)

    # A cliff is "holds up, then falls off and stays down" -- one big step in an
    # otherwise non-increasing curve. A profile that drops hard and climbs back
    # (0.2 / 0.9 / 0.3 / 0.85) is a sawtooth, not a cliff, and calling it one
    # would tell Baton the model is reliable up to some tier when its scores are
    # really just noise. Both conditions must hold.
    if non_increasing:
        return "cliff" if big_drops == 1 else "graceful"
    return "erratic"


def failure_mode_read(modes: Mapping[str, Any] | None) -> str:
    if not modes:
        return EM_DASH
    counts: dict[str, int] = {}
    total = 0
    for k, v in modes.items():
        n = as_int(v, 0)
        if n < 0:
            n = 0
        counts[str(k)] = n
        total += n
    if total <= 0:
        return EM_DASH

    no_engage = counts.get("no_code_emitted", 0) + counts.get("syntax_error", 0)
    wrong = counts.get("wrong_answer", 0)
    timeout = counts.get("timeout", 0)

    if no_engage > total / 2:
        return "capability gap"
    if wrong > total / 2:
        return "scaffolding candidate"
    if timeout > total / 2:
        return "too slow"
    return "mixed"


def collect_dimension_scores(
    cells: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
    capability: str | None,
) -> dict[str, dict[str, list[float | None]]]:
    """dimension -> model -> list of scores (including None for unscored).

    Prefer per-case scores when cases.jsonl is present (allows exclusion counts).
    Fall back to cell-level quality_by_dimension means when cases are absent.
    """
    # dim -> model -> scores
    out: dict[str, dict[str, list[float | None]]] = defaultdict(lambda: defaultdict(list))

    filtered_cases = [
        c for c in cases
        if capability is None or c.get("capability") == capability
    ]
    if filtered_cases:
        for c in filtered_cases:
            dim = c.get("dimension")
            model = c.get("model")
            if not dim or not model:
                continue
            # Preserve null scores explicitly so means can exclude them.
            # Missing key and JSON null both become None — never 0.0.
            score = c.get("score", None)
            out[str(dim)][str(model)].append(as_float_or_none(score))
        return out

    # Fallback: quality_by_dimension on cells (already a mean; one value per cell)
    for cell in cells:
        if capability is not None and cell.get("capability") != capability:
            continue
        model = cell.get("model")
        qbd = cell.get("quality_by_dimension")
        if not model or not isinstance(qbd, dict):
            continue
        for dim, q in qbd.items():
            out[str(dim)][str(model)].append(as_float_or_none(q))
    return out


def merge_failure_modes(
    cells: Sequence[Mapping[str, Any]],
    capability: str | None,
) -> dict[str, dict[str, int]]:
    """model -> mode -> count, summed across cells (optionally one capability)."""
    merged: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for cell in cells:
        if capability is not None and cell.get("capability") != capability:
            continue
        model = cell.get("model")
        modes = cell.get("failure_modes")
        if not model or not isinstance(modes, dict):
            continue
        for mode, count in modes.items():
            merged[str(model)][str(mode)] += as_int(count, 0)
    return merged


def pick_tier_map(
    cells: Sequence[Mapping[str, Any]],
    capability: str | None,
) -> dict[str, dict[str, float | None]]:
    """model -> tier -> quality.

    When a model has multiple cells (e.g. several capabilities without
    --capability), mean the non-null values per tier. Nulls are never
    treated as 0.0.
    """
    # model -> tier -> list of non-null scores
    acc: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for cell in cells:
        model = cell.get("model")
        if not model:
            continue
        if capability is not None and cell.get("capability") != capability:
            continue
        qbt = cell.get("quality_by_tier")
        if not isinstance(qbt, dict):
            continue
        for k, v in qbt.items():
            f = as_float_or_none(v)
            if f is None:
                continue
            acc[str(model)][str(k)].append(f)

    by_model: dict[str, dict[str, float | None]] = {}
    for model, tiers in acc.items():
        by_model[model] = {
            t: (sum(vals) / len(vals) if vals else None)
            for t, vals in tiers.items()
        }
    return by_model


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def section_run_summary(
    cells: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
    has_cases_file: bool,
) -> str:
    models = sorted({str(c["model"]) for c in cells if c.get("model")})
    capabilities = sorted({str(c["capability"]) for c in cells if c.get("capability")})
    total_cells = len(cells)
    total_cases = len(cases) if has_cases_file else sum(as_int(c.get("cases"), 0) for c in cells)

    lines = [
        "## Run summary",
        "",
        f"- **Models** ({len(models)}): {', '.join(models) if models else EM_DASH}",
        f"- **Capabilities** ({len(capabilities)}): {', '.join(capabilities) if capabilities else EM_DASH}",
        f"- **Total cells**: {total_cells}",
        f"- **Total cases**: {total_cases}"
        + ("" if has_cases_file else " (sum of cell `cases` fields; no `cases.jsonl`)"),
    ]

    error_cells = [
        c for c in cells
        if as_int(c.get("errors"), 0) > 0
    ]
    integrity_cells = [
        c for c in cells
        if c.get("integrity") is not None
    ]

    if error_cells:
        lines.append("")
        lines.append(f"**Cells with errors > 0** ({len(error_cells)}):")
        for c in error_cells:
            lines.append(
                f"- `{c.get('model', EM_DASH)}` / `{c.get('capability', EM_DASH)}`: "
                f"errors={as_int(c.get('errors'), 0)}"
            )
    else:
        lines.append("")
        lines.append("**Cells with errors > 0**: none")

    if integrity_cells:
        lines.append("")
        lines.append(f"**Cells with non-null integrity** ({len(integrity_cells)}):")
        for c in integrity_cells:
            lines.append(
                f"- `{c.get('model', EM_DASH)}` / `{c.get('capability', EM_DASH)}`: "
                f"`{json.dumps(c.get('integrity'), ensure_ascii=False)}`"
            )
    else:
        lines.append("")
        lines.append("**Cells with non-null integrity**: none")

    return "\n".join(lines)


def coverage(cell: Mapping[str, Any]) -> float | None:
    """Fraction of a cell's cases that actually produced a score.

    The number that decides whether a quality figure is comparable at all. A
    mean over 62% of the battery and a mean over 100% of it are different
    quantities, and nothing else in the row reveals which one you are reading.
    """
    total = as_float_or_none(cell.get("cases"))
    if not total:
        return None
    unscored = 0.0
    for mode, count in (cell.get("failure_modes") or {}).items():
        if mode in ("truncated", "integrity_violation", "harness_error"):
            unscored += as_float_or_none(count) or 0
    return max(0.0, (total - unscored) / total)


def format_coverage(cell: Mapping[str, Any]) -> str:
    cov = coverage(cell)
    if cov is None:
        return EM_DASH
    flag = " ⚠" if cov < 0.9 else ""
    return f"{cov * 100:.0f}%{flag}"


def section_leaderboard(
    cells: Sequence[Mapping[str, Any]],
    capability_filter: str | None,
) -> str:
    lines = ["## Leaderboard per capability", ""]

    caps: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for c in cells:
        cap = c.get("capability")
        if not cap:
            continue
        if capability_filter is not None and cap != capability_filter:
            continue
        caps[str(cap)].append(c)

    if not caps:
        lines.append("_No cells to rank._")
        return "\n".join(lines)

    for cap in sorted(caps):
        ranked = sorted(caps[cap], key=quality_sort_key)
        rows = []
        low_coverage = False
        for c in ranked:
            cov = coverage(c)
            if cov is not None and cov < 0.9:
                low_coverage = True
            rows.append([
                c.get("model") or EM_DASH,
                fmt_quality(c.get("quality")),
                format_coverage(c),
                fmt_quality(c.get("pass_rate")),
                fmt_toks(c.get("tokens_per_s")),
                fmt_ttft(c.get("ttft_p50_s")),
            ])
        lines.append(f"### `{cap}`")
        lines.append("")
        lines.append(md_table(
            ["model", "quality", "scored", "pass_rate", "tok/s", "ttft"],
            rows,
        ))
        lines.append("")
        if low_coverage:
            lines.append(
                "**Coverage warning.** A quality figure is a mean over the cases "
                "that produced a score; unscored cases are excluded, never counted "
                "as 0. Where `scored` is well under 100% the comparison is not "
                "like-for-like — and because truncation rises with difficulty, "
                "the excluded cases are disproportionately the hard ones, so a "
                "low-coverage score is biased *upward*. Read those rows as a "
                "ceiling, not a measurement."
            )
            lines.append("")

    return "\n".join(lines).rstrip()


def section_best_per_dimension(
    cells: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
    capability: str | None,
    top_n: int,
) -> str:
    lines = ["## Best model per dimension", ""]

    dim_scores = collect_dimension_scores(cells, cases, capability)
    if not dim_scores:
        lines.append(
            "_Skipped: no `quality_by_dimension` on cells and no usable "
            "`cases.jsonl` dimension scores._"
        )
        return "\n".join(lines)

    # Headers: dimension | 1st (score) | 2nd (score) | 3rd (score) | ...
    place_headers: list[str] = []
    for i in range(1, top_n + 1):
        if i == 1:
            place_headers.append("1st (score)")
        elif i == 2:
            place_headers.append("2nd (score)")
        elif i == 3:
            place_headers.append("3rd (score)")
        else:
            place_headers.append(f"{i}th (score)")

    headers = ["dimension", *place_headers]
    table_rows: list[list[str]] = []
    exclusion_notes: list[str] = []

    for dim in sorted(dim_scores):
        ranked: list[tuple[str, float, int, int]] = []  # model, mean, used, excluded
        for model, scores in dim_scores[dim].items():
            mean, n_used, n_excl = mean_excluding_nulls(scores)
            if mean is None:
                if n_excl:
                    exclusion_notes.append(
                        f"`{dim}` / `{model}`: all {n_excl} score(s) null/missing — excluded from ranking"
                    )
                continue
            ranked.append((model, mean, n_used, n_excl))
            if n_excl:
                exclusion_notes.append(
                    f"`{dim}` / `{model}`: mean over {n_used} scored case(s); "
                    f"{n_excl} null/missing excluded"
                )
        ranked.sort(key=lambda t: (-t[1], t[0]))

        row: list[str] = [dim]
        for i in range(top_n):
            if i < len(ranked):
                model, mean, _, _ = ranked[i]
                row.append(f"{model} ({fmt_quality(mean)})")
            else:
                row.append(EM_DASH)
        table_rows.append(row)

    lines.append(md_table(headers, table_rows))
    if exclusion_notes:
        lines.append("")
        lines.append("Null/missing scores excluded from means (not treated as 0.0):")
        for note in exclusion_notes:
            lines.append(f"- {note}")
    return "\n".join(lines)


def section_difficulty_profile(
    cells: Sequence[Mapping[str, Any]],
    capability: str | None,
) -> str:
    lines = ["## Difficulty profile", ""]
    by_model = pick_tier_map(cells, capability)
    if not by_model:
        lines.append("_No `quality_by_tier` data on cells._")
        return "\n".join(lines)

    rows = []
    for model in sorted(by_model):
        tm = by_model[model]
        row = [model]
        for t in TIERS:
            if t in tm:
                row.append(fmt_quality(tm[t]))
            else:
                row.append(EM_DASH)
        row.append(tier_shape(tm))
        rows.append(row)

    lines.append(md_table(
        ["model", "T1", "T2", "T3", "T4", "shape"],
        rows,
    ))
    lines.append("")
    lines.append(
        "Shape key: `flat` (max−min ≤ 0.15), `graceful` (monotonically non-increasing "
        "T1→T4 among present tiers), `cliff` (single adjacent drop > 0.4), else "
        "`erratic`. Missing tiers are skipped, not treated as 0."
    )
    return "\n".join(lines)


def section_failure_modes(
    cells: Sequence[Mapping[str, Any]],
    capability: str | None,
) -> str:
    lines = ["## Failure-mode profile", ""]
    merged = merge_failure_modes(cells, capability)
    if not merged:
        lines.append("_No `failure_modes` data on cells._")
        return "\n".join(lines)

    # Union of mode keys, stable order: known modes first, then alpha.
    preferred = [
        "no_code_emitted",
        "syntax_error",
        "wrong_answer",
        "timeout",
        "runtime_error",
        "assert_fail",
    ]
    all_modes: set[str] = set()
    for modes in merged.values():
        all_modes.update(modes.keys())
    mode_cols = [m for m in preferred if m in all_modes]
    mode_cols.extend(sorted(all_modes - set(mode_cols)))

    headers = ["model", *mode_cols, "read"]
    rows = []
    for model in sorted(merged):
        modes = merged[model]
        row: list[Any] = [model]
        for m in mode_cols:
            row.append(modes.get(m, 0))
        row.append(failure_mode_read(modes))
        rows.append(row)

    lines.append(md_table(headers, rows))
    lines.append("")
    lines.append(
        "Only **wrong_answer**-dominant models (`scaffolding candidate`) are worth "
        "scaffolding: they can engage the task but need structure. Models read as "
        "`capability gap` (no code / syntax) or `too slow` cannot usefully engage "
        "the task as-is; scaffolding will not fix a missing skill or a speed wall."
    )
    return "\n".join(lines)


def section_quality_per_unit_time(
    cells: Sequence[Mapping[str, Any]],
    capability: str | None,
) -> str:
    lines = ["## Quality per unit time", ""]

    candidates: list[tuple[str, float, float, float, float]] = []
    for c in cells:
        if capability is not None and c.get("capability") != capability:
            continue
        model = c.get("model")
        q = as_float_or_none(c.get("quality"))
        tps = as_float_or_none(c.get("tokens_per_s"))
        if model is None or q is None or tps is None:
            continue
        weight = as_float_or_none(c.get("cases")) or 1.0
        candidates.append((str(model), q, tps, q * tps, weight))

    if not candidates:
        lines.append(
            "_No rows with both non-null `quality` and `tokens_per_s`._"
        )
        return "\n".join(lines)

    # A model usually has one cell per capability. Collapsing those by keeping
    # the best one would report every model at its strongest job and call it
    # the model's number -- a cherry-pick dressed as a ranking. Take the mean
    # across capabilities instead, weighted by how many cases each contributed,
    # so a 108-case battery outweighs an 8-case one.
    sums: dict[str, list[float]] = {}
    for model, q, tps, _prod, weight in candidates:
        acc = sums.setdefault(model, [0.0, 0.0, 0.0])
        acc[0] += q * weight
        acc[1] += tps * weight
        acc[2] += weight

    best: dict[str, tuple[float, float, float]] = {}
    for model, (q_sum, tps_sum, weight) in sums.items():
        if weight <= 0:
            continue
        q_mean = q_sum / weight
        tps_mean = tps_sum / weight
        best[model] = (q_mean, tps_mean, q_mean * tps_mean)

    ranked = sorted(best.items(), key=lambda kv: (-kv[1][2], kv[0]))
    rows = [
        [model, fmt_quality(q), fmt_toks(tps), fmt_product(prod)]
        for model, (q, tps, prod) in ranked
    ]
    lines.append(md_table(
        ["model", "quality", "tok/s", "quality × tok/s"],
        rows,
    ))
    lines.append("")
    lines.append(
        "Rough throughput-adjusted ranking: higher means better quality delivered "
        "per unit of generation speed. Where a model has cells for several "
        "capabilities, quality and tok/s are case-weighted means across all of "
        "them, not its best one. Rows missing either input are omitted "
        "(null is not treated as zero)."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_report(
    cells: Sequence[Mapping[str, Any]],
    cases: Sequence[Mapping[str, Any]],
    has_cases_file: bool,
    capability: str | None,
    top_n: int,
    run_dir: Path,
) -> str:
    title = f"# Fleet routing report — `{run_dir.name}`"
    if capability:
        title += f" (capability: `{capability}`)"

    parts = [
        title,
        "",
        "Routing view over a Gauntlet run: which local model is best at which job, "
        "at what cost. Null scores are never treated as 0.0.",
        "",
        section_run_summary(cells, cases, has_cases_file),
        "",
        section_leaderboard(cells, capability),
        "",
        section_best_per_dimension(cells, cases, capability, top_n),
        "",
        section_difficulty_profile(cells, capability),
        "",
        section_failure_modes(cells, capability),
        "",
        section_quality_per_unit_time(cells, capability),
        "",
    ]
    return "\n".join(parts)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Turn a Gauntlet run directory into a model-routing Markdown report "
            "(which local model is best at which job, at what cost)."
        )
    )
    p.add_argument(
        "run_dir",
        type=Path,
        help="Path to a Gauntlet run directory containing cells.jsonl",
    )
    p.add_argument(
        "--capability",
        default=None,
        help="Restrict analysis to a single capability (e.g. code-gen)",
    )
    p.add_argument(
        "--markdown",
        metavar="OUT.md",
        default=None,
        type=Path,
        help="Also write the Markdown report to this file (UTF-8)",
    )
    p.add_argument(
        "--top",
        type=int,
        default=3,
        metavar="N",
        help="Top-N models per dimension (default: 3)",
    )
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir: Path = args.run_dir

    if not run_dir.exists():
        die(f"run directory not found: {run_dir}")
    if not run_dir.is_dir():
        die(f"run path is not a directory: {run_dir}")

    cells_path = run_dir / "cells.jsonl"
    if not cells_path.is_file():
        die(f"cells.jsonl not found in run directory: {cells_path}")

    if args.top < 1:
        die(f"--top must be >= 1, got {args.top}")

    cells = load_jsonl(cells_path)
    cases_path = run_dir / "cases.jsonl"
    has_cases_file = cases_path.is_file()
    cases = load_jsonl(cases_path) if has_cases_file else []

    if args.capability is not None:
        cells = [c for c in cells if c.get("capability") == args.capability]
        cases = [c for c in cases if c.get("capability") == args.capability]

    report = build_report(
        cells=cells,
        cases=cases,
        has_cases_file=has_cases_file,
        capability=args.capability,
        top_n=args.top,
        run_dir=run_dir,
    )

    # Default: print Markdown to stdout. Force UTF-8 first -- the report uses
    # em dashes for missing values, and a Windows console defaults to cp1252,
    # which cannot encode them and would crash the whole run at the last step.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):  # pragma: no cover - non-reconfigurable stream
        pass
    sys.stdout.write(report)
    if not report.endswith("\n"):
        sys.stdout.write("\n")

    if args.markdown is not None:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(report if report.endswith("\n") else report + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
