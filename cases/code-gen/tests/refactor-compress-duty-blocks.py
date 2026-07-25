def check(ns):
    f = ns.get("compress_duty_blocks")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([(1, 3, "a"), (3, 5, "a")], 0) == [(1, 5, "a")]),
        t(lambda: f([(1, 2, "a"), (2, 3, "b")], 5) == [(1, 2, "a"), (2, 3, "b")]),
        t(lambda: f([], 2) == []),
        t(lambda: f([(1, 3, "a"), (5, 6, "a")], 1) == [(1, 3, "a"), (5, 6, "a")]),
        t(lambda: f([(1, 1, "a"), (2, 4, "a")], 0) == [(2, 4, "a")]),
        t(lambda: f([(1, 3, "a"), (4, 6, "a")], 1) == [(1, 6, "a")]),
        t(lambda: f([(5, 6, "x"), (1, 2, "x")], 10) == [(1, 6, "x")]),
        t(lambda: f([(1, 5, "a"), (2, 3, "a")], 0) == [(1, 5, "a")]),
        t(lambda: f(None, 1) is None),
        t(lambda: f([(1, 3, "a"), (4, 5, "a")], 1) == [(1, 5, "a")]),
    ]
