# GAUNTLET-CANARY-22cec13d1c1f
def check(ns):
    f = ns.get("zero_sum_slice_count")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    n_large = 200000
    return [
        t(lambda: f([]) == 0),
        t(lambda: f([1, -1]) == 1),
        t(lambda: f([5]) == 0),
        t(lambda: f([0]) == 1),
        t(lambda: f([1, 2, -3]) == 1),
        t(lambda: f([0, 0]) == 3),
        t(lambda: f([1, -1, 1, -1]) == 4),
        t(lambda: f([0, 1, 0]) == 2),
        t(lambda: f([3, 1, -1, -3, 2, -2]) == 4),
        t(lambda: f([0] * n_large) == n_large * (n_large + 1) // 2),
    ]
