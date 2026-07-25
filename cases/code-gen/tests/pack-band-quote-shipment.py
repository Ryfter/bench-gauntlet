# GAUNTLET-CANARY-db30f7e1cec7
def check(ns):
    f = ns.get("pack_weight_band")
    g = ns.get("quote_shipment")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f(100) == "letter"),
        t(lambda: f(0) == "letter"),
        t(lambda: f(501) == "parcel"),
        t(lambda: f(2001) == "freight"),
        t(lambda: f(-3) == "invalid"),
        t(lambda: g([100, 600], {"letter": 3, "parcel": 8}) == 11),
        t(lambda: f(500) == "letter"),
        t(lambda: f(2000) == "parcel"),
        t(lambda: g([500], {"letter": 3, "parcel": 8}) == 3),
        t(lambda: g([10001, -5, 0], {"letter": 2, "oversize": 50}) == 52),
    ]
