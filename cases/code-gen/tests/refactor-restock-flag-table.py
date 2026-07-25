# GAUNTLET-CANARY-e275639e0567
def check(ns):
    f = ns.get("restock_flag")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(10, 5) == "medium"),
        t(lambda: f(50, 5) == "low"),
        t(lambda: f(3, 1) == "critical"),
        t(lambda: f(0, 99) == "critical"),
        t(lambda: f(None, 0) == "unknown"),
        t(lambda: f(4, None) == "unknown"),
        t(lambda: f(-3, 2) == "bad"),
        t(lambda: f(5, 2) == "critical"),
        t(lambda: f(5, 8) == "medium"),
        t(lambda: f(21, 1) == "medium"),
    ]
