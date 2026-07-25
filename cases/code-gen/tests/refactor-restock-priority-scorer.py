def check(ns):
    f = ns.get("restock_priority")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(10, 5, 20, 100, False) == 32),
        t(lambda: f(3, 15, 5, 100, False) == 65),
        t(lambda: f(5, 2, 2, 10, True) == 57),
        t(lambda: f(0, 0, 10, 10, False) == 50),
        t(lambda: f(-1, 1, 1, 1, False) == -1),
        t(lambda: f(None, 1, 1, 1, False) == -1),
        t(lambda: f(8, 0, 100, 100, False) == 0),
        t(lambda: f(7, 0, 100, 100, False) == 25),
        t(lambda: f(0, 0, 10, 10, True) == 75),
        t(lambda: f(1, 25, 0, 50, True) == 100),
    ]
