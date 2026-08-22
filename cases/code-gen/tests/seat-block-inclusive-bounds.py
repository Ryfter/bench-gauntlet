# GAUNTLET-CANARY-3d2d3a5ee758
def check(ns):
    f = ns.get("seat_in_block")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(5, 1, 10) is True),
        t(lambda: f(0, 1, 10) is False),
        t(lambda: f(11, 1, 10) is False),
        t(lambda: f(2, 3, 8) is False),
        t(lambda: f(1, 1, 10) is True),
        t(lambda: f(10, 1, 10) is True),
        t(lambda: f(7, 7, 7) is True),
        t(lambda: f(-3, -5, -1) is True),
        t(lambda: f(-5, -5, -1) is True),
        t(lambda: f(-1, -5, -1) is True),
    ]
