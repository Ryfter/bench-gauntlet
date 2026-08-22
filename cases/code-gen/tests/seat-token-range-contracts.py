# GAUNTLET-CANARY-5abd29a798df
def check(ns):
    f = ns.get("parse_seat_token")
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
        t(lambda: f("R12-C03") == (12, 3)),
        t(lambda: f("R1-C1") == (1, 1)),
        t(lambda: f("R99-C50") == (99, 50)),
        t(lambda: f("R01-C09") == (1, 9)),
        t(lambda: raises(TypeError, 12)),
        t(lambda: raises(TypeError, None)),
        t(lambda: raises(ValueError, "R12C03")),
        t(lambda: raises(ValueError, "R0-C1")),
        t(lambda: raises(ValueError, "R100-C1")),
        t(lambda: raises(ValueError, "R1-C51")),
    ]
