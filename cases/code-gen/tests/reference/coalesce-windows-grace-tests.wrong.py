def test_suite(impl):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(impl([], 0) == [])
    chk(impl([(0, 5)], 0) == [(0, 5)])
    chk(impl([(0, 5), (3, 8)], 0) == [(0, 8)])
    chk(impl([(1, 3), (0, 2)], 0) == [(0, 3)])
    chk(impl([(0, 2), (2, 4)], 0) == [(0, 4)])
    return checks
