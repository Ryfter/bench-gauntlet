# GAUNTLET-CANARY-c36bf722c2e7
def check(ns):
    f = ns.get("expand_seat_range")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("K9") == ["K9"]),
        t(lambda: f("A1-A3") == ["A1", "A2", "A3"]),
        t(lambda: f("C7-C7") == ["C7"]),
        t(lambda: f("B10-B12") == ["B10", "B11", "B12"]),
        t(lambda: f("M2-M5") == ["M2", "M3", "M4", "M5"]),
        t(lambda: f("A5-A2") == []),
        t(lambda: f("Z1-Z1") == ["Z1"]),
        t(lambda: f("A9-A11") == ["A9", "A10", "A11"]),
        t(lambda: f("A1-B3") == []),
        t(lambda: f("D3-E3") == []),
    ]
