# GAUNTLET-CANARY-94847d49be9f
def check(ns):
    C = ns.get("SpanPool")
    if not callable(C):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def s1():
        p = C(10)
        return p.claim(10) == 0 and p.free_total() == 0 and p.max_contiguous() == 0
    def s2():
        p = C(10)
        a = p.claim(3)
        return a == 0 and p.free_total() == 7 and p.max_contiguous() == 7 and p.is_claimed(0) is True
    def s3():
        p = C(10)
        p.claim(3)
        return p.claim(2) == 3 and p.claim_count() == 2 and p.is_claimed(3) is True
    def s4():
        p = C(8)
        p.claim(3)
        return (
            p.release(0, 3) is True and p.free_total() == 8
            and p.claim_count() == 0 and p.is_claimed(0) is False
        )
    def s5():
        p = C(8)
        p.claim(3)
        return p.release(0, 2) is False and p.release(1, 3) is False and p.free_total() == 5
    def s6():
        p = C(5)
        return p.claim(0) is None and p.claim(-1) is None and p.claim(6) is None and p.free_total() == 5
    def s7():
        p = C(10)
        p.claim(3)
        p.claim(3)
        p.claim(3)
        p.release(3, 3)
        return p.claim(4) is None and p.claim(3) == 3 and p.max_contiguous() == 1
    def s8():
        p = C(10)
        p.claim(4)
        p.claim(4)
        p.claim(2)
        p.release(0, 4)
        p.release(4, 4)
        return p.claim(8) == 0 and p.free_total() == 0 and p.max_contiguous() == 0
    def s9():
        p = C(6)
        p.claim(2)
        p.claim(2)
        p.release(0, 2)
        return p.claim(2) == 0 and p.is_claimed(0) is True and p.claim_count() == 2
    def s10():
        p = C(12)
        a = p.claim(3)
        b = p.claim(3)
        c = p.claim(3)
        d = p.claim(3)
        p.release(3, 3)
        p.release(9, 3)
        p.release(6, 3)
        e = p.claim(9)
        return (
            a == 0 and b == 3 and c == 6 and d == 9
            and e == 3 and p.free_total() == 0
            and p.max_contiguous() == 0 and p.claim_count() == 2
        )
    return [
        t(s1), t(s2), t(s3), t(s4), t(s5),
        t(s6), t(s7), t(s8), t(s9), t(s10),
    ]
