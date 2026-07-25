def check(ns):
    C = ns.get("TreeTally")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        tly = C()
        return tly.add("sales") == 1 and tly.own("sales") == 1
    def a1():
        tly = C()
        tly.add("a", 3)
        tly.add("a", 2)
        return tly.own("a") == 5 and tly.rollup("a") == 5
    def a2():
        tly = C()
        return tly.own("missing") == 0 and tly.rollup("missing") == 0
    def a3():
        tly = C()
        tly.add("a/b", 4)
        return tly.own("a") == 0 and tly.rollup("a") == 4 and tly.own("a/b") == 4
    def a4():
        tly = C()
        tly.add("x", 1)
        tly.add("x/y", 2)
        tly.add("x/y/z", 3)
        return tly.rollup("x") == 6 and tly.rollup("x/y") == 5 and tly.rollup("x/y/z") == 3
    def a5():
        tly = C()
        tly.add("a", 1)
        tly.add("ab", 10)
        tly.add("a/b", 2)
        return tly.rollup("a") == 3 and tly.rollup("ab") == 10
    def a6():
        tly = C()
        tly.add("p", 1)
        tly.add("p/q", 2)
        tly.add("p/q/r", 3)
        tly.add("p/s", 4)
        got = tly.clear("p/q")
        return (
            got == 5
            and tly.own("p/q") == 0
            and tly.own("p/q/r") == 0
            and tly.rollup("p") == 5
            and tly.own("p/s") == 4
        )
    def a7():
        tly = C()
        tly.add("m", 2)
        tly.add("m/n", 3)
        tly.clear("m")
        return tly.paths() == [] and tly.rollup("m") == 0
    def a8():
        tly = C()
        tly.add("a/b", 1)
        tly.add("a/c", 1)
        tly.add("a", 1)
        tly.add("b", 1)
        return tly.paths() == ["a", "a/b", "a/c", "b"] and tly.rollup("a") == 3
    def a9():
        tly = C()
        tly.add("ops", 1)
        tly.add("ops/eu", 2)
        tly.add("ops/eu/de", 3)
        tly.add("ops/eu/fr", 4)
        tly.add("ops/us", 5)
        tly.add("ops2", 100)
        if tly.rollup("ops") != 15:
            return False
        if tly.rollup("ops/eu") != 9:
            return False
        if tly.clear("ops/eu") != 9:
            return False
        if tly.rollup("ops") != 6:
            return False
        if tly.own("ops2") != 100 or tly.rollup("ops2") != 100:
            return False
        tly.add("ops/eu/de", 7)
        if tly.rollup("ops") != 13:
            return False
        return tly.paths() == ["ops", "ops/eu/de", "ops/us", "ops2"]
    return [
        t(lambda: a0()), t(lambda: a1()), t(lambda: a2()), t(lambda: a3()), t(lambda: a4()),
        t(lambda: a5()), t(lambda: a6()), t(lambda: a7()), t(lambda: a8()), t(lambda: a9()),
    ]
