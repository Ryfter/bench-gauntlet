"""A small always-on-top lamp showing whether local models are using the GPU.

Three states, because two are not enough to be useful:

    green   in use   inference is running right now
    yellow  idle     a model is resident in VRAM but nothing is running
    red     free     nothing loaded; the card is yours

Yellow is the reason this exists. A finished run that failed to release its
model looks *exactly* like an idle machine from the outside, while costing power
the whole time. Green tells you why the fans are up; yellow tells you something
should be cleaned up.

The state logic below is pure and unit-tested. The Tk window is a thin shell
around it, and runs as its own process polling the status file -- so it cannot
slow down, block, or crash a benchmark run.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from gauntlet import telemetry, vram
from gauntlet.runstatus import DEFAULT_STATUS_PATH, RunStatus, read_status

__all__ = ["IN_USE", "IDLE", "FREE", "IndicatorState", "indicator_state",
           "run_overlay", "existing_overlay_pid"]

POLL_MS = 2000          # status file: a cheap local read
TELEMETRY_EVERY = 5     # nvidia-smi is a subprocess -- every 5th tick, not every tick
POSITION_PATH = Path("scorecards") / ".overlay.json"
LOCK_PATH = Path("scorecards") / ".overlay.pid"


@dataclass(frozen=True)
class Level:
    name: str
    colour: str
    label: str


# Deliberately muted rather than saturated: this sits on top of whatever Kevin
# is actually working on, so it has to be readable without being loud.
IN_USE = Level("in_use", "#2ecc71", "in use")
IDLE = Level("idle", "#f1c40f", "idle")
FREE = Level("free", "#e74c3c", "free")


@dataclass(frozen=True)
class IndicatorState:
    level: Level
    detail: str


def indicator_state(status: RunStatus | None, loaded: list[str] | None) -> IndicatorState:
    """Decide what the lamp shows.

    `status` is the run marker (None when absent); `loaded` is the resident
    models, or None when LM Studio could not be queried. An active run wins
    outright -- it is generating whether or not we can enumerate VRAM.
    """
    if status is not None and status.is_alive:
        bits = [status.run_id]
        if status.model:
            bits.append(status.model)
        if status.capability:
            bits.append(f"[{status.capability}]")
        if status.cells_total:
            pct = f"{status.progress * 100:.0f}%" if status.progress is not None else "?"
            bits.append(f"cell {status.cells_done}/{status.cells_total} ({pct})")
        if status.cases_total:
            bits.append(f"case {status.cases_done}/{status.cases_total}")
        return IndicatorState(IN_USE, "  ".join(bits))

    if loaded is None:
        # Never claim the card is free on a failed query -- that is a guess
        # dressed as a fact, and the guess is the reassuring direction.
        return IndicatorState(IDLE, "VRAM unknown (lms unavailable)")
    if loaded:
        plural = "s" if len(loaded) > 1 else ""
        return IndicatorState(IDLE, f"{len(loaded)} model{plural} loaded, nothing running")
    return IndicatorState(FREE, "no models loaded")


def existing_overlay_pid() -> int | None:
    """The pid of a lamp already on screen, or None.

    Borderless windows carry no title, so a second lamp stacks invisibly on the
    first and neither one looks wrong -- you just get a stale reading from
    whichever is on top. Cheaper to refuse than to debug.
    """
    try:
        pid = int(LOCK_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    # Reuse the run marker's liveness check: it is the one that is safe on
    # Windows, where the POSIX os.kill(pid, 0) idiom terminates the target.
    probe = RunStatus(run_id="overlay", pid=pid, started_at="")
    return pid if probe.is_alive else None


def claim_overlay_lock() -> None:
    try:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass


def release_overlay_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def format_load(gpu: "telemetry.GpuLoad | None") -> str:
    """The physical readout: temperature, fan, VRAM.

    These are the numbers Kevin judges by -- he hears the fan and feels the
    heat long before he reads a log. A missing field is omitted rather than
    shown as zero.
    """
    if gpu is None:
        return ""
    parts = []
    if gpu.temperature_c is not None:
        parts.append(f"{gpu.temperature_c}°C")
    if gpu.fan_pct is not None:
        parts.append(f"fan {gpu.fan_pct}%")
    if gpu.vram_used_mib and gpu.vram_total_mib:
        parts.append(f"{gpu.vram_used_mib / 1024:.1f}/{gpu.vram_total_mib / 1024:.0f}GB")
    return "  ".join(parts)


def read_position() -> tuple[int, int] | None:
    try:
        data = json.loads(POSITION_PATH.read_text(encoding="utf-8"))
        return int(data["x"]), int(data["y"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_position(x: int, y: int) -> None:
    try:
        POSITION_PATH.parent.mkdir(parents=True, exist_ok=True)
        POSITION_PATH.write_text(json.dumps({"x": x, "y": y}), encoding="utf-8")
    except OSError:
        pass  # a forgotten position is not worth an error


def run_overlay(status_path: str | Path = DEFAULT_STATUS_PATH) -> None:
    """Show the lamp until it is closed. Blocks; run it in its own process."""
    import tkinter as tk

    claim_overlay_lock()
    root = tk.Tk()
    root.title("Gauntlet")
    root.overrideredirect(True)      # no title bar — it is a lamp, not a window
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.88)
    except tk.TclError:
        pass  # no compositing; a solid window is fine

    bg = "#1c1f24"
    frame = tk.Frame(root, bg=bg, padx=9, pady=6, highlightthickness=1,
                     highlightbackground="#3a4048")
    frame.pack()

    dot = tk.Canvas(frame, width=14, height=14, bg=bg, highlightthickness=0)
    dot.pack(side="left")
    blob = dot.create_oval(2, 2, 12, 12, fill=FREE.colour, outline="")

    label = tk.Label(frame, text="", bg=bg, fg="#e8eaed",
                     font=("Segoe UI", 9, "bold"))
    label.pack(side="left", padx=(7, 5))
    detail = tk.Label(frame, text="", bg=bg, fg="#9aa0a6", font=("Segoe UI", 8))
    detail.pack(side="left", padx=(0, 6))
    load = tk.Label(frame, text="", bg=bg, fg="#9aa0a6", font=("Segoe UI", 8))
    load.pack(side="left", padx=(0, 6))

    close = tk.Label(frame, text="✕", bg=bg, fg="#6b7178",
                     font=("Segoe UI", 9, "bold"), cursor="hand2")
    close.pack(side="left")
    close.bind("<Button-1>", lambda _e: _shutdown(root))
    root.bind("<Escape>", lambda _e: _shutdown(root))

    # Drag by grabbing anywhere on the lamp. Offset is captured on press so the
    # window does not jump to the cursor's corner.
    drag = {"x": 0, "y": 0}

    def press(event: "tk.Event") -> None:
        drag["x"], drag["y"] = event.x_root - root.winfo_x(), event.y_root - root.winfo_y()

    def motion(event: "tk.Event") -> None:
        root.geometry(f"+{event.x_root - drag['x']}+{event.y_root - drag['y']}")

    for widget in (frame, label, detail, dot):
        widget.bind("<Button-1>", press)
        widget.bind("<B1-Motion>", motion)

    pos = read_position()
    if pos:
        root.geometry(f"+{pos[0]}+{pos[1]}")
    else:
        root.update_idletasks()
        root.geometry(f"+{root.winfo_screenwidth() - root.winfo_width() - 24}+24")

    # Subprocess-backed readings are cached between ticks. The first version of
    # this polled `lms ps` every 2s and two copies were running at once -- a
    # process spawn about once a second, forever. An indicator built to reduce
    # annoyance has no business being a load of its own.
    cache: dict = {"n": 0, "loaded": None, "gpu": None}

    def tick() -> None:
        if cache["n"] % TELEMETRY_EVERY == 0:
            cache["loaded"] = vram.loaded_models()
            cache["gpu"] = telemetry.gpu_load()
        cache["n"] += 1

        state = indicator_state(read_status(status_path), cache["loaded"])
        gpu = cache["gpu"]
        dot.itemconfig(blob, fill=state.level.colour)
        label.config(text=state.level.label, fg=state.level.colour)
        detail.config(text=state.detail)

        # Heat and fan are how Kevin actually notices a run, so they get their
        # own readout and turn amber past the point they become audible.
        load.config(text=format_load(gpu),
                    fg="#f39c12" if (gpu and gpu.is_stressed) else "#9aa0a6")
        root.after(POLL_MS, tick)

    def _shutdown(win: "tk.Tk") -> None:
        save_position(win.winfo_x(), win.winfo_y())
        release_overlay_lock()
        win.destroy()

    root.protocol("WM_DELETE_WINDOW", lambda: _shutdown(root))
    tick()
    try:
        root.mainloop()
    finally:
        release_overlay_lock()
