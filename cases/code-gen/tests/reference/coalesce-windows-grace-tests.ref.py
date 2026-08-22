def test_suite(impl):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(impl([], 0) == [])
    chk(impl([(5, 5), (3, 1)], 2) == [])
    chk(impl([(0, 5)], 0) == [(0, 5)])
    chk(impl([(0, 5), (3, 8)], 0) == [(0, 8)])
    chk(impl([(0, 5), (6, 10)], 0) == [(0, 5), (6, 10)])
    chk(impl([(0, 5), (7, 10)], 2) == [(0, 10)])
    chk(impl([(0, 5), (8, 10)], 2) == [(0, 5), (8, 10)])
    chk(impl([(1, 3), (0, 2), (10, 12)], 1) == [(0, 3), (10, 12)])
    chk(impl([(0, 2), (2, 4)], 0) == [(0, 4)])
    chk(impl([(10, 20), (0, 5)], 3) == [(0, 5), (10, 20)])
    return checks
