def check(ns):
    f = ns.get("lazy_merge_sorted")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def lazy_two_sources():
        c = [0]
        def gen(start):
            x = start
            while True:
                c[0] += 1
                yield x
                x += 10
        g = f(gen(0), gen(1))
        first = next(g)
        return first == 0 and c[0] == 2
    def lazy_single_partial():
        c = [0]
        def gen():
            for i in range(1000):
                c[0] += 1
                yield i
        g = f(gen())
        next(g)
        next(g)
        next(g)
        return c[0] == 3
    def early_stop_multi():
        c = [0]
        def gen(step):
            x = 0
            while True:
                c[0] += 1
                yield x
                x += step
        g = f(gen(2), gen(3), gen(5))
        got = [next(g) for _ in range(4)]
        return got == [0, 0, 0, 2] and c[0] <= 6
    return [
        t(lambda: list(f([1, 3], [2, 4])) == [1, 2, 3, 4]),
        t(lambda: list(f()) == []),
        t(lambda: list(f([])) == []),
        t(lambda: list(f([1, 2, 3])) == [1, 2, 3]),
        t(lambda: list(f([1, 4], [2, 5], [3, 6])) == [1, 2, 3, 4, 5, 6]),
        t(lambda: list(f([1, 3], [1, 2])) == [1, 1, 2, 3]),
        t(lambda: list(f([-4, -1, 2], [-3, 0, 5])) == [-4, -3, -1, 0, 2, 5]),
        t(lazy_two_sources),
        t(lazy_single_partial),
        t(early_stop_multi),
    ]
