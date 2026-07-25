def check(ns):
    f = ns.get("sku_qty_totals")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(["SKU=A1 qty=3"]) == [("A1", 3)]),
        t(lambda: f(["SKU=A1 qty=2", "SKU=A1 qty=5"]) == [("A1", 7)]),
        t(lambda: f([]) == []),
        t(lambda: f(["nope", "SKU= qty=1", "SKU=X qty=abc"]) == []),
        t(lambda: f(["SKU=A qty=3", "SKU=B qty=3"]) == [("A", 3), ("B", 3)]),
        t(lambda: f(["SKU=A qty=5", "SKU=A qty=-2"]) == [("A", 3)]),
        t(lambda: f(["SKU=A qty=1 SKU=B qty=2"]) == [("B", 2), ("A", 1)]),
        t(lambda: f(["SKU=Z qty=0"]) == []),
        t(lambda: f(["SKU=A qty=5", "SKU=A qty=-5"]) == []),
        t(lambda: f(["prefix SKU=M9 qty=4 mid SKU=M9 qty=-1 end", "SKU=B2 qty=10 SKU=A1 qty=10"]) == [("A1", 10), ("B2", 10), ("M9", 3)]),
    ]
