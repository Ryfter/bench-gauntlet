"""Machine load: GPU temperature, fan, utilisation, VRAM, and system RAM.

Kevin does not notice a benchmark by reading a log -- he notices it because the
fan spins up and the box gets hot. So those are the numbers the indicator has to
show. VRAM alone was the wrong signal: the run that obliterated his machine did
it through a KV cache that spilled into *system* RAM, which a VRAM reading does
not reveal at all.

Parsing is pure and tested; the two collectors are thin shells. System RAM is
read through a ctypes call rather than a subprocess so it can be polled often
and cost nothing.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

_TIMEOUT_S = 15

# Thresholds for the "is it going crazy" read. Deliberately about what is
# audible or physical rather than about utilisation: a card can sit at 100%
# quietly, and that is fine -- heat and fan noise are what intrude.
#
# Calibrated to THIS machine, which is near-silent in normal use: idle sits
# around 32% fan and 45-50C, and Kevin heard the fans more on 2026-07-26 than in
# the preceding year of owning it. A generic 75C/60% threshold would have stayed
# green through the entire day he was complaining about, which makes it worse
# than no threshold -- it would have told him nothing was wrong.
HOT_C = 65
LOUD_FAN_PCT = 45


@dataclass(frozen=True)
class GpuLoad:
    temperature_c: int | None = None
    fan_pct: int | None = None
    utilisation_pct: int | None = None
    vram_used_mib: int | None = None
    vram_total_mib: int | None = None

    @property
    def vram_pct(self) -> float | None:
        if not self.vram_used_mib or not self.vram_total_mib:
            return None
        return 100.0 * self.vram_used_mib / self.vram_total_mib

    @property
    def is_hot(self) -> bool:
        return self.temperature_c is not None and self.temperature_c >= HOT_C

    @property
    def is_loud(self) -> bool:
        return self.fan_pct is not None and self.fan_pct >= LOUD_FAN_PCT

    @property
    def is_stressed(self) -> bool:
        """Whether the machine is in the state Kevin would notice from across
        the room. Heat or fan, not utilisation -- a busy card that stays cool
        and quiet is not a problem."""
        return self.is_hot or self.is_loud


QUERY = ("temperature.gpu,fan.speed,utilization.gpu,memory.used,memory.total")


def parse_nvidia_smi(line: str) -> GpuLoad:
    """One CSV row from `nvidia-smi --query-gpu=... --format=csv,noheader`.

    Fields can read `[N/A]` (notably fan speed on laptops and some datacentre
    cards), so each is parsed independently and a missing one stays None rather
    than discarding the whole reading.
    """
    fields = [f.strip() for f in line.split(",")]

    def num(index: int) -> int | None:
        if index >= len(fields):
            return None
        digits = "".join(c for c in fields[index] if c.isdigit())
        return int(digits) if digits else None

    return GpuLoad(temperature_c=num(0), fan_pct=num(1), utilisation_pct=num(2),
                   vram_used_mib=num(3), vram_total_mib=num(4))


def gpu_load() -> GpuLoad | None:
    """Current GPU telemetry, or None when nvidia-smi is unavailable."""
    if shutil.which("nvidia-smi") is None:
        return None
    try:
        proc = subprocess.run(
            ["nvidia-smi", f"--query-gpu={QUERY}", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    first = next((ln for ln in proc.stdout.splitlines() if ln.strip()), "")
    return parse_nvidia_smi(first) if first else None


@dataclass(frozen=True)
class SystemMemory:
    used_gb: float
    total_gb: float

    @property
    def used_pct(self) -> float:
        return 100.0 * self.used_gb / self.total_gb if self.total_gb else 0.0


def system_memory() -> SystemMemory | None:
    """Physical RAM in use. Cheap enough to poll often -- no subprocess.

    Worth watching alongside VRAM: a model whose KV cache overflows the card
    spills here, and that spill is exactly what made the machine crawl while
    VRAM still looked survivable.
    """
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class _MemStatus(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD),
                        ("dwMemoryLoad", wintypes.DWORD),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        status = _MemStatus()
        status.dwLength = ctypes.sizeof(_MemStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        total = status.ullTotalPhys / 1024**3
        return SystemMemory(used_gb=total - status.ullAvailPhys / 1024**3,
                            total_gb=total)

    try:  # POSIX
        page_size = os.sysconf("SC_PAGE_SIZE")
        total = os.sysconf("SC_PHYS_PAGES") * page_size / 1024**3
        avail = os.sysconf("SC_AVPHYS_PAGES") * page_size / 1024**3
        return SystemMemory(used_gb=total - avail, total_gb=total)
    except (ValueError, OSError, AttributeError):
        return None
