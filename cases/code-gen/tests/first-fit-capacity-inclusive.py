def check(ns):
    f = ns.get("first_fit_assign")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([5], 10) == [0]),
        t(lambda: f([3, 3], 10) == [0, 0]),
        t(lambda: f([6, 6], 10) == [0, 1]),
        t(lambda: f([], 10) == []),
        t(lambda: f([7, 4], 10) == [0, 1]),
        t(lambda: f([10], 10) == [0]),
        t(lambda: f([7, 3], 10) == [0, 0]),
        t(lambda: f([5, 5, 5], 10) == [0, 0, 1]),
        t(lambda: f([1, 1, 1, 1], 3) == [0, 0, 0, 1]),
        t(lambda: f([4, 4, 2, 2, 2], 6) == [0, 1, 0, 1, 2]),
    ]
