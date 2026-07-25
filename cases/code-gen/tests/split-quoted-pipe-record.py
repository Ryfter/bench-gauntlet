# GAUNTLET-CANARY-f0b38b06b346
def check(ns):
    f = ns.get("split_quoted_pipe_record")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("a|b|c") == ["a", "b", "c"]),
        t(lambda: f("only") == ["only"]),
        t(lambda: f("a|b|") == ["a", "b", ""]),
        t(lambda: f("|a") == ["", "a"]),
        t(lambda: f("a||b") == ["a", "", "b"]),
        t(lambda: f("") == [""]),
        t(lambda: f("  a  |  b  ") == ["a", "b"]),
        t(lambda: f('"a|b"|c') == ["a|b", "c"]),
        t(lambda: f('"  keep  "|x') == ["  keep  ", "x"]),
        t(lambda: f('x|"y""z"|w') == ["x", 'y"z', "w"]),
    ]
