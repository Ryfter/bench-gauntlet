from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class ModelMeta(BaseModel):
    id: str
    max_context: int | None = None
    quant: str | None = None
    size_bytes: int | None = None
    params: str | None = None
    vision: bool | None = None
    tool_use: bool | None = None
    loaded: bool = False


class Enricher(Protocol):
    """Adapters turn a server's native metadata endpoint into ModelMeta.
    Metadata-only — never loads a model, safe to call anytime."""

    def fetch(self, base_url: str) -> list[ModelMeta]: ...
