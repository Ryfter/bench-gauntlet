# GAUNTLET-CANARY-62bbf4a742ce
def check(ns):
    f = ns.get("coalesce_ranges")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([]) == []),
        t(lambda: f([(5, 5)]) == []),
        t(lambda: f([(1, 3)]) == [(1, 3)]),
        t(lambda: f([(1, 4), (2, 3)]) == [(1, 4)]),
        t(lambda: f([(5, 6), (1, 2)]) == [(1, 2), (5, 6)]),
        t(lambda: f([(3, 4), (3, 4)]) == [(3, 4)]),
        t(lambda: f([(1, 2), (2, 3)]) == [(1, 3)]),
        t(lambda: f([(1, 5), (5, 5), (5, 8)]) == [(1, 8)]),
        t(lambda: f([(0, 1), (10, 11), (1, 10)]) == [(0, 11)]),
        t(lambda: f([(i, i + 1) for i in range(200000)]) == [(0, 200000)]),
    ]
