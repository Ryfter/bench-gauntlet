"""Surface-form constraint checking for code-gen cases (DS-1000 style).

Some cases state a hard constraint on the *shape* of the answer, not just its
behaviour: "no imports", "must be a single expression", "must use a generator",
"must not call sorted()". Checking these by AST lets the scorecard separate two
very different failures that a single correctness number conflates:

  - the model cannot solve the problem            -> capability gap
  - the model solved it but ignored the instruction -> instruction-following gap

That distinction is the whole point of the selective-offload principle
(D-2026-06-30c): scaffolding fixes the second and does nothing for the first.
The seed doc flags the same confound in the summarize battery, where a rubric
demanding "exactly 3 bullets" measured instruction-following as much as
summarisation.

Constraints are declared per-case and evaluated against the candidate's parsed
AST. A violation is reported separately from functional correctness — never
silently folded into the score.
"""
from __future__ import annotations

import ast

# Declarative constraint names usable in a battery YAML `constraints:` list.
CONSTRAINTS = (
    "no-imports",
    "no-sorted",
    "no-builtin-sort",
    "single-expression",
    "must-use-generator",
    "must-use-comprehension",
    "no-loops",
    "no-recursion",
    "no-global-state",
)


class UnknownConstraint(ValueError):
    """A battery names a constraint this module does not implement."""


def _calls_named(tree: ast.AST, names: set[str]) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in names:
                return True
            if isinstance(fn, ast.Attribute) and fn.attr in names:
                return True
    return False


def _function_defs(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _check_one(name: str, tree: ast.AST) -> bool:
    """True == the constraint is satisfied."""
    if name == "no-imports":
        return not any(isinstance(n, (ast.Import, ast.ImportFrom))
                       for n in ast.walk(tree))

    if name == "no-sorted":
        return not _calls_named(tree, {"sorted"})

    if name == "no-builtin-sort":
        return not _calls_named(tree, {"sorted", "sort"})

    if name == "single-expression":
        # Exactly one function whose body is a lone `return <expr>`.
        fns = _function_defs(tree)
        if len(fns) != 1:
            return False
        body = [n for n in fns[0].body
                if not (isinstance(n, ast.Expr)
                        and isinstance(n.value, ast.Constant)
                        and isinstance(n.value.value, str))]  # drop docstring
        return len(body) == 1 and isinstance(body[0], ast.Return)

    if name == "must-use-generator":
        # A yield anywhere, or a generator expression.
        return any(isinstance(n, (ast.Yield, ast.YieldFrom, ast.GeneratorExp))
                   for n in ast.walk(tree))

    if name == "must-use-comprehension":
        return any(isinstance(n, (ast.ListComp, ast.SetComp, ast.DictComp,
                                  ast.GeneratorExp))
                   for n in ast.walk(tree))

    if name == "no-loops":
        return not any(isinstance(n, (ast.For, ast.While, ast.AsyncFor))
                       for n in ast.walk(tree))

    if name == "no-recursion":
        # Direct self-reference only; mutual recursion is out of scope and the
        # cases that use this constraint are written to not need it.
        for fn in _function_defs(tree):
            if _calls_named(fn, {fn.name}):
                return False
        return True

    if name == "no-global-state":
        return not any(isinstance(n, (ast.Global, ast.Nonlocal))
                       for n in ast.walk(tree))

    raise UnknownConstraint(name)


def check_constraints(source: str, constraints: list[str]) -> list[str]:
    """Return the names of every violated constraint (empty == all satisfied).

    A source that does not parse violates nothing here: that is a syntax_error,
    reported by the execution scorer, and double-counting it as a constraint
    violation would misattribute the failure.
    """
    if not constraints:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    for name in constraints:
        if name not in CONSTRAINTS:
            raise UnknownConstraint(name)

    return [name for name in constraints if not _check_one(name, tree)]
