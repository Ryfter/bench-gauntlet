def check(ns):
    f = ns.get("next_delay")
    g = ns.get("backoff_schedule")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def raises_ve(fn):
        try:
            fn()
            return False
        except ValueError:
            return True
        except Exception:
            return False
    return [
        t(lambda: f(0, 100, 1000, 0) == 100),
        t(lambda: f(1, 100, 1000, 0) == 200),
        t(lambda: f(4, 100, 1000, 0) == 1000),
        t(lambda: g(1, 50, 500, 0) == [50]),
        t(lambda: g(0, 100, 1000, 0) == []),
        t(lambda: f(0, 100, 1000, 8) == 99),
        t(lambda: f(0, 5, 1000, 20) == 0),
        t(lambda: g(3, 100, 1000, 0) == [100, 197, 394]),
        t(lambda: f(0, 0, 100, 5) == 0),
        t(lambda: raises_ve(lambda: f(-1, 1, 1, 0)) and raises_ve(lambda: g(-1, 1, 1, 0))),
    ]
