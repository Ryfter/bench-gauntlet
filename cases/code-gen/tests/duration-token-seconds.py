def check(ns):
    f = ns.get("duration_to_seconds")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("30s") == 30),
        t(lambda: f("5m") == 300),
        t(lambda: f("1h") == 3600),
        t(lambda: f("1h30m") == 5400),
        t(lambda: f("90m") == 5400),
        t(lambda: f("1d2h3m4s") == 93784),
        t(lambda: f("0s") == 0),
        t(lambda: f("") == -1),
        t(lambda: f("30m1h") == -1),
        t(lambda: f("1h1h") == -1),
    ]
