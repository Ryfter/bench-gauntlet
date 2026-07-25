def test_suite(impl):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(impl(0, [(5, 9)]) == 0)
    chk(impl(3, [(5, 2)]) == 6)
    chk(impl(3, [(5, 2), (5, 3)]) == 6)
    chk(impl(5, []) == 0)
    chk(impl(5, [(5, 1), (3, 4)]) == 5)
    return checks
