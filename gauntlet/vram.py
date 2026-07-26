"""Hand the GPU back when the run is done.

A loaded-but-idle model costs power for nothing, and on a desktop that is the
cost that matters most. LM Studio keeps a JIT-loaded model resident (with a TTL
measured in hours), so a finished run leaves tens of gigabytes of VRAM warm
unless we explicitly release it.

The rule is **snapshot-diff**: record what is loaded before the run, and
afterwards unload only models we ran that were not already there. Anything
resident when we arrived belongs to someone else's session, and evicting it
would be reaching into Kevin's own work.

Unloading shells out to the `lms` CLI rather than issuing HTTP, which keeps the
`OpenAIClient`-is-the-only-HTTP-component invariant intact.
"""
from __future__ import annotations

import shutil
import subprocess

_TIMEOUT_S = 60
_LOAD_TIMEOUT_S = 600  # a 30B model off a cold cache is not quick
# Header and separator rows in `lms ps` output, which we must not read as models.
_SKIP_PREFIXES = ("IDENTIFIER", "---", "===")


def lms_available() -> bool:
    return shutil.which("lms") is not None


def parse_lms_ps_rows(output: str) -> list[tuple[str, bool]]:
    """(identifier, is_local) for each loaded model.

    Locality matters: `lms ps` also lists models held by linked instances on
    other machines. Unloading one of those frees nothing on this card and
    interrupts a different box, so anything not `Local` is off limits.

    Detected by the presence of a bare `Local` token rather than by column
    index, because the SIZE column ("14.19 GB") contains a space and shifts
    every field after it.
    """
    rows: list[tuple[str, bool]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(_SKIP_PREFIXES):
            continue
        fields = stripped.split()
        rows.append((fields[0], "Local" in fields[1:]))
    return rows


def local_loaded_models() -> list[str] | None:
    """Models resident on *this* machine's GPU, or None if we cannot tell."""
    output = _lms_ps_output()
    if output is None:
        return None
    return [name for name, is_local in parse_lms_ps_rows(output) if is_local]


def unload_all_local() -> list[str]:
    """Clear this machine's GPU before a run. Returns what was freed.

    Exclusive-VRAM mode: a benchmark measures a model badly when it is sharing
    the card, because layers spill to CPU and the number that comes out
    describes the contention rather than the model. Starting from an empty card
    makes every model in a run comparable to every other one.
    """
    resident = local_loaded_models() or []
    return [m for m in resident if unload(m)]


def parse_lms_ps(output: str) -> list[str]:
    """Identifiers of the currently-loaded models, from `lms ps` output.

    Whitespace-column format, so take the first field of each data row. An
    unrecognisable line is skipped rather than guessed at: over-reporting a
    loaded model would make us unload something that is not ours.
    """
    models: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(_SKIP_PREFIXES):
            continue
        models.append(stripped.split()[0])
    return models


def models_to_unload(*, before: list[str], ran: list[str]) -> list[str]:
    """Which models this run is responsible for releasing.

    `ran` minus `before`: we clean up after ourselves and nothing else. Sorted
    and deduplicated so the action is deterministic.
    """
    already = set(before)
    return sorted({m for m in ran if m not in already})


def _lms_ps_output() -> str | None:
    if not lms_available():
        return None
    try:
        proc = subprocess.run(["lms", "ps"], capture_output=True, text=True,
                              timeout=_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def loaded_models() -> list[str] | None:
    """Currently-loaded models. `None` means we could not find out.

    The distinction matters and is not pedantic: `[]` says "nothing was loaded,
    so anything resident afterwards is ours to release", while `None` says "we
    have no idea what was already here". Collapsing the two would let a failed
    snapshot evict a model of Kevin's, because it would look identical to an
    empty machine. Same principle as unscored-is-not-zero: absence of knowledge
    is not knowledge of absence.
    """
    output = _lms_ps_output()
    return None if output is None else parse_lms_ps(output)


def release_after_run(before: list[str] | None, ran: list[str]) -> list[str]:
    """Unload what this run is responsible for, and report what was released.

    A `None` snapshot means we never learned what was already loaded, so we
    unload nothing -- leaving VRAM occupied is a wasted-power problem, but
    evicting Kevin's own model mid-session is a broken-work problem, and the
    second is worse.
    """
    if before is None:
        return []
    candidates = models_to_unload(before=before, ran=ran)
    # Only act on what is actually resident. `lms unload` exits 0 for a model
    # that was never loaded, so without this the report claims to have freed
    # models that were already gone -- and a tool whose entire job is reporting
    # machine state does not get to overstate what it did.
    resident = loaded_models()
    if resident is not None:
        candidates = [m for m in candidates if m in resident]
    return [m for m in candidates if unload(m)]


def load(model: str, *, context: int, ttl_s: int = 3600) -> bool:
    """Load a model at exactly the context Gauntlet will use, one slot only.

    Left to itself LM Studio JIT-loads at *its* defaults, which on this box was
    24000 context x 4 parallel slots. Gauntlet issues one request at a time at
    8192, so that allocated a KV cache for ~96k tokens to serve 8k -- about 12x
    the memory actually needed. It overflowed VRAM into system RAM and brought
    the machine to a crawl, and it also made the scorecard lie: cells recorded
    `context: 8192` while the model was really running at 24000.

    A TTL is set as a backstop so a hard-killed run cannot strand the model
    resident forever, since a SIGKILLed process never reaches its unload.
    """
    if not lms_available():
        return False
    try:
        proc = subprocess.run(
            ["lms", "load", model, "--context-length", str(context),
             "--parallel", "1", "--ttl", str(ttl_s), "--yes"],
            capture_output=True, text=True, timeout=_LOAD_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def unload(model: str) -> bool:
    """Release one model. Returns whether it succeeded.

    Never raises: this runs after the scored work is complete, and failing to
    free VRAM must not lose a finished run's results.
    """
    if not lms_available():
        return False
    try:
        proc = subprocess.run(["lms", "unload", model], capture_output=True,
                              text=True, timeout=_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0
