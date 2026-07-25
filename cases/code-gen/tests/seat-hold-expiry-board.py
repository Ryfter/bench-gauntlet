def check(ns):
    f = ns.get('SeatHoldBoard')
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        b = f(3)
        return b.hold(0, 'h1', 10, 5) is True
    def a1():
        b = f(3)
        b.hold(0, 'h1', 10, 5)
        return b.is_free(0, 12) is False
    def a2():
        b = f(3)
        b.hold(0, 'h1', 10, 5)
        return b.free_count(12) == 2
    def a3():
        b = f(3)
        b.hold(1, 'h1', 0, 10)
        return b.release('h1') is True and b.is_free(1, 0) is True
    def a4():
        b = f(2)
        b.hold(0, 'a', 0, 100)
        return b.hold(0, 'b', 50, 10) is False
    def a5():
        b = f(2)
        b.hold(0, 'a', 0, 100)
        return b.hold(1, 'a', 50, 10) is False
    def a6():
        b = f(2)
        b.hold(0, 'a', 10, 5)
        # expires_at = 15; free at now == 15
        return b.is_free(0, 15) is True and b.free_count(15) == 2
    def a7():
        b = f(2)
        b.hold(0, 'a', 10, 5)
        ok = b.hold(0, 'b', 15, 3) is True
        return ok and b.is_free(0, 16) is False and b.release('b') is True
    def a8():
        b = f(2)
        return (
            b.hold(-1, 'x', 0, 5) is False
            and b.hold(2, 'x', 0, 5) is False
            and b.hold(0, 'x', 0, 0) is False
            and b.hold(0, 'x', 0, -3) is False
            and b.is_free(9, 0) is False
        )
    def a9():
        b = f(4)
        b.hold(0, 'a', 0, 10)
        b.hold(2, 'c', 0, 10)
        b.hold(3, 'd', 0, 3)
        # at now=3, seat 3 expires; seats 0,2 still held
        c1 = b.free_count(3) == 2
        b.release('a')
        c2 = b.free_count(3) == 3 and b.is_free(0, 3) is True
        # seat 2 still held until 10
        c3 = b.is_free(2, 9) is False and b.is_free(2, 10) is True
        return c1 and c2 and c3
    return [
        t(lambda: a0()),
        t(lambda: a1()),
        t(lambda: a2()),
        t(lambda: a3()),
        t(lambda: a4()),
        t(lambda: a5()),
        t(lambda: a6()),
        t(lambda: a7()),
        t(lambda: a8()),
        t(lambda: a9()),
    ]
