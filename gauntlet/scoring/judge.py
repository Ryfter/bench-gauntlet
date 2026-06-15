"""LLM-judge scoring. The judge must be a non-reasoning strict-JSON model, and a
judge never grades its own model family (select_judge enforces this). A verdict
that cannot be parsed is recorded as unscored — never silently 0 (design G.5)."""
from __future__ import annotations

import json
import re

from gauntlet.client import OpenAIClient
from gauntlet.models import CaseResult
from gauntlet.scoring import _extract_json

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

_PASS_THRESHOLD = 0.5

JUDGE_PROMPT = (
    "You are a strict grader. Apply the rubric to the answer and respond with "
    'ONLY a JSON object: {{"score": <0..1 float>, "passed": <bool>}}.\n\n'
    "Rubric: {rubric}\n\nAnswer:\n{output}\n"
)


def parse_verdict(text: str) -> tuple[float, bool]:
    """Return (score in 0..1, passed). Raises ValueError if no usable verdict."""
    text = _THINK_RE.sub("", text).strip()
    try:
        data = _extract_json(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"unparseable judge verdict: {text!r}") from exc
    if not isinstance(data, dict) or "score" not in data:
        raise ValueError(f"verdict missing 'score': {data!r}")
    score = max(0.0, min(1.0, float(data["score"])))
    passed = bool(data["passed"]) if "passed" in data else score >= _PASS_THRESHOLD
    return score, passed


def select_judge(candidates: list[tuple[str, str]], target_family: str) -> str | None:
    """Pick the first (model_id, family) whose family differs from the model under
    test. Returns None if no different-family judge is available."""
    for model_id, family in candidates:
        if family != target_family:
            return model_id
    return None


def score_with_judge(client: OpenAIClient, judge_model: str, rubric: str,
                     output: str, case_id: str) -> CaseResult:
    prompt = JUDGE_PROMPT.format(rubric=rubric, output=output)
    reply = client.chat(model=judge_model, prompt=prompt, max_tokens=200)
    try:
        score, passed = parse_verdict(reply.text)
    except ValueError as exc:
        return CaseResult(case_id=case_id, method="judge", score=None, passed=False,
                          detail=f"unscored: {exc}")
    return CaseResult(case_id=case_id, method="judge", score=score, passed=passed,
                      detail=f"judge={judge_model}")
