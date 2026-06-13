from __future__ import annotations

import httpx

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


def fetch(base_url: str, transport: httpx.BaseTransport | None = None) -> list[ModelMeta]:
    url = base_url.rstrip("/") + "/api/v1/models"
    with httpx.Client(timeout=10.0, transport=transport) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return parse_lmstudio(resp.json())
