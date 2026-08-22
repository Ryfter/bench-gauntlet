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

from pydantic import BaseModel, Field

# Beside the run directories, not inside one, so it is findable without knowing
# the run id -- which is the whole point when you are asking "what is running?"
DEFAULT_STATUS_PATH = Path("scorecards") / ".running.json"


_STILL_ACTIVE = 259  # Windows STILL_ACTIVE exit code
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _win_pid_alive(pid: int) -> bool:
    """Liveness on Windows, without signalling the process.

    Opens the process for query only and reads its exit code; `STILL_ACTIVE`
    means running. A failed open means it is gone (or not ours to inspect,
    which for our own run marker amounts to the same thing).
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


class RunStatus(BaseModel):
    run_id: str
    pid: int
    started_at: str
    updated_at: str = ""
    model: str | None = None
    capability: str | None = None
    cells_done: int = 0
    cells_total: int = 0
    # Progress *within* the current cell. A cell is one battery against one
    # model, which for 108 code-gen cases against a verbose reasoning model runs
    # for hours -- so cell-granularity alone leaves the indicator looking frozen
    # for the whole of it, and an indicator that looks frozen is one you stop
    # believing. These are the heartbeat.
    cases_done: int = 0
    cases_total: int = 0
    # Recorded so cleanup survives a hard kill. `finally` does not run when the
    # process is SIGKILLed, which is exactly how an interrupted run tends to
    # end -- and then VRAM stays occupied with no in-memory record of what was
    # already resident. Persisting both halves of the snapshot-diff lets
    # `gauntlet release` finish the job from the file alone.
    vram_before: list[str] | None = None
    models_ran: list[str] = Field(default_factory=list)

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

        **Never use `os.kill(pid, 0)` here.** That is the POSIX idiom for
        probing liveness, but on Windows CPython routes any signal other than
        CTRL_C_EVENT/CTRL_BREAK_EVENT straight to `TerminateProcess` -- so the
        "harmless" probe would kill the very run it is asking about.
        """
        if self.pid <= 0:
            return False
        if os.name == "nt":
            return _win_pid_alive(self.pid)
        try:
            os.kill(self.pid, 0)
        except (ProcessLookupError, ValueError):
            return False
        except PermissionError:
            return True  # exists, owned by someone else
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
