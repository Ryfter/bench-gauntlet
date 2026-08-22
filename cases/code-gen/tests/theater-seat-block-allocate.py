# GAUNTLET-CANARY-a2b3e57055bb
def check(ns):
    f = ns.get("fits_block")
    g = ns.get("allocate_seats")
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
        t(lambda: f([False, False, False], 0, 2) is True),
        t(lambda: f([False, True, False], 0, 2) is False),
        t(lambda: g([False] * 5, [2, 2]) == [0, 2]),
        t(lambda: g([False, False, False], [1, 1]) == [0, 1]),
        t(lambda: g([], []) == []),
        t(lambda: g([True, True, True], [1]) == [None]),
        t(lambda: f([False, False], 1, 2) is False),
        t(lambda: g([False, False], [2]) == [0]),
        t(lambda: g([True, False, False], [2]) == [1]),
        t(lambda: raises_ve(lambda: f([False], -1, 1)) and raises_ve(lambda: f([False], 0, 0)) and raises_ve(lambda: g([False], [0])) and (lambda r: g(r, [1]) == [0] and r == [False, True])([False, True])),
    ]
