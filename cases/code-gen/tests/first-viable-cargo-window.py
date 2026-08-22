# GAUNTLET-CANARY-cee1e690cbd7
def check(ns):
    f = ns.get("first_viable_window")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([1, 2, 3], 6, 3) == 0),
        t(lambda: f([3], 3, 1) == 0),
        t(lambda: f([2, 2, 2, 2], 4, 2) == 0),
        t(lambda: f([9, 9, 9], 5, 1) == -1),
        t(lambda: f([], 10, 1) == -1),
        t(lambda: f([1, 2, 3], 10, 0) == -1),
        t(lambda: f([1, 2, 3], 10, 5) == -1),
        t(lambda: f([5, 1, 1], 3, 2) == 1),
        t(lambda: f([4, 1, 1, 1], 3, 3) == 1),
        t(lambda: f([1] * 200000, 1000, 1000) == 0),
    ]
