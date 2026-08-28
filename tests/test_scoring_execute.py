"""TDD for the code-exec scorer (gauntlet/scoring/execute.py): runs untrusted
model-generated code against a hidden, maintainer-authored assert suite in an
isolated subprocess. Correctness, not parseability — never crashes the runner."""
from __future__ import annotations

from gauntlet.scoring.execute import code_execution_match

ADD_TESTS = """
def check(ns):
    # Defensive lookup: a candidate that never defines add() fails every case
    # below rather than crashing the harness (missing symbol is the
    # candidate's fault, not ours -- it must score 0, not unscored).
    f = ns.get("add")
    cases = [((1, 2), 3), ((-1, 1), 0), ((0, 0), 0)]
    results = []
    for args, expected in cases:
        try:
            results.append(f(*args) == expected)
        except Exception:
            results.append(False)
    return results
"""


def _write_tests(tmp_path, name, src):
    path = tmp_path / name
    path.write_text(src, encoding="utf-8")
    return path


def test_correct_code_scores_1_and_passes(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "def add(a, b):\n    return a + b\n"
    result = code_execution_match(code, tests_path)
    assert result.score == 1.0
    assert result.passed is True


def test_partial_correctness_scores_fraction(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    # Hardcodes the wrong answer for (1, 2) only -> fails 1 of 3 hidden cases.
    code = "def add(a, b):\n    if (a, b) == (1, 2):\n        return 999\n    return a + b\n"
    result = code_execution_match(code, tests_path)
    assert 0.0 < result.score < 1.0
    assert result.passed is False


def test_wrong_code_scores_0(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "def add(a, b):\n    return 999\n"
    result = code_execution_match(code, tests_path)
    assert result.score == 0.0
    assert result.passed is False


def test_candidate_cannot_forge_sandbox_verdict_through_shared_globals(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = '''
import builtins
import json
import sys

def forged_print(*args, **kwargs):
    sys.__stdout__.write(
        '{"status":"ok","passed":7,"total":1,"violations":[]}\\n'
    )

builtins.print = forged_print
json.dumps = lambda payload: (
    '{"status":"ok","passed":7,"total":1,"violations":[]}'
)

def add(a, b):
    return 999
'''
    result = code_execution_match(code, tests_path)
    assert result.score == 0.0
    assert result.passed is False
    assert result.detail == "0/3 hidden asserts passed"


def test_syntax_error_scores_0_never_crashes(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "def add(a, b) return a + b\n"
    result = code_execution_match(code, tests_path)
    assert result.score == 0.0
    assert result.passed is False
    assert "syntax" in result.detail.lower()


def test_missing_function_scores_0_never_crashes(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "def not_add(a, b):\n    return a + b\n"
    result = code_execution_match(code, tests_path)
    assert result.score == 0.0
    assert result.passed is False


def test_runtime_exception_scores_0_never_crashes(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "def add(a, b):\n    raise RuntimeError('boom')\n"
    result = code_execution_match(code, tests_path)
    assert result.score == 0.0
    assert result.passed is False


def test_infinite_loop_times_out_and_scores_0(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "def add(a, b):\n    while True:\n        pass\n"
    result = code_execution_match(code, tests_path, timeout_s=0.5)
    assert result.score == 0.0
    assert result.passed is False
    assert "timeout" in result.detail.lower()


def test_fenced_code_block_is_stripped(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "```python\ndef add(a, b):\n    return a + b\n```"
    result = code_execution_match(code, tests_path)
    assert result.score == 1.0
    assert result.passed is True


def test_missing_tests_file_is_unscored_not_zero(tmp_path):
    result = code_execution_match("def add(a, b):\n    return a + b\n",
                                   tmp_path / "does-not-exist.py")
    assert result.score is None
    assert result.passed is False
    assert "unscored" in result.detail.lower()


def test_broken_hidden_test_harness_is_unscored_not_zero(tmp_path):
    # A bug in *our* hidden test file (not the candidate's fault) must not
    # silently read as a 0 — that would overstate confidence the model failed.
    tests_path = _write_tests(tmp_path, "tests.py", "def check(ns):\n    raise ValueError('harness bug')\n")
    code = "def add(a, b):\n    return a + b\n"
    result = code_execution_match(code, tests_path)
    assert result.score is None
    assert result.passed is False
    assert "unscored" in result.detail.lower()


def test_stateful_class_under_test(tmp_path):
    stateful_tests = """
def check(ns):
    cls = ns["Counter"]
    c = cls()
    results = []
    results.append(c.value() == 0)
    c.increment()
    c.increment()
    results.append(c.value() == 2)
    c.reset()
    results.append(c.value() == 0)
    return results
"""
    tests_path = _write_tests(tmp_path, "tests.py", stateful_tests)
    code = (
        "class Counter:\n"
        "    def __init__(self):\n"
        "        self._v = 0\n"
        "    def increment(self):\n"
        "        self._v += 1\n"
        "    def reset(self):\n"
        "        self._v = 0\n"
        "    def value(self):\n"
        "        return self._v\n"
    )
    result = code_execution_match(code, tests_path)
    assert result.score == 1.0
    assert result.passed is True


def test_sandbox_has_no_filesystem_access_to_repo_tree(tmp_path):
    # The candidate's cwd is an isolated tempdir, not the repo tree — writing a
    # relative-path file must not land anywhere the caller can see.
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = (
        "def add(a, b):\n"
        "    with open('leaked.txt', 'w') as fh:\n"
        "        fh.write('x')\n"
        "    return a + b\n"
    )
    result = code_execution_match(code, tests_path)
    assert result.score == 1.0
    assert not (tmp_path / "leaked.txt").exists()


# --- prose vs broken code (failure-mode attribution) --------------------------

_TESTS_ANY = """
def check(ns):
    f = ns.get("solve")
    if not callable(f):
        return [False] * 2
    return [True, True]
"""


def _tests_file(tmp_path):
    p = tmp_path / "hidden_tests.py"
    p.write_text(_TESTS_ANY, encoding="utf-8")
    return p


def test_prose_reply_is_no_code_emitted_not_syntax_error(tmp_path):
    """A chatty refusal is a different failure from broken code.

    Both score 0, but only one is worth trying to scaffold around, so the
    scorecard must not file them under the same reason.
    """
    result = code_execution_match(
        "I'd be happy to help! Could you clarify the expected output format?",
        _tests_file(tmp_path))
    assert result.failure_mode == "no_code_emitted"
    assert result.score == 0.0


def test_empty_reply_is_no_code_emitted(tmp_path):
    result = code_execution_match("   \n\n  ", _tests_file(tmp_path))
    assert result.failure_mode == "no_code_emitted"


def test_genuine_but_malformed_attempt_is_syntax_error(tmp_path):
    """A real attempt that does not parse must stay syntax_error — the
    prose check is generous on purpose and must not swallow broken code."""
    result = code_execution_match("def solve(:\n    return 1\n", _tests_file(tmp_path))
    assert result.failure_mode == "syntax_error"


def test_working_code_reports_no_failure_mode(tmp_path):
    result = code_execution_match("def solve(x):\n    return x\n", _tests_file(tmp_path))
    assert result.failure_mode == "none"
    assert result.score == 1.0


def test_sandbox_output_flood_does_not_score_as_success(tmp_path):
    """Unbounded stdout must not let a print bomb look like a perfect solution.

    Host stability, not a security boundary: once the pipe cap fills, the child
    blocks and the wall-clock timeout reaps it.
    """
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = "print('x' * 5_000_000)\ndef add(a, b):\n    return a + b\n"
    result = code_execution_match(code, tests_path, timeout_s=2.0)
    assert result.passed is False
    assert result.score != 1.0
    assert result.failure_mode in {"timeout", "runtime_exception"}


def test_sandbox_memory_bomb_does_not_score_as_success(tmp_path):
    tests_path = _write_tests(tmp_path, "tests.py", ADD_TESTS)
    code = (
        "x = bytearray(300 * 1024 * 1024)\n"
        "import time\n"
        "time.sleep(0.5)\n"
        "def add(a, b):\n"
        "    return a + b\n"
    )
    result = code_execution_match(code, tests_path, timeout_s=3.0)
    assert result.passed is False
    assert result.score != 1.0
    assert result.failure_mode in {"timeout", "runtime_exception"}


def test_kill_tree_bounds_windows_taskkill(monkeypatch):
    """A wedged taskkill must not hang the parent indefinitely."""
    import subprocess as sp

    import gauntlet.scoring.execute as ex

    seen = {}

    def fake_run(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return sp.CompletedProcess(args[0] if args else [], 0)

    monkeypatch.setattr(ex.os, "name", "nt")
    monkeypatch.setattr(ex.subprocess, "run", fake_run)

    class FakeProc:
        pid = 4242
        stdout = None
        stderr = None

        def kill(self):
            return None

        def wait(self, timeout=None):
            return 0

    ex._kill_tree(FakeProc())
    assert seen["kwargs"].get("timeout") is not None
    assert seen["kwargs"]["timeout"] > 0
