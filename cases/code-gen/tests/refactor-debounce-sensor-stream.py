# GAUNTLET-CANARY-3860a8def8ea
def check(ns):
    f = ns.get("debounce_sensor_stream")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([1, 1, 1], 3, 0) == [(2, "enter", 1)]),
        t(lambda: f([1, 2, 2, 2], 3, 0) == [(3, "enter", 2)]),
        t(lambda: f([5], 1, 0) == [(0, "enter", 5)]),
        t(lambda: f([], 2, 0) == []),
        t(lambda: f([1, 1, 1, 2, 2, 2], 3, 0) == [(2, "enter", 1), (5, "enter", 2)]),
        t(lambda: f(None, 2, 0) is None),
        t(lambda: f([1, 1, 1], 0, 0) is None),
        t(lambda: f([1, 1, 1, 2, 2, 2], 3, 2) == [(2, "enter", 1)]),
        t(lambda: f([0, 0, 1, 1, 1], 2, 1) == [(1, "enter", 0), (4, "enter", 1)]),
        t(lambda: f([2, 2, 3, 3, 3, 2, 2, 2], 3, 1) == [(4, "enter", 3)]),
    ]
