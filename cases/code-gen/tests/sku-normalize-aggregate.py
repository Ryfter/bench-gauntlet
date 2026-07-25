def check(ns):
    f = ns.get("normalize_sku")
    g = ns.get("aggregate_skus")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("abc") == "ABC"),
        t(lambda: f("  xy ") == "XY"),
        t(lambda: f("a b") == "AB"),
        t(lambda: g([("a", 1), ("A", 2)]) == {"A": 3}),
        t(lambda: g([("x", 0), ("x", 5)]) == {"X": 5}),
        t(lambda: g([("   ", 3)]) == {}),
        t(lambda: f("a-b") == "AB"),
        t(lambda: g([("a-b", 1), ("AB", 1)]) == {"AB": 2}),
        t(lambda: g([("sku-1", -2), ("SKU1", 4)]) == {"SKU1": 4}),
        t(lambda: g([("a b", 1), ("A-B", 2), ("  ab ", 3)]) == {"AB": 6}),
    ]
