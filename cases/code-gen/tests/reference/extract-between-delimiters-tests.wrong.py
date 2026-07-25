def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn("", "[", "]") is None)
    chk(fn("nope", "[", "]") is None)
    chk(fn("[hello]", "[", "]") is not None)
    chk(fn("pre[x]post", "[", "]") is not None)
    chk(fn("x[y", "[", "]") is None)
    chk(fn("<<val>>", "<<", ">>") is not None)
    return checks
