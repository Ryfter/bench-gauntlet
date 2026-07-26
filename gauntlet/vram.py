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
# Header and separator rows in `lms ps` output, which we must not read as models.
_SKIP_PREFIXES = ("IDENTIFIER", "---", "===")


def lms_available() -> bool:
    return shutil.which("lms") is not None


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


def loaded_models() -> list[str] | None:
    """Currently-loaded models. `None` means we could not find out.

    The distinction matters and is not pedantic: `[]` says "nothing was loaded,
    so anything resident afterwards is ours to release", while `None` says "we
    have no idea what was already here". Collapsing the two would let a failed
    snapshot evict a model of Kevin's, because it would look identical to an
    empty machine. Same principle as unscored-is-not-zero: absence of knowledge
    is not knowledge of absence.
    """
    if not lms_available():
        return None
    try:
        proc = subprocess.run(["lms", "ps"], capture_output=True, text=True,
                              timeout=_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return parse_lms_ps(proc.stdout)


def release_after_run(before: list[str] | None, ran: list[str]) -> list[str]:
    """Unload what this run is responsible for, and report what was released.

    A `None` snapshot means we never learned what was already loaded, so we
    unload nothing -- leaving VRAM occupied is a wasted-power problem, but
    evicting Kevin's own model mid-session is a broken-work problem, and the
    second is worse.
    """
    if before is None:
        return []
    return [m for m in models_to_unload(before=before, ran=ran) if unload(m)]


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
