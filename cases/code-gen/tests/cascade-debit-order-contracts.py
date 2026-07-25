def check(ns):
    f = ns.get("debit_cascade")
    ShortfallError = ns.get("ShortfallError")
    DuplicateOrderError = ns.get("DuplicateOrderError")
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
    L = [{"balance": 10}, {"balance": 5}, {"balance": 8}]
    return [
        t(lambda: f([{"balance": 10}, {"balance": 5}], [0, 1], 12) == [{"balance": 0}, {"balance": 3}]),
        t(lambda: f([{"balance": 4}, {"balance": 9}], [1], 3) == [{"balance": 4}, {"balance": 6}]),
        t(lambda: f([{"balance": 7}], [0], 7) == [{"balance": 0}]),
        t(lambda: exact(ValueError, lambda: f(L, [0], 0))),
        t(lambda: exact(IndexError, lambda: f(L, [], 1))),
        t(lambda: exact(IndexError, lambda: f(L, [3], 1))),
        t(lambda: exact(KeyError, lambda: f([{"bal": 1}], [0], 1))),
        t(lambda: isinstance(DuplicateOrderError, type) and exact(DuplicateOrderError, lambda: f(L, [0, 2, 0], 1))),
        t(lambda: isinstance(ShortfallError, type) and exact(ShortfallError, lambda: f([{"balance": 2}, {"balance": 2}], [0, 1], 5))),
        t(lambda: exact(TypeError, lambda: f([{"balance": 3}], [0], True))),
    ]
