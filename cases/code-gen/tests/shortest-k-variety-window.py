def check(ns):
    f = ns.get("shortest_k_variety")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    large = [i % 40 for i in range(250000)]
    return [
        t(lambda: f([1, 2, 3], 3) == 3),
        t(lambda: f([1, 2, 3], 2) == 2),
        t(lambda: f([1, 1, 1], 1) == 1),
        t(lambda: f([1, 1, 1], 2) == 0),
        t(lambda: f([], 1) == 0),
        t(lambda: f([1, 2, 3, 4, 5], 6) == 0),
        t(lambda: f([1, 2, 1, 2, 3], 3) == 3),
        t(lambda: f([7, 7, 7, 1, 2, 3, 7], 3) == 3),
        t(lambda: f([0, 1, 0, 1, 2, 1, 0], 3) == 3),
        t(lambda: f(large, 40) == 40),
    ]
