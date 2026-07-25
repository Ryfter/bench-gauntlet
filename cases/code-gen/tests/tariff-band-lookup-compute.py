def check(ns):
    f = ns.get("lookup_band")
    g = ns.get("compute_tariff")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    B = [{"limit": 10, "rate": 1.5}, {"limit": 50, "rate": 1.2}, {"limit": None, "rate": 0.9}]
    B2 = [{"limit": 5, "rate": 2.0}, {"limit": 10, "rate": 1.0}]
    return [
        t(lambda: f(B, 5) == 1.5),
        t(lambda: g(B, 5) == 7.5),
        t(lambda: f(B, 0) == 1.5 and g(B, 0) == 0.0),
        t(lambda: f(B, 10) == 1.5),
        t(lambda: f(B, 50) == 1.2),
        t(lambda: f(B, 51) == 0.9),
        t(lambda: g(B, 100) == 90.0),
        t(lambda: f(B, -3) is None and g(B, -3) is None),
        t(lambda: f([], 5) is None and f(B2, 11) is None and g(B2, 11) is None),
        t(lambda: g(B, 10) == 15.0 and g(B, 50) == 60.0),
    ]
