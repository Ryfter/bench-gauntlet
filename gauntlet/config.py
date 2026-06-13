from __future__ import annotations

import fnmatch
from typing import Literal

from pydantic import BaseModel, Field


class Target(BaseModel):
    name: str
    base_url: str
    api: Literal["openai"] = "openai"
    enrich: str | None = None
    box: str | None = None


class Box(BaseModel):
    id: str
    hardware: str  # public label, e.g. "RTX 5090 desktop"
    vram_gb: float
    usage_class: Literal["tight", "broad"] = "broad"
    busy: bool = False


class ModelProfile(BaseModel):
    """A load profile: model @ context — the unit under test."""
    target: str
    id: str
    context: int


class GauntletConfig(BaseModel):
    targets: list[Target] = Field(default_factory=list)
    boxes: list[Box] = Field(default_factory=list)
    models: list[ModelProfile] = Field(default_factory=list)
    keep_list: list[str] = Field(default_factory=list)

    def target_by_name(self, name: str) -> Target | None:
        return next((t for t in self.targets if t.name == name), None)

    def box_by_id(self, box_id: str) -> Box | None:
        return next((b for b in self.boxes if b.id == box_id), None)

    def box_for_target(self, target_name: str) -> Box | None:
        target = self.target_by_name(target_name)
        if target is None or target.box is None:
            return None
        return self.box_by_id(target.box)

    def is_kept(self, model_id: str) -> bool:
        """True if a keep_list glob matches (case-insensitive)."""
        mid = model_id.lower()
        return any(fnmatch.fnmatch(mid, pat.lower()) for pat in self.keep_list)
