# GAUNTLET-CANARY-521105824d78
def check(ns):
    f = ns.get("clamp_inplace")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def after(vals, lo, hi):
        v = list(vals)
        ret = f(v, lo, hi)
        return ret, v
    def same_obj(vals, lo, hi, expected):
        v = list(vals)
        oid = id(v)
        ret = f(v, lo, hi)
        return ret is None and id(v) == oid and v == expected
    return [
        t(lambda: after([1, 5, 9], 0, 10)[0] is None),
        t(lambda: after([1, 5, 9], 0, 10)[1] == [1, 5, 9]),
        t(lambda: same_obj([0, 5, 20], 1, 10, [1, 5, 10])),
        t(lambda: after([], 0, 5) == (None, [])),
        t(lambda: after([-3, -1], 0, 10)[1] == [0, 0]),
        t(lambda: after([100, 50], 0, 10)[1] == [10, 10]),
        t(lambda: after([-5, 3, 99], 0, 10)[1] == [0, 3, 10]),
        t(lambda: after([7], 7, 7)[1] == [7]),
        t(lambda: after([6, 7, 8], 7, 7)[1] == [7, 7, 7]),
        t(lambda: same_obj([-100, 0, 100], -10, 10, [-10, 0, 10])),
    ]
