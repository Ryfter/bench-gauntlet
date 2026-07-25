# GAUNTLET-CANARY-57658ee74b83
def check(ns):
    f = ns.get("sliding_windows")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    import types
    def independent():
        src = [10, 20, 30, 40]
        gen = f(src, 2)
        if not isinstance(gen, types.GeneratorType):
            return False
        a = next(gen)
        a[0] = 999
        b = next(gen)
        return b == [20, 30] and src == [10, 20, 30, 40] and a == [999, 20]
    def large_tail():
        windows = list(f(list(range(100)), 3))
        return (
            len(windows) == 98
            and windows[0] == [0, 1, 2]
            and windows[1] == [1, 2, 3]
            and windows[-1] == [97, 98, 99]
        )
    return [
        t(lambda: isinstance(f([1, 2, 3], 2), types.GeneratorType)),
        t(lambda: list(f([1, 2, 3, 4], 2)) == [[1, 2], [2, 3], [3, 4]]),
        t(lambda: list(f([1, 2, 3], 3)) == [[1, 2, 3]]),
        t(lambda: list(f([1, 2, 3], 1)) == [[1], [2], [3]]),
        t(lambda: list(f([], 1)) == []),
        t(lambda: list(f([1, 2], 0)) == []),
        t(lambda: list(f([1, 2], -3)) == []),
        t(lambda: list(f([1, 2], 5)) == []),
        t(lambda: independent()),
        t(lambda: large_tail()),
    ]
