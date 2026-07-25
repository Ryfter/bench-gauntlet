def check(ns):
    f = ns.get("debounce_ready")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([1], 1) == 0),
        t(lambda: f([0, 1, 0], 1) == 1),
        t(lambda: f([], 2) == -1),
        t(lambda: f([1, 1], 1) == 0),
        t(lambda: f([0, 0, 0], 2) == -1),
        t(lambda: f([1, 1, 1], 3) == 2),
        t(lambda: f([1, 0, 1, 1], 2) == 3),
        t(lambda: f([1, 1, 0, 1, 1, 1], 3) == 5),
        t(lambda: f([1, 1, 1], 0) == -1),
        t(lambda: f([1] * 100 + [0] + [1] * 5, 5) == 4),
    ]
