def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn([], 3, 2) == [])
    chk(fn(["a"], 3, 2) == [["a"]])
    chk(fn(["a", "a", "a"], 3, 1) == [["a", "a", "a"]])
    chk(fn(["a", "a", "a", "a"], 3, 5) == [["a", "a", "a"], ["a"]])
    chk(fn(["a", "b"], 1, 5) == [["a"], ["b"]])
    return checks
