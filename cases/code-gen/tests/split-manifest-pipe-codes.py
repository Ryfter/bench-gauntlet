def check(ns):
    f = ns.get("split_manifest_codes")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("A|B|C") == ["A", "B", "C"]),
        t(lambda: f("ABC") == ["ABC"]),
        t(lambda: f("  X  |  Y  ") == ["X", "Y"]),
        t(lambda: f("╬▒╬▓|╬│╬┤") == ["╬▒╬▓", "╬│╬┤"]),
        t(lambda: f("A|B|C|D|E|F|G|H|I|J") == ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]),
        t(lambda: f("") == []),
        t(lambda: f("A||B") == ["A", "B"]),
        t(lambda: f("|A|B|") == ["A", "B"]),
        t(lambda: f("|||") == []),
        t(lambda: f("  |  ") == []),
    ]
