def check(ns):
    f = ns.get("bus_boarding")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(10, [3, 3, 3]) == 3),
        t(lambda: f(5, [2, 2]) == 2),
        t(lambda: f(10, []) == 0),
        t(lambda: f(0, [1, 2, 3]) == 0),
        t(lambda: f(5, [5]) == 1),
        t(lambda: f(5, [6, 1, 1]) == 2),
        t(lambda: f(10, [4, 7, 3, 6, 2]) == 3),
        t(lambda: f(3, [1, 1, 1, 1]) == 3),
        t(lambda: f(8, [8, 1]) == 1),
        t(lambda: f(20, [15, 10, 5, 5, 1]) == 2),
    ]
