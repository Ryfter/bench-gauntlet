# GAUNTLET-CANARY-8b94d9bc3c10
def check(ns):
    C = ns.get("HoldBoard")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def s1():
        b = C(3)
        return b.hold(0, "ann") is True and b.status(0) == "held" and b.holder_of(0) == "ann"
    def s2():
        b = C(3)
        b.hold(1, "bob")
        return b.free_count() == 2
    def s3():
        b = C(2)
        b.hold(0, "ann")
        return b.confirm("ann") is True and b.status(0) == "booked" and b.holder_of(0) == "ann"
    def s4():
        b = C(2)
        b.hold(0, "ann")
        return (
            b.cancel("ann") is True and b.status(0) == "free"
            and b.holder_of(0) is None and b.free_count() == 2
        )
    def s5():
        b = C(2)
        b.hold(0, "ann")
        return b.hold(0, "bob") is False and b.holder_of(0) == "ann"
    def s6():
        b = C(3)
        b.hold(0, "ann")
        return b.hold(1, "ann") is False and b.status(1) == "free" and b.free_count() == 2
    def s7():
        b = C(2)
        b.hold(0, "ann")
        b.confirm("ann")
        return b.confirm("ann") is False and b.confirm("ghost") is False and b.status(0) == "booked"
    def s8():
        b = C(2)
        b.hold(0, "ann")
        b.confirm("ann")
        ok = b.cancel("ann")
        return ok is True and b.status(0) == "free" and b.hold(0, "bob") is True and b.holder_of(0) == "bob"
    def s9():
        b = C(2)
        return (
            b.hold(-1, "a") is False and b.hold(2, "a") is False and b.hold(0, "") is False
            and b.status(-1) is None and b.status(2) is None
        )
    def s10():
        b = C(3)
        b.hold(0, "a")
        b.hold(1, "b")
        b.confirm("a")
        b.cancel("b")
        b.hold(1, "c")
        b.hold(2, "b")
        return (
            b.status(0) == "booked" and b.status(1) == "held" and b.status(2) == "held"
            and b.holder_of(1) == "c" and b.free_count() == 0
            and b.hold(0, "x") is False
            and b.hold(1, "a") is False
            and b.cancel("a") is True and b.status(0) == "free" and b.free_count() == 1
        )
    return [
        t(s1), t(s2), t(s3), t(s4), t(s5),
        t(s6), t(s7), t(s8), t(s9), t(s10),
    ]
