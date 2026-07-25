def check(ns):
    f = ns.get("step_gaps")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    import types
    return [
        t(lambda: list(f([1, 2, 4])) == [1, 2]),
        t(lambda: list(f([10, 10, 10])) == [0, 0]),
        t(lambda: list(f([3, 1])) == [-2]),
        t(lambda: list(f([])) == []),
        t(lambda: list(f([7])) == []),
        t(lambda: list(f([0, -5, -2])) == [-5, 3]),
        t(lambda: isinstance(f([1, 2]), types.GeneratorType)),
        t(lambda: not isinstance(f([1, 2, 3]), list)),
        t(lambda: (lambda g: next(g) == 1 and next(g) == 1)(f(list(range(10000))))),
        t(lambda: list(f([100, -100, 50])) == [-200, 150]),
    ]
