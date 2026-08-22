# GAUNTLET-CANARY-6b9ddb2e8edb
def check(ns):
    f = ns.get("count_filled_slots")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(["a", "b", "c"]) == 3),
        t(lambda: f([]) == 0),
        t(lambda: f([None, None]) == 0),
        t(lambda: f(["x", None, "y"]) == 2),
        t(lambda: f(["", None, ""]) == 0),
        t(lambda: f([0]) == 1),
        t(lambda: f([False]) == 1),
        t(lambda: f([0, False, None, ""]) == 2),
        t(lambda: f([" "]) == 1),
        t(lambda: f(["  ", "", None, 1, False]) == 3),
    ]
