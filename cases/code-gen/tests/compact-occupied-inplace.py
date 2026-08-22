# GAUNTLET-CANARY-57d935468127
def check(ns):
    f = ns.get("compact_occupied_inplace")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def run(src):
        v = list(src)
        ret = f(v)
        return ret, v
    def same(src, exp):
        v = list(src)
        oid = id(v)
        ret = f(v)
        return ret is None and id(v) == oid and v == exp
    return [
        t(lambda: run(["A", "B"])[0] is None),
        t(lambda: run(["A", "B"])[1] == ["A", "B"]),
        t(lambda: run([]) == (None, [])),
        t(lambda: run([None, None])[1] == [None, None]),
        t(lambda: run([None])[1] == [None]),
        t(lambda: same(["X", None, "Y"], ["X", "Y", None])),
        t(lambda: run([None, "A", None, "B"])[1] == ["A", "B", None, None]),
        t(lambda: run([None, None, "A"])[1] == ["A", None, None]),
        t(lambda: run([None, "", None, 0, None])[1] == ["", 0, None, None, None]),
        t(lambda: same([None, "p", None, None, "q", None], ["p", "q", None, None, None, None])),
    ]
