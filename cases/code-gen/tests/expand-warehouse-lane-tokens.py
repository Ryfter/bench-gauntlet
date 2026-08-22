# GAUNTLET-CANARY-8e557caf8a58
def check(ns):
    f = ns.get("expand_lane_tokens")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("A1,B2") == ["A1", "B2"]),
        t(lambda: f("C5") == ["C5"]),
        t(lambda: f("A1-A3") == ["A1", "A2", "A3"]),
        t(lambda: f("") == []),
        t(lambda: f("A1,,B2") == ["A1", "B2"]),
        t(lambda: f(" A1 - A2 , B3 ") == ["A1", "A2", "B3"]),
        t(lambda: f("A3-A1") == ["A3", "A2", "A1"]),
        t(lambda: f("A1-A1") == ["A1"]),
        t(lambda: f("Z9-Z11") == ["Z9", "Z10", "Z11"]),
        t(lambda: f("B2-B4,B3") == ["B2", "B3", "B4", "B3"]),
    ]
