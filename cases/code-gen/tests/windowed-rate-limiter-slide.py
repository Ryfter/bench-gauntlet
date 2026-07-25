def check(ns):
    C = ns.get("WindowRateLimiter")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        r = C(2, 10)
        return r.allow(0) is True and r.allow(1) is True and r.allow(2) is False
    def a1():
        r = C(3, 100)
        return r.allow(10) and r.allow(10) and r.allow(10) and (r.allow(10) is False)
    def a2():
        r = C(1, 5)
        r.allow(0)
        return r.allow(3) is False and r.allow(5) is True
    def a3():
        r = C(2, 10)
        r.allow(0)
        r.allow(1)
        return r.counted(1) == 2 and r.counted(10) == 1 and r.counted(11) == 0
    def a4():
        r = C(2, 10)
        r.allow(0)
        r.allow(5)
        return r.allow(10) is True and r.counted(10) == 2
    def a5():
        r = C(2, 10)
        r.allow(0)
        r.allow(5)
        ok = r.allow(10)
        return ok is True and r.allow(10) is False
    def a6():
        r = C(1, 1)
        return r.allow(0) and (r.allow(0) is False) and r.allow(1) and (r.allow(1) is False)
    def a7():
        r = C(3, 4)
        r.allow(0)
        r.allow(1)
        r.allow(2)
        return r.allow(4) is True and r.counted(4) == 3 and r.allow(4) is False
    def a8():
        r = C(2, 10)
        r.allow(100)
        r.allow(101)
        return (
            r.allow(200) is True
            and r.counted(200) == 1
            and r.allow(200) is True
            and r.allow(200) is False
        )
    def a9():
        r = C(2, 5)
        if not (r.allow(3) and r.allow(4) and r.allow(5) is False):
            return False
        if r.allow(8) is not True:
            return False
        if r.counted(8) != 2:
            return False
        if r.allow(9) is not True:
            return False
        if r.counted(9) != 2:
            return False
        if r.allow(9) is not False:
            return False
        return True
    return [
        t(lambda: a0()), t(lambda: a1()), t(lambda: a2()), t(lambda: a3()), t(lambda: a4()),
        t(lambda: a5()), t(lambda: a6()), t(lambda: a7()), t(lambda: a8()), t(lambda: a9()),
    ]
