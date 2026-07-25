def check(ns):
    f = ns.get("first_rate_limit_hit")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([], 5, 10) == -1),
        t(lambda: f([1, 2, 3], 5, 100) == -1),
        t(lambda: f([10, 11, 12, 13], 2, 100) == 12),
        t(lambda: f([0, 100, 200], 1, 50) == -1),
        t(lambda: f([1, 2, 3], 5, 0) == -1),
        t(lambda: f([5], 0, 10) == 5),
        t(lambda: f([1, 1, 1, 1], 3, 1) == 1),
        t(lambda: f([0, 10, 20], 1, 10) == -1),
        t(lambda: f([0, 5, 10], 1, 5) == -1),
        t(lambda: f(list(range(200000)), 1000, 1000) == -1),
    ]
