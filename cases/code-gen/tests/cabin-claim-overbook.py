# GAUNTLET-CANARY-3d44a13e8301
def check(ns):
    f = ns.get("claim_cabin_slots")
    E = ns.get("OverbookError")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def raises(exc, *a):
        try:
            f(*a)
            return False
        except exc:
            return True
        except Exception:
            return False
    return [
        t(lambda: f({"A": 10}, [("A", 3)]) == {"A": 7}),
        t(lambda: f({"A": 5, "B": 4}, [("A", 1), ("B", 2)]) == {"A": 4, "B": 2}),
        t(lambda: f({"A": 3}, []) == {"A": 3}),
        t(lambda: raises(TypeError, None, [])),
        t(lambda: raises(TypeError, {"A": 2}, "A")),
        t(lambda: raises(KeyError, {"A": 2}, [("B", 1)])),
        t(lambda: raises(ValueError, {"A": 2}, [("A", 0)])),
        t(lambda: f({"A": 4}, [("A", 4)]) == {"A": 0}),
        t(lambda: isinstance(E, type) and issubclass(E, Exception) and raises(E, {"A": 2}, [("A", 3)])),
        t(lambda: (lambda m: (f(m, [("A", 1)]), m == {"A": 5})[1])({"A": 5})),
    ]
