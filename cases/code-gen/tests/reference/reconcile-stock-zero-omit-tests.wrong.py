def test_suite(impl):
    checks = []
    def chk(cond):
        try:
            checks.append(bool(cond))
        except Exception:
            checks.append(False)
    chk(impl({}, []) == {})
    chk(impl({"a": 3}, []) == {"a": 3})
    chk(impl({"a": 5}, [("a", -2)]) == {"a": 3})
    chk(impl({}, [("z", 4)]) == {"z": 4})
    chk(impl({"a": 1}, [("b", 2)]) == {"a": 1, "b": 2})
    chk(impl({"a": 1}, [("b", 2), ("b", 3)]) == {"a": 1, "b": 5})
    return checks
