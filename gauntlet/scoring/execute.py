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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from gauntlet.scoring import _strip_fences
from gauntlet.scoring._guard import GUARD_SRC

DEFAULT_TIMEOUT_S = 5.0

_RUNNER_SRC = '''
import importlib.util
import json
import os
import sys
import traceback

import _guard


def _emit(payload):
    payload["violations"] = _guard.violations()
    print(json.dumps(payload))


def main():
    deny_roots = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []

    ns = {"__name__": "candidate"}
    # Read our own inputs BEFORE the guard goes up, then load the hidden tests
    # too: once installed the guard blocks the benchmark tree, and the runner
    # must never be caught by its own control.
    try:
        with open("candidate.py", encoding="utf-8") as fh:
            source = fh.read()
    except OSError as exc:
        _emit({"status": "harness_error", "error": f"cannot read candidate: {exc}"})
        return

    try:
        spec = importlib.util.spec_from_file_location("hidden_tests", "hidden_tests.py")
        hidden = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hidden)
    except BaseException:
        _emit({"status": "harness_error", "error": traceback.format_exc(limit=5)})
        return

    try:
        code = compile(source, "candidate.py", "exec")
    except SyntaxError as exc:
        _emit({"status": "syntax_error", "error": str(exc)})
        return

    # Everything below this line runs untrusted code. The sandbox's own copy of
    # the hidden tests sits in cwd next to the candidate, so it must be denied
    # too — blocking the source tree while leaving the local copy readable
    # would guard the front door and leave the answers on the step.
    _guard.install(deny_roots + [os.path.abspath("hidden_tests.py")])

    try:
        exec(code, ns)
    except BaseException:
        _emit({"status": "runtime_error", "error": traceback.format_exc(limit=5)})
        return

    try:
        results = hidden.check(ns)
    except BaseException:
        _emit({"status": "harness_error", "error": traceback.format_exc(limit=5)})
        return

    total = len(results)
    passed = sum(1 for r in results if r)
    _emit({"status": "ok", "passed": passed, "total": total})


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


def _kill_tree(proc: subprocess.Popen) -> None:
    """Kill the sandbox process *and any children it spawned*, then reap it.

    Must not raise: it runs on the timeout path, and it must leave no live
    handle on the scratch dir or TemporaryDirectory cleanup fails (on Windows
    an open handle makes rmdir raise PermissionError/WinError 32).
    """
    try:
        if os.name == "nt":
            # No killpg on Windows; taskkill /T walks the child tree.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, check=False,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
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

    candidate_src = _strip_fences(output)
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

        proc = subprocess.Popen(
            [sys.executable, "runner.py", json.dumps(_deny_roots(tests_path))],
            cwd=tmp_path,
            env=_sandbox_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            **_spawn_kwargs(),  # own group -> a timeout can kill children too
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            # Must fully reap before leaving the `with`, or TemporaryDirectory
            # cleanup fails on a still-open handle (WinError 32).
            _kill_tree(proc)
            return ExecutionResult(score=0.0, passed=False,
                                    detail=f"timeout after {timeout_s}s",
                                    failure_mode="timeout")

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

    violations = verdict.get("violations") or []
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

    total = verdict.get("total", 0)
    passed_n = verdict.get("passed", 0)
    if total <= 0:
        return ExecutionResult(score=None, passed=False,
                                detail="unscored: hidden test suite reported 0 cases",
                                failure_mode="harness_error")
    score = passed_n / total
    return ExecutionResult(score=score, passed=score == 1.0,
                            detail=f"{passed_n}/{total} hidden asserts passed",
                            failure_mode="none" if score == 1.0 else "wrong_answer")
