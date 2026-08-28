"""Execution-based code-gen scoring: runs untrusted model-generated code against
a hidden, maintainer-authored assert suite (`check(ns) -> list[bool]`) in an
isolated subprocess — correctness, not parseability (design seed
docs/2026-06-30-discriminative-scoring-v2-seed.md, item 1).

Isolation: fresh subprocess per case (repo venv python via `sys.executable`),
own process group so a timeout kills any children too, a scratch tempdir as
cwd (not the repo tree), and a minimal env (no inherited proxy/API-key vars —
best-effort network discouragement, not a hard sandbox; see the PR description
for hardening tradeoffs). A syntax error, exception, timeout, or failed assert
scores low — it never raises out of this module. A broken hidden-test harness
(our bug, not the candidate's) is `unscored`, never silently 0 (scoring-honesty
invariant, CLAUDE.md).
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import signal
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from gauntlet.scoring import _strip_fences
from gauntlet.scoring._guard import GUARD_SRC

DEFAULT_TIMEOUT_S = 5.0
# Best-effort host-stability caps. These are not a security boundary: ctypes,
# raw syscalls, and other in-process escapes remain reachable. See
# docs/2026-07-25-benchmark-integrity-threat-model.md.
SANDBOX_MEMORY_BYTES = 256 * 1024 * 1024
SANDBOX_MAX_OUTPUT_BYTES = 1 * 1024 * 1024
SANDBOX_MAX_PROCESSES = 8
SANDBOX_KILL_TIMEOUT_S = 10.0

_RUNNER_SRC = '''
import importlib.util
import json
import os
import sys
import traceback

import _guard


def main():
    # Keep the verdict channel in locals captured before candidate code runs.
    # Candidate code shares this interpreter and may replace module globals or
    # builtins such as print, len, sum, and json.dumps.
    trusted_dumps = json.dumps
    trusted_write = sys.stdout.write
    trusted_flush = sys.stdout.flush
    trusted_len = len
    trusted_sum = sum
    trusted_violations = _guard.violations

    def emit(payload):
        payload["violations"] = trusted_violations()
        trusted_write(trusted_dumps(payload) + "\\n")
        trusted_flush()

    deny_roots = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []

    ns = {"__name__": "candidate"}
    # Read our own inputs BEFORE the guard goes up, then load the hidden tests
    # too: once installed the guard blocks the benchmark tree, and the runner
    # must never be caught by its own control.
    try:
        with open("candidate.py", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as exc:
        emit({"status": "harness_error", "error": f"cannot read candidate: {exc}"})
        return

    try:
        spec = importlib.util.spec_from_file_location("hidden_tests", "hidden_tests.py")
        hidden = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hidden)
    except BaseException:
        emit({"status": "harness_error", "error": traceback.format_exc(limit=5)})
        return

    try:
        code = compile(source, "candidate.py", "exec")
    except SyntaxError as exc:
        emit({"status": "syntax_error", "error": str(exc)})
        return

    # Everything below this line runs untrusted code. The sandbox's own copy of
    # the hidden tests sits in cwd next to the candidate, so it must be denied
    # too — blocking the source tree while leaving the local copy readable
    # would guard the front door and leave the answers on the step.
    _guard.install(deny_roots + [os.path.abspath("hidden_tests.py")])

    try:
        exec(code, ns)
    except BaseException:
        emit({"status": "runtime_error", "error": traceback.format_exc(limit=5)})
        return

    try:
        results = hidden.check(ns)
    except BaseException:
        emit({"status": "harness_error", "error": traceback.format_exc(limit=5)})
        return

    total = trusted_len(results)
    passed = trusted_sum(1 for r in results if r)
    emit({"status": "ok", "passed": passed, "total": total})


if __name__ == "__main__":
    main()
'''


FailureMode = Literal[
    "none",            # scored 1.0, nothing went wrong
    "syntax_error",    # candidate source does not parse
    "runtime_exception",  # candidate raised while being exec'd
    "wrong_answer",    # ran clean, but some hidden asserts failed
    "timeout",         # exceeded the sandbox wall clock
    "no_code_emitted",  # model returned prose/nothing — no code to run
    "truncated",       # cut off by the token budget before finishing -> unscored
    "integrity_violation",  # tried to read the benchmark tree / reach the net
    "harness_error",   # OUR bug, not the candidate's -> unscored
]

# Marker planted in every hidden-test file. If a candidate's *output* contains
# one, the model demonstrably saw the file it is graded against.
CANARY_RE = re.compile(r"GAUNTLET-CANARY-[0-9a-f]{12}")


def canary_for(case_id: str) -> str:
    """Deterministic per-case canary, so it is reproducible without storing it."""
    digest = hashlib.sha256(f"gauntlet-canary::{case_id}".encode()).hexdigest()
    return f"GAUNTLET-CANARY-{digest[:12]}"


@dataclass
class ExecutionResult:
    score: float | None   # None == unscored (harness fault, never the candidate's)
    passed: bool
    detail: str
    # Structured reason, so the scorecard can aggregate *why* a model failed
    # rather than parsing `detail` prose. This is what tells Baton whether a
    # miss is a capability gap or a working-memory problem (selective-offload
    # principle, D-2026-06-30c).
    failure_mode: FailureMode = "none"
    # What the candidate tried to do that it should not have: filesystem reads
    # of the benchmark tree, network use, or echoing a hidden-test canary.
    # Recorded even when the attempt was blocked — a blocked attempt is still
    # evidence, and a scorecard that hides it overstates its own trustworthiness.
    integrity_violations: list[dict] = field(default_factory=list)


def _sandbox_env() -> dict[str, str]:
    # Deliberately not os.environ: drops proxy config, API keys, and anything
    # else the parent process carries. Candidate code gets nothing to phone
    # home with beyond direct socket calls (a true network sandbox needs OS
    # support — netns/seccomp — out of scope for a subprocess-only sandbox).
    if os.name == "nt":
        # Windows needs SystemRoot for the C runtime + socket stack to init;
        # without it the interpreter fails to start at all.
        root = os.environ.get("SystemRoot", r"C:\Windows")
        return {"PATH": f"{root}\\System32", "SystemRoot": root}
    return {"PATH": "/usr/bin:/bin"}


# A fenced block: ``` or ~~~, an optional language tag, then the body. The body
# is lazy and the closer optional so a reply truncated mid-block still yields
# what the model managed to write.
_BLOCK_RE = re.compile(
    r"(?P<f>```|~~~)[ \t]*[A-Za-z0-9_+-]*[ \t]*\r?\n(?P<body>.*?)(?:\r?\n(?P=f)|\Z)",
    re.DOTALL,
)


def extract_code(output: str) -> str:
    """Pull the candidate program out of a chat reply.

    Models wrap code in prose — "Here's the solution:" before, "Hope this
    helps!" after — and an extractor that only unwraps a reply *starting* with
    a fence hands all of that to `ast.parse`. The result is a `syntax_error`
    that says nothing about the model's code and everything about how chatty it
    is, which is a bias dressed as a measurement.

    Where a reply holds several blocks, the longest wins: a usage example
    beside the implementation is not the submission.

    A reply with no fence is returned as-is. Deciding whether that is code or a
    refusal belongs to `_looks_like_code`, not here — this function must never
    invent a code block that the model did not write.
    """
    blocks = [m.group("body") for m in _BLOCK_RE.finditer(output)]
    blocks = [b for b in blocks if b.strip()]
    if not blocks:
        return output.strip()
    # `strip()` only at the ends — never reflow the body. Python is whitespace
    # significant, so touching interior indentation would break working code.
    return max(blocks, key=lambda b: len(b.strip())).strip("\r\n").rstrip()


def _looks_like_code(src: str) -> bool:
    """Did the model attempt Python at all?

    Anything that parses is code. Anything that does not is only reported as a
    *syntax* error if it at least reaches for the language — otherwise a chatty
    refusal ("I'd be happy to help! Could you clarify...") gets filed as broken
    code, which misattributes the failure. Deliberately generous: a genuine but
    malformed attempt should read as syntax_error, not as silence.
    """
    if not src.strip():
        return False
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        pass
    markers = ("def ", "class ", "import ", "return ", "lambda", "yield",
               "for ", "while ", "if ", "=", "(")
    return any(m in src for m in markers)


def _spawn_kwargs() -> dict[str, object]:
    """Put the child in its own group so a timeout can take its children with
    it. The mechanism is platform-specific: POSIX gets a new session, Windows
    a new process group."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _user_process_count() -> int:
    """How many processes this user already has, for a relative nproc cap.

    RLIMIT_NPROC is checked against the user's live count when the *child*
    forks, so the cap must sit a few above the current total. The parent
    keeps its own higher limit.
    """
    if sys.platform.startswith("linux"):
        uid = os.getuid()
        n = 0
        try:
            for name in os.listdir("/proc"):
                if not name.isdigit():
                    continue
                try:
                    if os.stat("/proc/" + name).st_uid == uid:
                        n += 1
                except OSError:
                    continue
        except OSError:
            return 1
        return max(n, 1)
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["ps", "-u", str(os.getuid()), "-o", "pid="],
                text=True, timeout=2,
            )
            n = len([line for line in out.splitlines() if line.strip()])
            return max(n, 1)
        except (OSError, subprocess.SubprocessError):
            return 1
    return 1


def _rlimit_pairs(timeout_s: float) -> list[tuple[str, int]]:
    return [
        ("RLIMIT_AS", SANDBOX_MEMORY_BYTES),
        ("RLIMIT_DATA", SANDBOX_MEMORY_BYTES),
        ("RLIMIT_RSS", SANDBOX_MEMORY_BYTES),
        ("RLIMIT_CPU", max(1, int(timeout_s))),
        ("RLIMIT_CORE", 0),
        ("RLIMIT_NPROC", _user_process_count() + SANDBOX_MAX_PROCESSES),
    ]


def _has_prlimit() -> bool:
    try:
        import resource
    except ImportError:
        return False
    return hasattr(resource, "prlimit")


def _posix_preexec(timeout_s: float):
    """Return a preexec_fn that applies best-effort rlimits in the child."""
    pairs = _rlimit_pairs(timeout_s)

    def _apply() -> None:
        try:
            import resource
        except ImportError:
            return
        for name, value in pairs:
            which = getattr(resource, name, None)
            if which is None:
                continue
            try:
                _cur, hard = resource.getrlimit(which)
                if hard != resource.RLIM_INFINITY and value > hard:
                    value = hard
                resource.setrlimit(which, (value, hard))
            except (ValueError, OSError):
                continue

    return _apply


def _prlimit_pid(pid: int, timeout_s: float) -> None:
    try:
        import resource
    except ImportError:
        return
    for name, value in _rlimit_pairs(timeout_s):
        which = getattr(resource, name, None)
        if which is None:
            continue
        try:
            resource.prlimit(pid, which, (value, value))
        except (ValueError, OSError):
            continue


def _rss_bytes(pid: int) -> int | None:
    """Resident set size of ``pid``, or None when unreadable.

    Parent-side sampling is the portable memory cap: macOS rejects RLIMIT_AS
    from this Python, and Windows rlimits do not exist. This is still
    best-effort host stability, not a security boundary.
    """
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/statm", encoding="ascii") as fh:
                parts = fh.read().split()
            return int(parts[1]) * os.sysconf("SC_PAGE_SIZE")
        except (OSError, IndexError, ValueError):
            return None
    if sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["ps", "-o", "rss=", "-p", str(pid)],
                text=True, timeout=1,
            )
            kb = int(out.strip().split()[0])
            return kb * 1024
        except (OSError, subprocess.SubprocessError, IndexError, ValueError):
            return None
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return None
            try:
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(counters)
                if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    return None
                return int(counters.WorkingSetSize)
            finally:
                kernel32.CloseHandle(handle)
        except (OSError, ValueError, TypeError):
            return None
    return None


def _windows_job(proc: subprocess.Popen, timeout_s: float):
    """Assign the child to a Job Object with memory/CPU/process caps.

    Best-effort: assignment can fail when the parent is already in a job that
    forbids breakaway. Callers must keep the returned handle until reaping so
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE can reap descendants if the parent dies.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
    JOB_OBJECT_LIMIT_PROCESS_TIME = 0x00000002
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        | JOB_OBJECT_LIMIT_PROCESS_MEMORY
        | JOB_OBJECT_LIMIT_PROCESS_TIME
        | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    )
    info.BasicLimitInformation.ActiveProcessLimit = SANDBOX_MAX_PROCESSES
    info.BasicLimitInformation.PerProcessUserTimeLimit = int(max(1.0, timeout_s) * 10_000_000)
    info.ProcessMemoryLimit = SANDBOX_MEMORY_BYTES
    if not kernel32.SetInformationJobObject(
        job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info),
    ):
        kernel32.CloseHandle(job)
        return None
    handle = getattr(proc, "_handle", None)
    if handle is None:
        kernel32.CloseHandle(job)
        return None
    if not kernel32.AssignProcessToJobObject(job, int(handle)):
        kernel32.CloseHandle(job)
        return None
    return job


def _close_windows_job(job) -> None:
    if not job:
        return
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle(job)
    except (OSError, ValueError, TypeError):
        pass


def _communicate_capped(
    proc: subprocess.Popen,
    timeout_s: float,
    max_bytes: int,
    *,
    memory_bytes: int,
    job=None,
) -> tuple[bytes, bytes]:
    """Read stdout/stderr up to ``max_bytes`` each, then stop.

    Stopping the read lets the kernel pipe fill so a print bomb blocks instead
    of growing without bound in the parent. A side thread samples RSS and
    kills the tree if it exceeds ``memory_bytes``. Wall-clock timeout still
    reaps a wedged child. Best-effort host stability, not a security boundary.
    """
    buckets = {
        "stdout": {"chunks": [], "n": 0},
        "stderr": {"chunks": [], "n": 0},
    }

    def _reader(stream, bucket: dict) -> None:
        if stream is None:
            return
        try:
            while True:
                if bucket["n"] >= max_bytes:
                    break
                chunk = stream.read(min(65536, max_bytes - bucket["n"] + 1))
                if not chunk:
                    break
                remain = max_bytes - bucket["n"]
                if remain <= 0:
                    break
                bucket["chunks"].append(chunk[:remain])
                bucket["n"] += min(len(chunk), remain)
                if len(chunk) > remain:
                    break
        except OSError:
            pass

    def _watch_rss() -> None:
        while proc.poll() is None:
            rss = _rss_bytes(proc.pid)
            if rss is not None and rss > memory_bytes:
                _kill_tree(proc, job)
                return
            time.sleep(0.02)

    threads = [
        threading.Thread(target=_reader, args=(proc.stdout, buckets["stdout"]), daemon=True),
        threading.Thread(target=_reader, args=(proc.stderr, buckets["stderr"]), daemon=True),
        threading.Thread(target=_watch_rss, daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        for thread in threads:
            thread.join(timeout=0.2)
        raise
    for thread in threads:
        thread.join(timeout=1.0)
    return b"".join(buckets["stdout"]["chunks"]), b"".join(buckets["stderr"]["chunks"])


def _kill_tree(proc: subprocess.Popen, job=None) -> None:
    """Kill the sandbox process *and any children it spawned*, then reap it.

    Must not raise: it runs on the timeout path, and it must leave no live
    handle on the scratch dir or TemporaryDirectory cleanup fails (on Windows
    an open handle makes rmdir raise PermissionError/WinError 32).

    Best-effort containment only — not a security boundary.
    """
    try:
        if os.name == "nt":
            # No killpg on Windows; taskkill /T walks the child tree.
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True, check=False,
                    timeout=SANDBOX_KILL_TIMEOUT_S,
                )
            except (OSError, subprocess.SubprocessError):
                pass
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=SANDBOX_KILL_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        pass
    # Release our own pipe handles; on Windows these also pin the temp dir.
    for stream in (proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except OSError:
            pass


def _deny_roots(tests_path: Path) -> list[str]:
    """Paths the candidate must not be able to read.

    The hidden tests live under `cases/`; blocking that whole subtree (rather
    than just this one file) stops a candidate reading a *sibling* case's
    answers too. The repo root itself is left readable so the sandbox can still
    import the standard library and the venv — this is a targeted deny-list, not
    a general confinement. See the threat-model doc.
    """
    roots: list[str] = []
    tests_dir = tests_path.resolve().parent
    roots.append(str(tests_dir))
    # Walk up to the `cases/` root if we are inside one.
    for parent in tests_dir.parents:
        roots.append(str(parent))
        if parent.name == "cases":
            break
    else:
        return [str(tests_dir)]
    return roots


def _validated_verdict_counts(verdict: object) -> tuple[int, int] | None:
    """Return trusted ``(passed, total)`` counts for an ``ok`` verdict.

    The sandbox is an integrity guard, not a security boundary, so the parent
    treats every byte from it as hostile even after the child-side hardening.
    ``bool`` is intentionally rejected although it subclasses ``int``.
    """
    if not isinstance(verdict, dict):
        return None
    passed = verdict.get("passed")
    total = verdict.get("total")
    if type(passed) is not int or type(total) is not int:
        return None
    if total <= 0 or passed < 0 or passed > total:
        return None
    return passed, total


def code_execution_match(output: str, tests_path: str | Path,
                          timeout_s: float = DEFAULT_TIMEOUT_S) -> ExecutionResult:
    tests_path = Path(tests_path)
    try:
        hidden_src = tests_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: cannot read tests file: {exc}",
                                failure_mode="harness_error")

    # Canary check runs on the RAW model output, before fences are stripped: a
    # model that echoes a hidden-test canary has demonstrably seen the file it
    # is graded against, whatever else it produced. That is unscoreable rather
    # than zero — we cannot say what it can do, only that this number is not
    # evidence of it.
    canaries = set(CANARY_RE.findall(hidden_src))
    echoed = sorted(c for c in canaries if c in output)
    if echoed:
        return ExecutionResult(
            score=None, passed=False,
            detail=f"unscored: output echoed hidden-test canary {echoed[0]}",
            failure_mode="integrity_violation",
            integrity_violations=[{"kind": "canary", "detail": echoed[0]}])

    candidate_src = extract_code(output)
    if not _looks_like_code(candidate_src):
        # The model returned nothing, a refusal, or plain prose. That is a real
        # (and common) small-model failure and a *different* one from writing
        # code that does not work — a model that never engages with the task
        # needs a different intervention from one with an off-by-one. Prose
        # would otherwise be reported as `syntax_error`, which is true of the
        # bytes but wrong about what happened.
        return ExecutionResult(score=0.0, passed=False,
                                detail="no code emitted",
                                failure_mode="no_code_emitted")

    with tempfile.TemporaryDirectory(prefix="gauntlet-codeexec-") as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "candidate.py").write_text(candidate_src, encoding="utf-8")
        (tmp_path / "hidden_tests.py").write_text(hidden_src, encoding="utf-8")
        (tmp_path / "runner.py").write_text(_RUNNER_SRC, encoding="utf-8")
        (tmp_path / "_guard.py").write_text(GUARD_SRC, encoding="utf-8")

        spawn_kwargs = dict(_spawn_kwargs())
        # Linux can apply rlimits after spawn via prlimit (thread-safe).
        # macOS has no prlimit, so the child applies them in preexec_fn.
        apply_after_spawn = os.name != "nt" and _has_prlimit()
        if os.name != "nt" and not apply_after_spawn:
            spawn_kwargs["preexec_fn"] = _posix_preexec(timeout_s)
        proc = subprocess.Popen(
            [sys.executable, "runner.py", json.dumps(_deny_roots(tests_path))],
            cwd=tmp_path,
            env=_sandbox_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **spawn_kwargs,  # own group -> a timeout can kill children too
        )
        job = _windows_job(proc, timeout_s) if os.name == "nt" else None
        if apply_after_spawn:
            _prlimit_pid(proc.pid, timeout_s)
        try:
            try:
                stdout_b, stderr_b = _communicate_capped(
                    proc, timeout_s, SANDBOX_MAX_OUTPUT_BYTES,
                    memory_bytes=SANDBOX_MEMORY_BYTES, job=job,
                )
            except subprocess.TimeoutExpired:
                # Must fully reap before leaving the `with`, or TemporaryDirectory
                # cleanup fails on a still-open handle (WinError 32).
                _kill_tree(proc)
                return ExecutionResult(score=0.0, passed=False,
                                        detail=f"timeout after {timeout_s}s",
                                        failure_mode="timeout")
            stdout = stdout_b.decode("utf-8", errors="replace")
            stderr = stderr_b.decode("utf-8", errors="replace")
        finally:
            _close_windows_job(job)
            for stream in (proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
                    pass

    if proc.returncode != 0 and not stdout.strip():
        # Sandbox process died before emitting its JSON verdict (killed by a
        # signal, OOM, etc.) — that's the candidate's fault, not ours.
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"process exited {proc.returncode}: {stderr[-500:]}",
                                failure_mode="runtime_exception")

    try:
        verdict = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"malformed sandbox output: stdout={stdout!r} stderr={stderr[-300:]!r}",
                                failure_mode="runtime_exception")

    if not isinstance(verdict, dict):
        return ExecutionResult(score=None, passed=False,
                                detail="unscored: sandbox verdict was not an object",
                                failure_mode="harness_error")

    violations = verdict.get("violations") or []
    if not isinstance(violations, list) or not all(
            isinstance(item, dict) for item in violations):
        return ExecutionResult(score=None, passed=False,
                                detail="unscored: malformed sandbox violations",
                                failure_mode="harness_error")
    if violations:
        # The candidate reached for the answers or the network. Whether or not
        # the guard stopped it, the resulting score is not evidence of
        # capability, so it is unscored rather than 0 — reporting a number here
        # would be the scorecard vouching for something it cannot.
        kinds = sorted({v.get("kind", "?") for v in violations})
        return ExecutionResult(
            score=None, passed=False,
            detail=f"unscored: integrity violation ({', '.join(kinds)})",
            failure_mode="integrity_violation",
            integrity_violations=violations)

    status = verdict.get("status")
    if status == "syntax_error":
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"syntax_error: {str(verdict.get('error', ''))[:300]}",
                                failure_mode="syntax_error")
    if status == "runtime_error":
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"runtime_error: {str(verdict.get('error', ''))[:300]}",
                                failure_mode="runtime_exception")
    if status == "harness_error":
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: hidden test harness error: {str(verdict.get('error', ''))[:300]}",
                                failure_mode="harness_error")
    if status != "ok":
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: unexpected sandbox status {status!r}",
                                failure_mode="harness_error")

    counts = _validated_verdict_counts(verdict)
    if counts is None:
        return ExecutionResult(score=None, passed=False,
                                detail="unscored: invalid hidden-test verdict counts",
                                failure_mode="harness_error")
    passed_n, total = counts
    score = passed_n / total
    return ExecutionResult(score=score, passed=score == 1.0,
                            detail=f"{passed_n}/{total} hidden asserts passed",
                            failure_mode="none" if score == 1.0 else "wrong_answer")
