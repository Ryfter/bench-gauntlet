"""Shared test utilities — not a test file."""
from __future__ import annotations

import json


def sse(*chunks: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> str:
    """Build a minimal OpenAI-compatible SSE response body for use in MockTransport handlers."""
    lines = []
    for chunk in chunks:
        lines.append("data: " + json.dumps({
            "choices": [{"delta": {"content": chunk}, "finish_reason": None}],
        }))
    lines.append("data: " + json.dumps({
        "choices": [{"delta": {}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }))
    lines.append("data: [DONE]")
    return "\n".join(lines) + "\n"
