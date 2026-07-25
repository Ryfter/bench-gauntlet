def check(ns):
    f = ns.get("consecutive_runs")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    import types
    return [
        t(lambda: isinstance(f("a"), types.GeneratorType)),
        t(lambda: not isinstance(f("aa"), list)),
        t(lambda: list(f("aaa")) == [("a", 3)]),
        t(lambda: list(f("")) == []),
        t(lambda: list(f("a")) == [("a", 1)]),
        t(lambda: list(f("aaabbc")) == [("a", 3), ("b", 2), ("c", 1)]),
        t(lambda: list(f("abab")) == [("a", 1), ("b", 1), ("a", 1), ("b", 1)]),
        t(lambda: list(f("\U0001f60a\U0001f60a!")) == [("\U0001f60a", 2), ("!", 1)]),
        t(lambda: list(f("xxxxxy")) == [("x", 5), ("y", 1)]),
        t(lambda: list(f("a" * 20 + "bb")) == [("a", 20), ("b", 2)]),
    ]
