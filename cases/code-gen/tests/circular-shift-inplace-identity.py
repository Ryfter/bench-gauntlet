def check(ns):
    f = ns.get("circular_shift_inplace")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    def case_simple():
        xs = [1, 2, 3, 4]
        r = f(xs, 1)
        return r is xs and xs == [2, 3, 4, 1]
    def case_empty():
        xs = []
        r = f(xs, 5)
        return r is xs and xs == []
    def case_single():
        xs = ["only"]
        r = f(xs, 3)
        return r is xs and xs == ["only"]
    def case_zero():
        xs = [1, 2, 3]
        r = f(xs, 0)
        return r is xs and xs == [1, 2, 3]
    def case_full_turn():
        xs = [1, 2, 3]
        r = f(xs, 3)
        return r is xs and xs == [1, 2, 3]
    def case_wrap():
        xs = [1, 2, 3]
        r = f(xs, 4)
        return r is xs and xs == [2, 3, 1]
    def case_neg():
        xs = [1, 2, 3]
        r = f(xs, -1)
        return r is xs and xs == [3, 1, 2]
    def case_two():
        xs = ["a", "b", "c", "d"]
        r = f(xs, 2)
        return r is xs and xs == ["c", "d", "a", "b"]
    def case_neg_wrap():
        xs = [10, 20, 30, 40]
        r = f(xs, -6)
        return r is xs and xs == [30, 40, 10, 20]
    def case_zeros_dup():
        xs = [0, 0, 1, 0]
        r = f(xs, -2)
        return r is xs and xs == [1, 0, 0, 0]
    return [
        t(case_simple),
        t(case_empty),
        t(case_single),
        t(case_zero),
        t(case_full_turn),
        t(case_wrap),
        t(case_neg),
        t(case_two),
        t(case_neg_wrap),
        t(case_zeros_dup),
    ]
