def check(ns):
    f = ns.get("token_bucket_accept")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(10, 0, [3, 3]) == [True, True]),
        t(lambda: f(5, 0, [2, 4]) == [True, False]),
        t(lambda: f(10, 0, []) == []),
        t(lambda: f(6, 0, [1, 1, 1]) == [True, True, True]),
        t(lambda: f(5, 5, [4, 4]) == [True, True]),
        t(lambda: f(5, 0, [5]) == [True]),
        t(lambda: f(0, 0, [0]) == [True]),
        t(lambda: f(3, 1, [3, 1, 1]) == [True, True, True]),
        t(lambda: f(2, 0, [0, 0, 3]) == [True, True, False]),
        t(lambda: f(100, 10, [100, 50, 50, 50]) == [True, False, False, False]),
    ]
