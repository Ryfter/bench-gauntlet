def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn("", "[", "]") is None)
    chk(fn("no markers here", "[", "]") is None)
    chk(fn("[hello]", "[", "]") == "hello")
    chk(fn("pre[x]post", "[", "]") == "x")
    chk(fn("a[b[c]d", "[", "]") == "b[c")
    chk(fn("][ok]", "[", "]") == "ok")
    chk(fn("x[y", "[", "]") is None)
    chk(fn("<<val>>", "<<", ">>") == "val")
    chk(fn("a<<b>>c<<d>>", "<<", ">>") == "b")
    chk(fn("[unicode-caf├⌐]", "[", "]") == "unicode-caf├⌐")
    return checks
