# GAUNTLET-CANARY-d9ab6653ca08
def check(ns):
    f = ns.get("apply_stock_delta")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def raises(exc, *a):
        try:
            f(*a)
            return False
        except exc:
            return True
        except Exception:
            return False
    return [
        t(lambda: f({"a": 5}, {"a": -2}) == {"a": 3}),
        t(lambda: f({"a": 5, "b": 1}, {"b": 4}) == {"a": 5, "b": 5}),
        t(lambda: f({"x": 3}, {}) == {"x": 3}),
        t(lambda: f({"x": 2}, {"x": 7}) == {"x": 9}),
        t(lambda: raises(TypeError, [1], {})),
        t(lambda: raises(TypeError, {}, "nope")),
        t(lambda: raises(TypeError, {"a": 1.5}, {"a": 1})),
        t(lambda: f({"x": 2}, {"x": -2}) == {"x": 0}),
        t(lambda: raises(KeyError, {"a": 1}, {"b": 1})),
        t(lambda: (lambda s: (f(s, {"a": 1}), s == {"a": 5})[1])({"a": 5})),
    ]
