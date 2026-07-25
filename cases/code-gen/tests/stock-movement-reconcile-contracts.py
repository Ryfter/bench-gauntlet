def check(ns):
    f = ns.get("reconcile_stock")
    StockCorruptError = ns.get("StockCorruptError")
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
        t(lambda: f({"a": 10}, [("a", -3)]) == {"a": 7}),
        t(lambda: f({"a": 5, "b": 2}, [("a", 1), ("b", -2)]) == {"a": 6, "b": 0}),
        t(lambda: f({"x": 4}, []) == {"x": 4}),
        t(lambda: exact(KeyError, lambda: f({"a": 1}, [("z", 1)]))),
        t(lambda: exact(TypeError, lambda: f([1], []))),
        t(lambda: exact(ValueError, lambda: f({"a": 5}, [("a", -10), ("a", 100)]))),
        t(lambda: isinstance(StockCorruptError, type) and exact(StockCorruptError, lambda: f({"a": -1}, []))),
        t(lambda: exact(TypeError, lambda: f({"a": 5}, [("a", True)]))),
        t(lambda: exact(TypeError, lambda: f({"a": True}, []))),
        t(lambda: exact(TypeError, lambda: f({"a": 1}, [["a", 1]]))),
    ]
