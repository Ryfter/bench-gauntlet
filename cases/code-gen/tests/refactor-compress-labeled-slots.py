def check(ns):
    f = ns.get("compress_slots")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([]) == []),
        t(lambda: f(None) == []),
        t(lambda: f([(1, 3, "a")]) == [(1, 3, "a")]),
        t(lambda: f([(1, 4, "a"), (2, 5, "a")]) == [(1, 5, "a")]),
        t(lambda: f([(1, 3, "a"), (3, 5, "b")]) == [(1, 3, "a"), (3, 5, "b")]),
        t(lambda: f([(5, 7, "x"), (1, 3, "x")]) == [(1, 3, "x"), (5, 7, "x")]),
        t(lambda: f([(1, 3, "a"), (3, 5, "a")]) == [(1, 5, "a")]),
        t(lambda: f([None, (1, 2, "z"), (2, 4, "z")]) == [(1, 4, "z")]),
        t(lambda: f([(1, 10, "a"), (2, 3, "a"), (8, 12, "a")]) == [(1, 12, "a")]),
        t(lambda: f([(1, 3, "a"), (2, 4, "b"), (5, 5, "a")]) == [(1, 3, "a"), (2, 4, "b")]),
    ]
