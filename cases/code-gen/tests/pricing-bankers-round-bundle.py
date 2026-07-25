# GAUNTLET-CANARY-dfd1d1225653
def check(ns):
    f = ns.get("round_money")
    g = ns.get("price_bundle")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(1.234, 2) == 1.23),
        t(lambda: f(1.236, 2) == 1.24),
        t(lambda: g([(10.0, 3, 0)], 10) == (30.0, 3.0, 33.0)),
        t(lambda: g([], 5) == (0.0, 0.0, 0.0)),
        t(lambda: g([(19.99, 1, 10)], 0) == (17.99, 0.0, 17.99)),
        t(lambda: g([(50.0, 2, 100)], 8) == (0.0, 0.0, 0.0)),
        t(lambda: f(1.225, 2) == 1.22),
        t(lambda: f(2.5, 0) == 2.0 and f(1.5, 0) == 2.0 and f(0.5, 0) == 0.0),
        t(lambda: g([(10.125, 1, 0)], 0) == (10.12, 0.0, 10.12)),
        t(lambda: f(-1.225, 2) == -1.22 and g([(10.125, 2, 0), (1.0, 1, 0)], 5) == (21.25, 1.06, 22.31)),
    ]
