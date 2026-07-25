# GAUNTLET-CANARY-6a1c29f05242
def check(ns):
    def t(thunk):
        try:
            return bool(thunk())
        except Exception:
            return False
    return [
        t(lambda: ns.get("ANSWER_1") == [2]),
        t(lambda: ns.get("ANSWER_2") == [1, 2, 3]),
        t(lambda: ns.get("ANSWER_3") == [5]),
        t(lambda: ns.get("ANSWER_4") == []),
        t(lambda: ns.get("ANSWER_5") == [4, 2]),
        t(lambda: ns.get("ANSWER_6") == [2]),
        t(lambda: ns.get("ANSWER_7") == [6, 3]),
        t(lambda: ns.get("ANSWER_8") == [8, 8]),
        t(lambda: ns.get("ANSWER_9") == [7]),
        t(lambda: ns.get("ANSWER_10") == [4, 2]),
    ]
