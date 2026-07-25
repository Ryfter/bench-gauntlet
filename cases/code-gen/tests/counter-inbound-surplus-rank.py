def check(ns):
    f = ns.get("surplus_skus")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(['apple', 'apple', 'banana'], ['apple']) == [('apple', 1), ('banana', 1)]),
        t(lambda: f([], []) == []),
        t(lambda: f(['x'], ['x']) == []),
        t(lambda: f([], ['ghost']) == []),
        t(lambda: f(['solo'], []) == [('solo', 1)]),
        t(lambda: f(['m', 'n', 'm', 'n'], []) == [('m', 2), ('n', 2)]),
        t(lambda: f(['b', 'b', 'b', 'a'], []) == [('b', 3), ('a', 1)]),
        t(lambda: f(['a', 'a', 'a'], ['a', 'a']) == [('a', 1)]),
        t(lambda: f(['╬▒', '╬▒', '╬▓', '╬▓'], ['╬▓', '╬▓', '╬▓']) == [('╬▒', 2)]),
        t(lambda: f(['a', 'a', 'a', 'a', 'b', 'b'], ['a', 'a', 'a']) == [('b', 2), ('a', 1)]),
    ]
