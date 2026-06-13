"""Typed outcomes. Startup/config errors raise; per-cell runtime errors
(Unreachable, OOM, JudgeUnavailable, BoxBusy) are recorded, not raised —
they live here as marker classes the runner (Plan 3) converts to cell states."""
from __future__ import annotations


class GauntletError(Exception):
    """Base for all Gauntlet errors."""


class ConfigNotFound(GauntletError):
    def __init__(self, path: str) -> None:
        super().__init__(f"No Gauntlet config found at: {path}")
        self.path = str(path)


class ConfigInvalid(GauntletError):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Invalid config {path}: {detail}")
        self.path = str(path)
        self.detail = detail


class BadBattery(GauntletError):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(f"Malformed battery {path}: {detail}")
        self.path = str(path)
        self.detail = detail


# Runtime cell-outcome markers (recorded by the runner, never abort a run).
class Unreachable(GauntletError):
    """Target endpoint could not be reached."""


class ModelLoadFailed(GauntletError):
    """Model failed to load / OOM."""


class JudgeUnavailable(GauntletError):
    """No eligible judge model available to score a case."""


class BoxBusy(GauntletError):
    """Box marked busy; cell deferred."""
