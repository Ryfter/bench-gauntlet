from __future__ import annotations

import httpx

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


def fetch(base_url: str, transport: httpx.BaseTransport | None = None) -> list[ModelMeta]:
    url = base_url.rstrip("/") + "/api/tags"
    with httpx.Client(timeout=10.0, transport=transport) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return parse_ollama(resp.json())
