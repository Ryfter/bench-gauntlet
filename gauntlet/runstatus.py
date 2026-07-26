"""The run indicator.

Gauntlet runs on Kevin's desktop, so a run that pegs the GPU for hours needs to
announce itself. A backgrounded process writing to a log file is invisible: the
first symptom is a loud machine and no way to tell what is causing it.

One small JSON file at a well-known path, written at start, updated per cell,
removed on exit. `gauntlet status` reads it. It deliberately carries no
base_url, host, or IP -- the privacy invariant applies to everything Gauntlet
writes, and knowing *what* is running never requires knowing *where*.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

# Beside the run directories, not inside one, so it is findable without knowing
# the run id -- which is the whole point when you are asking "what is running?"
DEFAULT_STATUS_PATH = Path("scorecards") / ".running.json"


class RunStatus(BaseModel):
    run_id: str
    pid: int
    started_at: str
    updated_at: str = ""
    model: str | None = None
    capability: str | None = None
    cells_done: int = 0
    cells_total: int = 0

    @property
    def progress(self) -> float | None:
        """Fraction complete, or None when the total is unknown."""
        if self.cells_total <= 0:
            return None
        return self.cells_done / self.cells_total

    @property
    def is_alive(self) -> bool:
        """Whether the recorded pid still exists.

        A killed run leaves its status file behind, and a stale file that reads
        as "running" is worse than none -- it is exactly the wrong answer to the
        question the file exists to answer.
        """
        try:
            os.kill(self.pid, 0)
        except (ProcessLookupError, ValueError):
            return False
        except PermissionError:
            return True  # exists, owned by someone else
        except OSError:
            return True
        return True


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_status(path: str | Path, status: RunStatus) -> None:
    status.updated_at = now_iso()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(status.model_dump_json(indent=2), encoding="utf-8")


def read_status(path: str | Path) -> RunStatus | None:
    """The current run, or None if nothing is running.

    A missing *or unparseable* file both mean "no run": this is called to
    diagnose a machine that is behaving oddly, so it must not add its own
    failure to whatever is already wrong.
    """
    path = Path(path)
    if not path.exists():
        return None
    try:
        return RunStatus.model_validate_json(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        return None


def clear_status(path: str | Path) -> None:
    """Remove the indicator. Safe to call twice, and safe to call from a
    `finally` -- an error while cleaning up would mask the real one."""
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass
