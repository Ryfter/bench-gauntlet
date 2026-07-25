"""Surface-form constraint checking (gauntlet/scoring/constraints.py)."""
from __future__ import annotations

import pytest

from gauntlet.scoring.constraints import (
    UnknownConstraint,
    check_constraints,
)


def test_no_constraints_is_always_satisfied():
    assert check_constraints("import os\n", []) == []


def test_no_imports_detects_both_import_forms():
    assert check_constraints("import os\n", ["no-imports"]) == ["no-imports"]
    assert check_constraints("from os import sep\n", ["no-imports"]) == ["no-imports"]
    assert check_constraints("def f():\n    return 1\n", ["no-imports"]) == []


def test_no_sorted_catches_bare_and_method_calls():
    assert check_constraints("def f(x):\n    return sorted(x)\n", ["no-sorted"]) == ["no-sorted"]
    # .sort() is a different constraint; no-sorted alone must not flag it.
    assert check_constraints("def f(x):\n    x.sort()\n    return x\n", ["no-sorted"]) == []
    assert check_constraints("def f(x):\n    x.sort()\n    return x\n",
                             ["no-builtin-sort"]) == ["no-builtin-sort"]


def test_single_expression_allows_docstring_but_not_extra_statements():
    ok = 'def f(x):\n    """Doc."""\n    return x + 1\n'
    assert check_constraints(ok, ["single-expression"]) == []

    multi = "def f(x):\n    y = x + 1\n    return y\n"
    assert check_constraints(multi, ["single-expression"]) == ["single-expression"]


def test_must_use_generator_accepts_yield_and_genexp():
    assert check_constraints("def f(x):\n    yield x\n", ["must-use-generator"]) == []
    assert check_constraints("def f(x):\n    return (i for i in x)\n",
                             ["must-use-generator"]) == []
    assert check_constraints("def f(x):\n    return [i for i in x]\n",
                             ["must-use-generator"]) == ["must-use-generator"]


def test_no_loops_and_no_recursion():
    assert check_constraints("def f(x):\n    for i in x:\n        pass\n",
                             ["no-loops"]) == ["no-loops"]
    rec = "def f(n):\n    return 1 if n <= 0 else f(n - 1)\n"
    assert check_constraints(rec, ["no-recursion"]) == ["no-recursion"]
    assert check_constraints("def f(n):\n    return n\n", ["no-recursion"]) == []


def test_multiple_violations_are_all_reported():
    src = "import os\ndef f(x):\n    return sorted(x)\n"
    assert sorted(check_constraints(src, ["no-imports", "no-sorted"])) == [
        "no-imports", "no-sorted",
    ]


def test_unparseable_source_reports_no_constraint_violation():
    # That is a syntax_error, attributed by the execution scorer. Reporting it
    # here too would double-count one failure as two different kinds.
    assert check_constraints("def f(:\n", ["no-imports"]) == []


def test_unknown_constraint_is_loud():
    with pytest.raises(UnknownConstraint):
        check_constraints("def f():\n    return 1\n", ["no-telepathy"])
