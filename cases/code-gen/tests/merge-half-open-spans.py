def check(ns):
    f = ns.get("merge_half_open")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([(1, 3), (5, 7)]) == [(1, 3), (5, 7)]),
        t(lambda: f([(1, 5), (3, 7)]) == [(1, 7)]),
        t(lambda: f([]) == []),
        t(lambda: f([(10, 20)]) == [(10, 20)]),
        t(lambda: f([(2, 2), (5, 1)]) == []),
        t(lambda: f([(1, 3), (3, 5)]) == [(1, 5)]),
        t(lambda: f([(0, 1), (-2, 0)]) == [(-2, 1)]),
        t(lambda: f([(1, 10), (2, 3), (4, 5), (12, 15)]) == [(1, 10), (12, 15)]),
        t(lambda: f([(8, 9), (1, 2), (2, 8)]) == [(1, 9)]),
        t(lambda: f([(-1000, -500), (-500, 0), (0, 1000), (2000, 2001)]) == [(-1000, 1000), (2000, 2001)]),
    ]
