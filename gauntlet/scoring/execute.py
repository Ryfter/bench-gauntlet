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

import json
import os
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

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


@dataclass
class ExecutionResult:
    score: float | None   # None == unscored (harness fault, never the candidate's)
    passed: bool
    detail: str


def _sandbox_env() -> dict[str, str]:
    # Deliberately not os.environ: drops proxy config, API keys, and anything
    # else the parent process carries. Candidate code gets nothing to phone
    # home with beyond direct socket calls (a true network sandbox needs OS
    # support — netns/seccomp — out of scope for a subprocess-only sandbox).
    return {"PATH": "/usr/bin:/bin"}


def code_execution_match(output: str, tests_path: str | Path,
                          timeout_s: float = DEFAULT_TIMEOUT_S) -> ExecutionResult:
    tests_path = Path(tests_path)
    try:
        hidden_src = tests_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: cannot read tests file: {exc}")

    candidate_src = _strip_fences(output)

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
            start_new_session=True,  # own process group -> can kill children on timeout
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            return ExecutionResult(score=0.0, passed=False,
                                    detail=f"timeout after {timeout_s}s")

    if proc.returncode != 0 and not stdout.strip():
        # Sandbox process died before emitting its JSON verdict (killed by a
        # signal, OOM, etc.) — that's the candidate's fault, not ours.
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"process exited {proc.returncode}: {stderr[-500:]}")

    try:
        verdict = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"malformed sandbox output: stdout={stdout!r} stderr={stderr[-300:]!r}")

    status = verdict.get("status")
    if status in ("syntax_error", "runtime_error"):
        return ExecutionResult(score=0.0, passed=False,
                                detail=f"{status}: {str(verdict.get('error', ''))[:300]}")
    if status == "harness_error":
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: hidden test harness error: {str(verdict.get('error', ''))[:300]}")
    if status != "ok":
        return ExecutionResult(score=None, passed=False,
                                detail=f"unscored: unexpected sandbox status {status!r}")

    total = verdict.get("total", 0)
    passed_n = verdict.get("passed", 0)
    if total <= 0:
        return ExecutionResult(score=None, passed=False,
                                detail="unscored: hidden test suite reported 0 cases")
    score = passed_n / total
    return ExecutionResult(score=score, passed=score == 1.0,
                            detail=f"{passed_n}/{total} hidden asserts passed")
