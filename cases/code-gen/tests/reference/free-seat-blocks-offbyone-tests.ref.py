def test_suite(impl):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(impl(0, []) == [])
    chk(impl(5, []) == [(0, 5)])
    chk(impl(5, [0, 1, 2, 3, 4]) == [])
    chk(impl(10, [2, 3, 7]) == [(0, 2), (4, 3), (8, 2)])
    chk(impl(5, [1, 1, 3]) == [(0, 1), (2, 1), (4, 1)])
    chk(impl(4, [-1, 99, 2]) == [(0, 2), (3, 1)])
    chk(impl(3, [1]) == [(0, 1), (2, 1)])
    chk(impl(1, []) == [(0, 1)])
    chk(impl(1, [0]) == [])
    chk(impl(6, [0, 5]) == [(1, 4)])
    return checks
