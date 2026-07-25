def check(ns):
    f = ns.get("build_invoice_lines")
    if not callable(f):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f([("A", 2, 5)]) == [{"sku": "A", "qty": 2, "unit_price": 5, "line_total": 10}]),
        t(lambda: f([("A", 1, 3), ("B", 2, 4)]) == [
            {"sku": "A", "qty": 1, "unit_price": 3, "line_total": 3},
            {"sku": "B", "qty": 2, "unit_price": 4, "line_total": 8},
        ]),
        t(lambda: f([]) == []),
        t(lambda: f([("", 1, 1)]) == []),
        t(lambda: f([(None, 1, 1)]) == []),
        t(lambda: f([("FREE", 1, 0)]) == [{"sku": "FREE", "qty": 1, "unit_price": 0, "line_total": 0}]),
        t(lambda: f([("Z", 0, 9)]) == [{"sku": "Z", "qty": 0, "unit_price": 9, "line_total": 0}]),
        t(lambda: f([("Z", 0, 0)]) == [{"sku": "Z", "qty": 0, "unit_price": 0, "line_total": 0}]),
        t(lambda: f([("A", 2, 5), ("", 3, 1), ("B", 0, 2)]) == [
            {"sku": "A", "qty": 2, "unit_price": 5, "line_total": 10},
            {"sku": "B", "qty": 0, "unit_price": 2, "line_total": 0},
        ]),
        t(lambda: f([("caf├⌐", 3, 0), ("y", 0, 3), ("z", 2, 2)]) == [
            {"sku": "caf├⌐", "qty": 3, "unit_price": 0, "line_total": 0},
            {"sku": "y", "qty": 0, "unit_price": 3, "line_total": 0},
            {"sku": "z", "qty": 2, "unit_price": 2, "line_total": 4},
        ]),
    ]
