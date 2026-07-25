# GAUNTLET-CANARY-62aa2a648d17
def check(ns):
    f = ns.get("filled_sections")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("hello world", 20) == ["hello world"]),
        t(lambda: f("hello\nworld", 20) == ["hello world"]),
        t(lambda: f("aaa bbb ccc", 7) == ["aaa bbb\nccc"]),
        t(lambda: f("", 10) == []),
        t(lambda: f("   \n  \n", 10) == []),
        t(lambda: f("one\n\ntwo", 10) == ["one", "two"]),
        t(lambda: f("one\n  \ntwo", 10) == ["one", "two"]),
        t(lambda: f("a  b\nc", 10) == ["a b c"]),
        t(lambda: f("longword\n\nshort", 5) == ["longword", "short"]),
        t(lambda: f("alpha\nbeta\n\ngamma delta epsilon", 10) == ["alpha beta", "gamma\ndelta\nepsilon"]),
    ]
