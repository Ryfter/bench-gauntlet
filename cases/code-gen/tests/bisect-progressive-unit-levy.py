def check(ns):
    f = ns.get("progressive_levy")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(0, [100, 500], [1, 2, 3]) == 0),
        t(lambda: f(50, [100, 500], [1, 2, 3]) == 50),
        t(lambda: f(100, [100, 500], [1, 2, 3]) == 100),
        t(lambda: f(101, [100, 500], [1, 2, 3]) == 102),
        t(lambda: f(150, [100, 500], [1, 2, 3]) == 200),
        t(lambda: f(500, [100, 500], [1, 2, 3]) == 900),
        t(lambda: f(501, [100, 500], [1, 2, 3]) == 903),
        t(lambda: f(10, [], [7]) == 70),
        t(lambda: f(250, [100], [0, 4]) == 600),
        t(lambda: f(1000, [100, 200, 400], [1, 1, 2, 5]) == 3600),
    ]
