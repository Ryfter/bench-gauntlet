def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn([], 10) == ([], 10))
    chk(fn([3, 3, 3], 10) == ([3, 3, 3], 1))
    chk(fn([5, 5], 10) == ([5, 5], 0))
    chk(fn([11], 10) == ([], 10))
    chk(fn([4, 7, 1], 10) == ([4], 6))
    chk(fn([0, 0, 5], 5) == ([0, 0, 5], 0))
    chk(fn([2, 2, 2], 6) == ([2, 2, 2], 0))
    chk(fn([1, 2, 3], 0) == ([], 0))
    chk(fn([10], 10) == ([10], 0))
    chk(fn([3, 3, 3, 3], 9) == ([3, 3, 3], 0))
    return checks
