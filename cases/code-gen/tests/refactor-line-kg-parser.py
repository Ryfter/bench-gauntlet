def check(ns):
    f = ns.get("line_kg")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("12kg") == 12.0),
        t(lambda: f("500g") == 0.5),
        t(lambda: f("2.5 kg") == 2.5),
        t(lambda: f("0kg") == 0.0),
        t(lambda: f(None) is None),
        t(lambda: f(42) is None),
        t(lambda: f("") == 0.0),
        t(lambda: f("  n/a  ") == 0.0),
        t(lambda: f("  1000 G ") == 1.0),
        t(lambda: f("-1kg") is None and f("kg") is None),
    ]
