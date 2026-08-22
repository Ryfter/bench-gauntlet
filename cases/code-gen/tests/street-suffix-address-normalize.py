# GAUNTLET-CANARY-c2b96b95d697
def check(ns):
    f = ns.get("expand_suffix")
    g = ns.get("normalize_address")
    if not callable(f) or not callable(g):
        return [False] * 10
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: f("st") == "Street"),
        t(lambda: g("12 Oak ave") == "12 Oak Avenue"),
        t(lambda: f("road") == "Road"),
        t(lambda: g("9 Pine ln") == "9 Pine Lane"),
        t(lambda: f("Plaza") == "Plaza"),
        t(lambda: g("") == ""),
        t(lambda: f("RD") == "Road"),
        t(lambda: g("St James rd") == "St James Road"),
        t(lambda: f("") == ""),
        t(lambda: g("  4  Elm   blvd  ") == "4 Elm Boulevard"),
    ]
