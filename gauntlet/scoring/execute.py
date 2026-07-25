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
import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gauntlet.scoring import _strip_fences

DEFAULT_TIMEOUT_S = 5.0

_RUNNER_SRC = '''
import importlib.util
import json
import traceback


def main():
    ns = {"__name__": "candidate"}
    try:
        with open("candidate.py", encoding="utf-8") as fh:
            source = fh.read()
        code = compile(source, "candidate.py", "exec")
    except SyntaxError as exc:
        print(json.dumps({"status": "syntax_error", "error": str(exc)}))
        return
    try:
        exec(code, ns)
    except BaseException:
        print(json.dumps({"status": "runtime_error", "error": traceback.format_exc(limit=5)}))
        return

    try:
        spec = importlib.util.spec_from_file_location("hidden_tests", "hidden_tests.py")
        hidden = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(hidden)
        results = hidden.check(ns)
    except BaseException:
        print(json.dumps({"status": "harness_error", "error": traceback.format_exc(limit=5)}))
        return

    total = len(results)
    passed = sum(1 for r in results if r)
    print(json.dumps({"status": "ok", "passed": passed, "total": total}))


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
    "harness_error",   # OUR bug, not the candidate's -> unscored
]


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


def code_execution_match(output: str, tests_path: str | Path,
                          timeout_s: float = DEFAULT_TIMEOUT_S) -> ExecutionResult:
    tests_path = Path(tests_path)
    try:
        hidden_src = tests_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: cannot read tests file: {exc}",
                                failure_mode="harness_error")

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

        proc = subprocess.Popen(
            [sys.executable, "runner.py"],
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
