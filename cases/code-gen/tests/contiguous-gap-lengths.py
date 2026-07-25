def check(ns):
    f = ns.get("contiguous_gap_lengths")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("###") == []),
        t(lambda: f("...") == [3]),
        t(lambda: f("") == []),
        t(lambda: f(".") == [1]),
        t(lambda: f(".#.") == [1, 1]),
        t(lambda: f("##..#.#.") == [2, 1, 1]),
        t(lambda: f("...#..") == [3, 2]),
        t(lambda: f("X.Y.Z") == [1, 1]),
        t(lambda: f("..α..β.") == [2, 2, 1]),
        t(lambda: f("." * 200 + "#" + "." * 3) == [200, 3]),
    ]
