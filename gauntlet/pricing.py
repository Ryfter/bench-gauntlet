"""Frontier pricing table for cost-equivalent calculations.

Local inference costs $0. The functions here compute what the same tokens
would have cost at a frontier API — letting the scorecard show how much
running locally saved vs. each frontier tier.

Prices are per-million tokens (input/output) as of mid-2026. Update the
table as prices change; nothing else needs to change.
"""
from __future__ import annotations

# All prices in USD per million tokens.
FRONTIER_PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-fable-5":    {"input_per_m": 10.00, "output_per_m": 50.00},
    "claude-opus-4-8":   {"input_per_m":  5.00, "output_per_m": 25.00},
    "claude-sonnet-4-6": {"input_per_m":  3.00, "output_per_m": 15.00},
    "claude-haiku-4-5":  {"input_per_m":  1.00, "output_per_m":  5.00},
    # OpenAI
    "gpt-5.5":           {"input_per_m":  5.00, "output_per_m": 30.00},
    "gpt-5.4":           {"input_per_m":  2.50, "output_per_m": 15.00},
    "gpt-5.4-mini":      {"input_per_m":  0.75, "output_per_m":  4.50},
    "gpt-5.4-nano":      {"input_per_m":  0.20, "output_per_m":  1.25},
    "gpt-5.3-codex":     {"input_per_m":  1.75, "output_per_m": 14.00},
}

# Human-readable display names for scorecard output.
FRONTIER_DISPLAY: dict[str, str] = {
    "claude-fable-5":    "Claude Fable 5",
    "claude-opus-4-8":   "Claude Opus 4.8",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-haiku-4-5":  "Claude Haiku 4.5",
    "gpt-5.5":           "GPT-5.5",
    "gpt-5.4":           "GPT-5.4",
    "gpt-5.4-mini":      "GPT-5.4 mini",
    "gpt-5.4-nano":      "GPT-5.4 nano",
    "gpt-5.3-codex":     "GPT-5.3 Codex",
}

# Default comparisons shown in every scorecard — user can override via --compare.
DEFAULT_COMPARE = ["claude-sonnet-4-6", "claude-haiku-4-5"]


def cost_usd(frontier: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Return the USD cost for this token usage at the given frontier tier, or None
    if the frontier ID is unknown."""
    p = FRONTIER_PRICING.get(frontier)
    if p is None:
        return None
    return (prompt_tokens / 1_000_000 * p["input_per_m"] +
            completion_tokens / 1_000_000 * p["output_per_m"])


def savings_summary(cells: list, compare: list[str] | None = None) -> str | None:
    """Return a Markdown cost-savings section for a list of Cells, or None if no
    token data is available. compare is a list of frontier IDs to show."""
    if compare is None:
        compare = DEFAULT_COMPARE

    total_prompt = sum(c.prompt_tokens or 0 for c in cells)
    total_completion = sum(c.completion_tokens or 0 for c in cells)
    if total_prompt == 0 and total_completion == 0:
        return None

    lines = [
        "",
        "## Cost savings (local inference vs frontier API)",
        "",
        f"- **Tokens used:** {total_prompt:,} prompt / {total_completion:,} completion"
        f" ({total_prompt + total_completion:,} total)",
        "",
        "| Frontier | Equivalent cost | You saved |",
        "|---|---|---|",
    ]
    for fid in compare:
        cost = cost_usd(fid, total_prompt, total_completion)
        if cost is None:
            continue
        name = FRONTIER_DISPLAY.get(fid, fid)
        lines.append(f"| {name} | ${cost:.4f} | ${cost:.4f} |")

    lines.append("")
    lines.append("_Local inference costs $0. \"You saved\" = what the API call would have cost._")
    return "\n".join(lines)
