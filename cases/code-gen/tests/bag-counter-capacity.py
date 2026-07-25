def check(ns):
    C = ns.get("BagCounter")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def s1():
        b = C(3)
        return b.check_in("alice") is True and b.count() == 1
    def s2():
        b = C(3)
        b.check_in("alice")
        return b.contains("alice") is True and b.contains("bob") is False
    def s3():
        b = C(3)
        b.check_in("a")
        b.check_in("b")
        return b.remaining() == 1
    def s4():
        b = C(2)
        b.check_in("a")
        return b.check_out("a") is True and b.count() == 0 and b.contains("a") is False
    def s5():
        b = C(3)
        b.check_in("a")
        return b.check_in("a") is False and b.count() == 1
    def s6():
        b = C(2)
        b.check_in("a")
        b.check_in("b")
        return b.check_in("c") is False and b.remaining() == 0 and b.count() == 2
    def s7():
        b = C(2)
        return b.check_in("") is False and b.count() == 0
    def s8():
        b = C(2)
        return b.check_out("ghost") is False and b.count() == 0
    def s9():
        b = C(1)
        b.check_in("a")
        b.check_out("a")
        return b.check_in("a") is True and b.count() == 1
    def s10():
        b = C(2)
        a = b.check_in("x")
        c = b.check_in("y")
        d = b.check_in("z")
        e = b.check_out("x")
        f = b.check_in("z")
        return (
            a is True and c is True and d is False and e is True and f is True
            and b.count() == 2 and b.contains("y") and b.contains("z")
            and (not b.contains("x")) and b.remaining() == 0
        )
    return [
        t(s1), t(s2), t(s3), t(s4), t(s5),
        t(s6), t(s7), t(s8), t(s9), t(s10),
    ]
