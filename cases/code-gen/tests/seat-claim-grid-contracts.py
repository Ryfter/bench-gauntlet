# GAUNTLET-CANARY-9a54e361ae78
def check(ns):
    f = ns.get("claim_seat")
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
    return [
        t(lambda: f([[None, ""]], 0, 0, "Ada") is True),
        t(lambda: (lambda g: f(g, 0, 1, "Bea") is True and g[0][1] == "Bea")([[None, ""]])),
        t(lambda: (lambda g: f(g, 0, 0, "Cy") is False and g[0][0] == "Cy")([["Cy"]])),
        t(lambda: exact(ValueError, lambda: f([["Dee"]], 0, 0, "Ed"))),
        t(lambda: exact(TypeError, lambda: f([[None]], 0, 0, 9))),
        t(lambda: exact(ValueError, lambda: f([[None]], 0, 0, ""))),
        t(lambda: exact(IndexError, lambda: f([[None]], 1, 0, "Zo"))),
        t(lambda: exact(IndexError, lambda: f([[None, None]], -1, 0, "Zo"))),
        t(lambda: exact(TypeError, lambda: f([[None], [None]], True, 0, "Zo"))),
        t(lambda: exact(IndexError, lambda: f([], 0, 0, "Zo"))),
    ]
