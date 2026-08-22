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
    chk(impl(4, []) == [(0, 4)])
    chk(impl(1, [0]) == [])
    return checks
