# GAUNTLET-CANARY-9b1c5b542cf8
def check(ns):
    f = ns.get("to_grams")
    g = ns.get("total_grams")
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
        t(lambda: f(5, "g") == 5),
        t(lambda: f(2, "kg") == 2000),
        t(lambda: f(3, "oz") == 84),
        t(lambda: g([(1, "kg"), (500, "g")]) == 1500),
        t(lambda: g([]) == 0),
        t(lambda: f(0, "oz") == 0),
        t(lambda: f(2500, "mg") == 2),
        t(lambda: f(999, "mg") == 0),
        t(lambda: raises_ve(lambda: f(-1, "g"))),
        t(lambda: raises_ve(lambda: f(1, "lb"))),
    ]
