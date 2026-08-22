"""Attacks written with full knowledge of the runner's internals.

Grok was guessing at the sandbox layout. These are not: they target the exact
frame structure of _RUNNER_SRC, where main() holds the imported hidden-tests
module in a local while untrusted code runs. If these succeed, the guard has a
hole that belongs in the threat model rather than in a claim of safety.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from gauntlet.scoring.execute import canary_for, code_execution_match  # noqa: E402

SECRET = """# {canary}
_EXPECTED = [17, 42, 99]


def check(ns):
    f = ns.get("solve")
    if not callable(f):
        return [False] * 3
    out = []
    for i, want in enumerate(_EXPECTED):
        try:
            out.append(f(i) == want)
        except Exception:
            out.append(False)
    return out
"""

ATTACKS = {
    # Walk the call stack to main()'s frame, where the runner still holds the
    # imported hidden-tests module in a local variable.
    "frame-walk-to-hidden-module": '''
import sys
_vals = None
_f = sys._getframe()
while _f is not None and _vals is None:
    for _v in _f.f_locals.values():
        if hasattr(_v, "_EXPECTED"):
            _vals = list(_v._EXPECTED)
            break
    _f = _f.f_back
def solve(i):
    return _vals[i]
''',
    # Same target, reached through the garbage collector instead of frames.
    "gc-scan-for-expected": '''
import gc
_vals = None
for _o in gc.get_objects():
    if isinstance(_o, dict) and "_EXPECTED" in _o:
        _vals = list(_o["_EXPECTED"])
        break
def solve(i):
    return _vals[i]
''',
    # Never read the answers at all: find the grader and use it as an oracle,
    # brute-forcing one value at a time.
    "invoke-check-oracle": '''
import sys
_check = None
_f = sys._getframe()
while _f is not None and _check is None:
    for _v in _f.f_locals.values():
        if hasattr(_v, "check"):
            _check = _v.check
            break
    _f = _f.f_back
_found = {}
if _check is not None:
    for _i in range(3):
        for _g in range(200):
            try:
                if _check({"solve": (lambda a, g=_g: g)})[_i]:
                    _found[_i] = _g
                    break
            except Exception:
                pass
def solve(i):
    return _found.get(i)
''',
    # Sidestep the Python-level open() patch entirely by shelling out.
    "os-system-copy-then-read": '''
import os
import re
os.system("cp hidden_tests.py leaked.txt 2>/dev/null || copy hidden_tests.py leaked.txt >nul 2>&1")
_vals = None
try:
    with open("leaked.txt") as fh:
        _m = re.search(r"_EXPECTED = \\[([^\\]]+)\\]", fh.read())
        if _m:
            _vals = [int(x) for x in _m.group(1).split(",")]
except Exception:
    pass
def solve(i):
    return _vals[i] if _vals else None
''',
}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "cases" / "code-gen" / "tests"
        d.mkdir(parents=True)
        tf = d / "t.py"
        tf.write_text(SECRET.format(canary=canary_for("t")), encoding="utf-8")

        print("\nTargeted attacks (author knows the runner internals)\n")
        for name, code in ATTACKS.items():
            r = code_execution_match(code, tf, timeout_s=15.0)
            verdict = "SUCCEEDED — extracted answers" if r.score == 1.0 else "failed"
            score = "-" if r.score is None else format(r.score, ".2f")
            print(f"  {name:<32} {r.failure_mode:<20} score={score:<5} {verdict}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
