def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn([], 5) == [])
    chk(fn(["hi"], 5) == ["hi"])
    chk(fn(["a", "b"], 10) == ["a b"])
    chk(fn(["to", "be", "or"], 20) == ["to be or"])
    chk(fn(["x", "y", "z"], 10) == ["x y z"])
    return checks
