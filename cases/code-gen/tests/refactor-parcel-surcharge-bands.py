# GAUNTLET-CANARY-8d58d7b1616b
def check(ns):
    f = ns.get("parcel_surcharge")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(0.5, "local", False) == 0),
        t(lambda: f(3, "domestic", False) == 5),
        t(lambda: f(2, "local", True) == 6),
        t(lambda: f(10, "intl", False) == 15),
        t(lambda: f(1, "intl", True) == 12),
        t(lambda: f(0, "local", False) == -1),
        t(lambda: f(100, "xx", True) == -1),
        t(lambda: f(5, "intl", False) == 10),
        t(lambda: f(25, "local", True) == 19),
        t(lambda: f(5.1, "intl", True) == 19),
    ]
