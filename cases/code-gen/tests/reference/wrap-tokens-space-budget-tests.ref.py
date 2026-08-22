def test_suite(fn):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(fn([], 5) == [])
    chk(fn(["hi"], 5) == ["hi"])
    chk(fn(["a", "b"], 3) == ["a b"])
    chk(fn(["a", "b"], 2) == ["a", "b"])
    chk(fn(["to", "be", "or"], 5) == ["to be", "or"])
    chk(fn(["hello"], 3) == ["hello"])
    chk(fn(["ab", "cd", "ef"], 5) == ["ab cd", "ef"])
    chk(fn(["ab", "cd"], 4) == ["ab", "cd"])
    chk(fn(["x", "yy", "z"], 4) == ["x yy", "z"])
    chk(fn(["╬▒╬▓", "╬│"], 3) == ["╬▒╬▓", "╬│"])
    return checks
