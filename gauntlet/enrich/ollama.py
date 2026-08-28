from __future__ import annotations

from gauntlet.client import OpenAIClient
from gauntlet.enrich import ModelMeta


def parse_ollama(payload: dict) -> list[ModelMeta]:
    out: list[ModelMeta] = []
    for m in payload.get("models", []):
        details = m.get("details") or {}
        out.append(
            ModelMeta(
                id=m["name"],
                max_context=None,         # not exposed by /api/tags
                quant=details.get("quantization_level"),
                size_bytes=m.get("size"),
                params=details.get("parameter_size"),
                vision=None,
                tool_use=None,
                loaded=False,
            )
        )
    return out


def fetch(base_url: str, transport=None) -> list[ModelMeta]:
    client = OpenAIClient(base_url, timeout=10.0, transport=transport)
    try:
        return parse_ollama(client.get_json("/api/tags"))
    finally:
        client.close()
