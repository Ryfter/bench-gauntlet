# GAUNTLET-CANARY-4be359869a7a
def check(ns):
    f = ns.get("max_stable_span")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([], 5) == 0),
        t(lambda: f([7], 0) == 1),
        t(lambda: f([1, 2, 3], 2) == 3),
        t(lambda: f([1, 2, 3], -1) == 0),
        t(lambda: f([5, 5, 5, 5], 0) == 4),
        t(lambda: f([10, 1, 2, 3], 2) == 3),
        t(lambda: f([3, 1, 5], 2) == 2),
        t(lambda: f([5, 2, 8], 3) == 2),
        t(lambda: f([10, 5, 6, 15], 5) == 3),
        t(lambda: f(list(range(200000)), 1000) == 1001),
    ]
