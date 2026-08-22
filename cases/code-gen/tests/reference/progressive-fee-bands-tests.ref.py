def test_suite(impl):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(impl(0, [(5, 9)]) == 0)
    chk(impl(5, []) == 0)
    chk(impl(3, [(5, 2)]) == 6)
    chk(impl(10, [(5, 2), (5, 3)]) == 25)
    chk(impl(3, [(5, 2), (5, 3)]) == 6)
    chk(impl(12, [(5, 1), (3, 4)]) == 33)
    chk(impl(5, [(5, 1), (3, 4)]) == 5)
    chk(impl(8, [(5, 1), (3, 4)]) == 17)
    chk(impl(1, [(0, 5), (10, 2)]) == 2)
    chk(impl(100, [(10, 1)]) == 100)
    return checks
