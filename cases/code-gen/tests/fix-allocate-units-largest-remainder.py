def check(ns):
    f = ns.get("allocate_units")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def raises_value_error(call):
        try:
            call()
            return False
        except ValueError:
            return True
        except Exception:
            return False
    return [
        t(lambda: f(5, [2, 3]) == [2, 3]),
        t(lambda: f(0, [4, 6]) == [0, 0]),
        t(lambda: f(10, [1, 0]) == [10, 0]),
        t(lambda: f(7, []) == []),
        t(lambda: f(9, [0, 0, 0]) == [0, 0, 0]),
        t(lambda: f(10, [1, 1, 1]) == [4, 3, 3]),
        t(lambda: f(1, [1, 1]) == [1, 0]),
        t(lambda: f(5, [1, 1, 1]) == [2, 2, 1]),
        t(lambda: raises_value_error(lambda: f(-1, [1, 2]))),
        t(lambda: raises_value_error(lambda: f(3, [1, -1]))),
    ]
