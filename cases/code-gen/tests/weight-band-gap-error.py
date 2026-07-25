def check(ns):
    f = ns.get("rate_for_weight")
    E = ns.get("BandGapError")
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
    bands = [{"lo": 0, "hi": 5, "rate": 10}, {"lo": 5, "hi": 10, "rate": 20}]
    gapped = [{"lo": 0, "hi": 2, "rate": 1}, {"lo": 4, "hi": 6, "rate": 2}]
    return [
        t(lambda: f(0, bands) == 10),
        t(lambda: f(4.9, bands) == 10),
        t(lambda: f(5, bands) == 20),
        t(lambda: f(9.99, bands) == 20),
        t(lambda: raises(TypeError, "3", bands)),
        t(lambda: raises(TypeError, 3, {"lo": 0})),
        t(lambda: raises(ValueError, -1, bands)),
        t(lambda: raises(KeyError, 1, [{"lo": 0, "hi": 5}])),
        t(lambda: isinstance(E, type) and issubclass(E, Exception) and raises(E, 10, bands)),
        t(lambda: isinstance(E, type) and issubclass(E, Exception) and raises(E, 3, gapped)),
    ]
