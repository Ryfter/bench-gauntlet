# GAUNTLET-CANARY-6ed3fd514682
def check(ns):
    f = ns.get("item_checksum")
    g = ns.get("validate_manifest")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("A", 5) == 70),
        t(lambda: f("", 12) == 12),
        t(lambda: f("X", 0) == 88),
        t(lambda: g([], 0) is True),
        t(lambda: g([], 3) is False),
        t(lambda: g([{"sku": "A", "qty": 5, "checksum": 70}], 5) is True),
        t(lambda: g([{"sku": "A", "qty": 5, "checksum": 70}, {"sku": "B", "qty": 2, "checksum": 68}], 7) is True),
        t(lambda: f("AB", 2) == 199 and g([{"sku": "AB", "qty": 2, "checksum": 199}], 2) is True),
        t(lambda: f("BA", 1) == 197 and f("AB", 1) == 198 and f("AB", 1) != f("BA", 1)),
        t(lambda: g([{"sku": "hello", "qty": 1, "checksum": 618}], 1) is True and g([{"sku": "A", "qty": 1, "checksum": 66}, {"sku": "A", "qty": 2, "checksum": 67}], 3) is False and g([{"sku": "", "qty": 1, "checksum": 1}], 1) is False),
    ]
