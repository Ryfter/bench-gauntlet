def check(ns):
    f = ns.get("half_open_hits")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([2, 3, 4], 2, 5) == 3),
        t(lambda: f([1, 2, 3], 1, 4) == 3),
        t(lambda: f([], 0, 10) == 0),
        t(lambda: f([7], 5, 10) == 1),
        t(lambda: f([5], 5, 10) == 1),
        t(lambda: f([10], 5, 10) == 0),
        t(lambda: f([10, 10, 9], 5, 10) == 1),
        t(lambda: f([-3, -1, 0], -2, 0) == 1),
        t(lambda: f([1, 2, 3], 3, 1) == 0),
        t(lambda: f(list(range(101)), 0, 100) == 100),
    ]
