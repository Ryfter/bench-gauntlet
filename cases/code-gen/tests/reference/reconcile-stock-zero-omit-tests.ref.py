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
    chk(impl({"a": 5}, [("a", -2), ("a", -1)]) == {"a": 2})
    chk(impl({"x": 3, "y": 1}, [("y", -1)]) == {"x": 3})
    chk(impl({}, [("z", -4)]) == {"z": -4})
    chk(impl({"a": 1}, [("b", 2), ("b", 3)]) == {"a": 1, "b": 5})
    chk(impl({"k": 2}, [("k", -5)]) == {"k": -3})
    chk(impl({"m": 1, "n": 2}, [("m", -1), ("n", 0)]) == {"n": 2})
    chk(impl({"a": 0, "b": 2}, []) == {"b": 2})
    return checks
