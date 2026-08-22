"""Source template for the in-sandbox integrity guard.

This module is never imported by Gauntlet itself. Its `GUARD_SRC` string is
written into the sandbox scratch directory and imported by the runner *before*
the candidate's code is exec'd, so the guard is already in place by the time
untrusted code gets to act.

Why it exists: the sandbox runs the candidate with a scratch tempdir as cwd,
but absolute paths and sockets were unrestricted. A candidate could therefore
`open()` its own hidden test file, or fetch an answer over the network, and
score 1.0 without demonstrating any capability. A benchmark that can be
shortcut measures nothing.

What this is NOT: a security boundary. It is a Python-level guard, and Python
gives determined code plenty of ways around it (`ctypes`, `os.system`, re-exec,
raw syscalls). It reliably stops *accidental and casual* cheating — a model that
notices a readable path next to it — and it records attempts. Real isolation
needs OS support (namespaces, seccomp, a container); see the threat-model doc.

Policy is deny-list, not allow-list, and deliberately so: the sandbox must stay
able to import the standard library, which lives outside the scratch dir. So we
block the paths that would constitute cheating (the repo tree, above all
`cases/`) rather than trying to confine all I/O.
"""
from __future__ import annotations

GUARD_SRC = '''
"""In-sandbox integrity guard. Installed before candidate code runs."""
import builtins
import io
import os
import sys

_VIOLATIONS = []
_DENY_ROOTS = []
_NET_BLOCKED = False


def violations():
    return list(_VIOLATIONS)


def _record(kind, detail):
    _VIOLATIONS.append({"kind": kind, "detail": str(detail)[:200]})


def _denied(path):
    try:
        resolved = os.path.realpath(os.path.abspath(os.fspath(path)))
    except Exception:
        return False
    for root in _DENY_ROOTS:
        if resolved == root or resolved.startswith(root + os.sep):
            return True
    return False


def _guard_path(fn, kind):
    def wrapper(file, *args, **kwargs):
        if _denied(file):
            _record(kind, file)
            raise PermissionError(
                "gauntlet integrity guard: reading the benchmark tree is not "
                "permitted from inside a scored solution"
            )
        return fn(file, *args, **kwargs)
    return wrapper


def _refuse_factory(kind, message):
    def _refuse(*args, **kwargs):
        _record(kind, message)
        raise PermissionError("gauntlet integrity guard: " + message)
    return _refuse


def _block_subprocesses():
    """Shelling out sidesteps every Python-level file patch.

    Verified: `os.system("cp hidden_tests.py leaked.txt")` followed by reading
    the copy defeated the open() guard completely, because the copy has an
    allowed name. Blocking process creation closes that whole class rather
    than playing whack-a-mole with filenames.
    """
    refuse = _refuse_factory(
        "subprocess", "spawning processes is not permitted from inside a "
                      "scored solution")
    os.system = refuse
    os.popen = refuse
    for name in ("execv", "execve", "execl", "execlp", "execvp", "spawnv",
                 "spawnve", "posix_spawn", "fork", "forkpty"):
        if hasattr(os, name):
            setattr(os, name, refuse)
    try:
        import subprocess
        subprocess.Popen = refuse
        subprocess.run = refuse
        subprocess.call = refuse
        subprocess.check_output = refuse
    except ImportError:
        pass


def _block_introspection():
    """Close the in-process routes to the grader's own data.

    Verified: `gc.get_objects()` reaches the hidden-test module's `__dict__`
    and reads the expected values straight out of it. The grader necessarily
    shares this process with the candidate, so these routes exist; blocking the
    obvious ones turns a silent success into a recorded violation.

    This raises the bar, it does not close the hole — see the threat model.
    """
    import gc
    gc.get_objects = _refuse_factory(
        "introspection", "walking live objects is not permitted from inside a "
                         "scored solution")
    gc.get_referrers = _refuse_factory(
        "introspection", "walking referrers is not permitted from inside a "
                         "scored solution")
    sys._getframe = _refuse_factory(
        "introspection", "walking the call stack is not permitted from inside "
                         "a scored solution")


def _block_network():
    import socket

    def _refuse(*args, **kwargs):
        _record("network", "socket use attempted")
        raise PermissionError(
            "gauntlet integrity guard: network access is not permitted from "
            "inside a scored solution"
        )

    socket.socket = _refuse
    socket.create_connection = _refuse
    socket.socketpair = _refuse
    try:
        socket.create_server = _refuse
    except AttributeError:
        pass


def install(deny_roots, block_network=True):
    """Patch file and network entry points. Idempotent per process."""
    global _NET_BLOCKED
    for root in deny_roots:
        if root:
            _DENY_ROOTS.append(os.path.realpath(os.path.abspath(root)))

    builtins.open = _guard_path(builtins.open, "filesystem")
    io.open = _guard_path(io.open, "filesystem")
    os.open = _guard_path(os.open, "filesystem")

    # Directory listing is enough to locate a hidden test file even without
    # reading it, so close that too.
    _os_listdir, _os_scandir = os.listdir, os.scandir
    os.listdir = _guard_path(_os_listdir, "filesystem")
    os.scandir = _guard_path(_os_scandir, "filesystem")

    _block_subprocesses()
    _block_introspection()

    if block_network:
        _block_network()
        _NET_BLOCKED = True

    # Nothing on sys.path should reach the repo tree.
    sys.path[:] = [p for p in sys.path if not _denied(p or ".")]
'''
