def check(ns):
    f = ns.get("max_span_under")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([2, 3, 1, 2, 4], 7) == 3),
        t(lambda: f([1, 1, 1, 1], 2) == 2),
        t(lambda: f([5], 5) == 1),
        t(lambda: f([5], 4) == 0),
        t(lambda: f([], 10) == 0),
        t(lambda: f([1, 2, 3, 4], 0) == 0),
        t(lambda: f([0, 0, 0, 0], 0) == 4),
        t(lambda: f([3, 0, 0, 3], 0) == 2),
        t(lambda: f([0, 0, 1, 0, 0, 0], 0) == 3),
        t(lambda: f([1] * 250000, 10000) == 10000),
    ]
