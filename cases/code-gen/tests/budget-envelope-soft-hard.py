# GAUNTLET-CANARY-dff64b88f988
def check(ns):
    C = ns.get("BudgetEnvelope")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def s1():
        e = C(10, 20)
        return e.spend(5) == "ok" and e.spent() == 5
    def s2():
        e = C(10, 20)
        e.spend(5)
        return e.remaining() == 15
    def s3():
        e = C(10, 20)
        e.spend(4)
        return e.soft_remaining() == 6
    def s4():
        e = C(10, 20)
        e.spend(8)
        return e.refund(3) is True and e.spent() == 5 and e.remaining() == 15
    def s5():
        e = C(10, 20)
        return e.spend(10) == "ok" and e.spend(1) == "soft" and e.spent() == 11
    def s6():
        e = C(5, 10)
        a = e.spend(8)
        return a == "soft" and e.spend(5) == "rejected" and e.spent() == 8
    def s7():
        e = C(5, 10)
        return e.spend(0) == "rejected" and e.spend(-1) == "rejected" and e.spent() == 0
    def s8():
        e = C(5, 10)
        e.spend(3)
        return e.refund(4) is False and e.refund(0) is False and e.spent() == 3
    def s9():
        e = C(10, 30)
        a = e.spend(15)
        return a == "soft" and e.soft_remaining() == 0 and e.spend(1) == "soft" and e.spent() == 16
    def s10():
        e = C(10, 25)
        a = e.spend(10)
        b = e.spend(5)
        e.refund(6)
        c = e.spend(1)
        return (
            a == "ok" and b == "soft" and c == "ok"
            and e.spent() == 10 and e.soft_remaining() == 0 and e.remaining() == 15
        )
    return [
        t(s1), t(s2), t(s3), t(s4), t(s5),
        t(s6), t(s7), t(s8), t(s9), t(s10),
    ]
