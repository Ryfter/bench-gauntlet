from __future__ import annotations

from gauntlet.client import OpenAIClient
from gauntlet.enrich import ModelMeta


def parse_lmstudio(payload: dict) -> list[ModelMeta]:
    out: list[ModelMeta] = []
    for m in payload.get("models", []):
        quant = (m.get("quantization") or {}).get("name")
        caps = m.get("capabilities") or {}
        out.append(
            ModelMeta(
                id=m["key"],
                max_context=m.get("max_context_length"),
                quant=quant,
                size_bytes=m.get("size_bytes"),
                params=m.get("params_string"),
                vision=caps.get("vision"),
                tool_use=caps.get("trained_for_tool_use"),
                loaded=bool(m.get("loaded_instances")),
            )
        )
    return out


def fetch(base_url: str, transport=None) -> list[ModelMeta]:
    client = OpenAIClient(base_url, timeout=10.0, transport=transport)
    try:
        return parse_lmstudio(client.get_json("/api/v1/models"))
    finally:
        client.close()
