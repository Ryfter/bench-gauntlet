# GAUNTLET-CANARY-3c1694b1ea21
def check(ns):
    f = ns.get("window_span")
    ChronologyError = ns.get("ChronologyError")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def exact(exc, thunk):
        try:
            thunk()
            return False
        except Exception as e:
            return type(e) is exc
    ev = [{"t": 10, "label": "a"}, {"t": 12, "label": "b"}, {"t": 15, "label": "c"}]
    return [
        t(lambda: f(ev, 0, 2) == ("a,b,c", 5)),
        t(lambda: f(ev, 1, 1) == ("b", 0)),
        t(lambda: f([{"t": 0, "label": "solo"}], 0, 0) == ("solo", 0)),
        t(lambda: exact(ValueError, lambda: f(ev, 2, 0))),
        t(lambda: exact(IndexError, lambda: f(ev, -1, 1))),
        t(lambda: exact(IndexError, lambda: f(ev, 0, 9))),
        t(lambda: exact(KeyError, lambda: f([{"t": 1}], 0, 0))),
        t(lambda: isinstance(ChronologyError, type) and exact(ChronologyError, lambda: f([{"t": 5, "label": "x"}, {"t": 3, "label": "y"}], 0, 1))),
        t(lambda: exact(TypeError, lambda: f(ev, True, 1))),
        t(lambda: exact(TypeError, lambda: f([{"t": 1, "label": "ok"}, "nope"], 0, 1))),
    ]
