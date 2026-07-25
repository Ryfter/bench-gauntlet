def check(ns):
    f = ns.get("reconcile_counts")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f({"a": 5}, {"a": 3}) == {"a": -2}),
        t(lambda: f({"x": 1, "y": 2}, {"x": 1, "y": 4}) == {"x": 0, "y": 2}),
        t(lambda: f({}, {}) == {}),
        t(lambda: f({"a": 3}, {}) == {"a": -3}),
        t(lambda: f({}, {"b": 7}) == {"b": 7}),
        t(lambda: f({"a": 1, "b": 2}, {"a": 1}) == {"a": 0, "b": -2}),
        t(lambda: f({"a": 0}, {"a": 0}) == {"a": 0}),
        t(lambda: f({"a": -5}, {"a": -2}) == {"a": 3}),
        t(lambda: f({"café": 1}, {"café": 2, "naïve": 3}) == {"café": 1, "naïve": 3}),
        t(lambda: f({str(i): i for i in range(50)}, {str(i): i * 2 for i in range(50)}) == {str(i): i for i in range(50)}),
    ]
