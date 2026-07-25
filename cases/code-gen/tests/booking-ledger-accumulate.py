def check(ns):
    C = ns.get("BookingLedger")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def a0():
        b = C(10)
        return b.book("ann", 3) is True and b.free() == 7 and b.held("ann") == 3
    def a1():
        b = C(5)
        return b.book("x", 0) is False and b.book("x", -2) is False and b.free() == 5
    def a2():
        b = C(4)
        b.book("a", 4)
        return b.book("b", 1) is False and b.free() == 0
    def a3():
        b = C(8)
        b.book("a", 3)
        return b.cancel("a") == 3 and b.free() == 8 and b.held("a") == 0
    def a4():
        b = C(6)
        return b.cancel("nobody") == 0 and b.free() == 6
    def a5():
        b = C(10)
        b.book("a", 4)
        b.book("b", 3)
        return b.free() == 3 and b.held("a") == 4 and b.held("b") == 3
    def a6():
        b = C(10)
        b.book("ann", 2)
        b.book("ann", 3)
        return b.held("ann") == 5 and b.free() == 5
    def a7():
        b = C(9)
        b.book("a", 5)
        b.book("b", 4)
        b.cancel("a")
        return b.free() == 5 and b.book("c", 5) is True and b.free() == 0
    def a8():
        b = C(7)
        b.book("a", 3)
        b.book("a", 2)
        b.book("a", 2)
        return b.held("a") == 7 and b.book("a", 1) is False and b.cancel("a") == 7
    def a9():
        b = C(12)
        b.book("p", 5)
        b.book("q", 5)
        b.book("p", 2)
        return (
            b.held("p") == 7
            and b.free() == 0
            and b.book("r", 1) is False
            and b.cancel("q") == 5
            and b.free() == 5
        )
    return [
        t(lambda: a0()), t(lambda: a1()), t(lambda: a2()), t(lambda: a3()), t(lambda: a4()),
        t(lambda: a5()), t(lambda: a6()), t(lambda: a7()), t(lambda: a8()), t(lambda: a9()),
    ]
