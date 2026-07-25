# GAUNTLET-CANARY-379fa2e3f217
def check(ns):
    f = ns.get("merge_ascending")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([1, 3], [2, 4]) == [1, 2, 3, 4]),
        t(lambda: f([], []) == []),
        t(lambda: f([7, 8, 9], []) == [7, 8, 9]),
        t(lambda: f([], [2, 5]) == [2, 5]),
        t(lambda: f([1, 2, 3], [4, 5]) == [1, 2, 3, 4, 5]),
        t(lambda: f([4, 5], [1, 2, 3]) == [1, 2, 3, 4, 5]),
        t(lambda: f([1, 1, 2], [1, 2, 2]) == [1, 1, 1, 2, 2, 2]),
        t(lambda: f([-5, -1, 0], [-3, -2, 4]) == [-5, -3, -2, -1, 0, 4]),
        t(lambda: f([1, 5, 9, 12], [2, 3, 4, 10, 11]) == [1, 2, 3, 4, 5, 9, 10, 11, 12]),
        t(lambda: f([0, 0], [0]) == [0, 0, 0]),
    ]
