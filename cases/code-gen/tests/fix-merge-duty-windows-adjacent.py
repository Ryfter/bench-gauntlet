# GAUNTLET-CANARY-0dd657b2f315
def check(ns):
    f = ns.get("merge_duty_windows")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([]) == []),
        t(lambda: f([(3, 8)]) == [(3, 8)]),
        t(lambda: f([(1, 2), (5, 9)]) == [(1, 2), (5, 9)]),
        t(lambda: f([(1, 5), (2, 3)]) == [(1, 5)]),
        t(lambda: f([(1, 4), (3, 7)]) == [(1, 7)]),
        t(lambda: f([(8, 3)]) == []),
        t(lambda: f([(4, 4), (1, 2)]) == [(1, 2)]),
        t(lambda: f([(0, 2), (2, 5)]) == [(0, 5)]),
        t(lambda: f([(1, 2), (4, 6), (2, 4)]) == [(1, 6)]),
        t(lambda: f([(10, 12), (0, 1), (1, 3), (9, 9)]) == [(0, 3), (10, 12)]),
    ]
