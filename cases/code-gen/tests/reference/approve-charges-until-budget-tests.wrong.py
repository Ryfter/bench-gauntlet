def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn([], 10) == ([], 10))
    chk(fn([3, 3, 3], 10) == ([3, 3, 3], 1))
    chk(fn([2, 2], 5) == ([2, 2], 1))
    chk(fn([11], 10) == ([], 10))
    chk(fn([1, 2, 3], 0) == ([], 0))
    return checks
