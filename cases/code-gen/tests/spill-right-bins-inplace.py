# GAUNTLET-CANARY-235a1fc9345f
def check(ns):
    f = ns.get("spill_right_inplace")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def run(src, lim):
        v = list(src)
        ret = f(v, lim)
        return ret, v
    def same(src, lim, exp):
        v = list(src)
        oid = id(v)
        ret = f(v, lim)
        return ret is None and id(v) == oid and v == exp
    return [
        t(lambda: run([3, 3], 5)[0] is None),
        t(lambda: run([3, 3], 5)[1] == [3, 3]),
        t(lambda: same([8, 1], 5, [5, 4])),
        t(lambda: run([], 5) == (None, [])),
        t(lambda: run([4], 5)[1] == [4]),
        t(lambda: run([20, 0, 0], 5)[1] == [5, 5, 10]),
        t(lambda: run([8, 8], 5)[1] == [5, 11]),
        t(lambda: run([12], 5)[1] == [12]),
        t(lambda: run([0, 0, 9], 5)[1] == [0, 0, 9]),
        t(lambda: run([-2, 10, 0], 5)[1] == [-2, 5, 5]),
    ]
